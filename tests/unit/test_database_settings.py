import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Environment, Settings


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
