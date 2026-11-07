"""句法多样性分析：结构模式分布、相邻相似度、段内/跨段复用、句首重复与长度分箱。

本模块只输出**可解释指标与分布**，不输出「AI 味分数」或任何单一总分
（理由见 docs/syntax_fingerprint.md §0.1：句法多样性不是「越高越好」的标量）。

计算单位与公式（每个指标都能手算复核）：

- **小句（clause）**：`text_processor` 切出的 `Clause`（标点边界 + 小句首连词）。
- **模式（pattern）**：一律取 `fingerprint.skeleton_key(clause)`，即**骨架串**
  （功能类 `ADV_NEG`/`ADV_LIM`/`PREP_BA`… 与内容类 `N`/`V`/`A` 都保留）。
  不用通配模式 `pattern_of()` 分组：通配把内容槽折成 `*`，会把「他推开门」「她关上了窗」
  并成同一模式，全文短句挤进一簇，分布熵失去区分度（同 `fingerprint.skeleton_key` 的取舍说明）。
  通配形式仍随 `distribution[].pattern` 一起给出，便于对照。
- `pattern_entropy = -Σ p_i·log2(p_i)`，单位 bit；`p_i = 第 i 个不同骨架串次数 / 小句数`。
- `pattern_entropy_norm = pattern_entropy / log2(k)`，`k` = 不同骨架串数；`k ≤ 1` 时记 0.0。
- `adjacent_similarity_mean = mean(similarity(骨架_i, 骨架_{i+1}))`，只统计**同一段落内**的
  相邻小句对（跨段相邻对不构成节奏），相似度取 `fingerprint.similarity`（0–1）。
- `adjacent_high_similarity_share` = 相似度 ≥ `NEAR_DUP_SIM` 的相邻对 / 全部同段相邻对。
- `paragraph_internal_repeat_rate` = 段内「与本段此前某小句骨架完全相同」的小句数 / 小句总数。
- `cross_paragraph_reuse_rate` = 出现在 ≥2 个段落中的骨架所覆盖的小句数 / 小句总数。
- `opening_pattern_repeat = 1 − 不同句首模式数 / 小句数`；句首模式 = 骨架串第一个非标点符号。
- `paragraph_first_opening_repeat`：同式，但只取每段第一个小句（测「段首固化」）。
- `sentence_length_bins` / `clause_length_bins`：按**字符数**（含词内标点，不含跨句字符）
  落进左闭右开区间，给出每档 `count` 与 `share`（share = count / 该单位总数）。

**可信度**：骨架串计数与分箱是确定性统计（可信，前提是分词正确）；所有阈值常量
（`NEAR_DUP_SIM` 等）都是**未标定**默认值，只用于把分布切成可读的段，不能当判定。
当前后端若无依存句法（默认 jieba），内容槽/功能槽的区分会在长句、成语、兼语结构上出错。
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from . import fingerprint as fp
from . import normalizer as norm
from .lexical import lexical_indices
from .errors import AnalysisError
from .text_processor import Clause, Document

# ---------------------------------------------------------------- 可标定常量
#: 「结构近似」阈值：相邻小句骨架相似度 ≥ 此值记为一对近重复（**未标定**，仅作分布参考）
NEAR_DUP_SIM = 0.85
#: 书写句长度分箱：(标签, 下界, 上界)，左闭右开，单位「字符」，None = 无上界
SENTENCE_LEN_BINS: tuple[tuple[str, int, int | None], ...] = (
    ("<5", 0, 5),
    ("5-9", 5, 10),
    ("10-19", 10, 20),
    ("20-29", 20, 30),
    ("30-49", 30, 50),
    ("50-79", 50, 80),
    ("80+", 80, None),
)
#: 小句长度分箱，同上
CLAUSE_LEN_BINS: tuple[tuple[str, int, int | None], ...] = (
    ("<4", 0, 4),
    ("4-6", 4, 7),
    ("7-9", 7, 10),
    ("10-14", 10, 15),
    ("15-19", 15, 20),
    ("20-29", 20, 30),
    ("30+", 30, None),
)
#: 小样本提示阈值：小句数低于此值时熵/均值波动大
SMALL_SAMPLE = 20
#: 「中等长度」书写句区间（字符）：Munoz-Ortiz 2024 观察到 LLM 集中在中等长度、人类更散
MID_LEN_LO, MID_LEN_HI = 10, 30


# ---------------------------------------------------------------- 小工具
def _r(x: float, n: int = 3) -> float:
    """统一四舍五入，并把 -0.0 归一为 0.0（避免进 JSON 出现 -0.0）。"""
    v = round(float(x), n)
    return 0.0 if v == 0 else v


def _entropy(counter: Counter) -> float:
    """香农熵（bit）：-Σ p·log2(p)。"""
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    return -sum((n / total) * math.log2(n / total) for n in counter.values() if n > 0)


def _bin(values: list[int], bins: tuple[tuple[str, int, int | None], ...]) -> dict[str, dict]:
    """把数值列表落进固定分箱，返回 {标签: {count, share}}。"""
    out: dict[str, dict] = {label: {"count": 0, "share": 0.0} for label, _, _ in bins}
    for v in values:
        for label, lo, hi in bins:
            if v >= lo and (hi is None or v < hi):
                out[label]["count"] += 1
                break
    total = len(values)
    if total:
        for label in out:
            out[label]["share"] = _r(out[label]["count"] / total)
    return out


def length_dispersion(lengths: list[int]) -> dict:
    """句长离散度：CV、分箱熵、中等长度堆积度。

    对应 Munoz-Ortiz et al. (2024) 的观察：人类句长分布更散（长句更多、尾部更重），
    LLM 更集中在 10-30 token 的中间段。这里只用**形状**指标，不设「越散越好」的判定。
    """
    if not lengths:
        return {"cv": 0.0, "mean": 0.0, "bin_entropy": 0.0, "bin_entropy_norm": 0.0,
                "mid_share": 0.0, "n": 0}
    mean = sum(lengths) / len(lengths)
    var = sum((L - mean) ** 2 for L in lengths) / len(lengths)
    std = math.sqrt(var)
    bins = _bin(lengths, SENTENCE_LEN_BINS)
    counter = Counter({k: v["count"] for k, v in bins.items() if v["count"]})
    ent = _entropy(counter)
    ent_norm = ent / math.log2(len(counter)) if len(counter) > 1 else 0.0
    mid = sum(1 for L in lengths if MID_LEN_LO <= L < MID_LEN_HI) / len(lengths)
    return {
        "cv": _r(std / mean if mean else 0.0),
        "mean": _r(mean),
        "bin_entropy": _r(ent),
        "bin_entropy_norm": _r(ent_norm),
        "mid_share": _r(mid),
        "n": len(lengths),
    }


def clause_opening(clause: Clause) -> str:
    """小句句首模式：骨架串里第一个非标点符号（无内容时返回 'P'）。

    style.py 的排比结构代理也用这个定义，保证「句首」在模块间一致。
    """
    for sym in clause.skel:
        if sym != "P":
            return sym
    return "P"


def _require_doc(doc: Document, analyzer: str) -> list[Clause]:
    """入口校验：类型 + 非空，返回可分析的小句列表。"""
    if not isinstance(doc, Document):
        raise AnalysisError(
            f"{analyzer} 需要 text_processor.Document，收到 {type(doc).__name__}",
            hint="先调用 inksoul.text_processor.process(text) 得到 Document，再传入",
        )
    clauses = [c for c in doc.clauses if c.token_count >= 1]
    if not clauses:
        raise AnalysisError(
            f"{analyzer} 没有可分析的小句（文档为空或只有符号）",
            hint="至少给一段含中文正文的文本；纯空白/纯标点会被拒绝",
        )
    return clauses


# ---------------------------------------------------------------- 报告结构
@dataclass
class DiversityReport:
    """句法多样性报告：全是分布与计数，没有总分。"""

    clause_count: int
    sentence_count: int
    paragraph_count: int
    distinct_patterns: int
    pattern_entropy: float
    pattern_entropy_norm: float
    adjacent_similarity_mean: float
    adjacent_pairs: int
    adjacent_high_similarity_share: float
    paragraph_internal_repeat_rate: float
    cross_paragraph_reuse_rate: float
    cross_paragraph_patterns: int
    opening_pattern_repeat: float
    paragraph_first_opening_repeat: float
    sentence_length_bins: dict[str, dict]
    clause_length_bins: dict[str, dict]
    length_dispersion: dict = field(default_factory=dict)
    lexical: dict = field(default_factory=dict)
    distribution: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        """转为可 JSON 序列化的 dict（浮点已统一舍入到 3 位）。"""
        return {
            "clause_count": self.clause_count,
            "sentence_count": self.sentence_count,
            "paragraph_count": self.paragraph_count,
            "distinct_patterns": self.distinct_patterns,
            "pattern_entropy": _r(self.pattern_entropy),
            "pattern_entropy_norm": _r(self.pattern_entropy_norm),
            "adjacent_similarity_mean": _r(self.adjacent_similarity_mean),
            "adjacent_pairs": self.adjacent_pairs,
            "adjacent_high_similarity_share": _r(self.adjacent_high_similarity_share),
            "paragraph_internal_repeat_rate": _r(self.paragraph_internal_repeat_rate),
            "cross_paragraph_reuse_rate": _r(self.cross_paragraph_reuse_rate),
            "cross_paragraph_patterns": self.cross_paragraph_patterns,
            "opening_pattern_repeat": _r(self.opening_pattern_repeat),
            "paragraph_first_opening_repeat": _r(self.paragraph_first_opening_repeat),
            "sentence_length_bins": self.sentence_length_bins,
            "clause_length_bins": self.clause_length_bins,
            "length_dispersion": self.length_dispersion,
            "lexical": self.lexical,
            "distribution": self.distribution,
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------- 主分析
def analyze_diversity(doc: Document) -> DiversityReport:
    """统计文档的句法结构分布与复用指标。

    Args:
        doc: `text_processor.process()` 产出的 Document。

    Returns:
        DiversityReport：模式分布 + 熵 + 相邻相似度 + 段内/跨段复用 + 句首重复 + 长度分箱。

    Raises:
        AnalysisError: 传入对象不是 Document，或文档里切不出任何小句。

    说明：本函数不做任何「好/坏」判定；`notes` 里逐条标注哪些量是低置信/未标定。
    """
    clauses = _require_doc(doc, "句法多样性分析")
    n = len(clauses)
    keys = [fp.skeleton_key(c) for c in clauses]
    counter: Counter = Counter(keys)
    k = len(counter)

    entropy = _entropy(counter)
    entropy_norm = entropy / math.log2(k) if k > 1 else 0.0

    # ---- 相邻相似度（同段内）
    sims: list[float] = []
    for a, b in zip(clauses, clauses[1:]):
        if a.para_id != b.para_id:
            continue
        sims.append(fp.similarity(fp.skeleton_key(a), fp.skeleton_key(b)))
    adj_mean = sum(sims) / len(sims) if sims else 0.0
    adj_high = (sum(1 for s in sims if s >= NEAR_DUP_SIM) / len(sims)) if sims else 0.0

    # ---- 段内重复：每个小句是否与本段此前小句骨架完全相同
    seen_in_para: dict[int, set] = defaultdict(set)
    within_repeat = 0
    for c, key in zip(clauses, keys):
        if key in seen_in_para[c.para_id]:
            within_repeat += 1
        seen_in_para[c.para_id].add(key)

    # ---- 跨段复用：骨架覆盖了 ≥2 个段落
    para_sets: dict[tuple, set[int]] = defaultdict(set)
    for c, key in zip(clauses, keys):
        para_sets[key].add(c.para_id)
    cross_keys = {key for key, ps in para_sets.items() if len(ps) >= 2}
    cross_n = sum(1 for key in keys if key in cross_keys)

    # ---- 句首结构重复
    openings = Counter(clause_opening(c) for c in clauses)
    opening_repeat = 1.0 - len(openings) / n

    first_clauses: list[Clause] = []
    for p in doc.paragraphs:
        if p.sentences and p.sentences[0].clauses:
            first_clauses.append(p.sentences[0].clauses[0])
    para_openings = Counter(clause_opening(c) for c in first_clauses)
    para_opening_repeat = (1.0 - len(para_openings) / len(first_clauses)) if first_clauses else 0.0

    # ---- 分布表（top 10）
    distribution: list[dict] = []
    for key, cnt in counter.most_common(10):
        members = [c for c, kk in zip(clauses, keys) if kk == key]
        distribution.append({
            "signature": " ".join(key),
            "pattern": " ".join(norm.to_pattern(list(key))),
            "count": cnt,
            "share": _r(cnt / n),
            "paragraph_spread": len(para_sets[key]),
            "examples": [c.text for c in members[:2]],
        })

    # ---- 长度分箱
    sent_lens = [s.length for s in doc.sentences]
    clause_lens = [c.length for c in clauses]

    notes: list[str] = []
    if not doc.has_dependency:
        notes.append(
            "当前后端无依存句法（默认 jieba），骨架串只到词性大类，"
            "兼语/连动/成语内部结构区分不出来（低置信）"
        )
    notes.append(
        f"阈值 NEAR_DUP_SIM={NEAR_DUP_SIM} 与长度分箱边界均为**未标定**默认值，"
        "只把分布切成可读的段，不构成判定"
    )
    if n < SMALL_SAMPLE:
        notes.append(f"样本仅 {n} 个小句（< {SMALL_SAMPLE}），熵与相邻相似度波动大（低置信）")
    if len(sims) == 0:
        notes.append("没有同段相邻小句对（每段只有 1 个小句？），adjacent_similarity_mean 记 0")
    notes.append(
        "length_dispersion.mid_share 高只说明句子挤在 10-29 字，本身不构成判定"
        "（Munoz-Ortiz 2024 的 LLM 集中现象是在英文新闻上测的）"
    )
    notes.append(
        "本报告不合成总分：熵高/低、复用率高低都可以有合理的文学解释"
        "（见 docs/syntax_fingerprint.md §0.1、§7.2）"
    )

    return DiversityReport(
        clause_count=n,
        sentence_count=len(doc.sentences),
        paragraph_count=len(doc.paragraphs),
        distinct_patterns=k,
        pattern_entropy=entropy,
        pattern_entropy_norm=entropy_norm,
        adjacent_similarity_mean=adj_mean,
        adjacent_pairs=len(sims),
        adjacent_high_similarity_share=adj_high,
        paragraph_internal_repeat_rate=within_repeat / n,
        cross_paragraph_reuse_rate=cross_n / n,
        cross_paragraph_patterns=len(cross_keys),
        opening_pattern_repeat=opening_repeat,
        paragraph_first_opening_repeat=para_opening_repeat,
        sentence_length_bins=_bin(sent_lens, SENTENCE_LEN_BINS),
        clause_length_bins=_bin(clause_lens, CLAUSE_LEN_BINS),
        length_dispersion=length_dispersion(sent_lens),
        lexical=lexical_indices([t.word for t in doc.tokens if not t.is_punct]),
        distribution=distribution,
        notes=notes,
    )
