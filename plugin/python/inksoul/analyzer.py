"""InkSoul 分析器：把各个分析引擎装配成一个报告。

对外只暴露两个口子：
- `Analyzer(cfg).analyze(text)` → `AnalysisReport`
- `analyze_text(text, **kw)` 便捷函数

设计约束（见 docs/architecture.md）：
- 任一子模块缺失时**降级不崩溃**：返回占位报告并在 notes 里写明原因（移动端环境依赖不可控）。
- 报告是「多指标并列」，**不合成单一总分**——文学判断不交给一个数字。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import fingerprint as fp
from .config import InkSoulConfig
from .errors import InkSoulError
from .text_processor import Document, TextProcessor


class _Placeholder:
    """子模块未就绪时的占位报告。"""

    def __init__(self, name: str, reason: str):
        self.name = name
        self.reason = reason
        self.notes = [f"{name} 模块不可用：{reason}"]

    def as_dict(self) -> dict:
        return {"unavailable": True, "name": self.name, "reason": self.reason, "notes": self.notes}


@dataclass
class AnalysisReport:
    text: str
    meta: dict[str, Any]
    fingerprint: Any
    diversity: Any = None
    style: Any = None
    narrative: Any = None
    dependency: Any = None
    review: Any = None
    coverage: dict | None = None

    def as_dict(self, *, include_text: bool = False) -> dict:
        data = {
            "meta": self.meta,
            "fingerprint": self.fingerprint.as_dict() if hasattr(self.fingerprint, "as_dict") else self.fingerprint,
            "diversity": self.diversity.as_dict() if hasattr(self.diversity, "as_dict") else self.diversity,
            "style": self.style.as_dict() if hasattr(self.style, "as_dict") else self.style,
            "narrative": self.narrative.as_dict() if hasattr(self.narrative, "as_dict") else self.narrative,
            "dependency": self.dependency.as_dict() if hasattr(self.dependency, "as_dict") else self.dependency,
            "review": self.review.as_dict() if hasattr(self.review, "as_dict") else self.review,
        }
        if self.coverage is not None:
            data["coverage"] = self.coverage
        if include_text:
            data["text"] = self.text
        return data

    def to_json(self, *, indent: int = 2, include_text: bool = False) -> str:
        return json.dumps(self.as_dict(include_text=include_text), ensure_ascii=False, indent=indent)


@dataclass
class Analyzer:
    """分析装配器。"""

    config: InkSoulConfig
    backend: Any = None
    processor: TextProcessor | None = None
    fingerprint_engine: fp.FingerprintEngine = field(default_factory=fp.FingerprintEngine)

    def __post_init__(self) -> None:
        if self.processor is None:
            from .nlp.backend import build_backend

            be = self.backend or build_backend(self.config.analysis.backend)
            self.backend = be
            self.processor = TextProcessor(be)
        self.fingerprint_engine.sim_threshold = float(self.config.analysis.cluster_sim_threshold)

    # ---- 文本
    def process(self, text: str) -> Document:
        return self.processor.process(text)  # type: ignore[union-attr]

    # ---- 分析
    def analyze(self, text: str, *, with_review: bool = True,
                baseline: fp.Baseline | None = None) -> AnalysisReport:
        limit = int(self.config.analysis.max_chars)
        if len(text) > limit:
            from .errors import InputTooLarge

            raise InputTooLarge(f"文本 {len(text)} 字，超过单次分析上限 {limit} 字",
                                hint="用 `inksoul analyze` 的目录模式分文件分析，或调高 analysis.max_chars")
        doc = self.process(text)
        fpr = self.fingerprint_engine.analyze(doc)
        diversity = self._load("diversity", "analyze_diversity", doc)
        style = self._load("style", "analyze_style", doc)
        narrative = self._load("narrative", "analyze_narrative", doc)
        dependency = self._load("dependency", "analyze_dependency", doc)
        review = None
        if with_review:
            try:
                from .reviewer import review as do_review

                review = do_review(doc, fingerprint_report=fpr, diversity=diversity,
                                   style=style, narrative=narrative)
            except InkSoulError as exc:
                review = _Placeholder("reviewer", str(exc))
            except Exception as exc:  # noqa: BLE001 - 降级不崩溃
                review = _Placeholder("reviewer", f"{type(exc).__name__}: {exc}")
        coverage = baseline.coverage(doc) if baseline is not None else None
        meta = {
            "backend": getattr(self.backend, "name", "unknown"),
            "backend_version": getattr(self.backend, "version", "unknown"),
            "has_dependency": bool(getattr(self.backend, "has_dependency", False)),
            "chars": len(text),
            "paragraphs": len(doc.paragraphs),
            "sentences": len(doc.sentences),
            "clauses": len(doc.clauses),
            "warnings": [n for n in (getattr(fpr, "notes", []) or []) if "低置信" in n],
        }
        return AnalysisReport(
            text=text, meta=meta, fingerprint=fpr, diversity=diversity,
            style=style, narrative=narrative, dependency=dependency, review=review, coverage=coverage,
        )

    def analyze_file(self, path: str | Path, **kw) -> AnalysisReport:
        p = Path(path).expanduser()
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise InkSoulError(
                f"文件不是 UTF-8 编码：{p}",
                hint="先转码：iconv -f GB18030 -t UTF-8 原文件 > 新文件",
            ) from exc
        except OSError as exc:
            raise InkSoulError(f"读取文件失败：{p}", hint="确认路径存在且是 UTF-8 编码的中文文本") from exc
        return self.analyze(text, **kw)

    # ---- 降级装配
    def _load(self, module: str, func: str, doc: Document) -> Any:
        try:
            mod = __import__(f"inksoul.{module}", fromlist=[func])
            return getattr(mod, func)(doc)
        except InkSoulError as exc:
            return _Placeholder(module, str(exc))
        except ImportError as exc:
            return _Placeholder(module, f"模块导入失败：{exc}")
        except Exception as exc:  # noqa: BLE001
            return _Placeholder(module, f"{type(exc).__name__}: {exc}")


def analyze_text(text: str, *, config: InkSoulConfig | None = None, **kw) -> AnalysisReport:
    """便捷入口：不关心配置时直接用默认配置。"""
    return Analyzer(config or InkSoulConfig()).analyze(text, **kw)
