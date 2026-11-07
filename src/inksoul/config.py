"""配置管理。

- 配置来源优先级：显式参数 > 环境变量 > 配置文件 > 内置默认值
- 密钥只从环境变量或 0600 权限的配置文件读取；任何输出都必须经过 redact()
- 本机 /sdcard 是 sdcardfs，不支持原子 rename，因此写入采用「临时文件 + 复制」策略
"""
from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .errors import ConfigError

DEFAULT_CONFIG_NAME = "config.json"
ENV_HOME = "INKSOUL_HOME"
ENV_API_KEY = "INKSOUL_API_KEY"
ENV_BASE_URL = "INKSOUL_BASE_URL"
ENV_MODEL = "INKSOUL_MODEL"

SECRET_FIELDS = ("api_key",)


def _default_home() -> Path:
    env = os.environ.get(ENV_HOME)
    if env:
        return Path(env).expanduser()
    dsh_home = os.environ.get("DSH_HOME") or str(Path.home() / ".dsh")
    return Path(dsh_home).expanduser() / "inksoul"


@dataclass
class ModelConfig:
    """OpenAI 兼容接口配置。"""

    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    model: str = "deepseek-chat"
    temperature: float = 0.8
    top_p: float = 0.95
    max_tokens: int = 4096
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    timeout: float = 120.0
    max_retries: int = 2
    extra_headers: dict[str, str] = field(default_factory=dict)
    #: 显式指定「模型族」，用于选择文风基线（不同模型族基线不同）
    family: str = "generic"

    def endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"


@dataclass
class AnalysisConfig:
    """分析层配置。"""

    backend: str = "auto"            # auto | jieba | spacy
    max_chars: int = 400_000         # 单次分析上限，超出抛 InputTooLarge
    chunk_chars: int = 20_000        # 长文本分块分析粒度
    norm_table_version: str = "v1"
    #: 相似度阈值（均为待标定值，见 docs/algorithm_design.md）
    cluster_sim_threshold: float = 0.60   # 与 docs/syntax_fingerprint.md §5.1 一致（未标定）
    suspect_min_freq: int = 3
    suspect_min_para_spread: int = 2
    suspect_max_gap_cv: float = 0.5
    #: 是否启用 L2/L3（需要依存句法后端）
    enable_dependency: bool = True
    enable_wl_kernel: bool = True


@dataclass
class GenerationConfig:
    """生成控制配置。"""

    candidates: int = 3
    max_revision_rounds: int = 2
    target_chars: int = 1200
    planner_model: str = ""          # 留空则用 model
    temperature_candidates: list[float] = field(default_factory=lambda: [0.75, 0.9, 1.05])


@dataclass
class AgentConfig:
    """Agent 闭环（生成→复核→改进→回滚）配置。"""

    max_rounds: int = 3
    candidates: int = 3
    #: 外部门禁命令；{file} 会被替换成正文临时文件路径
    gate_cmd: str = ""
    gate_timeout: float = 300.0
    story: str = "auto"   # auto/long/short/off：本地 story skill 注入


@dataclass(frozen=True)
class AgentPreset:
    """一条 agent 预设档：把 story 接线与预算固化成可复用的一组参数。"""

    name: str
    story: str = "auto"          # auto/long/short/off
    candidates: int = 3
    max_rounds: int = 3
    target_chars: int = 0
    deliver: str = ""            # ""/publish/cover
    require_from: bool = False   # 续写档必须给 --from
    gate: str = ""               # ""/deslop/full/essay/zhuque：文风闸门
    desc: str = ""


#: agent 预设档；CLI 用 --preset 选，显式参数永远优先于预设
AGENT_PRESETS: dict[str, AgentPreset] = {
    "draft": AgentPreset("draft", story="auto", candidates=1, max_rounds=0,
                         desc="直出：单候选、不修订，最快最省"),
    "long": AgentPreset("long", story="long", candidates=3, max_rounds=3, target_chars=3000,
                        gate="deslop",
                        desc="长篇单章：长篇规范 + 3 候选 + 最多 3 轮修订 + 定稿过闸门"),
    "short": AgentPreset("short", story="short", candidates=2, max_rounds=2, target_chars=1500,
                         gate="deslop",
                         desc="短篇：短篇规范，篇幅与轮次都更小，定稿过闸门"),
    "rewrite": AgentPreset("rewrite", story="long", candidates=2, max_rounds=2,
                           require_from=True,
                           desc="续写：必须给 --from 前文（story-import 口径）"),
    "publish": AgentPreset("publish", story="long", candidates=2, max_rounds=2, deliver="publish",
                           gate="deslop",
                           desc="成稿 + 发布资料（story-publish），定稿过闸门"),
    "cover": AgentPreset("cover", story="auto", candidates=1, max_rounds=0, deliver="cover",
                         desc="直出 + 封面提示词（story-cover）"),
    "deai": AgentPreset("deai", story="auto", candidates=2, max_rounds=3, target_chars=2000,
                        gate="deslop",
                        desc="去 AI 味一条龙：写作规范注入 + 闸门复核 + 按命中条目改进"),
}


def resolve_preset(name: str) -> AgentPreset | None:
    """按名字取预设；空名返回 None，未知名字抛 ConfigError。"""
    if not name:
        return None
    preset = AGENT_PRESETS.get(name)
    if not preset:
        raise ConfigError("未知的 agent 预设：%s" % name,
                          hint="可选：%s" % "、".join(AGENT_PRESETS))
    return preset

#: 内置闸门别名 → 实际命令；{file} 会被替换成正文临时文件路径
GATE_COMMANDS: dict[str, str] = {
    "": "",
    "off": "",
    "deslop": "/root/deslop/postwrite.sh {file}",
    "full": "/root/deslop/run_gates.sh {file}",
    "essay": "/root/deslop/postwrite.sh {file} --essay",
    "zhuque": "/root/deslop/postwrite.sh {file} --zhuque",
    # 纯 Python 内置闸门：随包发布，不依赖宿主 /root/deslop
    "markers": "__inksoul__:markers",
}


def resolve_gate(name: str) -> str:
    """闸门名 → 命令。空/off 返回空串；不像别名的当原始命令原样用。"""
    spec = (name or "").strip()
    if spec in GATE_COMMANDS:
        return GATE_COMMANDS[spec]
    if " " in spec or "/" in spec or "{file}" in spec:
        return spec   # 用户直接给了命令，例如 "python3 /x/check.py {file}"
    raise ConfigError("未知的闸门：%s" % spec,
                      hint="可选：%s；也可直接写完整命令" % "、".join(k for k in GATE_COMMANDS if k))


def merge_preset(preset: AgentPreset | None, *, story: str = "", candidates: int | None = None,
                 rounds: int | None = None, target_chars: int = 0,
                 deliver: str = "", gate: str = "") -> dict[str, Any]:
    """显式参数 > 预设 > 配置默认；返回可直接喂给 WritingAgent 的一组值。"""
    return {
        "story": story or (preset.story if preset else ""),
        "candidates": candidates if candidates is not None else (preset.candidates if preset else None),
        "max_rounds": rounds if rounds is not None else (preset.max_rounds if preset else None),
        "target_chars": target_chars or (preset.target_chars if preset else 0),
        "deliver": deliver or (preset.deliver if preset else ""),
        "gate": gate or (preset.gate if preset else ""),
    }


@dataclass
class InkSoulConfig:
    home: Path = field(default_factory=_default_home)
    model: ModelConfig = field(default_factory=ModelConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    log_level: str = "INFO"
    log_file: str = ""               # 留空则 <home>/logs/inksoul.log

    # ---------- 路径 ----------
    def path(self, *parts: str) -> Path:
        return self.home.joinpath(*parts)

    def log_path(self) -> Path:
        return Path(self.log_file).expanduser() if self.log_file else self.path("logs", "inksoul.log")

    # ---------- 序列化 ----------
    def to_dict(self, *, redact: bool = True) -> dict[str, Any]:
        data = asdict(self)
        data["home"] = str(self.home)
        if redact:
            for f in SECRET_FIELDS:
                if data["model"].get(f):
                    data["model"][f] = "***REDACTED***"
        return data

    # ---------- 校验 ----------
    def validate(self) -> None:
        m = self.model
        if not m.base_url.startswith(("http://", "https://")):
            raise ConfigError(
                f"model.base_url 必须是 http(s) 地址，当前为 {m.base_url!r}",
                hint="在配置里填写 OpenAI 兼容的 Base URL，例如 https://api.deepseek.com/v1",
            )
        if not (0.0 <= m.temperature <= 2.0):
            raise ConfigError(
                f"model.temperature 必须在 0–2 之间，当前为 {m.temperature}",
                hint="文学创作建议 0.7–1.1；过高会牺牲连贯性",
            )
        if self.analysis.backend not in ("auto", "jieba", "spacy"):
            raise ConfigError(
                f"analysis.backend 只能是 auto/jieba/spacy，当前为 {self.analysis.backend!r}",
                hint="不确定就填 auto（优先 spaCy，失败回退 jieba）",
            )
        if self.generation.candidates < 1:
            raise ConfigError("generation.candidates 至少为 1", hint="候选数 3–5 是性价比区间")
        if self.generation.candidates != len(self.generation.temperature_candidates):
            # 不报错，只补齐/截断，保持行为可预测
            temps = list(self.generation.temperature_candidates)
            if not temps:
                temps = [self.model.temperature]
            while len(temps) < self.generation.candidates:
                temps.append(min(1.3, temps[-1] + 0.15))
            self.generation.temperature_candidates = temps[: self.generation.candidates]

    def require_api_key(self) -> str:
        key = self.model.api_key or os.environ.get(ENV_API_KEY, "")
        if not key:
            raise ConfigError(
                "未配置模型 API Key",
                hint="设置环境变量 INKSOUL_API_KEY，或在配置文件中填写 model.api_key（文件权限 0600）",
            )
        return key


def _merge(dc: Any, data: dict[str, Any], where: str) -> None:
    for key, value in data.items():
        if not hasattr(dc, key):
            raise ConfigError(
                f"配置项 {where}{key} 不是已知字段",
                hint="运行 `inksoul config --show` 查看完整字段；未知字段不会被静默忽略",
            )
        current = getattr(dc, key)
        if hasattr(current, "__dataclass_fields__") and isinstance(value, dict):
            _merge(current, value, where + key + ".")
        else:
            setattr(dc, key, value)


def load_config(path: str | os.PathLike[str] | None = None, *, overrides: dict | None = None) -> InkSoulConfig:
    """加载配置。找不到文件时返回默认配置（不报错）。"""
    cfg = InkSoulConfig()
    if path is None:
        candidate = cfg.path(DEFAULT_CONFIG_NAME)
        env_path = os.environ.get("INKSOUL_CONFIG")
        path = env_path or (candidate if candidate.exists() else None)
    if path:
        p = Path(path).expanduser()
        if not p.exists():
            raise ConfigError(f"配置文件不存在：{p}", hint="运行 `inksoul config --init` 生成默认配置")
        try:
            raw = p.read_text(encoding="utf-8")
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"配置文件不是合法 JSON：{p}（{exc}）", hint="检查是否有多余逗号或中文引号") from exc
        _merge(cfg, data, "")
        cfg.home = Path(str(cfg.home)).expanduser()
    if overrides:
        _merge(cfg, overrides, "")
    # 环境变量优先级最高（便于 CI 与临时覆盖）
    if os.environ.get(ENV_BASE_URL):
        cfg.model.base_url = os.environ[ENV_BASE_URL]
    if os.environ.get(ENV_MODEL):
        cfg.model.model = os.environ[ENV_MODEL]
    if os.environ.get(ENV_API_KEY):
        cfg.model.api_key = os.environ[ENV_API_KEY]
    cfg.validate()
    return cfg


def save_config(cfg: InkSoulConfig, path: str | os.PathLike[str] | None = None) -> Path:
    """保存配置。密钥字段落盘时保持明文但强制 0600 权限，并在日志中重定向为 ***。"""
    target = Path(path).expanduser() if path else cfg.path(DEFAULT_CONFIG_NAME)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(cfg.to_dict(redact=False), ensure_ascii=False, indent=2)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, target)
    try:
        os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return target


def redact(text: str, cfg: InkSoulConfig | None = None) -> str:
    """把已知密钥从任意字符串里抹掉（日志、报错、工具输出都要过这一层）。"""
    if not text:
        return text
    secrets = set()
    if cfg is not None and cfg.model.api_key:
        secrets.add(cfg.model.api_key)
    env_key = os.environ.get(ENV_API_KEY)
    if env_key:
        secrets.add(env_key)
    out = text
    for s in secrets:
        if s and len(s) >= 6:
            out = out.replace(s, "***REDACTED***")
    return out