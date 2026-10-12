from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_measurement_filter
from app.api.schemas import MeasurementOut, Page
from app.core.db import get_db
from app.models import Measurement, Parameter, Station
from app.services.filters import MeasurementFilter, measurement_select

router = APIRouter(prefix="/measurements", tags=["measurements"])


@router.get("", response_model=Page[MeasurementOut], summary="Измерения с фильтрами и пагинацией")
def list_measurements(
    f: MeasurementFilter = Depends(get_measurement_filter),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    order: Literal["asc", "desc"] = Query("desc", description="Сортировка по времени измерения"),
    db: Session = Depends(get_db),
):
    columns = (
        Measurement.id, Measurement.station_id,
        Station.name.label("station_name"), Station.kind.label("station_kind"),
        Station.source, Station.lat, Station.lon,
        Measurement.parameter, Parameter.name.label("parameter_name"), Parameter.unit,
        Measurement.value, Measurement.pdk, Measurement.period_kind, Measurement.measured_at,
        Measurement.sub_point, Measurement.sub_point_name,
    )
    sort = Measurement.measured_at.asc() if order == "asc" else Measurement.measured_at.desc()
    rows = db.execute(
        f.apply(measurement_select(*columns)).order_by(sort, Measurement.id).limit(limit).offset(offset)
    ).all()
    total = db.scalar(f.apply(measurement_select(func.count(Measurement.id))))
    return Page(total=total, limit=limit, offset=offset, items=[MeasurementOut(**r._mapping) for r in rows])
