"""语法指纹引擎（L1 骨架 + 结构簇 + 修辞判据 + 体裁基线）。

实现依据 `docs/syntax_fingerprint.md`：

- **L1 骨架串**：`normalizer.to_pattern()` 把内容类折成通配 `*`，功能锚点（NEG / ADV_LIM /
  CONJ_* / PREP_* / DE_* / ASP）必须精确相等——这正是「词语不同、结构相同」可以被识别的原因。
- **加权编辑距离**：功能锚点替换代价 1.0、内容槽替换 0.15（同类）/0.25（异类），见 §3「主判据」。
- **结构簇**：先按骨架串精确分组，再与簇代表元比较（相似度 ≥ 0.6 且槽位模板一致）做星形归并（§5.1）。
- **机械复用嫌疑**：`freq ≥ 3 且 para_spread ≥ 2 且 gap_cv < 0.5`，另附 J1–J3 可解释证据（§6）。
  输出的是**嫌疑**，不是判定——须经标注实验标定后才能当评分器。
- **体裁基线**：coverage / novelty 双指标，**不合成单一总分**（§7.2）。

所有阈值集中在本文件顶部常量里，便于用实验数据重新标定（当前均为「未标定」默认值）。
"""
from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from . import normalizer as norm
from .text_processor import Clause, Document

# ---------------------------------------------------------------- 可标定阈值
CONTENT_SUB_COST_SAME = 0.15     # 同一内容类替换代价
CONTENT_SUB_COST_DIFF = 0.25     # 不同内容类替换代价
ANCHOR_SUB_COST = 1.0            # 功能锚点替换/增删代价
CLUSTER_SIM_THRESHOLD = 0.60     # 同簇相似度下限（§5.1 第 2 步）
SUSPECT_MIN_FREQ = 3             # 机械复用嫌疑最小频次
SUSPECT_MIN_PARA_SPREAD = 2      # 跨段落数下限
SUSPECT_MAX_GAP_CV = 0.5         # 间距变异系数上限
SUSPECT_MIN_RATE = 0.04          # 该骨架至少占全文小句的 4%（长文本护栏，未标定）
J1_POSITION_STDEV = 0.15         # 位置「高度固定」判据
J2_VARIATION_STDEV = 0.15        # 簇内变异「极小」判据
PAIR_SAMPLE_CLAUSES = 800        # 两两相似度参与计算的小句上限（O(n²)，超了先等距抽样）
VARIATION_SAMPLE = 60            # 簇内变异的成员上限（两两编辑距离 O(k²)，超了等距抽样）

#: J3 显式修辞标记（出现即倾向「修辞性重复」）
RHETORIC_MARKERS = (
    "如同", "仿佛", "宛如", "好像", "像是", "好似", "犹如",
    "一遍又一遍", "一次又一次", "反复", "不断", "愈发", "越发",
    "不再", "再也不是", "第一次", "最后一次",
)


# ---------------------------------------------------------------- 基础结构
def pattern_of(clause: Clause) -> tuple[str, ...]:
    """L1 通配模式（内容类 → `*`）：用于「同构」判定与 A/B 类例证。"""
    return norm.to_pattern(clause.skel)


def skeleton_key(clause: Clause) -> tuple[str, ...]:
    """L1 骨架串（功能类 + 内容类都保留）：结构簇的分组键（§5.1 第 1 步）。

    分簇必须用骨架串而不是通配模式：`他推开门` 与 `她关上了窗户` 的通配模式都是
    `PRON * P`，用通配模式分组会把全文所有短句并成一簇，簇内频次失去意义。
    """
    return tuple(clause.skel)


def _is_content_symbol(sym: str) -> bool:
    return sym == "*" or sym in norm.CONTENT_CLASSES or sym in ("QUANT", "NUM", "CL")


OPTIONAL_ANCHORS = {"ASP", "DE_N", "DE_ADV", "DE_COMP"}


def _indel_cost(sym: str) -> float:
    """可选标记（体标记、结构助词）增删便宜：`他推开门` 与 `他推开了门` 应视为同一结构。"""
    return 0.3 if sym in OPTIONAL_ANCHORS else ANCHOR_SUB_COST


def symbol_cost(a: str, b: str) -> float:
    """单符号替换代价（§3）：内容槽便宜、锚点昂贵。"""
    if a == b:
        return 0.0
    a_content, b_content = _is_content_symbol(a), _is_content_symbol(b)
    if a_content and b_content:
        return CONTENT_SUB_COST_SAME if a == b else CONTENT_SUB_COST_DIFF
    return ANCHOR_SUB_COST


def weighted_edit_distance(a: Sequence[str], b: Sequence[str]) -> float:
    """带权 Levenshtein。O(len(a)·len(b))，小句级长度（≤40）完全够用。"""
    if not a:
        return float(len(b)) * ANCHOR_SUB_COST
    if not b:
        return float(len(a)) * ANCHOR_SUB_COST
    prev = [i * ANCHOR_SUB_COST for i in range(len(b) + 1)]
    for i, ca in enumerate(a, 1):
        cur = [i * ANCHOR_SUB_COST]
        for j, cb in enumerate(b, 1):
            cost = symbol_cost(ca, cb)
            cur.append(min(prev[j] + _indel_cost(ca),        # 删除
                           cur[j - 1] + _indel_cost(cb),     # 插入
                           prev[j - 1] + cost))              # 替换
        prev = cur
    return prev[-1]


def similarity(pa: Sequence[str], pb: Sequence[str]) -> float:
    """归一到 0–1：1 表示结构完全同构。"""
    denom = max(len(pa), len(pb), 1) * ANCHOR_SUB_COST
    return max(0.0, 1.0 - weighted_edit_distance(pa, pb) / denom)


# ---------------------------------------------------------------- 数据类
@dataclass
class Cluster:
    """一组结构同构的小句（结构簇）。"""

    key: tuple[str, ...]
    members: list[Clause]
    freq: int = 0
    para_spread: int = 0
    run: int = 0
    mean_gap: float = 0.0
    gap_cv: float = 0.0
    variation: float = 0.0
    position_stdev: float = 0.0
    evidence: list[str] = field(default_factory=list)
    suspect: bool = False

    @property
    def informative(self) -> bool:
        """簇是否携带结构信息：除标点外至少 2 个功能类/内容槽。"""
        return sum(1 for s in self.key if s != "P") >= 2

    @property
    def signature(self) -> str:
        return " ".join(self.key)

    def as_dict(self) -> dict:
        return {
            "signature": self.signature,
            "freq": self.freq,
            "para_spread": self.para_spread,
            "run": self.run,
            "mean_gap": round(self.mean_gap, 2),
            "gap_cv": round(self.gap_cv, 3),
            "variation": round(self.variation, 3),
            "informative": self.informative,
            "position_stdev": round(self.position_stdev, 3),
            "suspect": self.suspect,
            "evidence": list(self.evidence),
            "clause_ids": [c.id for c in self.members],
            "examples": [c.text for c in self.members[:3]],
        }


@dataclass
class FingerprintReport:
    clause_count: int
    distinct_patterns: int
    pattern_entropy: float
    reuse_rate: float
    top_patterns: list[dict]
    clusters: list[Cluster]
    suspects: list[Cluster]
    mean_pairwise_similarity: float
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "clause_count": self.clause_count,
            "distinct_patterns": self.distinct_patterns,
            "pattern_entropy": round(self.pattern_entropy, 3),
            "reuse_rate": round(self.reuse_rate, 3),
            "mean_pairwise_similarity": round(self.mean_pairwise_similarity, 3),
            "top_patterns": self.top_patterns,
            "clusters": [c.as_dict() for c in self.clusters],
            "suspects": [c.as_dict() for c in self.suspects],
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------- 簇分析
class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _gap_stats(positions: list[int]) -> tuple[float, float, int]:
    """间距均值 / 变异系数 / 最长连续出现段。"""
    if len(positions) < 2:
        return 0.0, 0.0, len(positions)
    gaps = [b - a for a, b in zip(positions, positions[1:])]
    mean = statistics.fmean(gaps)
    stdev = statistics.pstdev(gaps) if len(gaps) > 1 else 0.0
    cv = (stdev / mean) if mean else 0.0
    run = best = 1
    for g in gaps:
        run = run + 1 if g == 1 else 1
        best = max(best, run)
    return mean, cv, best


def _position_index(doc: Document) -> dict[int, tuple[int, int]]:
    """小句 id → (段内序号, 该段小句数)，一次 O(n) 建表，避免逐簇 O(n²) 查找。"""
    by_para: dict[int, list[int]] = defaultdict(list)
    for c in doc.clauses:
        by_para[c.para_id].append(c.id)
    out: dict[int, tuple[int, int]] = {}
    for ids in by_para.values():
        for pos, cid in enumerate(ids):
            out[cid] = (pos, len(ids))
    return out


def _position_ratios(clauses: list[Clause],
                     index: dict[int, tuple[int, int]]) -> list[float]:
    """小句在所属段落中的相对位置（0 = 段首，1 = 段尾）。"""
    ratios = []
    for c in clauses:
        pos, total = index.get(c.id, (0, 1))
        ratios.append(pos / (total - 1) if total > 1 else 0.0)
    return ratios


def _variation(clauses: list[Clause]) -> float:
    """簇内两两加权距离的标准差：越小越像「换词填空」。"""
    pats = [skeleton_key(c) for c in clauses]
    if len(pats) < 2:
        return 0.0
    dists = [
        weighted_edit_distance(pats[i], pats[j])
        for i in range(len(pats))
        for j in range(i + 1, len(pats))
    ]
    return statistics.pstdev(dists) if len(dists) > 1 else 0.0


def _j3_marker(clauses: list[Clause]) -> str | None:
    for c in clauses:
        for m in RHETORIC_MARKERS:
            if m in c.text:
                return m
    return None


def _canonical_pattern(key: Sequence[str]) -> list[str]:
    """把骨架串压成「槽位模板」：连续内容槽折成一个 ``*``，丢掉标点与 ASP/DE。

    两条串只有在模板完全相同时才允许并簇。这样既允许词汇与体标记的差异
    （他推开了门 / 她关上窗户），又不允许把零主语、否定、把字句等结构级差异吞掉，
    也能区分「V+处所」与「V+把+宾」这类不同框架。
    """
    out: list[str] = []
    in_slot = False
    for sym in key:
        if sym == "P" or sym in OPTIONAL_ANCHORS:
            continue
        if _is_content_symbol(sym):
            if not in_slot:
                out.append("*")
                in_slot = True
        else:
            out.append(sym)
            in_slot = False
    return out


#: 无锚点模板（全是内容槽）时，用来区分「谓词开头」与「名词短语开头」
_SLOT_FAMILY = {
    "V": "pred", "A": "pred", "N": "np", "LOC": "np", "PRON": "np",
    "NAME": "np", "TIME": "np", "QUANT": "np", "CL": "np", "NUM": "np",
    "IDIOM": "np", "M": "np",
}


def _first_family(key: Sequence[str]) -> str:
    for sym in key:
        if sym == "P":
            continue
        return _SLOT_FAMILY.get(sym, sym)
    return ""


def _slot_class(sym: str) -> str:
    """逐位比较用：功能锚点按符号本身，内容槽按短语类型。"""
    if sym == "P" or _is_content_symbol(sym):
        return "P" if sym == "P" else _SLOT_FAMILY.get(sym, "other")
    return sym


def _anchor_compatible(a: Sequence[str], b: Sequence[str]) -> bool:
    """槽位模板必须完全一致；纯内容槽模板还要看槽数与起首成分类别。

    否则「V+处所」和「名词短语+形容词」都会被压成 ``*``，两个毫不相干的句子
    会被算成同一模板（实测会污染复用率）。
    """
    ca, cb = _canonical_pattern(a), _canonical_pattern(b)
    if ca != cb:
        return False
    if ca == ["*"]:
        # 无锚点模板（全是内容槽）信息量最低：必须逐位同类才算同构，
        # 否则「温两碗酒」「多是短衣帮」这类无关小句会被并进同一簇（实测孔乙己误报 38 条）。
        if len(a) != len(b):
            return False
        return all(_slot_class(x) == _slot_class(y) for x, y in zip(a, b))
    return True


class FingerprintEngine:
    """把小句集合变成结构簇与复用指标。"""

    def __init__(self, *, sim_threshold: float = CLUSTER_SIM_THRESHOLD):
        self.sim_threshold = sim_threshold

    # ---- 分簇
    def clusters(self, doc: Document) -> list[Cluster]:
        """代表元式分簇：先把精确同骨架分组，再按相似度归到「代表骨架」。

        不用并查集全量合并，是因为单链合并会把「A≈B、B≈C」串成一个大簇
        （实测 107 字短文就能被并成 1 簇、复用率虚高到 79%）。代表元式只做星形归并，
        并要求两边的功能锚点序列存在子序列关系，防止把不同句式混进同一模板。
        """
        clauses = [c for c in doc.clauses if c.token_count >= 2]
        if not clauses:
            return []
        pats = [skeleton_key(c) for c in clauses]

        exact: dict[tuple[str, ...], list[int]] = defaultdict(list)
        for i, p in enumerate(pats):
            exact[p].append(i)
        groups = sorted(exact.items(), key=lambda kv: (-len(kv[1]), -len(kv[0])))

        reps: list[Cluster] = []
        for key, idxs in groups:
            target: Cluster | None = None
            best = -1.0
            for rep in reps:
                if abs(len(rep.key) - len(key)) > 1:
                    continue
                if not _anchor_compatible(rep.key, key):
                    continue
                sim = similarity(rep.key, key)
                if sim >= self.sim_threshold and sim > best:
                    best, target = sim, rep
            if target is not None:
                target.members.extend(clauses[i] for i in idxs)
            else:
                reps.append(Cluster(key=key, members=[clauses[i] for i in idxs]))

        pos_index = _position_index(doc)
        out: list[Cluster] = []
        for cl in reps:
            cl.members.sort(key=lambda c: c.id)
            cl.freq = len(cl.members)
            cl.para_spread = len({c.para_id for c in cl.members})
            cl.mean_gap, cl.gap_cv, cl.run = _gap_stats([c.id for c in cl.members])
            # 变异是簇内两两编辑距离，O(k²)：成员多时等距抽样估计（见 VARIATION_SAMPLE）
            var_members = cl.members
            if len(var_members) > VARIATION_SAMPLE:
                step = len(var_members) // VARIATION_SAMPLE + 1
                var_members = var_members[::step]
            cl.variation = _variation(var_members)
            ratios = _position_ratios(cl.members, pos_index)
            cl.position_stdev = statistics.pstdev(ratios) if len(ratios) > 1 else 0.0
            self._judge(cl, len(clauses))
            out.append(cl)
        out.sort(key=lambda c: (-c.freq, c.key))
        return out

    # ---- 判据
    def _judge(self, cl: Cluster, total_clauses: int = 0) -> None:
        ev: list[str] = []
        rate = (cl.freq / total_clauses) if total_clauses else 1.0
        if (cl.freq >= SUSPECT_MIN_FREQ and cl.para_spread >= SUSPECT_MIN_PARA_SPREAD
                and cl.gap_cv < SUSPECT_MAX_GAP_CV and rate >= SUSPECT_MIN_RATE):
            cl.suspect = True
        if cl.freq >= 3:
            if cl.position_stdev <= J1_POSITION_STDEV:
                ev.append(f"J1 位置高度固定（位置标准差 {cl.position_stdev:.2f}）→ 倾向修辞性重复")
            else:
                ev.append(f"J1 位置随机（位置标准差 {cl.position_stdev:.2f}）→ 倾向模板填充")
            if cl.variation <= J2_VARIATION_STDEV:
                ev.append(f"J2 簇内变异极小（{cl.variation:.2f}），近似换内容词 → 模板嫌疑")
            else:
                ev.append(f"J2 簇内变异较大（{cl.variation:.2f}）→ 可能是同一节奏的反复")
        marker = _j3_marker(cl.members)
        if marker:
            ev.append(f"J3 出现显式修辞标记「{marker}」→ 倾向修辞性重复")
            if cl.variation <= J2_VARIATION_STDEV:
                cl.suspect = False
        if cl.suspect:
            ev.append(
                f"命中机械复用嫌疑：freq={cl.freq} ≥ {SUSPECT_MIN_FREQ}，"
                f"占全文 {rate:.1%} ≥ {SUSPECT_MIN_RATE:.0%}，"
                f"跨段 {cl.para_spread} ≥ {SUSPECT_MIN_PARA_SPREAD}，"
                f"间距变异 {cl.gap_cv:.2f} < {SUSPECT_MAX_GAP_CV}"
            )
        cl.evidence = ev

    # ---- 报告
    def analyze(self, doc: Document) -> FingerprintReport:
        clauses = [c for c in doc.clauses if c.token_count >= 2]
        if not clauses:
            return FingerprintReport(0, 0, 0.0, 0.0, [], [], [], 0.0, ["文本中没有可分析的小句"])
        cl = self.clusters(doc)
        counter: Counter = Counter(skeleton_key(c) for c in clauses)
        total = len(clauses)
        entropy = -sum((n / total) * math.log2(n / total) for n in counter.values() if n)
        repeated = sum(c.freq for c in cl if c.freq >= 2)
        # 两两相似度是 O(n²)：先在候选集上限内抽样，再计算（不能先算全量再抽样）
        sample = clauses
        pair_note = ""
        if len(clauses) > PAIR_SAMPLE_CLAUSES:
            step = len(clauses) // PAIR_SAMPLE_CLAUSES + 1
            sample = clauses[::step]
            pair_note = ("两两相似度按 %d/%d 小句等距抽样估计（O(n²)，上限 %d 句）"
                         % (len(sample), len(clauses), PAIR_SAMPLE_CLAUSES))
        keys = [skeleton_key(c) for c in sample]
        sims = [similarity(keys[i], keys[j])
                for i in range(len(keys)) for j in range(i + 1, len(keys))]
        top = [
            {"signature": " ".join(p), "count": n, "share": round(n / total, 3)}
            for p, n in counter.most_common(10)
        ]
        notes = []
        if pair_note:
            notes.append(pair_note)
        if any(c.freq > VARIATION_SAMPLE for c in cl):
            notes.append("簇内变异按每簇 ≤%d 成员等距抽样估计（两两编辑距离 O(k²)）" % VARIATION_SAMPLE)
        if not doc.has_dependency:
            notes.append("当前后端无依存句法（jieba），L2/L3 不可用；骨架与簇结果按 clause.confidence 折算置信度")
        return FingerprintReport(
            clause_count=total,
            distinct_patterns=len(counter),
            pattern_entropy=entropy,
            reuse_rate=repeated / total if total else 0.0,
            top_patterns=top,
            clusters=cl,
            suspects=[c for c in cl if c.suspect],
            mean_pairwise_similarity=statistics.fmean(sims) if sims else 0.0,
            notes=notes,
        )


# ---------------------------------------------------------------- 体裁基线
def _parse_pattern_row(row: object) -> tuple[tuple, int]:
    """一行 {"signature": ".. ..", "count": n} → (骨架元组, 计数)。"""
    if not isinstance(row, dict):
        return (), 0
    sig = str(row.get("signature") or "").split()
    try:
        count = int(row.get("count") or 0)
    except (TypeError, ValueError):
        count = 0
    return tuple(sig), max(0, count)


@dataclass
class Baseline:
    """某个体裁的人类参考分布（§7.1）。

    `patterns` 是骨架模式的多重集；`tau` 是内部最近邻距离的 95 分位，体裁自适应。
    """

    genre: str
    patterns: Counter
    tau: float
    n_clauses: int
    source: str = ""
    version: str = "v0-uncalibrated"

    @classmethod
    def from_dict(cls, data: dict) -> "Baseline":
        """从 `as_dict` / `baseline build` 写出的 JSON 还原（patterns 是骨架多重集）。

        `as_dict` 里只有 `top_patterns`（截断到 20 条），完整 `patterns` 由 `baseline build`
        额外写出；两者都读不到时退回 `top_patterns`，并保持 tau 不变。
        """
        if not isinstance(data, dict):
            raise ValueError("基线 JSON 必须是对象")
        raw = data.get("patterns")
        patterns: Counter = Counter()
        if isinstance(raw, list):
            for row in raw:
                sig, count = _parse_pattern_row(row)
                if sig:
                    patterns[sig] += count
        if not patterns:
            for row in data.get("top_patterns") or []:
                sig, count = _parse_pattern_row(row)
                if sig:
                    patterns[sig] += count
        return cls(genre=str(data.get("genre") or ""), patterns=patterns,
                   tau=float(data.get("tau") or 0.0),
                   n_clauses=int(data.get("n_clauses") or 0),
                   source=str(data.get("source") or ""),
                   version=str(data.get("version") or "v0-uncalibrated"))

    def as_dict(self) -> dict:
        return {
            "genre": self.genre,
            "n_clauses": self.n_clauses,
            "distinct_patterns": len(self.patterns),
            "tau": round(self.tau, 3),
            "source": self.source,
            "version": self.version,
            "top_patterns": [
                {"signature": " ".join(p), "count": n}
                for p, n in self.patterns.most_common(20)
            ],
        }

    def distance_to_baseline(self, pattern: Sequence[str]) -> float:
        """到基线最近邻的结构距离（用距离而非核，便于解释）。"""
        best = float("inf")
        for p in self.patterns:
            if abs(len(p) - len(pattern)) > 3:
                continue
            d = weighted_edit_distance(pattern, p)
            if d < best:
                best = d
                if best == 0.0:
                    break
        return 0.0 if best == float("inf") else best

    def coverage(self, doc: Document) -> dict:
        pats = [skeleton_key(c) for c in doc.clauses if c.token_count >= 2]
        if not pats:
            return {"coverage": 0.0, "novelty": 0.0, "n": 0, "tau": self.tau, "genre": self.genre}
        ds = [self.distance_to_baseline(p) for p in pats]
        covered = sum(1 for d in ds if d <= self.tau)
        return {
            "coverage": covered / len(pats),
            "novelty": 1.0 - covered / len(pats),
            "mean_distance": round(statistics.fmean(ds), 3),
            "n": len(pats),
            "tau": round(self.tau, 3),
            "genre": self.genre,
        }


def build_baseline(texts: Iterable[str], genre: str, *, source: str = "") -> Baseline:
    """从一批人类文本构造基线。"""
    from .text_processor import process

    counter: Counter = Counter()
    n = 0
    for text in texts:
        try:
            doc = process(text)
        except Exception:  # noqa: BLE001 - 坏样本跳过
            continue
        for c in doc.clauses:
            if c.token_count >= 2:
                counter[skeleton_key(c)] += 1
                n += 1
    if not counter:
        from .errors import AnalysisError

        raise AnalysisError(
            "基线文本为空，或没有长度 ≥2 的小句",
            hint="给至少一篇 500 字以上的同体裁人类文本；短样本无法形成分布",
        )
    tau = _compute_tau(counter)
    return Baseline(genre=genre, patterns=counter, tau=tau, n_clauses=n, source=source)


def _compute_tau(counter: Counter, sample: int = 2000) -> float:
    """95 分位阈值：对每个模式取到其他模式的最近邻距离。"""
    pats = list(counter)
    if len(pats) < 2:
        return 1.0
    if len(pats) > sample:
        step = max(1, len(pats) // sample)
        pats = pats[::step]
    ds = []
    for i, p in enumerate(pats):
        best = float("inf")
        for j, q in enumerate(pats):
            if i == j or abs(len(p) - len(q)) > 3:
                continue
            d = weighted_edit_distance(p, q)
            if d < best:
                best = d
        if best != float("inf"):
            ds.append(best)
    if not ds:
        return 1.0
    ds.sort()
    k = min(len(ds) - 1, int(round(0.95 * (len(ds) - 1))))
    return float(ds[k])


def cross_work_stats(docs: dict[str, Document]) -> dict:
    """跨作品同构统计（§5.2）：同一骨架出现在多少部作品中。"""
    by_pattern: dict[tuple[str, ...], set[str]] = defaultdict(set)
    counts: Counter = Counter()
    for name, doc in docs.items():
        for c in doc.clauses:
            if c.token_count >= 2:
                p = skeleton_key(c)
                by_pattern[p].add(name)
                counts[p] += 1
    shared = [
        {
            "signature": " ".join(p),
            "works": len(works),
            "work_ratio": round(len(works) / max(1, len(docs)), 3),
            "occurrences": counts[p],
        }
        for p, works in by_pattern.items()
        if len(works) >= 2
    ]
    shared.sort(key=lambda d: (-d["work_ratio"], -d["occurrences"]))
    return {
        "n_works": len(docs),
        "n_patterns": len(by_pattern),
        "shared_patterns": len(shared),
        "top_shared": shared[:10],
    }
