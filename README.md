# InkSoul

**给 AI Agent 的中文写作插件。** 模型写中文时，手里通常只有「感觉」；InkSoul 给它机械线索：
能测句法骨架、能比同质度、能过文风闸门、能自己改到达标。

```
npm:      dsh-inksoul
harness:  DeepSeek Harness（DSH）
入口:     lib/index.js  ← 四个诊断类工具 + 一个生成闭环 + 一段写作规范提示
引擎:     python/inksoul（随包分发，零第三方依赖）
```

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
| `inksoul_analyze` | 想量化一篇中文文本的句法骨架、句长分布、与体裁基线的距离 | 秒级 |
| `inksoul_corpus` | 一批稿子之间两两骨架相似度——判断是不是同一副骨架反复复用 | 秒级 |
| `inksoul_style` | **段级**风格距离（轻量，只回距离 + 六维 z + 该改哪两维）。正文按 800–1000 字一段写、每段跑一次，距离 >1.30 就重写这一段；整章一次生成实测距离 2.10 | 约 1 秒 |
| `inksoul_markers` | AI 味标记族密度（中文 Biber 清单：名词化/定语链/并列/被动/连接词/抽象/比喻/四字格），对照人类网文 p50/p90/p99 | 秒级 |
| `inksoul_gate` | 对定稿跑文风闸门（去 AI 味精查），拿回逐条命中项；`preset=markers` 是随包内置的纯 Python 闸门 | 1–90 秒 |
| `inksoul_agent` | 要真的写出正文：规划→多候选→复核→修订→闸门，闭环 | 分钟级 |
| `inksoul_doctor` | 环境自检；任何报错先跑它 | 1 秒 |

### 分段写作流程（预设里是硬约束）

1. **动笔前**：载入 `prose-deai` 与项目 `skills/inksoul-writing`、`skills/inksoul-diagnose`，回复里列出「已载入：…」，否则不算动笔资格。
   走 `inksoul agent --preset long|short|deai|publish|rewrite` 时，system 里只放一句「用 load_skill 载入 prose-deai / story-xxx」的要求（约 150 字），规范正文由 agent 在侦察阶段自己 `load_skill` 读，不再预先摘录进 prompt；`inksoul presets` 看每档要求载入哪几份、本地装没装、什么版本。
2. **逐段**：800–1000 字一段 → 落盘 `partNN.md` → `inksoul_style` → `NEAR` 进下一段，`FAR` 按「动作：」那两维只改这一段（最多 3 轮，段内 ≤1.50）。
3. **收尾**：段落全过后合并成章 → `inksoul_gate` 拿 `VERDICT: PASS` + `RECEIPT` → 交付时给「段号/字数/距离/超阈维度/重写次数」表。

为什么不是整章后验：人类池是按 900 字标定的，整章一次生成实测骨架复用率 z +4.57、距离 2.10（人类 p90 1.29）；同一段内容按段改写能压到 1.45。

### 为什么是插件而不是技能

技能只能塞说明书，还得先在本机装好 CLI、配好 PATH；插件把引擎一起打进 npm 包，
模型拿到的是一等工具：直接调、直接拿结构化结果、失败也能读懂原因。

### 结论口径（写进 `inksoul:policy`，照着说）

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
inksoul plan "写一段雨夜重逢" --register 情色   # 语域：文学书面/口语都市/爽文节奏/冷硬悬疑/情色
```

引擎细节（指纹算法、基线、PTC 工具面、闸门接线）见 [ENGINE.md](ENGINE.md)。

## 开发

```bash
pytest -q                      # 引擎测试
sh scripts/sync-python.sh      # 改完 src/ 后同步进插件包（prepack 也会跑）
npm pack --dry-run             # 看发布内容
```

## 许可

MIT。
