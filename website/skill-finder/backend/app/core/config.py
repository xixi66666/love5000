from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

SECRETS_DIR = Path(__file__).resolve().parents[2] / ".secrets"
GITHUB_TOKEN_FILE = SECRETS_DIR / "github_token"
WEBSITE_APPLICATION_FILE = Path(__file__).resolve().parents[4] / "src/main/resources/application.yml"


def _resolve_website_value(value: object) -> str:
    return re.sub(
        r"\$\{([^}:]+)(?::([^}]*))?\}",
        lambda match: os.environ.get(match[1], match[2] or ""),
        str(value or ""),
    )


def _read_website_database_url() -> str:
    try:
        document = yaml.safe_load(WEBSITE_APPLICATION_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError):
        raise ValueError("无法读取 website application.yml，请检查文件或设置 DATABASE_URL") from None

    try:
        datasource = document["spring"]["datasource"]
        jdbc_url = _resolve_website_value(datasource["url"])
        if not jdbc_url.startswith("jdbc:mysql://"):
            raise ValueError()
        parsed = urlsplit(jdbc_url.removeprefix("jdbc:"))
        if not parsed.hostname or not parsed.path.strip("/"):
            raise ValueError()
        url = URL.create(
            "mysql+asyncmy",
            username=_resolve_website_value(datasource["username"]),
            password=_resolve_website_value(datasource.get("password", "")),
            host=parsed.hostname,
            port=parsed.port or 3306,
            database=unquote(parsed.path.lstrip("/")),
            query={"charset": "utf8mb4"},
        )
        return url.render_as_string(hide_password=False)
    except (KeyError, TypeError, ValueError):
        raise ValueError("website application.yml 数据库配置无效，请检查配置或设置 DATABASE_URL") from None


def _read_token_file() -> str:
    try:
        return GITHUB_TOKEN_FILE.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(default="", repr=False)
    github_token: SecretStr = SecretStr("")
    admin_key: SecretStr = SecretStr("")
    business_timezone: str = "Asia/Shanghai"
    collection_cron: str = "0 2 * * *"
    scheduler_enabled: bool = False
    trending_top_n: int = 10
    trending_ai_keywords: str = (
        "ai,agent,agents,llm,gpt,claude,anthropic,openai,gemini,deepseek,copilot,"
        "mcp,model context protocol,skill,skills,plugin,plugins,rag,prompt,"
        "generative,genai,machine learning,neural,embedding,transformer,"
        "chatbot,multimodal,computer vision,speech"
    )
    trending_proxy: str = ""
    refresh_cooldown_minutes: int = 30
    cors_origins: str = "http://localhost:10002"
    intro_enabled: bool = False
    intro_model: str = "opencode-go/ox-alpha-free,opencode-go/deepseek-v4-flash"
    intro_api_base: str = "https://opencode.ai/zen/go/v1"
    intro_api_key: SecretStr = SecretStr("")
    opencode_api_key: str = ""
    intro_concurrency: int = 8
    intro_batch_size: int = 5
    intro_timeout_seconds: int = 300
    last30days_enabled: bool = True
    last30days_skill_dir: str = ""
    last30days_python: str = ""
    last30days_memory_dir: str = ""
    last30days_timeout_seconds: int = 600
    daily_reports_dir: str = "data/daily-reports"
    daily_public_url: str = "http://127.0.0.1:5177"
    daily_tts_voice: str = "zh-CN-YunxiNeural"
    daily_font: str = ""
    daily_qq_target: str = ""
    daily_openclaw_command: str = ""
    douyin_storage_state: str = ".secrets/douyin-state.json"
    douyin_publish_enabled: bool = False

    @model_validator(mode="after")
    def _load_token_from_file(self) -> Settings:
        if not self.database_url:
            self.database_url = _read_website_database_url()
        if not self.github_token.get_secret_value():
            self.github_token = SecretStr(_read_token_file())
        return self


settings = Settings()
