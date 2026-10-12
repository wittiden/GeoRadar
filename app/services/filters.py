from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.contract import MINSK
from app.models import Measurement, Parameter, Station


def aware(dt: datetime | None) -> datetime | None:
    """Время без часового пояса считаем минским (правило контракта)."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=MINSK)
    return dt


@dataclass
class StationFilter:
    source: list[str] | None = None
    kind: list[str] | None = None
    bbox: tuple[float, float, float, float] | None = None  # min_lon, min_lat, max_lon, max_lat
    q: str | None = None  # подстрока в названии

    def apply(self, stmt):
        if self.source:
            stmt = stmt.where(Station.source.in_(self.source))
        if self.kind:
            stmt = stmt.where(Station.kind.in_(self.kind))
        if self.bbox:
            min_lon, min_lat, max_lon, max_lat = self.bbox
            stmt = stmt.where(Station.lon.between(min_lon, max_lon), Station.lat.between(min_lat, max_lat))
        if self.q:
            esc = self.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(Station.name.ilike(f"%{esc}%", escape="\\"))
        return stmt


@dataclass
class MeasurementFilter:
    source: list[str] | None = None
    station_id: list[int] | None = None
    parameter: list[str] | None = None
    kind: list[str] | None = None
    sub_point: str | None = None
    date_from: datetime | None = None  # включительно
    date_to: datetime | None = None    # включительно

    def apply(self, stmt):
        if self.source:
            stmt = stmt.where(Station.source.in_(self.source))
        if self.station_id:
            stmt = stmt.where(Measurement.station_id.in_(self.station_id))
        if self.parameter:
            stmt = stmt.where(Measurement.parameter.in_(self.parameter))
        if self.kind:
            stmt = stmt.where(Station.kind.in_(self.kind))
        if self.sub_point is not None:
            stmt = stmt.where(Measurement.sub_point == self.sub_point)
        if self.date_from:
            stmt = stmt.where(Measurement.measured_at >= self.date_from)
        if self.date_to:
            stmt = stmt.where(Measurement.measured_at <= self.date_to)
        return stmt


def measurement_select(*columns):
    """SELECT по измерениям с join станций и параметров (фильтры работают по этим таблицам)."""
    return (
        select(*columns)
        .select_from(Measurement)
        .join(Station, Station.id == Measurement.station_id)
        .join(Parameter, Parameter.code == Measurement.parameter)
    )
