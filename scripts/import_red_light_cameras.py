"""Import cleaned red light camera GeoJSON into PostGIS.

Run from the repository root with:

    python scripts/import_red_light_cameras.py
"""

import os
from pathlib import Path

import geopandas as gpd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
INPUT_FILE = PROJECT_ROOT / "data/processed/Red Light Cameras Data - 4326.geojson"
TABLE_NAME = "red_light_cameras"


def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Check your .env file.")
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Processed GeoJSON not found: {INPUT_FILE}. "
            "Run scripts/clean_red_light_cameras.py first."
        )

    cameras = gpd.read_file(INPUT_FILE)
    if cameras.empty:
        raise ValueError("The GeoJSON contains no features.")
    if cameras.crs is None or cameras.crs.to_epsg() != 4326:
        raise ValueError("Expected source CRS EPSG:4326")
    if cameras.geometry.isna().any() or cameras.geometry.is_empty.any():
        raise ValueError("Dataset contains null or empty geometries.")
    if not cameras.geometry.is_valid.all():
        raise ValueError("Dataset contains invalid geometries.")

    # PostgreSQL column names are normalized to lowercase to match the API SQL.
    cameras = cameras.rename(columns={column: column.lower() for column in cameras.columns})
    cameras = cameras.rename(columns={"_id": "source_id"})

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

        cameras.to_postgis(
            name=TABLE_NAME,
            con=engine,
            if_exists="replace",
            index=False,
        )

        with engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_geometry "
                    f"ON {TABLE_NAME} USING GIST (geometry)"
                )
            )
            connection.execute(text(f"ANALYZE {TABLE_NAME}"))

        print(f"Imported {len(cameras):,} red light camera features into {TABLE_NAME}.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
