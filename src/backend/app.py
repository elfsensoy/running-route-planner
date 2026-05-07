from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.backend.schemas import RouteRequest, RouteResponse
from src.routing.route_service import (
    RouteGenerationError,
    available_poi_groups,
    available_pois,
    generate_route,
)


BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Running Route Planner API",
    description="Generate POI-aware loop routes in Fatih, Istanbul.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/poi-groups")
def poi_groups():
    return {"groups": available_poi_groups()}


@app.get("/api/pois")
def pois():
    return {"pois": available_pois()}


@app.post("/api/routes/generate", response_model=RouteResponse)
def create_route(payload: RouteRequest):
    try:
        return generate_route(
            start_lat=payload.start_lat,
            start_lon=payload.start_lon,
            min_distance_km=payload.min_distance_km,
            max_distance_km=payload.max_distance_km,
            poi_preferences=payload.poi_preferences,
            selected_poi_ids=payload.selected_poi_ids,
            elevation_preference=payload.elevation_preference,
            loop_route=payload.loop_route,
            end_lat=payload.end_lat,
            end_lon=payload.end_lon,
        )
    except RouteGenerationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"Missing project data file: {exc}") from exc
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"Missing Python dependency: {exc}") from exc


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend has not been created.")
    return FileResponse(index_path)
