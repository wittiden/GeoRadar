"""stations, parameters, measurements + справочник параметров

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Стартовый справочник параметров (docs/data-contract.md, раздел 3).
PARAMETERS = [
    ("gamma_dose_rate", "Мощность дозы гамма-излучения", "uSv/h"),
    ("air_pm_total", "Твёрдые частицы (недифференцированная по составу пыль/аэрозоль), воздух", "ug/m3"),
    ("air_co", "Углерод оксид, воздух", "ug/m3"),
    ("air_no2", "Азота диоксид, воздух", "ug/m3"),
    ("air_so2", "Серы диоксид, воздух", "ug/m3"),
    ("emis_pm_total", "Твёрдые частицы, выброс", "mg/dm3"),
    ("emis_co", "Углерод оксид, выброс", "mg/dm3"),
    ("emis_no2", "Азот (IV) оксид, выброс", "mg/dm3"),
]


def upgrade() -> None:
    op.create_table(
        "stations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False, server_default="other"),
        sa.Column("address", sa.Text()),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lon", sa.Double(), nullable=False),
        sa.Column("geo_quality", sa.Text(), nullable=False),
        sa.UniqueConstraint("source", "external_id", name="uq_stations_source_external_id"),
    )
    parameters = op.create_table(
        "parameters",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
    )
    op.create_table(
        "measurements",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("station_id", sa.BigInteger(), sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("parameter", sa.Text(), sa.ForeignKey("parameters.code"), nullable=False),
        sa.Column("sub_point", sa.Text(), nullable=False, server_default=""),
        sa.Column("sub_point_name", sa.Text()),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("pdk", sa.Numeric()),
        sa.Column("period_kind", sa.Text(), nullable=False, server_default="instant"),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source_url", sa.Text()),
        sa.Column("upload_id", sa.BigInteger()),
        sa.Column("raw", postgresql.JSONB()),
        sa.UniqueConstraint("station_id", "parameter", "sub_point", "measured_at", name="uq_measurements_series"),
    )
    op.create_index("ix_measurements_parameter_measured_at", "measurements", ["parameter", "measured_at"])
    op.bulk_insert(parameters, [{"code": c, "name": n, "unit": u} for c, n, u in PARAMETERS])


def downgrade() -> None:
    op.drop_table("measurements")
    op.drop_table("parameters")
    op.drop_table("stations")
