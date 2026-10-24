"""Clean and import all supported GeoJSON datasets into PostGIS."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def run_script(name: str) -> None:
    script_path = SCRIPTS_DIR / name
    print(f"\n==> Running {script_path.name}", flush=True)
    subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
        check=True,
        env=os.environ.copy(),
    )


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is missing. Check your .env file.")

    # clean_geojson.py processes all files in data/raw. The camera-specific
    # pass also converts source "None" placeholders to actual null values.
    run_script("clean_geojson.py")
    run_script("clean_red_light_cameras.py")

    run_script("import_geojson.py")
    run_script("import_cycling_geojson.py")
    run_script("import_red_light_cameras.py")

    print("\nAll datasets are cleaned and imported.", flush=True)


if __name__ == "__main__":
    main()
