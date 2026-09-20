from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_restaurants_returns_ok_and_a_list():
    resp = client.get("/api/restaurants")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) > 0


def test_get_unknown_restaurant_returns_404():
    resp = client.get("/api/restaurants/does-not-exist")
    assert resp.status_code == 404
