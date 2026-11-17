import json

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import DatabaseSettings, Environment, Settings


def test_postgresql_url_from_environment_uses_the_async_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_DATABASE_URL", "postgresql://test:p%40ss@127.0.0.1/work_service_test")
    settings = Settings(env=Environment.DEV)

    assert settings.database_url is not None
    assert settings.database_url.get_secret_value() == (
        "postgresql+asyncpg://test:p%40ss@127.0.0.1/work_service_test"
    )
    assert "p%40ss" not in repr(settings)


@pytest.mark.parametrize("url", ["invalid-private-value", "sqlite:///work", "postgresql://host"])
def test_invalid_database_urls_return_a_safe_error(url: str) -> None:
    with pytest.raises(ValidationError, match="APP_DATABASE_URL") as error:
        Settings(database_url=SecretStr(url))

    assert url not in str(error.value)


def test_production_requires_a_database_url() -> None:
    with pytest.raises(ValidationError, match="APP_DATABASE_URL"):
        Settings(env=Environment.PRD, allowed_hosts=["work.example.test"], database_url=None)


def test_runtime_bundle_selects_only_the_work_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("APP_DATABASE_URL", "postgresql://local@localhost/work_service_test")
    monkeypatch.setenv(
        "APP_SECRETS",
        json.dumps(
            {
                "WORK_API_DATABASE_URL": (
                    "postgresql://work_api_dev_runtime:bundle%40pass@10.0.0.5:5432/app_db_work_dev"
                ),
                "DATABASE_URL": "postgresql://other:other-pass@10.0.0.5:5432/app_db_dev",
                "APP_ENV": "prd",
                "JWT_SECRET": "synthetic-unused-secret",
            }
        ),
    )

    settings = Settings()

    assert settings.env == "dev"
    assert settings.database_url is not None
    assert settings.database_url.get_secret_value() == (
        "postgresql+asyncpg://work_api_dev_runtime:bundle%40pass@10.0.0.5:5432/app_db_work_dev"
    )
    assert "bundle%40pass" not in repr(settings)
    assert "other-pass" not in repr(settings)
    assert "synthetic-unused-secret" not in repr(settings)


@pytest.mark.parametrize(
    ("payload", "error_text"),
    [
        ("", "APP_SECRETS must be a JSON object"),
        ('{"key":"synthetic-private-input"', "APP_SECRETS must be a JSON object"),
        ('["synthetic-private-input"]', "APP_SECRETS must be a JSON object"),
        ('{"DATABASE_URL":"synthetic-private-input"}', "requires a nonempty WORK_API_DATABASE_URL"),
        ('{"WORK_API_DATABASE_URL":[]}', "requires a nonempty WORK_API_DATABASE_URL"),
        ('{"WORK_API_DATABASE_URL":"  "}', "requires a nonempty WORK_API_DATABASE_URL"),
    ],
)
def test_invalid_present_bundle_fails_without_using_local_url(
    monkeypatch: pytest.MonkeyPatch, payload: str, error_text: str
) -> None:
    monkeypatch.setenv(
        "APP_DATABASE_URL", "postgresql://local:local-pass@localhost/work_service_test"
    )
    monkeypatch.setenv("APP_SECRETS", payload)

    with pytest.raises(ValidationError, match=error_text) as error:
        Settings()

    assert "synthetic-private-input" not in str(error.value)
    assert "local-pass" not in str(error.value)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://work_api_dev_migrator:synthetic-pass@10.0.0.5/app_db_work_dev",
        "postgresql://work_api_prd_runtime:synthetic-pass@10.0.0.5/app_db_work_prd",
        "postgresql://work_api_dev_runtime:synthetic-pass@10.0.0.5/app_db_dev",
        "postgresql://work_api_dev_runtime:synthetic-pass@10.0.0.5/app_db_work_dev"
        "?user=work_api_dev_migrator",
        "postgresql://work_api_dev_runtime@10.0.0.5/app_db_work_dev",
    ],
)
def test_runtime_bundle_requires_an_environment_matched_runtime_login(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("APP_SECRETS", json.dumps({"WORK_API_DATABASE_URL": url}))

    with pytest.raises(
        ValidationError, match="WORK_API_DATABASE_URL must use the Work API runtime"
    ) as error:
        Settings()

    assert url not in str(error.value)
    assert "synthetic-pass" not in str(error.value)


def test_alembic_database_settings_ignore_runtime_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SECRETS", "synthetic-invalid-bundle")
    monkeypatch.setenv(
        "APP_DATABASE_URL",
        "postgresql://work_api_dev_migrator:synthetic-pass@localhost/app_db_work_dev",
    )

    settings = DatabaseSettings()

    assert settings.database_url is not None
    assert settings.database_url.get_secret_value() == (
        "postgresql+asyncpg://work_api_dev_migrator:synthetic-pass@localhost/app_db_work_dev"
    )
    monkeypatch.delenv("APP_DATABASE_URL")
    assert DatabaseSettings().database_url is None
