# InkSoul 进度（v0.1.0 交付态）

## 阶段 1 · 研究（已完成）
- `research/literature_review.md`：41 条文献，L1 12 / L2 19 / L3 10，含核实渠道、失败记录、
  TTCW 引用订正、主动放弃陈平 1987 的说明
- `research/research_findings.md`：7 条有证据结论 + 4 条「本项目假设」+ 4 项未解问题 + 研究→代码对照表
- `research/references.bib`：41 条；`research/notes/` 存检索脚本与逐篇笔记
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

## 未完成 / 下一步
1. 阈值标定（人工标注 ≥200 对小句 + ≥50 篇机械感判定）
2. 真实模型实验 C/D/F 正式版（需 API Key）
3. 零形回指与人物语言辨识度
4. `gen_model_samples.py` 尚未实现（预留接入点）
