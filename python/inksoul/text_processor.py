"""文本预处理：段落 / 句子 / 小句三级切分 + 分词 + 词性 + 统计。

为什么必须先切小句：汉语书写句常含多个小句，依存解析器会把它们压成一棵单根树
（本机实测：`他推开门，走进屋里，坐在椅子上，看着桌面。` 四个小句全挂到「推」上），
直接在书写句层面取指纹会丢层级。切分规则见 docs/algorithm_design.md §1.2。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import normalizer as norm
from .errors import AnalysisError
from .nlp.backend import BaseBackend, Token

SENT_END = "。！？!?…"
SENT_TAIL_CHARS = "”’」』）)\"'"          # 句末标点后可能跟的引号
CLAUSE_SEP = "，；：、,;:"
CLAUSE_HARD = "。！？!?…"
DASHES = "—～~"
#: 出现在小句首时应作为新小句起点的连词
CONJ_HEAD = ["然后", "于是", "但是", "可是", "不过", "因为", "所以", "如果", "虽然",
             "而", "却", "只是", "接着", "随后", "后来", "最后", "同时", "否则",
             "不仅", "而且", "并且", "然而", "因此", "假如", "要是", "哪怕", "即使"]

_MIN_CLAUSE_CHARS = 4


@dataclass
class Clause:
    id: int
    sentence_id: int
    para_id: int
    text: str
    tokens: list[Token]
    start: int = 0
    end: int = 0
    skel: list[str] = field(default_factory=list)
    sig: str = ""
    confidence: float = 1.0

    @property
    def length(self) -> int:
        return len(self.text)

    @property
    def token_count(self) -> int:
        return sum(1 for t in self.tokens if not t.is_punct)

    @property
    def has_predicate(self) -> bool:
        return any(t.norm == "V" for t in self.tokens)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "sentence_id": self.sentence_id,
            "para_id": self.para_id,
            "text": self.text,
            "length": self.length,
            "skel": self.sig,
            "tokens": [t.as_dict() for t in self.tokens],
            "confidence": round(self.confidence, 3),
        }


@dataclass
class Sentence:
    id: int
    para_id: int
    text: str
    start: int = 0
    end: int = 0
    clauses: list[Clause] = field(default_factory=list)
    tokens: list[Token] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.text)


@dataclass
class Paragraph:
    id: int
    text: str
    start: int = 0
    end: int = 0
    sentences: list[Sentence] = field(default_factory=list)


@dataclass
class Document:
    text: str
    paragraphs: list[Paragraph] = field(default_factory=list)
    backend_name: str = ""
    backend_version: str = ""
    norm_version: str = norm.NORM_TABLE_VERSION
    has_dependency: bool = False

    # ---- 便捷视图 ----
    @property
    def sentences(self) -> list[Sentence]:
        return [s for p in self.paragraphs for s in p.sentences]

    @property
    def clauses(self) -> list[Clause]:
        return [c for s in self.sentences for c in s.clauses]

    @property
    def tokens(self) -> list[Token]:
        return [t for s in self.sentences for t in s.tokens]

    def words(self) -> list[str]:
        return [t.word for t in self.tokens if not t.is_punct and t.word.strip()]

    def stats(self) -> dict:
        sents = self.sentences
        cls = self.clauses
        words = self.words()
        puncts = [t.word for t in self.tokens if t.is_punct]
        slens = [s.length for s in sents] or [0]
        clens = [c.length for c in cls] or [0]
        return {
            "chars": len(self.text),
            "paragraphs": len(self.paragraphs),
            "sentences": len(sents),
            "clauses": len(cls),
            "tokens": len(words),
            "unique_tokens": len(set(words)),
            "mean_sentence_len": round(sum(slens) / len(slens), 2),
            "mean_clause_len": round(sum(clens) / len(clens), 2),
            "max_sentence_len": max(slens),
            "punct_counts": _counter(puncts),
            "backend": self.backend_name,
            "backend_version": self.backend_version,
            "norm_version": self.norm_version,
        }


def _counter(items: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        out[it] = out.get(it, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------- 切分
def split_paragraphs(text: str) -> list[tuple[int, int, str]]:
    """按空行/单换行切段，返回 (start, end, text)。纯空白段丢弃。"""
    out: list[tuple[int, int, str]] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped:
            start = pos + len(line) - len(line.lstrip())
            out.append((start, start + len(stripped), stripped))
        pos += len(line)
    return out


def split_sentences(text: str) -> list[tuple[int, int, str]]:
    """句切分：句末标点（含连续 … / ？！」 组合）后断句。"""
    out: list[tuple[int, int, str]] = []
    buf: list[str] = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        buf.append(ch)
        if ch in SENT_END or ch == DASHES[0]:
            j = i + 1
            # 吸收连续的句末标点与随后的引号
            while j < n and (text[j] in SENT_END or text[j] in DASHES or text[j] in SENT_TAIL_CHARS):
                buf.append(text[j])
                j += 1
            # 若引号后紧跟句末标点也吸收
            seg = "".join(buf).strip()
            if seg:
                out.append((start, start + len(seg), seg))
            buf = []
            start = j
            i = j
            continue
        i += 1
    seg = "".join(buf).strip()
    if seg:
        out.append((start, start + len(seg), seg))
    return out


def _has_content(tokens: list[Token]) -> bool:
    """切分判据：小句内存在任一非标点 token（代词/副词也算，见 b4 记录）。"""
    return any(not t.is_punct for t in tokens)


def _split_clause_tokens(tokens: list[Token]) -> list[list[Token]]:
    """在 token 序列上切小句：标点边界 + 小句首连词。"""
    groups: list[list[Token]] = []
    cur: list[Token] = []
    for i, t in enumerate(tokens):
        # 连词位于小句首：若当前组已有内容，则先断开
        if t.word in CONJ_HEAD and _has_content(cur) and i > 0:
            prev = tokens[i - 1]
            if prev.is_punct or prev.norm in ("CONJ", "ADV", "PART"):
                groups.append(cur)
                cur = []
        cur.append(t)
        if t.is_punct and (t.word in CLAUSE_HARD or t.word in CLAUSE_SEP or t.word[:1] in (DASHES[0],)):
            if _has_content(cur):
                groups.append(cur)
                cur = []
            elif groups:
                groups[-1].extend(cur)   # 纯标点片段并入前一组
                cur = []
    if cur:
        if _has_content(cur) or not groups:
            groups.append(cur)
        else:
            groups[-1].extend(cur)
    # 合并过短的述谓缺失片段（如「的」字短语）
    merged: list[list[Token]] = []
    for g in groups:
        text = "".join(t.word for t in g)
        if merged and len(text.strip("，。；：、？！…—")) < _MIN_CLAUSE_CHARS and not _has_predicate(g):
            merged[-1].extend(g)
        else:
            merged.append(g)
    return [g for g in merged if "".join(t.word for t in g).strip()]


def _has_predicate(tokens: list[Token]) -> bool:
    return any(t.norm == "V" for t in tokens)


# ---------------------------------------------------------------- 主入口
class TextProcessor:
    """把原始文本变成 Document（段落 → 句子 → 小句 → token）。"""

    def __init__(self, backend: BaseBackend, *, user_dict: list[str] | None = None):
        self.backend = backend
        if user_dict:
            for w in user_dict:
                try:
                    self.backend._jieba.add_word(w)  # type: ignore[attr-defined]
                except AttributeError:
                    pass

    def process(self, text: str) -> Document:
        if not text or not text.strip():
            raise AnalysisError("输入文本为空", hint="至少给一段中文正文再分析")
        doc = Document(
            text=text,
            backend_name=getattr(self.backend, "name", "unknown"),
            backend_version=getattr(self.backend, "version", "unknown"),
            has_dependency=bool(getattr(self.backend, "has_dependency", False)),
        )
        cid = sid = 0
        for pid, (pstart, pend, ptext) in enumerate(split_paragraphs(text)):
            para = Paragraph(id=pid, text=ptext, start=pstart, end=pend)
            for sstart, send, stext in split_sentences(ptext):
                tokens = self.backend.analyze(stext)
                norm.apply(tokens, has_dep=doc.has_dependency)
                para.sentences.append(
                    Sentence(id=sid, para_id=pid, text=stext, start=pstart + sstart,
                             end=pstart + send, tokens=tokens)
                )
                sid += 1
            doc.paragraphs.append(para)

        for s in doc.sentences:
            for g in _split_clause_tokens(s.tokens):
                ctext = "".join(t.word for t in g)
                if not ctext.strip():
                    continue
                conf = 1.0 - (0.25 if not doc.has_dependency else 0.0)
                if len(ctext) <= 2:
                    conf -= 0.3
                clause = Clause(
                    id=cid, sentence_id=s.id, para_id=s.para_id, text=ctext,
                    tokens=g, start=0, end=len(ctext),
                    skel=norm.skeleton(g), sig=norm.skeleton_signature(g),
                    confidence=max(0.2, conf),
                )
                s.clauses.append(clause)
                cid += 1
        if not doc.clauses:
            raise AnalysisError(
                "未能切出任何小句（文本可能不含中文正文）",
                hint="检查输入是否为中文正文；纯符号/空白会被拒绝",
            )
        return doc


def process(text: str, backend: BaseBackend | None = None, **kwargs) -> Document:
    from .nlp.backend import build_backend

    be = backend or build_backend(kwargs.pop("backend_name", "auto"))
    return TextProcessor(be).process(text)
