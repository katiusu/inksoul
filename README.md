# InkSoul

面向 AI Agent 的**中文文学创作增强**插件：从句法骨架层面诊断「机械复用」，并把诊断结果
变成可执行的写作策略与局部修订建议。

- 不输出「AI 概率」，不输出单一总分——只给可解释的分布与问题清单
- 核心零依赖：`jieba` 是可选分词后端，缺失时有中文错误提示与降级路径
- 生成侧兼容 OpenAI 格式 API（`base_url` / `api_key` / `model` 可配），也可完全离线做分析

```bash
pip install -e .          # 或 pip install inksoul-0.1.0-py3-none-any.whl
inksoul doctor            # 环境自检
inksoul analyze 稿子.txt   # 句法指纹 + 文体 + 叙事 + 审查
inksoul plan "雨夜重逢" --genre 小说
```bash
inksoul agent "雨夜重逢" --out draft.txt --gate 'bash /root/deslop/postwrite.sh {file}'
```
```

文档：`docs/project_overview.md`（总览）、`docs/usage.md`（用法）、`docs/API_SPEC.md`（接口）、
`docs/limitations.md`（已知局限，务必先读）。
