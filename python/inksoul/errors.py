"""统一异常与中文错误提示。

所有对外错误都必须带「原因 + 下一步怎么做」，不允许只抛裸 Exception。
"""
from __future__ import annotations


class InkSoulError(Exception):
    """所有 InkSoul 异常的基类。"""

    code = "INKSOUL_ERROR"

    def __init__(self, message: str, *, hint: str = "", detail: dict | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.detail = detail or {}

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "detail": self.detail,
        }

    def __str__(self) -> str:  # pragma: no cover - 简单拼接
        base = f"[{self.code}] {self.message}"
        return f"{base}；建议：{self.hint}" if self.hint else base


class ConfigError(InkSoulError):
    code = "INKSOUL_CONFIG"


class BackendUnavailable(InkSoulError):
    """NLP 后端不可用（缺包、缺模型、版本不匹配）。"""

    code = "INKSOUL_BACKEND_UNAVAILABLE"


class ModelAPIError(InkSoulError):
    code = "INKSOUL_MODEL_API"


class AnalysisError(InkSoulError):
    code = "INKSOUL_ANALYSIS"


class InputTooLarge(InkSoulError):
    code = "INKSOUL_INPUT_TOO_LARGE"


class StaleFingerprint(InkSoulError):
    """指纹结果与当前分词器/归一表版本不一致。"""

    code = "INKSOUL_STALE_FINGERPRINT"
