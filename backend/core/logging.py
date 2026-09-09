"""Structured JSON log formatter (stdlib only).

Referenced from settings.LOGGING via dictConfig as ``'()': 'core.logging.JsonFormatter'``.
dictConfig lazy-imports the dotted path when logging is actually configured, so
settings.py stays free of any import-time dependency on this module.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from typing import Any

# Standard LogRecord attributes rendered explicitly in the base payload; skipped
# when copying record.__dict__ extras. 'event' is handled via getattr() in format().
_RESERVED = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "message", "module",
    "msecs", "msg", "name", "pathname", "processName", "relativeCreated",
    "stack_info", "thread", "threadName", "event",
})

# HttpRequest/HttpResponse objects Django passes as extra on django.request logs;
# str()-ing them would be noisy. Dropped.
_SKIP_EXTRAS = frozenset({"request", "response"})


def _default(value: Any) -> str:
    """json.dumps(default=...) for non-serializable extras."""
    s = str(value)
    return s if len(s) <= 500 else s[:500] + "...[truncated]"


class JsonFormatter(logging.Formatter):
    """One JSON object per log line.

    Always-present keys: timestamp, level, logger, message, event, module,
    line, func, process, thread. Keys passed via extra={...} are merged as
    top-level fields (method/path/status/duration_ms/user_id, ...). Exceptions
    are rendered through formatException() into an 'exc_info' string; json.dumps
    escapes newlines, so the output stays one physical line per record.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        # dictConfig may pass fmt/datefmt/format kwargs; we do not need them.
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _dt.datetime.fromtimestamp(
                record.created, tz=_dt.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self._message(record),
            "event": getattr(record, "event", None),
            "module": record.module,
            "line": record.lineno,
            "func": record.funcName,
            "process": record.process,
            "thread": record.threadName,
        }

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _RESERVED or key in _SKIP_EXTRAS:
                continue
            payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        # ensure_ascii=False: keep human-readable UTF-8 in the JSON output. If a
        # codec error ever appears in a weird locale, switch back to True.
        return json.dumps(payload, ensure_ascii=False, default=_default)

    @staticmethod
    def _message(record: logging.LogRecord) -> str:
        try:
            return record.getMessage()
        except Exception:
            return str(getattr(record, "msg", record))
