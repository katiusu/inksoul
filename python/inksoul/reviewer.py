"""文学质量审查：只输出「可解释的局部问题」，不输出单一总分。

判据来源
--------
- 机械复用嫌疑：``fingerprint.FingerprintEngine`` 的 cluster 证据（freq / 跨段 / 间距变异）。
- **修辞性重复豁免**：J3（显式修辞标记）命中且句式变异小的簇不报问题——
  这是「作者有意的结构复现」，见 docs/syntax_fingerprint.md §6。
- 相邻句式雷同：相邻小句骨架相似度 ≥ NEAR_DUP_SIM。
- 句首重复：同段内同一起句词/结构 ≥ OPENING_MIN_RUN 次。
- 对话标签同质：同一说话动词占比过高。
- 情绪直陈：``感到/觉得/心里`` + 情绪词的直白表达（启发式，误报率高，标低置信）。

每条问题都带 ``evidence``，方便人工复核；severity ∈ [0,1]，没有总分。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import fingerprint as fp
from .errors import InkSoulError
from .text_processor import Document

#: 相邻小句「雷同」阈值（未标定）
NEAR_DUP_SIM = 0.90
#: 同段句首重复触发次数
OPENING_MIN_RUN = 3
#: 对话标签同质：占比 ≥ 该值且总数 ≥ 3
SPEECH_VERB_SHARE = 0.6
#: 情绪直陈的触发词
EMOTION_CUES = ("感到", "觉得", "心里", "心中", "一阵", "涌起", "袭来")
#: 情绪词（粗表，只用于定位，不用于判定）
EMOTION_WORDS = ("开心", "高兴", "难过", "悲伤", "愤怒", "生气", "害怕", "恐惧",
                 "紧张", "焦虑", "委屈", "失落", "绝望", "兴奋", "平静", "温暖")

KIND_MECHANICAL = "机械复用"
KIND_ADJACENT = "相邻句式雷同"
KIND_OPENING = "句首重复"
KIND_DIALOGUE = "对话标签同质"
KIND_EMOTION = "情绪直陈"


@dataclass
class LiteraryIssue:
    """一条可解释的问题。"""

    kind: str
    clause_id: str
    text: str
    severity: float
    suggestion: str
    evidence: dict = field(default_factory=dict)
    paragraph_id: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = round(float(self.severity), 2)
        return d


@dataclass
class ReviewReport:
    """审查结果：问题清单 + 豁免清单 + 说明。"""

    issues: list[LiteraryIssue] = field(default_factory=list)
    exempted: list[dict] = field(default_factory=list)
    verdict: str = "未见明显机械复用"
    counts: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def blocking(self) -> list[LiteraryIssue]:
        """severity ≥ 0.6 的问题（建议修订）。"""
        return [i for i in self.issues if i.severity >= 0.6]

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "counts": dict(self.counts),
            "issues": [i.as_dict() for i in self.issues],
            "exempted": list(self.exempted),
            "notes": list(self.notes),
        }


def _has_j3_exemption(cluster) -> str:
    """返回豁免理由；无豁免返回空串。"""
    for line in getattr(cluster, "evidence", []) or []:
        if "J3" in line:
            return line
    return ""


def _clause_texts(doc: Document) -> dict[str, tuple]:
    out = {}
    for para in doc.paragraphs:
        for sent in para.sentences:
            for cl in sent.clauses:
                out[cl.id] = (cl.text, para.id, sent.id)
    return out


def review(doc: Document, *, fingerprint_report: fp.FingerprintReport | None = None,
           diversity=None, style=None, narrative=None,
           engine: fp.FingerprintEngine | None = None) -> ReviewReport:
    """执行审查。所有可选报告缺省时按需自算（缺模块就跳过对应规则）。"""
    clauses_all = list(getattr(doc, "clauses", None) or [])
    if not any(c.token_count >= 2 for c in clauses_all):
        raise InkSoulError(
            "没有可审查的文本（全是标点或单字片段）",
            hint="确认输入是中文正文；样本过短时分析结果没有统计意义",
        )
    engine = engine or fp.FingerprintEngine()
    report = fingerprint_report or engine.analyze(doc)
    texts = _clause_texts(doc)
    issues: list[LiteraryIssue] = []
    exempted: list[dict] = []
    notes: list[str] = []

    # 1) 机械复用嫌疑（含 J3 豁免）
    for cluster in report.suspects:
        reason = _has_j3_exemption(cluster)
        if reason:
            exempted.append({
                "signature": cluster.signature,
                "freq": cluster.freq,
                "reason": reason,
                "examples": [m.text for m in cluster.members[:3]],
            })
            continue
        members = list(cluster.members)
        anchor = members[0]
        text, para_id, _sent = texts.get(anchor.id, (anchor.text, "", ""))
        issues.append(LiteraryIssue(
            kind=KIND_MECHANICAL, clause_id=anchor.id, text=text,
            severity=0.7, paragraph_id=para_id,
            suggestion="同一骨架反复出现：改结构而非换词——拆成两个小句、"
                       "调整状语位置，或让小句承担不同功能",
            evidence={"signature": cluster.signature, "freq": cluster.freq,
                      "para_spread": cluster.para_spread,
                      "examples": [m.text for m in members[:4]],
                      "clause_ids": [m.id for m in members[:12]],
                      "evidence": list(getattr(cluster, "evidence", []) or [])[:4]},
        ))

    # 2) 相邻句式雷同
    clauses = list(doc.clauses)
    for prev, cur in zip(clauses, clauses[1:]):
        if prev.sentence_id != cur.sentence_id:
            continue
        sim = fp.similarity(prev.skel, cur.skel)
        if sim >= NEAR_DUP_SIM and len(prev.skel) >= 3 and len(cur.skel) >= 3:
            issues.append(LiteraryIssue(
                kind=KIND_ADJACENT, clause_id=cur.id, text=cur.text, severity=0.55,
                suggestion="相邻两句骨架几乎一样：换主语位置或改一句为短句/长句",
                evidence={"prev": prev.text, "sim": round(sim, 3)},
            ))

    # 3) 同段句首重复
    for para in doc.paragraphs:
        openings: dict[str, list] = {}
        for sent in para.sentences:
            if not sent.clauses:
                continue
            head_tokens = [t for t in sent.clauses[0].tokens if t.norm != "P"]
            key = head_tokens[0].word if head_tokens else ""
            openings.setdefault(key, []).append(sent)
        for key, sents in openings.items():
            if len(sents) >= OPENING_MIN_RUN and key.strip():
                issues.append(LiteraryIssue(
                    kind=KIND_OPENING, clause_id=sents[0].clauses[0].id,
                    text=sents[0].text, severity=0.45, paragraph_id=para.id,
                    suggestion=f"段内 {len(sents)} 句都以「{key}」起句：至少换一句起句方式",
                    evidence={"opening": key, "count": len(sents),
                              "sentences": [s.text[:24] for s in sents[:4]]},
                ))

    # 4) 对话标签同质
    if narrative is not None:
        counts = getattr(narrative, "speech_verb_counts", {}) or {}
        total = getattr(narrative, "speech_verb_total", 0) or sum(counts.values())
        if total >= 3 and counts:
            verb, n = max(counts.items(), key=lambda kv: kv[1])
            share = n / max(1, total)
            if share >= SPEECH_VERB_SHARE:
                issues.append(LiteraryIssue(
                    kind=KIND_DIALOGUE, clause_id="", text=f"「{verb}」×{n}",
                    severity=0.5,
                    suggestion=f"说话动词「{verb}」占 {share:.0%}：改用动作、停顿或直接引语承接",
                    evidence={"counts": dict(counts), "total": total, "share": round(share, 3)},
                ))

    # 5) 情绪直陈（低置信，只提示）
    for cl in clauses:
        hit_cue = [w for w in EMOTION_CUES if w in cl.text]
        hit_word = [w for w in EMOTION_WORDS if w in cl.text]
        if hit_cue and hit_word:
            issues.append(LiteraryIssue(
                kind=KIND_EMOTION, clause_id=cl.id, text=cl.text, severity=0.3,
                suggestion="情绪被直接命名：换成动作、生理反应或环境侧写，让读者自己读出来",
                evidence={"cue": hit_cue, "emotion_word": hit_word,
                          "confidence": "低（词表启发式，未标定）"},
            ))

    if not getattr(report, "suspects", None):
        notes.append("该文本未产生机械复用候选（样本过短或确实没有重复）")
    if style is None or diversity is None or narrative is None:
        notes.append("部分分析报告未提供：对话/文体相关规则已跳过")
    notes.append("severity 为启发式排序用，不是文学价值评分；阈值均未标定")

    counts = {}
    for issue in issues:
        counts[issue.kind] = counts.get(issue.kind, 0) + 1
    if any(i.severity >= 0.6 for i in issues):
        verdict = "存在疑似机械复用，建议局部修订"
    elif issues:
        verdict = "未见结构性重复，仅有少量表达提示"
    else:
        verdict = "未见明显机械复用"

    return ReviewReport(issues=issues, exempted=exempted, verdict=verdict,
                        counts=counts, notes=notes)
