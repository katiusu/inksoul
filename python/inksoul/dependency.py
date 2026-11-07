"""依存层指标：弧长分布、左右弧比例、依存关系分布与树深（L2 补充层）。

**为什么需要这一层**：Muñoz-Ortiz et al. (2024, *Artificial Intelligence Review* 57:265)
在 13,371 篇 NYT 新闻上对比 6 个 LLM 与人类文本，发现**依存层面的差异比句长更稳**：

- 人类左手弧比例更低（1–10 token 句：49.40% vs 模型 49.97–52.08%）
- 人类 amod 6.98% vs 模型 5.57–5.79%、appos 1.19% vs 0.85–1.07%
- 模型 aux 2.55–2.74%、cop 1.86–2.28% 明显高于人类（aux 1.91%、cop 1.26%）
- 弧长本身几乎相同，但 Ω 最优性（词序对树形的优化程度）人类明显更高

本模块只输出**分布与计数**，不输出「AI 味分数」，也不合成总分（ADR-2）。
Ω 未实现：需要枚举树形的 D_min 与随机排列期望 D_rla（LAL 库 / Gildea-Temperley 动态规划），
本机不装第三方库，故列为 TODO，先在 notes 里写明缺口。

**单位约定**：弧长以 **token 数**计（|head_pos − dep_pos|），不是字符数；分箱按句内 token 数。
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .errors import AnalysisError
from .text_processor import Document

# ---------------------------------------------------------------- 可标定常量
#: 弧长分箱：(标签, 下界, 上界)，左闭右开，单位 token
ARC_LEN_BINS: tuple[tuple[str, int, int | None], ...] = (
    ("1", 1, 2),
    ("2", 2, 3),
    ("3-4", 3, 5),
    ("5-7", 5, 8),
    ("8+", 8, None),
)
#: 句长分箱（按 token 数），与 Muñoz-Ortiz 原文的 1–10/11–20/… 对齐
SENT_TOKEN_BINS: tuple[tuple[str, int, int | None], ...] = (
    ("1-10", 1, 11),
    ("11-20", 11, 21),
    ("21-30", 21, 31),
    ("31-40", 31, 41),
    ("41+", 41, None),
)
#: 句长分箱的最小样本量：低于此值的分箱只给均值不做比较
BIN_MIN_SENTENCES = 10


def _r(x: float, n: int = 3) -> float:
    v = round(float(x), n)
    return 0.0 if v == 0 else v


def _bin_of(value: int, bins: tuple[tuple[str, int, int | None], ...]) -> str:
    for label, lo, hi in bins:
        if value >= lo and (hi is None or value < hi):
            return label
    return bins[-1][0]


@dataclass
class DependencyReport:
    """依存层报告：全是分布，没有总分。"""

    sentence_count: int
    arc_count: int
    left_arc_share: float
    arc_len_mean: float
    arc_len_std: float
    arc_len_bins: dict[str, dict]
    arc_len_by_sentence_bin: dict[str, dict]
    deprel_shares: dict[str, float]
    mean_tree_depth: float
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "sentence_count": self.sentence_count,
            "arc_count": self.arc_count,
            "left_arc_share": _r(self.left_arc_share),
            "arc_len_mean": _r(self.arc_len_mean),
            "arc_len_std": _r(self.arc_len_std),
            "arc_len_bins": self.arc_len_bins,
            "arc_len_by_sentence_bin": self.arc_len_by_sentence_bin,
            "deprel_shares": self.deprel_shares,
            "mean_tree_depth": _r(self.mean_tree_depth),
            "notes": list(self.notes),
        }


def analyze_dependency(doc: Document) -> DependencyReport:
    """统计文档的依存弧分布与树形指标。

    Raises:
        AnalysisError: 传入对象不是 Document，或当前后端没有依存句法（默认 jieba）。
    """
    if not isinstance(doc, Document):
        raise AnalysisError(
            f"依存分析需要 text_processor.Document，收到 {type(doc).__name__}",
            hint="先调用 inksoul.text_processor.process(text) 得到 Document",
        )
    if not doc.has_dependency:
        raise AnalysisError(
            "当前后端无依存句法，无法计算弧长/依存关系分布",
            hint="改用 spaCy 后端（analysis.backend=\"spacy\" 并安装 zh_core_web_sm）；"
                 "jieba 只能给词性，没有 head",
        )

    left = right = 0
    lengths: list[int] = []
    length_bins: Counter = Counter()
    by_sent_bin: dict[str, list[int]] = defaultdict(list)
    deprels: Counter = Counter()
    depths: list[int] = []
    n_sent = 0

    for sent in doc.sentences:
        tokens = sent.tokens
        if not tokens:
            continue
        pos_of = {t.index: i for i, t in enumerate(tokens)}
        n_sent += 1
        n_non_punct = sum(1 for t in tokens if not t.is_punct)
        bin_label = _bin_of(max(1, n_non_punct), SENT_TOKEN_BINS)

        sent_has_arc = False
        for t in tokens:
            if t.head is None or t.head == t.index:
                continue
            head_pos = pos_of.get(t.head)
            if head_pos is None:
                continue
            sent_has_arc = True
            L = abs(head_pos - pos_of[t.index])
            lengths.append(L)
            length_bins[_bin_of(L, ARC_LEN_BINS)] += 1
            by_sent_bin[bin_label].append(L)
            deprels[t.deprel or "unknown"] += 1
            if head_pos > pos_of[t.index]:
                left += 1
            else:
                right += 1

        if sent_has_arc:
            depths.append(_max_depth(tokens, pos_of))

    if not lengths:
        raise AnalysisError(
            "文档里没有可用的依存弧（所有 token 的 head 都是 None 或自身）",
            hint="确认后端真的返回了 head；空文档或纯标点文本无法分析",
        )

    total_arcs = len(lengths)
    arc_bins = {label: {"count": 0, "share": 0.0} for label, _, _ in ARC_LEN_BINS}
    for label, cnt in length_bins.items():
        arc_bins[label]["count"] = cnt
        arc_bins[label]["share"] = _r(cnt / total_arcs)

    sent_bins: dict[str, dict] = {}
    for label, _, _ in SENT_TOKEN_BINS:
        vals = by_sent_bin.get(label, [])
        sent_bins[label] = {
            "arcs": len(vals),
            "mean_arc_len": _r(statistics.fmean(vals)) if vals else 0.0,
            "low_sample": len(vals) < BIN_MIN_SENTENCES,
        }

    top = deprels.most_common(15)
    notes: list[str] = [
        "弧长以 token 计，不是字符；中文词均长会放大与英文文献的绝对差异，只比分布形状",
        "Ω 最优性（Ferrer-i-Cancho 2022）未实现：需要 D_min 与随机排列期望 D_rla，"
        "本机无 LAL 库；当前只能给弧长分布，不能给「词序优化度」",
        "本报告不合成总分：弧长/左右弧/依存类型都是分布，任一侧的偏离都可以有合理文学解释",
    ]
    if n_sent < BIN_MIN_SENTENCES:
        notes.append(f"仅 {n_sent} 句（< {BIN_MIN_SENTENCES}），分箱均值波动大（低置信）")

    return DependencyReport(
        sentence_count=n_sent,
        arc_count=total_arcs,
        left_arc_share=left / total_arcs,
        arc_len_mean=statistics.fmean(lengths),
        arc_len_std=statistics.pstdev(lengths) if total_arcs > 1 else 0.0,
        arc_len_bins=arc_bins,
        arc_len_by_sentence_bin=sent_bins,
        deprel_shares={k: _r(v / total_arcs) for k, v in top},
        mean_tree_depth=statistics.fmean(depths) if depths else 0.0,
        notes=notes,
    )


def _max_depth(tokens, pos_of: dict[int, int]) -> int:
    """句内最大树深：每个 token 沿 head 上溯的步数取最大。带环保护。"""
    best = 0
    for t in tokens:
        cur, steps, seen = t, 0, set()
        while cur is not None and cur.head is not None and cur.head != cur.index:
            if cur.index in seen:
                break
            seen.add(cur.index)
            pos = pos_of.get(cur.head)
            if pos is None:
                break
            cur = tokens[pos]
            steps += 1
            if steps > len(tokens):
                break
        best = max(best, steps)
    return best
