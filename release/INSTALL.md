# InkSoul 安装指南（release 包）

## 1. 一句话安装

```bash
python3 -m pip install inksoul-0.1.0-py3-none-any.whl
python3 -m pip install jieba     # 强烈建议；缺了也能装，但 analyze 会报中文错误
inksoul doctor
```

`doctor` 输出 `结论：核心功能可用` 即成功（exit 0）。缺 jieba 时 exit 2 且 `jieba: ✘ 缺失`。

## 2. 无 root / pip 受限时

```bash
python3 -m pip install --user --no-deps inksoul-0.1.0-py3-none-any.whl
export PATH="$HOME/.local/bin:$PATH"
```

或装到任意目录并用 PYTHONPATH 运行（本机实测可行）：

```bash
python3 -m pip install --no-deps --target /opt/inksoul inksoul-0.1.0-py3-none-any.whl
PYTHONPATH=/opt/inksoul python3 -m inksoul.cli doctor
```

## 3. 配置模型（仅生成正文需要）

```bash
mkdir -p ~/.dsh/inksoul && chmod 700 ~/.dsh/inksoul
cat > ~/.dsh/inksoul/config.json <<'JSON'
{"model": {"base_url": "https://api.deepseek.com/v1",
           "api_key": "sk-替换成你的密钥",
           "model": "deepseek-chat"}}
JSON
chmod 600 ~/.dsh/inksoul/config.json
```

或：`export INKSOUL_API_KEY=sk-…`（优先级更高）。配置项完整清单见 `docs/API_SPEC.md` §2。

## 4. 三条验证命令

```bash
inksoul doctor
printf '他慢慢地推开了房门。\n她轻轻地关上了窗户。\n' > /tmp/t.txt && inksoul analyze /tmp/t.txt
inksoul plan "雨夜，旧友重逢" --genre 小说
```

预期：第一句 exit 0；第二条给出「机械复用」问题（同一骨架 ×2）；
第三条输出 JSON 规划（`voice/rhythm/forbidden` 等）。

## 5. 在 Agent 里用

把 `skills/inksoul-writing/`、`skills/inksoul-diagnose/` 复制进 Agent 的 skills 目录，
Agent 即可按其中的流程调用 `inksoul` 命令。

## 6. 卸载

```bash
python3 -m pip uninstall -y inksoul
rm -rf ~/.dsh/inksoul   # 可选：配置、日志、基线
```
