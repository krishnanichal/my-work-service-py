import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_liveness_reports_process_health_with_request_correlation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with TestClient(app, base_url="http://localhost") as client:
        first = client.get("/health/live", headers={"X-Request-ID": "supplied-id"})
        second = client.get("/health/live")

    assert first.status_code == 200
    assert first.json() == {"status": "alive"}
    assert first.headers["x-request-id"] not in {"supplied-id", second.headers["x-request-id"]}
    record = json.loads(capsys.readouterr().out.splitlines()[0])
    assert record["severity"] == "INFO"
    assert record["environment"] == "dev"
    assert record["path"] == "/health/live"
    assert record["status_code"] == 200
    assert record["request_id"] == first.headers["x-request-id"]


def test_unsupported_method_preserves_allow_header() -> None:
    with TestClient(app, base_url="http://localhost") as client:
        response = client.post("/health/live")

    assert response.status_code == 405
    assert response.headers["allow"] == "GET"
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "method_not_allowed"
    assert response.json()["request_id"] == response.headers["x-request-id"]
