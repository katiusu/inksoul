# InkSoul 架构

## 1. 分层

```
┌─────────────────────────────── 调用方 ───────────────────────────────┐
│  CLI（inksoul …）   Python API（Analyzer / GenerationController）     │
│  Agent / Skill（skills/inksoul-writing/SKILL.md）                     │
└───────────────┬──────────────────────────────────────────────────────┘
                │  AnalysisReport / StylePlan / ReviewReport（纯 dataclass）
┌───────────────▼──────────────────────────────────────────────────────┐
│  analyzer.py   装配 + 降级（任一子模块缺失 → 占位报告 + notes）        │
├──────────────┬──────────────┬───────────────┬────────────────────────┤
│ text_processor│ fingerprint  │ diversity     │ style / narrative      │
│ 分句/分词/词性 │ 骨架/簇/复用率│ 分布类指标     │ 词汇、对话、节奏        │
├──────────────┴──────────────┴───────┬───────┴────────────────────────┤
│ normalizer.py（jieba 错标纠偏 + 符号映射）│ reviewer.py（问题判定 + J1/J2/J3）│
├─────────────────────────────────────┴────────────────────────────────┤
│ nlp/backend.py：jieba 后端 | spaCy 后端（可替换接口，能力位 has_dependency）│
├─────────────────────────────────────────────────────────────────────┤
│ llm.py（OpenAI 兼容，重试/脱敏）  generation.py（规划/候选/修订）        │
│ agent.py（Agent 闭环：候选→复核→改进→回滚→闸门）                     │
├─────────────────────────────────────────────────────────────────────┤
│ config.py（dataclass + JSON + 校验 + 打码） errors.py logging_setup.py │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. 数据模型（`text_processor.py`）

- `Token`：`word / pos / flag / norm`（归一符号）/ `sub`（细分符号）/ `index / start / end`
- `Clause`：`tokens / text / sig / skel / para_id / sent_id / id / confidence`
- `Sentence` → `clauses`；`Paragraph` → `sentences`；`Document` → `paragraphs`，并提供
  `clauses` 扁平视图与 `has_dependency`。

归一符号是一套**受控词表**（`normalizer.SYMBOLS`）：`PRON / N / V / A / ADV_* / PREP_* /
CONJ_* / ASP / DE / DIR / NEG / NUM / CL / M / P / NAME / IDIOM / TIME / LOC / ONO / Q …`。
骨架 = 归一符号序列（`Clause.skel`），指纹 = 骨架的元组键。

## 3. 降级策略

| 缺失项 | 行为 |
|---|---|
| jieba 未安装 | `build_backend` 抛 `BackendUnavailable`（中文提示「pip install jieba」）；CLI `doctor` 报 ✘ 并 exit 2 |
| spaCy 未安装且 `backend=spacy` | 同上，提示回退 `auto` |
| 无依存句法 | `Document.has_dependency=False`；fingerprint 的 L2/L3 关闭，`confidence` 折算，报告 notes 说明 |
| 子模块 import 失败 | `Analyzer._load` 捕获 → `_Placeholder`，其余报告照常产出 |
| 无 API Key | `generate()` 返回占位稿并标「未生成」，分析/审查仍可跑 |
| API 超时/429/5xx | `LLMClient` 指数退避重试 `max_retries`；耗尽抛 `ModelAPIError`（含 hint） |
| 文本超 `analysis.max_chars` | 抛 `InputTooLarge`，提示分段或调大上限 |

## 4. 长文本与内存

- 单次分析上限 `max_chars=400_000`（约 40 万字），超出**明确报错**而不是 OOM。
- 指纹里的两两相似度（全局 `mean_pairwise_similarity`）与簇内变异（`variation`）是 O(n²)：
  前者最多取 `PAIR_SAMPLE_CLAUSES=800` 个小句、后者每簇最多取 `VARIATION_SAMPLE=60` 个成员，
  按固定步长等距抽样，报告 `notes` 注明抽样比例；40 万字（5.3 万小句）实测约 16.5 s。
- 分簇是「分组 + 代表元比较」，复杂度约 O(组数 × 簇数)，不是全量并查集。

## 5. 生成链路（`generation.py`）

```
CreationBrief ──plan()──► StylePlan（文体规划：视角/节奏/对话/句式策略/禁忌）
                 │
                 ├─ 多候选：candidates 个，各自温度（默认 0.75/0.9/1.05）
                 │     ↓
                 │  analyze() → 每个候选的阻断级机械复用数
                 │     ↓  选稿：阻断数最少者优先，其次候选顺序（**不打综合分**）
                 ↓
              Draft ──revise()──► RevisionResult（逐条替换命中问题的小句，最多 8 条/轮）
                 ↓
              再次 analyze() 复核 → GenerationResult(text, plan, analysis, review, notes)
```

## 6. 为什么不做成「DSH 原生插件」

本会话实际检查过 DSH（`/usr/local/lib/node_modules/@deepseek-ai/dsh/`）的插件接口：
其扩展点面向 Node/TS 的 Web 插件与工具注册，没有「Python 分析插件」的原生加载协议。
因此 InkSoul 采用**标准 Python 包 + 薄适配层**：

1. 包本身可 `pip install`，可被任意 Python 进程 import；
2. `inksoul` CLI 提供子命令，任何 Agent 都能用 shell 调用；
3. `skills/inksoul-writing/SKILL.md` 描述「什么时候调、怎么读结果」，
   Agent 侧只需把 CLI/HTTP 当工具即可。

若将来 DSH 提供 Python 插件协议，只需在 `src/inksoul/adapters/` 增加一个薄模块，
分析层与生成层无需改动（两者都不依赖 DSH）。

## 7. 模块依赖方向（保证无环）

```
errors ← config ← normalizer ← text_processor ← fingerprint ← reviewer
                                        ↑            ↑
                        diversity / style / narrative ← analyzer ← cli
llm ← generation ← analyzer
```
`code_architecture_review` 自检结果见 `docs/limitations.md` §6。
