from fastapi.middleware.cors import CORSMiddleware
import logging
import json
import os
from pathlib import Path
from fastapi.responses import HTMLResponse

from dotenv import dotenv_values, load_dotenv
from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

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
    title="TOQuery API",
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


@app.get("/demo", include_in_schema=False)
def map_demo():
    """Serve the Leaflet map demo."""
    carto_key = dotenv_values(PROJECT_ROOT / ".env").get("CARTO_KEY") or os.getenv("CARTO_KEY")
    if not carto_key:
        raise HTTPException(status_code=503, detail="CARTO_KEY is missing from .env")

    html = (PROJECT_ROOT / "app" / "static" / "demo.html").read_text(encoding="utf-8")
    return HTMLResponse(
        html.replace("'__CARTO_KEY__'", json.dumps(carto_key)),
        headers={"Cache-Control": "no-store"},
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


@app.get("/cycling-network")
def get_cycling_network(
    min_lon: float = Query(ge=-180, le=180),
    min_lat: float = Query(ge=-90, le=90),
    max_lon: float = Query(ge=-180, le=180),
    max_lat: float = Query(ge=-90, le=90),
):
    """Return cycling network segments intersecting a geographic bounding box."""

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
            cn.segment_id,
            cn.street_name,
            cn.from_street,
            cn.to_street,
            cn.roadclass,
            cn.cnpclass,
            cn.surface,
            cn.owner,
            cn.dir_loworder,
            cn.infra_loworder,
            cn.infra_highorder,
            cn.installed,
            cn.upgraded,
            cn.converted,
            ST_AsGeoJSON(cn.geometry)::json AS geometry
        FROM cycling_network AS cn
        CROSS JOIN bounds
        WHERE cn.geometry && bounds.geom
          AND ST_Intersects(cn.geometry, bounds.geom)
        ORDER BY cn.street_name, cn.segment_id
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
        logger.exception("Cycling network query failed")
        raise HTTPException(
            status_code=503,
            detail="Unable to query cycling network",
        )

    properties = (
        "segment_id",
        "street_name",
        "from_street",
        "to_street",
        "roadclass",
        "cnpclass",
        "surface",
        "owner",
        "dir_loworder",
        "infra_loworder",
        "infra_highorder",
        "installed",
        "upgraded",
        "converted",
    )
    features = [
        {
            "type": "Feature",
            "geometry": row["geometry"],
            "properties": {key: row[key] for key in properties},
        }
        for row in rows
    ]

    return {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
    }


@app.get("/red-light-cameras")
def get_red_light_cameras(
    min_lon: float = Query(ge=-180, le=180),
    min_lat: float = Query(ge=-90, le=90),
    max_lon: float = Query(ge=-180, le=180),
    max_lat: float = Query(ge=-90, le=90),
):
    """Return red light camera locations intersecting a geographic bounding box."""

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
            rlc.intersection_id,
            rlc.linear_name_full_1,
            rlc.linear_name_full_2,
            rlc.rlc,
            rlc.tcs,
            rlc.name,
            rlc.district,
            rlc.ward_1,
            rlc.ward_2,
            rlc.ward_3,
            rlc.ward_4,
            rlc.activation_date,
            ST_AsGeoJSON(rlc.geometry)::json AS geometry
        FROM red_light_cameras AS rlc
        CROSS JOIN bounds
        WHERE rlc.geometry && bounds.geom
          AND ST_Intersects(rlc.geometry, bounds.geom)
        ORDER BY rlc.name, rlc.intersection_id
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
        logger.exception("Red light camera query failed")
        raise HTTPException(
            status_code=503,
            detail="Unable to query red light cameras",
        )

    properties = (
        "intersection_id",
        "linear_name_full_1",
        "linear_name_full_2",
        "rlc",
        "tcs",
        "name",
        "district",
        "ward_1",
        "ward_2",
        "ward_3",
        "ward_4",
        "activation_date",
    )
    features = [
        {
            "type": "Feature",
            "geometry": row["geometry"],
            "properties": {key: row[key] for key in properties},
        }
        for row in rows
    ]

    return {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
    }
