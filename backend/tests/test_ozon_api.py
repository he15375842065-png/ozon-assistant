"""API-level tests for the Ozon settings/category endpoints."""

from fastapi.testclient import TestClient


def test_ozon_check_without_credentials_returns_422(client: TestClient):
    response = client.post("/api/v1/settings/ozon/check", json={})
    assert response.status_code == 422
    assert "Client-Id" in response.json()["message"]


def test_ozon_category_sync_without_credentials_returns_422(client: TestClient):
    response = client.post("/api/v1/ozon/categories/sync")
    assert response.status_code == 422


def test_ozon_category_search_empty_cache(client: TestClient):
    response = client.get("/api/v1/ozon/categories", params={"q": "连衣裙"})
    assert response.status_code == 200
    assert response.json() == []


def test_ozon_category_attributes_empty_cache(client: TestClient):
    response = client.get("/api/v1/ozon/categories/17034433/attributes")
    assert response.status_code == 200
    assert response.json() == []


def test_ozon_settings_accepts_real_mode(client: TestClient):
    response = client.patch("/api/v1/settings", json={"ozon_mode": "real"})
    assert response.status_code == 200
    assert response.json()["ozon_mode"] == "real"
    # Restore mock mode so other tests are unaffected.
    client.patch("/api/v1/settings", json={"ozon_mode": "mock"})
