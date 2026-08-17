import pytest
from pydantic import ValidationError

from services.gateway.app.config import Settings


def test_settings_load_required_environment() -> None:
    settings = Settings(
        database_url="postgresql+psycopg2://postgres:postgres@localhost:5432/test",
        jwt_secret_key="secure-test-secret-value",
        _env_file=None,
    )

    assert settings.database_url.startswith("postgresql+psycopg2://")
    assert settings.jwt_secret_key.get_secret_value() == "secure-test-secret-value"


def test_settings_rejects_non_postgresql_database_url() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="sqlite:///local.db",
            jwt_secret_key="secure-test-secret-value",
            _env_file=None,
        )


def test_settings_rejects_placeholder_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg2://postgres:postgres@localhost:5432/test",
            jwt_secret_key="CHANGE_THIS_IN_PRODUCTION",
            _env_file=None,
        )
