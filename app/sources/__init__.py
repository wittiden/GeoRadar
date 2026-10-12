from typing import Protocol

from app.contract import MeasurementIn


class SourceAdapter(Protocol):
    code: str  # совпадает с MeasurementIn.station.source, напр. "rad_rss"

    def fetch(self) -> list[MeasurementIn]: ...
