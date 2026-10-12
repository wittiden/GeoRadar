import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import ParameterOut, SourceOut
from app.core.db import get_db
from app.models import Measurement, Parameter, Station
from app.services.ingest import IngestResult, collect
from app.sources.registry import REGISTRY

logger = logging.getLogger(__name__)
router = APIRouter(tags=["catalog"])


@router.get("/sources", response_model=list[SourceOut], summary="Источники и сколько в них данных")
def list_sources(db: Session = Depends(get_db)):
    stmt = (
        select(
            Station.source,
            func.count(func.distinct(Station.id)).label("stations"),
            func.count(Measurement.id).label("measurements"),
            func.min(Measurement.measured_at).label("first_measured_at"),
            func.max(Measurement.measured_at).label("last_measured_at"),
        )
        .select_from(Station)
        .outerjoin(Measurement, Measurement.station_id == Station.id)
        .group_by(Station.source)
        .order_by(Station.source)
    )
    return [SourceOut(**r._mapping) for r in db.execute(stmt)]


@router.post("/sources/{code}/collect", response_model=IngestResult,
             summary="Запустить сбор источника (синхронно, ждёт завершения)")
def collect_source(code: str, db: Session = Depends(get_db)):
    if code not in REGISTRY:
        raise HTTPException(404, f"unknown source {code!r}; registered: {sorted(REGISTRY)}")
    try:
        return collect(db, code)
    except Exception as e:
        logger.exception("collect failed", extra={"source_code": code})
        raise HTTPException(502, f"collect failed: {type(e).__name__}: {e}")


@router.get("/parameters", response_model=list[ParameterOut], summary="Справочник параметров")
def list_parameters(db: Session = Depends(get_db)):
    return db.scalars(select(Parameter).order_by(Parameter.code)).all()
