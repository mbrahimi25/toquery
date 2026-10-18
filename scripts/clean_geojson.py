
from pathlib import Path

import geopandas as gpd
from shapely import make_valid

RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/processed")


def clean_file(file_path: Path) -> None:
    print(f"\nProcessing: {file_path.name}")

    gdf = gpd.read_file(file_path)
    original_count = len(gdf)

    # Remove exact duplicate records by AREA_ID only when their
    # geometries and non-ID attributes match.
    if "AREA_ID" in gdf.columns:
        duplicate_mask = gdf["AREA_ID"].duplicated(keep=False)

        for area_id, group in gdf[duplicate_mask].groupby("AREA_ID"):
            if len(group) < 2:
                continue

            attribute_columns = [
                col for col in gdf.columns
                if col not in {"geometry", "_id", "OBJECTID"}
            ]

            attributes_match = (
                group[attribute_columns]
                .nunique(dropna=False)
                .le(1)
                .all()
            )

            geometries_match = all(
                group.geometry.iloc[0].equals(geom)
                for geom in group.geometry.iloc[1:]
            )

            if attributes_match and geometries_match:
                # Keep the first record and remove subsequent copies.
                keep_index = group.index[0]
                remove_indices = [
                    idx for idx in group.index if idx != keep_index
                ]

                gdf = gdf.drop(index=remove_indices)

                print(
                    f"Removed {len(remove_indices)} duplicate record(s) "
                    f"for AREA_ID {area_id}"
                )
            else:
                print(
                    f"WARNING: AREA_ID {area_id} has duplicates "
                    "that differ in attributes or geometry. Keeping them."
                )

    # Repair invalid geometries.
    invalid_mask = ~gdf.geometry.is_valid & gdf.geometry.notna()

    for idx in gdf.index[invalid_mask]:
        original_geometry = gdf.at[idx, "geometry"]
        repaired_geometry = make_valid(original_geometry)

        if (
            repaired_geometry is None
            or repaired_geometry.is_empty
            or not repaired_geometry.is_valid
        ):
            raise ValueError(
                f"Could not repair geometry at index {idx}"
            )

        gdf.at[idx, "geometry"] = repaired_geometry

        print(
            f"Repaired geometry at index {idx}: "
            f"{original_geometry.geom_type} -> "
            f"{repaired_geometry.geom_type}"
        )

    # Validate the complete dataset.
    if gdf.geometry.isna().any():
        raise ValueError("Null geometries remain after cleaning")

    if gdf.geometry.is_empty.any():
        raise ValueError("Empty geometries remain after cleaning")

    if (~gdf.geometry.is_valid).any():
        raise ValueError("Invalid geometries remain after cleaning")

    if "AREA_ID" in gdf.columns:
        remaining_duplicates = gdf["AREA_ID"].duplicated().sum()

        if remaining_duplicates:
            raise ValueError(
                f"{remaining_duplicates} duplicate AREA_ID value(s) remain"
            )

    # Write to the processed directory, never to the raw directory.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / file_path.name
    gdf.to_file(output_path, driver="GeoJSON")

    print("\nCleaning summary")
    print("-" * 40)
    print(f"Original features: {original_count:,}")
    print(f"Cleaned features: {len(gdf):,}")
    print(f"Features removed: {original_count - len(gdf):,}")
    print(f"Invalid geometries: {(~gdf.geometry.is_valid).sum()}")
    print(f"Empty geometries: {gdf.geometry.is_empty.sum()}")
    print(f"Null geometries: {gdf.geometry.isna().sum()}")
    print(f"Output: {output_path}")


def main() -> None:
    files = sorted(
        list(RAW_DIR.glob("*.geojson"))
        + list(RAW_DIR.glob("*.json"))
    )

    if not files:
        raise FileNotFoundError(
            f"No GeoJSON files found in {RAW_DIR.resolve()}"
        )

    for file_path in files:
        clean_file(file_path)


if __name__ == "__main__":
    main()
