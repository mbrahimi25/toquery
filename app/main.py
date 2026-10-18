from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path

import geopandas  # Not needed by the endpoint; remove if unused elsewhere.
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Load .env from the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from .env")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

app = FastAPI(
    title="GeoQuery API",
    description="A geospatial API for Toronto data.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "null",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Check API and database connectivity."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {"status": "ok", "database": "connected"}

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )


@app.get("/green-spaces")
def get_green_spaces(
    min_lon: float = Query(ge=-180, le=180),
    min_lat: float = Query(ge=-90, le=90),
    max_lon: float = Query(ge=-180, le=180),
    max_lat: float = Query(ge=-90, le=90),
):
    """
    Return green spaces intersecting a geographic bounding box.

    Coordinates use longitude/latitude in EPSG:4326.
    """

    if min_lon >= max_lon:
        raise HTTPException(
            status_code=422,
            detail="min_lon must be less than max_lon",
        )

    if min_lat >= max_lat:
        raise HTTPException(
            status_code=422,
            detail="min_lat must be less than max_lat",
        )

    query = text(
        """
        WITH bounds AS (
            SELECT ST_MakeEnvelope(
                :min_lon,
                :min_lat,
                :max_lon,
                :max_lat,
                4326
            ) AS geom
        )
        SELECT
            gs.area_id,
            gs.area_name,
            gs.area_class,
            ST_AsGeoJSON(gs.geometry)::json AS geometry
        FROM green_spaces AS gs
        CROSS JOIN bounds
        WHERE gs.geometry && bounds.geom
          AND ST_Intersects(gs.geometry, bounds.geom)
        ORDER BY gs.area_name
        """
    )

    try:
        with engine.connect() as connection:
            rows = connection.execute(
                query,
                {
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                },
            ).mappings().all()

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Unable to query green spaces",
        )

    features = [
        {
            "type": "Feature",
            "geometry": row["geometry"],
            "properties": {
                "area_id": row["area_id"],
                "area_name": row["area_name"],
                "area_class": row["area_class"],
            },
        }
        for row in rows
    ]

    return {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
    }
