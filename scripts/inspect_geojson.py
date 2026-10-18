
from pathlib import Path

from shapely import make_valid

import geopandas as gpd

DATA_DIR = Path("data/raw")


def inspect_file(file_path: Path) -> None:
    print(f"\n{'=' * 60}")
    print(f"File: {file_path.name}")

    gdf = gpd.read_file(file_path)

    # Basic dataset information
    print(f"Feature count: {len(gdf):,}")
    print(f"CRS: {gdf.crs}")
    print(f"Columns: {list(gdf.columns)}")
    print(
        "Geometry types:",
        gdf.geometry.geom_type.value_counts().to_dict(),
    )
    print(f"Bounds: {gdf.total_bounds}")

    print("\nFirst 3 records:")
    print(gdf.drop(columns="geometry").head(3).to_string(index=False))

    # General data quality checks
    print("\nData quality checks")
    print("-" * 40)

    if "AREA_NAME" in gdf.columns:
        print("Missing area names:", gdf["AREA_NAME"].isna().sum())

    if "AREA_ID" in gdf.columns:
        print("Missing area IDs:", gdf["AREA_ID"].isna().sum())

        duplicate_mask = gdf["AREA_ID"].duplicated(keep=False)
        duplicates = gdf[duplicate_mask]

        print(
            "Duplicate AREA_ID rows:",
            gdf["AREA_ID"].duplicated().sum(),
        )

        if not duplicates.empty:
            print("\nDuplicate AREA_ID records:")
            print(
                duplicates.drop(columns="geometry").to_string(
                    index=False
                )
            )

            print("\nDuplicate geometry comparison:")

            for area_id, group in duplicates.groupby("AREA_ID"):
                geometries = group.geometry

                # Compare every geometry against the first one.
                identical = all(
                    geometries.iloc[0].equals(geom)
                    for geom in geometries.iloc[1:]
                )

                print(f"AREA_ID: {area_id}")
                print("Number of records:", len(group))
                print("Geometries spatially identical:", identical)

    # Geometry quality checks
    null_geometries = gdf.geometry.isna()
    empty_geometries = gdf.geometry.is_empty
    invalid_geometries = ~gdf.geometry.is_valid

    print("\nGeometry quality")
    print("-" * 40)
    print("Invalid geometries:", invalid_geometries.sum())
    print("Empty geometries:", empty_geometries.sum())
    print("Null geometries:", null_geometries.sum())

    # Inspect invalid geometries and test potential repairs.
    invalid = gdf[invalid_geometries & ~null_geometries]

    if not invalid.empty:
        print("\nInvalid geometry records:")
        print(
            invalid.drop(columns="geometry").to_string(index=False)
        )

        print("\nGeometry validity reasons:")
        print(invalid.geometry.is_valid_reason())

        print("\nGeometry repair diagnostics:")
        print("-" * 40)

        for idx, row in invalid.iterrows():
            geom = row.geometry

            print(f"\nFeature index: {idx}")

            if "AREA_ID" in gdf.columns:
                print("AREA_ID:", row["AREA_ID"])

            if "AREA_NAME" in gdf.columns:
                print("AREA_NAME:", row["AREA_NAME"])

            print("Original type:", geom.geom_type)
            print("Original valid:", geom.is_valid)
            print("Original area (square degrees):", geom.area)

            try:
                repaired = make_valid(geom)

                print("Repaired type:", repaired.geom_type)
                print("Repaired valid:", repaired.is_valid)
                print("Repaired empty:", repaired.is_empty)
                print("Repaired area (square degrees):", repaired.area)
                print(
                    "Area difference (square degrees):",
                    repaired.area - geom.area,
                )
            except Exception as exc:
                print("Repair failed:", exc)


def main() -> None:
    files = sorted(
        list(DATA_DIR.glob("*.geojson"))
        + list(DATA_DIR.glob("*.json"))
    )

    if not files:
        raise FileNotFoundError(
            f"No GeoJSON files found in {DATA_DIR.resolve()}"
        )

    for file_path in files:
        try:
            inspect_file(file_path)
        except Exception as exc:
            print(f"\nError inspecting {file_path.name}: {exc}")


if __name__ == "__main__":
    main()
