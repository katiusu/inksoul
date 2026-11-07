# InkSoul 0.2.0rc1 预发布说明

日期：2026-11-07｜包：`inksoul-0.2.0rc1-py3-none-any.whl`（111 KB）、`inksoul-0.2.0rc1.tar.gz`（117 KB）
**预发布**：可用、有测试，但真实模型链路与阈值标定仍未完成。

## 相对 0.1.0 的变化

| 维度 | 0.1.0 | 0.2.0rc1 |
|---|---|---|
| 测试 | 77 | **184**（`Ran 184 tests OK`） |
| Agent 闭环 | 无 | `WritingAgent`：规划 → N 候选 → 择优 → 复核 → 局部修订 → 回滚 → 闸门 |
| 工具面 | 无 | **PTC**：模型写 Python 程序调 `read_prev` / `lookup_bible` / `measure` / `run_gate`，AST 预校验 + 独立子进程 |
| 预设档 | 无 | 七档 `draft/long/short/rewrite/publish/cover/deai`，`--list-presets` 可见 |
| 文风闸门 | 无 | `long/short/publish/deai` 默认 `deslop`；**只在定稿后跑**（1 次，未过再补 1 次） |
| 新增分析模块 | — | `dependency.py`（依存弧长/树深）、`corpus.py`（跨作品骨架余弦）、`lexical.py`（TTR/MTLD/MATTR/MSTTR/HDD）、`stylometry.py`（Burrows' Delta） |

## 本版关键修复（论文对齐审计整改，26 条）

- 指纹两两相似度改为**计算前**抽样（800 句）+ 簇内变异抽样（60 成员）+ 位置索引预建：40 万字 analyze 由外推 ~10.5 h 降至 **16.5 s**。
- `analyze --baseline` 原先必抛 `TypeError`（基线 JSON 往返契约不成立）→ 新增 `Baseline.from_dict`，往返可用。
- `do_review` 漏传 `narrative`（「对话标签同质」规则从未触发）已补。
- HDD 旧实现实为长度曲线（1x→10x 从 0.979 掉到 0.618），改按 McCarthy & Jarvis 定义，稳定在 0.375；`docs/paper_alignment.md` §6.3 已重算。
- `_run_gate` 的 `mkstemp` fd 泄漏修掉（30 次调用 fd delta = 0）。
- 文档账本纠正：Yule's K / distinct-2 / MATTR-500 / 套语密度 / PMI 标注「未实现」；`FingerprintReport` 字段表按代码重写；Delta 明示「字级口径，不可与原文直接比较」。

## 安装

```bash
python3 -m pip install --break-system-packages --force-reinstall --no-deps inksoul-0.2.0rc1-py3-none-any.whl
inksoul doctor          # 自检
inksoul --help
```

## 仍未验证 / 已知问题

1. **无真实 API Key**：`agent` 的「模型生成 → 闸门 → 重写」只跑过假模型，联网端到端未实测。
2. 闸门单次约 40 s（`postwrite.sh`），开闸门的一档会更慢。
3. 阈值仍未人工标定，输出是线索不是判定（见 `docs/limitations.md`）。
4. 已知小问题：PTC 沙箱对 `format.__globals__` 只做信息限制；`style._mtld` 与 `lexical.mtld` 口径不同；`analyze --json` 目录模式同名文件会覆盖。

## 审计与证据

- `research/notes/audit-2026-11-07.md`（26 条审计 + 修复状态）
- `docs/paper_alignment.md`（论文 ↔ 实现对照，含口径偏差披露）
