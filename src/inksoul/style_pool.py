"""人类文风池：把「像不像人」变成到人类池中心的距离（相对量），而不是绝对阈值。

背景：v0.4.4 的配对评测证明，按单一作者标定的绝对密度（每千字多少被动句）无法区分
人类与 deepseek-chat（AUC 0.29-0.52）。本模块改测「距离」：同体裁人类池的 mean/std，
用它把一篇稿子投影到 z 空间，取加权 L2 距离，越低越接近该体裁的人类写法。
"""
from __future__ import annotations

import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Iterable

DIMS = (
    "reuse_rate",            # fingerprint：小句骨架重复率，AI 偏高
    "mean_pairwise_similarity",  # fingerprint：句间骨架相似度，AI 偏高
    "conj_per_kchar",        # style：连接词密度，AI 偏低
    "long_sentence_share",   # style：长句占比，AI 更平均
    "dialogue_ratio",        # narrative：对白占比，强依赖 brief 类型
    "information_density_mean",  # narrative：单位篇幅信息量
)

DIM_LABELS = {
    "reuse_rate": "骨架复用率",
    "mean_pairwise_similarity": "句间骨架相似度",
    "conj_per_kchar": "连接词密度/千字",
    "long_sentence_share": "长句占比",
    "dialogue_ratio": "对白占比",
    "information_density_mean": "信息密度",
}

WEIGHTS = {d: 1.0 for d in DIMS}
MIN_NARRATIVE = 400
DEFAULT_POOL = Path(__file__).with_name("data") / "human_style_zh.json"


def metrics_from_dict(data: dict[str, Any]) -> dict[str, float]:
    """从已经算好的分析报告（as_dict）取六个可比维度。"""
    style = data.get("style") or {}
    nar = data.get("narrative") or {}
    fp = data.get("fingerprint") or {}
    raw = {
        "reuse_rate": fp.get("reuse_rate"),
        "mean_pairwise_similarity": fp.get("mean_pairwise_similarity"),
        "conj_per_kchar": style.get("conj_per_kchar"),
        "long_sentence_share": style.get("long_sentence_share"),
        "dialogue_ratio": nar.get("dialogue_ratio", style.get("dialogue_ratio")),
        "information_density_mean": nar.get("information_density_mean"),
    }
    out: dict[str, float] = {}
    for k in DIMS:
        v = raw.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = float(v)
    return out


def metrics_of(text: str, analyzer: Any) -> dict[str, float]:
    """从 Analyzer 直接算六个维度。"""
    return metrics_from_dict(analyzer.analyze(text).as_dict())


def _quantiles(vals: list[float]) -> dict[str, float]:
    s = sorted(vals)
    n = len(s)

    def q(p: float) -> float:
        if n == 1:
            return float(s[0])
        pos = p * (n - 1)
        lo = int(math.floor(pos))
        hi = min(lo + 1, n - 1)
        return float(s[lo] + (s[hi] - s[lo]) * (pos - lo))

    return {
        "mean": round(statistics.mean(s), 4),
        "std": round(statistics.pstdev(s), 4) if n > 1 else 0.0,
        "p10": round(q(0.10), 4),
        "p90": round(q(0.90), 4),
    }


def summarize(rows: Iterable[dict[str, float]]) -> dict[str, dict[str, float]]:
    rows = list(rows)
    out: dict[str, dict[str, float]] = {}
    for k in DIMS:
        vals = [r[k] for r in rows if k in r]
        if vals:
            out[k] = _quantiles(vals)
    return out


def distance(vec: dict[str, float], pool: dict[str, Any], genre: str = "网文") -> float | None:
    """到池中心的加权 z 距离；缺维度自动降权。"""
    table = ((pool.get("genres") or {}).get(genre) or {}).get("dims") or {}
    if not table:
        return None
    acc = 0.0
    wsum = 0.0
    for k, stats in table.items():
        if k not in vec:
            continue
        std = stats.get("std") or 0.0
        if std <= 1e-9:
            continue
        z = (vec[k] - stats["mean"]) / std
        z = max(-3.0, min(3.0, z))
        w = WEIGHTS.get(k, 1.0)
        acc += w * z * z
        wsum += w
    if wsum <= 0:
        return None
    return round(math.sqrt(acc / wsum), 4)


def dim_report(vec: dict[str, float], pool: dict[str, Any], genre: str = "网文") -> list[dict[str, Any]]:
    """逐维 z 值，用于解释「哪一项不像人」。"""
    table = ((pool.get("genres") or {}).get(genre) or {}).get("dims") or {}
    rows = []
    for k in DIMS:
        if k not in vec or k not in table:
            continue
        stats = table[k]
        std = stats.get("std") or 0.0
        z = 0.0 if std <= 1e-9 else (vec[k] - stats["mean"]) / std
        rows.append({"dim": k, "label": DIM_LABELS[k], "value": round(vec[k], 3),
                     "mean": stats["mean"], "z": round(z, 2)})
    rows.sort(key=lambda r: abs(r["z"]), reverse=True)
    return rows


def load_pool(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_POOL
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def sample_chunks(text: str, *, size: int = 900, count: int = 120, seed: int = 0,
                  min_narrative: int = MIN_NARRATIVE, analyzer: Any) -> list[tuple[str, dict[str, float]]]:
    """随机取段并算六维；叙述字数不足的段丢弃。"""
    rng = random.Random(seed)
    out: list[tuple[str, dict[str, float]]] = []
    tries = 0
    limit = count * 40
    while len(out) < count and tries < limit:
        tries += 1
        a = rng.randrange(0, max(1, len(text) - size))
        seg = text[a:a + size]
        if not seg.strip():
            continue
        try:
            vec = metrics_of(seg, analyzer)
        except Exception:
            continue
        if len(vec) < len(DIMS):
            continue
        out.append((seg, vec))
    return out


def build_pool(books: dict[str, str], *, genre: str = "网文", size: int = 900,
               per_book: int = 120, seed: int = 20261107, analyzer: Any) -> dict[str, Any]:
    """books: {书名: 全文}。同时保留每本书的子分布，用来检查作者间差异。"""
    all_rows: list[dict[str, float]] = []
    per_book_stats: dict[str, Any] = {}
    for i, (title, text) in enumerate(books.items()):
        rows = sample_chunks(text, size=size, count=per_book, seed=seed + i, analyzer=analyzer)
        vecs = [v for _, v in rows]
        all_rows.extend(vecs)
        per_book_stats[title] = {"chunks": len(vecs), "dims": summarize(vecs)}
        print("  %s: %d 段" % (title, len(vecs)), flush=True)
    return {
        "version": 1,
        "method": "人类池 z 距离：每段 %d 字，六维 mean/std，距离为加权 z 的 L2" % size,
        "dims": list(DIMS),
        "genres": {genre: {"chunks": len(all_rows), "books": list(books),
                           "dims": summarize(all_rows), "per_book": per_book_stats}},
    }


_ANALYZER_CACHE = None


def _analyzer():
    """复用同一 Analyzer（jieba 首次加载约 1s，之后每千字约 0.1s）。"""
    global _ANALYZER_CACHE
    if _ANALYZER_CACHE is None:
        from .analyzer import Analyzer
        from .config import InkSoulConfig

        _ANALYZER_CACHE = Analyzer(InkSoulConfig())
    return _ANALYZER_CACHE


def distance_of_text(text, pool=None, analyzer=None):
    """一段文本到人类池的距离；池缺失或算不出来时返回 None（不阻断调用方）。"""
    if not text or len(text.strip()) < 60:
        return None
    try:
        return distance(metrics_of(text, analyzer or _analyzer()), pool)
    except Exception:  # noqa: BLE001 - 覆盖缺失时静默降级
        return None
