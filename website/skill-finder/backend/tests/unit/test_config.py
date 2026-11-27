"""配置层默认值与凭据脱敏的回归测试。

`Settings(_env_file=None)` 显式跳过 `backend/.env`，只让 monkeypatch 注入的两个环境变量
生效，因此断言与开发者本机的私有配置无关。用例锁定的是：业务时区固定 `Asia/Shanghai`、
榜单只取前 10、AI 关键词表包含 `agent`、代理默认为空（默认直连）、调度器默认关闭
（离线测试与本地开发都不自动采集）。
最后一条断言要求 `repr(settings)` 不出现 GitHub Token——配置对象常被日志和异常信息
打印，一旦泄漏相当于把凭据写进日志。
"""

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
