import pytest

from app.core.config import Settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "mysql+asyncmy://user:pass@localhost/db")
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    settings = Settings(_env_file=None)
    assert settings.business_timezone == "Asia/Shanghai"
    assert settings.trending_top_n == 10
    assert "agent" in settings.trending_ai_keywords
    assert settings.trending_proxy == ""
    assert settings.scheduler_enabled is False
    assert "secret-token" not in repr(settings)
