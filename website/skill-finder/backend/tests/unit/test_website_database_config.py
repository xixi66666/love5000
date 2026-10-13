from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.core import config


@pytest.fixture()
def website_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("DATABASE_URL", "WEBSITE_DB_URL", "WEBSITE_DB_USERNAME", "WEBSITE_DB_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    config_file = tmp_path / "application.yml"
    config_file.write_text(
        "spring:\n"
        "  datasource:\n"
        "    url: ${WEBSITE_DB_URL:jdbc:mysql://db.example.test:3306/xixi?characterEncoding=UTF-8}\n"
        "    username: ${WEBSITE_DB_USERNAME:YOUR_USERNAME_HERE}\n"
        "    password: ${WEBSITE_DB_PASSWORD:YOUR_PASSWORD_HERE}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "WEBSITE_APPLICATION_FILE", config_file, raising=False)
    return config_file


def test_reads_website_datasource_when_database_url_is_not_set(website_config: Path) -> None:
    settings = config.Settings(_env_file=None)
    url = make_url(settings.database_url)
    assert url.drivername == "mysql+asyncmy"
    assert url.host == "db.example.test"
    assert url.port == 3306
    assert url.database == "xixi"
    assert url.username == "YOUR_USERNAME_HERE"
    assert url.password == "YOUR_PASSWORD_HERE"
    assert url.query == {"charset": "utf8mb4"}
    assert settings.database_url not in repr(settings)


def test_resolves_website_environment_overrides_and_encodes_credentials(
    website_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSITE_DB_URL", "jdbc:mysql://override.example.test:3307/xixi")
    monkeypatch.setenv("WEBSITE_DB_USERNAME", "YOUR_USERNAME_HERE@user")
    monkeypatch.setenv("WEBSITE_DB_PASSWORD", "YOUR_PASSWORD_HERE:#@/?")
    url = make_url(config.Settings(_env_file=None).database_url)
    assert url.host == "override.example.test"
    assert url.port == 3307
    assert url.username == "YOUR_USERNAME_HERE@user"
    assert url.password == "YOUR_PASSWORD_HERE:#@/?"


def test_explicit_database_url_overrides_website_config(
    website_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    website_config.unlink()
    database_url = "mysql+asyncmy://YOUR_USERNAME_HERE:YOUR_PASSWORD_HERE@custom.example.test/db"
    monkeypatch.setenv("DATABASE_URL", database_url)
    assert config.Settings(_env_file=None).database_url == database_url


def test_dotenv_database_url_overrides_website_config(website_config: Path) -> None:
    database_url = "mysql+asyncmy://YOUR_USERNAME_HERE:YOUR_PASSWORD_HERE@custom.example.test/db"
    env_file = website_config.with_name(".env")
    env_file.write_text("DATABASE_URL=" + database_url + "\n", encoding="utf-8")
    assert config.Settings(_env_file=env_file).database_url == database_url


def test_missing_website_config_reports_actionable_error(website_config: Path) -> None:
    website_config.unlink()
    with pytest.raises(ValueError, match="application.yml.*DATABASE_URL"):
        config.Settings(_env_file=None)


def test_invalid_website_config_does_not_expose_password(website_config: Path) -> None:
    website_config.write_text(
        "spring:\n  datasource:\n    url: invalid\n    password: YOUR_PASSWORD_HERE\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as error:
        config.Settings(_env_file=None)
    assert "YOUR_PASSWORD_HERE" not in str(error.value)
