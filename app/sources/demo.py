from datetime import datetime
from decimal import Decimal

from app.contract import GeoQuality, MeasurementIn, PeriodKind, StationIn, StationKind


class DemoAdapter:
    code = "demo"

    def fetch(self) -> list[MeasurementIn]:
        # Координаты и значения выдуманные.
        post = StationIn(source=self.code, external_id="demo-1", name="Демо-пост 1",
                         kind=StationKind.radiation_post, lat=53.90, lon=27.56,
                         geo_quality=GeoQuality.manual)
        air = StationIn(source=self.code, external_id="demo-2", name="Демо-пост воздуха",
                        kind=StationKind.air_post, address="ул. Демонстрационная", lat=54.50, lon=30.40,
                        geo_quality=GeoQuality.manual)
        return [
            MeasurementIn(station=post, parameter="gamma_dose_rate", value=Decimal("0.10"), unit="uSv/h",
                          measured_at=datetime(2026, 10, 3, 18, 0)),
            MeasurementIn(station=air, parameter="air_co", value=Decimal("1340"), unit="ug/m3",
                          pdk=Decimal("5000"), period_kind=PeriodKind.day,
                          measured_at=datetime(2026, 10, 1)),
            # Параметра нет в справочнике: он создастся автоматически (parameter_name обязателен по смыслу).
            MeasurementIn(station=air, parameter="air_p999", parameter_name="Тестовое вещество (демо)",
                          value=Decimal("12.5"), unit="ug/m3", period_kind=PeriodKind.day,
                          measured_at=datetime(2026, 10, 1)),
        ]
