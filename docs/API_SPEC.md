# InkSoul 接口规范

版本：`inksoul/1`（`inksoul.SCHEMA_VERSION`）｜包版本：`0.1.0`

三层接口：**Python API**（进程内）、**CLI**（任何 Agent 可调）、**JSON 报告**（跨语言）。

---

## 1. Python API

### 1.1 分析

```python
from inksoul import Analyzer, analyze_text, load_config

cfg = load_config()                      # 读 ~/.dsh/inksoul/config.json（可用 inksoul_home 覆盖）
report = Analyzer(cfg).analyze(text)     # AnalysisReport
data = report.as_dict()                  # 纯 dict，可直接 json.dumps
text = report.to_json(indent=2)
```

`AnalysisReport` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `text` | str | 原文（`as_dict(include_text=False)` 时不含） |
| `meta` | dict | `backend / has_dependency / chars / paragraphs / sentences / clauses / elapsed_ms` |
| `fingerprint` | `FingerprintReport` | 骨架、簇、复用率、熵、嫌疑、基线对比 |
| `diversity` | `DiversityReport` | 相邻相似度、段内/跨段重复、句首重复、长度分布 |
| `style` | `StyleReport` | 句长统计、TTR、词性分布、对话比、修辞/情绪词 |
| `narrative` | `NarrativeReport` | 视角、场景转换、对话节拍、信息密度 |
| `review` | `ReviewReport` | 问题清单（`with_review=True` 时） |
| `coverage` | dict \| None | 传入基线时的覆盖统计 |

`FingerprintReport`：`clause_count / distinct_patterns / pattern_entropy / reuse_rate /
clusters / suspects / top_patterns / mean_pairwise_similarity / notes`（无 `baseline` 与
`adjacent_similarity_mean` 字段；基线覆盖统计在 `AnalysisReport.coverage`）。

`ReviewReport`：`issues[] / exempted[] / verdict / counts / notes`，
`LiteraryIssue`：`kind / clause_id / paragraph_id / text / severity / suggestion / evidence`。

**没有 `score` 字段**——这是设计约束（见 `docs/limitations.md`）。

### 1.2 生成

```python
from inksoul.generation import GenerationController, build_plan, CreationBrief

ctrl = GenerationController(cfg)
plan = ctrl.plan("雨夜，旧友重逢", genre="小说", perspective="第三人称限制")
res  = ctrl.generate("雨夜，旧友重逢", genre="小说", max_rounds=2, candidates=3)
res.text        # 最终稿
res.analysis    # 每轮自检的 as_dict 列表
res.revisions   # 实际替换的小句数
res.notes       # 选稿理由、降级说明
```

`StylePlan`：`genre / voice / rhythm / dialogue / sentence_policy[] / forbidden[] /
target_chars / candidates / temperatures / notes`。

### 1.3 模型客户端

```python
from inksoul.llm import LLMClient
client = LLMClient(cfg.model)
resp = client.chat([{"role": "user", "content": "…"}], temperature=0.9)
resp.text, resp.usage, resp.latency_s, resp.attempts
```

兼容任何 OpenAI Chat Completions 格式的服务（DeepSeek、Moonshot、本地 vLLM 等）。
可注入 `transport(method, url, headers, body, timeout) -> (status, bytes)` 做测试替身。

### 1.4 错误

| 异常 | `code` | 触发 |
|---|---|---|
| `InkSoulError` | `INKSOUL_ERROR` | 通用（带 `hint`） |
| `ConfigError` | `INKSOUL_CONFIG` | 配置非法/未知字段 |
| `BackendUnavailable` | `INKSOUL_BACKEND_UNAVAILABLE` | jieba/spaCy 缺失 |
| `ModelAPIError` | `INKSOUL_MODEL_API` | 鉴权/超时/限流/坏响应 |
| `AnalysisError` | `INKSOUL_ANALYSIS` | 分析内部错误 |
| `InputTooLarge` | `INKSOUL_INPUT_TOO_LARGE` | 超 `analysis.max_chars` |
| `StaleFingerprint` | `INKSOUL_STALE_FINGERPRINT` | 基线版本与归一表不一致 |

所有异常都有中文 `str()`；`ModelAPIError` 的 `detail` 已脱敏（不含 api_key）。

---

## 2. 配置规范

默认路径 `~/.dsh/inksoul/config.json`（可用环境变量 `INKSOUL_HOME` 改根目录，
或用 `inksoul --config PATH`）。**未知字段会报错**，防止拼写错误静默失效。

```json
{
  "model": {
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "",
    "model": "deepseek-chat",
    "temperature": 0.8,
    "top_p": 0.95,
    "max_tokens": 4096,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "timeout": 120.0,
    "max_retries": 2,
    "family": "generic"
  },
  "analysis": {
    "backend": "auto",
    "max_chars": 400000,
    "chunk_chars": 20000,
    "cluster_sim_threshold": 0.6,
    "suspect_min_freq": 3,
    "suspect_min_para_spread": 2,
    "suspect_max_gap_cv": 0.5,
    "enable_dependency": true
  },
  "generation": {
    "candidates": 3,
    "max_revision_rounds": 2,
    "target_chars": 1200,
    "temperature_candidates": [0.75, 0.9, 1.05]
  },
  "log_level": "INFO",
  "log_file": ""
}
```

- `api_key` 也可用环境变量 `INKSOUL_API_KEY`（优先于配置文件）。
- 打印/日志一律走 `cfg.to_dict(redact=True)` 与 `redact()`，密钥显示为 `***REDACTED***`。
- `backend`：`auto`（jieba 优先，缺则 spaCy）｜`jieba`｜`spacy`。

---

## 3. CLI

```
inksoul [--config PATH] <子命令>

analyze   <文件|目录|->  [--json] [--no-review] [--baseline PATH]
generate  <创作要求>     [--genre G] [--perspective P] [--rounds N]
                         [--target-chars N] [--out PATH] [--offline] [--report]
plan      <创作要求>     [--genre G] [--perspective P] [--target-chars N]
baseline  build <目录>   --genre G [--out PATH]
doctor
--version
```

退出码：`0` 成功；`1` `InkSoulError`（输入/配置/分析，stderr 打「错误：…提示：…」）；
`2` 未预期错误；`3` 模型接口失败。

### JSON 输出示例（`analyze --json`，节选）

```json
{
  "meta": {"backend": "jieba", "has_dependency": false, "chars": 107,
           "paragraphs": 3, "sentences": 6, "clauses": 14, "elapsed_ms": 41},
  "fingerprint": {
    "clause_count": 14, "distinct_patterns": 22, "reuse_rate": 0.5,
    "pattern_entropy": 3.46,
    "suspects": [{"signature": "PRON ADV V ASP N P", "freq": 3,
                  "para_spread": 2, "gap_cv": 0.31, "evidence": ["J1 …", "J2 …"]}],
    "top_patterns": [{"signature": "PRON ADV V ASP N P", "count": 3, "share": 0.214}]
  },
  "review": {"verdict": "存在疑似机械复用，建议局部修订",
             "counts": {"机械复用": 1},
             "issues": [{"kind": "机械复用", "clause_id": 7, "text": "他慢慢地推开了房门。",
                         "severity": 0.7, "suggestion": "…", "evidence": {...}}]},
  "diversity": {"adjacent_similarity_mean": 0.42, "paragraph_internal_repeat_rate": 0.0},
  "style": {"ttr": 0.61, "dialogue_ratio": 0.3},
  "narrative": {"perspective": {"label": "第三人称", "confidence": 0.9}}
}
```
