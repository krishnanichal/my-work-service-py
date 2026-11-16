from collections.abc import Iterator

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, ValidationError

from app.app_factory import create_app
from app.core.config import Environment, Settings


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("APP_DEBUG", "true"),
        ("APP_ALLOWED_HOSTS", '["*.example.test"]'),
        ("APP_CORS_ORIGINS", '["*"]'),
    ],
)
def test_production_rejects_permissive_settings(
    monkeypatch: pytest.MonkeyPatch, setting: str, value: str
) -> None:
    monkeypatch.setenv("APP_ENV", "prd")
    monkeypatch.setenv("APP_ALLOWED_HOSTS", '["work.example.test"]')
    monkeypatch.setenv(setting, value)

    with pytest.raises(ValidationError, match=setting):
        Settings()


def test_production_requires_explicit_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prd")
    monkeypatch.delenv("APP_ALLOWED_HOSTS", raising=False)

    with pytest.raises(ValidationError, match="APP_ALLOWED_HOSTS"):
        Settings()


def test_production_requires_an_allowed_host_and_hides_docs() -> None:
    app = create_app(Settings(env=Environment.PRD, allowed_hosts=["work.example.test"]))
    with TestClient(app, base_url="https://work.example.test") as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/live", headers={"Host": "other.example.test"}).status_code == 400
        assert client.get("/openapi.json").status_code == 404


@pytest.mark.parametrize("streamed", [False, True])
def test_oversized_body_returns_safe_problem_response(streamed: bool) -> None:
    app = create_app(Settings(max_request_body_bytes=16))

    @app.post("/probe")
    async def read_body(request: Request) -> dict[str, int]:
        return {"length": len(await request.body())}

    def chunks() -> Iterator[bytes]:
        yield b"12345678"
        yield b"901234567"

    with TestClient(app, base_url="http://localhost") as client:
        body = chunks() if streamed else b"12345678901234567"
        response = client.post("/probe", content=body)

    assert response.status_code == 413
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "request_too_large"
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_validation_and_unexpected_errors_hide_internal_values() -> None:
    app = create_app(Settings())

    class Payload(BaseModel):
        model_config = ConfigDict(extra="forbid")
        name: str

    @app.post("/probe")
    async def parse_payload(payload: Payload) -> None:
        raise RuntimeError(payload.name)

    with TestClient(app, base_url="http://localhost", raise_server_exceptions=False) as client:
        invalid = client.post(
            "/probe", json={"name": "example", "private": "invalid-private-value"}
        )
        unexpected = client.post("/probe", json={"name": "unexpected-private-value"})

    assert invalid.status_code == 422
    assert invalid.json()["code"] == "request_validation_failed"
    assert "invalid-private-value" not in invalid.text
    assert unexpected.status_code == 500
    assert unexpected.json()["code"] == "internal_server_error"
    assert unexpected.json()["request_id"] == unexpected.headers["x-request-id"]
    assert "unexpected-private-value" not in unexpected.text
