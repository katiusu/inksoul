# InkSoul

**给 AI Agent 的中文写作插件。** 模型写中文时，手里通常只有「感觉」；InkSoul 给它机械线索：
能测句法骨架、能比同质度、能过文风闸门、能自己改到达标。

```
npm:      dsh-inksoul
harness:  DeepSeek Harness（DSH）0.2.1 与 0.2.2 均可
入口:     lib/index.js  ← 八个工具 + 一段写作规范提示
引擎:     python/inksoul（随包分发，零第三方依赖）
```

八个工具：五个诊断/度量（analyze / corpus / style / markers / molds）、一个闸门、一个生成闭环、一个自检。

## 装

```bash
dsh plugin --profile web add dsh-inksoul      # 从 npm 装
dsh plugin --profile web add /path/to/repo    # 从本地目录装
```

装完重启 dsh web，模型工具面里就会多出下面这些工具（都叫 `inksoul_*`），并在系统提示里附带一段
`inksoul:policy` 写作规范。**不需要** `pip install inksoul`，插件靠 `PYTHONPATH` 把包内源码指过去；
`jieba` 缺失只降级不分词，不会崩。

## 工具

| 工具 | 什么时候用 | 耗时 |
| --- | --- | --- |
| `inksoul_analyze` | 量化一篇中文文本的句法骨架、句长分布、与体裁基线的距离；顺带给出句数/段数/对白占比/顿号密度 | 秒级 |
| `inksoul_corpus` | 一批稿子之间两两骨架相似度——判断是不是同一副骨架反复复用 | 秒级 |
| `inksoul_style` | **段级**风格距离（轻量，只回距离 + 六维 z + 该改哪两维）。正文按 800–1000 字一段写、每段跑一次，距离 >1.30 就重写这一段；整章一次生成实测距离 2.10 | 约 1 秒 |
| `inksoul_markers` | AI 味标记族密度（中文 Biber 清单：名词化/定语链/并列/被动/连接词/抽象/比喻/四字格），对照人类网文 p50/p90/p99 | 秒级 |
| `inksoul_molds` | 句法模具配额（小说体）：22 项结构模具密度（坐标定位/轨迹/时间刻度/把字句/序数/量词/动作串/引号对白…），逐项算段级 z、合成复合分，超过人类段 p95（0.631）才算偏离 | 秒级 |
| `inksoul_gate` | 对定稿跑文风闸门（去 AI 味精查），拿回逐条命中项；`preset=markers` 是随包内置的纯 Python 闸门 | 1–90 秒 |
| `inksoul_agent` | 要真的写出正文：规划→出完全部候选→分段修订→闸门，闭环 | 分钟级 |
| `inksoul_doctor` | 环境自检；任何报错先跑它 | 1 秒 |

## 语域：同一体裁写出不同声音

`--register` 与 `inksoul_agent` 的 `register` 参数是一条**独立于体裁**的轴（体裁决定「写什么」，
语域决定「怎么说话」）：

| 语域 | 落点 |
| --- | --- |
| `文学书面` | 默认档。不覆盖体裁自带的叙述声音，只追加两条禁令（整段无事件的景物描写、把环境当情绪容器） |
| `口语都市` | 贴近日常说话的短句，对白占三成以上，靠称呼和口头禅区分人 |
| `爽文快推` | 短句密集、每段至少一个推进点，冲突当场用台词讲 |
| `冷硬悬疑` | 短句、省略连词、留断点，不解释动机 |
| `情色直写` | 一次刺激一段、越近越短但内容不减；不设尺度上限，禁器官清单与现成比喻，身体用俗语不用解剖名 |
| `场景速写` | 单句成段、段均 15–30 字，物只写真正碰到的，群声也当台词写 |

旧名 `爽文节奏` / `场景直写` / `情色` 仍可用（内部别名映射）。

## 结构判据：句子好看不等于小说

闸门除了句法层，还查两件「像不像人写的」的硬指标，源头是 16 篇同作者人工样本（13.9 万汉字）
与 8 篇跨作者样本的实测分布：

- **对白下限**：正文 ≥400 字时对白占比低于 **0.11**（八篇样本 p10）就报 0.5–0.65。通篇没有人物开口，
  句子再漂亮也是叙述者在替所有人说话。
- **顿号滥用**：每千汉字 >4.32（样本 p90）告警、>8 判阻断；同句出现 4 个以上顿号串名词且整句无动作也算阻断。
  八篇样本里有四篇全篇零顿号。

这两条都写进 `reviewer.py` 的 issue.text（正文原文），能被 `_locate` 找到，所以修订阶段真的改得动。

## 分段写作流程（预设里是硬约束）

1. **动笔前**：载入 `prose-deai` 与项目 `skills/inksoul-writing`、`skills/inksoul-diagnose`，回复里列出「已载入：…」，否则不算动笔资格。
   走 `inksoul agent --preset long|short|deai|publish|rewrite` 时，system 里只放一句「用 load_skill 载入 prose-deai / story-xxx」的要求，规范正文由 agent 在侦察阶段自己 `load_skill` 读；引擎核对的是**工具调用记录**（PTC 模式下读程序源码），模型自称「已读过」不算数，漏读任一项直接拒绝生成。`draft`/`cover` 不要求载入。
2. **逐段**：800–1000 字一段 → 落盘 `partNN.md` → `inksoul_style` → `NEAR` 进下一段，`FAR` 按「动作：」那两维只改这一段（最多 3 轮，段内 ≤1.50）。
3. **收尾**：段落全过后合并成章 → `inksoul_gate` 拿 `VERDICT: PASS` + `RECEIPT` → 交付时给「段号/字数/距离/超阈维度/重写次数」表。

生成闭环是**两阶段**的：Phase A 先把所有候选写完、期间禁止修订动作；Phase B 再分段修订。
早期版本边写边改，结果模型在第一段就陷进自我校对，后面的段落质量一路下滑。

为什么不是整章后验：人类池是按 900 字标定的，整章一次生成实测骨架复用率 z +4.57、距离 2.10（人类 p90 1.29）；同一段内容按段改写能压到 1.45。

## 为什么是插件而不是技能

技能只能塞说明书，还得先在本机装好 CLI、配好 PATH；插件把引擎一起打进 npm 包，
模型拿到的是一等工具：直接调、直接拿结构化结果、失败也能读懂原因。

## 结论口径（写进 `inksoul:policy`，照着说）

- 骨架相似度高 → 说「骨架复用明显」，不说「抄袭」；
- 偏离基线 → 说「偏离该基线分布」，不推「非人类」；
- 闸门未 PASS → 不当定稿交付，按命中条目改完重跑。

## 配置

`cordis.patch.yml` 里的默认片段：

```yaml
- id: inksoul
  name: dsh-inksoul
  config:
    enabled: true
    python: ''        # 留空 = python3 或 INKSOUL_PYTHON
    workdir: ''       # 留空 = 进程 cwd
    timeoutMs: 600000
    maxOutputChars: 20000
```

`inksoul_agent` 要调模型，配置在 `~/.dsh/inksoul/config.json`（或 `~/.inksoul/config.json`）：

```json
{ "model": { "base_url": "https://api.deepseek.com/v1", "api_key": "sk-…", "model": "deepseek-chat" } }
```

## 引擎与 CLI

引擎是纯 Python（`src/inksoul`，装进包时复制到 `python/inksoul`），也仍可单独当 CLI 用：

```bash
pip install -e .
inksoul doctor
inksoul analyze draft.txt --json
inksoul gate draft.txt --preset deslop
inksoul agent "写一段雨夜重逢" --preset deai --out draft.md
inksoul plan "写一段雨夜重逢" --register 情色直写     # 六档：文学书面/口语都市/爽文快推/冷硬悬疑/情色直写/场景速写
```

引擎细节（指纹算法、基线、PTC 工具面、闸门接线）见 [ENGINE.md](ENGINE.md)。

## 兼容性

- `dsh.engines.dsh` = `>=0.2.0-rc.1`。
- DSH 0.2.2 把 `list_agents` 从独立插件并进主包并移除了 `tool-subagent-control/list-agents` 子路径导出，
  0.2.1 则相反。插件用 `lib/list-agents-compat.mjs` 运行时探测：能解析到那个子路径才挂载，否则静默跳过。
  两个版本都能正常建会话。
- 插件里 Python 引擎是**热生效**的（每次调用起新进程）；写进 systemPrompt 的规范与工具描述要**重启 dsh** 才更新。

## 开发

```bash
pytest -q                      # 引擎测试
sh scripts/sync-python.sh      # 改完 src/ 后同步进插件包（prepack 也会跑）
npm pack --dry-run             # 看发布内容
```

## 许可

MIT。
