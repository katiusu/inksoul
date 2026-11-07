"""风格计量：Burrows' Delta（字频风格距离）。

依据：O'Sullivan 2025（Humanities & Social Sciences Communications）用 Burrows' Delta +
层次聚类区分人类与 LLM 短篇：人类文本簇宽而松散，LLM 按模型紧抱团。

方法（Burrows 2002）：取语料里最高频的 N 个功能词/字，算每篇的相对频率，再对每个特征
在**全语料**上做 z 标准化；两篇的距离 = 所有特征 |z_a − z_b| 的平均。只看高频词 ⇒
对内容不敏感、对潜在风格指纹敏感。中文没有空格，用**字**作特征单位（虚词、语气词、
高频实词都会进入 top-N），这是本项目的实现选择，不是原文做法（原文是英文词）。

Delta 是**距离**：越大越不像。同一个语料内部，两两平均 Delta 高 = 这一组文本彼此差异大；
不能反过来读成「越像人越好」。
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

#: 参与 Delta 的高频字个数（Burrows 原文 100–500，取小值以适配短篇）
N_FEATURES = 100
#: 每篇最少有效字符数，低于此值不参与（相对频率不稳）
MIN_CHARS = 200

_WS = re.compile(r"\s+")
_PUNCT = "，。！？；：、「」『』（）《》〈〉…—～·,.!?;:\"'()[]{}<>/\\|-_=+*&^%$#@~"


def _chars(text: str) -> list[str]:
    """把文本切成「有效字符」：去空白、去标点、拉丁文转小写。"""
    t = _WS.sub("", text or "")
    out = []
    for ch in t:
        if ch in _PUNCT:
            continue
        if "A" <= ch <= "Z":
            out.append(ch.lower())
        else:
            out.append(ch)
    return out


@dataclass
class DeltaReport:
    n_texts: int
    n_usable: int
    n_features: int
    features: list[str]
    mean_pairwise_delta: float
    max_pair: dict | None
    min_pair: dict | None
    spread: float
    works: list[dict] = field(default_factory=list)
    matrix: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "n_texts": self.n_texts,
            "n_usable": self.n_usable,
            "n_features": self.n_features,
            "features": self.features,
            "mean_pairwise_delta": round(self.mean_pairwise_delta, 3),
            "max_pair": self.max_pair,
            "min_pair": self.min_pair,
            "spread": round(self.spread, 3),
            "works": self.works,
            "matrix": self.matrix,
            "notes": list(self.notes),
        }


def _r(x: float, n: int = 3) -> float:
    v = round(float(x), n)
    return 0.0 if v == 0 else v


def burrows_delta(
    texts: dict[str, str],
    *,
    n_features: int = N_FEATURES,
    min_chars: int = MIN_CHARS,
) -> DeltaReport:
    """算两两 Delta。

    Args:
        texts: 名称 → 文本。
        n_features: 取多少个最高频字作特征。
        min_chars: 少于该字符数的文本不参与。

    Raises:
        ValueError: 可用文本少于 2 篇。
    """
    chars = {name: _chars(t) for name, t in texts.items()}
    usable = {name: cs for name, cs in chars.items()
              if len(cs) >= min_chars and name in texts}
    if len(usable) < 2:
        raise ValueError(
            f"可用文本仅 {len(usable)} 篇（要求每篇 ≥{min_chars} 有效字符、且至少 2 篇）"
        )

    merged: Counter = Counter()
    for cs in usable.values():
        merged.update(cs)
    features = [ch for ch, _ in merged.most_common(n_features) if not ch.isdigit()]
    if not features:
        raise ValueError("没有可用的高频字特征（文本全是数字或字符太少），Delta 需至少 2 篇含汉字文本")

    # 相对频率矩阵
    rel: dict[str, list[float]] = {}
    for name, cs in usable.items():
        total = len(cs) or 1
        c = Counter(cs)
        rel[name] = [c.get(ch, 0) / total for ch in features]

    # 每个特征做 z 标准化（跨文本）
    names = list(usable)
    z: dict[str, list[float]] = {name: [] for name in names}
    for j in range(len(features)):
        col = [rel[name][j] for name in names]
        mean = sum(col) / len(col)
        var = sum((x - mean) ** 2 for x in col) / len(col)
        sd = math.sqrt(var)
        for name in names:
            z[name].append(0.0 if sd == 0 else (rel[name][j] - mean) / sd)

    deltas: dict[tuple[str, str], float] = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            d = sum(abs(x - y) for x, y in zip(z[a], z[b])) / len(features)
            deltas[(a, b)] = d

    per_work = []
    for name in names:
        others = [(deltas[tuple(sorted((name, o)))], o) for o in names if o != name]
        mean_d = sum(d for d, _ in others) / len(others)
        nearest_d, nearest = min(others)
        per_work.append({
            "name": name,
            "chars": len(chars[name]),
            "mean_delta": _r(mean_d),
            "nearest": nearest,
            "nearest_delta": _r(nearest_d),
        })
    per_work.sort(key=lambda w: w["mean_delta"], reverse=True)

    vals = list(deltas.values())
    mean_pair = sum(vals) / len(vals)
    spread = math.sqrt(sum((v - mean_pair) ** 2 for v in vals) / len(vals))
    max_pair = max(deltas.items(), key=lambda kv: kv[1])
    min_pair = min(deltas.items(), key=lambda kv: kv[1])

    notes = [
        "Delta 是距离：越大越不像；组内平均 Delta 高 = 这组文本彼此差异大（O'Sullivan 2025："
        "人类簇宽、LLM 按模型抱团）",
        f"特征单位是**字**（中文无空格的自适应选择），N={len(features)}；"
        "未标定阈值：这里不提供「Delta > X 即异常」的判定",
        "仅 2 篇时 z 标准化退化为二值方向，Delta 只有相对意义",
        "样本少于 5 篇时 spread 参考价值低",
    ]
    return DeltaReport(
        n_texts=len(texts),
        n_usable=len(names),
        n_features=len(features),
        features=features[:20],
        mean_pairwise_delta=_r(mean_pair),
        max_pair={"a": max_pair[0][0], "b": max_pair[0][1], "delta": _r(max_pair[1])},
        min_pair={"a": min_pair[0][0], "b": min_pair[0][1], "delta": _r(min_pair[1])},
        spread=_r(spread),
        works=per_work,
        matrix=[
            {"a": a, "b": b, "delta": _r(d)} for (a, b), d in deltas.items()
        ],
        notes=notes,
    )
