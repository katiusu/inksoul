"""文体统计（Stylometric Analyzer）：句长分布、词汇多样性、词类配比、标点/对话占比、修辞标记。

本模块只输出**可解释指标与分布**，不输出「AI 味分数」或任何单一总分
（见 docs/linguistic_analysis.md §0.1 三条方法论红线、§6 V1–V7 的分维思路）。

单位与公式（每个指标都能手算复核）：

- **句长**：书写句（`Sentence`）的字符数 `len(sentence.text)`，**含标点**；单位「字符」。
  - `sentence_length_stats.mean/median/p95/std/min/max`：`std` 用**总体标准差**（`pstdev`，
    除以 n），`p95` 用线性插值（位置 `0.95·(n−1)`）。
- **长/短句**：长句 = 句长 ≥ `SENT_LONG_CHARS`(25)；短句 = 句长 ≤ `SENT_SHORT_CHARS`(8)（均为未标定阈值）。
  - `long_short_ratio = 长句数 / max(短句数, 1)`（分母下限 1，避免除零；因此**不是**对数比）。
  - `long_sentence_share = 长句数 / 总句数`，`short_sentence_share = 短句数 / 总句数`，
    这两个占比才是解释长/短结构的主依据，比值只作辅助。
- **词汇多样性**：
  - `ttr = 不同词数 / 词数`（词 = 非标点、非空白 token；单位：无量纲 0–1），对长度敏感，仅作粗指标。
  - `mtld_like`：MTLD（Measure of Textual Lexical Diversity）实现——沿序列累加
    `TTR = 型/例`，每当 TTR ≤ `MTLD_THRESHOLD`(0.72) 记一个因子并从零重开；
    末尾残余按 `(1 − TTR) / (1 − 0.72)` 折成部分因子；`MTLD = 词数 / 因子数`，
    正反两遍取平均。单位：词。**词数 < `MTLD_MIN_TOKENS`(100) 时结果不稳定（低置信）**。
- **词类配比** `pos_distribution`：按 `normalizer` 归一后的功能类（`N`/`V`/`A`/`ADV_LIM`/`PREP_BA`…）计，
  `share = 该类 token 数 / 非标点 token 数`；另给 `function_word_share`
  （`normalizer.ANCHOR_CLASSES` 中的 token 占比）与 `conj_per_kchar`（每千字符连词数）。
- **对话占比** `dialogue_ratio`：成对引号（`“”`/`「」`/`『』`/`‘’`/直引号）内字符数 /
  全文非空白字符数（引号本身不计入分子，括号栈配对，未闭合引号不计）。
- **标点占比** `punctuation_ratio`：标点 token 的字符数 / 全文非空白字符数。
- **修辞标记** `rhetoric_marker_counts`：由**显式词表**命中统计（同一片段只计一次，长词优先），
  另加两项**结构代理**（排比 = 连续 ≥3 个小句共享同一句首模式；疑问句 = 以 `？/吗/呢/么` 收尾）。
  词表法只看标记词，**看不到真正的比喻/通感/借代**——这一栏是低置信占位，不能当修辞质量判据。
- **情绪词** `emotion_lexicon_hits`：自建情绪词表命中次数；`emotion_per_kchar = 命中数 / 非空白字符数 × 1000`。
  词表只覆盖显式命名情绪的写法，**不含**由动作/体感承载的隐性情绪（见 docs/linguistic_analysis.md P9）。
- **段落节奏** `paragraph_rhythm`：逐段句数/字符数/平均句长 + 平均句长的变异系数
  （`cv = pstdev / mean`）+ 全篇相邻句长绝对差均值（`sentence_len_delta_mean`，单位「字符」）
  + 长短交替占比 `long_short_alternation_share`（相邻句中一长一短的对数 / 相邻对总数）。

**可信度**：句长/标点/对话占比/词类配比=确定性统计（可信）；词表类（修辞、情绪）只覆盖显式写法，
阈值（25/8/0.72）全部**未标定**。`notes` 里逐条标注。
"""
from __future__ import annotations

import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from . import normalizer as norm
from .diversity import _require_doc, clause_opening
from .errors import AnalysisError
from .text_processor import Document

# ---------------------------------------------------------------- 可标定常量
#: 长句阈值（字符，含标点）——**未标定**
SENT_LONG_CHARS = 25
#: 短句阈值（字符，含标点）——**未标定**
SENT_SHORT_CHARS = 8
#: MTLD 因子阈值（标准 MTLD 取 0.72）
MTLD_THRESHOLD = 0.72
#: 词数低于此值时 MTLD 不稳定
MTLD_MIN_TOKENS = 100
#: 排比结构代理：连续共享同一句首模式的小句数下限
PARALLEL_MIN_RUN = 3

#: 成对引号：开 → 闭
QUOTE_PAIRS = {"“": "”", "「": "」", "『": "』", "‘": "’", '"': '"'}

#: 修辞显式标记词（**只看字面**；同片段长词优先，避免「好像」被「像」重复计）
RHETORIC_MARKERS: dict[str, tuple[str, ...]] = {
    "明喻": ("好像", "像是", "仿佛", "宛如", "如同", "犹如", "好似", "宛若", "恰似", "似的", "像"),
    "暗喻": ("成了", "变成", "化作", "化为", "变作"),
    "反复": ("一遍又一遍", "一次又一次", "一遍遍地", "反复", "不断", "一再", "又一次", "再次"),
    "反问": ("难道", "岂不", "岂能", "怎能", "何必", "未尝", "谁说"),
    "夸张": ("万分", "无比", "无穷无尽", "天翻地覆", "惊天动地", "震耳欲聋", "铺天盖地"),
}

#: 自建情绪词表（**无权威中文表**，见 docs/linguistic_analysis.md P1/P9 的说明）
EMOTION_LEXICON: dict[str, tuple[str, ...]] = {
    "负面": ("孤独", "恐惧", "绝望", "悲伤", "痛苦", "愤怒", "焦虑", "愧疚", "委屈", "难堪",
             "尴尬", "慌乱", "不安", "沉重", "酸涩", "悲凉", "心慌", "窒息", "压抑", "麻木",
             "疲惫", "无力", "凄凉", "惆怅"),
    "正面": ("喜悦", "温暖", "幸福", "安心", "欢喜", "温柔", "欣慰", "轻松", "满足", "激动",
             "甜蜜", "平静", "踏实"),
    "抽象状态词": ("情绪", "心情", "气氛", "氛围", "感觉", "感受", "状态", "气场"),
}


# ---------------------------------------------------------------- 小工具
def _r(x: float, n: int = 3) -> float:
    """统一四舍五入，-0.0 归一为 0.0。"""
    v = round(float(x), n)
    return 0.0 if v == 0 else v


def _percentile(values: list[int], q: float) -> float:
    """线性插值分位数（q ∈ [0,1]），空列表返回 0.0。"""
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return float(vals[0])
    pos = q * (len(vals) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def _length_stats(lengths: list[int]) -> dict:
    """长度分布统计：mean / median / p95 / std(总体) / min / max / n，单位「字符」。"""
    if not lengths:
        return {"mean": 0.0, "median": 0.0, "p95": 0.0, "std": 0.0, "min": 0, "max": 0, "n": 0}
    return {
        "mean": _r(statistics.fmean(lengths)),
        "median": _r(statistics.median(lengths)),
        "p95": _r(_percentile(lengths, 0.95)),
        "std": _r(statistics.pstdev(lengths)),
        "min": min(lengths),
        "max": max(lengths),
        "n": len(lengths),
    }


def _mtld(tokens: list[str], threshold: float = MTLD_THRESHOLD) -> float:
    """MTLD 及其反向平均，单位「词」；词数过少时退化为不同词数。"""
    if not tokens:
        return 0.0
    if len(tokens) < MTLD_MIN_TOKENS:
        return float(len(set(tokens)))
    gap = 1.0 - threshold
    if gap <= 0:
        return float(len(set(tokens)))

    def one_pass(seq: list[str]) -> float:
        factors = 0.0
        types: set[str] = set()
        count = 0
        for word in seq:
            count += 1
            types.add(word)
            if len(types) / count <= threshold:
                factors += 1.0
                types.clear()
                count = 0
        if count > 0:
            factors += (1.0 - len(types) / count) / gap
        if factors <= 0:
            return float(len(seq))
        return len(seq) / factors

    return (one_pass(tokens) + one_pass(list(reversed(tokens)))) / 2.0


def _quote_spans(text: str) -> list[tuple[int, int]]:
    """用括号栈配对引号，返回 (开始, 结束) 字符区间（不含引号本身）；未闭合的不计。"""
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


def dialogue_char_ratio(doc: Document) -> float:
    """对话字符占比 = 引号内字符数 / 全文非空白字符数（narrative.py 复用此定义）。"""
    if not isinstance(doc, Document):
        raise AnalysisError(
            f"对话占比 需要 text_processor.Document，收到 {type(doc).__name__}",
            hint="先调用 inksoul.text_processor.process(text) 得到 Document，再传入",
        )
    total = len(re.sub(r"\s+", "", doc.text))
    if not total:
        return 0.0
    quoted = sum(end - start for start, end in _quote_spans(doc.text))
    return quoted / total


def _count_markers(text: str, markers: tuple[str, ...]) -> tuple[dict[str, int], int]:
    """在同一文本上统计显式标记词：长词优先、互不重叠。返回 (逐词计数, 总数)。"""
    if not text or not markers:
        return {}, 0
    pattern = re.compile("|".join(re.escape(m) for m in sorted(set(markers), key=len, reverse=True)))
    hits = Counter(m.group(0) for m in pattern.finditer(text))
    return dict(sorted(hits.items(), key=lambda kv: -kv[1])), sum(hits.values())


def _parallelism_runs(clauses: list, min_run: int = PARALLEL_MIN_RUN) -> int:
    """排比结构代理：连续 ≥min_run 个小句共享同一句首模式（且非纯标点）的段数。"""
    runs = 0
    cur = 1
    prev = None
    for c in clauses:
        op = clause_opening(c)
        if prev is not None and op == prev and op != "P":
            cur += 1
        else:
            if cur >= min_run:
                runs += 1
            cur = 1
        prev = op
    if cur >= min_run:
        runs += 1
    return runs


# ---------------------------------------------------------------- 报告结构
@dataclass
class StyleReport:
    """文体统计报告：分布与计数，无总分。"""

    sentence_length_stats: dict
    long_short_ratio: float
    long_sentence_share: float
    short_sentence_share: float
    ttr: float
    mtld_like: float
    token_count: int
    type_count: int
    pos_distribution: dict[str, dict]
    function_word_share: float
    conj_per_kchar: float
    dialogue_ratio: float
    punctuation_ratio: float
    rhetoric_marker_counts: dict[str, dict]
    emotion_lexicon_hits: dict[str, int]
    emotion_group_counts: dict[str, int]
    emotion_total: int
    emotion_per_kchar: float
    paragraph_rhythm: dict
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        """转为可 JSON 序列化的 dict（浮点已统一舍入到 3 位）。"""
        return {
            "sentence_length_stats": self.sentence_length_stats,
            "long_short_ratio": _r(self.long_short_ratio),
            "long_sentence_share": _r(self.long_sentence_share),
            "short_sentence_share": _r(self.short_sentence_share),
            "ttr": _r(self.ttr, 4),
            "mtld_like": _r(self.mtld_like),
            "token_count": self.token_count,
            "type_count": self.type_count,
            "pos_distribution": self.pos_distribution,
            "function_word_share": _r(self.function_word_share),
            "conj_per_kchar": _r(self.conj_per_kchar),
            "dialogue_ratio": _r(self.dialogue_ratio),
            "punctuation_ratio": _r(self.punctuation_ratio),
            "rhetoric_marker_counts": self.rhetoric_marker_counts,
            "emotion_lexicon_hits": self.emotion_lexicon_hits,
            "emotion_group_counts": self.emotion_group_counts,
            "emotion_total": self.emotion_total,
            "emotion_per_kchar": _r(self.emotion_per_kchar),
            "paragraph_rhythm": self.paragraph_rhythm,
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------- 主分析
def analyze_style(doc: Document) -> StyleReport:
    """统计文档的文体分布指标（句长/词汇/词类/标点/对话/修辞标记/节奏）。

    Args:
        doc: `text_processor.process()` 产出的 Document。

    Returns:
        StyleReport：各项分布与计数，`notes` 里标注低置信/未标定项。

    Raises:
        AnalysisError: 传入对象不是 Document，或切不出任何小句。
    """
    clauses = _require_doc(doc, "文体分析")
    sentences = doc.sentences
    tokens = doc.tokens
    non_punct = [t for t in tokens if not t.is_punct and t.word.strip()]
    words = [t.word for t in non_punct]
    no_ws_chars = len(re.sub(r"\s+", "", doc.text)) or 1

    # ---- 句长
    sent_lens = [s.length for s in sentences]
    stats = _length_stats(sent_lens)
    n_sent = len(sent_lens)
    n_long = sum(1 for L in sent_lens if L >= SENT_LONG_CHARS)
    n_short = sum(1 for L in sent_lens if L <= SENT_SHORT_CHARS)
    long_short_ratio = n_long / max(n_short, 1)

    # ---- 词汇多样性
    type_count = len(set(words))
    ttr = type_count / len(words) if words else 0.0
    mtld = _mtld(words)

    # ---- 词类配比（归一后功能类）
    pos_counter: Counter = Counter(t.norm or "X" for t in non_punct)
    total_non_punct = len(non_punct) or 1
    pos_distribution = {
        cls: {"count": cnt, "share": _r(cnt / total_non_punct)}
        for cls, cnt in sorted(pos_counter.items(), key=lambda kv: -kv[1])
    }
    function_n = sum(1 for t in non_punct if t.norm in norm.ANCHOR_CLASSES and t.norm != "P")
    conj_n = pos_counter.get("CONJ", 0)

    # ---- 标点 / 对话
    punct_chars = sum(len(t.word) for t in tokens if t.is_punct)
    dialogue_ratio = dialogue_char_ratio(doc)

    # ---- 修辞标记
    text = doc.text
    rhetoric: dict[str, dict] = {}
    for category, markers in RHETORIC_MARKERS.items():
        hits, total = _count_markers(text, markers)
        rhetoric[category] = {"count": total, "method": "词表命中", "hits": hits}
    rhetoric["排比"] = {
        "count": _parallelism_runs(clauses),
        "method": f"结构代理：连续 ≥{PARALLEL_MIN_RUN} 个小句共享同一句首模式",
        "hits": {},
    }
    q_sent = sum(1 for s in sentences if "？" in s.text or "?" in s.text
                 or s.text.rstrip("”’」』）)")[-1:] in ("吗", "呢", "么"))
    rhetoric["疑问句"] = {
        "count": q_sent,
        "method": "结构统计：以？/?收尾，或以吗/呢/么结尾",
        "hits": {},
    }

    # ---- 情绪词
    emotion_hits: dict[str, int] = {}
    group_counts: dict[str, int] = {}
    for group, words_ in EMOTION_LEXICON.items():
        hits, total = _count_markers(text, words_)
        group_counts[group] = total
        for w, c in hits.items():
            emotion_hits[w] = emotion_hits.get(w, 0) + c
    emotion_hits = dict(sorted(emotion_hits.items(), key=lambda kv: -kv[1]))
    emotion_total = sum(emotion_hits.values())

    # ---- 段落节奏
    para_means: list[float] = []
    clause_counts: list[int] = []
    char_counts: list[int] = []
    for p in doc.paragraphs:
        lens = [s.length for s in p.sentences]
        clause_counts.append(sum(len(s.clauses) for s in p.sentences))
        char_counts.append(len(p.text))
        para_means.append(statistics.fmean(lens) if lens else 0.0)
    para_cv = (statistics.pstdev(para_means) / statistics.fmean(para_means)) if len(para_means) > 1 and statistics.fmean(para_means) else 0.0
    deltas = [abs(b - a) for a, b in zip(sent_lens, sent_lens[1:])]
    alternating = sum(1 for a, b in zip(sent_lens, sent_lens[1:])
                      if (a >= SENT_LONG_CHARS) != (b >= SENT_LONG_CHARS))
    paragraph_rhythm = {
        "paragraph_count": len(doc.paragraphs),
        "sentence_counts": [len(p.sentences) for p in doc.paragraphs],
        "clause_counts": clause_counts,
        "char_counts": char_counts,
        "mean_sentence_len_per_para": [_r(m) for m in para_means],
        "mean_sentence_len_cv": _r(para_cv),
        "sentence_len_delta_mean": _r(statistics.fmean(deltas)) if deltas else 0.0,
        "long_short_alternation_share": _r(alternating / len(deltas)) if deltas else 0.0,
        "unit": "字符（含标点）",
    }

    # ---- 说明
    notes: list[str] = []
    if not doc.has_dependency:
        notes.append("后端无依存句法（默认 jieba），词类配比只到词性大类，兼语/连动无法区分（低置信）")
    notes.append(
        f"阈值均为**未标定**默认值：长句 ≥{SENT_LONG_CHARS} 字、短句 ≤{SENT_SHORT_CHARS} 字、"
        f"MTLD 因子 {MTLD_THRESHOLD}、排比 ≥{PARALLEL_MIN_RUN} 连；只用于分档，不构成判定"
    )
    if len(words) < MTLD_MIN_TOKENS:
        notes.append(
            f"词数仅 {len(words)}（< {MTLD_MIN_TOKENS}），mtld_like 已退化为不同词数，"
            "ttr 也受长度影响（低置信）"
        )
    notes.append(
        "修辞标记与情绪词是**显式词表命中**：看不到隐喻/通感/借代，也看不到由动作承载的隐性情绪，"
        "命中为 0 不等于没有修辞（低置信，占位指标）"
    )
    notes.append("对话占比按成对引号字符统计，嵌套引号与未闭合引号处理已简化（低置信）")
    notes.append("本报告不合成总分：句长长短、词类配比都可以有合理的文体解释，须与同体裁基线比")

    return StyleReport(
        sentence_length_stats=stats,
        long_short_ratio=long_short_ratio,
        long_sentence_share=n_long / n_sent if n_sent else 0.0,
        short_sentence_share=n_short / n_sent if n_sent else 0.0,
        ttr=ttr,
        mtld_like=mtld,
        token_count=len(words),
        type_count=type_count,
        pos_distribution=pos_distribution,
        function_word_share=function_n / total_non_punct,
        conj_per_kchar=conj_n / no_ws_chars * 1000,
        dialogue_ratio=dialogue_ratio,
        punctuation_ratio=punct_chars / no_ws_chars,
        rhetoric_marker_counts=rhetoric,
        emotion_lexicon_hits=emotion_hits,
        emotion_group_counts=group_counts,
        emotion_total=emotion_total,
        emotion_per_kchar=emotion_total / no_ws_chars * 1000,
        paragraph_rhythm=paragraph_rhythm,
        notes=notes,
    )
