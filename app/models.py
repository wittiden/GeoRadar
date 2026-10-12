from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Double, ForeignKey, Index, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {str: Text}


class Station(Base):
    __tablename__ = "stations"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_stations_source_external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str]
    external_id: Mapped[str]
    name: Mapped[str]
    kind: Mapped[str] = mapped_column(server_default="other")
    address: Mapped[str | None]
    lat: Mapped[float] = mapped_column(Double)
    lon: Mapped[float] = mapped_column(Double)
    geo_quality: Mapped[str]


class Parameter(Base):
    __tablename__ = "parameters"

    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    unit: Mapped[str]


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        UniqueConstraint("station_id", "parameter", "sub_point", "measured_at", name="uq_measurements_series"),
        Index("ix_measurements_parameter_measured_at", "parameter", "measured_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    station_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stations.id"))
    parameter: Mapped[str] = mapped_column(ForeignKey("parameters.code"))
    sub_point: Mapped[str] = mapped_column(server_default="")
    sub_point_name: Mapped[str | None]
    value: Mapped[Decimal] = mapped_column(Numeric)
    pdk: Mapped[Decimal | None] = mapped_column(Numeric)
    period_kind: Mapped[str] = mapped_column(server_default="instant")
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_url: Mapped[str | None]
    upload_id: Mapped[int | None] = mapped_column(BigInteger)  # NULL для автосбора
    raw: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
