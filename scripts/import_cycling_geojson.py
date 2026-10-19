import os
from pathlib import Path

import geopandas as gpd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
INPUT_FILE = Path("data/processed/cycling-network - 4326.geojson")
TABLE_NAME = "cycling_network"


def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Check your .env file.")

    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Processed GeoJSON not found: {INPUT_FILE}")

    gdf = gpd.read_file(INPUT_FILE)

    if gdf.empty:
        raise ValueError("The GeoJSON contains no features.")
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        raise ValueError("Expected source CRS EPSG:4326")
    if gdf.geometry.isna().any() or gdf.geometry.is_empty.any():
        raise ValueError("Dataset contains null or empty geometries.")
    if not gdf.geometry.is_valid.all():
        raise ValueError("Dataset contains invalid geometries.")

    # Normalize source property names for portable SQL identifiers.
    gdf = gdf.rename(columns={column: column.lower() for column in gdf.columns})
    gdf = gdf.rename(columns={"_id": "source_id"})

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

        gdf.to_postgis(
            name=TABLE_NAME,
            con=engine,
            if_exists="replace",
            index=False,
        )

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_cycling_network_geometry
                    ON cycling_network USING GIST (geometry)
                    """
                )
            )
            connection.execute(text("ANALYZE cycling_network"))

        print(f"Imported {len(gdf):,} cycling network features.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
