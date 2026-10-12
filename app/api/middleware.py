import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var

logger = logging.getLogger("app.request")

# Принимаем только «безопасные» id от клиента, чтобы не пускать мусор в логи.
_RID_RE = re.compile(r"[A-Za-z0-9._-]{8,64}")


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp, quiet_paths: tuple[str, ...] = ("/health", "/ready")) -> None:
        self.app = app
        self.quiet_paths = quiet_paths  # пробы пишем на уровне DEBUG, чтобы не шуметь

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        rid = headers.get(b"x-request-id", b"").decode("latin-1")
        if not _RID_RE.fullmatch(rid):
            rid = uuid.uuid4().hex
        token = request_id_var.set(rid)

        start = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = rid
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("unhandled exception")
            raise
        finally:
            path = scope["path"]
            level = (
                logging.DEBUG if path in self.quiet_paths and status < 400
                else logging.ERROR if status >= 500
                else logging.WARNING if status >= 400
                else logging.INFO
            )
            client = scope.get("client")
            logger.log(
                level,
                "request",
                extra={
                    "method": scope["method"],
                    "path": path,
                    "query": scope["query_string"].decode("latin-1"),
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                    "client": client[0] if client else None,
                    "user_agent": headers.get(b"user-agent", b"").decode("latin-1") or None,
                },
            )
            request_id_var.reset(token)
