# 使用手册

## 1. 三条主要用法

### 1.1 诊断已有稿件

```bash
inksoul analyze 稿子.txt
inksoul analyze ./章节/ --json > report.json     # 目录批量
cat 稿子.txt | inksoul analyze -
```

文本报告包含：概览、句法指纹（骨架 Top5 + 嫌疑簇）、句法多样性、文体、叙事、审阅意见。

### 1.2 先拿文体规划，再自己写

```bash
inksoul plan "雨夜，旧友在旧书店重逢" --genre 小说 --perspective 第三人称限制
```

输出 JSON：`voice / rhythm / dialogue / sentence_policy / forbidden / target_chars`。
`forbidden` 是本项目的「反套语清单」，可直接粘进写作 prompt。

### 1.3 端到端生成（需 API Key）

```bash
inksoul generate "写一个雨夜重逢的开头，600 字" --genre 小说 --out draft.txt --report
```

流程：规划 → 3 个候选（温度 0.75/0.9/1.05）→ 按**阻断级问题数**择稿 → 逐条局部修订
（每轮 ≤ 8 处）→ 复核 → 写出正文。`--report` 打印每轮自检 JSON。

## 2. 怎么读审阅意见

```json
{"kind": "机械复用", "clause_id": 7, "text": "他慢慢地推开了房门。",
 "severity": 0.7,
 "suggestion": "同一骨架在相邻段落出现了 3 次：换一种进入方式（直接写声音/物件/对话）",
 "evidence": {"signature": "PRON ADV V ASP N P", "freq": 3, "para_spread": 2,
              "evidence": ["J1 位置随机…", "J2 簇内变异极小…"]}}
```

- `kind`：`机械复用` / `相邻句式雷同` / `句首重复` / `情绪直陈`。
- `severity`：0–1，仅供排序，**不是质量分**。
- `evidence.J1–J3`：为什么判成「机械」而不是「修辞」。看到 `J3 …倾向修辞性重复`
  就不该改——那是作者的手段。
- `exempted`：被豁免的簇，列出来供人工复核（本项目不替你做最终判断）。

## 3. 工作流（对应任务书第九部分九步）

| 步 | 命令/动作 |
|---|---|
| 1 理解需求 | 写下题材、人物关系、想要的效果 |
| 2 定文体 | `inksoul plan …`，人工确认或改写 |
| 3 文体规划 | 把 `voice/rhythm/forbidden` 带进生成 prompt |
| 4 生成初稿 | `inksoul generate …`（或让 Agent 用它） |
| 5 文体分析 | `inksoul analyze draft.txt --json` |
| 6 识别机械复用 | 看 `fingerprint.suspects` 与 `review.issues` |
| 7 局部修订 | 只改被点名的小句；**先看 J3 再决定** |
| 8 检查表现力 | 看 `narrative.dialogue_*`、`style.long_short_ratio` |
| 9 输出 | 定稿；保留 `report.json` 作为版本记录 |

## 4. 常用姿势

```bash
# 只想要问题清单，不要全文报告
inksoul analyze 稿.txt --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d['review'], ensure_ascii=False, indent=2))"

# 建自己的体裁基线（用你的旧稿当参照）
inksoul baseline build ./旧稿 --genre 小说 --out ~/.dsh/inksoul/baseline.json
inksoul analyze 新稿.txt --baseline ~/.dsh/inksoul/baseline.json

# 离线试跑生成流程（不调模型，只检查配置与规划）
inksoul generate "测试" --offline --report
```

## 5. 写作时的硬规矩（避免把工具用成指标游戏）

1. 不为降低复用率而改掉**有效**的排比、回环、重复节拍。
2. 不机械替换同义词——先看骨架，再看词。
3. 不为了指标增加修辞；`forbidden` 清单只用来**删**套语，不用来加新词。
4. 修订后必须重跑 analyze，确认没有引入新的雷同。
5. 作者风格优先于任何阈值；阈值是提示，不是命令。

## 6. Agent 模式（一键闭环）

```bash
inksoul agent "雨夜，旧友在旧书店重逢" --genre 小说 --out draft.txt --report report.json \
    --gate 'bash /root/deslop/postwrite.sh {file}' --rounds 3
```

流程：规划 → 3 候选 → 择优 → 复核 → 只改被点名的小句 → **回滚判定** → 闸门。
定稿取 rank 最小的一版（闸门 > 阻断级问题数 > 问题总数），不是最后一版。

```text
阶段          字数  阻断  问题     MTLD    MATTR 闸门
候选#0         812     2     5     94.3    0.802 fail
修订#1         806     0     2    101.7    0.815 pass
```

- --gate：闸门命令，{file} 换成正文路径；不填就只跑内部复核。
- --report：每轮轨迹 + 定稿分析写 JSON，便于对比版本。
- 停止原因见 docs/agent_mode.md §4；局限见 §6。
- `--story auto|long|short|off` 注入本地 story 写作规范；`--from` 续写、`--ref` 参考拆解报告、
  `--deliver publish|cover` 额外产出发布资料/封面提示词。清单用 `inksoul skills` 看，细节见 docs/agent_mode.md §7。
- `--preset draft|long|short|rewrite|publish|cover|deai` 一键套档（候选/轮次/字数/story/交付物/闸门），
  手册 `--list-presets`，显式参数永远覆盖预设，见 docs/agent_mode.md §8。
- `--gate deslop|full|essay|zhuque|off` 文风闸门：闸门未过就按命中条目整篇重写，一条龙见 docs/agent_mode.md §9。
- `--tools` / `--tool-mode ptc|standard` 工具面：默认 PTC（模型写程序循环调 read_prev/lookup_bible/measure/run_gate，只有结论回上下文），笔记进提示、程序轨迹记入报告，见 docs/agent_mode.md §10。