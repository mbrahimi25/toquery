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
