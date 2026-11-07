# InkSoul 插件 GUI 测试提示词（v0.3.0 / preset-inksoul）

> 前置：重启 dsh web，右上角预设切到「**InkSoul 写作**」。每个用例都写了「该看到什么」，看不到就是失败，把原话贴回来。
> 只有第 6–8 例花钱/慢（`inksoul_agent` 需要 API Key，分钟级）。前 5 例是秒级、零成本。

## 0. 冒烟：工具在不在
```
用 inksoul_doctor 做一次环境自检，把原始输出贴出来，别总结。
```
预期：JSON 含 python 版本、arch、jieba 状态、模型配置；结论行「核心功能可用」。
看不到工具 → 插件没激活，不是提示词的问题。

## 1. 单篇指纹（inksoul_analyze，文本走 stdin）
```
用 inksoul_analyze 分析下面这段文字，把 JSON 里的 clause_count、平均句长、骨架与前 3 个高频骨架列出来，再说一句它更像书面语还是口语。

天还没亮，巷口的豆浆摊先冒了热气。老板把桶盖掀开一条缝，白汽顺着缝往外钻，扑在他手背上。他缩了缩手，又舍不得盖回去。
```
预期：`clause_count` 为正值、返回句长分布与骨架列表；解读只描述指标，不下「是不是 AI」的结论。

## 2. 同骨架复用（inksoul_corpus，目录）
```
用 inksoul_corpus 扫 examples/ 目录，告诉我最相似的前三对是哪两篇、相似度多少，并判断是不是同一骨架反复复用。
```
预期：返回两两相似度排序（默认 top=5）；结论措辞是「骨架复用明显」，而不是「抄袭」。
目录空或不足 20 个小句时它会报「只有 0 篇达到 20 个小句」——那是夹具问题，换目录再试。

## 3. 定稿闸门（inksoul_gate，最重要的一个）
```
把下面这段当定稿，用 inksoul_gate 跑一次文风闸门（默认 deslop 预设），原样贴出 status、verdict、逐条 FAIL 命中行和 RECEIPT 行。

夜色渐深，城市的灯光如繁星般闪烁。我站在窗前，心中涌起一股难以言喻的情绪。这一刻，时间仿佛静止了，所有的喧嚣都在这一瞬间远去，只留下无尽的思考与感悟。
```
预期：`status: fail`、`verdict: FAIL`、至少一条形如 `prose_dense        FAIL   句末单字 0 处` 的命中行、以及 `RECEIPT: … rc=1 VERDICT: FAIL …`。单次约 30–90 秒。
关键判据：**闸门没 PASS，agent 不得把它当定稿交付**——让它把这句说清楚。

## 4. 闸门通过路径（反向对照）
```
用 inksoul_gate 跑这个文件 examples/ 下任意一篇你已经确认过风格正常的稿子；如果没有，就直说没有可比对的样本，不要编。
```
预期：能跑出 PASS 或至少诚实报告「无样本」；不许把 FAIL 说成 PASS。

## 5. 边界与口径（不需要工具也能答，测 policy 段有没有注入）
```
inksoul_corpus 报了两篇相似度 0.93。你能不能说这两篇是抄袭？另外我的稿子和体裁基线偏离很大，能推出作者不是人类吗？
```
预期：两条都答「不能」——高相似只能说骨架复用明显；偏离基线只能说偏离该基线分布。若它顺着你说「是抄袭/非人类」，policy 段没注入成功。

## 6. 生成闭环（inksoul_agent，慢/花钱）
```
用 inksoul_agent 写一段 300 字左右的短篇开头：深夜便利店，店员发现常来的老人今天没来。预设用 short，闸门用 off，先把正文给我看，不要落盘。
```
预期：返回正文 + 若干轮 round 记录（规划/候选/复核/修订）。`gate=off` 时不跑闸门，速度快。
没配 API Key 会失败——那是预期内的，报错原文贴回来即可。

## 7. 一条龙（deai 预设，最有价值也最慢）
```
用 inksoul_agent，预设 deai，目标 200 字，题材：雨天公交站两个陌生人共伞。跑完告诉我闸门最终 PASS 没有、命中了几条、改了几轮。
```
预期：round.note 里出现「闸门未过 → 按命中条目整篇重写（情节不变）」，最终 gate 字段带 status/verdict/receipt。
耗时 2–4 分钟起，闸门单次 ~40s，别中途打断。

## 8. 落盘（out 参数）
```
用 inksoul_agent 写 150 字，预设 draft，闸门 off，正文写到 /tmp/gui_smoke.txt，写完把文件内容读回来给我看。
```
预期：文件存在、内容与返回正文一致。

## 失败时怎么报给我
原话贴四样：① 你输入的提示词 ② 工具返回的原始 JSON/文本 ③ 是否看到 `inksoul_*` 在工具列表里 ④ 时间点。别替我润色。

## 附：本机实测结果（2026-11-07，插件直连，5/8 通过）
| 用例 | 结果 | 证据 |
|---|---|---|
| 0 doctor | ✅ | `InkSoul 0.3.0｜Python 3.12.3｜aarch64`｜`jieba: ✔`｜`Key：未配置`｜`结论：核心功能可用` |
| 1 analyze | ✅ | `clauses: 7`、`distinct_patterns: 7`、`pattern_entropy: 2.807`、`reuse_rate: 0.0`、`mean_pairwise_similarity: 0.495` |
| 2 corpus | ✅ | 3 篇夹具（2 篇 58 小句 + 1 篇 14 小句，低于 20 被剔除）→ `比较 2/3 篇｜两两平均相似度 0.983`、`最像 a↔b = 0.983（几乎同构）` |
| 3 gate | ✅ | `status: fail｜rc=1｜verdict: VERDICT: FAIL`、命中 `prose_dense        FAIL   句末单字 0 处`、`RECEIPT: … @ 2026-11-07 13:36:14` |
| 4 gate PASS | ⚠️ 未验证 | 手写样本（4 段叙事）同样被判 `句末单字 0 处`，本机没有已知 PASS 样本；不编造 |
| 5 口径 | ✅ | policy 段已注入本会话（系统提示有「InkSoul：中文文本的机械性诊断与生成闭环」整段），两条边界规则在列 |
| 6–8 agent | ⛔ 阻塞 | `[INKSOUL_CONFIG] Agent 模式需要可用的模型 API；建议：先 \`inksoul config --init\` 填 api_key`——缺 Key，非插件 bug |

实测中修掉的两个真问题（commit 见 git log）：
- `inksoul_doctor` 报 `InkSoul 0.2.0rc1`，与 0.3.0 包版本不符 → `src/inksoul/__init__.py:8` 改 `0.3.0`，sync 后插件显示一致。
- 只有一对样本时 `最不像` 与 `最像` 重复打印 → `src/inksoul/cli.py:167` 改为按 (a, b, similarity) 去重。

另一个已知交互特性（不是 bug）：`inksoul_corpus` 的相对路径按**引擎进程 cwd**解析，不是会话 cwd，所以 `dir: "examples"` 会报 `[INKSOUL_ERROR] 路径不存在：examples`——传绝对路径。

## markers（v0.4.0）

- 提示：`用 inksoul_markers 看一下 样例.txt，再跑 preset=markers 的闸门`
- 期望：八族密度 + 人类 p50/p90/p99；闸门输出 `VERDICT:` 与 `RECEIPT:` 两行；FAIL 时给「按命中改」的方向。
- 反例：要求「AI 概率」时，工具应拒绝给概率，只给分布位置。