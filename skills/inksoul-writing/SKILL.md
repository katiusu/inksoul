---
name: inksoul-writing
version: 1.0.0
description: "中文文学写作的生成闭环：规划 → 多候选 → 复核 → 修订 → 文风闸门，含预设档与 PTC 工具面。触发方式：/inksoul-writing、用 inksoul 写、开 agent 档、设定稿闸门。"
metadata: {"openclaw":{"source":"https://github.com/katiusu/inksoul"}}
---

# inksoul-writing：用 InkSoul 跑生成闭环

**前提**：生成正文要模型。先配 key，再跑，否则只会得到规划与诊断。

```bash
mkdir -p ~/.dsh/inksoul && chmod 700 ~/.dsh/inksoul
cat > ~/.dsh/inksoul/config.json <<'JSON'
{"model":{"base_url":"https://api.deepseek.com/v1","api_key":"sk-替换","model":"deepseek-chat"}}
JSON
chmod 600 ~/.dsh/inksoul/config.json
inksoul doctor   # 应显示模型已配置
```

环境变量 `INKSOUL_API_KEY` 优先级高于配置文件；任何 OpenAI 兼容端点都可。**不要把 key 写进提示词、代码或提交。**

## 七档预设

| 档 | 用途 | 候选 | 轮次 | 闸门 |
| --- | --- | --- | --- | --- |
| `draft` | 快速出稿 | 3 | 3 | 无 |
| `long` | 长篇单章 | 3 | 3 | deslop |
| `short` | 短篇 | 3 | 3 | deslop |
| `rewrite` | 改写既有稿 | 2 | 2 | 无 |
| `publish` | 发布前定稿 | 4 | 3 | deslop |
| `cover` | 封面文案 | 2 | 2 | 无 |
| `deai` | 去 AI 味一条龙 | 2 | 3 | deslop |

`inksoul --list-presets` 可看当前实际值。优先级：命令行显式 > 预设 > 配置文件。

## 主用法

```bash
inksoul plan --preset long                  # 只看规划，不调模型
inksoul agent "写第 3 章：雨夜对峙" --preset long --target-chars 3000
inksoul agent "改写这段" --preset rewrite --file 旧稿.md
inksoul agent "写开头" --preset deai --gate off   # 关闸门省 40s
```

## 闸门（gate）

预设 `long`/`short`/`publish`/`deai` 默认带 `deslop`，**只在定稿后跑一次**（约 40–90s；逐候选跑会到 4 分钟，所以默认不开）。

- `--gate off` 关掉；`--gate deslop|full|essay|zhuque` 换档；
- `--gate "/路径/脚本.sh {file}"` 自定义，`{file}` 换成正文路径；
- 闸门 FAIL 且有命中条目时，Agent 会**整篇重写并保持情节不变**，最多两轮；
- 定稿仍未 PASS 也会返回正文，并把 `status/verdict/receipt/findings` 留在结果的 gate 字段里——**不要谎报 PASS**。

## PTC 工具面（可选）

`--tools` 等价 `--tool-mode ptc`：侦察阶段模型写一段 Python 程序，程序内调用四个工具（`read_prev` / `lookup_bible` / `measure` / `run_gate`），而不是一步步 function calling。程序跑在子进程沙箱里，禁 import、禁私有属性、禁 open/eval/exec。

```bash
inksoul agent "续写第 12 章" --preset long --tools --tool-steps 2
```

预算：PTC 2 段程序，标准模式（`--tool-mode standard`）3 轮。工具只有四个、扇出窄时标准模式更省；跨多章批量诊断才值得 PTC。

## 协作顺序（推荐）

1. `inksoul plan` 定骨架；
2. `inksoul agent --preset long` 出稿；
3. `inksoul analyze` 看指纹是否偏离目标；
4. 需要发布 → `--preset publish` 带闸门再跑一遍；
5. 闸门 FAIL 的条目要么让 Agent 重写，要么人工按条目改，**别把 FAIL 的稿当定稿交出去**。

## 相关文档

- `docs/agent_mode.md`：预设字段、闸门别名、PTC 边界
- `docs/usage.md`：全部子命令与参数
- `docs/limitations.md`：什么时候别用它