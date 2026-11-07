"""AI 味标记层：中文「修辞-语法」标记的密度测量。

依据
----
- Reinhart 等 2025 (PNAS)：LLM 与人类的差异是**特征组合**而非单一特征；GPT-4o 相对人类
  现在分词从句 5.3×、名词化 2.1×、短语并列 1.9×——所以本模块按「标记族」分别计数，
  不合成单一 AI 分数（ADR-2）。
- Muñoz-Ortiz 等 2024：句法与依存层比句长更稳；因此标记层只测句内结构，不重复句长统计。
- O'Sullivan 2025 / Li & Zhang 2025：特征清单可迁移，但**判定器目标不可迁移**——
  本模块只给「相对人类基线分位数的位置」，不说「这是 AI 写的」。

中文清单不是 Biber 66 类的翻译，而是按中文可观测结构重建：
轻动词+名词化、定语链嵌套、顿号并列堆叠、无施事被动、论述型连接词、评价性抽象、
比喻模板、四字格堆叠。

用法
----
    from inksoul.markers import analyze_markers, compare_to_baseline
    rep = analyze_markers(doc)
    rows = compare_to_baseline(rep, load_baseline())
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

#: 标记族：键 → 中文名（顺序即输出顺序）
KIND_NAMES: dict[str, str] = {
    "NOM": "动词名词化/轻动词框架",
    "ATTR": "定语链嵌套",
    "PARALLEL": "并列堆叠",
    "PASSIVE": "受事/被动框架",
    "CONNECTIVE": "论述型连接词",
    "ABSTRACT": "评价性抽象",
    "SIMILE": "比喻模板",
    "IDIOM": "四字格堆叠",
}

KINDS: tuple[str, ...] = tuple(KIND_NAMES)

#: 每千字密度低于该叙述字数时不给结论
MIN_NARRATIVE_CHARS = 400
#: 低于此叙述字数时改用泊松尾部检验（密度方差过大，分位数不可靠）
SHORT_WINDOW_CHARS = 1200

QUOTE_CHARS = "“”「」『』"

_NOM_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"对[^，。；！？]{1,10}(?:进行|加以|予以|开展|实施)"), "对…进行"),
    (re.compile(r"(?:进行|加以|予以|给予|作出|开展|实施|实现)[^，。；！？]{0,6}"
                r"(?:分析|处理|研究|讨论|总结|评价|说明|描述|推动|调整|改善|提升|优化|"
                r"梳理|构建|打造|呈现|展现|把握|落实|推进)"), "轻动词+名词化动词"),
    (re.compile(r"(?:的|了)(?:过程|方式|手段|层面|维度|机制|逻辑|结构|体系|格局|趋势)"), "抽象框架词"),
)

#: 抽象后缀：只收长度 ≥3 的词，避免「温度」「变化」这类日常词
_NOM_SUFFIXES = ("性", "化", "层面", "维度", "机制", "逻辑", "格局", "趋势", "体系")

_ATTR_CHAIN = re.compile(r"(?:[^，。；！？、\s“”「」『』]{1,6}的){2,}")

_PARALLEL = re.compile(r"[^，。；！？、\s]{1,8}、[^，。；！？、\s]{1,8}、[^，。；！？、\s]{1,8}")

_PASSIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"为[^，。；！？]{1,8}所[一-龥]{1,4}"), "为…所"),
    (re.compile(r"(?:受到|遭到|遭受|备受|饱受)"), "受/遭"),
    (re.compile(r"被[^，。；！？]{0,6}[一-龥]{1,4}"), "被字结构"),
)

#: 论述型连接词：只收书面议论文/说明文高频、小说叙述低频的
_CONNECTIVES: tuple[str, ...] = (
    "然而", "因此", "此外", "同时", "总之", "综上", "由此可见", "首先", "其次", "再次",
    "最后", "值得注意的是", "换句话说", "换言之", "与此同时", "不仅如此", "尽管如此",
    "某种意义上", "从某种意义上", "也就是说", "进一步说", "在此基础上", "正因为如此",
)

_ABSTRACT_PHRASES: tuple[str, ...] = (
    "一种", "某种", "某种程度上", "某种意义上", "在一定程度上", "体现了", "展现了",
    "呈现出", "构成了", "意味着", "本质上", "无疑是", "不可否认", "显而易见",
    "值得注意", "在此基础上", "进一步说", "可以说", "的体现", "的象征", "的缩影",
    "的写照", "的存在",
)

_SIMILE = re.compile(
    r"(?:仿佛|宛如|犹如|好似|宛若|如同|像是)[^，。；！？]{0,14}(?:一般|一样|似的)"
)

_OPENING_STRIP = " \t\u3000“”「」『』（(—…·"


@dataclass
class MarkerHit:
    """一个标记命中：族、标签、所在小句、上下文。"""

    kind: str
    label: str
    clause_id: int
    text: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "label": self.label,
                "clause_id": self.clause_id, "text": self.text}


@dataclass
class MarkerReport:
    """标记层报告：计数 + 每千字密度 + 命中样例。"""

    chars: int = 0
    narrative_chars: int = 0
    dialogue_chars: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    narrative_counts: dict[str, int] = field(default_factory=dict)
    per_1000: dict[str, float] = field(default_factory=dict)
    hits: list[MarkerHit] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "chars": self.chars,
            "narrative_chars": self.narrative_chars,
            "dialogue_chars": self.dialogue_chars,
            "counts": dict(self.counts),
            "narrative_counts": dict(self.narrative_counts),
            "per_1000": dict(self.per_1000),
            "hits": [h.as_dict() for h in self.hits],
            "notes": list(self.notes),
        }


def _is_quoted(text: str) -> bool:
    return any(ch in text for ch in QUOTE_CHARS)


def _clause_matches(text: str) -> Iterable[tuple[str, str, str]]:
    """返回 (kind, label, matched_text)。"""
    for pat, label in _NOM_PATTERNS:
        for m in pat.finditer(text):
            yield "NOM", label, m.group(0)
    for m in _ATTR_CHAIN.finditer(text):
        yield "ATTR", "的" * m.group(0).count("的"), m.group(0)
    for m in _PARALLEL.finditer(text):
        yield "PARALLEL", "顿号并列", m.group(0)
    for pat, label in _PASSIVE_PATTERNS:
        for m in pat.finditer(text):
            yield "PASSIVE", label, m.group(0)
    for phrase in _ABSTRACT_PHRASES:
        if phrase in text:
            yield "ABSTRACT", phrase, phrase
    for m in _SIMILE.finditer(text):
        yield "SIMILE", "比喻框架", m.group(0)


def _starts_with_connective(text: str) -> str:
    head = text.lstrip(_OPENING_STRIP)
    for word in _CONNECTIVES:
        if head.startswith(word):
            return word
    return ""


def analyze_markers(doc: Any, *, max_hits: int = 120) -> MarkerReport:
    """测量一篇 Document 的标记密度。

    叙述句（不含引号）与对话句分开统计：AI 味集中在叙述层，对话会稀释密度。
    样本不足时（叙述 < MIN_NARRATIVE_CHARS）退回全文口径并写 note。
    """
    chars = len(getattr(doc, "text", "") or "")
    narr_counts = {k: 0 for k in KINDS}
    all_counts = {k: 0 for k in KINDS}
    hits: list[MarkerHit] = []
    narrative_chars = 0
    dialogue_chars = 0
    narr_sents = 0
    conn_sents = 0

    for sent in getattr(doc, "sentences", []) or []:
        quoted = _is_quoted(sent.text)
        if quoted:
            dialogue_chars += len(sent.text)
        else:
            narrative_chars += len(sent.text)
            narr_sents += 1
            word = _starts_with_connective(sent.text)
            if word:
                conn_sents += 1
                narr_counts["CONNECTIVE"] += 1
                all_counts["CONNECTIVE"] += 1
                if len(hits) < max_hits:
                    hits.append(MarkerHit("CONNECTIVE", "句首「%s」" % word,
                                          sent.clauses[0].id if sent.clauses else -1,
                                          sent.text[:60]))

        for cl in sent.clauses:
            text = cl.text
            matched = list(_clause_matches(text))
            # token 层：抽象后缀 + 四字格
            for tok in cl.tokens:
                word = tok.word
                if not word or tok.is_punct:
                    continue
                # jieba 的 'l'（习用语）会把「捕捉到/脑海中/没多久」这类常见搭配也算进来，
                # 噪声远大于信号，只保留 'i'（成语/四字格）。
                if tok.pos == "i" and len(word) >= 4:
                    matched.append(("IDIOM", "四字格「%s」" % word, word))
                if len(word) >= 3 and word.endswith(_NOM_SUFFIXES):
                    matched.append(("NOM", "抽象后缀「%s」" % word, word))
            for kind, label, text_hit in matched:
                all_counts[kind] += 1
                if not quoted:
                    narr_counts[kind] += 1
                if len(hits) < max_hits:
                    hits.append(MarkerHit(kind=kind, label=label,
                                          clause_id=cl.id, text=text[:60]))

    notes: list[str] = []
    base = narr_counts
    denom = narrative_chars
    if narrative_chars < MIN_NARRATIVE_CHARS:
        notes.append(
            "叙述字数仅 %d（阈值 %d）：密度退回全文口径，只作参考" % (narrative_chars, MIN_NARRATIVE_CHARS)
        )
        base = all_counts
        denom = chars
    per_1000 = {k: (round(base[k] * 1000.0 / denom, 2) if denom else 0.0) for k in KINDS}

    if narr_sents:
        notes.append("叙述句 %d 句，其中 %d 句以论述型连接词起句（%.1f%%）"
                     % (narr_sents, conn_sents, 100.0 * conn_sents / narr_sents))
    notes.append("密度单位＝每千字标记次数；叙述句与对话句分开统计；不输出 AI 概率")
    return MarkerReport(chars=chars, narrative_chars=narrative_chars,
                        dialogue_chars=dialogue_chars, counts=all_counts,
                        narrative_counts=dict(base), per_1000=per_1000,
                        hits=hits, notes=notes)


def load_baseline(path: str | None = None) -> dict:
    """读人类基线分位数文件（缺省用包内 data/marker_baseline_zh.json）。"""
    import json
    import os

    if not path:
        path = os.path.join(os.path.dirname(__file__), "data", "marker_baseline_zh.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def baseline_rows(baseline: dict, genre: str = "网文") -> dict[str, dict] | None:
    genres = (baseline or {}).get("genres") or {}
    row = genres.get(genre) or genres.get("all")
    return (row or {}).get("per_1000") or None


def _poisson_level(count: int, rate_p99: float, n_chars: int) -> tuple[str, float | None]:
    """短样本判定：以人类 p99 密度为泊松均值，看「出现这么多次」有多罕见。

    400 字里一条「被」= 2.5/千字，看着超过 p90，但对 lam=2.3 的泊松而言
    P(X≥1)≈0.9，完全不构成证据；6 条才算异常。返回 (level, P(X≥count))。
    """
    if n_chars <= 0 or count <= 0:
        return "ok", None
    lam = max(rate_p99, 0.0) * n_chars / 1000.0
    if lam <= 0:
        return ("very_high", 0.0) if count >= 3 else ("ok", None)
    p_le = 0.0
    term = math.exp(-lam)
    for k in range(0, count):
        p_le += term
        term *= lam / (k + 1)
    p_ge = max(0.0, 1.0 - p_le)
    if count >= 3 and p_ge < 0.01:
        return "very_high", p_ge
    if count >= 3 and p_ge < 0.05:
        return "high", p_ge
    return "ok", p_ge


def compare_to_baseline(report: MarkerReport, baseline: dict | None,
                        genre: str = "网文") -> list[dict]:
    """把密度放到人类基线分布上看位置：ok / high（>p90）/ very_high（>p99）。"""
    rows = baseline_rows(baseline or {}, genre)
    if not rows:
        return []
    # 样本长度决定判定方式，而不是一刀切：
    #   叙述 < MIN_NARRATIVE_CHARS（400）→ 不判定，insufficient
    #   叙述 < SHORT_WINDOW_CHARS（1200）→ 泊松尾部检验（少量出现不构成证据）
    #   否则按 3000 字块分位数
    n_chars = int(getattr(report, "narrative_chars", 0))
    insufficient = n_chars < MIN_NARRATIVE_CHARS
    out: list[dict] = []
    for kind in KINDS:
        stats = rows.get(kind) or {}
        value = float(report.per_1000.get(kind, 0.0))
        count = int((report.narrative_counts or {}).get(kind, 0))
        p50 = float(stats.get("p50", 0.0))
        p90 = float(stats.get("p90", 0.0))
        p99 = float(stats.get("p99", 0.0))
        method = "quantile"
        p_ge = None
        if p90 <= 0 or insufficient:
            level = "ok"
        elif n_chars < SHORT_WINDOW_CHARS:
            method = "poisson"
            level, p_ge = _poisson_level(count, p99, n_chars)
        elif value > p99:
            level = "very_high"
        elif value > p90:
            level = "high"
        else:
            level = "ok"
        out.append({
            "kind": kind, "name": KIND_NAMES[kind], "value": round(value, 2),
            "count": count, "method": method,
            "p_ge": None if p_ge is None else round(p_ge, 4),
            "expected": round(p99 * n_chars / 1000.0, 2) if method == "poisson" else None,
            "p50": round(p50, 2), "p90": round(p90, 2), "p99": round(p99, 2),
            "ratio_p90": round(value / p90, 2) if p90 else None, "level": level,
            "insufficient": insufficient,
        })
    return out


#: 每族一条改写方向（供 reviewer / 闸门引用）
SUGGESTIONS: dict[str, str] = {
    "NOM": "把「对…进行/作出…」拆成动词直接落地的句子：「他推开窗」而不是「他对窗户进行了推开」",
    "ATTR": "拆定语链：连续两个以上的「的」通常能断成两句或改成并列动作",
    "PARALLEL": "顿号并列收到两项以内，第三项改成独立小句",
    "PASSIVE": "给动作补回施事，或把「被/受到」改成主动句",
    "CONNECTIVE": "删掉句首的「然而/因此/此外/同时」——小说里因果关系让读者自己接",
    "ABSTRACT": "把「一种/某种/体现了」换成具体动作或物件",
    "SIMILE": "比喻只在能带来新信息时留；「仿佛…一般」这种框架容易模板化",
    "IDIOM": "四字格连着堆会压掉动作节奏，一段最多留一个",
}


def count_tags(text: str) -> dict[str, int]:
    """轻量计数：只数句内结构标记，不分叙述/对话、不碰 jieba。

    与 analyze_markers 的区别：不算密度、不做词性标注（IDIOM 恒为 0），
    用于修订后的**局部复检**——比较同一窗口改写前后的标记总量。
    """
    counts = {k: 0 for k in KINDS}
    body = text or ""
    for clause in re.split(r"[，。；！？、\s]+", body):
        if not clause:
            continue
        for kind, _label, _hit in _clause_matches(clause):
            counts[kind] += 1
    for sent in re.split(r"[。！？\n]+", body):
        if _starts_with_connective(sent):
            counts["CONNECTIVE"] += 1
    return counts


def total_tags(text: str) -> int:
    """窗口内标记总数（D1 局部复检用）。"""
    return sum(count_tags(text).values())


def verdict_of(rows: list[dict]) -> tuple[str, list[dict]]:
    """单一判定源：内置闸门与 reviewer 共用同一套 FAIL 规则。

    - 任一标记族 > 人类 p99 → FAIL
    - 两族及以上 > 人类 p90 → FAIL
    - 叙述不足（全部 insufficient）→ SKIP，不判定
    - 其余 → PASS
    返回 (verdict, 责任族)：FAIL 时责任族即 reviewer 应判 blocking 的那些族，
    这样「闸门 PASS」与「标记类阻断为 0」永远同真同假（P0-3）。
    """
    if not rows:
        return "NO_BASELINE", []
    if all(r.get("insufficient") for r in rows):
        return "SKIP", []
    very_high = [r for r in rows if r["level"] == "very_high"]
    high = [r for r in rows if r["level"] == "high"]
    if very_high:
        return "FAIL", very_high
    if len(high) >= 2:
        return "FAIL", high
    return "PASS", []


def gate_text(text: str, *, genre: str = "网文", baseline_path: str | None = None,
              filename: str = "稿子") -> tuple[bool, list[str]]:
    """内置闸门：返回 (passed, 报告行)。不依赖宿主脚本，纯 Python。

    判定：任一标记族 > 人类 p99，或 ≥2 族 > p90 → FAIL；否则 PASS。
    这是**相对人类分布**的位置，不是「AI 概率」。
    """
    from .text_processor import process

    doc = process(text)
    rep = analyze_markers(doc)
    try:
        baseline = load_baseline(baseline_path)
    except (OSError, ValueError):
        baseline = {}
    rows = compare_to_baseline(rep, baseline, genre)
    verdict, failing = verdict_of(rows)

    lines = ["InkSoul 内置闸门（markers）：%s" % filename,
             "字数 %d｜叙述 %d｜对话 %d" % (rep.chars, rep.narrative_chars, rep.dialogue_chars),
             "实验性：分位数基线来自单一作者样本；2026-11-07 的 40 对配对评测显示"
             "对 deepseek-chat 无区分度（各族 AUC 0.29-0.52，AI 稿全部 PASS），"
             "不要据此判定稿子像不像 AI：docs/experiments/eval_pairs_2026-11-07.md"]
    if rep.narrative_chars < MIN_NARRATIVE_CHARS:
        lines.append("样本过短（叙述 %d 字 < %d）：只输出密度，不判定"
                     % (rep.narrative_chars, MIN_NARRATIVE_CHARS))
    if not rows:
        lines.append("未找到人类基线，只输出密度：")
        for kind in KINDS:
            lines.append("  %-10s %6.2f/千字" % (KIND_NAMES[kind], rep.per_1000.get(kind, 0.0)))
        return True, lines

    very_high = [r for r in rows if r["level"] == "very_high"]
    high = [r for r in rows if r["level"] == "high"]
    for r in rows:
        flag = {"ok": "ok  ", "high": "HIGH", "very_high": "VHIGH"}[r["level"]]
        line = ("  [%s] %-14s %6.2f/千字（人类 p50 %.2f / p90 %.2f）"
                % (flag, r["name"], r["value"], r["p50"], r["p90"]))
        if r.get("method") == "poisson" and r.get("p_ge") is not None:
            line += "｜泊松 P(X≥%d)=%.3f" % (r.get("count", 0), r["p_ge"])
        lines.append(line)
    if verdict == "FAIL":
        lines.append("VERDICT: FAIL")
        lines.append("按命中改：" + "；".join(
            SUGGESTIONS.get(r["kind"], "") for r in (very_high or high)[:3]))
        verdict, passed, rc = "VERDICT: FAIL", False, 1
    elif verdict == "SKIP":
        # 样本过短时不能给 PASS：那等于用一句「被」蒙混过关
        lines.append("VERDICT: SKIP（叙述 %d 字 < %d，未判定）"
                     % (rep.narrative_chars, MIN_NARRATIVE_CHARS))
        verdict, passed, rc = "VERDICT: SKIP", True, 0
    else:
        lines.append("VERDICT: PASS")
        verdict, passed, rc = "VERDICT: PASS", True, 0
    import datetime
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append("RECEIPT: %s rc=%d %s @ %s" % (filename, rc, verdict, stamp))
    return passed, lines
