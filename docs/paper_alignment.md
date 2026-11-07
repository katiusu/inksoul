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
3. ~~**中文 Biber 清单**~~ → **已实现 2026-11-07**：`src/inksoul/markers.py` 八族（名词化/轻动词、定语链、并列堆叠、
   受事被动、论述型连接词、评价性抽象、比喻模板、四字格），只统计叙述句、按每千字密度对照人类网文分位数；
   基线由 `scripts/calibrate_markers.py` 在 542 个 3000 字块上标定（见 §7）。
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

## 7. AI 味标记族（2026-11-07）

Reinhart 2025 的结论是「差异在特征组合」且必须按体裁分层，所以这里不做总分、不做分类器，
只把句式层面的「AI 常驻特征」做成可数、可定位的密度，再放到**人类网文的分布**上看位置。

- 实现 `src/inksoul/markers.py`：八族标记（`NOM`/`ATTR`/`PARALLEL`/`PASSIVE`/`CONNECTIVE`/`ABSTRACT`/`SIMILE`/`IDIOM`），
  零第三方依赖；含引号（`“”「」『』`）的句子算对话，**只统计叙述句**，对话与叙述分开计数。
- 基线 `src/inksoul/data/marker_baseline_zh.json`：人类网文 542 个 3000 字块（步长 1500，剔除叙述 <800 字的块），
  取 p50/p90/p99。叙述字数 <400 时不判定（一条「被」就能把每千字推到 p99，短样本没有统计意义）。
- 判定口径：任一族 > 人类 p99，或 ≥2 族 > p90 → `VERDICT: FAIL`；否则 PASS。**给的是分布位置，不是 AI 概率。**
- 接入：`inksoul_analyze` 的 `markers` 字段、reviewer 的「AI 味标记」条目、`inksoul markers` 子命令、
  以及 `inksoul_gate --preset markers`（纯 Python，不依赖宿主 `/root/deslop`）。
- 分位数（每千字，p50/p90/p99）：NOM 0.00/0.88/1.86；ATTR 0.91/2.02/3.42；PARALLEL 0.00/0.41/0.96；
  PASSIVE 1.69/3.47/5.74；CONNECTIVE 0.41/1.04/2.10；ABSTRACT 0.39/1.03/2.07；SIMILE 0.00/0.47/0.88；
  IDIOM 4.05/6.44/8.92。
- 已知限制：jieba 的 `l`（习用语）会把「捕捉到/脑海中」算成四字格，故 `IDIOM` 只认 `i` 且长度 ≥4；
  该族仍混入部分常见搭配，只作提示，不单独触发 FAIL。

## 8. v0.4.1：短样本判定与「先定位再改写」（2026-11-07）

### 8.1 短稿不再只能 SKIP：泊松尾部检验

3000 字块的 p50/p90/p99 直接套到 400 字草稿上会把方差放大 7 倍：一条「被」= 2.5/千字，
已经越过 p90(3.47) 的一半，一条就能把短稿判成异常或被迫 SKIP。
处理分三段（src/inksoul/markers.py）：

| 叙述字数 | 判定方式 |
|---|---|
| < 400（MIN_NARRATIVE_CHARS） | 不判定，闸门给 VERDICT: SKIP（没有回执比假 PASS 诚实） |
| 400–1200（SHORT_WINDOW_CHARS） | 以 p99 密度为均值的泊松尾部检验 P(X≥observed)，count≥3 且 p<0.01 判 VHIGH、p<0.05 判 HIGH |
| ≥ 1200 | 原分位数规则（>p99 或 ≥2 族 >p90 判 FAIL） |

实测（600 字叙述，PASSIVE p99=5.74/千字，lam≈3.44）：1 条 P(X≥1)=0.97、4 条 0.45、6 条 0.14 全判 ok；
8 条 0.025 判 HIGH，10 条 0.003 判 VHIGH→FAIL。少量出现不再冤枉，堆砌仍然拦得住。

### 8.2 修订链路接通：span 定位与标记族锚点

原实现两处断裂，导致 long/publish 档的修订轮实际空转：

1. reviewer 的标记族问题句写的是指标字符串（NOM 13.27/千字（人类 p90 0.88…）），
   正文里根本不存在，revise() 的 str.find 必然失配 → 永远跳过。
   现在改成正文里真实存在的小句（每族最多 3 条去重样本），指标留在 evidence。
2. revise() 只做精确匹配，标点/空白规范化过的句子就找不到。
   新增 _locate()：精确匹配 → 归一化（只留字母数字汉字）+ difflib 最长匹配 → 索引映射回原文，
   返回 (start, end)；不足 6 字或相似度 <60% 直接返回 None，不猜、不模糊替换。
   替换时若新句自带句末标点，会吸收原标点，避免出现「。。」。

停止原因也按事实分档：没有 severity≥0.6 的问题时记「无可修订项」，有阻断但落不下时记
「有 N 条阻断级问题但修订未落地（定位失败 x/改写不合格 y）」，不再统一糊成「无可用修订」。

实测（stiff 夹具，叙述 591 字）：定位 3/3 成功，NOM 24→19 条，密度 40.61→32.53/千字；
端到端 long 档 3 候选 + 修订轮跑通，闸门 PASS 回执正常。

参考：Du et al. 2022（ITERATER，编辑意图/保留跨度）、Kim et al. 2022（Learning Where to Edit，
定位与改写解耦）、LaSEr-Edit 2024（span 局部编辑 + 约束校验）。

## 9. v0.4.2：多轮收敛循环（2026-11-07）

v0.4.1 之前，改进阶段是「单轮 + 一掉分就回滚」，19 条标记族问题永远收敛不了。
现在改成真正的收敛循环（src/inksoul/agent.py）：

- 终止条件：内置闸门 PASS 且无阻断问题 / 预算 REVISION_BUDGET_SEC=240s 用完 / 轮次上限（--rounds，默认 3）/ 连续 2 轮排名无改善。
- 闸门策略：内置闸门（__inksoul__: 前缀，纯 Python）每轮都跑，外部闸门（40s 级）仍只在定稿跑。
- 路由：闸门阻断→整篇 restyle；有 severity≥0.6→逐句 revise；只剩 0.3~0.6（如标记族 high）→同样逐句 revise（min_severity=0.3），不再动辄整篇重写。
- 允许一次「变差」：连续两轮排名不变差才判定为停滞回滚，避免把一族的减少误判成整体变差。
- 定稿后重跑分析（rec2 原地替换 history），报告里的字数/阻断/问题数对应最终正文，而不是回滚前那一版。
- restyle 长度护栏：原稿 ≥500 字时，重写稿掉到 70% 以下判为丢内容，保留原稿并记 notes。

实测（long 档，1200 字目标，候选 2，--rounds 4，--gate markers）：
候选#1 1515 字（阻断 12）→ 修订#1 1405 字（6）→ 修订#2 1410 字（6）→ 定稿 1072 字、阻断 0、问题 3、
VERDICT: PASS，停止原因「定稿过闸门 PASS（2 次）」。

观察：逐句修订能压阻断数，但长文里 LLM 改写常引入新的标记族命中（MTLD 从 216 掉到 ~95），
所以真正的收敛往往发生在定稿闸门的那一次整篇重写；这也是把 restyle 放在闸门失败路径上的理由。

## 10. v0.4.3：P0 三件套（2026-11-07）

对应 docs/development_plan.md 的 P0（D1 局部复检 / D2 restyle 三保真 / D3 单一判定源）。

**D3 单一判定源（src/inksoul/markers.py）**
新增 `verdict_of(rows) -> (verdict, failing)`：任一标记族 > p99，或 ≥2 族 > p90 判 FAIL；
叙述不足判 SKIP；否则 PASS。`gate_text` 与 `reviewer.review` 都走它——reviewer 只给
`failing` 里的族发 severity=0.6 的阻断项，其余 high 记 0.35。于是「闸门 PASS」与
「标记类阻断为 0」同真同假，不再出现「PASS 且 9 条阻断」的解读冲突（阻断来自依存/
多样性/叙事时，闸门输出新增「覆盖范围」一行说明它不在闸门内）。agent 轮记录会写
「闸门 PASS 仅覆盖标记族，另有 N 条阻断」。

**D1 修订局部复检（src/inksoul/generation.py）**
`revise(..., recheck=True)`：每替换一句，比较该句 ±200 字窗口的标记总数（`markers.count_tags`，
轻量、不分词、IDIOM 恒 0）。新句把窗口标记抬高超过容差（before+1 且 ≥2）就重采样一次
（温度 0.8，指令明说不要被动/名词化/四字格堆叠）；仍不改善就放弃这句并计入「改写不合格」。
依据：LaSEr-Edit「局部编辑 + 约束校验」——改写后必须复检，而不是整篇重跑。

**D2 restyle 三保真（src/inksoul/generation.py `_fidelity_checks`）**
除原有 70% 字数下限外追加：字数 85–115%、字符 3-gram 余弦 ≥0.60、句长 CV 与 MTLD 变化 ≤15%。
违反任一条就保留原稿并在 notes 写清越界项。依据：Sourati 等 2026——AI 润色把方差压低
21–50%，而语义余弦仍有 87% 样本 >0.95，「像原文」不足以证明没被改薄。

实测（stiff 夹具 1020 字，84 个叙述标记；deepseek-chat）：
单轮 84→64（-23.8%），3 轮闭环 84→24（-71.4%），新引入标记 2 个（2/27 ≈ 7%），改写不合格 0 处。
restyle 三保真在 3 段人类文本上的采纳率 2/3：一段 93% 字数 + 余弦 0.62 通过；一段被字数 85% 卡住
（模型删了 15%）；一段 101% 字数 + 余弦 0.80 通过。一次整篇 restyle 约 17-25s。

验收（`tests/test_p0_guards.py` 12 个用例；全量 222 tests OK）：
- verdict 三档与 insufficient 分支一致；reviewer 给 FAIL 族的 severity 恒 ≥0.6。
- 修订：新句引入 2 个标记族 → 重采样仍超标 → 应用 0 处、notes 记「改写不合格」。
- restyle：字数塌缩、语义漂移都被拦下；同长度改写（CV 不变）正常采纳。
