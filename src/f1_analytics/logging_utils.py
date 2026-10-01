"""Small logging helper with secret redaction.

The dashboard and CLI log technical exception details through this module so
programming bugs stay detectable, while user-facing messages never include
secrets or raw tracebacks.
"""

from __future__ import annotations

import logging
import re
import sys

LOGGER_NAME = "f1_analytics"

# OpenAI-style keys are the only secret in any message we log; everything
# else (DB paths, model paths) is fine to log.
_SECRET_PATTERNS = (
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"), "sk-***"),
    (re.compile(r"(api[_-]?key)\s*[:=]\s*\S+", re.IGNORECASE), r"\1=***"),
    (re.compile(r"\b(Authorization|Bearer)\s+\S+", re.IGNORECASE), r"\1 ***"),
)


def redact(text: str) -> str:
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


class RedactingLogger:
    """Logger adapter that redacts secrets before each record."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _log(self, level: int, msg: str, *args: object) -> None:
        text = msg if not args else msg % args
        self._logger.log(level, redact(str(text)))

    def error(self, msg: str, *args: object) -> None:
        self._log(logging.ERROR, msg, *args)

    def warning(self, msg: str, *args: object) -> None:
        self._log(logging.WARNING, msg, *args)

    def info(self, msg: str, *args: object) -> None:
        self._log(logging.INFO, msg, *args)

    def exception(self, msg: str, *args: object) -> None:
        self._log(logging.ERROR, msg, *args)


_log = RedactingLogger(get_logger())


def log_error(msg: str, *args: object) -> None:
    _log.error(msg, *args)


def log_warning(msg: str, *args: object) -> None:
    _log.warning(msg, *args)


def log_info(msg: str, *args: object) -> None:
    _log.info(msg, *args)


__all__ = ["redact", "log_error", "log_warning", "log_info"]