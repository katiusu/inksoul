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
| `inksoul_markers` | AI 味标记族密度（中文 Biber 清单：名词化/定语链/并列/被动/连接词/抽象/比喻/四字格），对照人类网文 p50/p90/p99 | 秒级 |
| `inksoul_gate` | 对定稿跑文风闸门（去 AI 味精查），拿回逐条命中项；`preset=markers` 是随包内置的纯 Python 闸门 | 1–90 秒 |
| `inksoul_agent` | 要真的写出正文：规划→多候选→复核→修订→闸门，闭环 | 分钟级 |
| `inksoul_doctor` | 环境自检；任何报错先跑它 | 1 秒 |

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
