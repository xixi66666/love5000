"""运行配置的唯一入口。

取值优先级（高到低）：环境变量 → ``backend/.env``（:class:`Settings` 的
``env_file``）→ 代码默认值。两个字段例外地有“派生”兜底：

- 数据库连接为空时，读取 ``website/src/main/resources/application.yml`` 的
  ``spring.datasource``，展开其中的 ``${WEBSITE_DB_*}`` 占位符并转成
  ``mysql+asyncmy`` 连接串，从而与 ``website`` 共用 ``xixi`` 库而不复制凭据；
- GitHub Token 为空时读取 ``backend/.secrets/github_token``。

约束：Token、ADMIN_KEY、BGM 路径都用 ``SecretStr`` / ``repr=False`` 承载，
派生失败只抛出不含凭据的说明文本，任何分支都不把密码写进异常消息或日志。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlsplit

import yaml
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# parents[2] 是 backend 目录，parents[4] 是 website 模块目录；两处私有文件均已被 .gitignore 排除。
SECRETS_DIR = Path(__file__).resolve().parents[2] / ".secrets"
GITHUB_TOKEN_FILE = SECRETS_DIR / "github_token"
WEBSITE_APPLICATION_FILE = Path(__file__).resolve().parents[4] / "src/main/resources/application.yml"


def _resolve_website_value(value: object) -> str:
    """展开 Spring 风格的 ``${变量名:默认值}`` 占位符。

    ``website`` 的 ``application.yml`` 用这种写法读取 ``WEBSITE_DB_*``，这里按同名
    环境变量替换；变量缺失时使用冒号后的默认值，没有默认值则为空串。

    Args:
        value: YAML 里的原始值，可能是 ``None`` 或非字符串。

    Returns:
        展开后的字符串。
    """
    return re.sub(
        r"\$\{([^}:]+)(?::([^}]*))?\}",
        lambda match: os.environ.get(match[1], match[2] or ""),
        str(value or ""),
    )


def _read_website_database_url() -> str:
    """从 website 的 ``application.yml`` 派生 asyncmy 连接串。

    解析步骤：读 YAML → 取 ``spring.datasource`` → 展开占位符 → 确认是
    ``jdbc:mysql://`` → 用 ``sqlalchemy.engine.URL`` 重组为 ``mysql+asyncmy``，
    并把字符集固定为 utf8mb4。库名做 URL 反转义，密码保持原样交给驱动。

    Returns:
        带明文密码的连接串，仅供 SQLAlchemy 建连接池使用，不得写日志。

    Raises:
        ValueError: 文件缺失、YAML 非法、URL 不是 MySQL 或缺少主机/库名时抛出，
            消息里只说明“检查配置或设置 DATABASE_URL”，不含原始配置内容。
    """
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
    """读取 ``.secrets/github_token`` 里的 Token。

    文件缺失或不是合法 UTF-8 时返回空串而非抛错：本地没有 Token 仍能启动服务，
    只是采集更容易被 GitHub 限流。

    Returns:
        去掉首尾空白的 Token，缺失时为空串。
    """
    try:
        return GITHUB_TOKEN_FILE.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""


class Settings(BaseSettings):
    """全部运行配置，进程内共用一个实例（见文件末尾的 ``settings``）。

    字段名与环境变量名大小写无关地一一对应（``DATABASE_URL`` → ``database_url``）。
    ``extra="ignore"`` 允许 ``.env`` 里保留其他工具用的键而不报错；因此新增配置时
    只需在此声明字段，不必修改解析逻辑。
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 显式配置优先；为空时由下方 model_validator 从 website 的 application.yml 派生。
    # repr=False 保证它不会出现在 Settings 的 repr、异常消息或调试输出里。
    database_url: str = Field(default="", repr=False)
    # GitHub Token；为空时读取 backend/.secrets/github_token，只用于请求头。
    github_token: SecretStr = SecretStr("")
    # 管理接口密钥；未配置时所有管理端点都返回 401，不会因为“没配置”而放行。
    admin_key: SecretStr = SecretStr("")
    # 业务时区：决定“今天”的归属，影响 Star 快照日期与日报日期，不要改成 UTC。
    business_timezone: str = "Asia/Shanghai"
    # 五段式 cron：分 时 日 月 周；默认每天 02:00 采集一次。
    collection_cron: str = "0 2 * * *"
    # 默认关闭：本机开发与 pytest 不启动后台调度，避免测试期间访问真实网络。
    scheduler_enabled: bool = False
    # 每个周期（日/周/月）保留的仓库条数。
    trending_top_n: int = 10
    # 逗号分隔的 AI 关键词；过滤时不区分大小写，空串表示不过滤。
    trending_ai_keywords: str = (
        "ai,agent,agents,llm,gpt,claude,anthropic,openai,gemini,deepseek,copilot,"
        "mcp,model context protocol,skill,skills,plugin,plugins,rag,prompt,"
        "generative,genai,machine learning,neural,embedding,transformer,"
        "chatbot,multimodal,computer vision,speech"
    )
    # 代理地址，同时用于 GitHub Trending、GitHub API 与 README 请求；空串表示直连。
    trending_proxy: str = ""
    # 成功/部分成功任务的冷却分钟数；FAILED 不受此限制，可立即重试。
    refresh_cooldown_minutes: int = 30
    # 允许跨域访问的来源，逗号分隔。
    cors_origins: str = "http://localhost:10002"
    # 中文简介：开关、并发批次与单次调用超时。密钥与模型名不在这里，统一来自 model.properties。
    intro_enabled: bool = False
    intro_concurrency: int = 8
    intro_batch_size: int = 5
    intro_timeout_seconds: int = 300
    # 近 30 天研究：调用用户级 skill，目录留空时按 ~/.codex 等约定位置自动发现。
    last30days_enabled: bool = True
    last30days_skill_dir: str = ""
    last30days_python: str = ""
    last30days_memory_dir: str = ""
    last30days_timeout_seconds: int = 600
    # 日报产物根目录（相对 backend 运行目录）；下面一组字段全部属于云端日报与视频流程。
    daily_reports_dir: str = "data/daily-reports"
    daily_public_url: str = "http://127.0.0.1:5177"
    # 配音音色与视频引擎；引擎失败不会自动切换，必须显式改配置。
    daily_tts_voice: str = "zh-CN-YunxiNeural"
    daily_video_renderer: Literal["remotion", "hyperframes", "legacy"] = "hyperframes"
    daily_node_command: str = "node"
    remotion_browser_executable: str = ""
    remotion_concurrency: int = Field(default=2, ge=1, le=8)
    hyperframes_browser_executable: str = ""
    hyperframes_concurrency: int = Field(default=1, ge=1, le=8)
    # 单次渲染超时，单位秒，限制在 1-120 分钟，防止卡死进程长期占用资源。
    daily_render_timeout_seconds: int = Field(default=1800, ge=60, le=7200)
    daily_tts_provider: Literal["edge", "mimo"] = "mimo"
    daily_whisper_model: str = "small"
    daily_assets_dir: str = "data/video-assets"
    daily_require_demo_assets: bool = True
    # FFmpeg 工具链命令，可填绝对路径以适配未加入 PATH 的安装。
    daily_ffmpeg_command: str = "ffmpeg"
    daily_ffprobe_command: str = "ffprobe"
    # 可选配乐：本地授权文件优先，其次 HTTPS 来源；两者都为空时不加背景音乐。
    daily_bgm_file: str = Field(default="", repr=False)
    daily_bgm_source: str = ""
    daily_font: str = ""
    # QQ 推送（可选）：目标与 OpenClaw 命令必须同时配置，否则 notify 接口直接回 409。
    daily_qq_target: str = ""
    daily_openclaw_command: str = ""
    # 抖音登录态文件（私有，禁止提交）与发布总开关；未登录或开关关闭时只生成不发布。
    douyin_storage_state: str = ".secrets/douyin-state.json"
    douyin_publish_enabled: bool = False

    @model_validator(mode="after")
    def _load_token_from_file(self) -> Settings:
        """在字段解析完成后补齐两个“从文件派生”的值。

        只在对应字段为空时派生，因此环境变量或 ``.env`` 的显式配置始终优先；
        派生失败（YAML 缺失/非法）会让进程启动即失败，而不是等到第一次采集才报错。

        Returns:
            自身，供 pydantic 继续后续校验。
        """
        if not self.database_url:
            self.database_url = _read_website_database_url()
        if not self.github_token.get_secret_value():
            self.github_token = SecretStr(_read_token_file())
        return self


# 进程级单例：导入即读取 .env 并可能读取 website 的 application.yml，所有模块共用同一份配置。
settings = Settings()
