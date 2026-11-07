# 20 个选题的文献检索结果（2026-11-05）

> 检索方式：OpenAlex（检索/引用数/OA 状态）+ Crossref（DOI 与题录校验），部分题名逐条核对 DOI。
> **本文件只收录实际查到题录的条目**；每条标注证据：`c=` Crossref 引用数，`OA` OpenAlex 开放状态。
> 可复现性分级：★★★ 数据与代码公开 ／ ★★ 至少语料或代码其一公开 ／ ★ 方法可照做但需自建数据 ／ 待核 未验证。
> ⚠ 标注「薄」的主题 = 该方向没有直接对应的高权威文献，硬找会凑数，建议自建指标或用最近邻方法。

---

## T1 人类与 AI 文学文本的句法结构差异

| 论文 | 出处 | 证据 | 用途 | 可复现 |
|---|---|---|---|---|
| Reinhart, Markey, Laudenbach, Pantusen, Yurko, Weinberg 2025. *Do LLMs write like humans? Variation in grammatical and rhetorical styles* | PNAS | c=69，DOI 10.1073/pnas.2422455122；arXiv 2410.16107 | **本主题的核心论文**：用多个人类语料（含学术、新闻、论坛）对比 GPT 系列的语法与修辞风格分布，直接给出"风格分布而非单点特征"的框架 | ★★★（arXiv 版 + 代码仓库） |
| Herbold, Hippe, Andreas, Zorn, Najafi, Remus 2023. *A large-scale comparison of human-written versus ChatGPT-generated essays* | Scientific Reports 13 | c=330，OA gold，DOI 10.1038/s41598-023-45644-9 | 大规模语料上对比词汇、句法、篇章结构；结论是"LLM 作文在多项指标上更均质"。是最早的量化基准之一 | ★★★ |
| Muñoz-Ortiz, Gómez-Rodríguez, Vilares 2024. *Contrasting linguistic patterns in human and LLM-generated news text* | Artificial Intelligence Review | c=119，OA hybrid，DOI 10.1007/s10462-024-10903-2 | **用依存句法**而非表面句法比较人与 LLM 文本，方法可直接迁到中文 | ★★★ |
| O'Sullivan 2025. *Stylometric comparisons of human versus AI-generated creative writing* | HSSC 12 | c=21，OA gold，DOI 10.1057/s41599-025-05986-3（本地已有） | Burrows' Delta + 聚类；证明"人的簇宽、模型的簇紧" | ★★ |

**要点**：句法层面的结论已相当稳固——差异不在"更长/更短"，而在**分布的方差与依存结构的多样性**。InkSoul 的句法指纹应测分布形状，不是均值。

---

## T2 中文文学文本的句法模式复用 ⚠ 薄

没有直接研究"中文文学句法模式复用"的高权威论文。最近邻：

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| "Are translated Chinese Wuxia fiction and western heroic literature…" 2022 | Digital Scholarship in the Humanities | DOI 10.1093/llc/fqac019，OA green | 武侠小说的文体计量；给出可复用的中文小说特征集 |
| "Retranslated Chinese classical canon Journey to the West: a stylometric analysis" 2023 | DSH | DOI 10.1093/llc/fqad085，OA hybrid | 同一作品多次转译的句法复现分析——"复用"的方法论原型 |
| 刘颖等 2024（本地 #5）| HSSC 11 | DOI 10.1057/s41599-024-03510-7 | 中文语言复杂度的 Kolmogorov 度量 |

**结论**：这个主题要么自建指标（n-gram 句法模板复现率 / 依存子树重复率），要么把 DSH 的中文小说文体学方法搬过来。**不建议继续找现成论文。**

---

## T3 句法多样性与语言复杂度

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| Kyle & Crossley 2018. *Measuring syntactic complexity in L2 writing using fine-grained clausal and phrasal indices* | Modern Language Journal | c=429 | 细粒度句法复杂度指数的标准来源（L2SCA 的直接前身） |
| Lu Xiaofei 2010/2011. *Automatic analysis of syntactic complexity in second language writing*（L2SCA 工具） | IJCL | 工具本身 | **可直接跑中文（配中文分词/依存）**，是复现成本最低的一环 |
| 2026. *Beyond Quantification: Rethinking the Measurement of Syntactic Complexity* | IJAL | DOI 10.1111/ijal.70175 | 最新批评：单纯数指标不够，要看分布 |

**要点**：L2SCA 系列是成熟基建；"多样性"要另加熵/变异系数，不能只取均值。

---

## T4 LLM 的语言风格同质化

| 论文 | 出处 | 证据 | 用途 | 可复现 |
|---|---|---|---|---|
| Doshi & Hauser 2024. *Generative AI enhances individual creativity but reduces the collective diversity of novel content* | Science Advances 10 | c=1113，OA gold，DOI 10.1126/sciadv.adn5290 | **本领域引用最高的因果证据**：个体创意↑、集体多样性↓ | ★★★ |
| Sourati 等 2026. *Shrinking landscape of linguistic diversity* | Nature Human Behaviour | 88 万条文本，复杂度方差降 21–50%（本地已有） | 把"同质化"量化到方差层面 | ★★ |
| *Homogenization Effects of Large Language Models on Human Creative Ideation* 2024 | Creativity & Cognition | c=219，DOI 10.1145/3635636.3656204 | 人机协作实验中"想法趋同"的实证 | 待核 |
| *Perceptions of authorial voice* / 相关声音研究 | Assessing Writing 2022 | c=10，DOI 10.1016/j.asw.2022.100632 | 声音维度怎么测 | 待核 |

**要点**：这条线已经形成"因果实验（Doshi）+ 大规模语料（Sourati）+ 文体计量（O'Sullivan）"三层证据，是整批选题里最扎实的。

---

## T5 人类与 AI 创作的文体计量

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| O'Sullivan 2025（本地 #1） | HSSC | gold | 文学短篇的 Delta 方法 |
| *Stylometric detection of AI-generated texts* 2026 | DSH | DOI 10.1093/llc/fqag064 | 最新检测方法 |
| Li & Zhang 2025（本地 #8） | CCL 2025 | 34 特征、F1 91.8% | 中文社交文本特征表可直接抄 |
| Chakrabarty 等 2024. *Art or Artifice? LLMs and the False Promise of Creativity* | CHI 2024 | c=114，DOI 10.1145/3613904.3642731 | 创意写作的评估框架（不只是检测） |

---

## T6 中文句法结构与依存分析

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| Chen & Manning 2014. *A fast and accurate dependency parser using neural networks* | EMNLP 2014 | c=706，DOI 10.3115/v1/d14-1082 | 依存解析基线；至今仍是可复现下限 |
| Zhou 等 2014. *Building Chinese discourse corpus with connective-driven dependency tree* | EMNLP 2014 | c=94，DOI 10.3115/v1/d14-1224 | **中文篇章级依存语料（CDTB）**，做"句间连接"必需 |
| Universal Dependencies 中文树库（GSD / GSDSimp） | UD 项目 | 公开、CC BY-SA | 唯一开箱即用的中文依存标注数据 |

**要点**：中文句法分析不用自己训模型——UD 中文树库 + Stanza/HanLP 就够；真正的缺口在**篇章层**，CDTB 是少数可用资源。

---

## T7 句首结构与连接成分的重复 ⚠ 薄

没有"LLM 句首重复"的专门研究。可用替代：

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| *Discourse Coherence in the Wild: A Dataset, Evaluation and Methods* 2018 | SIGDIAL | c=49，DOI 10.18653/v1/W18-5403 | 篇章连贯性的可计算定义 |
| 连接词使用研究（ESL）2019 | IJIL | c=46 | 连接词过度使用的标注框架 |
| CDTB（见 T6） | — | — | 句间连接词的依存标注 |

**结论**：这是一个**空白且有价值**的点——"句首结构重复率"没人系统做过。可以自建指标并作为 InkSoul 的差异化贡献。

---

## T8 语篇组织模式与段落结构同质化 ⚠ 薄

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| RST 篇章结构解析（rst-dt / DMRST） | ACL 系列 | 公开代码 | 段落组织可形式化为 RST 树 |
| *Discourse-Structural Noise in LLM-Generated Explanations* 2026 | WNUT | DOI 10.18653/2026.wnut-1.5 | 最新的 LLM 篇章结构噪声研究 |

**结论**：方法有（RST 解析），但"段落结构同质化"尚无权威计量研究。属可攻方向。

---

## T9 叙事中的句法变化与节奏 ⚠ 薄（但有经典方法）

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| *Sentence length distribution / burstiness* 类研究 | 计算文体学 | — | 句长分布 = 节奏的最直接代理指标 |
| 修辞学经典：节奏与句长（Leech & Short《Style in Fiction》方法章） | 教材 | — | 把"节奏"操作化为句长/停顿/信息密度 |

**结论**：文学理论讲得多，可计算的少。可行做法：句长方差、句长自相关（burstiness）、段落内句数节奏——这三项没人系统做过。

---

## T10 AI 文本的词汇多样性与表达模式

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| *Playing with words: Comparing the vocabulary and lexical diversity of ChatGPT and humans* 2024 | Machine Learning with Applications | c=47，OA gold，DOI 10.1016/j.mlwa.2024.100602 | TTR/MATTR/HD-D 多指标对照，结论：AI 词汇多样性**更高** |
| Kendro, Maloney, Jarvis 2026（本地 #14） | IJAL | DOI 10.1111/ijal.70115 | 6 维词汇多样性 + 4 模型 × 240 人 |
| *GPT detectors are biased against non-native English writers* 2023 | Patterns | c=664，DOI 10.1016/j.patter.2023.100779 | **必读的警告**：检测器会误伤非母语者，评估必须控制这个混杂 |

---

## T11 文学作品中的隐性情绪表达

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| *Sentiment Analysis for Literary Texts: Hemingway as a Case-study* 2024 | JDMDH | c=5，OA diamond，DOI 10.46298/jdmdh.13155 | 文学文本情感分析的可复现流程 |
| Kim & Klinger 类情感语料工作（FICTION / dailydialog 系） | — | 公开语料 | 情绪标注体系与数据 |

**要点**：隐性情绪需要"不出现情绪词"的检测；现有工具都偏显性词。这是可做的增量。

---

## T12 人物语言风格与个体化

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| *Character Speech Individualization in Charles Dickens's Novels* 2022 | Studies in Media and Communication | OA diamond，DOI 10.11114/smc.v10i3.5848 | 用计量方法区分人物话语 |
| *Speech in the English Novel: Speech and Character: Idiolect*（经典） | 专著章节 | — | idiolect 的理论定义 |
| 对话风格迁移（参数高效微调）2025 | Bulletin of T. Shevchenko Univ. | DOI 10.17721/1812-5409.2025/2.30 | 技术路线 |

**结论**：人物声音的**计量**研究比理论少得多；可直接用 Burrows' Delta 做"人物 × 章节"的距离矩阵。

---

## T13 修辞的模式化与过度使用

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| Reinhart 等 2025 PNAS（见 T1） | PNAS | 修辞风格（rhetorical styles）的分布比较 | 直接有"修辞过度使用"的量化 |
| *Do LLMs write like humans?* 同上的修辞维度 | — | — | 同上 |
| 公式化语言研究（formulaic language）综述 | 专著 | c=7 | 定义与标注框架 |

---

## T14 人类创作中的语言选择机制

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| *Beyond subjective judgments: Predicting evaluations of creative writing* 2018 | Behavior Research Methods | c=64 | 创作质量的可计算化 |
| *Synthetic Literature: Writing Science Fiction in a Co-Creative Process* 2017 | — | c=53 | 人机共创的语言选择交互 |
| 作者修订过程研究（Keystroke logging 类） | — | — | 真实写作过程数据 |

**结论**：机制研究偏认知/实验，计算侧几乎没有。想用只能做小规模实验（自行收集）。

---

## T15 AI 辅助写作与作者声音

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| *Voice in L2 writing in the age of AI* 2025 | JSLW | c=32，DOI 10.1016/j.jslw.2025.101212（closed） | 声音研究的理论框架 |
| *Authorial voice and textual ownership in AI-assisted EFL academic writing* 2026 | Computers & Composition | c=3，DOI 10.1016/j.compcom.2026.103035 | 最新的声音/归属实证 |
| *Exploring Students' Generative AI-Assisted Writing Processes* 2024 | Tech Know Learn | c=346，DOI 10.1007/s10758-024-09744-3 | 过程数据 |

---

## T16 具体性、感官描写与具身叙事

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| Brysbaert, Warriner, Kuperman 2014. *Concreteness ratings for 40 thousand generally known English word lemmas* | Behavior Research Methods | c=1822，DOI 10.3758/s13428-013-0403-5 | **具体性评分的标准资源**，直接可算 |
| *Vision dominates in perceptual language* 2018 | Cognition | c=181 | 感官词汇的分布规律 |
| *Large language models predict human sensory judgments* 2024 | Scientific Reports | c=84，OA gold | 用 LLM 打感官标签的可行性 |

**要点**：这一主题是 20 个里**最容易做量化**的——有现成评分表 + 现成感官词典，当天就能算出"具体性分布"。

---

## T17 生成式模型的叙事扁平化

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| Chakrabarty 等 2024. *Art or Artifice?* | CHI 2024 | c=114，DOI 10.1145/3613904.3642731 | 创意评估的五维框架 |
| Xu 等 2025. *Sui Generis*（本地 #7） | PNAS | 情节元素跨代回响 | 重复性度量 |
| Doshi & Hauser 2024（见 T4） | Sci Adv | 集体多样性下降 | 因果证据 |
| *MirrorStories: Reflecting Diversity through Personalized Narrative Generation* 2024 | EMNLP | DOI 10.18653/v1/2024.emnlp-main.382 | 多样性可被提升的反证 |

---

## T18 不同文学体裁的语言风格差异

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| Sukying & Barrot 2025（本地 #12） | CCC | 议论文 vs 记叙文句法差异 | 直接的体裁对照 |
| *Modeling Communicative Purpose with Functional Style* 2017 | ACL Workshop | DOI 10.18653/v1/W17-4910 | 功能文体分类 |

**结论**：体裁效应必须作为协变量控制，否则会误判为文风差异。

---

## T19 中文文学语料库与计算文体学

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| *Corpus stylistics and Chinese literary discourses* 2019 | Routledge Handbook of Chinese Applied Linguistics 章 | DOI 10.4324/9781315213705-36 | 中文语料库文体学的唯一综述章 |
| *Interfacing corpus linguistics and computational stylistics* 2013 | IJCL | c=19，DOI 10.1075/ijcl.18.2.04gra | 方法桥接 |
| 中文网络文学计算文体学（本地 #9，Yao 2025） | Translation Spaces | DOI 10.1075/ts.24043.yao | 网文语料 |

**结论**：中文文学语料库本身是最大瓶颈——没有像 Gutenberg/Project Gutenberg 那样大规模开放的中文文学语料。这条应作为工程任务而不是文献任务。

---

## T20 基于句法与文体特征的生成过程控制

| 论文 | 出处 | 证据 | 用途 |
|---|---|---|---|
| *Rich Syntactic and Semantic Information Helps Unsupervised Text Style Transfer* 2020 | INLG | DOI 10.18653/v1/2020.inlg-1.17 | 句法信息用于风格迁移 |
| *Real-Time Syntactic Scaffolding for Controllable L2 Text Generation* 2025 | IEEE AI3E | DOI 10.1109/ai3e69313.2025.00049 | 句法脚手架式控制 |
| *Contextual Diversity Measure (CDM) for Controllable Story Generation* 2026 | ACL SRW | DOI 10.18653/v1/2026.acl-srw.98 | 把"多样性"变成可优化目标 |

**结论**：生成侧的可控性文献集中在"风格迁移"，把**中文句法指纹**当控制信号的工作基本没有——这是 InkSoul 最有机会的位置。

---

## 优先阅读顺序（我的判断）

1. **Doshi & Hauser 2024**（Sci Adv）— 因果最硬，决定整个问题的合法性
2. **Reinhart 等 2025**（PNAS）— 方法论骨架，分布而非均值
3. **Muñoz-Ortiz 2024**（AI Review）— 依存句法对比的现成流程，可直迁中文
4. **Brysbaert 2014**（BRM）— 资源类，当天可用
5. **Li & Zhang 2025**（CCL）— 中文特征清单
6. **Chakrabarty 2024**（CHI）— 评估框架

**文献薄弱、适合自建指标的主题**：T2、T7、T8、T9、T12、T14。这六块不是"没找到"，是"确实没人做"——可以成为贡献点，但别指望有论文兜底。
