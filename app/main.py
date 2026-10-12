import logging

from fastapi import FastAPI

from app.api.middleware import RequestLoggingMiddleware
from app.api.routers import api_router, health
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging(settings.log_level, settings.log_json)
logger = logging.getLogger("app")

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(RequestLoggingMiddleware)
app.include_router(health.router)
app.include_router(api_router, prefix="/api/v1")

logger.info("app configured", extra={"log_json": settings.log_json, "level": settings.log_level})
