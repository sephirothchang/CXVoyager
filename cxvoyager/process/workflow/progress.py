# SPDX-License-Identifier: GPL-3.0-or-later
"""Progress feed utilities used to share live updates across workflow stages."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, MutableMapping

from .runtime_context import RunContext

__all__ = [
    "PROGRESS_MESSAGES_KEY",
    "PROGRESS_SINK_KEY",
    "record_progress",
    "progress_info",
    "progress_warning",
    "progress_error",
    "progress_debug",
    "create_stage_progress_logger",
]

PROGRESS_MESSAGES_KEY = "progress_messages"
PROGRESS_SINK_KEY = "progress_log_sink"


def _normalize_stage(stage: Any) -> str | None:
    if stage is None:
        return None
    if hasattr(stage, "value"):
        return str(getattr(stage, "value"))
    return str(stage)


def _normalize_level(level: Any) -> str:
    if isinstance(level, str):
        return level.lower()
    name = logging.getLevelName(level)
    if isinstance(name, str):
        return name.lower()
    try:
        return str(level).lower()
    except Exception:  # pragma: no cover - defensive
        return "info"


def _safe_repr(data: Any) -> str:
    try:
        return repr(data)
    except Exception:  # pragma: no cover - defensive
        return str(data)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _append_to_context(ctx: RunContext, entry: Dict[str, Any]) -> None:
    messages: List[Dict[str, Any]] = ctx.extra.setdefault(PROGRESS_MESSAGES_KEY, [])
    messages.append(entry)

    sink = ctx.extra.get(PROGRESS_SINK_KEY)
    if callable(sink):
        try:
            sink(entry)
        except Exception:  # pragma: no cover - defensive
            # sink implementations should be trusted, but never break the workflow
            pass


def record_progress(
    ctx: RunContext | None,
    message: str,
    *,
    stage: str | None = None,
    level: str = "info",
    extra: Dict[str, Any] | None = None,
) -> None:
    """Store a progress entry on the given context and broadcast it if possible."""

    if ctx is None:
        return

    normalized_level = (level or "info").lower()
    stage_value: str | None
    if stage is None:
        stage_value = None
    elif hasattr(stage, "value"):
        stage_value = getattr(stage, "value")
    else:
        stage_value = str(stage)

    entry: Dict[str, Any] = {
        "message": message,
        "stage": stage_value,
        "level": normalized_level,
        "at": _now(),
    }
    if extra:
        entry["extra"] = extra

    _append_to_context(ctx, entry)


def progress_info(ctx: RunContext | None, message: str, *, stage: str | None = None, extra: Dict[str, Any] | None = None) -> None:
    record_progress(ctx, message, stage=stage, level="info", extra=extra)


def progress_warning(ctx: RunContext | None, message: str, *, stage: str | None = None, extra: Dict[str, Any] | None = None) -> None:
    record_progress(ctx, message, stage=stage, level="warning", extra=extra)


def progress_error(ctx: RunContext | None, message: str, *, stage: str | None = None, extra: Dict[str, Any] | None = None) -> None:
    record_progress(ctx, message, stage=stage, level="error", extra=extra)


def progress_debug(ctx: RunContext | None, message: str, *, stage: str | None = None, extra: Dict[str, Any] | None = None) -> None:
    record_progress(ctx, message, stage=stage, level="debug", extra=extra)


class ProgressLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that mirrors log entries into the progress feed."""

    def __init__(
        self,
        logger: logging.Logger,
        ctx: RunContext | None,
        stage: Any,
        *,
        prefix: str | None = None,
        include_progress_extra_in_message: bool = True,
    ) -> None:
        stage_value = _normalize_stage(stage)
        extra: MutableMapping[str, Any] = {}
        if stage_value is not None:
            extra["stage"] = stage_value
        super().__init__(logger, extra)
        self._ctx = ctx
        self._stage = stage_value
        self._prefix = prefix
        self._include_progress_extra_in_message = include_progress_extra_in_message

    def log(self, level: int, msg: str, *args: Any, progress_extra: Mapping[str, Any] | None = None, **kwargs: Any) -> None:  # type: ignore[override]
        message = msg % args if args else msg
        normalized_level = _normalize_level(level)

        if progress_extra:
            progress_extra_dict: Dict[str, Any] | None = dict(progress_extra)
        elif progress_extra is None:
            progress_extra_dict = None
        else:
            progress_extra_dict = dict(progress_extra)

        record_progress(self._ctx, message, stage=self._stage, level=normalized_level, extra=progress_extra_dict)

        if not self.logger.isEnabledFor(level):
            return

        log_message = message
        if self._include_progress_extra_in_message and progress_extra_dict:
            log_message = f"{log_message} | extra={_safe_repr(progress_extra_dict)}"
        if self._prefix:
            log_message = f"{self._prefix} {log_message}"

        # Ensure adapter extras are merged with kwargs extras like standard LoggerAdapter
        processed_kwargs = dict(kwargs)
        extra_from_kwargs = processed_kwargs.get("extra")
        if extra_from_kwargs is None:
            extra_from_kwargs = {}
            processed_kwargs["extra"] = extra_from_kwargs
        if progress_extra_dict is not None:
            extra_from_kwargs.setdefault("progress_extra", progress_extra_dict)

        log_message, processed_kwargs = self.process(log_message, processed_kwargs)
        self.logger._log(level, log_message, (), **processed_kwargs)


def create_stage_progress_logger(
    ctx: RunContext | None,
    stage: Any,
    *,
    logger: logging.Logger | None = None,
    prefix: str | None = None,
    include_progress_extra_in_message: bool = True,
) -> ProgressLoggerAdapter:
    base_logger = logger or logging.getLogger(__name__)
    return ProgressLoggerAdapter(
        base_logger,
        ctx,
        stage,
        prefix=prefix,
        include_progress_extra_in_message=include_progress_extra_in_message,
    )