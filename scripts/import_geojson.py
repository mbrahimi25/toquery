
import os
from pathlib import Path

import geopandas as gpd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

INPUT_FILE = Path("data/processed/Green Spaces - 4326.geojson")
TABLE_NAME = "green_spaces"
BATCH_SIZE = 250


def main():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is missing. Check your .env file."
        )

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Processed GeoJSON not found: {INPUT_FILE}"
        )

    print(f"Reading {INPUT_FILE}...", flush=True)
    gdf = gpd.read_file(INPUT_FILE)

    if gdf.empty:
        raise ValueError("The GeoJSON contains no features.")

    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        raise ValueError("Expected source CRS EPSG:4326")

    if gdf.geometry.isna().any():
        raise ValueError("Dataset contains null geometries.")

    if gdf.geometry.is_empty.any():
        raise ValueError("Dataset contains empty geometries.")

    if not gdf.geometry.is_valid.all():
        raise ValueError("Dataset contains invalid geometries.")

    # Rename source fields to predictable database column names.
    gdf = gdf.rename(
        columns={
            "_id": "source_id",
            "AREA_ID": "area_id",
            "AREA_ATTR_ID": "area_attr_id",
            "PARENT_AREA_ID": "parent_area_id",
            "AREA_CLASS_ID": "area_class_id",
            "AREA_CLASS": "area_class",
            "AREA_SHORT_CODE": "area_short_code",
            "AREA_LONG_CODE": "area_long_code",
            "AREA_NAME": "area_name",
            "AREA_DESC": "area_desc",
            "OBJECTID": "object_id",
        }
    )

    total = len(gdf)
    print(f"Loaded {total:,} features.", flush=True)

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )

    try:
        # Confirm the database is reachable and PostGIS is enabled.
        with engine.begin() as connection:
            connection.execute(
                text("CREATE EXTENSION IF NOT EXISTS postgis")
            )
            connection.execute(text("SELECT PostGIS_Full_Version()"))

        # Import one batch at a time and report progress.
        for start in range(0, total, BATCH_SIZE):
            end = min(start + BATCH_SIZE, total)
            batch = gdf.iloc[start:end]

            batch.to_postgis(
                name=TABLE_NAME,
                con=engine,
                if_exists="replace" if start == 0 else "append",
                index=False,
            )

            print(
                f"Imported {end:,}/{total:,} features "
                f"({end / total:.0%})",
                flush=True,
            )

        # Create a spatial index for efficient geometry queries.
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_green_spaces_geometry
                    ON green_spaces
                    USING GIST (geometry)
                    """
                )
            )

            connection.execute(
                text(
                    "ANALYZE green_spaces"
                )
            )

        # Verify the imported table.
        with engine.connect() as connection:
            count = connection.execute(
                text("SELECT COUNT(*) FROM green_spaces")
            ).scalar_one()

            geometry_types = connection.execute(
                text(
                    """
                    SELECT DISTINCT GeometryType(geometry)
                    FROM green_spaces
                    """
                )
            ).scalars().all()

            srids = connection.execute(
                text(
                    """
                    SELECT DISTINCT ST_SRID(geometry)
                    FROM green_spaces
                    """
                )
            ).scalars().all()

        print("\nImport complete.", flush=True)
        print(f"Expected features: {total:,}")
        print(f"Imported features: {count:,}")
        print(f"Geometry types: {geometry_types}")
        print(f"SRIDs: {srids}")

        if count != total:
            raise RuntimeError(
                f"Row count mismatch: expected {total}, found {count}"
            )

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
