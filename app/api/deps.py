from datetime import datetime

from fastapi import HTTPException, Query

from app.services.filters import MeasurementFilter, StationFilter, aware

BBOX_DESC = "Рамка: minLon,minLat,maxLon,maxLat (например 23,51,33,56.5)"


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = (float(x) for x in raw.split(","))
    except ValueError:
        raise HTTPException(422, "bbox: нужно 4 числа через запятую: minLon,minLat,maxLon,maxLat")
    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(422, "bbox: min должен быть меньше max")
    return min_lon, min_lat, max_lon, max_lat


def get_station_filter(
    source: list[str] | None = Query(None, description="Источник; можно несколько: ?source=a&source=b"),
    kind: list[str] | None = Query(None, description="Тип станции"),
    bbox: str | None = Query(None, description=BBOX_DESC),
    q: str | None = Query(None, description="Подстрока в названии"),
) -> StationFilter:
    return StationFilter(source=source, kind=kind, bbox=_parse_bbox(bbox), q=q)


def get_measurement_filter(
    source: list[str] | None = Query(None, description="Источник; можно несколько"),
    station_id: list[int] | None = Query(None, description="id станции; можно несколько"),
    parameter: list[str] | None = Query(None, description="Код параметра; можно несколько"),
    kind: list[str] | None = Query(None, description="Тип станции"),
    sub_point: str | None = Query(None, description="Точный sub_point (напр. номер источника выбросов)"),
    date_from: datetime | None = Query(None, description="С (включительно). Без пояса = Europe/Minsk"),
    date_to: datetime | None = Query(None, description="По (включительно). Без пояса = Europe/Minsk"),
) -> MeasurementFilter:
    return MeasurementFilter(
        source=source, station_id=station_id, parameter=parameter, kind=kind,
        sub_point=sub_point, date_from=aware(date_from), date_to=aware(date_to),
    )
