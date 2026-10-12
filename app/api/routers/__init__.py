from fastapi import APIRouter

from app.api.routers import catalog, measurements, stations

api_router = APIRouter()
api_router.include_router(catalog.router)
api_router.include_router(stations.router)
api_router.include_router(measurements.router)
