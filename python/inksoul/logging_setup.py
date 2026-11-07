"""日志系统：文件 + 控制台，所有消息经 redact() 脱敏。"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from .config import InkSoulConfig, redact

_LOGGER_NAME = "inksoul"


class _RedactFilter(logging.Filter):
    def __init__(self, cfg: InkSoulConfig):
        super().__init__()
        self.cfg = cfg

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover - 防御性
            return True
        record.msg = redact(msg, self.cfg)
        record.args = ()
        return True


def setup_logging(cfg: InkSoulConfig, *, level: str | None = None) -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(getattr(logging, (level or cfg.log_level).upper(), logging.INFO))
    logger.propagate = False
    for h in list(logger.handlers):
        logger.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    stream.addFilter(_RedactFilter(cfg))
    logger.addHandler(stream)

    path: Path = cfg.log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.addFilter(_RedactFilter(cfg))
        logger.addHandler(fh)
    except OSError as exc:  # 只读环境下降级为仅控制台
        logger.warning("日志文件不可写（%s），已降级为仅控制台输出", exc)
    return logger


def get_logger(name: str = "") -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME + (f".{name}" if name else ""))
