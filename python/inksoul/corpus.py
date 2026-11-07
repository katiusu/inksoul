"""跨作品（语料级）同质统计：作品间骨架分布相似度。

**为什么需要这一层**：Doshi & Hauser (2024, *Science Advances*) 让 293 人写 8 句短故事，
用 OpenAI embeddings 的两两平均余弦相似度衡量「集体多样性」，发现拿到 GenAI 想法后
**个体 novelty 上升（+6.7%）而同批作品之间更相似**——个体变好、集体变窄。
Sourati et al. (2026, *Nature Human Behaviour*) 在 88 万+ 文本上看到同样的方差压缩
（LLM 润色使写作复杂度方差降 21–50%）。单篇指标看不见这一层，必须跨作品算。

本模块用**骨架分布余弦**（不是 embedding）作代理：不依赖外部模型，可离线复现。
输出两两相似度矩阵与聚合量，不输出「像不像 AI」的判定（ADR-2）。
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

from . import fingerprint as fp
from .errors import AnalysisError

#: 视为「几乎同构」的骨架分布余弦阈值（**未标定**，只用于标记 top 对）
NEAR_IDENTICAL_SIM = 0.90
#: 单篇最少小句数：低于此值的作品不参与两两比较（分布不稳）
MIN_CLAUSES_PER_WORK = 20


def _r(x: float, n: int = 3) -> float:
    v = round(float(x), n)
    return 0.0 if v == 0 else v


def _profile(text: str, backend=None) -> tuple[Counter, int]:
    from .text_processor import process

    doc = process(text, backend=backend)
    counter: Counter = Counter()
    for c in doc.clauses:
        if c.token_count >= 2:
            counter[fp.skeleton_key(c)] += 1
    return counter, sum(counter.values())


def _cosine(a: Counter, b: Counter) -> float:
    """骨架分布的余弦相似度（计数向量）。空向量返回 0.0。"""
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class CorpusReport:
    """语料级报告：两两相似度 + 每篇相对同侪的偏离。"""

    n_works: int
    n_compared: int
    mean_pairwise_similarity: float
    max_pair: dict | None
    min_pair: dict | None
    works: list[dict] = field(default_factory=list)
    matrix: list[dict] = field(default_factory=list)
    shared_patterns: dict | None = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "n_works": self.n_works,
            "n_compared": self.n_compared,
            "mean_pairwise_similarity": _r(self.mean_pairwise_similarity),
            "max_pair": self.max_pair,
            "min_pair": self.min_pair,
            "works": self.works,
            "matrix": self.matrix,
            "shared_patterns": self.shared_patterns,
            "notes": list(self.notes),
        }


def analyze_corpus(texts: dict[str, str], *, backend=None) -> CorpusReport:
    """比较一批作品的骨架分布相似度（Doshi 式集体多样性代理）。

    Args:
        texts: {作品名: 文本}，建议同体裁、同语言。
        backend: 可选的 NLP 后端；不给则用默认后端。

    Raises:
        AnalysisError: 少于 2 篇，或所有作品都太短（< MIN_CLAUSES_PER_WORK 小句）。
    """
    if not isinstance(texts, dict) or not texts:
        raise AnalysisError("语料分析需要 {作品名: 文本} 字典", hint="至少给 2 篇同体裁文本")
    if len(texts) < 2:
        raise AnalysisError(
            f"只给了 {len(texts)} 篇，跨作品比较至少要 2 篇",
            hint="单篇的同质化看 diversity.distribution；这里要的是作品之间的相似度",
        )

    profiles: dict[str, Counter] = {}
    sizes: dict[str, int] = {}
    for name, text in texts.items():
        counter, n = _profile(text, backend)
        if n:
            profiles[name] = counter
            sizes[name] = n

    usable = [n for n in profiles if sizes[n] >= MIN_CLAUSES_PER_WORK]
    if len(usable) < 2:
        raise AnalysisError(
            f"只有 {len(usable)} 篇达到 {MIN_CLAUSES_PER_WORK} 个小句，无法比较",
            hint="补更长的文本，或用更低的 MIN_CLAUSES_PER_WORK（需自行承担方差）",
        )

    sims: list[tuple[float, str, str]] = []
    for a, b in combinations(usable, 2):
        sims.append((_cosine(profiles[a], profiles[b]), a, b))
    sims.sort(reverse=True)
    mean_sim = sum(s for s, _, _ in sims) / len(sims)

    per_work: dict[str, list[float]] = {n: [] for n in usable}
    for s, a, b in sims:
        per_work[a].append(s)
        per_work[b].append(s)
    works = [
        {
            "name": name,
            "clauses": sizes[name],
            "distinct_patterns": len(profiles[name]),
            "mean_similarity_to_others": _r(sum(per_work[name]) / len(per_work[name])),
            "max_similarity_to_others": _r(max(per_work[name])),
        }
        for name in usable
    ]
    works.sort(key=lambda d: -d["mean_similarity_to_others"])

    matrix = [
        {"a": name, "b": other, "similarity": _r(_cosine(profiles[name], profiles[other]))}
        for name in usable
        for other in usable
        if name < other
    ]

    shared = None
    try:
        from .text_processor import process as _process

        docs = {n: _process(texts[n], backend=backend) for n in usable}
        shared = fp.cross_work_stats(docs)
    except Exception:  # noqa: BLE001 - 共享模式是加分项，失败不影响主结论
        shared = None

    best, worst = sims[0], sims[-1]
    notes: list[str] = [
        "相似度是**骨架分布余弦**，不是语义 embedding：文体同构能测，题材重复测不到",
        f"阈值 NEAR_IDENTICAL_SIM={NEAR_IDENTICAL_SIM} 与 MIN_CLAUSES_PER_WORK="
        f"{MIN_CLAUSES_PER_WORK} 均为**未标定**默认值",
        "均值高说明这批作品彼此更像（Doshi 的集体多样性下降方向），"
        "但同体裁、同作者、同题材料都会推高它——**不能单凭此判 AI**",
        "小样本（<5 篇）时均值波动大，看矩阵与 per-work 偏离更可靠",
    ]
    if len(usable) < 5:
        notes.append(f"仅比较了 {len(usable)} 篇（< 5），两两均值低置信")

    return CorpusReport(
        n_works=len(texts),
        n_compared=len(usable),
        mean_pairwise_similarity=mean_sim,
        max_pair={"a": best[1], "b": best[2], "similarity": _r(best[0]),
                  "near_identical": best[0] >= NEAR_IDENTICAL_SIM},
        min_pair={"a": worst[1], "b": worst[2], "similarity": _r(worst[0])},
        works=works,
        matrix=matrix,
        shared_patterns=shared,
        notes=notes,
    )
