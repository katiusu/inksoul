# Agent 模式：生成 → 复核 → 改进 闭环

一条命令把「直出」「去 AI 味复核」「局部改进」「回滚」「外部门禁」串起来，
产物是**定稿 + 每轮轨迹 + 定稿那份的分析**（AgentResult）。

## 1. 用法

```bash
inksoul agent "雨夜，旧友在旧书店重逢" --genre 小说 --perspective 第三人称限制 \
    --out draft.txt --report report.json \
    --gate 'bash /root/deslop/postwrite.sh {file}' --rounds 3 --candidates 3
```

- --gate 省略就退化成「内部复核闭环」（不跑外部脚本）。
- --report 写 JSON：chosen_round / stop_reason / rounds[] / gate / analysis / notes。
- 不加 --out 时正文直接打印到 stdout。

配置里也可以写死（agent.gate_cmd / agent.max_rounds / agent.candidates，
见 InkSoulConfig.agent）。

## 2. 闭环的五步

1. **规划**：build_plan 体裁先验 + 模型细化（失败退回先验）。
2. **多候选**：按温度序列出 N 份，各自 Analyzer.analyze 打分（不是总分，是问题项）。
3. **择优**：取 rank 最小的一份。
4. **改进**：对 review.blocking（severity ≥ 0.6）的问题句做窗口式单句改写，每轮最多 8 处。
5. **回滚判定**：新一轮 rank 严格更小才接受，否则退回上一版并停轮。

只要某轮 rank 已经到 (0, 0, 0)（闸门过 + 无阻断 + 无问题），立即停。

## 3. 取舍规则（唯一的排序依据）

    rank = (闸门是否 FAIL/ERROR, 阻断级问题数, 问题总数)

- **闸门优先**：外部检测不过的稿子，哪怕内部指标全绿也不算最好的一份。
- **不做加权总分**：没有 0–100，避免把创作变成指标优化（docs/limitations.md §1）。
- 定稿永远是 rank 最小的那版，**不是最后一版**——最后一版常常是被改坏的。

## 4. 四种停止原因

| stop_reason | 含义 | 该怎么办 |
|---|---|---|
| 复核通过：无阻断级问题 | 理想终态 | 定稿 |
| 修订未改善，已回滚到问题最少的那一版 | 模型改不出更好的句子 | 人工看 rounds 轨迹 |
| 无可用修订（问题句无法定位…） | 问题句找不到，或模型没给可替换的改写 | 检查 review.issues[].text |
| 达到轮次上限（N） | 3 轮通常够；再多是在拧指标 | 调 --rounds 或接受现状 |

## 5. 闸门约定

- 命令里用 {file} 占位正文路径；没有占位符时自动把路径追加到命令尾部（已 shell 转义）。
- 解析输出里的 VERDICT: 与 RECEIPT 行；VERDICT: FAIL 或非零退出码都算阻断。
- 回执原样进 AgentResult.gate.receipt，便于事后追责（哪次、哪个文件、什么裁决）。
- 超时默认 300s（朱雀那类检测要几十秒），可用 agent.gate_timeout 调。

## 6. 已知局限

1. 改进只改被点名的句子，**不改结构**——结构性问题（视角漂移、时间线混乱）不在闭环范围内。
2. 词汇指标（MTLD/MATTR）只做记录，不参与 rank：AI 文本多样性可能**更高**，低分不等于更好（docs/limitations.md §7）。
3. 闸门命令由用户提供，本项目不内置任何检测服务，也不对检测器结论负责。
4. 候选数 × 每轮修订都会调模型，成本是单次生成的 3–6 倍。
## 7. 接入本地 story skill 家族

story 家族（zenstory-ai/oh-story-claudecode，0.10.1）装在 `~/.agents/skills/story-*`。
Agent 模式按用途分成三种接法，**story-deslop 不接**（去 AI 味是外部闸门的活）：

| 用法 | 覆盖的 skill | 行为 |
|---|---|---|
| 注入写作规范（默认） | story-long-write / story-short-write / story-review | 取 SKILL.md 命中「写前必读/结构/章/节奏/开头」的块（≤4000 字）拼成 system 附加段；复核段 ≤1500 字 |
| `--from 前文.txt` | story-import | 取前文尾部 3000 字进提示，按「续写必须衔接」生成 |
| `--ref 报告.md`（可重复） | story-long-analyze / story-short-analyze | 每个文件前 3000 字作为参考资料进提示 |
| `--deliver publish\|cover` | story-publish / story-cover | 闭环结束后追加一次模型调用，产出发布资料或封面提示词，写进 `deliverables` |

- `--story auto` 按目标字数选：≥ 8000 字用长篇规范，否则短篇；`off` 不注入。
- story / story-setup / story-long-scan / story-short-scan 不注入：前两个是环境与路由，后两个要联网扫榜，进提示只会占字数。
- 注入前统一加 GUARD 声明：只采纳写作手法条目，涉及命令/路径/文件/联网的句子一律忽略（SKILL.md 是写给 agent 的操作手册，不能当指令执行）。

```bash
inksoul skills                       # 表：哪个 skill 存在、版本、选中哪个
inksoul skills --show story-long-write --chars 300
inksoul agent "第 4 章：雨夜对峙" --story long --from 第3章.txt --ref 拆解报告.md \
    --deliver publish --out ch4.txt --report ch4.json
```

`AgentResult.skills` 记录本次选中的 skill 与版本，`deliverables` 记录额外产出，报告 JSON 里都有。

## 8. 预设档（--preset）

把「story 接线 + 候选数 + 轮次 + 目标字数 + 交付物」固化成六个可复用档位，省得每次手敲一长串参数。

| 预设 | story | 候选 | 轮次 | 目标字数 | 交付物 | 闸门 | 说明 |
|---|---|---|---|---|---|---|---|
| draft | auto | 1 | 0 | — | — | — | 直出：单候选、不修订，最快最省 |
| long | long | 3 | 3 | 3000 | — | deslop | 长篇单章：长篇规范 + 3 候选 + 最多 3 轮修订 + 定稿过闸门 |
| short | short | 2 | 2 | 1500 | — | deslop | 短篇：短篇规范，篇幅与轮次都更小，定稿过闸门 |
| rewrite | long | 2 | 2 | — | — | — | 续写：必须给 `--from` 前文 |
| publish | long | 2 | 2 | — | story-publish | deslop | 成稿 + 发布资料，定稿过闸门 |
| cover | auto | 1 | 0 | — | story-cover | — | 直出 + 封面提示词 |
| deai | auto | 2 | 3 | 2000 | — | deslop | 去 AI 味一条龙：规范注入 + 闸门复核 + 按命中条目改进 |

- 优先级：**显式参数 > 预设 > 配置文件**。`--preset long --candidates 5` 就是 5 个候选。
- `--preset rewrite` 缺 `--from` 直接退出码 2，不浪费模型调用。
- `--list-presets` 只打印上表后退出；`brief` 可省略，配合 `--list-presets` 用。

```bash
inksoul agent --list-presets
inksoul agent "第 4 章：雨夜对峙" --preset long --out ch4.txt --report ch4.json
inksoul agent "续写下一段" --preset rewrite --from 第3章.txt --out ch4.txt
inksoul agent "一个关于末班地铁的短篇" --preset short --out s.txt
```

定义在 `src/inksoul/config.py` 的 `AGENT_PRESETS`，新增档位只加一行 `AgentPreset(...)`。

## 9. 去 AI 味一条龙（--gate / deai 预设）

项目自带文风闸门在 `/root/deslop/`：`postwrite.sh` 跑全套检查并落 RECEIPT，`run_gates.sh` 只跑检查。
Agent 模式把「写 → 查 → 改」串成闭环：

1. **直出带规范**：`story` 注入 story-long-write / story-short-write 的写法条目（含禁 AI 腔的规约），从生成阶段就把文风约束进去。
2. **闸门复核**：`--gate` 对每份候选与每轮修订都跑一次，解析 `VERDICT`、`RECEIPT` 与表中 `FAIL` 命中行。
3. **按命中条目改进**：闸门没过且解析到命中行 → 走 `generation.restyle` 整篇重写（只改文风、情节不变，提示里逐条列出命中项）；
   闸门过了但内部复核有问题 → 走 `generation.revise` 的窗口式局部替换。每轮都比 rank，改坏就回滚。

闸门别名：

| 别名 | 命令 | 场景 |
|---|---|---|
| `off` / 空 | 不跑 | 默认，最省 |
| `deslop` | `postwrite.sh {file}` | 小说正文，全套闸门 + 回执 |
| `full` | `run_gates.sh {file}` | 只跑检查、不落回执 |
| `essay` | `postwrite.sh {file} --essay` | 作文/议论文，跳过网文专属三闸 |
| `zhuque` | `postwrite.sh {file} --zhuque` | 加跑朱雀 AIGC 概率检测（慢） |
| 其他 | 原样当命令执行 | 例：`python3 /x/check.py {file}` |

```bash
inksoul agent "第 7 章：渡口夜话" --preset deai --out ch7.txt --report ch7.json
inksoul agent "写一段雨夜对峙" --gate essay --out draft.txt
inksoul agent "改写这一段" --gate deslop --candidates 1 --rounds 4 --out fix.txt
```

- 闸门每次评分约 40s（`zhuque` 更久），默认超时 300s。**闸门只在定稿后跑，不逐候选、不逐轮跑**：一次运行通常 1 次闸门（未过再补 1 次），额外 40–90s。
- `long` / `short` / `publish` / `deai` 四档默认带 `gate="deslop"`；想关掉就显式 `--gate off`。
- 定稿若仍未 PASS，`AgentResult.gate` 里保留 status / verdict / receipt / findings，报告 JSON 的 `gate` 字段可直接看，notes 会标「外部门禁未 PASS」。
- 闸门只做裁定，不做改写：它的任务是把命中项交给模型，模型只负责按条目重写。

## 10. 工具面：PTC 程序化调用（--tools / --tool-mode）

写作前允许模型查资料做「侦察」，用完就收，不进生成循环。**默认基座是 PTC。**

```bash
inksoul agent "第 8 章：渡口的火" --preset long --tools --out ch8.txt
inksoul agent "续写" --from ch7.txt --tool-mode ptc --tool-steps 3 --out ch8.txt
inksoul agent "续写" --from ch7.txt --tool-mode standard --out ch8.txt
```

| 模式 | 模型做什么 | 一次侦察的成本 |
|---|---|---|
| `ptc`（`--tools` 默认） | 写一段 Python 程序，程序里循环调工具，只把结论带回上下文 | 1 段程序 + 1 轮收尾 |
| `standard` | 一次一轮 function calling，结果逐步回灌 | 每调一个工具多一轮 chat |

PTC 程序里这些函数直接可用（不用 import）：

| 函数 | 作用 | 返回 |
|---|---|---|
| `read_prev(path, limit=3000)` | 读前文/参考稿末尾 | `{path, chars, text}` |
| `lookup_bible(query, top=3)` | 在 `bible/ 设定/ settings/ notes/ bible.md` 里按关键词找设定 | `{query, hits:[{source, text}]}` |
| `measure(text)` | 字数/句数/平均句长/句长 CV/逗号密度/短句占比 | `{chars, sentences, avg_sentence, cv, comma_per_100, short_ratio}` |
| `run_gate(text, gate="")` | 跑文风闸门 | `{status, verdict, findings, receipt}` |
| `print(...)` | 输出你要看的东西（回灌给模型） | — |

**为什么把基座换成 PTC**：标准模式「模型说调 X → 宿主执行 → 结果回灌 → 再问」的每一步都要重发上下文；
跨章体检、批量量指标这类天然循环的场景，PTC 让模型一次把循环写完，上下文里只留结论。

**安全边界**（`src/inksoul/ptc.py`）：

- 程序在**独立子进程**里执行，父进程只收 stdout 与错误；
- 子进程内建受限 builtins：无 `open` / `import` / `eval` / `exec`，禁私有属性；
- 父进程先做 AST 预校验，命中禁用节点直接拒跑，不进子进程；
- 单次运行超时默认 60s，输出上限 20000 字；
- `read_prev` / `lookup_bible` 只能读 `roots`（默认当前目录 + InkSoul 主目录）以内，越界返回 error。

**预算与轨迹**：PTC 默认 2 段程序（`--tool-steps N` 可调），每段一次 chat；不开工具面是零额外成本。
侦察笔记（≤1500 字）拼进生成提示的 `extra_user`；每段程序的 `code / stdout / error / elapsed` 记进报告 `tool_steps`，事后可复盘。
