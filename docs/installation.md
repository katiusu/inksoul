# 安装指南

## 0. 环境要求

| 项 | 要求 | 实测环境 |
|---|---|---|
| Python | ≥ 3.9 | 3.12.3（aarch64 / Ubuntu PRoot on Android） |
| 内存 | ≥ 512 MB 空闲 | 手机可用 |
| GPU | **不需要** | 无 |
| 网络 | 仅「生成正文」需要 | 分析全程离线 |
| 核心依赖 | **无**（jieba 可选） | jieba 0.42.1 |

## 1. 从 wheel 安装（推荐）

```bash
cd release
python3 -m pip install --user inksoul-0.1.0-py3-none-any.whl
python3 -m pip install --user jieba          # 可选但强烈建议；缺失时 analyze 会报中文提示
inksoul doctor
```

预期输出（本机实测）：

```
InkSoul 0.1.0｜Python 3.12.3｜aarch64
配置目录：/root/.dsh/inksoul
  jieba: ✔
  NLP 后端：jieba 0.42.1（依存：False）
  模型：deepseek-chat @ https://api.deepseek.com/v1｜Key：未配置
结论：核心功能可用
```

`doctor` 在缺 jieba 时输出 `✘ 缺失` 并 **exit 2**（明确失败，不静默降级）。

## 2. 从源码安装（开发用）

```bash
git clone …  # 或直接进入源码目录
pip install -e .
python3 -m unittest discover -s tests -p "test_*.py" -t .   # 77 项
```

## 3. 在 DSH / Agent 中接入

本插件是**标准 Python 包 + CLI**（DSH 当前没有 Python 插件原生加载协议，见
`docs/architecture.md` §6）：

1. 让 Agent 能执行 `inksoul` 命令（PATH 中有该可执行文件即可）；
2. 把 `skills/inksoul-writing/SKILL.md` 放进 Agent 的 skills 目录；
3. SKILL 里定义了「何时调 analyze、如何读 JSON、如何按问题做局部修订」的流程。

## 4. 配置模型（只在需要生成正文时）

```bash
mkdir -p ~/.dsh/inksoul
cat > ~/.dsh/inksoul/config.json <<'JSON'
{"model": {"base_url": "https://api.deepseek.com/v1",
           "api_key": "sk-你的密钥",
           "model": "deepseek-chat"}}
JSON
chmod 600 ~/.dsh/inksoul/config.json
```

或只用环境变量：`export INKSOUL_API_KEY=sk-…`（优先级高于配置文件）。

**安全**：密钥不进日志、不进 git；`inksoul doctor` 只显示「已配置/未配置」；
`config.json` 建议 `chmod 600`。

## 5. 卸载

```bash
python3 -m pip uninstall -y inksoul
rm -rf ~/.dsh/inksoul          # 配置与日志（可选）
```

## 6. 排障

| 现象 | 原因 | 处理 |
|---|---|---|
| `错误：NLP 后端不可用…` | 缺 jieba | `pip install jieba` |
| `错误：文本过长（… > 400000 字）` | 超上限 | 分段分析，或调大 `analysis.max_chars` |
| `错误：未配置 API Key` | 无密钥 | 见 §4 |
| `3` 退出码 | 模型接口失败 | 看 stderr 的 `提示：` 行（鉴权/超时/限流） |
| 首次 analyze 卡 1–10 s | jieba 构建前缀词典 | 正常；`jieba` 会缓存 |
