---
name: inksoul-diagnose
version: 1.0.0
description: "中文文本的机械性诊断：句法骨架指纹、跨作品相似度、长度/句子分布与文体距离、审阅报告。触发方式：/inksoul-diagnose、用 inksoul 诊断、查句法指纹、算文本相似、看分布与文体距离。"
metadata: {"openclaw":{"source":"https://github.com/katiusu/inksoul"}}
---

# inksoul-diagnose：用 InkSoul 做机械性诊断

**边界先说清**：InkSoul 输出的是可复现的机械线索，不是「AI 概率」。任何结论都要带原始指标，不要写成判定。

## 先确认可用

```bash
inksoul --version     # 期望 0.2.0rc1 或更高
inksoul doctor        # 期望末行「结论：核心功能可用」
```

缺 jieba 时 analyze 仍可用，但中文分词相关指标会降级；`python3 -m pip install jieba` 补上。若 `inksoul` 不在 PATH，用 `PYTHONPATH=<site> python3 -m inksoul.cli`。

## 四条主命令

| 目的 | 命令 |
| --- | --- |
| 句法骨架指纹 | `inksoul analyze 文件.md` |
| 机器可读 | `inksoul analyze 文件.md --json` |
| 跨作品比相似 | `inksoul corpus 目录/ --top 5` |
| 自带基线对比 | `inksoul baseline 文件.md` |
| 审阅报告（人读） | `inksoul review 文件.md` |
| 生成计划不调模型 | `inksoul plan --preset long` |

stdin 也行：`cat 稿.txt | inksoul analyze -`。

## analyze 的读法

输出形如「段落 2｜句 3｜小句 7｜字数 47」。要点：

- **句法骨架指纹**看的是虚词/句式骨架的复用模式，不是词汇；改写同义词骗不过它。
- 单篇绝对值意义有限，重点看**同一作者多篇之间**的相似度，以及**与基线**的距离。
- `--json` 的字段名与含义见 `docs/API_SPEC.md`；不要自己编字段。

## 性能与规模

- 40 万字 / 16.5 秒（aarch64 手机容器实测），纯 Python，零第三方依赖（jieba 可选）。
- 大于 100 万字的目录先分卷再跑，避免一次性吃满内存。

## 报告怎么写

1. 先列命令与原样输出（可复现），再给解读。
2. 相似度高 → 说「骨架复用明显」，不给「抄袭」结论。
3. 与基线差距大 → 说「偏离该基线分布」，不推「非人类」。
4. 存疑处标「需人工判断」，别用概率词。

## 相关文档

- `docs/API_SPEC.md`：JSON 字段与取消语义
- `docs/limitations.md`：能力边界（哪些指标不能当证据）
- `docs/paper_alignment.md`：每个指标对应的论文出处