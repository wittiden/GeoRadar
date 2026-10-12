import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Всё, что не входит в стандартные атрибуты LogRecord, считаем «extra».
_STD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime", "taskName"}


def _extra(record: logging.LogRecord) -> dict:
    return {k: v for k, v in record.__dict__.items() if k not in _STD}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if rid := request_id_var.get():
            data["request_id"] = rid
        data.update(_extra(record))
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def formatMessage(self, record: logging.LogRecord) -> str:
        line = super().formatMessage(record)
        parts = [f"{k}={v}" for k, v in _extra(record).items()]
        if rid := request_id_var.get():
            parts.insert(0, f"request_id={rid}")
        return f"{line} {' '.join(parts)}" if parts else line


def setup_logging(level: str = "INFO", json_logs: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter() if json_logs
        else TextFormatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # uvicorn пишет через наш root-логгер, чтобы формат был единым.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
