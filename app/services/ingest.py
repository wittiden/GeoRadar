"""Запись измерений в БД. Единая точка входа для ВСЕХ источников и загрузки CSV.

Идемпотентно: повторная запись тех же данных дублей не создаёт
(ключ уникальности: станция + параметр + sub_point + время).
"""
import logging
import time

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.contract import MeasurementIn
from app.models import Measurement, Parameter, Station
from app.sources.registry import REGISTRY

logger = logging.getLogger(__name__)
BATCH = 1000
MAX_ERRORS = 20


class IngestResult(BaseModel):
    received: int      # сколько записей пришло
    inserted: int      # сколько новых записано
    duplicates: int    # уже были в БД
    rejected: int      # отклонено (напр. единица не совпала со справочником)
    errors: list[str] = []  # первые причины отклонения


def _chunks(rows: list, size: int):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def ingest(db: Session, items: list[MeasurementIn]) -> IngestResult:
    if not items:
        return IngestResult(received=0, inserted=0, duplicates=0, rejected=0)
    try:
        return _ingest(db, items)
    except Exception:
        db.rollback()
        raise


def _ingest(db: Session, items: list[MeasurementIn]) -> IngestResult:
    # 1. Параметры: неизвестные создаём, у известных сверяем единицу.
    units = {p.code: p.unit for p in db.scalars(select(Parameter).where(Parameter.code.in_({i.parameter for i in items})))}
    new_params = {}
    for i in items:
        if i.parameter not in units and i.parameter not in new_params:
            new_params[i.parameter] = {"code": i.parameter, "name": i.parameter_name or i.parameter, "unit": i.unit}
    if new_params:
        db.execute(insert(Parameter).values(list(new_params.values())).on_conflict_do_nothing())
        units.update({c: p["unit"] for c, p in new_params.items()})

    good: list[MeasurementIn] = []
    errors: list[str] = []
    rejected = 0
    for i in items:
        if i.unit != units[i.parameter]:
            rejected += 1
            if len(errors) < MAX_ERRORS:
                errors.append(f"{i.parameter}: единица {i.unit!r}, в справочнике {units[i.parameter]!r}")
        else:
            good.append(i)

    # 2. Станции: upsert по (source, external_id), побеждает последняя версия.
    stations = {(i.station.source, i.station.external_id): i.station for i in good}
    station_rows = [
        {"source": s.source, "external_id": s.external_id, "name": s.name, "kind": s.kind.value,
         "address": s.address, "lat": s.lat, "lon": s.lon, "geo_quality": s.geo_quality.value}
        for s in stations.values()
    ]
    station_ids: dict[tuple[str, str], int] = {}
    for chunk in _chunks(station_rows, BATCH):
        stmt = insert(Station).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_stations_source_external_id",
            set_={c: stmt.excluded[c] for c in ("name", "kind", "address", "lat", "lon", "geo_quality")},
        ).returning(Station.id, Station.source, Station.external_id)
        for r in db.execute(stmt):
            station_ids[(r.source, r.external_id)] = r.id

    # 3. Измерения: дубли молча пропускаются.
    rows = [
        {"station_id": station_ids[(i.station.source, i.station.external_id)], "parameter": i.parameter,
         "sub_point": i.sub_point, "sub_point_name": i.sub_point_name, "value": i.value, "pdk": i.pdk,
         "period_kind": i.period_kind.value, "measured_at": i.measured_at, "source_url": i.source_url,
         "raw": i.raw}
        for i in good
    ]
    inserted = 0
    for chunk in _chunks(rows, BATCH):
        stmt = insert(Measurement).values(chunk).on_conflict_do_nothing(constraint="uq_measurements_series")
        inserted += len(db.execute(stmt.returning(Measurement.id)).all())
    db.commit()

    return IngestResult(received=len(items), inserted=inserted, duplicates=len(good) - inserted,
                        rejected=rejected, errors=errors)


def collect(db: Session, code: str) -> IngestResult:
    """Запустить адаптер источника и записать результат в БД. KeyError, если источника нет в реестре."""
    adapter = REGISTRY[code]()
    started = time.perf_counter()
    logger.info("collect started", extra={"source_code": code})
    items = adapter.fetch()
    result = ingest(db, items)
    logger.info(
        "collect finished",
        extra={"source_code": code, "duration_ms": round((time.perf_counter() - started) * 1000, 1),
               **result.model_dump(exclude={"errors"})},
    )
    return result
