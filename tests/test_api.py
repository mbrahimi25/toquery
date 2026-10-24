from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_green_spaces_rejects_reversed_longitude_bounds():
    response = client.get(
        "/green-spaces",
        params={
            "min_lon": -79.5,
            "min_lat": 43.5,
            "max_lon": -79.6,
            "max_lat": 43.8,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "min_lon must be less than max_lon"


def test_red_light_cameras_rejects_reversed_latitude_bounds():
    response = client.get(
        "/red-light-cameras",
        params={
            "min_lon": -79.5,
            "min_lat": 43.8,
            "max_lon": -79.4,
            "max_lat": 43.5,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "min_lat must be less than max_lat"
