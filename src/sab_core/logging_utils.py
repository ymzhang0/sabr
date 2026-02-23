from __future__ import annotations

import logging
import os
import sys
from collections import deque
from threading import Lock
from typing import Any

from loguru import logger


_LEVEL_MAP: dict[str, int] = {
    "TRACE": logging.DEBUG,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "SUCCESS": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
_VALID_LEVELS = set(_LEVEL_MAP.keys())
_SOURCE_WIDTH = 38
_FUNC_MAX_LEN = 30


class _RingLogBuffer:
    def __init__(self, maxlen: int = 600) -> None:
        self._lines: deque[str] = deque(maxlen=maxlen)
        self._version = 0
        self._lock = Lock()

    def append(self, line: str) -> None:
        with self._lock:
            self._lines.append(line)
            self._version += 1

    def snapshot(self, limit: int = 120) -> tuple[int, list[str]]:
        with self._lock:
            lines = list(self._lines)
            if limit > 0:
                lines = lines[-limit:]
            return self._version, lines


_LOG_BUFFER = _RingLogBuffer(maxlen=max(100, int(os.getenv("SABR_LOG_BUFFER_SIZE", "600"))))


def _normalize_level(value: str | None, fallback: str = "INFO") -> str:
    candidate = (value or "").strip().upper()
    if candidate in _VALID_LEVELS:
        return candidate
    return fallback


def _logging_level(level_name: str) -> int:
    return _LEVEL_MAP.get(level_name.upper(), logging.INFO)


def _short_module(module_name: Any) -> str:
    module = str(module_name or "-")
    return module.split(".")[-1] or "-"


def _short_function(function_name: Any) -> str:
    function = str(function_name or "-")
    if len(function) <= _FUNC_MAX_LEN:
        return function
    return function[: (_FUNC_MAX_LEN - 3)] + "..."


def _compact_source(module_name: Any, function_name: Any, line: Any) -> str:
    module = _short_module(module_name)
    function = _short_function(function_name)
    return f"{module}.{function}:{line}"


def _patch_record(record: dict[str, Any]) -> None:
    extra = record["extra"]
    source_module = extra.get("py_name") or record.get("name")
    source_function = extra.get("py_func") or record.get("function")
    source_line = extra.get("py_line") or record.get("line")
    extra["src"] = _compact_source(source_module, source_function, source_line)


def _render_plain_line(record: dict[str, Any]) -> str:
    ts = record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    level = str(record["level"].name).upper().ljust(8)
    src = str(record["extra"].get("src", "-")).ljust(_SOURCE_WIDTH)
    message = str(record.get("message", ""))
    return f"{ts} | {level} | {src} | {message}"


def _ring_buffer_sink(message: Any) -> None:
    _LOG_BUFFER.append(_render_plain_line(message.record))


class InterceptHandler(logging.Handler):
    """Route stdlib logging records into Loguru with original call-site metadata."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logger.bind(
            py_name=record.name,
            py_func=record.funcName,
            py_line=record.lineno,
        ).opt(
            exception=record.exc_info,
        ).log(level, record.getMessage())


def setup_logging(default_level: str = "INFO") -> str:
    """
    Configure unified logging for Loguru + stdlib logging + Uvicorn loggers.

    Environment variables:
    - SABR_LOG_LEVEL: global level for app logs.
    - SABR_ACCESS_LOG_LEVEL: level for uvicorn access logs.
    - SABR_HTTPX_LOG_LEVEL: level for httpx/httpcore logs.
    """
    global_level = _normalize_level(
        os.getenv("SABR_LOG_LEVEL") or os.getenv("SABR_DEBUG_LEVEL"),
        fallback=_normalize_level(default_level),
    )
    access_level = _normalize_level(os.getenv("SABR_ACCESS_LOG_LEVEL"), fallback="WARNING")
    httpx_level = _normalize_level(os.getenv("SABR_HTTPX_LOG_LEVEL"), fallback="WARNING")
    alembic_level = _normalize_level(os.getenv("SABR_ALEMBIC_LOG_LEVEL"), fallback="WARNING")

    logger.remove()
    logger.configure(patcher=_patch_record)
    logger.add(
        sys.stderr,
        level=global_level,
        colorize=True,
        backtrace=False,
        diagnose=False,
        enqueue=False,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[src]: <" + str(_SOURCE_WIDTH) + "}</cyan> | "
            "<level>{message}</level>"
        ),
    )
    logger.add(
        _ring_buffer_sink,
        level="TRACE",
        colorize=False,
        backtrace=False,
        diagnose=False,
        enqueue=False,
        catch=False,
    )

    root_logger = logging.getLogger()
    root_logger.handlers = [InterceptHandler()]
    root_logger.setLevel(_logging_level(global_level))

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "aiida", "alembic", "httpx", "httpcore"):
        logging_logger = logging.getLogger(name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    logging.getLogger("uvicorn").setLevel(_logging_level(global_level))
    logging.getLogger("uvicorn.error").setLevel(_logging_level(global_level))
    logging.getLogger("uvicorn.access").setLevel(_logging_level(access_level))
    logging.getLogger("httpx").setLevel(_logging_level(httpx_level))
    logging.getLogger("httpcore").setLevel(_logging_level(httpx_level))
    logging.getLogger("alembic").setLevel(_logging_level(alembic_level))

    return global_level


def get_log_buffer_snapshot(limit: int = 120) -> tuple[int, list[str]]:
    return _LOG_BUFFER.snapshot(limit=limit)


def _serialize_field(value: Any) -> str:
    if isinstance(value, str):
        compact = value.replace("\n", "\\n")
        if (not compact) or any(ch in compact for ch in (" ", "|", "'")):
            escaped = compact.replace("'", "\\'")
            return f"'{escaped}'"
        return compact
    if value is None:
        return "None"
    return str(value)


def log_event(event: str, **fields: Any) -> str:
    """Build a consistent `evt=... | key=value` log message."""
    parts = [f"evt={event}"]
    for key, value in fields.items():
        parts.append(f"{key}={_serialize_field(value)}")
    return " | ".join(parts)
