from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError


def test_health_ok(client: TestClient) -> None:
    with patch("app.api.health.check_database", return_value=True):
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "revampradar-api"
    assert payload["database"] == "ok"
    assert "version" in payload


def test_health_unavailable_when_database_is_down(client: TestClient) -> None:
    with patch(
        "app.api.health.check_database",
        side_effect=OperationalError("SELECT 1", {}, Exception("db down")),
    ):
        response = client.get("/health")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["database"] == "unavailable"
