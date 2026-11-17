import pytest
from pydantic import ValidationError

from app.core.config import Settings


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
