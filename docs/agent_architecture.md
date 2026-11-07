# InkSoul Agent 架构

> 版本：v1（研究阶段）
> 形态：**dsh 插件**（Cordis 插件模块，TypeScript/ESM），内部以 **Python 子进程**承担 NLP 与统计。
> 本文所有平台能力断言都标注了证据位置（源码行号来自本机 `/usr/local/lib/node_modules/@deepseek-ai/dsh/`，调研过程见 `research/dsh_plugin.md`）。

---

## 1. 定位：它是什么，不是什么

| 是 | 不是 |
|---|---|
| 一个**生成期的结构控制器**：规划 → 候选生成 → 结构评估 → 局部重写 → 审查 | 不是 AI 文本检测器 |
| 一个**可解释的诊断器**：输出"哪几句复用了同一骨架""节奏太平在哪一段" | 不是"润色/降重"工具 |
| 一个**插件**：在 dsh 里提供工具、命令、上下文与规范 | 不是独立应用，不做 GUI（v1） |
| 一个**人类作者的副驾**：所有判定都可回退到人 | 不是自动写作机（v1 明确 human-in-the-loop） |

**核心不变量（Invariant）**：InkSoul 的每一次干预都必须是**可解释、可撤销、可度量**的。任何"模型说了算"的环节都必须留下记录，否则不得上线。

---

## 2. dsh 平台的真实能力边界（决定了架构形状）

### 2.1 能做什么（有代码证据）

| 能力 | 机制 | 证据 |
|---|---|---|
| 注册工具 | `ctx.tools.register(defineTool({name, description, parameters, output:{schema,render}, execute}))` | `dsh-tools/lib/index.js:839`（`defineTool`）、`:2799`（`tools` 服务） |
| 注入常驻规范 | `ctx.systemPrompt.section({name, order, text})` | `dsh-system-prompt` 服务 |
| 注入**动态**上下文 | `ctx.systemPrompt.context({name, order, text: (context)=>string})`，每步重新求值、可按 agent 门控 | 同上 |
| 注册 skill（按需加载，不占常驻上下文） | `ctx.skills.register({name, description, whenToUse, content, resourceBase})` | — |
| 注册斜杠命令 | `ctx.commands.register({definitionId, name, description, input?, handler})` | `dsh-commands/lib/index.js:266` |
| 拦截/改写工具调用 | waterfall：`tools/pre-execute`（:3325）、`tools/execute`（:3434）、`tools/post-execute`（:3607）、`tools/result`（:3520） | `dsh-tools/README.md` Extension points |
| 改写整份 prompt | waterfall `system-prompt/assemble` | `dsh-system-prompt/lib/index.js:398` |
| 每步前决策 | waterfall `agent/pre-step` | `dsh-agent-loop/lib/index.js:911` |
| 起 Python 子进程 / 读写文件 / HTTP | 插件跑在宿主 Node 进程内，可直接 `import 'node:child_process'`、`node:fs`、`fetch` | — |
| 结构化结果渲染 | `output.schema` + `output.render`；`presentCall/presentResult/presentationMeta/card` | — |

### 2.2 不能做什么（同样有证据，或至少"未找到证据"）

1. **没有 token 级流式改写 hook**。`agent/assistant-stream` 只作为观察型事件出现（`ctx.on`），未找到 waterfall 版本。→ **去 AI 味必须在生成完成之后做，不能边生成边改。** 这一条直接否掉了"实时去味"的产品叙事。
2. **没有公开 API 让插件自己发起一次模型对话**（未在 `dsh-agent`/`dsh-agent-loop` 找到 `send`/`submit` 之类方法）。→ **编排必须走"注册工具 + 让主 agent 调用"**，或注册 subagent provider（`subagent/provider-added` 事件存在，挂载点未验证）。
3. **插件不能决定 UI 长什么样**（除 client 插件）。官方 Web 端不消费 `presentCall/presentResult`。→ v1 的"报告"必须是 **markdown 文本 / 结构化 schema**，不是自绘面板。
4. **不能假设工作区是普通文件系统**。本机工作区在 `/sdcard`（sdcardfs），`write`/`edit` 的原子发布报 `EINVAL: 无法原子发布文件`。→ 插件写稿必须走 `bash`/`python3`，或先写 `/tmp` 再 `mv`。
5. **热重载会丢内存态**。所有会话级状态必须落盘。

### 2.3 由边界反推出的三个架构决定

| 决定 | 理由 |
|---|---|
| **D1：审查与重写是"事后工具"，不是"流中拦截"** | 没有流式 hook。且事后做反而更好：能看到完整文本的结构分布，而 token 级只能看局部 |
| **D2：控制回路由主 agent 驱动，插件只提供"手和尺"** | 插件不能自发起对话。→ InkSoul = 一组工具 + 一段规范 + 一个命令，由 agent 自己按 SOP 串联 |
| **D3：重型分析离线/异步，在线只跑轻量** | L3 WL 核在 10 万字上需 10–60 s（`syntax_fingerprint.md` §10），不能阻塞每一步 |

---

## 3. 架构总览

```
┌──────────────────────────── dsh 宿主（Node） ────────────────────────────┐
│                                                                          │
│  systemPrompt.section  ← 写作宪法（≤800 字，静态）                        │
│  systemPrompt.context  ← 项目状态切片（每步读 JSON，按 agent 门控）        │
│  skills.register       ← 体裁规范 / 去味规则 / 审查 rubric（按需加载）     │
│  commands.register     ← /inksoul（状态、开关、基线标定）                  │
│                                                                          │
│  tools: [plan_scene] [gen_candidates] [fingerprint] [stylometry]          │
│         [narrative_scan] [voice_check] [revise_span] [review_report]      │
│                                                                          │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ spawn(python3, ...)  stdin/stdout JSON
┌───────────────▼──────────────────────── InkSoul Engine（Python） ─────────┐
│                                                                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────────────┐  │
│  │ 预处理层    │→│ 六个分析器  │→│ 评分与重排  │→│ 报告生成           │  │
│  │ tokenize   │  │ syntax     │  │ score()    │  │ report.md/json    │  │
│  │ clause-split│ │ style      │  │ violations │  │ diff view         │  │
│  │ zero-anaph │  │ narrative  │  │ budget     │  │                   │  │
│  │ pos/dep    │  │ voice      │  └────────────┘  └───────────────────┘  │
│  └────────────┘  │ lexical    │                                          │
│                  │ review     │  ← 依赖：jieba / spacy(zh) / networkx    │
│                  └────────────┘     / apted；LTP 待 torch                 │
│                                                                           │
│  基线库（离线构建，只读）：genre_baseline/{novel,essay,webnovel}/...      │
└───────────────────────────────────────────────────────────────────────────┘
                │
       稿件与状态（磁盘，插件自有目录）
       <dshHome>/inksoul/{project}/state.json, scenes/*.md, reports/*.md
```

### 3.1 数据流（一次写作）

```
1  plan_scene(state, outline)        → scene_card.json（含信息释放表、结构预算）
2  gen_candidates(scene_card, k=3)   → 3 段正文（由主 agent 生成，插件不做生成）
3  fingerprint(text)                 → {clauses, skeletons, clusters, coverage}
4  score(fp, budget, profile)        → {total, terms}；选优
5  revise_span(text, target_clause)  → 由主 agent 重写指定小句
6  consistency_check(new, old, state)→ 通过/回退
7  review_report(all)                → report.md（人读）
```

**注意第 2 步**：**插件不调用模型**。它把"要生成什么、以什么策略生成"变成结构化指令交给主 agent。这是 D2 的直接后果，也是本项目与"自建 agent 框架"的关键区别。

---

## 4. 七个模块的接口契约

每个模块都必须能被独立调用与独立测试（这是高内聚低耦合的硬要求）。下面给出**输入/输出的 JSON 契约**，这是架构的实质内容。

### 4.0 九项规格总表（任务要求逐项覆盖）

任务书要求每个模块说明九项：理论依据、对应论文、输入、输出、实现方法、可用开源工具、计算成本、技术局限、与其他模块的关系。总表如下，细节在后文各小节。

| 模块 | 理论依据 / 对应论文 | 输入 | 输出 | 实现方法 | 开源工具 | 计算成本 | 技术局限 | 与其他模块关系 |
|---|---|---|---|---|---|---|---|---|
| **M1 Syntax Diversity Engine** | 依存句法 + 图核：Collins \& Duffy 2001；Tai 1979（TED）；Guo 等 2025（WL 路线、recall 范式）；FastKASSIM 2023；沈家煊 2012（零句/流水句） | 文本 + 体裁 + 归一表版本 + 窗口 | 小句列表（骨架串 L1 / 依存边 L2 / WL 指纹 L3）、重复簇、四项指标、J1–J4 判定 | 自切小句 → 归一 N1–N10 → 骨架串 → 依存边集 → WL 子树核 + 加权编辑距离 → 跨段聚类 | `jieba`、`spacy`+`zh_core_web_sm`、`networkx`、`apted` | **10 万字 ≈ 2–4 min 解析 + 10–60 s 核计算**（解析 214.6 句/秒实测） | 解析器把流水句压成单根树（实测）；分词错误污染骨架；无中文参考分布 | 向 M6 供 `forbidden_skeletons`；向 M7 供 `anti_repetition` 门禁；依赖 M2 的体裁判定 |
| **M2 Stylometric Analyzer** | Biber 1988（多维特征）；Reinhart 等 2025（66 特征出现率）；Sourati 等 2026（方差收缩） | 文本 + 体裁 | 66 维特征向量、体裁最近邻与 z 分数、可解释 flags | 特征计数 → 按体裁基线算 z → 按 \|z\| 排序输出 | 纯 Python + `spacy` POS + `jieba` | **秒级（O(n)）** | **中文无已发表人类基线**，必须自建；特征选择带理论负载 | 为 M1/M3/M5 提供体裁基线与 z 标尺；向 M6 提供预算 |
| **M3 Narrative Analyzer** | Li 等 2026（叙事扁平化三维：thematic motion / affect / diversity）；Wilmot \& Keller 2024（悬念=不确定性消减）；Chakrabarty 等 2024（过度解释） | 正文 + （可选）大纲/场景卡 | 场景表（视角/进出情绪/信息释放与被隐藏）、节奏序列、过度解释率、扁平化指标 | 规则 + 词表 + 场景切分（人工或大纲）→ 序列统计 | 规则 + 词表；可选句向量 | **秒级**（情感分类需小模型，可选） | **场景边界检测无可靠方法**；"过度解释"高度依赖体裁 | 向 M6 供节奏与信息释放预算；向 M7 供 structure/rhythm 报告 |
| **M4 Character Voice Engine** | 作者归属与文体计量：Huang 等 2025（综述）；Przystalski 等 2026（短样本可分） | 引语列表（人物→台词） | 人物语言档案 + 可辨识度（留一准确率 − 随机基线） | 抽引语 → 分组 → 组内/组间特征距离 + 简单分类器 | `sklearn`（可选）或纯统计 | **秒级** | **单角色样本常仅 10 句**，统计不可靠 → 建议 ≥8 轮才出结论 | 向 M6 供 `character_cards`；向 M7 供 voice 报告 |
| **M5 Lexical Analyzer** | Guo 等 2025（TTR/unique-n）；Juzek \& Ward 2024（过度表征 "delve" 类） | 文本 | TTR / MATTR（窗口 50）/ MSTTR / MTLD / HDD（近似） | 滑窗与分段统计 | `jieba` | **秒级** | 设计稿里的 Yule's K、distinct-2、MATTR-500、套语密度、PMI 搭配新颖度**尚未实现** | 向 M7 供 lexical 报告 |
| **M6 Generation Controller** | `generation_strategy.md` S1–S6 对比；Guo 2025（温度甜点 t=0.6）；Sanchez 2023（过约束→生硬）；Li 2026（控方差非均值） | 场景卡 + 状态 + 人物档案 + M1–M5 诊断 | **结构化生成指令**（开场类型、预算、禁用骨架、必含项、锚点上下文） | 编排器：`systemPrompt.context` 每步注入 + 工具返回指令对象 | dsh `systemPrompt.context`、工具返回值 | **零额外推理**（纯编排） | **无法保证模型服从**；自然语言形容会被当内容复述 → 必须用结构化字段 | 消费 M1–M5 全部输出；把重写请求派回 M7 |
| **M7 Literary Reviewer** | Chakrabarty 等 2024（TTCW 14 项）；Fein 等 2025（LitBench 78% 上限）；Porter 2024（读者判断 κ=0.005） | 正文 + 上游全部报告 | 硬门禁（一致性/反重复）、软报告、人评包（盲配对 + rubric） | 规则门禁 + 分项报告；**不输出单一总分** | 规则；LLM 评委须本地重验 | **规则秒级**；人评为外部成本 | **不自动判优**：与专家 κ≈0、奖励模型上限 78% | 消费全部模块输出；产出重写请求回 M6 |


### 4.1 Syntax Diversity Engine（句法多样性引擎）

```jsonc
// in
{"text": "...", "lang": "zh", "genre": "novel",
 "norm_table": "v1", "window": 20}
// out
{"clauses": [{"id":0,"text":"她没有回答","span":[0,5],"skel":"PRON NEG V",
              "l2":[["nsubj","PRON","V",1],["neg","NEG","V",1]]}],
 "clusters": [{"skeleton":"PRON NEG V ， ADV_LIM V *","members":[3,17,42],
               "para_spread":3,"gap_cv":0.31}],
 "metrics": {"skeleton_entropy":4.12,"reuse_rate":0.077,
             "coverage_vs_baseline":0.63,"clause_len_cv":0.41},
 "suspects": [{"cluster_id":0,"judgements":{"J1":"pass","J2":"fail","J3":"pass","J4":"todo"}}]}
```
- 理论依据：依存句法 + 图核（Collins & Duffy 2001；Tai 1979；Guo 等 2025 的 WL 路线；FastKASSIM）。
- 依赖：`jieba`（分词）→ `spacy zh_core_web_sm`（UD 依存）→ `networkx`（WL）/`apted`（TED）。
- 成本：10 万字 ≈ 解析 2–4 min（214.6 句/秒实测）+ WL 10–60 s。
- 局限：解析器把流水句压成单根树（实测），小句切分必须自己做；分词错误会污染骨架。

### 4.2 Stylometric Analyzer（文体计量）

```jsonc
// out
{"feature_vector": {"mean_word_len":4.3,"ttr":0.41,"mattr500":0.72,
                    "shannon_entropy":6.1,"punct_rate":0.098,
                    "func_word_dist":{...},"constructions":{"ba":0.012,"bei":0.004,
                    "serial_verb":0.031,"pivotal":0.006,"existential":0.019}},
 "genre_distance": {"nearest":"novel_literary","z":1.42},
 "flags": [{"feature":"explicit_conj_rate","z":2.8,"note":"形合化偏高"}]}
```
- 理论依据：Biber 的多维特征体系；Reinhart 等（2025）的 66 特征出现率范式（英语可直接对标其人类率表）；Sourati 等（2026）的方差收缩。
- 输入：文本 + 体裁。
- 输出：特征向量 + 与体裁基线的 z 分数 + 可解释 flags。
- 成本：O(n)，秒级。
- 局限：**中文没有已发表的对应人类基线**，必须自建（`evaluation_framework.md` 实验 0）；特征的选择本身带理论负载。

### 4.3 Narrative Analyzer（叙事分析）

```jsonc
// out
{"scenes": [{"id":0,"span":[0,1200],"pov":"third_limited","enter_emotion":"警惕",
             "exit_emotion":"松动","info_released":["他撒过谎"],
             "info_withheld":["为什么"],"functions":["环境","动作","内心","总结"]}],
 "rhythm": {"sent_len_seq":[...],"lag1_autocorr":0.42,"clause_cv":0.33},
 "over_explanation": {"explicit_emotion_rate":3.1,
                      "para_final_summary_rate":0.21},
 "function_ngram_entropy": 1.83,
 "flatness": {"thematic_cv":0.091,"affect_share":0.29}}
```
- 理论依据：叙事学（视角/信息释放/场景功能）+ 计算叙事学（Piper 等的综述；情感弧线）；**Narrative Flattening（Li 等 2026）的三个句级维度**给了可直接复用的度量（thematic motion / affective prevalence / linguistic diversity），且其结论"后训练压缩方差"正是本模块要报的量。
- 成本：规则 + 词表，秒级；情感分类需小模型（可选）。
- 局限：**场景边界检测没有可靠方法**，需人工/大纲提供；"过度解释"的判定高度依赖体裁。

### 4.4 Character Voice Engine（人物语言）

```jsonc
// out
{"characters": [{"name":"林","turns":14,
                 "profile":{"mean_turn_len":11.2,"q_marker_rate":0.14,
                            "sentence_type_dist":{"decl":0.6,"quest":0.3,"imp":0.1},
                            "lexical_field":["收","拿","放"],
                            "avoidance":"沉默/反问"}}],
 "separability": {"acc":0.71,"baseline":0.33,"lift":0.38}}
```
- 理论依据：作者身份识别/文体计量（可迁移性：同作者内文本可分 → 同人物内台词应可分）。
- 实现：抽取引语 → 按人物分组 → 组内/组间特征距离 + 简单分类器（留一验证）。
- 成本：秒级（sklearn 可选，或纯统计）。
- 局限：**短对话样本太少**（一个角色可能只有 10 句），统计不可靠。→ 建议只在 ≥8 轮时给结论。

### 4.5 Lexical Analyzer

```jsonc
{"mattr500":0.72,"yule_k":118.4,"distinct2":0.61,
 "cliche_hits":[{"phrase":"嘴角勾起","count":3,"spans":[...]}],
 "collocation_novelty":{"mean_pmi_z":-0.8},
 "metaphor":{"trigger_rate":0.9,"vehicle_fields":{"自然":0.6,"身体":0.3},
             "cross_domain_distance":{"mean":0.41}}}
```
- 理论依据：词汇多样性（MTLD/MTLD 类指标在文内更稳定；TTR/unique-n 已被 Guo 等使用并指出全局版优于移动平均）；过度表征现象（Juzek & Ward 2024）。
- 成本：秒级。
- 局限：套语表需要自建且会过时；PMI 需参考语料。

### 4.6 Generation Controller（生成控制）

**不是**一个分析器，而是**编排器**：

```jsonc
// in: 场景卡 + 状态 + 档案 → out: 给主 agent 的生成指令（结构化）
{"opener":"action","budget":{...},"forbidden_skeletons":[...],
 "must_include":["零主语链≥1","短句≤4字≥1"],
 "anchor_context":{"prev_2_sentences":"...","character_cards":[...]}}
```
- 实现方式：`systemPrompt.context` 注入（每步）+ 工具返回指令对象。
- **关键约束**：注入内容必须是**结构化字段**，不是自然语言形容词。理由：自然语言形容会被模型当内容模仿/复述，且不可验证（`generation_strategy.md` §7.4）。
- 成本：零额外推理；纯编排。
- 局限：无法保证模型服从；只能通过"生成后检查 + 重写"闭环兜底。

### 4.7 Literary Reviewer（文学审查）

```jsonc
{"hard_gates":[{"id":"consistency","pass":true},{"id":"anti_repetition","pass":false,
                "detail":"小句 42/61 同骨架"}],
 "soft_report":{"structure":{...},"rhythm":{...},"voice":{...}},
 "human_review_packet":{"blind_pairs":[...],"rubric":"TTCW-14"}}
```
- 理论依据：Chakrabarty 等（2024）的 TTCW 14 项 rubric（专家通过率 84.7% vs 模型最好 4.19/14）；**禁止**用检测器概率作质量分（`linguistic_analysis.md` §5.4）。
- 成本：规则秒级；人评是外部成本。
- 局限：**本模块的产品价值在"给人看"，不在"自动判优"**。自动判优的上限见 LitBench：最佳奖励模型 78%，最强零样本裁判 73.1%（Fein 等 2025）。

---

## 5. 状态与持久化

```
<dshHome>/inksoul/
  _active.json                 # 当前项目指针
  <project>/
    state.json                 # 世界/人物/伏笔/时间线（结构化）
    outline.md                 # 人工维护
    scenes/s017.json           # scene_card
    drafts/s017.v3.md          # 版本化稿件
    reports/s017.report.md     # 审查报告
    baseline/genre.json        # 本项目自定义体裁基线（可选覆盖）
```

规则：
- **所有状态 JSON 带 `schema_version`**，读时校验；不匹配则拒绝并提示迁移。
- 写入一律"临时文件 + rename"，避免 sdcardfs 的原子发布失败。
- 报告只追加不覆盖（用时间戳后缀）。

---

## 6. 三条关键设计决策（ADR）

### ADR-1：为什么不做"去 AI 味"这个词

**决定**：产品与代码中禁用"去 AI 味"作为功能名，统一为"结构诊断与修整"。

**理由**：① 平台没有流式 hook，做不到实时去味；② 更重要的，"去 AI 味"把目标定义为**逃避检测**，而本项目明确不以检测为目的（`linguistic_analysis.md` §5.4 已给出证据说明检测器不是质量尺）；③ 用"去味"命名会诱导实现走向"改词表/换同义词"的表面工程。

### ADR-2：为什么审查不输出单一总分

**决定**：所有报告都是**多维向量 + 分体裁 z 分数**，不合并为一个 0–100 分。

**理由**：① Guo 等（2025）证明"句法多样性"与质量负相关，单维度合成必然错；② Narrative Flattening 的核心发现是"要测的是方差不是均值"，方差无法与均值合成；③ 单一总分会让作者优化那个数字而不是作品（Goodhart）。

### ADR-3：为什么基线必须是"分体裁 + 可重算"的产物

**决定**：`genre_baseline/` 是**构建产物**（脚本 + 版本号 + 语料清单），不是手调常数。

**理由**：Rallapalli 等（2026）发现"体裁效应 > 来源效应"→ 不按体裁分开，指标全部失真；Li 等（2026）发现"用网文当人类基线会低估扁平化"→ 基线语料的选择本身决定结论。手调常数不可审计，也无法随语料更新。

---

## 7. 替代架构：三个方案与一个建议

按研究原则 10（允许推翻原设想），这里并列三个可行形态，并给出推荐。

| 方案 | 形态 | 优点 | 缺点 | 适用 |
|---|---|---|---|---|
| **A. 全插件** | TS 插件 + Python 子进程 + 工具 + 命令 + 上下文注入 | 体验最好；状态可跨会话；能拦截危险工具 | 工程量大（~2–3 周）；依赖宿主 API（有版本漂移风险）；调试链路长 | 长期产品 |
| **B. skill + 脚本** | 一份 `SKILL.md`（写作 SOP）+ 若干 Python 脚本，靠 agent 主动调用 | 极轻（1–2 天）；零宿主 API 依赖；可移植到任何 agent | 无状态、无门禁、靠模型自觉；无法强制"先规划后写" | **v0 立即验证** |
| **C. 外部服务** | 独立 HTTP 服务 + 一个薄插件做代理 | 语言自由；可复用现有 Python 生态 | 部署成本；本机资源受限；离线不可用 | 团队化后 |

**建议（分阶段，不推翻 A）**：

1. **v0：先做方案 B**。用 B 在真实写作上验证"结构诊断是否真的有用"——**如果诊断给作者看了之后，改出来的文本人评没有改善，那么 A 再精致也没意义**。这是本架构最重要的可证伪点。
2. **v1：方案 A 的最小集**：只做 3 个工具（`fingerprint` / `narrative_scan` / `review_report`）+ 1 段常驻规范。不做命令族、不做面板。
3. **v2：补 Generation Controller 的编排闭环**（依赖 v0 阶段积累的"改与不改"对比数据）。

---

## 8. 失败路径与降级（必须实现）

| 失败 | 降级行为 |
|---|---|
| Python 环境缺失 / 依赖装不上 | 退化为"纯词表版"（词汇指标 + 句长统计），报告里明确标注 `degraded: true` |
| 解析器输出异常（空树/超长句） | 跳过该句并计数，报告 `parse_fail_rate`；> 15% 则整个句法模块返回不可用 |
| 体裁基线未构建 | 只给原始值，不给 z 分数；**不**用"全局均值"冒充基线 |
| 模型不服从配额 | 不重试同一指令；记录到 `compliance_log`，连续 3 次失败则停止该场景的结构控制 |
| 局部重写破坏一致性 | 回滚到改前版本，记录失败片段供人工处理 |

---

## 9. v1 范围（明确不做什么）

- 不做 GUI 面板；不做 web UI。
- 不做模型调用/训练/微调。
- 不做多语言（只有中文；英语仅作为"有现成基线"的对照实验）。
- 不做"整本长篇自动生成"；只做**单场景级**的结构控制与人审辅助。
- 不接入任何 AI 检测 API。

