"""叙事分析（Narrative Analyzer）：视角、场景切换、对话节拍、言语动词、信息密度、节奏提示。

本模块只输出**可解释指标与分布**，不输出「AI 味分数」或任何单一总分
（见 docs/linguistic_analysis.md §0.1、§6 V5「信息组织」的分维思路）。

单位与公式：

- **视角 `perspective`**：只看**叙述层小句**（不含任何引号字符的小句），因为引语里的
  「我」是角色的嘴，不是叙述者的视角。
  - `first_person_clause_ratio r1 = 含第一人称代词(我/我们/咱们…)的叙述小句数 / 叙述小句数`
  - `third_person_clause_ratio r3` 同式，词表为他/她/它/他们/她们/它们。
  - 判定：`r1 ≥ MIX_MIN 且 r3 ≥ MIX_MIN 且 |r1−r3| < DOMINANCE` → 「混用」；
    否则取高者 → 「第一人称」/「第三人称」；叙述小句里一个代词都没有 → 「无法判定」
    （汉语零主语叙事很常见，这不是错误）。
  - `confidence = min(1, 叙述小句数 / PERSP_MIN_CLAUSES) × 分离度`；
    主导型 分离度 = `min(1, |r1−r3| / PERSP_SEP_SCALE)`，
    混用型 分离度 = `min(1, min(r1,r3) / MIX_MIN)`。**这是启发式置信度，未标定**。
  - 另给 `dialogue_first_person_ratio`：引语小句里含「我」的比例，作为对照证据（不算进标签）。
- **场景切换 `scene_shift_count`**：小句级「标记切换」次数（**不是场景数量**）。
  按文档顺序遍历小句，取每句出现的**显式时间词**集合与**地点词**集合
  （自建词表，见 TIME_MARKERS / LOCATION_MARKERS）；维护「最近一次出现的时间标记」与
  「最近一次出现的地点标记」，某句带来的标记集合与最近一次不同时记 1 次（时间、地点各算一次），
  首次出现不计数。`paragraph_scene_shifts` 是相邻段落之间（各取该段首个时间/地点标记）的计数。
- **对话 `dialogue_ratio`**：与 `style.dialogue_char_ratio` 同一实现（引号内字符 / 非空白字符）。
  `dialogue_beats`：把句子按「是否含引号」标成 0/1 序列，**引语段的段数**（一段连续引语句 = 一拍）。
  `longest_dialogue_beat` 为最长连续引语句数；`dialogue_alternation` 为 0↔1 切换次数（一问一答的轮转）。
- **言语动词 `speech_verb_counts`**：按 token 统计（词表 = `normalizer.SPEECH_VERBS` + 少量补充），
  单位「次」。分词粒度会改变计数（例如「低声说」可能被切成「低声/说」），低置信。
- **信息密度 `information_density_per_paragraph`**：逐段给出
  `content_tokens`（归一后属 `normalizer.CONTENT_CLASSES` 的 token 数，含 TIME/LOC）、
  `content_per_clause = content_tokens / 小句数`、`content_per_100_chars = content_tokens / 段字符数 × 100`、
  `dialogue_share`（该段引号内字符 / 段字符数）。**这是分词口径的代理量，不是语义信息量**。
- **节奏提示 `pacing_notes`**：把上面的数按固定阈值翻成人话（每个阈值都标了「低置信/未标定」），
  只提示可查证的现象，不下「好/坏」结论。

**可信度**：对话占比、言语动词计数、信息密度=确定性统计（在分词正确的前提下可信）；
视角、场景切换、节奏判断=规则启发式，词表与阈值全部**未标定**，`notes` 里逐条标注。
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from . import normalizer as norm
from .diversity import _require_doc
from .style import QUOTE_PAIRS, dialogue_char_ratio
from .text_processor import Clause, Document

# ---------------------------------------------------------------- 可标定常量
#: 混用判定：两种人称占比都要达到的下限（**未标定**）
MIX_MIN = 0.10
#: 主导判定：|r1 − r3| 达到此值才算「主导」，否则倾向混用（**未标定**）
DOMINANCE = 0.20
#: 视角置信度：叙述小句数达到此值视为样本充足（**未标定**）
PERSP_MIN_CLAUSES = 30
#: 视角置信度：人称占比差达到此值视为「分离清晰」（**未标定**）
PERSP_SEP_SCALE = 0.30
#: 节奏提示阈值（**未标定**）
PACING_CV_LOW = 0.15
PACING_CV_HIGH = 0.50
PACING_DENSITY_LOW = 1.2
PACING_DENSITY_HIGH = 3.0

FIRST_PERSON = ("我", "我们", "咱们", "咱", "俺", "我俩")
SECOND_PERSON = ("你", "你们", "您", "您们")
THIRD_PERSON = ("他", "她", "它", "他们", "她们", "它们", "对方", "别人")

#: 时间标记（自建词表，≥2 字，避免单字误命中）
TIME_MARKERS = (
    "清晨", "早晨", "早上", "上午", "中午", "下午", "傍晚", "黄昏", "夜里", "夜晚",
    "深夜", "凌晨", "半夜", "天亮", "入夜", "夜深", "第二天", "次日", "昨天", "今天",
    "明天", "后天", "前几天", "几天后", "三天后", "片刻", "良久", "半晌", "许久",
    "过了一会儿", "这时", "那时", "此刻", "此时", "刚才", "后来", "从此", "当年",
)
#: 地点标记（自建词表，≥2 字）
LOCATION_MARKERS = (
    "屋里", "屋外", "门口", "房间", "室内", "室外", "楼下", "楼上", "走廊", "楼道",
    "街上", "街口", "巷子", "车里", "车上", "窗边", "床边", "桌边", "厨房", "客厅",
    "卧室", "院子", "阳台", "医院", "车站", "办公室", "教室", "电梯", "郊外", "河边",
    "公司", "学校", "店里", "柜台", "门口", "门前", "窗台", "楼梯",
)
#: 言语动词补充（normalizer.SPEECH_VERBS 之外的常见写法）
SPEECH_EXTRA = ("说道", "问道", "答道", "开口", "开口说", "应声", "插嘴", "咕哝")

PAIR_QUOTES = frozenset(QUOTE_PAIRS) | frozenset(QUOTE_PAIRS.values())


# ---------------------------------------------------------------- 小工具
def _r(x: float, n: int = 3) -> float:
    """统一四舍五入，-0.0 归一为 0.0。"""
    v = round(float(x), n)
    return 0.0 if v == 0 else v


def _has_quote(text: str) -> bool:
    """小句/句子文本里是否出现引号字符。"""
    return any(ch in PAIR_QUOTES for ch in text)


def _markers_in(text: str, markers: tuple[str, ...]) -> set[str]:
    """子串命中的标记集合（不用分词结果，避免多字词被切碎）。"""
    return {m for m in markers if m in text}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


# ---------------------------------------------------------------- 报告结构
@dataclass
class PerspectiveInfo:
    """视角判定结果（启发式，未标定）。"""

    label: str
    confidence: float
    first_person_clause_ratio: float
    third_person_clause_ratio: float
    second_person_clause_ratio: float
    narrative_clauses: int
    pronoun_clauses: int
    dialogue_first_person_ratio: float
    method: str

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": _r(self.confidence),
            "first_person_clause_ratio": _r(self.first_person_clause_ratio),
            "third_person_clause_ratio": _r(self.third_person_clause_ratio),
            "second_person_clause_ratio": _r(self.second_person_clause_ratio),
            "narrative_clauses": self.narrative_clauses,
            "pronoun_clauses": self.pronoun_clauses,
            "dialogue_first_person_ratio": _r(self.dialogue_first_person_ratio),
            "method": self.method,
        }


@dataclass
class NarrativeReport:
    """叙事分析报告：视角 + 场景 + 对话 + 信息密度 + 节奏提示，无总分。"""

    perspective: PerspectiveInfo
    scene_shift_count: int
    paragraph_scene_shifts: int
    scene_marker_counts: dict[str, int]
    dialogue_ratio: float
    dialogue_beats: int
    longest_dialogue_beat: int
    dialogue_alternation: int
    speech_verb_counts: dict[str, int]
    speech_verb_total: int
    information_density_per_paragraph: list[dict]
    information_density_mean: float
    information_density_cv: float
    pacing_notes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        """转为可 JSON 序列化的 dict（浮点已统一舍入到 3 位）。"""
        return {
            "perspective": self.perspective.as_dict(),
            "scene_shift_count": self.scene_shift_count,
            "paragraph_scene_shifts": self.paragraph_scene_shifts,
            "scene_marker_counts": self.scene_marker_counts,
            "dialogue_ratio": _r(self.dialogue_ratio),
            "dialogue_beats": self.dialogue_beats,
            "longest_dialogue_beat": self.longest_dialogue_beat,
            "dialogue_alternation": self.dialogue_alternation,
            "speech_verb_counts": self.speech_verb_counts,
            "speech_verb_total": self.speech_verb_total,
            "information_density_per_paragraph": self.information_density_per_paragraph,
            "information_density_mean": _r(self.information_density_mean),
            "information_density_cv": _r(self.information_density_cv),
            "pacing_notes": list(self.pacing_notes),
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------- 各子分析
def _perspective(doc: Document, clauses: list[Clause]) -> PerspectiveInfo:
    """叙述层视角判定（排除引语小句）。"""
    narrative = [c for c in clauses if not _has_quote(c.text)]
    quoted = [c for c in clauses if _has_quote(c.text)]
    n = len(narrative)
    n1 = n3 = n2 = n_pron = 0
    for c in narrative:
        words = {t.word for t in c.tokens if not t.is_punct}
        has1 = any(w in FIRST_PERSON for w in words)
        has3 = any(w in THIRD_PERSON for w in words)
        has2 = any(w in SECOND_PERSON for w in words)
        if has1:
            n1 += 1
        if has3:
            n3 += 1
        if has2:
            n2 += 1
        if has1 or has3:
            n_pron += 1
    r1 = n1 / n if n else 0.0
    r3 = n3 / n if n else 0.0
    r2 = n2 / n if n else 0.0

    sample_scale = _clip01(n / PERSP_MIN_CLAUSES)
    if n_pron == 0:
        label, conf = "无法判定", 0.0
    elif r1 >= MIX_MIN and r3 >= MIX_MIN and abs(r1 - r3) < DOMINANCE:
        label = "混用"
        conf = sample_scale * _clip01(min(r1, r3) / MIX_MIN)
    elif r1 > r3:
        label = "第一人称"
        conf = sample_scale * _clip01(abs(r1 - r3) / PERSP_SEP_SCALE)
    elif r3 > r1:
        label = "第三人称"
        conf = sample_scale * _clip01(abs(r1 - r3) / PERSP_SEP_SCALE)
    else:
        label = "混用"
        conf = sample_scale * _clip01(min(r1, r3) / MIX_MIN)

    d1 = sum(1 for c in quoted if any(t.word in FIRST_PERSON for t in c.tokens)) / len(quoted) if quoted else 0.0
    method = (
        "叙述层小句里的人称代词占比（引语小句已排除）；"
        f"MIX_MIN={MIX_MIN}、DOMINANCE={DOMINANCE}、PERSP_MIN_CLAUSES={PERSP_MIN_CLAUSES} 均为未标定值"
    )
    return PerspectiveInfo(
        label=label,
        confidence=conf,
        first_person_clause_ratio=r1,
        third_person_clause_ratio=r3,
        second_person_clause_ratio=r2,
        narrative_clauses=n,
        pronoun_clauses=n_pron,
        dialogue_first_person_ratio=d1,
        method=method,
    )


def _scene(doc: Document, clauses: list[Clause]) -> tuple[int, int, dict[str, int]]:
    """场景切换：小句级 + 段落级，返回 (小句级次数, 段落级次数, 标记计数)。"""
    times: list[set[str]] = []
    locs: list[set[str]] = []
    counter: Counter = Counter()
    for c in clauses:
        t = _markers_in(c.text, TIME_MARKERS)
        l = _markers_in(c.text, LOCATION_MARKERS)
        times.append(t)
        locs.append(l)
        for m in t | l:
            counter[m] += 1

    # 小句级：跟踪「最近一次出现的时间/地点标记」，出现不同的新标记即记 1 次切换
    clause_shifts = 0
    last_time: set[str] | None = None
    last_loc: set[str] | None = None
    for t, l in zip(times, locs):
        if t:
            if last_time is not None and t != last_time:
                clause_shifts += 1
            last_time = t
        if l:
            if last_loc is not None and l != last_loc:
                clause_shifts += 1
            last_loc = l

    # 段落级：每段首个出现的时间/地点标记
    first_time: list[tuple | None] = []
    first_loc: list[tuple | None] = []
    for p in doc.paragraphs:
        t_hit = None
        l_hit = None
        for s in p.sentences:
            for c in s.clauses:
                if t_hit is None:
                    ts = _markers_in(c.text, TIME_MARKERS)
                    if ts:
                        t_hit = tuple(sorted(ts))
                if l_hit is None:
                    ls = _markers_in(c.text, LOCATION_MARKERS)
                    if ls:
                        l_hit = tuple(sorted(ls))
                if t_hit is not None and l_hit is not None:
                    break
            if t_hit is not None and l_hit is not None:
                break
        first_time.append(t_hit)
        first_loc.append(l_hit)

    para_shifts = 0
    for i in range(1, len(doc.paragraphs)):
        if first_time[i] and first_time[i - 1] and first_time[i] != first_time[i - 1]:
            para_shifts += 1
        elif first_loc[i] and first_loc[i - 1] and first_loc[i] != first_loc[i - 1]:
            para_shifts += 1

    return clause_shifts, para_shifts, dict(sorted(counter.items(), key=lambda kv: -kv[1]))


def _dialogue_beats(doc: Document) -> tuple[int, int, int]:
    """把句子标成「含引号/不含引号」，返回 (节拍数, 最长节拍, 切换次数)。"""
    flags = [1 if _has_quote(s.text) else 0 for s in doc.sentences]
    beats = 0
    longest = 0
    cur = 0
    prev = 0
    for f in flags:
        if f:
            cur += 1
            longest = max(longest, cur)
            if prev == 0:
                beats += 1
        else:
            cur = 0
        prev = f
    alternation = sum(1 for a, b in zip(flags, flags[1:]) if a != b)
    return beats, longest, alternation


def _speech_verbs(doc: Document) -> tuple[dict[str, int], int]:
    """按 token 统计言语动词。"""
    vocab = set(norm.SPEECH_VERBS) | set(SPEECH_EXTRA)
    counter: Counter = Counter()
    for t in doc.tokens:
        if t.is_punct:
            continue
        if t.word in vocab or t.norm == "SPEECH":
            counter[t.word] += 1
    ordered = dict(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))
    return ordered, sum(ordered.values())


def _information_density(doc: Document) -> tuple[list[dict], float, float]:
    """逐段信息密度（内容词口径），返回 (逐段列表, 均值, 变异系数)。"""
    rows: list[dict] = []
    values: list[float] = []
    for p in doc.paragraphs:
        clauses = [c for s in p.sentences for c in s.clauses]
        content = sum(1 for c in clauses for t in c.tokens
                      if not t.is_punct and t.norm in norm.CONTENT_CLASSES)
        chars = len(p.text) or 1
        per_clause = content / len(clauses) if clauses else 0.0
        quoted = sum(e - s for s, e in _quote_spans_of(p.text))
        rows.append({
            "para_id": p.id,
            "chars": len(p.text),
            "clauses": len(clauses),
            "content_tokens": content,
            "content_per_clause": _r(per_clause),
            "content_per_100_chars": _r(content / chars * 100),
            "dialogue_share": _r(quoted / chars),
        })
        values.append(per_clause)
    if not values:
        return rows, 0.0, 0.0
    mean = statistics.fmean(values)
    cv = (statistics.pstdev(values) / mean) if len(values) > 1 and mean else 0.0
    return rows, mean, cv


def _quote_spans_of(text: str) -> list[tuple[int, int]]:
    """段落内的引号区间（与 style._quote_spans 同规则，按需小规模复用）。"""
    spans: list[tuple[int, int]] = []
    stack: list[str] = []
    start = -1
    for i, ch in enumerate(text):
        if stack:
            if ch == stack[-1]:
                stack.pop()
                if not stack and start >= 0:
                    spans.append((start, i))
                    start = -1
            elif ch in QUOTE_PAIRS:
                stack.append(QUOTE_PAIRS[ch])
        elif ch in QUOTE_PAIRS:
            stack.append(QUOTE_PAIRS[ch])
            start = i + 1
    return spans


def _pacing_notes(clause_count: int, paragraph_count: int, density_mean: float,
                  density_cv: float, beats: int, sentence_count: int,
                  dialogue_ratio: float, shifts: int) -> list[str]:
    """把数值翻成可查证的现象提示（每条都标「低置信/未标定」）。"""
    out: list[str] = []
    # 段落少于 3 时 CV 由构造决定（单段必为 0），不出提示
    if paragraph_count >= 3 and sentence_count >= 4:
        if density_cv < PACING_CV_LOW:
            out.append(
                f"段内信息密度高度均匀（CV={density_cv:.2f} < {PACING_CV_LOW}），"
                "节奏可能平铺（低置信/未标定）"
            )
        elif density_cv >= PACING_CV_HIGH:
            out.append(
                f"段间信息密度落差大（CV={density_cv:.2f} ≥ {PACING_CV_HIGH}），"
                "快慢交替明显（低置信/未标定）"
            )
        else:
            out.append(f"段间信息密度居中（CV={density_cv:.2f}），无明显单一节奏（低置信/未标定）")
    if density_mean and density_mean < PACING_DENSITY_LOW:
        out.append(
            f"平均每小句 {density_mean:.2f} 个内容词（< {PACING_DENSITY_LOW}），"
            "叙述偏稀疏或小句偏碎（低置信/未标定）"
        )
    elif density_mean >= PACING_DENSITY_HIGH:
        out.append(
            f"平均每小句 {density_mean:.2f} 个内容词（≥ {PACING_DENSITY_HIGH}），"
            "单句承载偏高，可能出现长句堆叠（低置信/未标定）"
        )
    if sentence_count:
        per100 = beats / sentence_count * 100
        out.append(f"每百句约 {per100:.0f} 拍对话（共 {beats} 拍 / {sentence_count} 句），"
                   f"对话字符占比 {dialogue_ratio:.2f}（低置信/未标定）")
    if clause_count:
        out.append(f"场景标记切换 {shifts} 次 / {clause_count} 个小句"
                   "（仅统计显式时间地点词，隐性转场看不到；低置信）")
    return out


# ---------------------------------------------------------------- 主分析
def analyze_narrative(doc: Document) -> NarrativeReport:
    """统计叙事结构指标（视角/场景/对话节拍/言语动词/信息密度/节奏提示）。

    Args:
        doc: `text_processor.process()` 产出的 Document。

    Returns:
        NarrativeReport：各维度分布与计数，`notes` / `pacing_notes` 标注低置信与未标定项。

    Raises:
        AnalysisError: 传入对象不是 Document，或切不出任何小句。
    """
    clauses = _require_doc(doc, "叙事分析")
    perspective = _perspective(doc, clauses)
    clause_shifts, para_shifts, marker_counts = _scene(doc, clauses)
    beats, longest, alternation = _dialogue_beats(doc)
    dialogue_ratio = dialogue_char_ratio(doc)
    verbs, verb_total = _speech_verbs(doc)
    density_rows, density_mean, density_cv = _information_density(doc)

    pacing = _pacing_notes(
        clause_count=len(clauses),
        paragraph_count=len(doc.paragraphs),
        density_mean=density_mean,
        density_cv=density_cv,
        beats=beats,
        sentence_count=len(doc.sentences),
        dialogue_ratio=dialogue_ratio,
        shifts=clause_shifts,
    )

    notes: list[str] = []
    if not doc.has_dependency:
        notes.append("后端无依存句法（默认 jieba）；本模块全部指标只用到词表与标点（低置信）")
    notes.append(
        "视角判定是**规则启发式**：只数叙述层小句里的人称代词，"
        "汉语零主语叙事会被判成「无法判定」，confidence 未标定"
    )
    notes.append("场景词表为自建（无权威中文表），只覆盖显式时间/地点词，隐性转场统计不到（低置信）")
    notes.append(
        "信息密度按分词口径统计内容词数，是**代理量**不是语义信息量；"
        "jieba 分词错误会直接改变数值（低置信）"
    )
    if len(doc.sentences) < 5:
        notes.append(f"仅 {len(doc.sentences)} 句，节拍与密度统计波动大（低置信）")
    notes.append("本报告不合成总分：对话多少、密度高低本身都不是缺陷，须与同体裁基线比")

    return NarrativeReport(
        perspective=perspective,
        scene_shift_count=clause_shifts,
        paragraph_scene_shifts=para_shifts,
        scene_marker_counts=marker_counts,
        dialogue_ratio=dialogue_ratio,
        dialogue_beats=beats,
        longest_dialogue_beat=longest,
        dialogue_alternation=alternation,
        speech_verb_counts=verbs,
        speech_verb_total=verb_total,
        information_density_per_paragraph=density_rows,
        information_density_mean=density_mean,
        information_density_cv=density_cv,
        pacing_notes=pacing,
        notes=notes,
    )
