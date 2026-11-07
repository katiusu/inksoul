"""可替换的中文 NLP 后端接口。"""
from .backend import BaseBackend, JiebaBackend, SpacyBackend, Token, build_backend  # noqa: F401

__all__ = ["BaseBackend", "JiebaBackend", "SpacyBackend", "Token", "build_backend"]
