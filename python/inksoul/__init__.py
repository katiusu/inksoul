"""InkSoul —— 面向 AI Agent 的中文文学创作增强插件（Python 算核）。

设计原则见 docs/architecture.md；所有指标都是「分布诊断」，不输出单一总分，
也不输出所谓「AI 概率」。
"""
from __future__ import annotations

__version__ = "0.3.0"  # 与 pyproject.toml 的 project.version 保持同步
SCHEMA_VERSION = "inksoul/1"

from .errors import (  # noqa: E402,F401
    AnalysisError,
    BackendUnavailable,
    ConfigError,
    InkSoulError,
    InputTooLarge,
    ModelAPIError,
    StaleFingerprint,
)
from .config import InkSoulConfig, load_config  # noqa: E402,F401


def __getattr__(name):
    """惰性导出分析器：避免子模块导入时触发重型依赖加载。"""
    if name in ("WritingAgent", "AgentResult"):
        from .agent import AgentResult, WritingAgent  # 局部导入，避免循环

        return {"WritingAgent": WritingAgent, "AgentResult": AgentResult}[name]
    if name in ("Analyzer", "analyze_text"):
        from .analyzer import Analyzer, analyze_text  # 局部导入，避免循环

        return {"Analyzer": Analyzer, "analyze_text": analyze_text}[name]
    raise AttributeError(f"module 'inksoul' has no attribute {name!r}")

__all__ = [
    "__version__",
    "SCHEMA_VERSION",
    "WritingAgent",
    "AgentResult",
    "Analyzer",
    "analyze_text",
    "InkSoulConfig",
    "load_config",
    "InkSoulError",
    "ConfigError",
    "BackendUnavailable",
    "ModelAPIError",
    "AnalysisError",
    "InputTooLarge",
    "StaleFingerprint",
]
