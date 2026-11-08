"""句法模具配额层：小说体的结构模具密度 + 上下限双边判据。

为什么需要这一层
----------------
markers.py 的八族（名词化/定语链/并列/被动/连接词/抽象/比喻/四字格）面向议论文体：
在 第01章 上 8/8 都没超标，四字格密度 0.27 反而远低于人类 p50 4.05——方向反了。
小说体的 AI 味来自另一套结构模具：把一切写成「坐标系上的位置」——

  - 空间坐标：鞋尖 / 沿口 / 墙根 / 缝 / 正中
  - 空间轨迹：从腰头到第三遍 / 从左臀到右臀 / 往走廊尽头
  - 时间坐标：第几级台阶 / 第几分钟 / 第几遍熨

数字只是这套坐标的刻度，不是问题本身。所以本层测的是**模具**（可数结构），
不测「像不像 AI」。

双边判据
--------
只设上限会写得更平。这一章同时有 14 项超人类 p90、5 项低于人类 p10（感叹/省略/
问号/叠词/对白全部缺失）——单调的真正原因是**只用一个语法平面**。因此每项都标注
方向：

  OVER   超过人类 p90 → 要减
  UNDER  低于人类 p10 → 要补
  NEUTRAL 人类本来就更多（破折号、日历跨度、了字连用）→ 不要压

基线来源
--------
experiment/corpus/human/*.txt 的 16 本现代中文网文，共 1,629,419 汉字，逐本算密度后
取 mean/p10/p90（不用全书合并值，避免长书dominate）。密度单位：次/千汉字。

用法
----
    from inksoul.molds import analyze_molds
    rep = analyze_molds(text)
    print(rep.as_text())
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_HAN = re.compile(r"[\u4e00-\u9fa5]")


def han_count(text: str) -> int:
    return len(_HAN.findall(text))


@dataclass(frozen=True)
class Mold:
    """一条结构模具。密度单位 = 次/千汉字。"""

    key: str
    name: str
    pattern: str
    mean: float          # 16 本人类均值
    p10: float           # 人类 10 分位（下限参考）
    p90: float           # 人类 90 分位（上限参考）
    direction: str       # "over" | "under" | "neutral"
    note: str = ""

    def compile(self) -> re.Pattern[str]:
        return re.compile(self.pattern, re.M)


#: 顺序即输出顺序：先上限（14 项），再下限（5 项），最后 neutral（3 项）
MOLDS: tuple[Mold, ...] = (
    # ---- 上限：坐标化叙述（三项同源，合计指向同一笔法）----
    Mold("LOC", "坐标定位（鞋尖/沿口/墙根/缝/边）",
         r"(?:[裙领袖]口|[缝边角面]上|正中|沿口|墙根|鞋尖)", 0.1596, 0.0498, 0.2139, "over",
         "把物体写成方格位置；同源：空间轨迹、时间刻度"),
    Mold("TRACK", "空间轨迹（从X到Y / 往X）",
         r"(?:从[^。，]{1,10}到|往[^。，]{1,6}[，。]|[上下左右里外前后]移|换到)", 0.3692, 0.1809, 0.5863, "over"),
    Mold("CLOCK", "时间刻度（第N遍/几点/分钟）",
         r"(?:第[一二三四五六七八九十百]+[分钟遍级]|[一二三四五六七八九十]+点[一二三四五六七八九十]*分?)", 0.343, 0.1356, 0.6055, "over"),
    Mold("BA", "真处置把字句",
         r"(?:一|两|几|三|半)?把[^。，]{1,12}(?:了|着|上|下|起|回|开|走|来|去|进|过)[^。，]{0,6}[，。]", 0.326, 0.0754, 0.5081, "over",
         "原始正则把[^。，]{1,12}[，。] 在人类样本全是量词假阳性（两把刀/一把扯下纸罩）"),
    Mold("ORD", "序数（第x次/遍/回）",
         r"第[一二三四五六七八九十百]+[次遍回轮]", 0.1172, 0.0609, 0.1948, "over"),
    Mold("NUM", "量词精确计数",
         r"[二三四五六七八九十两第][一二三四五六七八九十]*[遍次级层步秒分米厘元号格班排枚颗截只双道根条]", 0.9881, 0.4624, 1.4099, "over"),
    Mold("VERB", "动作动词串（拧抹按推拉提抽挪捏压…）",
         r"(?:拧|抹|按|推|拉|提|抽|挪|捏|压)[^。，]{0,6}[，]", 1.0222, 0.6936, 1.4319, "over",
         "「挪到脚趾/挪到手指/挪到牙齿」是穷举流水账；「走到尾骨那儿停住」是慢镜头，靠语义判断"),
    Mold("SEQ", "序列副词连用（先/再/然后/最后）",
         r"(?:先|再|然后|最后|接着)[^。！？]{0,12}(?:再|然后|最后|接着)", 0.1297, 0.0918, 0.1676, "over"),
    Mold("YIJIU", "一…就…",
         r"一[^。，]{0,6}就[^。，]{0,6}", 0.3172, 0.0305, 0.5814, "over"),
    Mold("ZHE", "着 持续体",
         r"[一-龥]着[^。，]{0,4}[，。]", 2.5223, 1.5423, 3.5533, "over"),
    Mold("DIR", "趋向补语（起来/下去/出来/进去…）",
         r"(?:起来|下去|出来|进去|过来|回去|上来|下来)", 3.0325, 2.1187, 3.5838, "over"),
    Mold("ZSUBJ", "零主语小句",
         r"(?:^|[。，])[一-龥]{1,2}(?:看|走|坐|站|说|想|笑|拿|放|推|拉|抬|低|转|停)[^。，]{0,6}[，。]", 1.8072, 1.3312, 2.2813, "over"),
    Mold("POS", "方位短语（在X上/里/中）",
         r"在[^。，]{1,10}(?:上|里|中|内|下)", 3.7953, 2.447, 4.7153, "over"),
    Mold("GUO", "过 经历体",
         r"[一-龥]过[^。，]{0,4}[，。]", 2.2478, 1.7003, 2.7883, "over"),
    # ---- 下限：被缺掉的「另一个语法平面」----
    Mold("EXCL", "感叹号", r"！", 4.995, 1.3602, 7.578, "under", "缺 = 没有情绪爆发"),
    Mold("ELLIP", "省略号", r"…", 5.1516, 0.6968, 9.937, "under", "缺 = 没有停顿/留白"),
    Mold("QUES", "问号", r"？", 4.2654, 2.7015, 6.486, "under", "缺 = 没有疑问/自问/试探"),
    Mold("REDUP", "叠词", r"([一-龥])\1(?:的|地)?", 7.8383, 5.0096, 10.4784, "under", "缺 = 没有口语的重音"),
    Mold("QUOTE", "引号对白", r"“[^”]{2,}”", 10.1391, 7.5236, 12.0547, "under", "缺 = 没有人在说话"),
    # ---- neutral：人类本来就更多，别压 ----
    Mold("DASH", "破折号/冒号", r"[—：]", 4.583, 1.1461, 6.4842, "neutral"),
)

MOLD_MAP: dict[str, Mold] = {m.key: m for m in MOLDS}
_KEYS = {m.key: m.compile() for m in MOLDS}


@dataclass
class Row:
    key: str
    name: str
    direction: str
    count: int
    per_1000: float
    mean: float         # 16 本人类均值（倍数以此为准）
    ref: float          # over→p90 / under→p10 / neutral→mean
    ratio: float        # per_1000 / ref（ref=0 时用 inf 或 0）
    status: str         # "OVER" | "UNDER" | "OK" | "NEG"
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "name": self.name, "status": self.status,
            "count": self.count, "per_1000": round(self.per_1000, 2),
            "mean": round(self.mean, 2),
            "ref": round(self.ref, 2),
            "ratio": (round(self.ratio, 2) if self.ratio != float("inf") else None),
            "note": self.note,
        }


@dataclass
class MoldReport:
    n_chars: int
    rows: list[Row] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)   # 段太短，下限不下判

    @property
    def over(self) -> list[Row]:
        return [r for r in self.rows if r.status == "OVER"]

    @property
    def under(self) -> list[Row]:
        return [r for r in self.rows if r.status == "UNDER"]

    @property
    def verdict(self) -> str:
        if self.over:
            return "OVER"
        if self.under:
            return "UNDER"
        return "PASS"

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_chars": self.n_chars,
            "verdict": self.verdict,
            "over": [r.as_dict() for r in self.over],
            "under": [r.as_dict() for r in self.under],
            "rows": [r.as_dict() for r in self.rows],
        }

    def as_text(self) -> str:
        out = ["模具报告  正文 %d 汉字" % self.n_chars]
        over = self.over
        under = self.under
        if over:
            out.append("超上限 %d 项（人类 p90 之上，要减）：" % len(over))
            for r in sorted(over, key=lambda x: -x.ratio):
                out.append("  %-6s %-20s %5.1f/千字   均值 %4.2f  p90 %4.2f   %4.1f×" % (
                    r.key, r.name, r.per_1000, r.mean, r.ref, r.ratio))
        if under:
            out.append("低于下限 %d 项（人类 p10 之下，要补）：" % len(under))
            for r in sorted(under, key=lambda x: x.ratio):
                out.append("  %-6s %-20s %5.1f/千字   均值 %4.2f  p10 %4.2f   %4.2f×   %s" % (
                    r.key, r.name, r.per_1000, r.mean, r.ref, r.ratio, r.note))
        if not over and not under:
            out.append("VERDICT: PASS  模具密度全部落在人类 p10–p90 区间")
        if self.excluded:
            out.append("（段长 %d < 600 字，下限项 %s 不判）" % (self.n_chars, "、".join(self.excluded)))
        return "\n".join(out)


def analyze_molds(text: str, *, min_chars_for_under: int = 600) -> MoldReport:
    n = han_count(text)
    if n == 0:
        raise ValueError("正文没有汉字，无法测量")
    rows: list[Row] = []
    excluded: list[str] = []
    for m in MOLDS:
        count = len(_KEYS[m.key].findall(text))
        dens = count / n * 1000
        mean = m.mean
        if m.direction == "over":
            ref, status = m.p90, ("OVER" if dens > m.p90 else "OK")
            ratio = dens / mean if mean else (float("inf") if dens else 0.0)
        elif m.direction == "under":
            ref = m.p10
            if n < min_chars_for_under:
                status, ratio = "NEG", (dens / mean if mean else 0.0)
                excluded.append(m.key)
            else:
                status = "UNDER" if dens < m.p10 else "OK"
                ratio = dens / mean if mean else 0.0
        else:
            ref = m.mean
            status = "NEG"
            ratio = dens / mean if mean else 0.0
        rows.append(Row(m.key, m.name, m.direction, count, dens, mean, ref, ratio, status, m.note))
    return MoldReport(n_chars=n, rows=rows, excluded=excluded)


def gate_text(text: str, **kw: Any) -> tuple[str, str]:
    """返回 (VERDICT, 可读报告)。"""
    rep = analyze_molds(text, **kw)
    return rep.verdict, rep.as_text()

