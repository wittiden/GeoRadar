import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness: процесс жив")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness: доступна БД")
def ready(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("database is not available")
        raise HTTPException(503, "database unavailable")
    return {"status": "ready"}
