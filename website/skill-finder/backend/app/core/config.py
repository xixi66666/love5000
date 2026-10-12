from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRETS_DIR = Path(__file__).resolve().parents[2] / ".secrets"
GITHUB_TOKEN_FILE = SECRETS_DIR / "github_token"


def _read_token_file() -> str:
    try:
        return GITHUB_TOKEN_FILE.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "mysql+asyncmy://skill_finder:change_me@127.0.0.1:3306/skill_finder?charset=utf8mb4"
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
    opencode_api_key: str = ""
    intro_concurrency: int = 8
    intro_batch_size: int = 5
    intro_timeout_seconds: int = 300
    last30days_enabled: bool = True
    last30days_skill_dir: str = ""
    last30days_python: str = ""
    last30days_memory_dir: str = ""
    last30days_timeout_seconds: int = 600

    @model_validator(mode="after")
    def _load_token_from_file(self) -> Settings:
        if not self.github_token.get_secret_value():
            self.github_token = SecretStr(_read_token_file())
        return self


settings = Settings()
