import os
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.app_factory import create_app
from app.core.config import Environment, Settings

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url() -> SecretStr:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set TEST_DATABASE_URL to run the PostgreSQL integration suite")
    if make_url(url).database != "work_service_test":
        pytest.fail("TEST_DATABASE_URL must point to the disposable work_service_test database")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("APP_DATABASE_URL", url)
        command.upgrade(Config("alembic.ini"), "head")
    return SecretStr(url)


def build_test_app(url: SecretStr) -> FastAPI:
    return create_app(Settings(env=Environment.DEV, database_url=url, allowed_hosts=["localhost"]))


def test_user_lifecycle_persists_across_application_restarts(database_url: SecretStr) -> None:
    handle = f"work-{uuid4().hex[:12]}"
    with TestClient(build_test_app(database_url), base_url="http://localhost") as client:
        readiness = client.get("/health/ready")
        assert readiness.status_code == 200
        assert readiness.json() == {"status": "ready"}
        total = client.get("/api/v1/users").json()["total"]

        created = client.post(
            "/api/v1/users", json={"handle": handle.upper(), "display_name": "  River Song  "}
        )
        assert created.status_code == 201
        user = created.json()
        assert set(user) == {"id", "handle", "display_name", "created_at"}
        assert UUID(user["id"]).version == 4
        assert user["handle"] == handle
        assert user["display_name"] == "River Song"

        page = client.get(f"/api/v1/users?limit=1&offset={total}")
        assert page.status_code == 200
        assert page.json() == {"items": [user], "total": total + 1, "offset": total, "limit": 1}
        end = client.get(f"/api/v1/users?limit=1&offset={total + 1}")
        assert end.json() == {"items": [], "total": total + 1, "offset": total + 1, "limit": 1}

    path = f"/api/v1/users/{user['id']}"
    with TestClient(build_test_app(database_url), base_url="http://localhost") as client:
        assert client.get(path).json() == user
        updated = client.patch(path, json={"display_name": "Updated"})
        assert updated.status_code == 200
        assert updated.json() == {**user, "display_name": "Updated"}
        assert client.get(path).json() == updated.json()

        deleted = client.delete(path)
        assert deleted.status_code == 204
        assert deleted.content == b""
        for response in (
            client.get(path),
            client.patch(path, json={"display_name": "Missing"}),
            client.delete(path),
        ):
            assert response.status_code == 404
            assert response.json() == {
                "message": "Not Found",
                "status": 404,
                "code": "user_not_found",
            }


def test_concurrent_requests_cannot_create_case_variant_handles(database_url: SecretStr) -> None:
    handle = f"work-{uuid4().hex[:12]}"
    with TestClient(build_test_app(database_url), base_url="http://localhost") as client:

        def create(value: str) -> Response:
            return client.post("/api/v1/users", json={"handle": value, "display_name": "Tester"})

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(create, [handle, handle.upper()]))

        winner, conflict = sorted(responses, key=lambda response: response.status_code)
        assert winner.status_code == 201
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "user_handle_conflict"
        assert conflict.headers["content-type"] == "application/problem+json"
        assert client.delete(f"/api/v1/users/{winner.json()['id']}").status_code == 204


def test_user_input_and_pagination_are_bounded(database_url: SecretStr) -> None:
    with TestClient(build_test_app(database_url), base_url="http://localhost") as client:
        assert client.get("/api/v1/users?limit=101").status_code == 422
        assert client.get("/api/v1/users?offset=-1").status_code == 422
        assert client.get("/api/v1/users/invalid-uuid").status_code == 422
        invalid = client.post(
            "/api/v1/users",
            json={"handle": "ab", "display_name": " ", "password": "private-sample-value"},
        )

    assert invalid.status_code == 422
    assert invalid.json()["code"] == "request_validation_failed"
    assert "private-sample-value" not in invalid.text


def test_bad_database_credentials_keep_liveness_and_return_safe_errors(
    database_url: SecretStr,
) -> None:
    invalid_password = uuid4().hex
    invalid = make_url(database_url.get_secret_value()).set(password=invalid_password)
    application = build_test_app(SecretStr(invalid.render_as_string(hide_password=False)))
    with TestClient(application, base_url="http://localhost") as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        unavailable = client.get("/api/v1/users")

    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "message": "Service Unavailable",
        "status": 503,
        "code": "service_unavailable",
    }
    assert invalid_password not in unavailable.text
