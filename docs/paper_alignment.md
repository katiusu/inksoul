# 论文 → 项目比对与改进记录（2026-11-06）

> 依据：`research/notes/intensive-reading-2026-11-06.md` 六篇精读。本文只记录**改了哪些代码、为什么改、实测数字**，
> 以及**读了但决定不改**的项（附理由）。

## 1. 比对表

| 论文结论 | InkSoul v0.1.0 现状 | 差距 | 处理 |
|---|---|---|---|
| 人类句长更散，模型挤在中等长度（Muñoz-Ortiz） | `diversity` 有句长分箱与 `style` 有 mean/std，但**没有归一化离散度** | 无法跨文本/跨长度比较 | **已改**：`length_dispersion`（cv / bin_entropy_norm / mid_share） |
| 依存弧长、左右弧、依存类型差异比句长更稳（Muñoz-Ortiz） | L2 只有边集加权编辑距离，`has_dependency` 能力位闲置 | 缺整个依存统计层 | **已改**：新增 `dependency.py`（弧长分箱/左右弧/依存关系/树深） |
| 个体 novelty 升、集体多样性降（Doshi） | `cross_work_stats` 只数「哪些骨架跨作品出现」 | 没有两两相似度与聚合量 | **已改**：新增 `corpus.py` + CLI `corpus` |
| 方差压缩 / 集体窄化（Sourati 2026） | 同上 | 同上 | 同上（同一测量面） |
| 必须按体裁分层（Reinhart） | `Baseline` 已带 genre，但阈值仍全局 | 缺 per-genre 阈值文件 | 未改：已有 Baseline 承载，阈值标定是独立任务 |
| 特征组合 > 单特征加总（Reinhart） | ADR-2 已拒绝单一总分 | 方向一致 | 不改，写进文档作为外部支持 |
| 二元 rubric 评创作、LLM 当裁判不可靠（Chakrabarty） | reviewer 回传问题小句、无总分 | 缺「创作维度」条目 | 未改：TTCW 中文版是 v0.2 独立任务 |
| 具体性词典（Brysbaert） | 无抽象化指标 | 缺中文常模 | 未改：资源缺口 |
| AI 端要用真模型（Herbold） | 实验里「AI 端」是模板拼接 | 实验结论外推受限 | 未改代码，记入 limitations |

## 2. 已落地的改动

### 2.1 `src/inksoul/diversity.py` · 句长离散度
- 新增 `length_dispersion(lengths)`：`cv`（std/mean）、`bin_entropy`、`bin_entropy_norm`、
  `mid_share`（落在 10–29 字的比例，常量 `MID_LEN_LO/MID_LEN_HI`）。
- `DiversityReport` 增加字段并进入 `as_dict()`；notes 明确「mid_share 高本身不构成判定，
  该现象是英文新闻上的测量」。

### 2.2 `src/inksoul/dependency.py`（新）
- 输入 `Document`，要求 `has_dependency=True`，否则抛 `AnalysisError`（由 analyzer 降级为占位报告）。
- 输出：`left_arc_share`、`arc_len_mean/std`、`arc_len_bins`（1/2/3-4/5-7/8+）、
  `arc_len_by_sentence_bin`（1-10/11-20/21-30/31-40/41+，与原文对齐）、`deprel_shares`（top15）、
  `mean_tree_depth`。弧长按 **token** 计，不按字符。
- **Ω 未实现**（需要 D_min 与随机排列期望），notes 里写明缺口——不假装有。

### 2.3 `src/inksoul/corpus.py`（新）+ CLI `corpus`
- `analyze_corpus({作品名: 文本})`：每篇取骨架计数 → 余弦相似度 → 两两矩阵、
  `mean_pairwise_similarity`、`max_pair`/`min_pair`、每篇相对同侪的平均/最大相似度、
  复用 `fingerprint.cross_work_stats` 给共享骨架。
- `inksoul corpus <目录|文件...> [--json]`。

## 3. 实测（本项目自己的数据，可作为论文结论的中文复现）

`experiment/data/` 现成两组：`generated/`（模板拼接 6 篇，各约 1000 字）、`raw_sources/`（人类 8 篇）。

| 语料 | n | 两两平均相似度 | 最高对 |
|---|---|---|---|
| 模板拼接 `generated/` | 6 | **0.902** | 0.942（t_mock_01 ↔ t_mock_06） |
| 人类 `raw_sources/`（混合体裁） | 8 | **0.136** | 0.253 |
| 人类 · 小说同体裁 | 3 | 0.159 | 0.166 |
| 人类 · 散文同体裁 | 3 | 0.116 | 0.127 |
| 人类 · 对话体 | 2 | 0.210 | 0.210 |

**结论**：体裁匹配后人类仍 ≤0.21，模板拼接 0.90，**分离度 4–8 倍**，与 Doshi 的「集体同质化」方向一致。
**但**：模板文本同源同长、由同一脚本生成，这是上限估计；换成真模型输出后该值必然下降——所以
`NEAR_IDENTICAL_SIM=0.90` **不能当检测阈值**，只能当「这批文本彼此高度同构」的标记。

## 4. 测试

- `tests/test_paper_metrics.py` 新增 11 条：离散度（空/单值/散布 vs 集中/报告字段）、
  依存（无后端报错/弧长与左右弧/占位降级）、语料（同文近同构/矩阵界与排序/单篇拒绝/过短拒绝）。
- 全量：`PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -t .` → **Ran 176 tests OK**。

## 5. 待办（读出来了但还没做）

1. **Ω 最优性**：需要 LAL 或自实现 Gildea-Temperley；这是 Muñoz-Ortiz 里人类/模型差距最大的一维。
2. **阈值标定**：`cluster_sim_threshold=0.60`、`NEAR_DUP_SIM=0.85`、`NEAR_IDENTICAL_SIM=0.90`、
   `mid_share` 分段——全部仍是未标定默认值，需要 ≥200 对小句 + ≥50 篇机械感判定的人工标注。
3. **中文 Biber 清单**：定语链嵌套、动词名词化（「进行…的处理」）、介词框架、并列堆叠、被动标记。
4. **TTCW 中文版 14 条**：Chakrabarty 的 rubric 移植。
5. **真模型语料**：把 `gen_model_samples.py` 做出来，替换模板拼接，重跑 §3 表。

## 6. 第二批论文（01/03/05/07/08/09/13/14）带来的改动（2026-11-06）

### 6.1 新增 `src/inksoul/lexical.py` · 词汇多样性五指标
依据 Kendro 2026：单看 TTR 会把「长文本」误判成「词汇贫乏」，必须用长度稳健指标。
实现 `ttr` / `mtld`（前向+后向平均，阈值 0.72）/ `mattr`（窗口 50）/ `msttr`（段长 100）/
`hdd`（超几何 D，抽样固定 42）；`lexical_indices()` 汇总，词数 <50 时只报 TTR 并写 note。

HDD 的公式在 2026-11-07 审计后修正：旧实现是按 1..42 逐步累加「抽 i 个词出现新类型」的概率，
实际画的是长度曲线（同一文本 1x/2x/5x/10x → 0.979/0.934/0.801/0.618），与 McCarthy & Jarvis 定义不符；
现按「每个类型被抽中的概率求和 / 42」计算，同口径下 1x/2x/5x/10x → 0.375/0.373/0.371/0.371，长度稳健。

已并入 `DiversityReport.lexical`（`analyze` 的 diversity 段落里直接可见）。

### 6.2 新增 `src/inksoul/stylometry.py` · Burrows' Delta
依据 O'Sullivan 2025：高频**字**相对频率 → 跨文本 z 标准化 → 两两 |z 差| 均值。
输出距离矩阵、每篇同侪均值、最近邻、`spread`。CLI `corpus` 会同时打印。

**口径偏差（已披露）**：原文的 Burrows' Delta 建立在功能词频率上，本项目用去标点高频汉字
（`stylometry._chars`，单字单位），所以数值不能与原文直接比较，只用于本库内部横向比较。

### 6.3 实测

| 指标 | 模板拼接（6 篇） | 人类（8 篇） |
|---|---|---|
| MTLD | 16.0（t_mock_01） | 107–121 |
| MATTR（窗口 50） | 0.435 | 0.807–0.847 |
| MSTTR（段 100） | 0.290 | 0.735–0.764 |
| HDD | 0.496（t_mock_01） | 0.835–0.914 |

表内 MTLD / MATTR / MSTTR 为原口径数值；HDD 一行为 2026-11-07 修正后的重算值（同一批语料、过滤标点）。

**但**：模板是「模板×重复」，词型只有 33 种（人类 429–751 种），这是构造性差异而非模型差异；
真实模型输出会落在两者之间——Kendro 2026 甚至发现 AI 更高。所以这些数只能证明**指标有区分力**，
不能证明「AI 词汇多样性低」。

**Delta 使用教训（重要）**：
- 单独在模板组内算 → 平均 1.302；单独在人类组内算 → 1.197。数值方向与 O'Sullivan 相反，
  因为 z 标准化是在**本组内**做的：组内越同质，特征标准差越小，距离被放大。
- **Delta 只在同一个比较集里可比**。把 14 篇合在一起算：每篇的最近邻 14/14 都是同组，
  模板组组内 Delta 0.22–0.33、人类组 0.62–0.79——完全复现 O'Sullivan「AI 抱团、人类松散」。
- 结论写进 API 文档：**不要跨语料比较 Delta 绝对数值**。
