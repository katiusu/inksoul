# 两篇论文全文精读提取（数字均引自原文；未报告处标"原文未报告"）

## 一、Reinhart, Markey, Laudenbach, Pantusen, Yurko, Weinberg, Brown (2025). "Do LLMs write like humans? Variation in grammatical and rhetorical styles." PNAS 122(8):e2422455122 · DOI 10.1073/pnas.2422455122
> 源：PNAS 正文全文（Europe PMC PMC11874169 fullTextXML）+ SI Appendix 22 页 PDF（Table S1–S12）
**1 模型（S1）**：GPT-4o 2024-08-06 / GPT-4o Mini 2024-07-18（皆 128K，**只有 instruct 版**，OpenAI Batch API 默认设置）；Llama 3 8B、70B（8K，**base**，纯续写）与 8B-Instruct、70B-Instruct（8K，vLLM 0.5.5）。base/instruct 唯一差别=是否给指令：instruct 得提示词+chunk1，base 只给 chunk1。GPT 无 base 版 → 调优对照只能靠 Llama。
**2 语料**：**单一 prompt 模板**（无多模板、无 few-shot）：`In the same style, tone, and diction of the following text, complete the next 500 words, generate exactly 500 words, and note that the text does not necessarily end after the generated words:` + 人类文本前 ~500 词。起点各 12,000 篇人类英文；取前 ~1,000 词→spaCy 句界切两个 ~500 词 chunk；chunk1 作上下文，比对人类 chunk2。剔除拒答/乱码/<100 词后：HAP-E n=**8,290**（66,320 chunks）、CAP n=**9,615**（76,920 chunks）。HAP-E 6 体裁(n)：academic 1,227 / news 1,322 / fiction 1,395 / spoken 1,721 / blogs 1,526 / TV-movie 1,099；CAP 8 语域(COCA)：acad 1,221 / blog 1,071 / fic 1,372 / mag 1,293 / news 1,188 / spok 1,334 / tvm 1,006 / web 1,130；外部迁移用 M4（arXiv 摘要 vs GPT-3.5 摘要）。
**3 特征**：Biber **66 类**，pseudobibeR（R）+ spaCy 依存树，统计**每 1,000 词出现率**；该 tagset **无 it-cleft / wh-cleft 类别**。Lexical：Mean word length、Type-token ratio、Nominalizations、Gerunds、Other nouns、Adverbs、Attributive adjectives、Predicative adjectives、Prepositional phrases、Demonstratives。Grammatical：Present participial clauses、"That" clauses as subject、Agentless/"By-" passives、Past/Present participial postnominal、Phrasal/Clausal co-ordination、Infinitives、Existential "there"、"That" verb complements、"Wh-" relatives as subject/object、Pied-piping relatives、Sentence relatives、Split auxiliaries、Contractions、Stranded prepositions、Possibility/Necessity/Predictive modals。Rhetorical/discourse：Conjuncts、Downtoners、Hedges、Amplifiers、Emphatics、Discourse particles、Public/Private/Suasive verbs、"Seem"/"Appear"、Because、Though、If-unless、Other adverbial subordinators、Time/Place adverbials、Pro-verb "do"、Analytic/Synthetic negation、1st/2nd/3rd-person pronouns、Indefinite pronouns、"Wh-" questions。
**4 核心结果**（S5 出现率 + S6 配对 Cohen's d；人类 chunk2=100%，|d|>1.3 为 very large）
| 特征 | 人类率/千词 | GPT-4o | d | Llama3-70B-Inst | d | Llama3-70B-base | d |
|---|---|---|---|---|---|---|---|
| Present participial clauses | 1.7 | **527%** | **1.38** | 261% | 0.56 | 102% | 0.01 |
| "That" clauses as subject | 2.1 | 263% | 0.77 | 173% | 0.33 | 68% | −0.20 |
| Mean word length | 4.4 字符 | 116% | **2.24** | 103% | 0.45 | 100% | 0.01 |
| Nominalizations | 14.6 | **214%** | **1.23** | 151% | 0.59 | 91% | −0.12 |
| Phrasal co-ordination | 6.1 | 194% | 0.81 | 170% | 0.53 | 97% | −0.02 |
| Attributive adjectives | 43.8 | 150% | 1.09 | 104% | 0.10 | 83% | −0.37 |
| Past participial postnominal | 1.5 | 235% | 0.55 | 75% | −0.13 | 131% | 0.14 |
| Adverbs | 71.8 | 82% | −0.53 | 75% | −0.77 | 102% | 0.05 |
| Agentless passives | 7.8 | **53%** | −0.56 | 89% | −0.13 | 98% | −0.02 |
| Clausal co-ordination | 12.4 | **59%** | −0.59 | 127% | 0.36 | 116% | 0.18 |
| Because | 1.5 | **20%** | −0.50 | 38% | −0.35 | 105% | 0.02 |
方向：instruct（尤其 GPT-4o）**名词短语更密、小句更少**——参与小句/that-主语从句/名词化/并列短语/定语形容词/介词短语/长词全部超额；**限定小句与口语手段塌陷**——无施事被动≈半、because≈1/5–1/3、clausal coordination、contractions、1/2 人称、"be" 主动词、pro-verb "do"、emphatics、hedges 全低。Llama base 几乎贴 100%（|d|≤0.25）→ 偏差主要由**指令调优**引入，非预训练语料。
**5 LLM 间差异 / instruct vs base**：七分类混淆矩阵错误集中于同族不同规模（8B↔70B、8B-Inst↔70B-Inst、4o↔4o Mini）→ 规模带来的风格差远小于 tuning。家族反向模式：clausal coordination GPT-4o 63%/59% vs Llama-Instruct 141%/127%；downtoners GPT-4o 155%/118% vs 全部 Llama ≤73%。instruct 更"机器"：participial d 0.56 vs 0.01、mean word length 0.45 vs 0.01、nominalization 0.59 vs −0.12；Lasso 可分性 base ~75% vs instruct/GPT-4o 92–96%（S10）。词汇（S7/S8）：GPT-4o camaraderie 162×、tapestry 155×、intricate 119×、amidst 100×、palpable 95×；"tapestry" 见于 **23%**、"amidst" **27%** 的 GPT-4o 输出；脏话低 100×+。
**6 检测与迁移**：七源随机森林测试准确率 **66%**（随机 14%），仅 **4.2%** LLM 文本误判为人类、**9.8%** 人类文本误判为 LLM；逐对 RF **93–98%** 且 HAP-E↔CAP 双向迁移保持（S9：GPT-4o 98.3%→98.4%），Lasso 73–96%（Llama base 仅 ~73–78%）；训练于 HAP-E、测 M4 GPT-3.5 摘要：GPT-4o 70.63%、4o Mini 60.77%、Llama-70B-Inst 68.20%、8B-Inst 65.60%，Llama base 仅 **51.17%/51.85%**（≈随机，S11/S12）。
**7 局限**：原文自认——指令调优流程不公开（"not possible to determine the cause more precisely"）、分类器"跨 LLM 或跨语域泛化困难"；**无独立 Limitations 章节**。本喵补充——单一 prompt 模板；500 词片段，段落/篇章组织与跨段重复未测；仅英语；人类文本被截到 ~1,000 词；特征是出现率，与修辞效果无因果链；base/instruct 对比混淆了"是否给指令"；GPT 用默认设置、Llama 采样参数未报告。
**8 可控变量启示**：①**该压**：present participial clauses（要到人类 1.7/千词需砍 60–80%）、that-主语从句、nominalization、phrasal coordination、attributive adjectives、prepositional phrases、mean word length、past participial postnominal（名词短语复杂度抓手）；②**该补**：because/if/though 等从属连词与限定小句、clausal coordination、agentless passive、contractions、1/2 人称、pro-verb "do"、emphatics/hedges、existential there、that-verb-complements；③全部是**每千词可计数率**（pseudobibeR 可复算）→ 生成后算 66 维率向量，与**同体裁**人类基线（S5 给逐特征人类率）配对比 d 值修正；④词汇黑名单：tapestry/intricate/camaraderie/palpable/amidst/solace/unravel/underscore/fleeting；⑤目标值按体裁定而非全局平均（原文核心论点正是 LLM 不随语境调节风格）。

## 二、Guo, Shang, Clavel (2025). "Benchmarking Linguistic Diversity of Large Language Models." TACL · DOI 10.1162/tacl.a.47
> 源：arXiv:2412.10271**v2**（2025-07-25，TACL 接收版）全文；direct.mit.edu 的 publisher PDF 本机三次下载超时未取到，故引用页码以 arXiv v2 为准。
**1 三维度与指标（原文定义）**
| 维度 | 指标 | 公式/实现要点 |
|---|---|---|
| Lexical | **Unique-n**（uni/bi/trigram 平均） | unique n-gram 数 ÷ n-gram 总数；n=1 即 TTR；用**全局**而非 moving-average 版（moving average 会漏全局重复，引 Bestgen 2023）；为消长度影响每个 n 固定随机取 **40K** |
| Syntactic | **依存树 + Weisfeiler-Lehman 图核的平均成对距离** | 神经依存解析器（Qi et al. 2020，Universal Dependencies）出树，节点=词、边=依存、节点带 PoS 标签；WL 核把树映射进 RKHS（可做同构检验），多样性 = 树间平均成对距离 |
| Semantic | **Sentence-BERT 嵌入的平均成对余弦距离** | 句子向量化后算嵌入空间离散度，缩放到 [0,1] |
- 测的是 **across-input diversity**（每输入只生成 1 个输出，跨输入比），**不测 per-input**（同 prompt 多采样）；原文显式排除风格多样性与社会语言多样性（"less interpretable and often overlap"）。
- 相关性：词法↔语义**正相关**、句法↔质量**常负相关**（"higher syntactic diversity is associated with lower quality scores"）；维度间 句法↔语义 +0.55、词法↔句法 +0.13、词法↔语义 −0.14。
**2 数据与模型**：5 任务（创造力递增）——LM=Wikitext-2（128 token 续写）、MT=WMT-14 法→英、Summ=XLSUM 英文、NUG=DailyDialog（预测末句）、ASG=WritingPrompts（Reddit 故事续写）；**每任务随机 10K 样本、每任务仅 1 个数据集**。6 族、各取最接近 7B：Llama-3.1-8B、Mistral-NeMo-12B、Qwen2.5-7B、Gemma-2-9B、Falcon-7B、OLMo-7B（LM 用 base，其余用 instruct）。解码 nucleus sampling（t=0.6 + top-k/top-p 0.9，原文如此表述），后续实验固定 t=0.6。**单语英语**（"we study linguistic diversity in a monolingual context, focusing on the English language"）；MT 输入法语、语义用 multilingual SBERT、句法用法语解析器，作者声明不可与英语任务直接比。**不含中文**。
**3 句法深度分析（§5.3，ASG）**：把 Le Bronnec et al. (2024) 的 **Precision-Recall 框架**搬到依存树——GPT-2 嵌入 + PCA + K-Means 估计分布支撑集。Precision=模型树落在人类支撑集内的比例（合语法性），**Recall=人类树落在模型支撑集内的比例（覆盖人类句法全谱的能力）**。结果（Table 2）：**Precision 99.07–99.73%（近乎满分）而 Recall 仅 35.20–75.27%**（按表头顺序 Llama 35.20 / Mistral 65.87 / Qwen 75.27 / Gemma 37.97 / Falcon 75.00 / OLMo 39.40；列-模型映射在 HTML 中无法完全核验）。结论：模型句法"几乎全部合法、但只覆盖人类句法的一小半"——**recall 才是区分模型、暴露缺口的指标**，precision 不是。
**4 缺失/过量的具体 POS n-gram 模板（Table 3）**：人类独有 (ADV,ADV,ADP) "right along with"、(VERB,ADP,DET,NOUN) "picking up the pieces"、(DET,ADJ,NOUN,ADP,DET,NOUN) "the old woman down the street"；模型过量 (PRON,NOUN,ADJ) "her voice soft"（**无动词的独立主格小句**）、(NOUN,CCONJ,NOUN,PRON) "carvings and symbols that"、"particular focus on time and space"（抽象名词并列）。归因：记忆预训练句法模板且 SFT/偏好调优很少改写（引 Shaib et al. 2024b）；OLMo 预训练 **>80% 来自 Common Crawl、<0.3% 来自 Project Gutenberg**（后者才与叙事文体对齐）→ 预训练域与创作任务错配。
**5 故事生成（ASG，Table 5 原始分）**：人类 **词法 59.04 / 句法 65.35 / 语义 44.90**，任务输入 41.19 / 59.86 / 44.15；**6 模型范围：词法 52.28–56.90、句法 52.58–58.12、语义 41.90–43.91**（逐模型列序无法从 HTML 可靠还原，故只给范围）。ASG 是**唯一三维度全落后人类**的任务（"LLMs consistently lag behind humans in all three diversity aspects"）；反例 NUG：词法人类 40.25 vs 模型 40.68–50.53、语义 44.38 vs 45.25–46.69（DailyDialog 面向英语学习者、话题泛化，模型反把话题引向更复杂方向）；Summ/MT 多样性甚至高于人类参考。预训练 token 少者（Falcon 1.5T、OLMo 2.7T vs Llama-3.1 15T）词法多样性稳定更低，句法/语义无此效应；过滤宽松者（Qwen2.5 只过滤质量）故事生成三维度更高，Llama-3.1/Gemma-2/OLMo（质量+隐私+安全过滤）更低。
**6 各因素的方向与幅度（均在 ASG 上）**
| 因素 | 词法 | 句法 | 语义 | 原文依据 |
|---|---|---|---|---|
| 预训练量（OLMo checkpoint） | 早期骤降→**持续上升、未饱和** | 早期骤降→**饱和**在小范围波动 | 稳步升、较早饱和 | 2B token 处词法骤降 |
| SFT（Tulu v2） | 极小 | 极小 | 极小 | "minimal impact on any diversity metric" |
| DPO（Ultrafeedback） | **升** | **降** | — | 原文未给数值 |
| instruct vs base（全模型） | **升** | **降**（降幅大于语义的降幅） | 降 | "the decline in syntactic diversity is more pronounced than that in semantic diversity" |
| 温度（0.1→高） | **升**，质量仅轻微下降 | 多数在区间内波动，OLMo/Falcon 明显下行 | 无一致趋势 | t=0.6 "relevance 仍较高而多样性显著提升"；模型排名对温度稳定 |
| prompt 改写（"be as creative as possible"） | 几乎无影响 | 几乎无影响 | 几乎无影响 | "enhancing linguistic diversity through straightforward prompt engineering alone would be challenging" |
| 规模（Qwen2.5 0.5B→32B） | **单调升** | 稳定但**7B 达峰后回落** | 稳定 | "scaling up is not always the solution" |
| 4-bit 量化（vs bf16） | **降**（小模型降幅更大） | **降**（大模型更明显） | 不变 | "greater impact on the diversity of form rather than content" |
**7 明确没有覆盖**：①**语言**——只做英语（MT 仅法→英输入），自称单语、"methodology is language agnostic" 但未验证，**无中文**；②**长度/篇章**——指标停在句集与 n-gram 集合层，最长只到故事续写，**跨段落重复、篇章级回指、章节结构未测**（LM 任务仅 128 token），无文学长文本；③**质量与文学性**——只用 BERTScore/COMET/perplexity 当质量代理，自认自动指标与人类判断相关性弱，未测文体模仿、角色声音一致性；④**多样性类型**——只测 across-input，不测 per-input，显式排除风格/社会语言多样性；⑤**规模**——每任务仅 1 个数据集、10K 样本；模型只取 ~7B 一档（规模实验另用 Qwen2.5 到 32B），**GPT-4o/Claude 等闭源旗舰不在基准内**；⑥**解析器依赖**——依存树出自单一神经解析器，解析误差与"多样性"不可分离，WL 距离对树大小的敏感性未讨论。
