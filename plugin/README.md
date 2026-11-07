# dsh-inksoul

把 [InkSoul](https://github.com/katiusu/inksoul) 接成 DeepSeek Harness 的一等工具。

## 装它

```bash
dsh plugin --profile web add /path/to/this/dir
```

## 给了什么

| 工具 | 作用 |
| --- | --- |
| `inksoul_doctor` | 环境自检（Python / 架构 / jieba / 模型配置） |
| `inksoul_analyze` | 单篇句法骨架指纹、句长分布、与体裁基线距离 |
| `inksoul_corpus` | 目录内多篇两两骨架相似度 |
| `inksoul_agent` | 规划→多候选→复核→修订→文风闸门（分钟级） |

外加一段 `inksoul:policy` 系统提示（order 9600），说明何时用、结论怎么表述。

## 为什么不依赖本地安装

`python/` 里是 InkSoul 的纯 Python 源码（零第三方依赖），插件调用时把 `PYTHONPATH` 指过去，
所以机器上 `pip uninstall inksoul` 之后照样能用。只有 `jieba` 是可选加速，缺了会降级但不崩。

要出正文得配模型：`~/.inksoul/config.json` 或 `INKSOUL_API_KEY`（OpenAI 兼容端点）。

## 配置

| 键 | 默认 | 含义 |
| --- | --- | --- |
| `enabled` | true | 关掉则不注册任何工具 |
| `python` | `''` | Python 可执行文件；空则用 `INKSOUL_PYTHON` 或 `python3` |
| `workdir` | `''` | 子进程工作目录；空则用宿主 cwd |
| `timeoutMs` | 600000 | 单次调用超时 |
| `maxOutputChars` | 20000 | 结果截断上限 |

## 边界

输出是可复现的机械线索，不是 AI 概率。相似度只说骨架复用，不说抄袭；偏离基线不推非人类。
