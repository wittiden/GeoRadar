from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_station_filter
from app.api.schemas import Page, StationOut
from app.core.db import get_db
from app.models import Station
from app.services.filters import StationFilter

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("", response_model=Page[StationOut], summary="Список станций")
def list_stations(
    f: StationFilter = Depends(get_station_filter),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        f.apply(select(Station)).order_by(Station.source, Station.name, Station.id).limit(limit).offset(offset)
    ).all()
    total = db.scalar(f.apply(select(func.count(Station.id))))
    return Page(total=total, limit=limit, offset=offset, items=rows)


# Объявлен ДО /{station_id}, чтобы "geojson" не разбирался как id.
@router.get("/geojson", summary="Станции как GeoJSON FeatureCollection (для карты)")
def stations_geojson(
    f: StationFilter = Depends(get_station_filter),
    limit: int = Query(5000, ge=1, le=20000),
    db: Session = Depends(get_db),
):
    rows = db.scalars(f.apply(select(Station)).order_by(Station.id).limit(limit)).all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},  # GeoJSON: [lon, lat]
                "properties": {
                    "id": s.id, "source": s.source, "external_id": s.external_id,
                    "name": s.name, "kind": s.kind, "address": s.address,
                },
            }
            for s in rows
        ],
    }


@router.get("/{station_id}", response_model=StationOut, summary="Одна станция")
def get_station(station_id: int, db: Session = Depends(get_db)):
    station = db.get(Station, station_id)
    if station is None:
        raise HTTPException(404, "station not found")
    return station
