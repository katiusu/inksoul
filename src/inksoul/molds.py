"""句法模具配额层（0.6.2 校准版）：结构模具密度，段级基线 + 复合判据。

为什么换成这个判据
------------------
0.6.1 的做法是「21 项各自对照人类 p90/p10，任一项越线即 FAIL」，且基线来自
**整本**密度（16 本书各一个点）。两个问题叠在一起：

1. 单位错配：基线是「整本」的密度分布，判的是 900 字的一章。文本越长，多数
   密度越稳定；拿整本的分布判一小段，方差被系统性低估。
2. 形态不可用：21 项各取 10% 尾概率，任一项越线的期望是 1-0.9**21 ≈ 89%。
   在 1288 个人类段上实测，逐项 veto 的假失败率是 81.9%——即使基线换成段级
   也一样，问题不在单位，在多指标同时硬否决。

校准后的做法（同一批 1288 段，留一本人交叉验证）：

  - 基线采样单位 = 判定单位 = 1000 字窗（han >= 600）；
  - 每项算段级 z = (密度 - 人类段均值) / 人类段标准差；
  - 复合分 = 东向截断 z 的均值（over 项取 max(0, z)，under 项取 max(0, -z)）；
  - 复合分超过人类段分布的 p95 才算偏离；
  - 假失败率：81.9% → 6.2%；AI 稿件 10/10 全部越线（区分力保留）。

下限项（感叹/省略/问号/叠词/引号对白）只做诊断输出：它们反映体裁惯例，
缺一项不代表「不像人」，写进改写指令会把文写平。

数据文件
--------
data/molds_baseline.json：16 本现代中文网文、1288 段 1000 字窗的逐段密度统计
（mean/sd/p10/p50/p90/p95/p99）与复合分分位。见 research/notes/molds-calibration-evidence.md。

用法
----
    from inksoul.molds import analyze_molds
    rep = analyze_molds(text)
    print(rep.as_text())
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_HAN = re.compile(r"[\u4e00-\u9fa5]")

#: 判定单位（汉字数；与基线采样单位一致）
WINDOW_CHARS = 1000
#: 窗内汉字少于此数就不判（密度在 600 字以下不稳）
MIN_WINDOW_HAN = 600
#: 正文少于这个汉字数直接给 INSUFFICIENT（<600 时密度方差过大，与窗级基线不可比）
MIN_TEXT_HAN = 600
#: 基线缺失时的兜底阈值（人类段复合分 p95）
DEFAULT_THRESHOLD = 0.67


def han_count(text: str) -> int:
    return len(_HAN.findall(text))


@dataclass(frozen=True)
class Mold:
    """一条结构模具。密度单位 = 次/千汉字。阈值不写死在这里，见 baseline()。"""

    key: str
    name: str
    pattern: str
    direction: str       # "over" | "under" | "neutral"
    note: str = ""


#: 顺序即输出顺序：14 项上限、5 项下限、3 项 neutral
MOLDS: tuple[Mold, ...] = (
    # ---- 上限：坐标化叙述 ----
    Mold("LOC", "坐标定位（鞋尖/沿口/墙根/缝/边）",
         r"(?:[裙领袖]口|[缝边角面]上|正中|沿口|墙根|鞋尖)", "over",
         "把物体写成方格位置；同源：空间轨迹、时间刻度"),
    Mold("TRACK", "空间轨迹（从X到Y / 往X）",
         r"(?:从[^。，]{1,10}到|往[^。，]{1,6}[，。]|[上下左右里外前后]移|换到)", "over"),
    Mold("CLOCK", "时间刻度（第N遍/几点/分钟）",
         r"(?:第[一二三四五六七八九十百]+[分钟遍级]|[一二三四五六七八九十]+点[一二三四五六七八九十]*分?)", "over"),
    Mold("BA", "真处置把字句",
         r"(?:一|两|几|三|半)?把[^。，]{1,12}(?:了|着|上|下|起|回|开|走|来|去|进|过)[^。，]{0,6}[，。]", "over",
         "原始正则 把[^。，]{1,12}[，。] 在人类样本全是量词假阳性（两把刀/一把扯下纸罩）"),
    Mold("ORD", "序数（第x次/遍/回）",
         r"第[一二三四五六七八九十百]+[次遍回轮]", "over"),
    Mold("NUM", "量词精确计数",
         r"[二三四五六七八九十两第][一二三四五六七八九十]*[遍次级层步秒分米厘元号格班排枚颗截只双道根条]", "over"),
    Mold("VERB", "动作动词串（拧抹按推拉提抽挪捏压…）",
         r"(?:拧|抹|按|推|拉|提|抽|挪|捏|压)[^。，]{0,6}[，]", "over",
         "「挪到脚趾/挪到手指/挪到牙齿」是穷举流水账；「走到尾骨那儿停住」是慢镜头，靠语义判断"),
    Mold("SEQ", "序列副词连用（先/再/然后/最后）",
         r"(?:先|再|然后|最后|接着)[^。！？]{0,12}(?:再|然后|最后|接着)", "over"),
    Mold("YIJIU", "一…就…",
         r"一[^。，]{0,6}就[^。，]{0,6}", "over"),
    Mold("ZHE", "着 持续体",
         r"[一-龥]着[^。，]{0,4}[，。]", "over"),
    Mold("DIR", "趋向补语（起来/下去/出来/进去…）",
         r"(?:起来|下去|出来|进去|过来|回去|上来|下来)", "over"),
    Mold("ZSUBJ", "零主语小句",
         r"(?:^|[。，])[一-龥]{1,2}(?:看|走|坐|站|说|想|笑|拿|放|推|拉|抬|低|转|停)[^。，]{0,6}[，。]", "over"),
    Mold("POS", "方位短语（在X上/里/中）",
         r"在[^。，]{1,10}(?:上|里|中|内|下)", "over"),
    Mold("GUO", "过 经历体",
         r"[一-龥]过[^。，]{0,4}[，。]", "over"),
    # ---- 下限：另一套语法平面（只诊断，不否决）----
    Mold("EXCL", "感叹号", r"！", "under", "缺 = 没有情绪爆发"),
    Mold("ELLIP", "省略号", r"…", "under", "缺 = 没有停顿/留白"),
    Mold("QUES", "问号", r"？", "under", "缺 = 没有疑问/自问/试探"),
    Mold("REDUP", "叠词", r"([一-龥])\1(?:的|地)?", "under", "缺 = 没有口语的重音"),
    Mold("QUOTE", "引号对白", r"(?:“[^”]{2,}”|「[^」]{2,}」)", "under",
         "0.6.2 起同时认 「」——本项目正文体例用直角引号，旧正则只认 “” 会误判全篇无对白"),
    # ---- neutral：人类本来就更多，别压 ----
    Mold("COLON", "冒号", r"：", "neutral", "人类均值 3.70、p90 6.33；不要和破折号混算"),
    Mold("DASH", "破折号（——）", r"——", "neutral",
         "人类一半样本几乎不用（p50 0.16），p90 0.95；它是风格开关，不是配额"),
    Mold("DTAIL", "句末破折号（—— 后紧接换行或句末标点）", r"——(?=[ \t]*(?:\n|$)|[。！？])", "neutral",
         "AI 专属手法：用破折号做「意味深长」的延宕，人类 p90 仅 0.13/千字"),
)

MOLD_MAP: dict[str, Mold] = {m.key: m for m in MOLDS}
_KEYS = {m.key: re.compile(m.pattern, re.M) for m in MOLDS}
#: 进复合分的项（neutral 只报数）
JUDGED = tuple(m for m in MOLDS if m.direction in ("over", "under"))


@lru_cache(maxsize=1)
def baseline() -> dict[str, Any]:
    path = Path(__file__).with_name("data") / "molds_baseline.json"
    if not path.is_file():
        return {"items": {}, "composite_p95": DEFAULT_THRESHOLD, "meta": {"missing": str(path)}}
    return json.loads(path.read_text(encoding="utf-8"))


def threshold() -> float:
    return float(baseline().get("composite_p95") or DEFAULT_THRESHOLD)


def _densities(text: str) -> dict[str, float]:
    n = han_count(text) or 1
    return {m.key: len(_KEYS[m.key].findall(text)) * 1000.0 / n for m in MOLDS}


def _composite_with(base: dict[str, Any], dens: dict[str, float]) -> tuple[float, dict[str, float]]:
    """复合分 = 单向截断 z 的均值。over 取 max(0,z)，under 取 max(0,-z)。"""
    zs: dict[str, float] = {}
    total = 0.0
    missing = 0
    for m in JUDGED:
        st = (base.get("items") or {}).get(m.key)
        if not st:
            missing += 1
            continue
        sd = st.get("sd") or 1e-9
        z = (dens[m.key] - st["mean"]) / sd
        # 截尾：个别项（NUM/POS）人类分布右偏严重，单个 z=5.7 会独占复合分；
        # 截到 ±3（约 0.1% 尾部）保留方向、不让单项绑架整段判定。
        z = max(-3.0, min(3.0, z))
        zs[m.key] = z
        total += max(0.0, z) if m.direction == "over" else max(0.0, -z)
    denom = max(1, len(JUDGED) - missing)
    return total / denom, zs


def composite(dens: dict[str, float]) -> tuple[float, dict[str, float]]:
    return _composite_with(baseline(), dens)


@dataclass
class Row:
    key: str
    name: str
    direction: str
    count: int
    per_1000: float
    mean: float
    sd: float
    p_ref: float          # 人类分位参考：over/neutral → p90，under → p10
    z: float
    contribution: float   # 对复合分的贡献（单向截断后）
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "name": self.name, "direction": self.direction,
            "count": self.count, "per_1000": round(self.per_1000, 2),
            "human_mean": round(self.mean, 3), "human_sd": round(self.sd, 3),
            "human_ref": round(self.p_ref, 3), "z": round(self.z, 2),
            "contribution": round(self.contribution, 3), "note": self.note,
        }


@dataclass
class WindowResult:
    index: int
    n_chars: int
    composite: float
    verdict: str

    def as_dict(self) -> dict[str, Any]:
        return {"index": self.index, "n_chars": self.n_chars,
                "composite": round(self.composite, 3), "verdict": self.verdict}


@dataclass
class MoldReport:
    n_chars: int
    rows: list[Row] = field(default_factory=list)
    windows: list[WindowResult] = field(default_factory=list)
    threshold: float = DEFAULT_THRESHOLD
    worst_index: int = 0
    insufficient: bool = False

    @property
    def verdict(self) -> str:
        if self.insufficient:
            return "INSUFFICIENT"
        if not self.windows:
            return "PASS"
        return self.windows[self.worst_index].verdict

    @property
    def composite_score(self) -> float:
        return self.windows[self.worst_index].composite if self.windows else 0.0

    @property
    def pass_rate(self) -> str:
        if not self.windows:
            return "0/0"
        ok = sum(1 for w in self.windows if w.verdict == "PASS")
        return "%d/%d" % (ok, len(self.windows))

    def diagnostics_top(self, k: int = 3) -> list[Row]:
        return sorted(self.rows, key=lambda r: -r.contribution)[:k]

    def under_missing(self) -> list[Row]:
        return [r for r in self.rows if r.direction == "under" and r.count == 0]

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_chars": self.n_chars,
            "verdict": self.verdict,
            "composite": round(self.composite_score, 3),
            "composite_threshold": round(self.threshold, 3),
            "pass_rate": self.pass_rate,
            "windows": [w.as_dict() for w in self.windows],
            "worst_window": self.worst_index,
            "rows": [r.as_dict() for r in self.rows],
            "under_missing": [r.key for r in self.under_missing()],
        }

    def as_text(self) -> str:
        if self.insufficient:
            return "模具报告  正文 %d 汉字：不足 %d 字，密度不可比，不判。" % (self.n_chars, MIN_TEXT_HAN)
        out = ["模具报告  正文 %d 汉字 → %d 个 %d 字窗" % (self.n_chars, len(self.windows), WINDOW_CHARS)]
        out.append("复合偏离 z（最差窗）= %.2f    人类段 p95 = %.2f    窗级通过 %s    VERDICT: %s" % (
            self.composite_score, self.threshold, self.pass_rate, self.verdict))
        top = [r for r in self.diagnostics_top(3) if r.contribution > 0.05]
        if top:
            out.append("偏离贡献最大（诊断：报 z，不单独判死刑）：")
            for r in top:
                out.append("  %-6s %-20s %5.1f/千字  人类 %4.2f±%4.2f  p%s %4.2f  z=%+.2f" % (
                    r.key, r.name, r.per_1000, r.mean, r.sd,
                    "90" if r.direction != "under" else "10", r.p_ref, r.z))
        miss = self.under_missing()
        if miss:
            out.append("下限项本段未出现（诊断，不进否决）：%s" % "、".join("%s %s" % (r.key, r.name) for r in miss))
        if self.verdict == "PASS":
            out.append("落在人类段级分布内。注意：人类自身也有约 5% 的段越线，PASS 只说明「不偏离人群」，不是「像人」。")
        if len(self.windows) > 1:
            bad = [w for w in self.windows if w.verdict != "PASS"]
            if bad:
                out.append("越线窗：%s" % "、".join("#%d(z=%.2f)" % (w.index, w.composite) for w in bad[:6]))
        return "\n".join(out)


def _split_windows(text: str) -> list[str]:
    """按 raw 字符切 1000 字窗（与基线采样完全同法），不足一个窗就整段当一窗。"""
    n = han_count(text)
    if n < WINDOW_CHARS + 200:
        return [text]
    wins = [text[i:i + WINDOW_CHARS] for i in range(0, len(text), WINDOW_CHARS)]
    kept = [w for w in wins if han_count(w) >= MIN_WINDOW_HAN]
    return kept or [text]


def analyze_molds(text: str) -> MoldReport:
    n = han_count(text)
    if n == 0:
        raise ValueError("正文没有汉字，无法测量")
    if n < MIN_TEXT_HAN:
        return MoldReport(n_chars=n, insufficient=True, threshold=threshold())

    base = baseline()
    thr = threshold()
    windows: list[WindowResult] = []
    rows_by_win: list[list[Row]] = []
    for i, w in enumerate(_split_windows(text)):
        dens = _densities(w)
        score, zs = _composite_with(base, dens)
        verdict = "DRIFT" if score > thr else "PASS"
        windows.append(WindowResult(i, han_count(w), score, verdict))
        rows: list[Row] = []
        for m in MOLDS:
            st = (base.get("items") or {}).get(m.key) or {}
            z = zs.get(m.key, 0.0)
            contrib = (max(0.0, z) if m.direction == "over" else max(0.0, -z)) if m.direction in ("over", "under") else 0.0
            ref = st.get("p90" if m.direction != "under" else "p10", 0.0)
            rows.append(Row(
                key=m.key, name=m.name, direction=m.direction,
                count=len(_KEYS[m.key].findall(w)), per_1000=dens[m.key],
                mean=float(st.get("mean", 0.0)), sd=float(st.get("sd", 0.0)),
                p_ref=float(ref), z=z, contribution=contrib, note=m.note,
            ))
        rows_by_win.append(rows)

    worst = max(range(len(windows)), key=lambda i: windows[i].composite)
    return MoldReport(n_chars=n, rows=rows_by_win[worst], windows=windows,
                      threshold=thr, worst_index=worst)


def gate_text(text: str, **kw: Any) -> tuple[str, str]:
    """返回 (VERDICT, 可读报告)。"""
    rep = analyze_molds(text)
    return rep.verdict, rep.as_text()
