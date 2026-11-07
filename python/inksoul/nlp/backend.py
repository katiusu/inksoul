"""NLP 后端抽象层。

设计要点（见 docs/algorithm_design.md §1）：
- 上层模块**只依赖 Token**，不依赖具体工具；换分词器只改本文件。
- 后端能力自描述：`has_dependency` 决定 L2/L3 是否可用，而不是靠 try/except 猜。
- 缺依赖时不静默降级：能降则降并记 warning，不能降则抛 BackendUnavailable（中文提示）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..errors import BackendUnavailable

_CJK = re.compile(r"[\u3400-\u9fff]")
_PUNCT = set("，。、；：？！…—～·《》〈〉「」『』“”‘’（）()【】[]{}<>,.;:?!\"'`~-_/\\|+=*&^%$#@")


def is_cjk_char(ch: str) -> bool:
    return bool(_CJK.match(ch))


def is_punct(word: str) -> bool:
    if not word:
        return False
    if all(c in _PUNCT for c in word):
        return True
    return False


@dataclass
class Token:
    """统一 token 表示。偏移是相对于所属句子文本的字符下标。"""

    index: int
    word: str
    pos: str = ""                 # 原始词性（jieba flag 或 UD POS）
    tag: str = ""                 # 细粒度标签（spaCy tag_）
    start: int = 0
    end: int = 0
    head: int | None = None       # 依存父节点 index（None 表示后端不支持）
    deprel: str = ""              # 依存关系（UD）
    norm: str = ""                # 归一后的功能类（normalizer 填）
    sub: str = ""                 # 归一的子类（如 PREP 下的 ba/bei）

    @property
    def is_punct(self) -> bool:
        return is_punct(self.word) or self.pos in ("w", "PUNCT", "SYM")

    @property
    def is_content(self) -> bool:
        return self.norm in ("N", "V", "A", "NAME", "IDIOM", "QUANT", "M", "TIME", "LOC", "ADV?")

    def as_dict(self) -> dict:
        d = {"i": self.index, "w": self.word, "pos": self.pos, "norm": self.norm}
        if self.head is not None:
            d["head"] = self.head
            d["deprel"] = self.deprel
        return d


@runtime_checkable
class BaseBackend(Protocol):
    name: str
    version: str
    has_dependency: bool

    def analyze(self, text: str) -> list[Token]:  # pragma: no cover - 协议
        ...


class JiebaBackend:
    """jieba posseg：分词 + 词性，**无依存**。"""

    name = "jieba"
    has_dependency = False

    def __init__(self, user_dict: list[str] | None = None):
        try:
            import jieba
            import jieba.posseg as pseg
        except ImportError as exc:  # pragma: no cover - 环境相关
            raise BackendUnavailable(
                "缺少中文分词依赖 jieba",
                hint="在 Ubuntu PRoot 中执行：python3 -m pip install --break-system-packages jieba",
                detail={"missing": "jieba"},
            ) from exc
        self._jieba = jieba
        self._pseg = pseg
        self.version = getattr(jieba, "__version__", "unknown")
        for w in user_dict or []:
            jieba.add_word(w)

    def analyze(self, text: str) -> list[Token]:
        tokens: list[Token] = []
        cursor = 0
        for i, pair in enumerate(self._pseg.cut(text)):
            word = pair.word
            if not word:
                continue
            pos = pair.flag or ""
            # jieba 不给偏移：按顺序在原文里查找（对重复词也能正确前进）
            start = text.find(word, cursor)
            if start < 0:
                start = cursor
            end = start + len(word)
            cursor = end
            tokens.append(Token(index=i, word=word, pos=pos, start=start, end=end))
        return tokens


class SpacyBackend:
    """spaCy + zh_core_web_sm：分词 + UD 词性 + 依存。"""

    name = "spacy"
    has_dependency = True

    def __init__(self, model: str = "zh_core_web_sm"):
        try:
            import spacy
        except ImportError as exc:  # pragma: no cover
            raise BackendUnavailable(
                "缺少依赖 spaCy",
                hint="python3 -m pip install --break-system-packages spacy，再下载 zh_core_web_sm 模型",
                detail={"missing": "spacy"},
            ) from exc
        try:
            self._nlp = spacy.load(model)
        except OSError as exc:
            raise BackendUnavailable(
                f"spaCy 模型 {model} 未安装",
                hint=f"python3 -m spacy download {model}（aarch64 可离线放置到 site-packages）",
                detail={"missing": model},
            ) from exc
        self.version = getattr(spacy, "__version__", "unknown")
        self.model_name = model

    def analyze(self, text: str) -> list[Token]:
        doc = self._nlp(text)
        tokens: list[Token] = []
        for i, t in enumerate(doc):
            tokens.append(
                Token(
                    index=i,
                    word=t.text,
                    pos=t.pos_ or "",
                    tag=t.tag_ or "",
                    start=t.idx,
                    end=t.idx + len(t.text),
                    head=(t.head.i if t.head is not None else None),
                    deprel=t.dep_ or "",
                )
            )
        return tokens


def build_backend(name: str = "auto", *, user_dict: list[str] | None = None,
                  model: str = "zh_core_web_sm") -> BaseBackend:
    """按名字构造后端。

    `auto` = jieba 优先，spaCy 兜底（2026-10-31 实测：jieba 载入 0.9s、spaCy 12.4s；
    spaCy zh_core_web_sm 对「窗关上」切成「窗关 / 上」，中文分词质量低于 jieba。
    需要依存句法时显式选 `spacy` 或 `hybrid`，见 docs/decisions.md ADR-4）。
    """
    name = (name or "auto").lower()
    if name == "jieba":
        return JiebaBackend(user_dict=user_dict)
    if name == "spacy":
        return SpacyBackend(model=model)
    if name != "auto":
        raise BackendUnavailable(
            f"未知的 NLP 后端：{name!r}",
            hint="可选值：auto / jieba / spacy",
            detail={"backend": name},
        )
    errors: list[str] = []
    try:
        backend = JiebaBackend(user_dict=user_dict)
        setattr(backend, "fallback_from", None)
        return backend
    except BackendUnavailable as exc:
        errors.append(f"jieba: {exc.message}")
    try:
        backend = SpacyBackend(model=model)
        setattr(backend, "fallback_from", "; ".join(errors))
        return backend
    except BackendUnavailable as exc:
        errors.append(f"spacy: {exc.message}")
    raise BackendUnavailable(
        "没有可用的中文 NLP 后端（jieba 与 spaCy 均不可用）",
        hint="至少安装 jieba：python3 -m pip install --break-system-packages jieba",
        detail={"errors": errors},
    )
