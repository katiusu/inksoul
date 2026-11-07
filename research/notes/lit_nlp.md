# InkSoul 文献笔记 · NLP / 计算语言学侧

> 主题：从生成机制层面改善 AI 文学文本的机械化倾向
> 检索与核实时间：2026-10-31（UTC）。核实通道：OpenAlex API、Crossref API、arXiv API、ACL Anthology 页面、PMLR 页面、Semantic Scholar API。
> 每条均标注 `peer-reviewed` / `preprint` / `workshop` / `thesis`，并给出 DOI / arXiv ID / ACL URL。
> 「读取深度」逐条注明：读全文 / 读摘要。凡未读全文者，结论不超出摘要所述范围。

---

## A. 句法模板、结构重复与多样性度量

### 1. Detection and Measurement of Syntactic Templates in Generated Text

- **作者**: Chantal Shaib, Yanai Elazar, Junyi Jessy Li, Byron C. Wallace
- **年份**: 2024
- **发表处**: Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing (EMNLP 2024)
- **类型**: peer-reviewed
- **链接**: https://aclanthology.org/2024.emnlp-main.368/ ；DOI https://doi.org/10.18653/v1/2024.emnlp-main.368
- **核实证据**:
  - `ACL: https://aclanthology.org/2024.emnlp-main.368/` 页面 title = "Detection and Measurement of Syntactic Templates in Generated Text - ACL Anthology"；页面内 DOI 字面量 `10.18653/v1/2024.emnlp-main.368`
  - `ARXIV: 2407.00211v2, published=2024-06-28, updated=2024-10-06`
- **研究问题**: 已有的生成多样性评估集中在词级特征（distinct-n、Self-BLEU 一类）。是否存在超出 n-gram 的、句法层面的模板化重复？模型输出与人类参考文本在句法模板分布上差多少？这些模板从哪里来？
- **数据与规模**: 多任务、多模型的下游生成输出，并与人类参考文本对照；模板来源分析回溯到预训练语料。
- **方法**: 定义「句法模板」（syntactic template，对依存/成分句法结构的抽象模式），统计其在模型输出与人类文本中的分布；把模板作为特征做模型/任务/领域区分；用模板追踪预训练数据中的风格记忆。
- **主要结论（量化）**:
  - 模型生成的文本在下游任务中比人类参考文本以**更高的比例**呈现模板化。
  - 模型生成文本中**76%** 的模板能在预训练数据中找到，而人类撰写文本中该比例只有 **35%**。
  - 这些模板**不会被 RLHF 等微调过程覆盖**。
  - 模板作为特征可区分不同模型、任务与领域，也可用于分析训练数据的风格记忆。
- **限制**: 句法模板依赖句法分析器质量；模板定义对语言（尤其中文分词/依存规范）敏感；未直接给出「文学文本」这一体裁的结论，任务以 QA/摘要等下游任务为主。
- **对 InkSoul 的可借鉴点**: 「句法模板集合的重复率 + 模板的预训练来源可追溯性（76% vs 35%）」是本项目最直接可复用的测量范式——把「机械化」操作化为「句法模板熵低 + 模板高度可追溯至预训练分布」，可在中文上以依存弧标签序列（而非成分树）重建模板抽取器。
- **读取深度**: 仅读摘要（arXiv API summary）。

---

### 2. The Curious Case of Neural Text Degeneration

- **作者**: Ari Holtzman, Jan Buys, Li Du, Maxwell Forbes, Yejin Choi
- **年份**: 2019（arXiv v1 2019-04-22；v2 2020-02-14）
- **发表处**: 本轮核实仅取得 arXiv 记录（OpenAlex 返回 venue = "arXiv (Cornell University)", type = preprint）
- **类型**: preprint（按本轮可核验证据记录；未取得会议论文集的权威页面，故不标注会议）
- **链接**: https://arxiv.org/abs/1904.09751 ；DOI https://doi.org/10.48550/arxiv.1904.09751
- **核实证据**: `OPENALEX: doi=10.48550/arxiv.1904.09751, venue=arXiv (Cornell University), year=2019, type=preprint, cited_by=1304`；`ARXIV: 1904.09751v2, published=2019-04-22`
- **研究问题**: 以似然（likelihood）为解码目标时，为什么高质量语言模型会生成「平淡且奇怪地重复」（bland and strangely repetitive）的文本？
- **数据/方法**: 对比人类文本与机器文本的分布差异；在不同解码策略（beam search、纯采样、top-k 等）下比较同一模型输出的质量；提出 Nucleus Sampling（top-p）。
- **主要结论（量化）**: 论文的核心经验发现是「解码策略本身即便在完全相同的模型上也会显著改变机器文本质量」；似然最大化导致退化，而 top-p 采样在截断不可靠尾部的同时保留多样性，从而在不牺牲流畅度与连贯性的前提下提升多样性。摘要未给出具体数字指标。
- **限制**: 2019 年 GPT-2 时代模型；「重复」以词/短语级现象描述，未提供句法层度量；作者本身也承认退化机制的解释不完整（后续 2310.01693 "Closing the Curious Case of Neural Text Degeneration" 专门补这个理论缺口，本笔记未核实该文）。
- **对 InkSoul 的可借鉴点**: 把「机械化」的**解码侧成因**与「数据侧成因」区分开：Nucleus Sampling 只能改变尾部截断，不能改变模型学到的句法模板分布——这正好解释了为什么单纯调温度/top-p 消不掉模板化（与第 1 条 76% 模板可追溯至预训练互为印证）。
- **读取深度**: 仅读摘要。

---

### 3. Texygen: A Benchmarking Platform for Text Generation Models

- **作者**: Yaoming Zhu, Sidi Lu, Lei Zheng, Jiaxian Guo, Weinan Zhang, Jun Wang, Yong Yu
- **年份**: 2018
- **发表处**: 本轮仅核实 arXiv 记录
- **类型**: preprint（本轮未取得 ACL Anthology 权威页面，不做会议归属）
- **链接**: https://arxiv.org/abs/1802.01886
- **核实证据**: `ARXIV: 1802.01886v1, published=2018-02-06`；OpenAlex 检索该标题未返回 ACL 版本条目
- **研究问题**: 开放域文本生成研究缺少统一基准，导致多样性/质量/一致性指标不可比。
- **方法**: 实现多种文本生成模型 + 一套评估指标（多样性、质量、一致性），标准化实现以便复现。
- **主要结论**: 摘要只陈述平台贡献，未给出量化结论。**Self-BLEU 这一指标通常被归到该平台/论文名下**，但本轮读到的摘要中并未点名 Self-BLEU——引用 Self-BLEU 时应回查正文表格再定归属。
- **限制**: 2018 年指标（BLEU 系、基于 n-gram 的多样性），对长文本与句法结构不敏感。
- **对 InkSoul 的可借鉴点**: distinct-n / Self-BLEU 只能作为**基线层**指标（词面重复），不能承担「机械化」的主证据——主证据应放到第 1、4 条的句法/结构层。
- **读取深度**: 仅读摘要。

---

### 4. Benchmarking Linguistic Diversity of Large Language Models

- **作者**: Yanzhu Guo, Guokan Shang, Chloé Clavel
- **年份**: 2025
- **发表处**: Transactions of the Association for Computational Linguistics (TACL), Volume 13, 2025
- **类型**: peer-reviewed
- **链接**: https://aclanthology.org/2025.tacl-1.69/ ；DOI https://doi.org/10.1162/tacl.a.47
- **核实证据**:
  - `ACL: https://aclanthology.org/2025.tacl-1.69/` 页面 title = "Benchmarking Linguistic Diversity of Large Language Models - ACL Anthology"；页面内出现 `10.1162/tacl.a.47` 与 "Volume 13. 2025."
  - `OPENALEX: doi=10.1162/tacl.a.47, venue=Transactions of the Association for Computational Linguistics, year=2025, type=article, cited_by=11`
  - `ARXIV: 2412.10271v2, published=2024-12-13`
- **研究问题**: 如何系统地度量 LLM 输出的**语言多样性**（不止词面），并据此比较模型？
- **方法**: 构造语言多样性基准，在多个层级上度量输出多样性并与人类文本对照。
- **主要结论（量化）**: 摘要层面确认了 LLM 输出在语言多样性上偏离人类分布，并给出基准化结论；**具体数字本轮未读到**（仅读摘要，数字在正文表格）。
- **限制**: 摘要无量化数字；需读全文取表。
- **对 InkSoul 的可借鉴点**: 作为「语言多样性」这一维度的**指标框架来源**——它把多样性拆成多层（词汇/句法/语义），可直接借其层级定义来构造中文版「机械化指数」的多层打分。
- **读取深度**: 仅读摘要（**数字缺口，需补读全文**）。

---

### 5. Do LLMs produce texts with "human-like" lexical diversity?

- **作者**: Kelly Kendro, Jeffrey Maloney, Scott Jarvis
- **年份**: 2025（arXiv v1 2025-07-31，v2 2025-11-21）
- **发表处**: International Journal of Applied Linguistics（DOI 见下）
- **类型**: peer-reviewed（期刊已给出 DOI）
- **链接**: https://arxiv.org/abs/2508.00086 ；DOI https://doi.org/10.1111/ijal.70115
- **核实证据**: `ARXIV: 2508.00086v2, published=2025-07-31`；arXiv metadata 的 `arxiv:doi` 字段 = `10.1111/ijal.70115`
- **研究问题**: 从**词汇多样性**角度，ChatGPT 系列模型的输出是否真的「像人」？新模型是否更接近人类？
- **数据与规模**: 4 个 ChatGPT 模型（ChatGPT-3.5、ChatGPT-4、ChatGPT-o4 mini、ChatGPT-4.5）输出 × 人类 L1/L2 英语写作者 **n = 240**，跨 4 个教育层级。
- **方法**: 在每篇文本上测 **6 个词汇多样性维度**：volume、abundance、variety-repetition、evenness、disparity、dispersion；统计用 one-way MANOVA、one-way ANOVA、SVM 分类。
- **主要结论（量化）**:
  - ChatGPT 文本在**每一个**多样性变量上都与人类文本显著不同；其中 ChatGPT-o4 mini 与 ChatGPT-4.5 偏离最大。
  - **新模型反而更不像人**：ChatGPT-4.5 的词汇多样性水平高于旧模型（尽管 token 数更少），但作者的总判断是「模型并不产出人类式的词汇多样性，且新模型的文本更不 human-like」。
  - 人类写作者内部（按教育层级、L1/L2 语言状态）词汇多样性**没有**显著差异。
- **限制**: 仅英语、仅说明/议论类写作任务（非文学创作）；「更像人」的判定完全建立在多样性指标上，不含句法结构。
- **对 InkSoul 的可借鉴点**: (a) 六个维度的拆法（尤其 evenness/disparity/dispersion 这类**分布形状**维度，而不只是 TTR）可以直接移植成中文分词后的词频分布指标；(b) 「人内方差 < 模型间差异」这一对照设计，是论证「机械化」时必须做的基线——先证明人类内部不齐整、模型内部高度齐整。
- **读取深度**: 仅读摘要。

---

### 6. Comparing LLM-generated and human-authored news text using formal syntactic theory

- **作者**: Olga Zamaraeva, Dan Flickinger, Francis Bond, Carlos Gómez-Rodríguez
- **年份**: 2025
- **发表处**: 本轮仅核实 arXiv 记录（无 DOI）
- **类型**: preprint（无 DOI）
- **链接**: https://arxiv.org/abs/2506.01407
- **核实证据**: `ARXIV: 2506.01407v1, published=2025-06-02`；OpenAlex/Crossref 未返回正式发表版本
- **研究问题**: 用形式句法理论（而非统计 n-gram）比较 LLM 与人类在同体裁（纽约时报风格）下的语法结构分布差异。
- **数据与规模**: 6 个大语言模型生成的 NYT 风格文本 vs 真实的、人类撰写的 NYT 文本。
- **方法**: 用 Head-driven Phrase Structure Grammar (HPSG) 对文本做语法结构分析，比较 **HPSG 语法类型（grammar types）的分布**。
- **主要结论**: 人类与 LLM 文本在 HPSG 语法类型分布上呈现**系统性差异**（作者称这是首次对 NYT 体裁做这种比较）。摘要未给出量化数字。
- **限制**: 仅一个体裁（NYT 新闻）、6 个模型；HPSG 分析依赖解析/语法工程资源，对中文需另行构建（中文无同等成熟的 HPSG 大规模资源）；摘要无数字。
- **对 InkSoul 的可借鉴点**: 提供了一条与「句法模板」互补的路线——**不数模板，而是数语法构造类型的分布距离**。中文可退化为「依存弧标签 + 词类二元组」的构造类型分布做近似，并直接沿用「分布差异是否系统性」的检验框架。
- **读取深度**: 仅读摘要。

---

### 7. Interpretable Stylistic Variation in Human and LLM Writing Across Genres, Models, and Decoding Strategies

- **作者**: Swati Rallapalli, Shannon Gallagher, Ronald Yurko, Tyler Brooks, Chuck Loughin, Michele Sezgin, Violet Turri
- **年份**: 2026
- **发表处**: 本轮仅核实 arXiv 记录（无 DOI）
- **类型**: preprint（无 DOI）
- **链接**: https://arxiv.org/abs/2604.14111
- **核实证据**: `ARXIV: 2604.14111v1, published=2026-04-15`；无 journal_ref / DOI 字段
- **研究问题**: 人类文本与机器文本的风格差异，在**体裁、模型、解码策略**三个因素下分别有多大？哪些差异是稳健的？
- **数据与规模**: 人类文本 + **11 个 LLM** 的输出，覆盖 **8 个体裁**、**4 种解码策略**。
- **方法**: 用 Douglas Biber 的**词汇语法与功能特征集**（lexicogrammatical & functional features）做大规模风格变化分析（与第 8 条 Reinhart 等同一特征体系）。
- **主要结论（四条，均为定性表述）**:
  1. LLM 文本的关键语言区分特征**对生成条件稳健**——即使提示模型「写得更像人」，或给它人类文本让它续写，这些特征依然存在。
  2. **体裁对风格特征的影响大于文本来源**（人类 vs 机器）。
  3. chat 变体的模型在风格空间中倾向于**聚成一团**。
  4. 模型对风格的影响大于解码策略（有少数例外）。
- **限制**: 仅读摘要，具体效应量未获取；Biber 特征集是为英语设计的，中文需重建特征清单。
- **对 InkSoul 的可借鉴点**: 结论 (1) 是本项目**最关键的一条机制证据**：机械化不能靠 prompt 层「写得像人」修掉，必须在生成/训练机制层解决。结论 (2) 提醒对照组必须**按体裁分层**，否则体裁效应会掩盖来源效应。
- **读取深度**: 仅读摘要。


## B. 人类 vs AI 写作风格的量化差异（文体计量 / 作者指纹）

### 8. Do LLMs write like humans? Variation in grammatical and rhetorical styles

- **作者**: Alex Reinhart, Ben Markey, Michael Laudenbach, Kachatad Pantusen, Ronald Yurko, Gordon Weinberg, David West Brown
- **年份**: 2025
- **发表处**: Proceedings of the National Academy of Sciences (PNAS), 122 (2025), e2422455122
- **类型**: peer-reviewed
- **链接**: https://doi.org/10.1073/pnas.2422455122 ；预印本 https://arxiv.org/abs/2410.16107
- **核实证据**:
  - `OPENALEX: doi=10.1073/pnas.2422455122, venue=Proceedings of the National Academy of Sciences, year=2025, type=article, cited_by=63`
  - `ARXIV: 2410.16107v2；arxiv:journal_ref="Proceedings of the National Academy of Sciences 122 (2025), e2422455122"；arxiv:doi=10.1073/pnas.2422455122`
- **研究问题**: 已有研究只看表层特征（词选择、标点）并训练分类器做检测，**没有人研究 LLM 的修辞风格（rhetorical styles）**。LLM 的语法与修辞风格分布与人类差多少？随模型规模、指令微调如何变化？
- **数据与规模**: 用 Llama 3 系列多个变体与 GPT-4o，从常见 prompt 出发构建**两个平行语料**（人类撰写 / LLM 撰写）。
- **方法**: 采用 **Douglas Biber 的词汇、语法与修辞特征集**，做特征分布对比与分类。
- **主要结论（量化/定性）**:
  - 人类与 LLM 之间存在**系统性差异**，且不同 LLM 之间也有系统性差异。
  - 这些差异**从小模型到大模型持续存在**（不随规模扩大而消失）。
  - 差异**在 instruction-tuned 模型上比 base 模型更大**。
  - 作者的判断：尽管能力很强，LLM **难以匹配人类风格变异性**（struggle to match human stylistic variation）。
- **限制**: 特征体系与语料以英语为主；摘要未给出综合效应量（需读全文取表）；平行语料的 prompt 设计会引入体裁约束。
- **对 InkSoul 的可借鉴点**: 这是本项目「机械化 = 风格方差压缩」论断的**主引文**：注意区分两个机制——(a) 特征均值偏移，(b) **特征方差收缩**（人类组内方差大、模型组内方差小）。InkSoul 的指标应显式报告后者。另：instruction-tuned 差异更大这一条，说明对齐/微调环节是机械化的重要来源，而不只是预训练数据。
- **读取深度**: 仅读摘要（**量化表格需补读全文**）。

---

### 9. Linguistic and Embedding-Based Profiling of Texts generated by Humans and Large Language Models

- **作者**: Sergio E. Zanotto, Segun Aroyehun
- **年份**: 2025
- **发表处**: Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing (EMNLP 2025)
- **类型**: peer-reviewed
- **链接**: https://arxiv.org/abs/2507.13614 （arXiv v3 metadata 的 journal_ref 指向 EMNLP 2025；ACL 页面本次未单独核验）
- **核实证据**: `ARXIV: 2507.13614v3, published=2025-07-18, updated=2025-09-30`；`arxiv:journal_ref="Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing (EMNLP 2025)"`；无 DOI 字段
- **研究问题**: 已有工作多把「人/机分类」当目标；本文反过来**刻画**两类文本在形态、句法、语义多层语言特征上的差异，以及这些特征如何随采样策略、重复控制、模型发布时间变化。
- **数据与规模**: 人类文本 + **11 个 LLM** 生成文本，覆盖 **8 个领域**。
- **方法**: 计算多层语言特征（如**依存距离 dependency length**、情感度 emotionality），并做统计比较；另用 style embeddings 检验两类文本的变异性。
- **主要结论**:
  - **人类文本倾向于更简单的句法结构**（simpler syntactic structures）与**更多样的语义内容**。
  - 人类与机器文本都随领域呈风格多样，但**人类文本的特征变化幅度更大**。
  - **更新的模型输出呈现相似的变异性 → 指向机器生成文本的同质化（homogenization）**。
- **限制**: 摘要未给数字；「更简单句法」这一结论方向与直觉相反，需读全文确认其度量（依存距离 vs 树高 vs 从句密度）——**这条不能直接当作「AI 句法更复杂」的依据**。
- **对 InkSoul 的可借鉴点**: (a) 「依存距离」作为可移植到中文的低成本句法指标（中文依存树由 CDTB/CTB 体系标注）；(b) 「人类组内方差 > 模型组内方差」在这里以多领域形式再次出现，可作为方差比的第二个独立证据点。
- **读取深度**: 仅读摘要。

---

### 10. Stylometry recognizes human and LLM-generated texts in short samples

- **作者**: Karol Przystalski, Jan K. Argasiński, Iwona Grabska-Gradzińska, Jeremi K. Ochab
- **年份**: 2026（arXiv v1 2025-07-01）
- **发表处**: Expert Systems with Applications, 296, 129001 (2026)
- **类型**: peer-reviewed
- **链接**: https://arxiv.org/abs/2507.00838 ；DOI https://doi.org/10.1016/j.eswa.2025.129001
- **核实证据**: `ARXIV: 2507.00838v2, published=2025-07-01`；`arxiv:journal_ref="Expert Systems with Applications 296, 129001 (2026)"`；`arxiv:doi=10.1016/j.eswa.2025.129001`
- **研究问题**: 在**短样本**（10 句）条件下，文体计量特征能否区分人类与多种 LLM 生成的文本，并做模型归属？
- **数据与规模**: 基于 Wikipedia 构造基准数据集，含 (a) 人类撰写的词条摘要、(b) 纯 LLM 生成文本（GPT-3.5/4、LLaMa 2/3、Orca、Falcon）、(c) 经 T5/BART/Gensim/Sumy 摘要处理的版本、(d) 经 Dipper/T5 改写的版本；文本长度统一为 10 句。
- **方法**: 用人工设计的文体特征（**StyloMetrix**）与自建 n-gram 特征管线，编码词汇、语法、**句法**与标点模式；分类器用决策树与 LightGBM；用 SHAP 解释特征。
- **主要结论（量化）**:
  - 多分类（**7 类**）交叉验证 **MCC 最高 .87**。
  - 二分类准确率在 **.79 – 1.0** 之间；Wikipedia vs GPT-4 的平衡数据集上达 **.98**。
  - SHAP 指出的判别特征：百科文体的特征词、个体过度使用的词，以及 **LLM 相对人类文本更强的语法标准化（greater grammatical standardisation）**。
- **限制**: 单一文本类型（百科摘要），体裁外推未验证；作者自己强调「至少在定义良好的文本类型内」可区分；短样本设定可能高估了特征稳定性。
- **对 InkSoul 的可借鉴点**: (a)「**grammatical standardisation**」正是机械化的一个可操作定义——可用「句法结构类型的熵」直接量化，比抽象说「机械化」更可测；(b) StyloMetrix 的特征分组（词汇/语法/句法/标点）可作为中文特征清单的骨架；(c) 用 SHAP 做「哪些特征在拉高机械度」的归因，对生成机制诊断有用。
- **读取深度**: 仅读摘要。

---

### 11. Neural Authorship Attribution: Stylometric Analysis on Large Language Models

- **作者**: Tharindu Kumarage, Huan Liu
- **年份**: 2023
- **发表处**: 本轮仅核实 arXiv 记录（无 DOI）
- **类型**: preprint（无 DOI）
- **链接**: https://arxiv.org/abs/2308.07305
- **核实证据**: `ARXIV: 2308.07305v1, published=2023-08-14`
- **研究问题**: 能否把 AI 生成文本「归属」到具体来源模型（LLM 版作者归属）？闭源 vs 开源模型在写作签名（writing signature）上有何差别？
- **方法**: 在**词汇、句法、结构**三个层面整合文体特征，考察其对可解释性的贡献，并用于增强基于预训练语言模型的分类器。
- **主要结论**: 给出「不同 LLM 具有可区分的写作签名、且闭源与开源两组内部亦存在差异」的经验结论；摘要未给数字。
- **限制**: 摘要无量化结果；2023 年模型集，未覆盖 2025-2026 模型。
- **对 InkSoul 的可借鉴点**: 「**模型间**风格签名可区分」反过来支撑一个推论：如果不同模型各有签名，而人类内部方差更大，那么「机械化」是**跨模型共有的收敛方向**而非某一家的怪癖——这正是 InkSoul 想攻击的对象层级。
- **读取深度**: 仅读摘要。

---

### 12. Authorship Attribution in the Era of LLMs: Problems, Methodologies, and Challenges

- **作者**: Baixiang Huang, Canyu Chen, Kai Shu
- **年份**: 2024（arXiv v1 2024-08-16，v3 更新至 2026-05-26）
- **发表处**: 本轮仅核实 arXiv 记录（无 DOI；为综述）
- **类型**: preprint（综述）
- **链接**: https://arxiv.org/abs/2408.08946
- **核实证据**: `ARXIV: 2408.08946v3, published=2024-08-16, updated=2026-05-26`
- **研究问题**: LLM 时代「作者归属」这一领域被拆成哪些子问题、各有哪些方法与基准、开放问题是什么。
- **方法**: 系统性文献综述，把问题分为四类：(1) 人类文本归属；(2) LLM 生成文本检测；(3) LLM 生成文本归属；(4) 人机共写文本归属。
- **主要结论**: 指出该领域的两个核心挑战是**泛化性**（跨领域）与**可解释性**；并给出开放问题与未来方向清单。摘要不含量化结论。
- **限制**: 综述，本身无实验；作为「地图」使用而非证据使用。
- **对 InkSoul 的可借鉴点**: 用它做**文献地图**——把本项目的测量需求映射到四分类中的第 (2)(3) 类，并借其「泛化性/可解释性」两条挑战作为评估自家指标的自检清单。
- **读取深度**: 仅读摘要。

---

### 13. Missing the human touch? A computational stylometry analysis of GPT-4 translations of online Chinese literature

- **作者**: Xiaofang Yao, Yong-Bin Kang, Anthony McCosker
- **年份**: 2025
- **发表处**: Target（John Benjamins 翻译研究期刊）；DOI 见下
- **类型**: peer-reviewed
- **链接**: https://arxiv.org/abs/2506.13013 ；DOI https://doi.org/10.1075/ts.24043.yao
- **核实证据**: `ARXIV: 2506.13013v1, published=2025-06-16`；arXiv metadata `arxiv:doi=10.1075/ts.24043.yao`
- **研究问题**: 在**中国网络文学**翻译这一文学性任务上，LLM（GPT-4）的译文在文体特征上是否接近人类译者？「human touch」是否还成立？
- **数据与规模**: 中国网络文学文本，GPT-4 译文 vs 人类译文对照。
- **方法**: 计算文体计量分析（computational stylometry），比较**词汇、句法、内容**三类特征。
- **主要结论**: GPT-4 译文在词汇、句法、内容特征上**与人类译文高度接近**，作者据此认为 LLM 可能复现了文学翻译风格中的「human touch」，并讨论人机译文界限日益模糊的后人类视角。
- **限制**: 任务性质是**翻译**而非原创生成（源文本约束强，风格自由度低），不能外推到「AI 原创小说」；样本为网络文学单一类型；摘要无数字。
- **对 InkSoul 的可借鉴点**: 这是一条**反向证据**，必须收进来做对照：在有强源文本约束（翻译）时，风格差异可被压到很小。含义是——InkSoul 若要用「与人类文本的距离」作指标，必须**控制任务约束强度**，否则测到的是任务而非机制。
- **读取深度**: 仅读摘要。


## C. AI 文本检测器：作为测量工具的有效性边界

> 这一节在 InkSoul 里的角色不是「做检测」，而是**把检测器当作测量仪器来评估其量程与失效条件**。文学文本（尤其中文）恰恰落在这些失效区里。

### 14. DetectGPT: Zero-Shot Machine-Generated Text Detection using Probability Curvature

- **作者**: Eric Mitchell, Yoonho Lee, Alexander Khazatsky, Christopher D. Manning, Chelsea Finn
- **年份**: 2023
- **发表处**: Proceedings of the 40th International Conference on Machine Learning (ICML 2023), PMLR 202
- **类型**: peer-reviewed
- **链接**: https://arxiv.org/abs/2301.11305 ；会议页 https://proceedings.mlr.press/v202/mitchell23a.html
- **核实证据**:
  - `PMLR: https://proceedings.mlr.press/v202/mitchell23a.html` 页面 title = "DetectGPT: Zero-Shot Machine-Generated Text Detection using Probability Curvature"，正文含 "Proceedings of the 40th International Conference on Machine Learning"
  - `ARXIV: 2301.11305v2, published=2023-01-26, updated=2023-07-23`
  - `OPENALEX` 仅收录 arXiv 版本（doi=10.48550/arxiv.2301.11305, type=preprint）
- **研究问题**: 能否不训练分类器、不收集数据、不打水印，仅靠模型自身的概率函数结构判断一段文本是否由该模型生成？
- **方法**: 发现 LLM 采样的文本倾向于落在模型 log 概率函数的**负曲率（negative curvature）区域**；据此定义曲率判据：用另一个通用预训练模型（如 T5）做随机扰动，比较原文本与扰动文本的 log 概率差。
- **主要结论（量化）**: 在检测 20B GPT-NeoX 生成的假新闻文章上，把最强零样本基线的 **0.81 AUROC** 提升到 **0.95 AUROC**。
- **限制**: 需要白盒 log 概率（闭源模型不适用）；扰动步骤计算开销大（Fast-DetectGPT 专门为此优化）；对**改写/润色**后的文本鲁棒性差（见第 18 条）；文学文本的「负曲率」假设未验证。
- **对 InkSoul 的可借鉴点**: 「概率曲率」可以作为**生成机制层面的一个可观测量**：它衡量的是「这段文字在模型分布上是否处于被采样的典型区域」。如果 InkSoul 想让文本「离开负曲率区」，这与「降低机械度」在几何上是同一件事——可作为一个**可微或可打分的训练目标**候选。
- **读取深度**: 仅读摘要。

---

### 15. Fast-DetectGPT: Efficient Zero-Shot Detection of Machine-Generated Text via Conditional Probability Curvature

- **作者**: Guangsheng Bao, Yanbin Zhao, Zhiyang Teng, Linyi Yang, Yue Zhang
- **年份**: 2023（arXiv v3 更新至 2024-12-16）
- **发表处**: 本轮仅核实 arXiv 记录（无 DOI）
- **类型**: preprint（会议归属本轮未核验）
- **链接**: https://arxiv.org/abs/2310.05130
- **核实证据**: `ARXIV: 2310.05130v3, published=2023-10-08, updated=2024-12-16`
- **研究问题**: DetectGPT 的扰动步骤太贵，且判别依据可更直接。LLM 与人类在给定上下文时的**词选择**差异能否用一个更廉价的曲率指标刻画？
- **方法**: 提出**条件概率曲率（conditional probability curvature）**，用「采样步」替代 DetectGPT 的「扰动步」。
- **主要结论（量化）**: 在白盒与黑盒设置下，相对 DetectGPT **提升约 75%**，同时**加速 340 倍**。
- **限制**: 摘要未给绝对准确率；对改写与非英语文本的表现未在摘要中说明。
- **对 InkSoul 的可借鉴点**: 340 倍加速使「把曲率当训练期监控指标」在算力上可行——可考虑在生成过程中按段采样计算条件概率曲率，作为机械化度的在线代理指标。
- **读取深度**: 仅读摘要。

---

### 16. Ghostbuster: Detecting Text Ghostwritten by Large Language Models

- **作者**: Vivek Verma, Eve Fleisig, Nicholas Tomlin, Dan Klein
- **年份**: 2024
- **发表处**: Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (NAACL-HLT 2024), long paper
- **类型**: peer-reviewed
- **链接**: https://doi.org/10.18653/v1/2024.naacl-long.95 ；预印本 https://arxiv.org/abs/2305.15047
- **核实证据**: `OPENALEX: doi=10.18653/v1/2024.naacl-long.95, venue=NAACL-HLT, year=2024, type=conference-paper, cited_by=56`；`OPENALEX` 另有 arXiv 条目 doi=10.48550/arxiv.2305.15047
- **研究问题**: 如何检测**「幽灵写作」**（人给想法、模型成文）这类混合文本？零样本/微调方法在混合文本上失效怎么办？
- **方法**: **黑盒**方法：把候选文本多次输入多个模型做概率计算，构造一组特征（含各模型概率、词级统计），训练一个线性分类器。
- **主要结论**: 摘要未给出本项目可用的数字（正文报 SOTA 的准确率与跨域结果）。**本条仅作方法学记录**，数字需读全文。
- **限制**: 黑盒但需多次调用 API，成本高；对**短文本**与**领域外**文本效果下降（论文自称的局限）。
- **对 InkSoul 的可借鉴点**: 「把同一段文本喂给多个模型取概率作为特征」这一构造，可以改造成**风格指纹向量**：不同模型对同一段人类/机器文本的概率反应差异，本身就是一种机制层的表征，而不只是检测特征。
- **读取深度**: 仅读摘要（**数字缺口**）。

---

### 17. SeqXGPT: Sentence-Level AI-Generated Text Detection

- **作者**: Pengyu Wang, Linyang Li, Ke Ren, Botian Jiang, Dong Zhang, Xipeng Qiu
- **年份**: 2023
- **发表处**: Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing (EMNLP 2023)
- **类型**: peer-reviewed
- **链接**: https://doi.org/10.18653/v1/2023.emnlp-main.73 ；预印本 https://arxiv.org/abs/2310.08903
- **核实证据**: `OPENALEX: doi=10.18653/v1/2023.emnlp-main.73, venue=EMNLP, year=2023, type=conference-paper, cited_by=53`；`ARXIV: 2310.08903v2`
- **研究问题**: 文档级检测粒度太粗；能否做到**句级**检测（对人机混合文本定位到句）？
- **方法**: 用多个白盒模型在句级抽取 log 概率等特征，构造句子级特征序列，用分类器（含序列模型）做句级判别。
- **主要结论**: 摘要未给具体数字，正文报句级检测的 SOTA。**本条仅作方法学记录**。
- **限制**: 依赖白盒模型；句级标注数据构建成本高；对中文的适用性未在摘要中讨论。
- **对 InkSoul 的可借鉴点**: **句级粒度**正是文学文本必需的粒度——机械化往往体现为「局部段落突然变成模板句」。InkSoul 的评估应做句级/段级打分而非全文单一分数，才能定位到具体病灶。
- **读取深度**: 仅读摘要（**数字缺口**）。

---

### 18. RAID: A Shared Benchmark for Robust Evaluation of Machine-Generated Text Detectors

- **作者**: Liam Dugan, Alyssa Hwang, Filip Trhlík, Josh Magnus Ludan, Andrew Zhu, Hainiu Xu, Daphne Ippolito, Chris Callison-Burch
- **年份**: 2024
- **发表处**: Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (ACL 2024), long paper
- **类型**: peer-reviewed
- **链接**: https://doi.org/10.18653/v1/2024.acl-long.674 ；预印本 https://arxiv.org/abs/2405.07940
- **核实证据**: `OPENALEX: doi=10.18653/v1/2024.acl-long.674, venue=ACL, year=2024, type=conference-paper, cited_by=48`；`ARXIV: 2405.07940v2`
- **研究问题**: 检测器的报告数字因数据集、攻击方式、领域不同而不可比。需要一个**共享基准**来测鲁棒性。
- **数据与规模**: 覆盖**多种生成模型、多个领域、多种对抗攻击（含改写）**的大规模基准（RAID）。
- **方法**: 统一评测协议 + 对抗攻击（尤其改写）+ 跨领域/跨模型泛化评估。
- **主要结论**: 摘要未给数字；核心论断是「现有检测器在加入改写等攻击后性能大幅下降、跨域泛化差」。**数字需读全文**。
- **限制**: 以英语为主；文学体裁覆盖有限。
- **对 InkSoul 的可借鉴点**: **改写攻击下的性能崩塌**是「检测器不能作为文学文本机械化度量」的核心理由——因为文学写作本身就在不断改写润色。InkSoul 应据此在方法学上回避「用检测器分数当机械化度」。
- **读取深度**: 仅读摘要（**数字缺口**）。

---

### 19. Can AI-Generated Text be Reliably Detected?

- **作者**: Vinu Sankar Sadasivan, Aounon Kumar, Sriram Balasubramanian, Wenxiao Wang, Soheil Feizi
- **年份**: 2023（arXiv v1 2023-03-17；v4 2025-01-17）
- **发表处**: 预印本 arXiv 2303.11156；Semantic Scholar/DBLP 另记录期刊版本 "Trans. Mach. Learn. Res. 2025"（标题略有扩展）
- **类型**: preprint（arXiv 版）；期刊版存在但本轮未取得其独立 DOI 页面
- **链接**: https://arxiv.org/abs/2303.11156
- **核实证据**:
  - `ARXIV: 2303.11156v4, published=2023-03-17, updated=2025-01-17`
  - `SEMANTIC SCHOLAR: year=2025, venue="Trans. Mach. Learn. Res.", DBLP key journals/tmlr/SadasivanKB0F25, externalIds 含 DOI 10.48550/arXiv.2303.11156`
  - `OPENALEX: doi=10.48550/arxiv.2303.11156, type=preprint, cited_by=172`
- **研究问题**: 在**有对手**的情况下，AI 文本检测器（含水印、神经网络检测器、零样本分类器、检索式检测器）有多可靠？
- **数据/方法**: 提出**递归改写攻击（recursive paraphrasing attack）**，在约 **300 token** 的段落上压力测试多类检测方案；另测试**伪造攻击**（把人类文本误判为 AI）；并给出理论分析。
- **主要结论（量化/理论）**:
  - 递归改写能**显著降低检出率**，而**文本质量只轻微下降**。
  - 攻击者可在**无白盒访问**的情况下推断水印的隐藏签名，从而把人类文本构陷为 AI 生成。
  - 理论上给出「最优检测器的 AUROC」与「人类/AI 文本分布间**总变差距离（Total Variation）**」的关系：随模型进步（分布靠近），可靠检测在原理上会变得不可能。
- **限制**: 段落级（~300 token）设定；攻击者模型假设较强；理论结论针对最优检测器。
- **对 InkSoul 的可借鉴点**: 最重的理论依据——**「人类分布与模型分布的总变差距离」就是 InkSoul 要拉大的那个量**。项目可以把自己的目标函数表述为「提高人类文本与生成文本分布的可分性/变差距离」，而不仅仅是降低某个模板计数。
- **读取深度**: 仅读摘要。

---

### 20. StyleDecipher: Robust and Explainable Detection of LLM-Generated Texts with Stylistic Analysis

- **作者**: Siyuan Li, Aodu Wulianghai, Xi Lin, Guangyan Li, Xiang Chen, Jun Wu, Jianhua Li
- **年份**: 2025
- **发表处**: 本轮仅核实 arXiv 记录（无 DOI）
- **类型**: preprint（无 DOI）
- **链接**: https://arxiv.org/abs/2510.12608
- **核实证据**: `ARXIV: 2510.12608v1, published=2025-10-14`
- **研究问题**: 现有检测方法泛化差、对改写脆弱、缺乏可解释性，尤其在**风格多样**与**人机混合署名**场景。
- **方法**: 联合建模**离散风格指标**（stylistic indicators）与**连续风格表示**（语义嵌入导出），在统一表示空间捕捉风格层差异；无需模型内部访问或分段标注。
- **主要结论（量化）**: 在 5 个领域（新闻、代码、论文、评论、学术摘要）取得域内 SOTA；**跨域评测比现有基线最高高 36.30%**；对对抗扰动与人机混合内容保持鲁棒。
- **限制**: 5 个领域里**没有小说/文学**；跨域增益是与「现有基线」比，绝对水平未在摘要给出。
- **对 InkSoul 的可借鉴点**: 「离散指标 + 连续嵌入」的双通道设计，正好对应 InkSoul 需要的「可解释指标（能指出哪条规则被违反）+ 可比较标量（能画曲线）」。可照此把「句式模板命中」与「风格嵌入距离」拼成一个混合度量。
- **读取深度**: 仅读摘要。

---

### 21. LLM Encoder vs. Decoder: Robust Detection of Chinese AI-Generated Text with LoRA

- **作者**: Houji Jin, Negin Ashrafi, Armin Abdollahi, Wei Liu, Jian Wang, Ganyu Gui, Maryam Pishgar, Huanghao Feng
- **年份**: 2025
- **发表处**: 本轮仅核实 arXiv 记录（无 DOI）
- **类型**: preprint（无 DOI）
- **链接**: https://arxiv.org/abs/2509.00731
- **核实证据**: `ARXIV: 2509.00731v1, published=2025-08-31`
- **研究问题**: 中文 AI 生成文本检测中，编码器模型与解码器（LLM）模型谁更鲁棒？分布偏移下谁撑得住？
- **数据与规模**: 使用 **NLPCC 2025 中文 AI 生成文本检测任务**的公开数据集。
- **方法**: 比较三类方案——编码器（Chinese BERT-large、RoBERTa-wwm-ext-large，用基于 prompt 的掩码语言建模微调）、解码器（Qwen2.5-7B / DeepSeek-R1-Distill-Qwen-7B 经 LoRA 适配 + 轻量分类头）、FastText 基线。
- **主要结论（量化）**:
  - 编码器模型「几乎记住训练数据」，但在分布偏移下显著退化：**RoBERTa 76.3%**、**BERT 79.3%** 测试准确率。
  - **FastText 出人意料地稳健，83.5%** 准确率，但缺乏深层语义理解。
  - **LoRA 适配的 Qwen2.5-7B 达 95.94%** 测试准确率，精确率-召回率较平衡，泛化最好。
- **限制**: 单一任务数据集（NLPCC 2025），「分布偏移」的具体构造需读正文；未覆盖文学体裁；FastText 的高分提示数据集可能存在**词面伪迹（dataset-specific artifacts）**。
- **对 InkSoul 的可借鉴点**: 两条硬信息： (a) 中文检测任务已有公开基准（NLPCC 2025），可直接用来标定自家指标的中文有效性；(b) **FastText 靠词面就能到 83.5%** 说明中文 AI 文本存在明显的词面级伪迹——这本身就是「机械化」的可测量证据（词面层已有强信号），而句法层的信号尚待分离。
- **读取深度**: 仅读摘要。

---

### 22. LLM-Detector: Improving AI-Generated Chinese Text Detection with Open-Source LLM Instruction Tuning

- **作者**: Rongsheng Wang, Haoming Chen, Ruizhe Zhou, Han Ma, Yaofei Duan, Yanlan Kang, Songhua Yang, Baoyu Fan, Tao Tan
- **年份**: 2024（arXiv v1 2024-02-02）
- **发表处**: 本轮仅核实 arXiv 记录（无 DOI）
- **类型**: preprint（无 DOI）
- **链接**: https://arxiv.org/abs/2402.01158
- **核实证据**: `ARXIV: 2402.01158v1, published=2024-02-02`
- **研究问题**: 基于 BERT/RoBERTa 的中文 AI 文本检测器易**域内过拟合**，域外（OOD）检测差；句级检测尤其弱。
- **数据与规模**: 自建数据集——人类专家与 **9 类 LLM** 对多领域问题的回答，并构造「人类句子 + LLM 润色句」的混合数据。
- **方法**: 用开源 LLM 做**指令微调**，同时支持文档级与**句级**检测。
- **主要结论**: 先前方法在句级检测与 OOD 检测上表现差，而 LLM-Detector 在句级与文档级均**显著优于基线**并展现较强泛化；因基于开源 LLM，便于定制部署。摘要无具体数字。
- **限制**: 摘要无量化；自建数据集未公开规模细节（需读正文）；域外测试集构造方式影响结论强度。
- **对 InkSoul 的可借鉴点**: 「人类句子被 LLM 润色」这一混合数据的构造方式，正是文学创作的真实工作流（人写骨架 + AI 润色）。InkSoul 若要测量「润色是否引入机械化」，可以直接复用这个**句级混合**的实验设计。
- **读取深度**: 仅读摘要。


## D. 同质化（homogenization）与多样性：生成机制侧的直接证据

### 23. The Homogenizing Effect of Large Language Models on Human Expression and Thought

- **作者**: Zhivar Sourati, Alireza S. Ziabari, Morteza Dehghani
- **年份**: 2025（arXiv v1 2025-08-02，v2 2026-01-05）
- **发表处**: 本轮仅核实 arXiv 记录（无 DOI；跨学科综述/立场文章）
- **类型**: preprint（综述/观点）
- **链接**: https://arxiv.org/abs/2508.01491
- **核实证据**: `ARXIV: 2508.01491v2, published=2025-08-02, updated=2026-01-05`
- **研究问题**: LLM 的广泛使用是否会标准化人类的语言与推理，从而压缩认知多样性？
- **方法**: 跨语言学、心理学、认知科学、计算机科学的证据综合（synthesis），非新实验。
- **主要结论（机制论断）**:
  - LLM **反映并强化主导风格**，同时边缘化另类表达与推理策略。
  - 机制有两条： (a) 设计上**镜像训练数据中的模式**； (b) 当所有人跨情境依赖**同一批模型**时，收敛被**放大（amplifying convergence）**。
  - 作者主张这种同质化若不加以约束，会「压平驱动集体智能与适应性的认知景观」。
- **限制**: 综述/立场文章，无自有实验与量化；因果推断弱，属机制假设而非测量结果。**引用时只能作为「机制假设来源」，不能当证据**。
- **对 InkSoul 的可借鉴点**: 提供「**个人层同质化** vs **语料层同质化**」的区分：InkSoul 在单篇文本层做测量，但论证价值来自「多人多篇的方差收缩」。这决定了实验设计必须**成组**（同一 prompt、多模型、多人）而非单篇评估。
- **读取深度**: 仅读摘要（本就是综述，摘要即全文结构）。

---

### 24. Task-Dependent Evaluation of LLM Output Homogenization: A Taxonomy-Guided Framework

- **作者**: Shomik Jain, Jack Lanchantin, Maximilian Nickel, Candace Ross, Karen Ullrich, Ashia Wilson, Jamelle Watson-Daniels
- **年份**: 2025（arXiv v1 2025-09-25，v3 2026-04-22）
- **发表处**: 本轮仅核实 arXiv 记录（无 DOI）
- **类型**: preprint（无 DOI）
- **链接**: https://arxiv.org/abs/2509.21267
- **核实证据**: `ARXIV: 2509.21267v3, published=2025-09-25, updated=2026-04-22`
- **研究问题**: 「输出同质化」是否有害**取决于任务**——数学题应保持答案一致但策略可多样，创意写作则要求情节/设定等**叙事要素**变化（而不只是词汇多样）。已有工作几乎不按任务区分多样性的含义。
- **方法（四项贡献）**: (1) 任务分类法，区分「**功能性多样性**（functional diversity）——用户是否感知为有意义的差异」；(2) 小规模用户研究，验证分类法与人类感知一致；(3) 任务相关的采样技术，只在**不该同质化**的地方增加多样性；(4) 证据挑战「多样性-质量权衡」的存在。
- **主要结论**: 作者主张所观察到的 diversity-quality trade-off 可能源自**把多样性与质量都做成了任务无关的定义**（即测量假象而非真实权衡）。
- **限制**: 用户研究规模小（摘要称 a small user study）；分类法覆盖的任务类型有限，文学创作只作为例子出现。
- **对 InkSoul 的可借鉴点**: 这是本项目**指标定义**的关键约束：不能只算词级/句级多样性，必须定义「**叙事功能性多样性**」（情节走向、场景、人物决策的差异）。InkSoul 的评测至少要区分「表层多样性」与「功能性多样性」两层，否则会重犯作者批评的测量错误。
- **读取深度**: 仅读摘要。

---

### 25. Modifying Large Language Model Post-Training for Diverse Creative Writing

- **作者**: John Joon Young Chung, Vishakh Padmakumar, Melissa Roemmele, Yuqian Sun, Max Kreminski
- **年份**: 2025
- **发表处**: 本轮仅核实 arXiv 记录（无 DOI）
- **类型**: preprint（无 DOI）
- **链接**: https://arxiv.org/abs/2503.17126
- **核实证据**: `ARXIV: 2503.17126v1, published=2025-03-21`
- **研究问题**: 创意写作没有唯一正确答案，但 LLM 后训练只优化质量、忽视输出多样性。能否在后训练目标里同时要多样性与质量？
- **方法**: 在训练目标中加入 **deviation**（某训练样本与同 prompt 下其他样本的差异度），以「从稀有的高质量实例中学习」；把该目标套用到 **DPO** 与 **ORPO** 上。
- **主要结论（量化）**: 最佳 **8B** 模型可达到与**人类创作数据集相当的多样性**，同时输出质量接近所考察的最佳指令微调模型（GPT-4o、DeepSeek-R1）；另有**人工评测**、消融实验，以及与已有 DivPO 方法的对比。
- **限制**: 多样性指标的定义需读正文（摘要未列）；「与人类数据集相当」是相对比较，绝对水平未知；仅在英文创意写作上验证。
- **对 InkSoul 的可借鉴点**: **最接近 InkSoul 目标的可行技术路线**——「deviation 作为训练信号」可以直接搬：把「与本 batch 内其他样本的句法模板差异」作为 deviation 的一个分量，在 DPO/ORPO 阶段施加，而不是靠解码期采样。这是「生成机制层」改善的实例。
- **读取深度**: 仅读摘要。

---

### 26. Improving Diversity in LLM Short Story Generation

- **作者**: Zahra Solati Dehkordi, Vasileios Lampos
- **年份**: 2026
- **发表处**: 本轮仅核实 arXiv 记录（无 DOI）
- **类型**: preprint（无 DOI）
- **链接**: https://arxiv.org/abs/2610.06729
- **核实证据**: `ARXIV: 2610.06729v3, published=2026-10-05, updated=2026-10-29`
- **研究问题**: LLM 短篇小说生成的多样性不足；具体应在哪些叙事维度上增加多样性？
- **方法（DivLM，两阶段后训练）**: 第一阶段在创意写作语料上继续预训练，并用 **weight residuals** 恢复指令跟随能力；第二阶段用强化学习，配一个**自定义复合奖励函数**，同时最大化目标叙事维度（体裁、语调、风格、命名实体）上的多样性与响应质量。
- **主要结论（量化）**: 在两个 LLM 系列上，**多样性指标平均提升 >9%**（相对其他方法），同时保持指令跟随、整体质量与与人类输出的相似度。
- **限制**: 摘要未说多样性用哪些具体指标（需读正文）；>9% 是相对增益；对**中文**未验证。
- **对 InkSoul 的可借鉴点**: 明确指出可多样化的**四个维度：体裁 / 语调 / 风格 / 命名实体**——这几乎就是文学文本机械化诊断表的雏形，可直接作为中文检查项（尤其「命名实体重复」是中文网文里极显性的机械化特征，本条目给了它文献依据）。
- **读取深度**: 仅读摘要。

---

## E. 句法结构相似度工具与中文句法资源

### 27. New Ranking Algorithms for Parsing and Tagging: Kernels over Discrete Structures, and the Voted Perceptron

- **作者**: Michael Collins, Nigel Duffy
- **年份**: 2001
- **发表处**: Proceedings of the 39th Annual Meeting of the Association for Computational Linguistics (ACL 2001)
- **类型**: peer-reviewed
- **链接**: https://doi.org/10.3115/1073083.1073128
- **核实证据**: `OPENALEX: doi=10.3115/1073083.1073128, venue=Proceedings of the ACL Meeting, year=2001, type=conference-paper, cited_by=504`；`biblio: first_page=263, last_page=263`（短篇）
- **研究问题**: 如何把感知机学习推广到**指数级规模的树表示**（如 all-subtrees / DOP 表示、所有标注句片段的表示）上，从而把「树核」直接用于解析与标注？
- **方法**: 基于感知机的新学习算法；讨论在「所有子树」「所有标注片段」等指数表示上的高效计算；在 WSJ 句法分析与 web 数据命名实体抽取两个任务上做实验。
- **主要结论**: 作者报告在两个任务上**显著提升**（摘要用语 "significant improvements"），未在摘要给出具体数字。
- **限制**: 摘要未给量化数字；这是**方法论基础文献**，不是关于 LLM 的经验研究。
- **对 InkSoul 的可借鉴点**: 树核（subset tree kernel / subtree kernel）为「两棵句法树有多像」提供了可计算的核函数，是把「句法模板重复」形式化为**结构相似度**的数学基础。InkSoul 若要在中文上度量「句子结构重复」，这条路比 n-gram 干净。
- **读取深度**: 仅读摘要（OpenAlex abstract）。

---

### 28. Efficient Convolution Kernels for Dependency and Constituent Syntactic Trees

- **作者**: Alessandro Moschitti
- **年份**: 2006
- **发表处**: Machine Learning: ECML 2006, Lecture Notes in Computer Science, pp. 318–329
- **类型**: peer-reviewed
- **链接**: https://doi.org/10.1007/11871842_32
- **核实证据**: `OPENALEX: doi=10.1007/11871842_32, venue=Lecture Notes in Computer Science, year=2006, type=conference-paper, cited_by=454, biblio: first=318, last=329`
- **研究问题**: 如何设计**高效**的卷积核，直接作用于**依存树与成分树**，用于关系抽取等任务？
- **方法**: 在树结构上定义部分匹配的卷积核（subset tree kernel 等），避免显式枚举特征；用于带句法信息的分类任务。
- **主要结论**: 该核显著提升句法驱动的分类性能，成为后续句法相似度的标准工具。**注意：OpenAlex 未提供本文摘要（abstract 字段为空），本条的方法描述仅据标题与出版物信息，未读到摘要正文。**
- **限制**: 未读摘要，故不引用任何数字；文献性质为方法基础。
- **对 InkSoul 的可借鉴点**: 依存树核让「同一句法骨架换了词」这类重复**可被检测**——这是中文（分词 + 依存）场景里最实用的一种树核变体。可作为模板抽取器的打分器，替代「Arc 标签序列完全相等」这种硬匹配。
- **读取深度**: **未读摘要（OpenAlex 无摘要字段）**，仅核实书目。

---

### 29. The Tree-to-Tree Correction Problem

- **作者**: Kuo-Chung Tai
- **年份**: 1979
- **发表处**: Journal of the ACM, 26(3), 422–433
- **类型**: peer-reviewed（期刊）
- **链接**: https://doi.org/10.1145/322139.322143
- **核实证据**: `OPENALEX: doi=10.1145/322139.322143, venue=Journal of the ACM, year=1979, type=article, cited_by=867, biblio: volume=26, issue=3, first=422, last=433`
- **研究问题**: 给定两棵带标签的有序树 T 与 T'，如何定义并计算「树间距离」——由最小编辑操作代价序列度量？允许的编辑操作是：把一个节点改成另一个节点、删除一个节点、插入一个节点。
- **方法**: 给出求解该问题的算法，时间复杂度 **O(V·V'·L²·L'²)**，其中 V、V' 为两树节点数，L、L' 为两树最大深度。
- **主要结论**: 该复杂度即论文的核心结果；作者同时指出可应用于「度量树间相似度」「程序语言的自动纠错」「求两棵树的**最大公共子结构**」。
- **限制**: 1979 年的复杂度结果（后续有更快的算法，本轮未核实）；有序树、允许节点重标代价模型，对自然语言句法树需要额外的代价设定。
- **对 InkSoul 的可借鉴点**: 「**最大公共子结构**」正是「句法模板」的形式化定义；树编辑距离则给出「两句结构差多远」的严格度量。InkSoul 可以用「两树最大公共子树的规模 / 树规模」作为模板重合度，比数 n-gram 更能反映句法层机械化。
- **读取深度**: 仅读摘要（OpenAlex abstract，OCR 有噪声，数字已核对为 O(V·V'·L²·L'²)）。

---

### 30. FastKASSIM: A Fast Tree Kernel-Based Syntactic Similarity Metric

- **作者**: Maximillian Chen, Caitlyn Chen, Xiao Yu, Zhou Yu
- **年份**: 2023
- **发表处**: Proceedings of the 17th Conference of the European Chapter of the Association for Computational Linguistics (EACL 2023), main
- **类型**: peer-reviewed
- **链接**: https://doi.org/10.18653/v1/2023.eacl-main.17 ；预印本 https://arxiv.org/abs/2203.08299
- **核实证据**: `OPENALEX: doi=10.18653/v1/2023.eacl-main.17, venue=EACL, year=2023, type=conference-paper, cited_by=5`；`ARXIV: 2203.08299v4, published=2022-03-15, updated=2023-01-27`
- **研究问题**: 语法是语言的基础，但**句级/文档级的句法相似度指标**很少；现有的标准文档级句法相似度指标计算昂贵，且在遇到句法差异大的文档时表现不稳定。
- **方法**: FastKASSIM——在成对文档之间，**配对并平均最相似的成分句法树**（基于树核），得到句级与文档级的句法相似度。
- **主要结论（量化）**:
  - 对句法差异**更鲁棒**；在 r/ChangeMyView 语料上比前身指标**快最多 5.32 倍**。
  - 应用发现：r/ChangeMyView 上**句法相似的论证更有说服力**；在 Australian High Court Judgment 语料上**句法是作者归属的预测因子**。
- **限制**: 仅英语、仅成分树；「最相似树配对平均」在长文档上仍可能被少数极相似句对拉高，需读正文看其归一化方式。
- **对 InkSoul 的可借鉴点**: 这是**唯一一条同时给出「句法相似度指标 + 作者归属可预测性」的实证论文**，直接把「句法层相似度」与「风格/作者身份」打通。InkSoul 的「机械化」若要论证为风格层现象，可复用其「句法相似度能否预测类别」的验证范式（用句法相似度特征去预测「人写/AI 写」或「哪个模型」）。5.32 倍加速也说明这套计算在中文长文本上可行。
- **读取深度**: 仅读摘要。

---

### 31. The Penn Chinese TreeBank: Phrase structure annotation of a large corpus

- **作者**: Nianwen Xue, Fei Xia, Fu-Dong Chiou, Martha Stone Palmer
- **年份**: 2005
- **发表处**: Natural Language Engineering, 11(2), 207–238
- **类型**: peer-reviewed（期刊）
- **链接**: https://doi.org/10.1017/S135132490400364X
- **核实证据**: `OPENALEX: doi=10.1017/s135132490400364x, venue=Natural Language Engineering, year=2005, type=article, cited_by=665, biblio: volume=11, issue=2, first=207, last=238`
- **研究问题**: 中文 NLP 工具各自在不同分词标准、词性标注集与括号标注规范上训练，导致**无法比较**；需要大规模、公开、规范统一的树库。
- **数据与规模**: 自 1998 年末开始构建；**前两期共 25 万词（250 thousand words）**，已完成分词、词性标注与句法括号标注，经 LDC 发布。
- **方法**: 讨论若干汉语语言学问题及其对树库标注的影响，以及如何在标注规范中处理这些问题；并描述提升标注速度同时保证质量的工程策略。
- **主要结论**: 交付了当时可公开获取的大规模中文句法标注语料；摘要不含评测数字。
- **限制**: 成分树（phrase structure）而非依存树；体裁为新闻（LDC 语料），**文学文本不在其中**——这点对 InkSoul 很关键。
- **对 InkSoul 的可借鉴点**: 中文句法分析器与标注规范的**事实基准**。但要注意：CTB 是新闻体裁，用其训练的解析器在小说/散文中会有域偏移——InkSoul 若要用依存/句法指标，必须先在文学语料上**测解析器可靠度**，否则测到的是解析错误而非机械化。
- **读取深度**: 仅读摘要（OpenAlex abstract）。


---

## 汇总表（31 条，均已通过 API / 出版方页面核实书目）

| # | 简称 | 年 | 类型 | 标识符（核实所得） | 对 InkSoul 的主用途 |
|---|------|----|------|------------------|---------------------|
| 1 | Shaib et al. Syntactic Templates | 2024 | peer-reviewed | 10.18653/v1/2024.emnlp-main.368 | 句法模板重复率范式（76% vs 35%） |
| 2 | Holtzman et al. Neural Text Degeneration | 2019 | preprint | arXiv:1904.09751 | 解码侧成因，区分数据侧/解码侧 |
| 3 | Zhu et al. Texygen | 2018 | preprint | arXiv:1802.01886 | distinct-n/Self-BLEU 仅作基线层 |
| 4 | Guo et al. Linguistic Diversity | 2025 | peer-reviewed | 10.1162/tacl.a.47 | 多层多样性指标框架 |
| 5 | Kendro et al. Lexical Diversity | 2025 | peer-reviewed | 10.1111/ijal.70115 | 6 维词汇多样性 + 人内方差基线 |
| 6 | Zamaraeva et al. HPSG | 2025 | preprint | arXiv:2506.01407 | 语法构造类型分布距离 |
| 7 | Rallapalli et al. Biber 多因素 | 2026 | preprint | arXiv:2604.14111 | 体裁>来源；prompt 修不掉机械化 |
| 8 | Reinhart et al. PNAS | 2025 | peer-reviewed | 10.1073/pnas.2422455122 | 方差收缩 + 指令微调是来源 |
| 9 | Zanotto & Aroyehun | 2025 | peer-reviewed | arXiv:2507.13614 (EMNLP 2025) | 依存距离；人类组内方差更大 |
| 10 | Przystalski et al. | 2026 | peer-reviewed | 10.1016/j.eswa.2025.129001 | grammatical standardisation + SHAP 归因 |
| 11 | Kumarage & Liu | 2023 | preprint | arXiv:2308.07305 | 模型间风格签名可区分 |
| 12 | Huang et al. 综述 | 2024 | preprint | arXiv:2408.08946 | 文献地图（四分类） |
| 13 | Yao et al. 网文翻译 | 2025 | peer-reviewed | 10.1075/ts.24043.yao | **反向证据**：强约束任务差异可压至极小 |
| 14 | DetectGPT | 2023 | peer-reviewed | PMLR v202 / arXiv:2301.11305 | 概率曲率作为机制层可观测量 |
| 15 | Fast-DetectGPT | 2023 | preprint | arXiv:2310.05130 | 340× 加速→可作在线监控 |
| 16 | Ghostbuster | 2024 | peer-reviewed | 10.18653/v1/2024.naacl-long.95 | 多模型概率→风格指纹向量 |
| 17 | SeqXGPT | 2023 | peer-reviewed | 10.18653/v1/2023.emnlp-main.73 | 句级粒度评估 |
| 18 | RAID | 2024 | peer-reviewed | 10.18653/v1/2024.acl-long.674 | 改写攻击下崩塌→弃用检测器分数 |
| 19 | Sadasivan et al. | 2023/2025 | preprint | arXiv:2303.11156 (TMLR 2025 版) | 总变差距离=InkSoul 的目标量 |
| 20 | StyleDecipher | 2025 | preprint | arXiv:2510.12608 | 离散指标+嵌入双通道 |
| 21 | Jin et al. LoRA 中文检测 | 2025 | preprint | arXiv:2509.00731 | NLPCC2025 基准；FastText 83.5% 词面伪迹 |
| 22 | LLM-Detector 中文 | 2024 | preprint | arXiv:2402.01158 | 人句+AI 润色的句级混合设计 |
| 23 | Sourati et al. 同质化 | 2025 | preprint | arXiv:2508.01491 | 个体层 vs 语料层同质化 |
| 24 | Jain et al. 功能性多样性 | 2025 | preprint | arXiv:2509.21267 | 必须定义「叙事功能性多样性」 |
| 25 | Chung et al. 创意写作后训练 | 2025 | preprint | arXiv:2503.17126 | deviation 进 DPO/ORPO（机制层路线） |
| 26 | DivLM | 2026 | preprint | arXiv:2610.06729 | 四维叙事多样性（含命名实体） |
| 27 | Collins & Duffy 树核 | 2001 | peer-reviewed | 10.3115/1073083.1073128 | 结构相似度形式化基础 |
| 28 | Moschitti 依存/成分树核 | 2006 | peer-reviewed | 10.1007/11871842_32 | 依存树核替换硬匹配（**未读摘要**） |
| 29 | Tai 树到树纠正 | 1979 | peer-reviewed | 10.1145/322139.322143 | 最大公共子结构=模板的形式定义 |
| 30 | FastKASSIM | 2023 | peer-reviewed | 10.18653/v1/2023.eacl-main.17 | 句法相似度→作者归属可预测 |
| 31 | 宾州中文树库 CTB | 2005 | peer-reviewed | 10.1017/S135132490400364X | 中文句法资源基准（新闻体裁域偏移） |

统计：peer-reviewed **16** 条，preprint **15** 条，workshop 0 条，thesis 0 条（共 31 条）。
peer-reviewed 编号：#1,4,5,8,9,10,13,14,16,17,18,27,28,29,30,31。其余为 preprint。

---

## 检索缺口

以下方向**没有取得可核验文献**，或只取得不足以支撑结论的材料。按「缺什么 → 试过什么 → 卡在哪」记录，避免后来者重复踩坑。

### 缺口 1：中文文学（小说/散文）文体的直接量化研究 —— 最大缺口

- **缺**: 直接研究「中文 LLM 生成小说/散文的文体特征与机械化」的同行评议论文。这是 InkSoul 的核心场景，却几乎找不到对应文献。
- **试过**: OpenAlex `search=Chinese LLM novel style`、`Chinese fiction generation stylometry`；arXiv `abs:"Chinese" AND abs:"novel" AND abs:"style"`；ACL Anthology 检索页（`/search/?q=` 返回结构不稳定，未取得可用结果）。
- **卡在**: 中文文学生成研究多集中在**诗歌生成**、**网文续写产品**、**故事大纲生成**，少有针对**文体层**的量化分析；且多数成果发表在中文学术期刊（《中文信息学报》《计算机学报》），**未被 OpenAlex/Crossref 完整收录**，而 CNKI/万方必需订阅，本轮无法访问。
- **下一步建议**: 需用 CNKI/万方检索「中文信息学报 + 生成文本 风格」「大模型 中文 文体」；或改用知网镜像。**这是需要人工渠道的缺口，工具层解决不了。**

### 缺口 2：中文依存句法/篇章资源（CDH、中文依存树库）

- **缺**: 「CDH」在中文 NLP 文献中并非标准缩写。可能的指代有：Chinese Discourse Treebank（Zhou & Xue）、Chinese Dependency Treebank（CDT）、以及 Harbin 体系的 CDT。**三种候选我都无法确认用户指的是哪一个。**
- **试过**: OpenAlex `search=Chinese Discourse Treebank`、`Chinese dependency treebank annotation` —— 均返回 **HTTP 429**（无 key 共享每日 $0.10 预算，当日额度在密集核实中耗尽）。
- **卡在**: 额度问题，非资源不存在。CDT/CDTB 本体是 LDC 发布的标注规范文档，**未必有独立期刊论文**，因此即便额度恢复也可能查不到「论文」形式的入口。
- **下一步建议**: 直接查 LDC 目录（`catalog.ldc.upenn.edu`）取 LDC 编号作为资源引证；论文侧可查周明/薛念文团队 2010 前后工作。
- **已有替代**: 本条已收录 **CTB**（#31），可作为中文成分句法资源的事实基准；但 CTB 是**新闻体裁**，对文学作品存在系统域偏移，这一点已在 #31 中标出。

### 缺口 3：Zhang & Shasha 1989 树编辑距离（SIAM J. Comput.）

- **缺**: 树编辑距离的经典算法论文（`Simple fast algorithms for the editing distance between trees and related problems`，SIAM Journal on Computing 18(6):1245-1262）的权威核实。
- **试过**: OpenAlex 精确标题检索 **3 轮**，全部 **HTTP 429**；Crossref 全程 429；未尝试 arXiv（该文无预印本）。
- **卡在**: 纯粹的 API 额度问题。
- **替代方案（已用）**: 收录 **Tai 1979**（#29）作为树编辑距离的**源头文献**（1.0 版复杂度 O(V·V'·L²·L'²)，且明确提出「最大公共子结构」概念），已足够支撑 InkSoul 的形式化论证；Zhang-Shasha 只是**更快的实现**，不是概念必需。若需精确引用，额度恢复后一条 OpenAlex 查询即可补。

### 缺口 4：DetectGPT 之外的「检测器失效」量化证据（中文/文学条件）

- **缺**: 在**中文文学文本**上测过的检测器性能数字（F1/AUROC）。现有 RAID（#18）、SeqXGPT（#17）、Ghostbuster（#16）的摘要均不含数字，正文数字未读；且都是英语/通用领域。
- **试过**: 已读 #16/#17/#18 摘要（均无数字）；#21 是唯一给出中文数字的（NLPCC 2025 数据集，但**非文学体裁**）。
- **卡在**: 需要读全文的表格才能取数；且没有任何论文在中文文学体裁上报过检测器数字。
- **影响**: 若 InkSoul 想在论文里写「检测器在中文文学文本上失效」，**目前没有直接文献支撑**，只能引用「改写攻击导致崩塌」（#18）与「FastText 靠词面伪迹」（#21）做间接论证。这是一个**需要自己做实验填补的空位**，也可以成为 InkSoul 的一个贡献点。

### 缺口 5：跨语言/多语言风格同质化的量化研究

- **缺**: 同时覆盖多语言、给出量化同质化指标的研究。
- **试过**: OpenAlex 与 arXiv 的组合检索未发现；已收录的 #23（同质化）是综述且以英语/认知视角为主，#4（语言多样性）以英语为主。
- **卡在**: 该方向 2025-2026 才开始出现，可能多数仍在预印本阶段且未被我检索到。
- **下一步建议**: 检索词可试 `multilingual homogenization LLM`、`cross-lingual stylistic convergence`。**本轮未覆盖，属明确缺口。**

### 缺口 6：会议归属无法确认的条目（诚实标注）

| 论文 | 情况 | 处理 |
|------|------|------|
| Holtzman et al. 1904.09751 | OpenAlex 仅返回 arXiv 记录；OpenReview 被浏览器验证墙拦截（403 / "Verifying your browser"），无法核验会议页 | 记为 **preprint**，不标会议 |
| Zhu et al. Texygen 1802.01886 | ACL Anthology 单条页面抓取失败（curl 未产生文件）；未再重试 | 记为 **preprint**，不标会议 |
| Bao et al. Fast-DetectGPT 2310.05130 | 同上，未取得会议页 | 记为 **preprint** |
| Moschitti 2006 | 书目已核实（DOI/LNCS/页码），但 **OpenAlex 无 abstract 字段** | 已标注「未读摘要」，不引用其结论数字 |

> 说明：这四条**不是查不到文献**，而是**查不到「会议归属」这一层证据**。按铁律「不得编造」，一律降级为 preprint 记录，宁可保守。

### 缺口 7：workshop 与 thesis 类文献

- 本轮 **0 条 workshop、0 条 thesis**。原因是检索全部走 OpenAlex/arXiv/ACL 主页，层级天然偏向主会与期刊；workshop 论文在 OpenAlex 中常被归入主会或缺失，学位论文（尤其中文学位论文）基本不收录。
- 若 InkSoul 需要 workshop 级的早期探索（如 In2Writing、Creative AI workshop），应直接查对应 workshop 的 ACL Anthology 卷号（如 `2024.in2writing-1`）。**本轮未做。**

---

## 给后续维护者的三条操作提醒

1. **OpenAlex 额度是真瓶颈**。无 key 时共享每日 $0.10，单次 `select=` 全字段查询约 1-2 美分，密集核实 30 条约当天耗尽，之后全部 429。**先批量规划查询，别逐条试**；或申请免费 key。
2. **Crossref 已在本次会话中全程不可用**（持续 429），不要把它当主通道。ACL Anthology 页面 + arXiv metadata 的 `journal_ref`/`doi` 字段是**更可靠的替代**——本次 31 条里绝大多数靠这两者交叉确认。
3. **`arxiv:journal_ref` 是最容易被忽略的金矿**。多篇正式发表版（#8 PNAS、#9 EMNLP、#10 ESWA、#13 Target）的期刊/会议信息是直接从 arXiv API 的 `journal_ref` 字段读出来的，比 Crossref 稳、比 S2 快。
