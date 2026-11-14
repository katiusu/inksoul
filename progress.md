# InkSoul 进度（v0.1.0 交付态）

## 阶段 1 · 研究（已完成）
- `research/literature_review.md`：47 条文献，L1 12 / L2 21 / L3 14（2026-11 补叙事学 6 条），含核实渠道、失败记录、
  TTCW 引用订正、主动放弃陈平 1987 的说明
- `research/research_findings.md`：7 条有证据结论 + 4 条「本项目假设」+ 4 项未解问题 + 研究→代码对照表
- `research/references.bib`：47 条；`research/notes/` 存检索脚本与逐篇笔记
- 设计文档：`docs/linguistic_analysis.md`、`docs/syntax_fingerprint.md`、
  `docs/generation_strategy.md`、`docs/evaluation_framework.md`、`docs/agent_architecture.md`、
  `docs/technical_roadmap.md`

## 阶段 2 · 核心引擎（已完成）
`src/inksoul/` 17 个文件：text_processor / normalizer（三遍消歧 + 动词表）/ nlp.backend（jieba|spaCy）/
fingerprint（加权编辑距离 + 星形分簇 + J1–J3 + 基线）/ diversity / style / narrative / reviewer /
llm（OpenAI 兼容 + 重试 + 脱敏）/ generation（规划→多候选→修订）/ analyzer / config / errors /
logging_setup / cli（6 子命令）/ data/verbs_zh.txt

## 阶段 3 · 测试（已完成）
`python3 -m unittest discover -s tests -p "test_*.py" -t .` → **Ran 77 tests ... OK**（1.6 s）

## 阶段 4 · 实验（已完成 v0 管线）
- 语料：8 篇人类（Wikisource 固定 revid + sha256）、6 篇模板拼接、8 篇修辞/机械标注
- 结果：人类复用率 0.436 / 阻断问题 0；模板 1.000 / 2.0；修辞误报 0.0、机械检出 1.0
- 报告：`experiment/reports/report.md`（含「不能从这个实验得到什么」与已知漏报）

## 阶段 5 · 交付（已完成）
- `docs/`：project_overview / architecture / algorithm_design / API_SPEC / installation / usage / limitations
- `skills/`：inksoul-writing、inksoul-diagnose（各含 SKILL.md + skill.md 指针）
- `examples/quickstart.py`：离线可跑（规划 + 诊断），有 Key 时生成正文
- `release/`：`inksoul-0.1.0-py3-none-any.whl`（sha256 fbc9351a…）、RELEASE_NOTES、INSTALL
- 安装实测：`pip install --target /tmp/inklib` → 44 文件；doctor 与 analyze 均正常

## 2026-11-14 · 八篇人工样本提炼与对白判据
- 来源：用户给的 21453.zip（8 篇 .mhtml，同一站点、同一亚类型的 R18 约稿）。抽取脚本与指标表见 `research/human_samples_8.md`，抽取结果在 `/tmp/s8/txt/`。
- 七篇非日记体样本：对白占比 0.11–0.36（中位 0.20），对话标签 0–2 次，短段（≤15 字）占 28%–60%，段均 15–34 字、句均 15–37 字；03 尤娜是日记体（0.03 / 73 字），作为反例排除。
- 新增判据「叙述替代对白」：`reviewer.py` `DIALOGUE_MIN_RATIO = 0.11`，ratio < 0.11 报 0.5、< 0.0605 报 0.65（阻断）；正文短于 400 字不判——短文本一句台词就能把比值从 0 拉到 0.3，`test_works_when_model_api_down` 就是被这条卡住后补的门限。
- 该判据补的缺口：改写稿 v4 台词占比 0.042（不足样本下界三分之一），此前能通过全部闸门，因为句法、去 AI 味、露骨层三道检查都不关心人物是否开口。
- 「情色」档补三条实测特征：节奏加「单句成段」；对话加「心里冒出的话直接用引号写出，不转述」；forbid 加「用叙述转述人物之间的交流」。
- SYSTEM_PROMPT 第 3 条补一句：人物心里翻腾的话写成他自己会说的那一句（可直接加引号），不由叙述者总结。
- 未做成判据的项（防过拟合）：短段占比 28%–60%、感叹号 1.8–11.6/千字——跨度与题材强相关，08 与 04 差 5 倍，硬卡会误伤。
- 测试：250 passed。样本 06 ratio=0.332 不触发；改写稿 v4 ratio=0.042 触发 0.65。
- 语域档按样本调整（同一批证据）：`口语都市` 加「内心话直接引语 + 动作/反应/台词各自成段」；`爽文节奏` 加「冲突当场用台词讲，关键转折用台词完成」；`冷硬悬疑` 加「不补语气标签 + 一个动作一段 + 禁叙述转述对话」。
- 新增第六档 `场景直写`：单句成段（段均 15–30 字）、群声也当台词、时间顺着场景走不回溯、物只写人物真碰到的；forbid 含整段心理分析、把同一场景拆成插叙。这档对应八篇样本的共同结构（不限于 R18），与「情色」的区别是前者管场景密度、后者管身体尺度。
- SYSTEM_PROMPT 第 4 条补：靠称呼和语气区分人物，不用「他说」「她道」标签承接连篇对白。
- CLI `--register` 三处 help 文本加「场景直写」。
- 验证：`build_plan` 实跑三档 prompt，文学书面仍留空（叙述声音取体裁默认「限制视角叙述，动作与感官优先」），口语都市与场景直写各自带上新条目。250 passed。
- 语域档改名（六个档名落在同一根轴上，各档都读得出「语体 + 推进方式」）：`爽文节奏→爽文快推`、`场景直写→场景速写`、`情色→情色直写`；文学书面/口语都市/冷硬悬疑不动。新增 `REGISTER_ALIASES`（旧名继续可用，避免已写进脚本的 `--register 情色` 失效），`build_plan` 先查别名再查预设，未登录档名静默落回文学书面（不把无效档名写进提示）。CLI 三处 help 同步。
- 验证：`build_plan(CreationBrief(theme=..., register="情色"), use_llm=False).register == "情色直写"`；"场景直写"→"场景速写"、"爽文节奏"→"爽文快推"、"不存在"→"文学书面" 均成立；250 passed；`diff -rq src/inksoul python/inksoul` 无差异。
- 情色直写档按三篇样本（01 憋尿 5087 字、05 群交 4102 字、06 直播 1863 字）重提炼。关键发现：三篇内部句长差异极大（01 对白驱动段均 21.5、05 长句被动段均 33.9、06 极短弹幕段均 14.9），**不能从风格上提炼**，只能提炼推进结构。新增三条互斥规则：①动作—反应绑定（一个动作后必须跟一个看得见的结果，不写「感到很舒服」）②越近越短（顶点前一段可只剩一个词）③比喻只允许人物自己说出口的，叙述者的比喻一律删。forbid 新增「快感像潮水一样涌来」这类现成比喻，「器官清单式罗列」细化为「只点部位不写动作和反应」。250 passed，mirror 已同步。

## 0.7.0-rc.2 · 六条 backlog 落地 + 两阶段生成（2026-11-14）

用户把这批要求合成一轮：「现在一起都做了，正好更新rc.2」。六条全部落地，判据见 `docs/backlog.md`。

- **1 强制载入 skills（前置条件，不是提示）**：`WritingAgent._check_skills_loaded(required, tool_steps)` 只认侦察阶段的工具调用记录——没有 `load_skill` 调用、或漏读 `required` 里任一项，直接抛 `InkSoulError` 并列出缺哪几个，不往下生成。`require_skills=False` 只给离线自测用（8 个假模型测试显式关掉，另加 4 个单测覆盖：缺 load_skill 抛错 / 完全没调用抛错 / 读到了放行 / 关掉开关不抛）。
- **2 不要废话**：`lib/index.js` 的 `inksoul_agent` 描述与 `POLICY_ZH` 加输出纪律——只给结论与正文，不写「好的/我来/以下是/已为你完成」，不复述请求，不加总结段；过程最多一行进度。
- **3 先出完再改（两阶段显式化）**：Phase A 一次出完所有候选、期间零修订；Phase B 逐段修订，每次修订记录「改前 rank → 改后 rank」写进 `RoundRecord.note`，报告里多一行「两阶段：Phase A 初稿 N 段零修订；Phase B 修订 M 次」。判据：Phase A 期间修订调用数为 0（结构上就没有调用点）。
- **4 情色最大尺度 + 不用专业部位名**：
  - (a) 情色直写档 `sentence_policy` 新增「尺度不设上限：动作、声音、体液、反应写到底，不淡出、不跳时间、不用事后叙述代替过程，高潮不回避」；`forbid` 新增解剖学名词黑名单（阴蒂/阴唇/阴道/内壁/黏膜/尿道/直肠/子宫），要求用人物自己会说的那个词。
  - (b)(c) 跨仓改 `/root/.agents/skills/prose-deai/scripts/check_intimacy.py`：`EXPLICIT` 拆成 `ANATOMY`（专业部位名，命中即违规，且不再放行别的项）与俗语实名层（小穴/穴口/肉棒/鸡巴/龟头/菊穴/后穴/骚逼…，仍是放行 CTX/NEAR 的依据）。此前解剖名既是「合法实名」又是放行依据，等于写得越专业越安全，方向反了。实测：「她的阴蒂被反复按着」「内壁一阵阵地收缩」判部位名，「小穴/肉棒/穴口」仍放行。
- **5 小说默认第三人称**：`CreationBrief.perspective` 改回空值 + `__post_init__` 按体裁补——小说类「第三人称限制视角」，散文「第一人称」（保留传统）。`build_plan` 的 `voice` 改为 `reg.get("voice") or preset["voice"]`，删掉 `brief.perspective or`：此前一填人称就把六个语域的 voice 全顶掉，是真回归。CLI 三处 `--perspective` 补 help 并标「留空按体裁」。视角行的落点是 `CreationBrief.prompt_block()`（`generation.py:353`、`agent.py:428` 都拼它），`StylePlan` 不设该字段——一度误加 `perspective=` 传参直接 TypeError，已回滚，254 passed。
- **6 不滥用顿号**：`narrative.py` 新增 `_dunhao(doc)` → `dunhao_per_kchar`（每千汉字）与 `dunhao_clause_count`（单句 ≥3 个顿号的句数），`NarrativeReport` 两字段进 `as_dict`。`reviewer.py` 新增规则 5c 与 `KIND_DUNHAO="顿号滥用"`：>8.0 判 0.65、>4.32 判 0.5、否则 ≥3 个清单句判 0.5。阈值来自八篇人工样本（0.00–4.32/千字，8 篇里 4 篇为 0，中位 0.62）。`SYSTEM_PROMPT` 新增第 6 条（原第 6 条顺延为 7）：并列拆短句或换段，一句里顿号最多两个。
- **注册表**：`SYSTEM_PROMPT` 现在 7 条。
- **测试**：254 passed（250 + 4 个 skill 闸门单测）。
- **版本**：package.json `0.7.0-rc.2` / pyproject.toml 与 `__init__.py` `0.7.0rc2`。
- **打包安装**：`npm pack` → `dsh-inksoul-0.7.0-rc.2.tgz`（38 files、148 KB），解包到 `/root/.dsh/plugin-src/dsh-inksoul`（保留 node_modules 与 pnpm-lock.yaml）；安装前备份 `/root/backups/dsh-inksoul-pre-rc2-1114.tgz`。
- **坑（记下来）**：tar 解包保留 mtime，而 0.7.0rc1→rc2 只差一个字符、文件大小不变，旧 `__pycache__` 的 mtime+size 校验照样命中——安装后 `import inksoul` 仍报 0.7.0rc1。修法：装完 `find python -name __pycache__ -exec rm -rf {} +` 再验版本。
- **生效范围**：python 引擎改动下一次工具调用即生效（每次 `runCli` 都新起子进程）；`lib/index.js` 的 `POLICY_ZH` 与工具描述是 apply 时注入的 systemPrompt section，需重启 DSH 服务才对已开会话生效。

## 0.7.0-rc.2 工作中 · 同作者 16 篇语料校准「情色直写」档（2026-11-14）
- 语料：`/sdcard/Documents/alhs-12657/`（alhs.xyz author 12657「雅雅」）16 篇，**138,822 汉字 / 6,074 段**，跨 2021-10 至 2023-05。前次提炼只用了 3 篇 1.1 万字。
- 指纹：段均 **22.9**（单篇 21.0–24.3，全书最长一段 93 字）、短段（≤15 字）36.2%、句均 20.3、对白段占 **28.9%**（1,680 段）且中位 **12 字**（31.2% ≤6 字）、对话标签 **0.13/千字**（16 篇里 6 篇为零）、顿号 **0.04/千字**（13 篇为零）、省略号 23.3/千字 > 感叹号 6.7、叙述层「我」0.8/千字（第三人称）、段首高频为转折词（而 170 / 可 170 / 不 145 / 只 129）。
- 「情色直写」档按 16 篇重写：rhythm 给出段落中位二十来字、上限九十，并把「越接近顶点段落越短」补成「内容不减——写清是哪个动作、什么反应，不是留白或省略到高潮」（修 backlog 第 4 条 (a)）；dialogue 改为「对白段占三成、一段一句、中位十来字」；sentence_policy 新增「同一个人一个称呼」「并列拆短句或换段，不用顿号串名词」；forbid 新增「用同义词轮换称呼同一个人」「用顿号串起并列的名词或动作」。
- 报告：`research/author_yaya_12657.md`（11 条可执行写法 + 与 AI 默认产出对照 + 边界：单作者单站，段长 22.9 是该作者常量、不是跨作者常量）。
- 测试：250 passed；`build_plan(CreationBrief(theme=…, register="情色直写"))` 实跑确认新条目进 prompt。

## 0.7.0-rc.1 · 六档语域 + 对白判据 + 模具层合并发布（2026-11-14）

本版把 0.6.2 系列的全部工作合并发布：模具配额层（molds.py + molds_baseline.json + inksoul_molds 工具）、八篇人工样本提炼、对白下限判据、六档语域（含改名与别名）、情色直写重提炼。
- 版本号：package.json `0.7.0-rc.1`（npm semver）/ pyproject.toml 与 `__init__.py` `0.7.0rc1`（PEP 440 等价写法）。
- 打包：`npm pack` → `dsh-inksoul-0.7.0-rc.1.tgz`，38 个文件、143 KB；解包安装到 `/root/.dsh/plugin-src/dsh-inksoul`（保留 node_modules 与 pnpm-lock.yaml）。
- 安装前备份：`/root/backups/dsh-inksoul-pre-rc3-1114-1717.tgz`。
- 验证：`lib/index.js` 动态导入成功（导出 Config/PY_ROOT/apply/name/runCli）；安装副本 `PYTHONPATH=…/python python3 -c "import inksoul"` → 0.7.0rc1；六档语域键齐全；molds 可导入；250 passed。
- 注意：lib/index.js 里 `inksoul_agent` 的说明为「预设要求 agent 用 load_skill 自己载入 prose-deai」，与 0.6.2 运行时的「已内联」不同，重启后生效。
- 生效需重启 DSH 服务。

## 0.6.2-rc2 · 语域维 + 提示词止血（2026-11-14）
- P0：SYSTEM_PROMPT 第 3 条不再把情绪交给环境承担（改为人物此刻要做什么、被什么挡住、身体先出现什么反应；环境只在他真的看向/摸到/闻到某物时才出现）；第 5 条禁止用数字、计数、日期、重复动作造仪式感。
- P1：新增 `REGISTER_PRESETS` 五档（文学书面/口语都市/爽文节奏/冷硬悬疑/情色），与体裁正交；`CreationBrief.register` / `StylePlan.register` / CLI `--register`（plan、generate、agent 三个子命令）。
- 「文学书面」刻意留空 voice/rhythm/dialogue，只追加 forbid 与 sentence_policy——默认语域不得顶掉体裁先验（`test_genre_differs` 就是这么失败的）。
- 对白目标改为下限：`对白占比 ≥0.12（人类池均值 0.23）`，不再给 p10–p90 区间（区间宽到无约束）。
- 修 min_severity 三套并存：agent 主路径 0.6→0.45，与 generation 默认一致；低段 0.3 保留。
- 文献：`research/literature_review.md` 新增 §8 主题六（事件索引/时距/意识呈现/人物网络），新条目标 L2/L3，DOI 未核实故 bib 不列 DOI；§9 缺口加第 9 条（叙事层中文零基线）。references.bib 41→47。
- 测试：250 passed。

## 未完成 / 下一步
1. 阈值标定（人工标注 ≥200 对小句 + ≥50 篇机械感判定）
2. 真实模型实验 C/D/F 正式版（需 API Key）
3. 零形回指与人物语言辨识度
4. `gen_model_samples.py` 尚未实现（预留接入点）

## 0.6.2-rc1 · 模具判据校准（进行中）
- 新增 `src/inksoul/molds.py` + `data/molds_baseline.json`（1902 段 1000 字窗，19 项判据）+ CLI `molds`
- 判定改为复合偏离 z > 人类段 p95（0.631）；LOBO 假失败率 6.2%，AI 稿件 15/15 越线
- 提示词规则 12/19/20 重写：molds 只诊断、超阈改贡献最大 2 项、最多 2 轮；撤回 22.8×/16.6× 等旧倍数
- 版本策略：预发布号 0.6.2-rc1，等待用户确认再转正式版
- 2026-11-14 预设内联写作规范：`AgentPreset.skills` + `skillpack.SkillPack`（6000/2600 预算、
  节切分、缺文件明示）；`inksoul presets [--json|--prompt]`；`--no-skills` / `--skills`。

## 0.7.0-rc.2 · 同伴审查修复（2026-11-14）
- BUG-1 PTC 无 `load_skill`：`src/inksoul/ptc.py` 沙箱补 `load_skill(name, section)`；沙箱 box 用 `__new__` 绕过 `__init__`，补 `box.loaded` 与 `box.skill_roots`（缺后者 `_load_skill` 直接 AttributeError）；`ProgramResult.skills` 回传并写回父进程 `box.loaded`。
- BUG-2 阻断项不可定位：`src/inksoul/reviewer.py` 新增 `_sample_clause(doc, pred)`，5b/5c 的 `issue.text` 改回正文原文（指标串进 evidence），`generation._locate` 才找得到；5c 补 400 字门槛与单句顿号数 `max_per_clause`（≥4 阻断）。
- BUG-3 技能闸门只验字符串：`src/inksoul/agent.py:_check_skills_loaded` 改查 `ToolBox.loaded`（只有真读到正文才记账），无工具面才退回调用记录；`len(tool_steps or [])` 容错 None。
- `check_intimacy.py`：新增 `ANATOMY_AMBIGUOUS`（内壁/子宫/尿道/直肠/黏膜），同行无性语境时不判部位名；同步退出码与 HARD_RE 的过时注释。
- `/root/deslop/run_gates.sh` 命中计数正则改 `^\s*[0-9]+\s+\[(部位名|强禁|语境)\]`（原 `^(HARD|HARD_RE|CTX)` 恒 0）。
- 验证：254 passed；PTC 实跑 `load_skill("prose-deai")` → `skills=['prose-deai']`、`box.loaded` 同步；111 字含 12 顿号不再阻断，长文本 5b/5c 的 text 均可在正文定位。
