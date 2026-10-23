# TOQuery API

A FastAPI service for querying Toronto green spaces and cycling network data by geographic bounding box. The database uses PostgreSQL with PostGIS.

## Requirements

- Python 3.12 or later
- PostgreSQL with PostGIS, or Docker Desktop with Docker Compose
- A `CARTO_KEY` if you want to use the `/demo` map page

## Run locally with Docker Compose

The repository includes a Dockerfile for the API and a Compose configuration for the API and PostGIS database.

1. Create a `.env` file in the project root (next to `compose.yaml`) with:

   ```dotenv
   DB_PASSWORD=choose_a_local_database_password
   CARTO_KEY=your_carto_key
   ```

   `CARTO_KEY` is only needed for `/demo`. Keep `.env` private; it is ignored by Git.

2. From the project root, build and start both services:

   ```powershell
   docker compose up --build
   ```

3. Visit `http://localhost:8000/docs` for interactive API documentation, or call the endpoints described below.

4. Stop the containers with `Ctrl+C`, then run:

   ```powershell
   docker compose down
   ```

Compose keeps database files in the `postgres_data` volume between stops. To remove the database and all its stored data as well, run `docker compose down -v`.

The included `sql/init.sql` enables the PostGIS extension on a fresh database. It does not import the green space or cycling data, so load the required `green_spaces` and `cycling_network` tables before expecting those endpoints to return features.

## Run the API without Docker

This starts the API with your own PostgreSQL/PostGIS database. Make sure the database is running, PostGIS is enabled, and the required tables are loaded.

1. Create and activate a virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install the Python dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Create a project-root `.env` file and set your database URL. Add `CARTO_KEY` if you want `/demo`:

   ```dotenv
   DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/DATABASE
   CARTO_KEY=your_carto_key
   ```

   Replace the database URL values with your local database credentials. `DATABASE_URL` is required when the application starts; `CARTO_KEY` is only required by `/demo`.

4. Start the development server:

   ```powershell
   python -m uvicorn app.main:app --reload
   ```

The API is available at `http://localhost:8000`. Stop it with `Ctrl+C`.

## Endpoints

All API routes use HTTP `GET`. The two data endpoints take a bounding box in longitude/latitude coordinates (EPSG:4326), with the minimum values southwest of the maximum values northeast.

### `GET /health`

Checks that the API can connect to its configured database.

Example:

```text
http://localhost:8000/health
```

Returns `200` with `{"status":"ok","database":"connected"}` when healthy, or `503` if the database cannot be reached.

### `GET /green-spaces`

Returns green spaces intersecting the requested bounding box as a GeoJSON `FeatureCollection`. Each feature includes `area_id`, `area_name`, and `area_class` properties.

Required query parameters:

| Parameter | Meaning | Valid range |
| --- | --- | --- |
| `min_lon` | Western longitude | -180 to 180 |
| `min_lat` | Southern latitude | -90 to 90 |
| `max_lon` | Eastern longitude | -180 to 180 |
| `max_lat` | Northern latitude | -90 to 90 |

Example (central Toronto area):

```text
http://localhost:8000/green-spaces?min_lon=-79.42&min_lat=43.63&max_lon=-79.36&max_lat=43.68
```

The response includes `type`, `features`, and `count`. Invalid coordinate bounds return `422`; database query failures return `503`.

### `GET /cycling-network`

Returns cycling network segments intersecting the requested bounding box as a GeoJSON `FeatureCollection`. Feature properties include segment and street details such as `segment_id`, `street_name`, `from_street`, `to_street`, infrastructure class, and installation dates.

It takes the same required `min_lon`, `min_lat`, `max_lon`, and `max_lat` parameters as `/green-spaces`.

Example:

```text
http://localhost:8000/cycling-network?min_lon=-79.42&min_lat=43.63&max_lon=-79.36&max_lat=43.68
```

The response includes `type`, `features`, and `count`. Invalid coordinate bounds return `422`; database query failures return `503`.

### `GET /demo`

Serves the Leaflet map demo page. It requires `CARTO_KEY`; without it the endpoint returns `503`. This route is hidden from the generated OpenAPI schema.

```text
http://localhost:8000/demo
```

## Interactive API documentation

When the server is running, FastAPI provides:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

