import json
from collections.abc import Iterator

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, SecretStr

from app.app_factory import create_app
from app.core.config import Environment, Settings


def test_production_requires_an_allowed_host_and_hides_docs() -> None:
    app = create_app(
        Settings(
            env=Environment.PRD,
            allowed_hosts=["work.example.test"],
            database_url=SecretStr("postgresql://test@127.0.0.1/work_service_test"),
        )
    )
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
    assert response.headers["x-request-id"]
    assert response.json() == {
        "message": "Content Too Large",
        "status": 413,
        "code": "request_too_large",
    }


def test_validation_and_unexpected_errors_hide_internal_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(Settings(env=Environment.DEV, debug=True, database_url=None))

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
    assert invalid.json() == {
        "message": "Unprocessable Content",
        "status": 422,
        "code": "request_validation_failed",
        "detail": "Check the request fields and parameter formats.",
    }
    assert unexpected.status_code == 500
    assert unexpected.json() == {
        "message": "Internal Server Error",
        "status": 500,
        "code": "internal_server_error",
    }
    logs = capsys.readouterr().out
    assert "invalid-private-value" not in logs
    assert "unexpected-private-value" not in logs
    errors = [
        record for line in logs.splitlines() if (record := json.loads(line))["severity"] == "ERROR"
    ]
    assert len(errors) == 1
    assert errors[0]["error_type"] == "RuntimeError"
    assert errors[0]["request_id"] == unexpected.headers["x-request-id"]


def test_http_error_preserves_protocol_headers_only() -> None:
    app = create_app(Settings(database_url=None))

    @app.get("/probe")
    async def deny_access() -> None:
        raise HTTPException(
            status_code=401,
            detail="private-error-detail",
            headers={"WWW-Authenticate": "Bearer", "Server": "private-server-banner"},
        )

    with TestClient(app, base_url="http://localhost") as client:
        response = client.get("/probe")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert "server" not in response.headers
    assert response.json() == {"message": "Unauthorized", "status": 401, "code": "unauthorized"}


def test_request_logs_use_route_templates_and_omit_request_data(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(Settings(database_url=None))
    with TestClient(app, base_url="http://localhost") as client:
        matched = client.get(
            "/api/v1/users/8cd5d82a-7e96-4093-9790-007b319df8ce",
            params={"example": "private-query-value"},
            headers={"Authorization": "Bearer private-token", "Cookie": "test=private-cookie"},
        )
        missing = client.get("/private-unmatched-path")

    assert matched.status_code == 503
    assert missing.status_code == 404
    assert missing.json() == {"message": "Not Found", "status": 404, "code": "not_found"}
    logs = capsys.readouterr().out
    for value in (
        "8cd5d82a-7e96-4093-9790-007b319df8ce",
        "private-unmatched-path",
        "private-query-value",
        "private-token",
        "private-cookie",
    ):
        assert value not in logs
    first, second = [json.loads(line) for line in logs.splitlines()]
    assert first["route"] == "/api/v1/users/{user_id}"
    assert second["route"] == "unmatched"
    assert second["request_id"] == missing.headers["x-request-id"]
