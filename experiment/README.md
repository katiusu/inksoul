# experiment/ 数据与脚本说明

## 目录

```
data/raw_sources/   8 篇人类文本（公有领域，Wikisource 固定 revid + sha256）
data/generated/     6 篇「模板拼接」对照样本（gen_samples.py 生成）+ 1 篇人工改写稿
data/rhetoric/      8 篇标注样本：4 修辞性重复 / 4 机械模板（含 labels.json）
scripts/            gen_samples.py（生成对照样本）、run_experiments.py（跑 A/B/D/E/F）
results/            all.json（全量指标）、summary.md（自动生成表）
reports/report.md   实验报告（人工撰写，含结论与局限）
```

## 语料来源与合规

### 人类文本（`data/raw_sources/`）

全部来自**中文维基文库**的公有领域作品（作者逝世逾 50 年），按固定版本号抓取并记录 sha256：

| key | 作品 | 作者 | 年份 | 体裁 |
|---|---|---|---|---|
| h_novel_01 | 孔乙己 | 鲁迅 | 1919 | 小说 |
| h_novel_02 | 药 | 鲁迅 | 1919 | 小说 |
| h_novel_03 | 祝福 | 鲁迅 | 1924 | 小说 |
| h_prose_01 | 背影 | 朱自清 | 1925 | 散文 |
| h_prose_02 | 荷塘月色 | 朱自清 | 1927 | 散文 |
| h_prose_03 | 差不多先生传 | 胡适 | 1924 | 散文 |
| h_dialogue_01 | 雷雨（节选） | 曹禺 | 1933 | 对话/戏剧 |
| h_dialogue_02 | 茶馆（节选） | 老舍 | 1957 | 对话/戏剧 |

字段（revid / url / chars / sha256 / fetched_at）见 `manifest.json`。
**没有**采集任何私人文本、论坛帖、付费内容。

### 模板拼接样本（`data/generated/`）

`gen_samples.py` 用固定模板池 + 固定词表拼接生成，seed 记录在 `manifest.json`。
**它不是任何 LLM 的输出**，只代表「无意识模板复用」这一端的上界，用于先验证实验管线。

真实模型样本需要 API Key（本机没有），脚本预留 `gen_model_samples.py` 的接入点（未实现）。

### 修辞/机械标注样本（`data/rhetoric/`）

8 篇短样本，人工标注为 `修辞性`（排比/复调/首语重复/短句节拍）或 `机械`（同模板换词）。
`labels.json` 记录标签与说明；样本由本项目撰写，用于测量**误报**与**检出**。

## 复现

```bash
PYTHONPATH=src python3 experiment/scripts/gen_samples.py      # 重新生成对照样本（可选）
PYTHONPATH=src python3 experiment/scripts/run_experiments.py  # 跑全部实验 → results/
```

## 注意

- 所有阈值「未标定」，结果只用于验证管线与方向，不作为产品判定依据。
- 实验 D 的「人工机械感评分」尚未采集，当前用标签代理，**不能当效度证据**。
