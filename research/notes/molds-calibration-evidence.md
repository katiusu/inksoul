# 模具判据校准：本地文献证据与实测映射

日期：2026-11-14 · 结论指向 0.6.1 `molds` 的三处结构性问题（判定单位、判据形态、下限项）

## 0. 一句话结论

本地 14 篇 PDF 里**没有**任何一篇直接研究「中文小说 900 字段级密度门控」，但有 5 篇（+项目自己的文献综述）在**方法学层面**逐条对上 0.6.1 的三个错误；把它们的做法移植过来的原型在 1288 个人类段上把假失败率从 **81.9% 压到 6.2%**，同时 AI 稿件的判据仍全部命中。

## 1. 证据 → 改进映射

| # | 0.6.1 的错误 | 支撑文献 | 原文 | 移植做法 |
|---|---|---|---|---|
| 1 | 基线是**整本级**（16 本书各算一个密度值取 mean/p10/p90），却判 **900 字段** | **Liu 2024**（中文文本复杂度，L1）<br>**Kendro 2026**（词汇多样性） | Liu：「RTTR was reported to be sensitive to text length … MATTR and MTLD were involved for their independence of text length」（Zenker & Kyle 2021）；「comparisons would not be rigorous due to differences in genres, themes and text lengths」<br>Kendro：「lexical diversity … depends on text-internal (e.g., text length) … variables」；「the remaining four measures, which do not vary by text length (cf. Bestgen, 2024)」 | 参考分布必须与判定单位**同长度、同体裁**。基线的采样单位 = 判定单位 = 900–1000 字窗；禁用「整本 → 段」的跨单位阈值。Length-sensitive 的项（词长、句长）要么换成不随长度变的指标，要么单列。 |
| 2 | **21–22 项同时判，任一项越线即 FAIL** | **Herbold 2023**（Sci Rep，42 项检验）<br>**Sourati 2026**（Bonferroni/BH） | Herbold：「42 tests. We use the Holm-Bonferroni method … to achieve a family-wise error rate of 0.05」；「it is likely that all—even tiny—correlations are significant given our amount of data. Consequently, our interpretation of these results focuses on the strength of the correlations.」<br>Sourati：「To control for multiple comparisons, we applied Bonferroni corrections」；「with Dunn's test and Benjamini-Hochberg adjustments」 | ① 单项 p90 换成**族错误率受控**的形式：要么 p99（≈0.05/21），要么改成**复合分**（各项单侧 z 的均值）只在分布尾部截断；② 主要判据改为**效应量**（超均值几倍 / Cohen's d），而不是「有没有越线」；③ 报告里必须给出**假失败率**（人类对照组的 FAIL 比例）。 |
| 3 | **5 项「下限」**（EXCL/ELLIP/QUES/REDUP/QUOTE）按网文语料标定，缺一项即判 UNDER 并进改写指令 | **Li & Zhang 2025**（中文社交媒体检测）<br>**Reinhart 2025**（PNAS）<br>项目文献综述 §2.3 | Li & Zhang：「feature set tailored to Chinese social media」；「detection models exhibit performance limitations when applied to short texts (Mireshghallah et al., 2024)」<br>Reinhart：「…do not align with genre conventions familiar to human audiences」<br>综述:82 转载 Rallapalli：「体裁是比 AI/人类更强的分组变量，参考分布必须按体裁建立」 | 下限项**不是**「人类必然存在」的硬约束，而是体裁惯例。要么按体裁分档建模，要么只做**诊断输出**（报数、不进 veto、不进改写指令）；QUOTE 的标点必须按本项目实际体例（「」）重标定。 |
| 4 | （附带）判据没有可解释的分布证据，全是硬编码阈值 | **O'Sullivan 2025**（文体计量）<br>Herbold 2023 | O'Sullivan：z-score「standardise the data to account for differences in text length」；「Occasional overlaps occur … between GPT-3.5 and human texts」<br>Herbold：全文以 Cohen's d 报效应量 | 每条模具输出必须带：人类分布（mean/p10/p90）、当前 z、以及**该阈值在人类上的失败率**。单个文本落在人类分布内不等于「像人」（人类之间也重叠），所以判据只能做**分布距离**，不能做「过/不过」。 |

## 2. 校准实验（可复现）

脚本 `/tmp/calib.py`；语料：`experiment/corpus/human/*.txt` 16 本，滑窗 1000 字、han≥600；共 **1288 段**，21 项判据（16 over + 5 under）。

设计：**留一本人交叉验证**（在一本书上判、用其余 15 本拟合基线），避免「自己判自己」。

| 判据 | 留出人类段的 FAIL 率 |
|---|---|
| A) 逐项 p90/p10，任一项越线即 FAIL（= 0.6.1 思路，只是把基线换成段级） | **81.9%** |
| B) 复合分 = 21 项单侧 z 的均值，> 训练集 p95 | **6.2%** |

关键点：**A 换成段级基线也救不了**——21 项各自 10% 的尾概率，任意一项越线的期望就是 1−0.9²¹ ≈ 89%。所以问题不只是「基线单位错」，而是「多项同时硬 veto」这个形态本身在统计上不可用。B 是把 21 项压成一个统计量，族错误率随单项数增长的速度从乘法降回加法。

同一脚本给 AI 稿打分（`/tmp/q6b`，5 组 × 3 臂，人类 p95 cutoff = 0.67）：

| 组 | C（裸生成） | P（具体条件） | D（统计指标目标表） |
|---|---|---|---|
| g0 | 2.24 | 2.93 | 2.01 |
| g1 | 1.55 | 1.78 | 1.21 |
| g2 | 2.90 | 1.38 | 1.85 |
| g3 | 2.47 | 1.70 | 1.91 |
| g4 | 2.03 | 2.81 | 2.12 |

10/10 全部越线 → 判据有区分力（对人类 6.2%，对 AI 100%）；但注意 **D 臂（按 0.6.1 的目标表去凑）系统性低于 C 臂**，说明「往人类 p10–p90 区间里收」确实把文本推平——这与 0.6.1 的 molds 均值 C=10.8 / D=9.4 同向，是**指标与主观质量反相关**的第二个独立证据。

## 3. 落到代码的具体改法

1. `molds_baseline.json` 重建：以 **900–1000 字窗**为采样单位，逐段算密度 → 存 mean/sd/p10/p90/p95/p99；每本各存一份（用于留一验证），并保留 `n_segments`。
2. `cmd_molds` 判定逻辑：`composite = mean(max(0, z) for over 项) 与 mean(max(0, -z) for under 项) 的合并均值`；VERDICT 由 composite 分位决定（默认 p95），单项只在报告里列「诊断」。若坚持单项 veto，阈值必须 ≥ p99 且要求 ≥2 项同时越线。
3. 下限项：不进 VERDICT、不进改写指令，只报「本段未出现：破折号/省略号/问号/叠词/引号对白」。
4. 报告加三列：人类同期失败率、当前 z、该维度的人类 mean±sd，让调用方能自己判断。
5. 提示词侧（cordis.patch.yml 规则 20）不要再写「不是 PASS 就改」；改成「composite 超 p95 时，按报告里 z 最高的 2 项定向改，最多 2 轮」。

## 4. 这些证据**不能**支持的

- 没有一篇给出中文小说段级的**模具密度参考值**；本项目的基线只能自建。
- Reinhart 是 500 词英文片段、Herbold 是德语学生作文、Li & Zhang 是微博短评——三者的**绝对数值不可迁移**，只可迁移**方法**（同单位、族错误率、效应量、体裁条件化）。
- 复合分能否对应读者感知，本地无实验；q6b 只能证明它与「凑指标会变平」同向，不能证明它度量质量。

## 5. 落地结果（0.6.2-rc1）

- `src/inksoul/molds.py`：段级基线（1902 段 1000 字窗）、19 项判据、z 截尾 ±3、复合分阈值 0.631。
- 实测：人类段 5.0%（同分布）/ 6.2%（留一本人）；q6b 15 份 AI 稿件 15/15 越线。
- 下限项（EXCL/ELLIP/QUES/REDUP/QUOTE）只输出「本段未出现」，不进 VERDICT、不进改写指令。
- 单窗仍可能误报（番外数字密集段落 NUM z 顶到阈值）：报告同时给窗级通过率，不要只看总 VERDICT。
