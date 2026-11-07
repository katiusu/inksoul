<div align="center">

# InkSoul

**面向 AI Agent 的中文文学创作增强工具**

从句法骨架层面诊断「机械复用」，把诊断结果变成可执行的写作策略与局部修订建议。

[![tests](https://img.shields.io/badge/tests-184%20passed-brightgreen)](https://github.com/katiusu/inksoul)
[![python](https://img.shields.io/badge/python-3.9%2B-blue)](https://github.com/katiusu/inksoul)
[![deps](https://img.shields.io/badge/core%20deps-0-informational)](https://github.com/katiusu/inksoul)
[![version](https://img.shields.io/badge/version-0.2.0rc1-orange)](https://github.com/katiusu/inksoul/releases/tag/v0.2.0-rc.1)
[![license](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

</div>

## 这是什么

InkSoul 不是「AI 检测器」。它把一篇中文文稿拆成小句，提取**句法骨架**（词性 + 依赖关系 + 句式特征），
回答一个具体问题：*这篇稿子是不是在用少数几个句式反复套模板？*

- **不输出「AI 概率」**，也**不输出单一总分**——只给可解释的分布与问题清单（ADR-2）
- 核心**零依赖**：`jieba` 是可选分词后端，缺失时有中文错误提示与降级路径
- 生成侧兼容 OpenAI 格式 API，也可完全离线只做分析
- 诊断结果直接接进写作闭环：规划 → 候选 → 择优 → 复核 → 修订 → 定稿闸门

## 核心能力

| 层 | 能力 |
|---|---|
| 文本处理 | 段落/句子/小句切分、jieba 分词与词性、归一符号体系（含 `把/被/只是/没有` 消歧） |
| 句法指纹 | 加权编辑距离、星形结构簇、骨架复用率、模式熵、J1–J3 修辞判据、体裁基线 |
| 跨作品相似 | 语料级骨架余弦：模板拼接 vs 人类写作的分离度（实测 0.902 vs 0.136） |
| 分布分析 | 句法多样性、文体（TTR/MTLD/MATTR/MSTTR/HDD）、叙事（视角/场景/对话节拍/信息密度） |
| 文体距离 | Burrows&apos; Delta（字频 z 标准化，同集内可比的风格距离矩阵） |
| 审阅 | 四类问题（机械复用/相邻雷同/句首重复/情绪直陈），带证据与建议，**无总分** |
| 生成 | OpenAI 兼容客户端、文体规划、多候选择稿、局部修订、复核 |
| Agent | 一条命令跑完闭环；**PTC 工具面**让模型写程序调用 `read_prev`/`lookup_bible`/`measure`/`run_gate` |

## 安装

```bash
# 预发布 wheel（推荐当前版本）
pip install inksoul-0.2.0rc1-py3-none-any.whl

# 或从源码可编辑安装
pip install -e .

# 可选：中文分词后端
pip install -e ".[jieba]"
```

预发布说明见 [release/RELEASE_NOTES-0.2.0rc1.md](release/RELEASE_NOTES-0.2.0rc1.md)。

## 快速开始

```bash
inksoul doctor                        # 环境自检（jieba / 配置 / 模型 Key）
inksoul analyze 稿子.txt               # 句法指纹 + 文体 + 叙事 + 审查
inksoul analyze 稿子.txt --json out.json
inksoul plan "雨夜重逢" --genre 小说     # 只出写作规划，不生成正文
inksoul corpus 作品目录/               # 跨作品骨架相似度
```

## Agent 模式

一条命令跑完「规划 → N 候选 → 择优 → 复核 → 局部修订 → 回滚 → 定稿闸门」：

```bash
inksoul agent "雨夜重逢" --preset long --out draft.txt
inksoul agent "雨夜重逢" --tools --tool-mode ptc --out draft.txt
inksoul --list-presets
```

| 预设档 | 用途 | 候选 | 闸门 |
|---|---|---|---|
| `draft` | 快速起稿 | 2 | — |
| `long` | 长篇单章 | 3 | deslop |
| `short` | 短篇 | 3 | deslop |
| `rewrite` | 改写重写 | 2 | — |
| `publish` | 上架前定稿 | 4 | deslop |
| `cover` | 封面文案 | 3 | — |
| `deai` | 去 AI 味一条龙 | 2 | deslop |

**定稿闸门**：默认只在定稿后跑一次（未过则按命中条目整篇重写一次），不逐候选、不逐轮，避免 40 s × 6 的浪费。
关掉用 `--gate off`，换成自定义脚本用 `--gate 'bash my_check.sh {file}'`。

## 设计原则

1. **线索不是判定**：所有阈值未人工标定，输出帮助人判断，不替代人判断。
2. **可复现优先**：同一文本同一配置必须给出同一结果；抽样、降级都写进报告的 `notes`。
3. **诚实记账**：文档里写了但代码没有的指标，一律标「未实现」；口径与论文不同的地方主动披露。

## 项目结构

```text
src/inksoul/     分析算核（文本处理 / 指纹 / 多样性 / 文体 / 审阅 / 生成 / Agent / PTC）
tests/           184 个单元测试（`python3 -m unittest discover -s tests -p "test_*.py" -t .`）
docs/            17 份设计、使用、接口、局限、论文对照文档
research/        文献题录、精读笔记、论文对齐审计
release/         wheel / sdist / 版本说明
```

## 文档

- [docs/project_overview.md](docs/project_overview.md) — 项目总览
- [docs/usage.md](docs/usage.md) — 命令行用法
- [docs/API_SPEC.md](docs/API_SPEC.md) — Python API 与 JSON 报告格式
- [docs/agent_mode.md](docs/agent_mode.md) — Agent 模式、预设档、工具面、闸门
- [docs/paper_alignment.md](docs/paper_alignment.md) — 论文 ↔ 实现对照（含口径偏差披露）
- [docs/limitations.md](docs/limitations.md) — **已知局限，务必先读**

## 验证状态

- 单元测试：**184 通过**（`Ran 184 tests in ~7s`）
- 规模：40 万字 analyze 约 16.5 s（两两相似度与簇内变异均按抽样估计，notes 会写明）
- **未验证**：真实模型 API 的端到端生成（本机无 Key）；阈值的人工标定

## 许可

MIT。第三方论文全文不入库（`research/papers/*.pdf` 已在 `.gitignore` 中），只保留题录与索引。
