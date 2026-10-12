from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator

MINSK = ZoneInfo("Europe/Minsk")

# Грубый bbox Беларуси (с запасом). Нужен, чтобы ловить перепутанные lat/lon.
LAT_MIN, LAT_MAX = 51.0, 56.5
LON_MIN, LON_MAX = 23.0, 33.0

# Коды источников. Новый источник = новая константа + адаптер в app/sources/.
SOURCE_RAD_RSS = "rad_rss"
SOURCE_ORSHA = "orsha_ecokarta"
SOURCE_UPLOAD = "upload"


class GeoQuality(str, Enum):
    source = "source"        # координаты пришли из самого источника
    geocoded = "geocoded"    # получены геокодингом по названию
    manual = "manual"        # внесены вручную / из справочника


class StationKind(str, Enum):
    air_post = "air_post"                  # пост наблюдения за воздухом
    industrial_site = "industrial_site"    # предприятие / промплощадка / источник выбросов
    radiation_post = "radiation_post"      # пост радиационного мониторинга
    other = "other"


class PeriodKind(str, Enum):
    """За какой промежуток времени значение. measured_at = НАЧАЛО промежутка."""
    instant = "instant"  # момент времени (rad.org.by)
    day = "day"          # сутки (orsha: «1 октября 2026 г.»)
    month = "month"      # месяц (orsha: «Июнь 2026»)


def _clean(s: str) -> str:
    """Убирает лишние пробелы и переводы строк (напр. 'Браслав\\n')."""
    return re.sub(r"\s+", " ", s).strip()


class StationIn(BaseModel):
    source: str
    # Идентификатор поста В ИСТОЧНИКЕ. orsha: Nid (str). rad.org.by: id нет ->
    # нормализованное название. Пара (source, external_id) уникальна.
    external_id: str
    name: str
    kind: StationKind = StationKind.other
    address: str | None = None
    lat: float = Field(ge=LAT_MIN, le=LAT_MAX)
    lon: float = Field(ge=LON_MIN, le=LON_MAX)
    geo_quality: GeoQuality

    @field_validator("name", "external_id")
    @classmethod
    def _norm(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("не может быть пустым")
        return v

    @field_validator("address")
    @classmethod
    def _norm_addr(cls, v: str | None) -> str | None:
        return _clean(v) or None if v is not None else None


class MeasurementIn(BaseModel):
    station: StationIn
    # Код параметра из справочника, напр. 'gamma_dose_rate', 'air_no2'.
    parameter: str = Field(pattern=r"^[a-z0-9_]+$")
    # Название параметра: используется только если параметра ещё нет в справочнике.
    parameter_name: str | None = None
    value: Decimal = Field(allow_inf_nan=False)
    unit: str                         # каноническая единица, напр. 'uSv/h'
    measured_at: datetime             # после валидации всегда aware, в UTC
    period_kind: PeriodKind = PeriodKind.instant
    pdk: Decimal | None = None        # ПДК/норматив, как указан в источнике
    # Доп. ключ ряда внутри станции (напр. номер источника выбросов).
    # Пустая строка = нет. Входит в ключ уникальности.
    sub_point: str = ""
    sub_point_name: str | None = None
    source_url: str | None = None
    raw: dict | None = None           # исходная запись источника (для отладки)

    @field_validator("measured_at")
    @classmethod
    def _to_utc(cls, v: datetime) -> datetime:
        # Без часового пояса считаем, что это Europe/Minsk (UTC+3, без DST).
        if v.tzinfo is None:
            v = v.replace(tzinfo=MINSK)
        return v.astimezone(timezone.utc)


_CSV_OPTIONAL = {"station_kind", "station_address", "period_kind", "pdk",
                 "sub_point", "sub_point_name", "source_url"}


class CsvRow(BaseModel):
    """Одна строка загружаемого/выгружаемого CSV (плоский вид MeasurementIn).

    Порядок полей = порядок колонок в CSV.
    """

    source: str
    station_external_id: str
    station_name: str
    station_kind: StationKind = StationKind.other
    station_address: str | None = None
    lat: float
    lon: float
    parameter: str
    value: Decimal
    unit: str
    measured_at: datetime
    period_kind: PeriodKind = PeriodKind.instant
    pdk: Decimal | None = None
    sub_point: str = ""
    sub_point_name: str | None = None
    source_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _blank_to_default(cls, data):
        # Пустая ячейка в необязательной колонке = значение по умолчанию.
        if isinstance(data, dict):
            return {k: v for k, v in data.items()
                    if not (k in _CSV_OPTIONAL and isinstance(v, str) and not v.strip())}
        return data

    def to_measurement(self) -> MeasurementIn:
        return MeasurementIn(
            station=StationIn(
                source=self.source,
                external_id=self.station_external_id,
                name=self.station_name,
                kind=self.station_kind,
                address=self.station_address,
                lat=self.lat,
                lon=self.lon,
                geo_quality=GeoQuality.source,
            ),
            parameter=self.parameter,
            value=self.value,
            unit=self.unit,
            measured_at=self.measured_at,
            period_kind=self.period_kind,
            pdk=self.pdk,
            sub_point=self.sub_point,
            sub_point_name=self.sub_point_name,
            source_url=self.source_url,
        )


CSV_COLUMNS = list(CsvRow.model_fields.keys())


# --------------------------------------------------------------------------
# Хелперы для адаптеров (orsha-ecokarta и др.)
# --------------------------------------------------------------------------

UNIT_MAP = {
    "мкЗв/ч": "uSv/h",
    "мкг/м3": "ug/m3",
    "мкг/м³": "ug/m3",
    "мг/м3": "mg/m3",
    "мг/дм3": "mg/dm3",   # как в источнике; смысл единицы для выбросов уточнить
}


def normalize_unit(raw: str) -> str:
    u = _clean(raw)
    try:
        return UNIT_MAP[u]
    except KeyError:
        raise ValueError(f"неизвестная единица измерения: {u!r}")


_COORDS_RE = re.compile(r"Широта:\s*(-?[\d.]+)\s*Долгота:\s*(-?[\d.]+)")


def parse_ru_coords(text: str) -> tuple[float, float]:
    """'Широта: 54.48 Долгота: 30.39' -> (54.48, 30.39) = (lat, lon)."""
    m = _COORDS_RE.search(text or "")
    if not m:
        raise ValueError(f"не удалось разобрать координаты: {text!r}")
    return float(m.group(1)), float(m.group(2))


_MONTHS_GEN = {"января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5,
               "июня": 6, "июля": 7, "августа": 8, "сентября": 9,
               "октября": 10, "ноября": 11, "декабря": 12}
_MONTHS_NOM = {"январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5,
               "июнь": 6, "июль": 7, "август": 8, "сентябрь": 9,
               "октябрь": 10, "ноябрь": 11, "декабрь": 12}


def parse_ru_period(text: str) -> tuple[datetime, PeriodKind]:
    """Разбирает период orsha-ecokarta.

    '1 октября 2026 г.' -> (2026-10-01 00:00 Минск, day)
    'Июнь 2026'         -> (2026-06-01 00:00 Минск, month)
    """
    t = _clean(text or "").lower().replace("г.", "").strip()
    m = re.fullmatch(r"(\d{1,2})\s+([а-я]+)\s+(\d{4})", t)
    if m and m.group(2) in _MONTHS_GEN:
        d, mon, y = int(m.group(1)), _MONTHS_GEN[m.group(2)], int(m.group(3))
        return datetime(y, mon, d, tzinfo=MINSK), PeriodKind.day
    m = re.fullmatch(r"([а-я]+)\s+(\d{4})", t)
    if m and m.group(1) in _MONTHS_NOM:
        return datetime(int(m.group(2)), _MONTHS_NOM[m.group(1)], 1, tzinfo=MINSK), PeriodKind.month
    raise ValueError(f"не удалось разобрать период: {text!r}")
