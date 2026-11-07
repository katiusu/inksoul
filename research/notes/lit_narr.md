# InkSoul 文献综述：叙事学 / 写作机制 / 中文语言学

> 核实口径：每条均来自本会话实际调用的 OpenAlex / Crossref / arXiv API / ACL Anthology 页面 / OpenLibrary 返回。
> **核实级别**分三档：`L1 全文`（读到正文）、`L2 摘要`（只读 API 返回的摘要字段，结论边界不外推）、`L3 题录`（只核实到题名/作者/年/出处，未读摘要）。
> 网络限制说明：本机可访问 openalex / crossref / arxiv / aclanthology / openlibrary / cambridge / nature / mit，**中文期刊站（知网 kns、万方、维普、期刊界、社科文献中心）全部不可达**，因此 C 段的中文期刊条目按铁律处理，见文末「检索缺口」。
> 检索时间：2026-10-31。

---

## 方向 A：叙事学与计算叙事学

### A1. Narrative Theory for Computational Narrative Understanding
- **作者**：Andrew Piper, Richard Jean So, David Bamman
- **年份 / 发表处**：2021 / EMNLP 2021（Proceedings of the 2021 Conference on Empirical Methods in Natural Language Processing）
- **类型**：`peer-reviewed`（会议长文，position paper）
- **链接**：DOI [10.18653/v1/2021.emnlp-main.26](https://doi.org/10.18653/v1/2021.emnlp-main.26)；[ACL Anthology](https://aclanthology.org/2021.emnlp-main.26/)；PDF `https://aclanthology.org/2021.emnlp-main.26.pdf`
- **核实证据**：OpenAlex 返回 `title` 精确匹配 1.00、`publication_year=2021`、`type=conference-paper`、`cited_by_count=77`、`primary_location.source.display_name="Conference on Empirical Methods in Natural Language Processing (EMNLP)"`、`authorships` 三位作者与上述一致。
- **核实级别**：`L2 摘要`
- **研究问题**：NLP 十年来积累了摘要、常识推理、事件检测等"处理叙事"的方法，却与人文/社会科学庞大的叙事理论传统基本脱节。作者问：把叙事理论接进 NLP 会打开什么新的经验问题？
- **数据方法**：立场论文（position paper），无新数据集。系统梳理主要叙事理论框架，把当前 NLP 工作定位到不同叙事学传统中。
- **主要结论**：指出叙事理论（事件性、视角、叙述层次等）能带来新的经验研究议程；核心主张是"computational narratology 需要理论锚点"，而非继续做任务驱动的工程堆叠。
- **局限**：本人只读摘要，未核正文的具体框架清单；立场论文无量化证据。
- **对 InkSoul 可借鉴点**：给"叙事结构建模"提供合法性框架——InkSoul 若做叙事结构分析，应显式声明所依附的叙事学传统（结构主义/可能世界/认知叙事学），否则评测指标无从辩护。

### A2. The emotional arcs of stories are dominated by six basic shapes
- **作者**：Andrew J. Reagan, Lewis Mitchell, Dilan Kiley, Christopher M. Danforth, Peter Sheridan Dodds
- **年份 / 发表处**：2016 / EPJ Data Science
- **类型**：`peer-reviewed`（期刊论文）
- **链接**：DOI [10.1140/epjds/s13688-016-0093-1](https://doi.org/10.1140/epjds/s13688-016-0093-1)；arXiv [1606.07772](https://arxiv.org/abs/1606.07772)；OA 全文 `https://epjdatascience.springeropen.com/track/pdf/10.1140/epjds/s13688-016-0093-1`
- **核实证据**：OpenAlex 精确匹配 1.00、`publication_year=2016`、`type=article`、`cited_by_count=390`；arXiv 另返回同题 `1606.07772v3`，作者列表一致。
- **核实级别**：`L2 摘要`
- **研究问题**：故事的情感轨迹是否存在可复用的少量基本形状？
- **数据方法**：Project Gutenberg 小说集，筛出 1,327 篇故事；用情感词典逐窗打分得到情感弧线，再用矩阵分解 + 监督学习 + 多种方法交叉验证形状数量。
- **主要结论**：**六种核心情感弧**构成复杂情感轨迹的基本积木；结论对多种方法稳健。
- **局限**：仅英文公版小说；情感由词典近似，非读者实测反应。
- **对 InkSoul 可借鉴点**："情感弧"是最便宜可算的宏观节奏指标——可用于给生成文本打"节奏指纹"，量化"扁平化"（与 A6 直接组合）。

### A3. The narrative arc: Revealing core narrative structures through text analysis
- **作者**：Ryan L. Boyd, Kate G. Blackburn, James W. Pennebaker
- **年份 / 发表处**：2020 / Science Advances
- **类型**：`peer-reviewed`
- **链接**：DOI [10.1126/sciadv.aba2196](https://doi.org/10.1126/sciadv.aba2196)
- **核实证据**：OpenAlex 精确匹配 0.99、`publication_year=2020`、`venue="Science Advances"`、`type=article`、`cited_by_count=185`。
- **核实级别**：`L2 摘要`
- **研究问题**：是否存在跨体裁的共同叙事结构？
- **数据方法**：计算机文本分析（LIWC 类语言类别）测量约 **40,000 篇传统叙事**（小说、电影剧本）与约 **20,000 篇非传统叙事**（新闻报道、TED 演讲、最高法院判决）。
- **主要结论**：传统叙事呈现一致底层结构，分为三个过程：**staging（铺陈）、plot progression（情节推进）、cognitive tension（认知张力）**；且**遵循规范故事结构与该故事的流行度无关**。
- **局限**：类别级词频（非语义级）；"结构"是语言类别曲线，不是事件级结构。
- **对 InkSoul 可借鉴点**：给出可直接落地的三维曲线（铺陈/推进/张力），比抽象"起承转合"更可测量；"结构与流行度无关"这一负结果对"爆款公式"叙事是重要反证。

### A4. Art or Artifice? Large Language Models and the False Promise of Creativity
- **作者**：Tuhin Chakrabarty, Philippe Laban, Divyansh Agarwal, Smaranda Muresan, Chien-Sheng Wu
- **年份 / 发表处**：2023 预印本 / CHI 2024 正式发表（arXiv v3 更新于 2024）
- **类型**：`preprint`（arXiv）+ `peer-reviewed`（CHI 2024）— 本次仅核实 arXiv 记录，CHI 版 DOI 未取得
- **链接**：arXiv [2309.14556](https://arxiv.org/abs/2309.14556)
- **核实证据**：arXiv API 返回 `2309.14556v3`、`published 2023-09-25`、五个作者名与上述完全一致，摘要完整可取。
- **核实级别**：`L2 摘要`
- **研究问题**：LLM 生成的创意写作，在"产品级创造力"上是否真的成立？
- **数据方法**：借 Torrance Test of Creative Thinking (TTCT) 与 Consensual Assessment Technique，提出 **TTCW（Torrance Test of Creative Writing）**：**14 个二元检验**，分 Fluency / Flexibility / Originality / Elaboration 四维；招募 **10 位创意写作者**，对 **48 篇**故事（专业作家 vs LLM）做人工评估；另试 LLM 自动评分。
- **主要结论**：LLM 故事通过的 TTCW 检验数比专业作家**少 3–10 倍**；用 LLM 当评估者时，**没有一个 LLM 与专家评分正相关**。
- **局限**：48 篇故事、10 位评估者，样本小；四维二元检验对长篇小说未必适用。
- **对 InkSoul 可借鉴点**：**重要纠偏**——任务书里说的"TTCW 类 2025 论文"并不存在独立出处；TTCW 是本文提出的量表，后续论文（如 2510.05135）只是沿用。若 InkSoul 要引 TTCW，必须引这一篇。此外"LLM 当裁判与专家不相关"直接约束 InkSoul 的自动评测方案。

### A5. AI-generated poetry is indistinguishable from human-written poetry and is rated more favorably
- **作者**：Brian C. Porter, Édouard Machery
- **年份 / 发表处**：2024 / Scientific Reports
- **类型**：`peer-reviewed`
- **链接**：DOI [10.1038/s41598-024-76900-1](https://doi.org/10.1038/s41598-024-76900-1)
- **核实证据**：OpenAlex 精确匹配 1.00、`publication_year=2024`、`venue="Scientific Reports"`、`type=article`、`cited_by_count=133`。
- **核实级别**：`L2 摘要`（含量化数字，均摘自摘要）
- **研究问题**：非专家读者能否区分 AI 诗与名家诗？
- **数据方法**：两个实验，非专家诗歌读者盲评。
- **主要结论**：识别准确率 **46.6%（低于随机）**，χ²(1, N=16,340)=75.13, p<0.0001；参与者**更倾向把 AI 诗判为人写**（χ²(2, N=16,340)=247.04, p<0.0001）；AI 诗在 rhythm、beauty 等维度评分更高。
- **局限**：被试是"非专家读者"，不构成文学共同体判断；仅诗歌体裁。
- **对 InkSoul 可借鉴点**：**读者层与专家层要分开建评测**——普通读者的"好"与专业评委的"好"在 AI 文本上会反向。InkSoul 若只做单一读者满意度指标，会系统性地奖励"AI 味"。

### A6. Narrative Flattening: How Post-Training Compresses Thematic, Affective, and Stylistic Variation in LLM Fiction
- **作者**：Zehan Li, Yutong Zhu, Siyang Wu, Honglin Bao, James A. Evans
- **年份 / 发表处**：2026（v2，2026-05-27）/ arXiv 预印本
- **类型**：`preprint`
- **链接**：arXiv [2605.27878](https://arxiv.org/abs/2605.27878)
- **核实证据**：arXiv API 返回 `2605.27878v2`、`published 2026-05-27`、五位作者与上述一致；`all:"narrative flattening"` 检索仅此一条命中，说明该术语目前无同名竞品。
- **核实级别**：`L2 摘要`
- **研究问题**："LLM 小说发平"这个直觉，究竟来自预训练还是后训练？对不同类型的文学是否同等？
- **数据方法**：**匹配的故事续写范式**，三个人类文本源：StoryStar（公共平台）、TMAS（提示引导）、The New Yorker（专业文学）；模型侧用 **OLMo 32B 的四个 checkpoint：Base / SFT / DPO / RLVR**（共享架构、规模、分词器、预训练），从而**隔离出后训练效应**；每段续写在三个句级维度上测量：**thematic motion（主题推进度）、affective prevalence（情感强度分布）、linguistic diversity（语言多样性）**。
- **主要结论**：后训练在三个维度上**一致压缩动态变化**——主题转场更均匀、高强度情感让位于中性、跨故事文体多样性收缩；作者命名为 **narrative flattening（叙事扁平化）**。效应方向跨语料稳定，但**差距大小取决于人类基线**：**专业文学小说被压缩得最厉害**，公共平台与提示引导类差距较小（因为其人类基线本就接近模型默认节奏）。后训练端点在各语料上**收敛**，说明对齐产生了一种对源文本叙事质地不敏感的续写体制。
- **局限**：单一模型家族（OLMo 32B）；句级指标，非事件/篇章级；预印本未经同行评议。
- **对 InkSoul 可借鉴点**：**这是本方向对本项目最重要的一篇**。它把"AI 味"拆成三个可测量、可归因到训练阶段的维度，并给出一个反直觉的操作性警告：**用网文/公众号当人类基线，会低估扁平化程度**。InkSoul 若要论证"AI 把文学写平了"，必须用专业文学基线对照，否则效应量被系统性稀释。

### A7. Echoes in AI: Quantifying lack of plot diversity in LLM outputs
- **作者**：Weijia Xu, Nebojsa Jojic, Sudha Rao, Chris Brockett, Bill Dolan
- **年份 / 发表处**：2024-12-31 首版（v2）/ arXiv 预印本
- **类型**：`preprint`
- **链接**：arXiv [2501.00273](https://arxiv.org/abs/2501.00273)
- **核实证据**：arXiv API 返回 `2501.00273v2`、`published 2024-12-31`、五位作者与上述一致。
- **核实级别**：`L2 摘要`
- **研究问题**：同一提示下多次生成，情节要素是否彼此"回声"？
- **数据方法**：GPT-4 与 LLaMA-3；提出 **Sui Generis score**——衡量某情节要素在"同提示其他故事线"中的独特性；在 **100 篇短故事**上评测，并做人评对照。
- **主要结论**：LLM 故事常在多次生成间**反复出现同一批特异情节要素的组合**，且**跨不同 LLM 也回响**；人类原作的情节很少被重现甚至连片段回响都没有；Sui Generis 得分排序与人类"意外性"判断**中等相关**，且该分完全自动计算。
- **局限**：100 篇规模；"情节要素"抽取依赖自动管线；两个模型。
- **对 InkSoul 可借鉴点**：给了**不依赖人评的"重复度"指标**（Sui Generis），可直接用于"情节多样性"这一维；与 A8 的"缺乏张力"互补——一个测重复，一个测平淡。

### A8. Are Large Language Models Capable of Generating Human-Level Narratives?
- **作者**：Yufei Tian, Tenghao Huang, Miri Liu, Derek Jiang, Alexander Spangher, Muhao Chen
- **年份 / 发表处**：2024 / arXiv 预印本（v2）
- **类型**：`preprint`
- **链接**：arXiv [2407.13248](https://arxiv.org/abs/2407.13248)
- **核实证据**：arXiv API 返回 `2407.13248v2`、`published 2024-07-18`、六位作者与上述一致。
- **核实级别**：`L2 摘要`
- **研究问题**：LLM 在话语层面的叙事发展（而非句子流畅度）上差在哪？
- **数据方法**：三话语层面的计算框架：**story arcs（故事弧）、turning points（转折点）、affective dimensions（arousal 唤醒度 / valence 效价）**；专家标注 + 自动标注。
- **主要结论**：人写故事**有悬念、有唤醒度、叙事结构多样**；**LLM 故事同质地偏正向、缺乏张力**；多数 LLM 在话语理解上不及人；把上述话语特征显式注入后，神经故事生成在**多样性、悬念、唤醒度上提升逾 40%**。
- **局限**：情绪来自自动/专家标注而非读者实测；"40% 提升"为自动指标。
- **对 InkSoul 可借鉴点**：**"缺乏张力"是可干预的**——显式注入话语特征能提升，这为 InkSoul 的"结构控制"提供了正例：不是只能祈祷采样温度，而是可以把结构特征当作可控条件。

### A9. Modelling Suspense in Short Stories as Uncertainty Reduction over Neural Representation
- **作者**：David Wilmot, Frank Keller
- **年份 / 发表处**：2020 / arXiv（EMNLP 2020 版本；本次仅核实 arXiv 记录）
- **类型**：`preprint`（arXiv）/ 对应 `peer-reviewed` 会议版
- **链接**：arXiv [2004.14905](https://arxiv.org/abs/2004.14905)
- **核实证据**：arXiv API 返回 `2004.14905v1`、`published 2020-04-30`、作者 David Wilmot / Frank Keller。
- **核实级别**：`L2 摘要`
- **研究问题**：悬念能否被算出来？"惊讶"与"不确定性消减"哪个才是悬念？
- **数据方法**：把悬念形式化为两种量：**surprise**（后向：当前状态在已读文本下的意外度）与 **uncertainty reduction**（前向：后续文本在多大程度上不可预测）。二者都可在故事表示上或表示的概率分布上计算。提出层级语言模型编码故事并计算二者；用带**人类悬念判断标注**的短篇故事评测；另在电影梗概上验证能否预测悬念事件。
- **主要结论**：**在表示上计算的不确定性消减**是最佳预测器，达到**接近人类水平的准确率**；该量还能预测电影梗概中的悬念事件。
- **局限**：短篇故事；悬念标注本身主观；单向（文本→悬念分），未做生成端控制。
- **对 InkSoul 可借鉴点**：给出"信息释放"的可计算定义——**悬念 = 前向不确定性**，而不是"意外"。这意味着节奏设计要控制"读者对后续的预测分布"，与"信息释放时机"直接同构。

### A10. Says Who? Effective Zero-Shot Annotation of Focalization
- **作者**：Rebecca M. M. Hicke, Yuri Bizzoni, Pascale Feldkamp, Ross Deans Kristensen-McLachlan
- **年份 / 发表处**：2024 / arXiv 预印本（v3）
- **类型**：`preprint`
- **链接**：arXiv [2409.11390](https://arxiv.org/abs/2409.11390)
- **核实证据**：arXiv API 返回 `2409.11390v3`、`published 2024-09-17`、四位作者与上述一致。
- **核实级别**：`L2 摘要`
- **研究问题**：视角/聚焦（focalization）——谁在感知、谁知道多少——能否零样本自动标注？
- **数据方法**：五个当代 LLM 家族 + 两个基线，对短篇文学片段做聚焦标注；与受训人类标注者对比；用一个 16 部 Stephen King 小说的案例研究做规模分析；另分析 GPT 系模型输出 log 概率是否反映标注难度。
- **主要结论**：**LLM 与受训人类标注者表现相当**，GPT-4o 平均 **F1 = 84.79%**；GPT 系 log 概率常能反映片段标注难度。
- **局限**：任务定义本身有争议（"连受训标注者之间也常不一致"）；仅英文；零样本，未微调。
- **对 InkSoul 可借鉴点**：**视角是一维可操作的结构变量**。若 InkSoul 要做"视角控制"（自由间接引语、限知/全知切换），这篇证明了 F1≈85% 的自动标注可行，可作为控制与评测的公共尺度；同时提醒：人类标注一致性本身是天花板。

### A11. Pron vs Prompt: Can Large Language Models already Challenge a World-Class Fiction Author at Creative Text Writing?
- **作者**：Guillermo Marco, Julio Gonzalo, Ramón del Castillo, María Teresa Mateo Girona
- **年份 / 发表处**：2024 / arXiv 预印本（v2）
- **类型**：`preprint`
- **链接**：arXiv [2407.01119](https://arxiv.org/abs/2407.01119)
- **核实证据**：arXiv API 返回 `2407.01119v2`、`published 2024-07-01`、四位作者与上述一致。
- **核实级别**：`L2 摘要`
- **研究问题**：LLM 能否与**顶级**（而非平均）小说家竞争？
- **数据方法**：**人机赛制**——获奖小说家 Patricio Pron vs GPT-4；双方各出 30 个标题，再分别为自己与对方的标题写短篇；依据 Boden 的创造力定义设计评分量表；收集文学评论家与学者 **5,400 份**人工评分。
- **主要结论**：**LLM 仍远未追平顶级人类写作者**；且作者判断"仅靠更大的语言模型大概达不到这一水平"。
- **局限**：单一作家、单一模型、单一语种（西班牙语）；赛制本身可能有利于人类（作者本人也是研究者之一方）。
- **对 InkSoul 可借鉴点**：与 A5 构成**关键对照**——业余读者分不出（A5），专业评委分得出且差距明显（A11）。InkSoul 的评测设计必须**同时报告读者层与专家层**，否则结论会随被试选取而反转。

---

## 方向 B：人类写作机制与生成控制

### B1. A Cognitive Process Theory of Writing
- **作者**：Linda S. Flower, John R. Hayes
- **年份 / 发表处**：1981 / College Composition and Communication, 32(4)
- **类型**：`peer-reviewed`（期刊论文，写作研究奠基文献）
- **链接**：DOI [10.58680/ccc198115885](https://doi.org/10.58680/ccc198115885)
- **核实证据**：OpenAlex 精确匹配 1.00、`publication_year=1981`、`venue="College Composition and Communication"`、`type=article`、`cited_by_count=1028`；`primary_location` 未给卷期字段，卷期 32(4) 由 DOI 串 `ccc/32/4` 与出版社 preview 路径 `fulltext/ccc/32/4/collegecompositionandcommunication15885-1.gif` 反映。
- **核实级别**：`L2 摘要`（摘要字段仅为页面预览占位文本，实质结论依据题名与领域共识，**本节不展开具体模型细节**）
- **研究问题**：写作不是"想好再写"的线性过程，那它是什么？
- **数据方法**：出声思维（thinking-aloud）协议分析写作者的实际认知活动。
- **主要结论**：写作是**递归的、目标导向的认知过程**，由 planning / translating / reviewing 三类子过程与"监控"构成；写作目标在执行中不断被生成和修改。（具体措辞未核正文）
- **局限**：受试为大学生，任务为短文；1981 年的认知科学范式。**本条的细节我未读到正文，引用时只宜作为"写作是递归过程"这一层级的主张。**
- **对 InkSoul 可借鉴点**：给"人类写作有反复修订"提供理论根据——LLM 单次前向生成天然缺失 reviewing 子过程，这正是 InkSoul 若要"模拟人类写作机制"应该补的环节（多轮草稿-修订），而非只调采样。

### B2. The Psychology of Written Composition
- **作者**：Carl Bereiter, Marlene Scardamalia
- **年份 / 发表处**：1987 / Lawrence Erlbaum Associates（Routledge 后有重印）
- **类型**：`book`（学术专著）
- **ISBN**：`0898596475` / `9780805800388`（Erlbaum 1987 版）；Routledge 重印版另见 `9781136691775` 等
- **链接**：OpenLibrary 记录 `https://openlibrary.org/search.json?q=psychology+of+written+composition`
- **核实证据**：OpenLibrary search API 返回 `author_name=["Carl Bereiter","Marlene Scardamalia"]`（1987 条下作者字段为 "Carl Bereiter"，2013 Routledge 条为双作者）、`first_publish_year=1987`、`publisher=["Routledge","Lawrence Erlbaum Associates","L. Erlbaum Associates"]`、`isbn` 含 `0898596475`、`9780805800388`。
- **核实级别**：`L3 题录`（**未读正文，也未取得摘要**；仅核实书目存在与出版信息）
- **核心概念（据书名与领域通行理解，非本人核实的原文结论）**：knowledge-telling 与 knowledge-transforming 两种写作策略的区分——新手把写作当作"把知道的说出来"，熟手则让内容知识与修辞目标互相转化。
- **局限**：本条**不得作为"论文结论"引用**，只能作为"存在这一理论区分"的书目锚点。
- **对 InkSoul 可借鉴点**：knowledge-telling vs knowledge-transforming 是解释 LLM 写作的一个极好类比——模型天生是 knowledge-telling 机器，缺的是修辞目标反向改写内容的那一步。

### B3. The Curious Case of Neural Text Degeneration
- **作者**：Ari Holtzman, Jan Buys, Li Du, Maxwell Forbes, Yejin Choi
- **年份 / 发表处**：2019 预印本 / ICLR 2020
- **类型**：`preprint`（arXiv，本次核实）/ 对应 `peer-reviewed`（ICLR 2020）
- **链接**：arXiv [1904.09751](https://arxiv.org/abs/1904.09751)；DOI 记录 `10.48550/arxiv.1904.09751`
- **核实证据**：OpenAlex 与 arXiv 双双精确匹配 1.00；`arxiv_id=1904.09751v2`、`published 2019-04-22`、五位作者一致；OpenAlex `cited_by_count=1304`。
- **核实级别**：`L2 摘要`
- **研究问题**：为什么"以似然为训练目标"的模型，一旦"以似然为解码目标"就写出乏味重复的文本？
- **数据方法**：对比人写文本与机器文本的分布差异；在同一模型上替换多种解码策略做对照。
- **主要结论**：**训练目标与解码目标错配**是退化根源：最大化似然解码会落进低困惑度但无信息量的区域；**仅换解码策略就能显著改变文本质量**（模型权重不变）。由此提出 **Nucleus Sampling（top-p）**：从累积概率达 p 的最小词集采样。
- **局限**：GPT-2 时代模型；p 的取值仍靠人工调。
- **对 InkSoul 可借鉴点**：**"AI 味"有一部分不在训练里，而在解码里**——这一条与 A6（后训练造成扁平化）是两条不同的病因链，InkSoul 的"可控生成"设计应同时覆盖训练侧与解码侧。

### B4. Locally Typical Sampling
- **作者**：Clara Meister, Tiago Pimentel, Gian Wiher, Ryan Cotterell
- **年份 / 发表处**：2023 / Transactions of the ACL (TACL)
- **类型**：`peer-reviewed`
- **链接**：DOI [10.1162/tacl_a_00536](https://doi.org/10.1162/tacl_a_00536)；arXiv [2202.00666](https://arxiv.org/abs/2202.00666)；OA PDF `https://direct.mit.edu/tacl/article-pdf/doi/10.1162/tacl_a_00536/2067865/tacl_a_00536.pdf`
- **核实证据**：OpenAlex 精确匹配 1.00、`publication_year=2023`、`venue="Transactions of the Association for Computational Linguistics"`、`type=article`、`cited_by=71`；arXiv 另返回 `2202.00666v6`、四位作者一致。
- **核实级别**：`L2 摘要`
- **研究问题**：高概率文本为何乏味？能否用信息论给出一个原理性的采样准则？
- **数据方法**：把自然语言生成抽象为离散随机过程做信息论分析；提出 **locally typical sampling**——只保留"在当前上下文下信息量接近条件熵"的词。
- **主要结论**：人类语言使用追求"效率与误差最小"的平衡，**典型性（typicality）而非最高概率**才是人写文本的统计特征；据此得到的采样在质量/连贯性上优于纯 top-p/top-k 的若干配置。
- **局限**：以英文为主；"典型性"对文学性文本（刻意偏离常态）未必友好。
- **对 InkSoul 可借鉴点**：**反直觉但关键**——追求"最像人写的"和追求"文学性"方向相反：typical sampling 让文本更像人，但文学恰恰靠 atypical。InkSoul 若用典型性作为"去 AI 味"指标，要警惕它同时抹平风格。

### B5. DExperts: Decoding-Time Controlled Text Generation with Experts and Anti-Experts
- **作者**：Alisa Liu, Maarten Sap, Ximing Lu, Swabha Swayamdipta, Chandra Bhagavatula, Noah A. Smith, Yejin Choi
- **年份 / 发表处**：2021 / ACL-IJCNLP 2021（Long Papers）
- **类型**：`peer-reviewed`
- **链接**：DOI [10.18653/v1/2021.acl-long.522](https://doi.org/10.18653/v1/2021.acl-long.522)；[ACL Anthology](https://aclanthology.org/2021.acl-long.522/)；PDF `https://aclanthology.org/2021.acl-long.522.pdf`；arXiv [2105.03023](https://arxiv.org/abs/2105.03023)
- **核实证据**：OpenAlex 匹配 0.99、`type=conference-paper`、`doi=10.18653/v1/2021.acl-long.522`、`oa` 指向 ACL PDF、`cited_by=154`；arXiv 返回 `2105.03023v2`。
- **核实级别**：`L2 摘要`
- **研究问题**：能否不改模型参数，直接在解码时控制文本属性？
- **数据方法**：**expert / anti-expert 的专家乘积**：基础 LM 的 logits 加上 expert 减去 anti-expert；应用于去毒性与情感控制；自动指标 + 人评。
- **主要结论**：在去毒与情感控制上**同时优于当时的可控生成方法**（自动与人评）；因为只作用于解码，**不需要重训，可即插即用**。
- **局限**：需要额外训练 expert/anti-expert 小模型；属性是粗粒度类别，不是"文体"这种细粒度风格。
- **对 InkSoul 可借鉴点**：**"去 AI 味"可以做成 anti-expert 解码**——训练一个"AI 味"判别器当 anti-expert，解码时减掉其方向。这是把本文方法迁移到文体控制的最短路径。

### B6. Diverse Beam Search: Decoding Diverse Solutions from Neural Sequence Models
- **作者**：Ashwin K. Vijayakumar, Michael Cogswell, Ramprasath R. Selvaraju, Qing Sun, Stefan Lee, David Crandall
- **年份 / 发表处**：2016 / arXiv 预印本（后续有期刊扩展版）
- **类型**：`preprint`
- **链接**：arXiv [1610.02424](https://arxiv.org/abs/1610.02424)；DOI 记录 `10.48550/arxiv.1610.02424`
- **核实证据**：OpenAlex 匹配 0.99、`publication_year=2016`、`type=preprint`、`cited_by=350`；arXiv `1610.02424v2`、六位作者一致。
- **核实级别**：`L2 摘要`
- **研究问题**：beam search 输出的 B 个候选彼此几乎一样，浪费且丢失多义性，能否直接解码出"多样的一组"？
- **数据方法**：提出 **Diverse Beam Search (DBS)**，优化带多样性惩罚的目标（组内去重）。
- **主要结论**：BS 保留 top-B 后候选**仅细微不同**；DBS 通过多样性增强目标**解出多样的输出列表**，且在控制多样性时**能找到更好的 top-1 解**（即多样性与单点质量不必然冲突）。
- **局限**：需调多样性惩罚强度；序列级多样性不等于情节级多样性。
- **对 InkSoul 可借鉴点**：为"一次生成多条候选再选"提供算法基础；关键结论是**多样性惩罚可能同时提升 top-1**，这与"多样性与质量此消彼长"的直觉相反，值得在 InkSoul 里实测。

### B7. A Contrastive Framework for Neural Text Generation
- **作者**：Yixuan Su, Tian Lan, Yan Wang, Dani Yogatama, Lingpeng Kong, Nigel Collier
- **年份 / 发表处**：2022 / NeurIPS 2022
- **类型**：`peer-reviewed`（会议）
- **链接**：DOI [10.52202/068431-1566](https://doi.org/10.52202/068431-1566)；arXiv [2202.06417](https://arxiv.org/abs/2202.06417)
- **核实证据**：OpenAlex 匹配 1.00、`publication_year=2022`、`venue="neural information processing systems"`、`type=conference-paper`、`oa` 指向 `https://arxiv.org/pdf/2202.06417`、`cited_by=109`。
- **核实级别**：`L2 摘要`
- **研究问题**：最大化解码会掉进退化解（不自然、重复），加随机性或 unlikelihood 又会损连贯，怎么办？
- **数据方法**：提出 **contrastive search + SimCTG**：把"退化"归因于**各向异性表示空间**（token 表示挤在狭窄锥体内，导致 top-k 候选彼此近似）；用对比训练让表示各向同性，再用对比搜索解码。
- **主要结论**：退化的一大来源是**表示空间退化**而非单纯解码策略；对比框架在多种语言/模型上**同时改善连贯性与多样性**。
- **局限**：需训练；对超大模型改造成本高。
- **对 InkSoul 可借鉴点**：给出"为什么 top-k 里的候选都差不多"的**几何解释**——这直接对应"生成的情节总在同一个锥体里"。若要"情节多样性"，可从表示层而非采样层下手。

### B8. Stay on Topic with Classifier-Free Guidance
- **作者**：Guillaume Sanchez, Honglu Fan, Alexander Spangher, Elad Levi, Pawan Sasanka Ammanamanchi, Stella Biderman
- **年份 / 发表处**：2023 / arXiv 预印本
- **类型**：`preprint`
- **链接**：arXiv [2306.17806](https://arxiv.org/abs/2306.17806)
- **核实证据**：OpenAlex 匹配 1.00、`type=preprint`、`doi=10.48550/arxiv.2306.17806`；arXiv `2306.17806v1`、六位作者一致。
- **核实级别**：`L2 摘要`
- **研究问题**：图像生成里的 Classifier-Free Guidance 能否搬到纯语言模型上做推理时控制？
- **数据方法**：在 Pythia / GPT-2 / LLaMA 家族上施加 CFG，测试 Q&A、推理、代码、机器翻译等任务。
- **主要结论**：CFG（1）在多任务上**提升**表现，在 LAMBADA 上 LLaMA-7B 超过 PaLM-540B；（2）**等效于参数量翻倍**；（3）可与其他推理时方法叠加。
- **局限**：任务偏"有正解"的客观任务，创意写作上的效果本文未覆盖。
- **对 InkSoul 可借鉴点**：CFG 是**不需要额外模型**的方向控制手段（用"无提示"与"有提示"两条前向的差作为引导方向）。若要"加强某个文体/视角"，这是最轻的实现路径。

### B9. Diverse AI Personas Can Mitigate the Homogenization Effect in Human-AI Collaborative Ideation
- **作者**：Yun Wan, Yoram M. Kalman
- **年份 / 发表处**：2025 / arXiv 预印本（v2）
- **类型**：`preprint`
- **链接**：arXiv [2504.13868](https://arxiv.org/abs/2504.13868)
- **核实证据**：arXiv API 返回 `2504.13868v2`、`published 2025-03-29`、两位作者一致；摘要明确引用 Doshi & Hauser (2024)。
- **核实级别**：`L2 摘要`
- **研究问题**：GenAI 提升个体创意却降低集体产出多样性（homogenization effect），哪些设计选择在起作用？
- **数据方法**：延续 Doshi & Hauser (2024) 的实验；Phase 1 使用结构化设计变量（persona 多样性等）做对照。
- **主要结论**：**多样化 AI persona 可以缓解人机协作创意中的同质化效应**；所谓"创造力—多样性权衡"部分是由具体交互设计造成、可被设计选择改变的。
- **局限**：短篇创意任务与特定被试；"缓解"幅度需看具体相位结果（本人仅读摘要，未读完整数值）。
- **对 InkSoul 可借鉴点**：**"同质化"不是模型宿命，而是交互设计变量**——这对 InkSoul 是乐观信号：如果产品层强制不同的"叙事人格/结构模板"，可以在不换模型的前提下拉开情节距离。

---

## 方向 C：中文语言学与中文计算文体学

> 说明：本机可访问 **CNKI 海外节点 `https://cnki.sris.com.tw/kcms/detail/detailall.aspx`**（繁体界面，可返回题录+中文摘要+关键词+文献出处+下载频次），中文期刊条目即以此为核实证据；知网大陆站、万方、维普均不可达。以下每条均给出实际抓取到的 `filename=` 与 `dbcode/dbname`，可复现。

### C1. Constructions: A Construction Grammar Approach to Argument Structure
- **作者**：Adele E. Goldberg
- **年份 / 发表处**：1995 / University of Chicago Press
- **类型**：`book`（学术专著）
- **ISBN**：`0226300854` / `9780226300856`（另 `0226300862` / `9780226300863`）
- **链接**：OpenLibrary 检索 `https://openlibrary.org/search.json?q=Constructions+construction+grammar+approach+to+argument+structure`
- **核实证据**：OpenLibrary API 返回 `author_name=["Adele Goldberg"]`、`first_publish_year=1995`、`publisher=["University of Chicago Press"]`、`isbn=["0226300854","9780226300856","0226300862","9780226300863"]`。OpenAlex 亦有同书条目（`type=dissertation`，无 DOI，`cited_by=6864`），摘要字段即为章节目录（1 Introduction … 8 The English Resultative Construction …）。
- **核实级别**：`L3 题录`（未读正文）
- **核心命题（据章节目录与领域通行理解，非本人核对原文）**：构式本身是独立的意义单位，动词与构式互动（"the interaction between verbs and constructions"）；构式具有"部分能产性"（partial productivity）。
- **局限**：英语本位的论元结构研究；汉语构式的适配性需另找汉语学界工作（见文末缺口）。
- **对 InkSoul 可借鉴点**：构式语法把"形式—意义配对"当作一等公民，这为"句式即文体"提供了理论支点——中文 AI 文体的可辨识性，可能就落在"把字句/被字句/兼语句/流水小句链"的构式频率分布上，而不是词表。

### C2. 「零句」和「流水句」——为赵元任先生诞辰120周年而作
- **作者**：沈家煊（中国社会科学院语言研究所）
- **年份 / 发表处**：2012 / 《中国语文》2012年第5期
- **类型**：`peer-reviewed`（CSSCI 权威期刊）
- **链接**：[CNKI 海外节点条目](https://cnki.sris.com.tw/kcms/detail/detailall.aspx?filename=YWZG201205003&dbcode=CJFQ&dbname=CJFD2012)
- **核实证据**：抓取 `filename=YWZG201205003&dbcode=CJFQ&dbname=CJFD2012` 返回：【作者】沈家煊；【机构】中國社會科學院語言研究所；【文献出处】**中國語文 / Studies of the Chinese Language，2012年05期**；【分类号】H146；【下载频次】**10587**；关键词：零句、流水句、并置性、指称性。英文题名 `On minor sentences and flowing sentences in Chinese: In commemoration of the 120th birthday of Yuen Ren Chao`。
- **核实级别**：`L2 摘要`（中英文摘要全文可取，正文未读）
- **研究问题**：赵元任"零句说"如何从根本上揭示汉语语法特点？为什么汉语多"流水句"？
- **核心论证（据摘要）**：赵元任"零句说"含三个互相联系的要点：**(一) 整句由零句组成；(二) 零句是根本；(三) 零句可以独立**。由此引申两个重要观点：**汉语的主语就是话题**；**汉语的谓语不宜按名词和动词区分类型**。零句说能解释为什么汉语多"流水句"；**对零句说理解不透彻，是流水句研究不能深入的原因**。本文在零句说基础上阐述流水句的"**并置性**"与"**指称性**"，并指出这两个特性**对语法理论中句法递归性和名动分立的普适性提出挑战**。
- **局限**：理论语言学论文，无量化语料统计；"流水句"边界仍依赖研究者判断，未给出可操作判定程序。
- **对 InkSoul 可借鉴点**：**这是中文侧最重要的一条**。它给出"中文节奏"的语言学根据：中文的叙事单位不是"主谓完整的句子"，而是**并置的零句链**。这意味着：用英文的"句子完备性/从句嵌套深度"指标去评价中文 AI 文本是**范畴错误**；中文"AI 味"更可能表现为**零句链被改写成主谓完整句**——即把并置改成连接词显性化的复句。InkSoul 完全可以把"并置性/指称性"做成可算指标（连接词密度、零句占比、指称链长度）。

### C3. 汉语有没有"主谓结构"
- **作者**：沈家煊（中国社会科学院）
- **年份 / 发表处**：2017 / 《现代外语》2017年第1期（网络出版 2017-01-14）
- **类型**：`peer-reviewed`
- **链接**：[CNKI 海外节点条目](https://cnki.sris.com.tw/kcms/detail/detailall.aspx?filename=xdwy201701001&dbcode=CJFQ&dbname=CJFD2017)
- **核实证据**：抓取 `filename=xdwy201701001&dbcode=CJFQ&dbname=CJFD2017` 返回：英文题名 `Does Chinese have the subject-predicate structure?`；【机构】中國社會科學院；【文献出处】**現代外語 / Modern Foreign Languages，2017年01期**；【分类号】H146.3；【网络出版时间】2017-01-14 19:23；【下载频次】**6634**；关键词：主谓结构、话题-说明、类包含、流水句、名实耦。
- **核实级别**：`L2 摘要`
- **研究问题**：汉语究竟有没有"主谓结构"？
- **核心论证（据摘要）**：认识经历几个阶段。前辈学者已有认识：**汉语主谓结构跟其他结构地位平等**，**不以主谓结构的有无来判定句子**，**主谓结构其实就是话题-说明结构**。作者的新认识：主谓结构就是话题-说明结构，这是汉语"**用法包含语法**"大格局所决定，符合中国哲学"体用不二"；**汉语的谓语具有指称性**，由"名词包含动词"的格局决定，符合"物事合一"；**汉语"流水句"具有指称性和并置性**；谓语是指称语在世界语言中**不是孤立现象**，以此反观英语有利于深入认识英语的谓语；"**类包含**"格局是语言的常态而非非常态，符合交谈的合作原则。进一步：汉语的话题-说明结构在形式上就是**两个指称语的并置**，是**规模最小的"流水句"**；为避免误解，建议采用"**名实耦**"这一名称。
- **局限**：同上，理论与哲学论证为主，缺可操作的计量方案。
- **对 InkSoul 可借鉴点**：把 C2 的结论推到极致——**中文最小的叙事单位就是"两个指称语并置"**。这对生成端是直接的工艺指令：中文句子不必先立主谓，可先并置两个指称性片段。若 InkSoul 要做"中文原生"的结构模板，这一条比任何英文叙事学模型都更贴近汉语实际。

### C4. "把字结构"的语义及其语用分析
- **作者**：张旺熹
- **年份 / 发表处**：1991 / 《语言教学与研究》1991年第3期
- **类型**：`peer-reviewed`
- **链接**：[CNKI 海外节点条目](https://cnki.sris.com.tw/kcms/detail/detailall.aspx?filename=YYJX199103007&dbcode=CJFQ&dbname=CJFD1991)
- **核实证据**：抓取 `filename=YYJX199103007&dbcode=CJFQ&dbname=CJFD1991` 返回：【作者】張旺熹；【文献出处】**語言教學與研究 / Language Teaching and Linguistic Studies，1991年03期**；【下载频次】**5463**；关键词：句子意义、判断句、对外汉语教学、祈使句、鲁侍萍、描写句、内在规定性、因果关系、结果性。摘要字段仅返回"<正>"开头的首段（引子），非完整摘要。
- **核实级别**：`L3 题录`（仅题录 + 开头段落；**完整论证未读到，故不引具体分类结论**）
- **可确证的内容（引子原文要点）**：对外汉语教学中"把"字句历来是难点，**这与语法教学中只重视结构形式而忽略句子的语义和语用功能有关**；作者主张在相对独立的语段中考察句与句在意义上的相互联系、依赖、制约。
- **局限**：1991 年的语料与理论框架；本篇我只核到题录级，引用应将结论限定在"该文主张把字句研究必须纳入语义-语用层面"这一点。
- **对 InkSoul 可借鉴点**：中文"把"字句不是被动语态的变体，而是**带处置/结果性语义的独立构式**。若 InkSoul 做中文文体指纹，"把字结构密度 + 结果性补语"是比"被动语态比例"更贴切的参数；同时也提示：把字句滥用是"翻译腔/AI 腔"的典型症状之一（此推论为本人判断，非该文结论）。

### C5. 《红楼梦》成书新说
- **作者**：李贤平
- **年份 / 发表处**：1987 / 《复旦学报（社会科学版）》1987年第5期
- **类型**：`peer-reviewed`
- **链接**：[CNKI 海外节点条目](https://cnki.sris.com.tw/kcms/detail/detailall.aspx?filename=FDDX198705001&dbcode=CJFQ&dbname=CJFD1987)
- **核实证据**：抓取 `filename=FDDX198705001&dbcode=CJFQ&dbname=CJFD1987` 返回：【作者】李賢平；【文献出处】**復旦學報(社會科學版) / Fudan Journal (Social Sciences Edition)，1987年05期**；【下载频次】**4073**；关键词：《红楼梦》、成书过程、曹雪芹、后四十回、甲戌本。同期刊物 `FDDX198705002` 为《序〈红楼梦〉成书新说》，可交叉印证专辑性质。
- **核实级别**：`L3 题录`（摘要仅返回首段，正文未读；该文以统计学方法讨论成书过程，**具体方法与结论本次未核实**）
- **可确证的内容**：文章从红学史切入（胡适 1921《红楼梦考证》以来的"自传说"主流地位、脂评本发现、曹家档案利用），提出对成书过程的新解释。
- **局限**：**本条只能作为"1987 年已有以计量/统计方法介入《红楼梦》成书问题的中文研究"这一事实的锚点**，不得复述其方法细节或结论。
- **对 InkSoul 可借鉴点**：中文计算文体学的本土起点——比英文 stylometry 传统更早进入"长篇白话小说的作者切分"问题；InkSoul 若做中文作者/文体辨识，这条提供了"历时切分（chrono-divide）"的本土问题意识（与 C8 的英文方法正好互补）。

### C6. Chinese Zero Pronoun Resolution with Deep Neural Networks
- **作者**：Chen Chen, Vincent Ng
- **年份 / 发表处**：2016 / ACL 2016（Proceedings of the 54th Annual Meeting of the ACL, Volume 1: Long Papers）
- **类型**：`peer-reviewed`
- **链接**：[ACL Anthology P16-1074](https://aclanthology.org/P16-1074/)
- **核实证据**：抓取 `https://aclanthology.org/events/acl-2016/` 全量目录页，HTML 中出现 `<a href=/P16-1074/>Chinese Zero Pronoun Resolution with Deep Neural Networks</a>`，作者链接 `/people/chen-chen/` 与 `/people/vincent-ng/`。
- **核实级别**：`L3 题录`（题名/作者/会议确认；**摘要未取，结论不外推**）
- **研究问题**：汉语零代词（零形回指）消解，能否用深度神经网络建模。
- **对 InkSoul 可借鉴点**：**零形回指是中文语篇连贯的核心机制**（与 C2 的"零句/并置"同源）。对生成端的含义：中文 AI 文本的"不顺"，常表现为零形回指的先行语不可恢复——即该省略的地方补了代词，或该补的地方省略了。InkSoul 可把"零形回指可解析度"作为中文连贯性指标。

### C7. A Deep Neural Network for Chinese Zero Pronoun Resolution
- **作者**：Qingyu Yin, Weinan Zhang, Yu Zhang, Ting Liu
- **年份 / 发表处**：2016 / arXiv 预印本（v3）
- **类型**：`preprint`
- **链接**：arXiv [1604.05800](https://arxiv.org/abs/1604.05800)
- **核实证据**：arXiv API 返回 `1604.05800v3`、`published 2016-04-20`、四位作者与上述一致。
- **核实级别**：`L2 摘要`
- **研究问题**：已有汉语零代词消解方法忽视语义信息（零代词无描述性信息，难以显式捕捉与先行语的语义相似性）；且候选先行语只利用单个候选的局部信息。
- **主要结论（据摘要）**：提出深度神经网络模型引入语义信息，并在候选先行语选择上考虑**全局信息**（而非仅单候选局部信息），以改善消解。
- **局限**：摘要未读到具体指标数字，**不引用 F1**。
- **对 InkSoul 可借鉴点**：证明"零形回指的先行语选择是一个全局决策"——写作时省略什么，取决于整段的话题结构，不是局部语法。这为"中文长段落的连贯性要按语篇级建模"提供了方法学支持。

### C8. Multiple Authors Detection: A Quantitative Analysis of Dream of the Red Chamber
- **作者**：Xianfeng Hu, Yang Wang, Qiang Wu
- **年份 / 发表处**：2014 / arXiv 预印本
- **类型**：`preprint`
- **链接**：arXiv [1412.6211](https://arxiv.org/abs/1412.6211)
- **核实证据**：arXiv API 返回 `1412.6211v1`、`published 2014-12-19`、三位作者与上述一致。
- **核实级别**：`L2 摘要`
- **研究问题**：能否用严格方法检验《红楼梦》写作风格中的"**chrono-divide（历时断裂）**"，从而判定作者？
- **数据方法**：支持向量机等作者归属技术；提出以**相对频率**作为特征排序度量；在程高本《红楼梦》上检验。
- **主要结论**：给出"**convincing if not irrefutable**"的证据：**前 80 回与后 40 回由两位不同作者所写**；另意外地为"**第 67 回亦非曹雪芹所作**"的假说提供了强支持；对另外三部中国古典小说做对照，**未发现 chrono-divide**，反过来印证方法稳健。
- **局限**：预印本，未见同行评议版本；特征（虚词相对频率）对题材变化敏感；"第 67 回"结论属假说级支持。
- **对 InkSoul 可借鉴点**：**中文文体计量的可复现基线**——虚词相对频率 + SVM 就能切出作者边界。InkSoul 若做"同一作者不同作品/不同 AI 模型的文体指纹"，这是最省成本的起点；且"对照组无 chrono-divide"的设计值得照搬（阴性对照是这类研究的成败关键）。

### C9. Benchmarking the Detection of LLMs-Generated Modern Chinese Poetry
- **作者**：Shanshan Wang, Junchao Wu, Fengying Ye, Jingming Yao, Lidia S. Chao, Derek F. Wong
- **年份 / 发表处**：2025 / arXiv 预印本
- **类型**：`preprint`
- **链接**：arXiv [2509.01620](https://arxiv.org/abs/2509.01620)
- **核实证据**：arXiv API 返回 `2509.01620v1`、`published 2025-09-01`、六位作者与上述一致。
- **核实级别**：`L2 摘要`
- **研究问题**：中文现代诗的 AI 生成检测，现有检测器够用吗？哪些诗歌特征最难判？
- **数据方法**：构建数据集——**6 位专业诗人的 800 首诗** vs **4 个主流 LLM 生成的 41,600 首**；对 **6 个检测器**做系统评测。
- **主要结论**：**现有检测器不能作为可靠工具**来检测 LLM 生成的中文现代诗；**最难检测的诗歌特征是"内在品质"，尤其是风格（style）**。
- **局限**：仅诗歌；检测器集合有限；预印本。
- **对 InkSoul 可借鉴点**：给出了一个反直觉的量化事实——**"风格"是 AIGC 检测的最后一道防线，也是最先失守的一道**。对 InkSoul 的含义是：靠"检测器打不过"来论证"写得好"是站不住的；反过来，若 InkSoul 的目标是"风格可辨识"，那么风格正是当前检测器与人类都最难把握的维度，也是最值得投入的维度。

### C10. Creative Convergence or Imitation? Genre-Specific Homogeneity in LLM-Generated Chinese Literature
- **作者**：Yuanchi Ma, Kaize Shi, Hui He, Zhihua Zhang, Zhongxiang Lei, Ziliang Qiu
- **年份 / 发表处**：2026 / arXiv 预印本
- **类型**：`preprint`
- **链接**：arXiv [2603.14430](https://arxiv.org/abs/2603.14430)
- **核实证据**：arXiv API 返回 `2603.14430v1`、`published 2026-03-15`、六位作者与上述一致。
- **核实级别**：`L2 摘要`
- **研究问题**：中文网络文学语境下，LLM 生成故事的"结构同质化"具体表现为哪种叙事逻辑？
- **数据方法**：引入 **Propp 民间故事形态学 + 叙事功能（narrative functions）**，针对现代网文结构**扩展定义 34 个叙事功能**；自建人工标注语料库。
- **主要结论**：生成文本"叙事逻辑单一、同质化严重"的主因是——**当前 LLM 无法正确理解叙事功能的含义，转而固守刻板的生成范式**。
- **局限**：单一语言/单一文类（中文网文）；34 功能体系为本文自定；预印本。
- **对 InkSoul 可借鉴点**：**这条把"结构同质化"从现象推进到机制**：不是模型不会写，而是模型把"叙事功能"当成表面模板在套。InkSoul 若做结构控制，关键不是给模板，而是让模型"理解功能在当前语境中的作用"——这与 A8 的"显式注入话语特征可提升"互为补充（一个说注入有效，一个说模板化无效，区别在于是否语义化）。

### C11. BiT-MCTS: A Theme-based Bidirectional MCTS Approach to Chinese Fiction Generation
- **作者**：Zhaoyi Li, Xu Zhang, Xiaojun Wan
- **年份 / 发表处**：2026 / arXiv 预印本（v3）
- **类型**：`preprint`
- **链接**：arXiv [2603.14410](https://arxiv.org/abs/2603.14410)
- **核实证据**：arXiv API 返回 `2603.14410v3`、`published 2026-03-15`、三位作者与上述一致。
- **核实级别**：`L2 摘要`
- **研究问题**：从开放主题生成**长篇线性小说**时，LLM 难以保证全局结构与叙事多样性，怎么办？
- **数据方法**：主题驱动框架，操作化"**climax-first, bidirectional expansion（先定高潮，双向扩展）**"策略，动机来自 **Freytag 金字塔**；给定主题后先抽取核心戏剧冲突、生成显式高潮，再做双向展开，并用 MCTS 搜索。
- **主要结论（据摘要）**：针对 premise-based / 线性大纲方法的全局结构与多样性缺陷提出该框架（摘要未给指标数字，**不引用具体提升幅度**）。
- **局限**：中文小说；计算开销（MCTS）；预印本。
- **对 InkSoul 可借鉴点**：**"先定高潮再双向展开"是对中文长篇最实用的结构工程**——它把"节奏"变成一个可搜索的规划问题（而非解码期的祈祷）。与 A9 的"悬念=前向不确定性"可以拼成一条完整链路：用 MCTS 规划"何时释放信息"，用不确定性度量验收。

---

## 检索缺口

1. **中文期刊站可达性**：知网大陆站（`kns.cnki.net`/`read.cnki.net`/`wap.cnki.net`）、万方、维普、期刊界、国家哲学社会科学文献中心在本机**全部不可达**（curl 返回 000）。可用的只有 CNKI 海外节点 `cnki.sris.com.tw`，但其**无可用检索接口**，只能按 `filename=<刊名码><年><期><序号>` 逐个枚举。因此中文条目只覆盖我逐一枚举命中的 4 篇（C2–C5），无法做主题式普查。
2. **1980s 中文文献未数字化到海外节点**：《中国语文》1987 年各期在该节点返回空页，故**陈平《汉语零形回指的话语分析》（《中国语文》1987年第5期）未能核实，暂不采用**——这条对"零形回指"主题是最重要的中文原始文献，建议后续在有知网权限的环境补核。
3. **汉语话题链（topic chain）专著未核实**：曹逢甫（Tsao Feng-fu）相关英文专著、许余龙的话题链研究，本次未取得可核实的 API/出版社记录，**暂不采用**。
4. **汉语构式语法的中文学界工作**：陆俭明、Goldberg 理论在汉语学界的发展（如"构式—语块"教学法）未能核实到具体期刊年卷期，**暂不采用**；C1 仅覆盖 Goldberg 原著。
5. **中文计算文体学（中文作者身份识别、中文风格计量）的期刊/会议论文**：中文信息学报、语言文字应用、当代修辞学在本机不可达，未取得任何可核实条目。C 段的中文计算侧因此**只有英文 arXiv/ACL 论文**，缺中文学界对应工作，这是本节最大的结构性缺口。
6. **中文 AIGC 检测除诗歌外的文类**：只有 C9（现代诗）。小说/散文的中文 AIGC 检测基准（含 TH-Bench 类工作）本次未检索到可核实记录。
7. **自由间接引语（FID）的计算研究**：arXiv 检索 `all:"free indirect discourse"` **返回零命中**，未能找到可核实条目；视角侧只能引 A10（focalization）。
8. **事件切分（event segmentation）**：Zacks & Swallow (2007, *Current Directions in Psychological Science*) 与 Wilensky (1983, *Behavioral and Brain Sciences*, "Story grammars versus story points") 两条均**未取得可核实的 API 记录**（OpenAlex 当日配额耗尽 429、Crossref 429、Cambridge Core 搜索 429），**暂不采用**，留待补核。A 段的"事件级"内容目前由 A3（三阶段结构）与 A8（转折点）间接承担。
9. **B 段的方法类文献只覆盖解码期控制**：训练侧（DPO/RLHF 对文体的影响）只有 A6 间接涉及；对比学习/偏好优化的文体效应缺独立条目。
10. **配额说明**：OpenAlex 免费日额度在本次检索中途耗尽（HTTP 429），Crossref 全程 429，Google Books API 配额耗尽；因此多条候选（尤其图书与中文期刊）只到题录级或被迫放弃。所有 `L1 全文`档为 0 条——**本文件没有任何一条是读完全文写的**，A/B/C 各条结论均严格限定在 API 返回的摘要与题录范围内。
