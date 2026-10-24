"""Clean Toronto red light camera locations into data/processed.

Run from the repository root with:

    python scripts/clean_red_light_cameras.py
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd


INPUT_PATH = Path("data/raw/Red Light Cameras Data - 4326.geojson")
OUTPUT_DIR = Path("data/processed")


def clean_file(input_path: Path = INPUT_PATH) -> Path:
    if not input_path.exists():
        raise FileNotFoundError(f"Input GeoJSON not found: {input_path.resolve()}")

    cameras = gpd.read_file(input_path)
    original_count = len(cameras)

    if cameras.crs is None:
        raise ValueError("Input GeoJSON has no CRS; expected EPSG:4326")
    if cameras.crs.to_epsg() != 4326:
        cameras = cameras.to_crs("EPSG:4326")

    # The source encodes missing values as the literal text "None". Convert
    # that placeholder to actual nulls while leaving other text untouched.
    for column in cameras.columns:
        if column != cameras.geometry.name and cameras[column].dtype == object:
            cameras[column] = cameras[column].replace("None", None)

    # IDs such as INTERSECTION_ID can legitimately repeat, so they are not
    # treated as unique keys. Compare every property and the geometry itself.
    feature_keys = cameras.drop(columns=cameras.geometry.name).apply(
        lambda row: tuple(row.tolist()), axis=1
    )
    geometry_keys = cameras.geometry.map(lambda geom: geom.wkb if geom is not None else None)
    combined = pd.Series(
        [(properties, geometry) for properties, geometry in zip(feature_keys, geometry_keys)],
        index=cameras.index,
    )
    cameras = cameras.loc[~combined.duplicated(keep="first")].copy()

    if cameras.geometry.isna().any() or cameras.geometry.is_empty.any():
        raise ValueError("Null or empty geometries remain after cleaning")
    if (~cameras.geometry.is_valid).any():
        raise ValueError("Invalid geometries remain after cleaning")
    if not cameras.geometry.geom_type.isin(["Point", "MultiPoint"]).all():
        raise ValueError("Expected camera geometries to be Point or MultiPoint")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / input_path.name
    cameras.to_file(output_path, driver="GeoJSON")

    print(f"Input features: {original_count:,}")
    print(f"Output features: {len(cameras):,}")
    print(f"Exact duplicate features removed: {original_count - len(cameras):,}")
    print(f"Output: {output_path}")
    return output_path


if __name__ == "__main__":
    clean_file()
