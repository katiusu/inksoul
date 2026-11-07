"""词汇多样性：TTR / MTLD / MATTR / MSTTR / HDD。

依据：Kendro, Maloney & Jarvis 2026（IJAL）用六个维度测 LLM 词汇多样性，发现 AI 文本的
词汇多样性**高于**人类；所以多样性的高低本身不是「像不像人」的判据，必须与体裁基线并列。
本模块只算指标，不给结论。

为什么要多个指标：TTR 随文本变长单调下降（同一段文字截一半 TTR 就变），
所以长文本之间的 TTR 不可比。MTLD 与 MATTR 是长度稳健的替代：

- **MTLD**（McCarthy 2005, McCarthy & Jarvis 2010）：沿文本滑动，累计 TTR 跌破阈值
  （默认 0.72）就切一个「因子」，MTLD = 总词数 / 因子数。前向、后向各算一次取平均，
  消除方向偏差。**阈值敏感**，换阈值会整体平移，但同一阈值下可比。
- **MATTR**（Covington & McFall 2010）：固定窗口（默认 50 词）滑动平均 TTR。
- **MSTTR**（Johnson 1944 / Hess 等）：切成不重叠的 100 词段，段内 TTR 取平均。
- **HDD**（McCarthy & Jarvis 2007）：超几何分布 D——「随机抽 42 个词，期望有多少个
  不同类型」除以 42，长度极稳，但短文本方差大。
"""
from __future__ import annotations

import math
from collections import Counter

#: MATTR 滑窗大小（词）
MATTR_WINDOW = 50
#: MSTTR 分段大小（词）
MSTTR_SEGMENT = 100
#: MTLD 的 TTR 阈值
MTLD_TTR = 0.72
#: HDD 抽样规模（McCarthy & Jarvis 的固定值，不要改）
HDD_SAMPLE = 42
#: 低于此词数时只报 TTR，其它指标记 None（波动太大）
MIN_TOKENS = 50


def _r(x: float, n: int = 3) -> float:
    v = round(float(x), n)
    return 0.0 if v == 0 else v


def ttr(tokens: list[str]) -> float:
    """类型/词符比。短文本可用，长文本会随长度下降。"""
    return len(set(tokens)) / len(tokens) if tokens else 0.0


def mattr(tokens: list[str], window: int = MATTR_WINDOW) -> float | None:
    """滑动窗口平均 TTR（固定窗口 ⇒ 与文本长度无关）。"""
    if len(tokens) < window:
        return None
    vals = []
    for i in range(len(tokens) - window + 1):
        chunk = tokens[i:i + window]
        vals.append(len(set(chunk)) / window)
    return sum(vals) / len(vals)


def msttr(tokens: list[str], segment: int = MSTTR_SEGMENT) -> float | None:
    """不重叠分段平均 TTR；不足一段返回 None。"""
    if len(tokens) < segment:
        return None
    segs = [tokens[i:i + segment] for i in range(0, len(tokens) - segment + 1, segment)]
    if not segs:
        return None
    return sum(len(set(s)) / len(s) for s in segs) / len(segs)


def _mtld_one(seq: list[str], threshold: float) -> float:
    """单向 MTLD：因子数 = TTR 跌破阈值的次数（含末尾不完备因子）。"""
    factors = 0.0
    types: set[str] = set()
    count = 0
    for w in seq:
        count += 1
        types.add(w)
        if count and len(types) / count <= threshold:
            factors += 1.0
            types.clear()
            count = 0
    if count:  # 末尾残段按 TTR 折算成不完备因子
        residual = len(types) / count
        if residual < 1.0:
            factors += (1.0 - residual) / (1.0 - threshold)
    if factors <= 0:
        return float(len(seq))
    return len(seq) / factors


def mtld(tokens: list[str], threshold: float = MTLD_TTR) -> float | None:
    """MTLD = 前向与后向的平均（McCarthy & Jarvis 2010）。"""
    if not tokens:
        return None
    fwd = _mtld_one(tokens, threshold)
    bwd = _mtld_one(list(reversed(tokens)), threshold)
    return (fwd + bwd) / 2.0


def hdd(tokens: list[str], sample: int = HDD_SAMPLE) -> float | None:
    """超几何分布 D（McCarthy & Jarvis 2007）：随机抽 sample 个词的期望类型数 / sample。

    对每个类型 i（出现 f_i 次）算它被抽中的概率 1 - C(n-f_i, sample)/C(n, sample)，
    按类型求和即样本期望类型数，再除以 sample。抽样规模固定为 sample，
    所以指标不随全文长度漂移（旧实现按 1..sample 逐步累加概率，实为长度曲线）。
    """
    n = len(tokens)
    if n < sample or n <= 0:
        return None
    den = math.comb(n, sample)
    if not den:
        return None
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    expected = 0.0
    for f in counts.values():
        miss = math.comb(n - f, sample) if n - f >= sample else 0
        expected += 1.0 - miss / den
    return expected / sample


def lexical_indices(tokens: list[str], *, min_tokens: int = MIN_TOKENS) -> dict:
    """一次算全套；词数不足时 MTld/MATTR 等记 None 并在 notes 里说明。"""
    clean = [t for t in tokens if t and t.strip()]
    n = len(clean)
    out = {
        "token_count": n,
        "type_count": len(set(clean)),
        "ttr": _r(ttr(clean)),
        "mtld": None,
        "mattr": None,
        "msttr": None,
        "hdd": None,
        "params": {
            "mattr_window": MATTR_WINDOW,
            "msttr_segment": MSTTR_SEGMENT,
            "mtld_ttr": MTLD_TTR,
            "hdd_sample": HDD_SAMPLE,
        },
        "notes": [],
    }
    if n < min_tokens:
        out["notes"].append(
            f"仅 {n} 个词（< {min_tokens}），只报 TTR；MTLD/MATTR/MSTTR/HDD 记 None"
        )
        return out
    out["mtld"] = _r(mtld(clean))
    out["mattr"] = _r(mattr(clean))
    out["msttr"] = _r(msttr(clean))
    out["hdd"] = _r(hdd(clean))
    if out["msttr"] is None:
        out["notes"].append(f"不足 {MSTTR_SEGMENT} 词，MSTTR 记 None")
    out["notes"].append(
        "词汇多样性高不等于「像人」：Kendro 2026 发现 AI 文本多样性反而更高，"
        "该指标只能与同体裁同长度的人类基线并列看"
    )
    return out
