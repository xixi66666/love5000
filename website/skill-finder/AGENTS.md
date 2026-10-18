# AGENTS.md

## 服务边界

`website/skill-finder` 是 `love5000` 中的独立 AI 项目趋势追踪微服务（GitHub Trending 采集 + 排行展示），
**不是** Java Maven 模块，不加入父 `pom.xml` 的 `<modules>`，不执行 `mvn -pl skill-finder ...`。

- 后端：`backend/app/main.py`，FastAPI + SQLAlchemy 2（异步）+ APScheduler + Scrapling，Python 3.11+。
- 前端：`frontend/`，Vue 3 + TypeScript + Vite；构建产物 `frontend/dist` 由后端同端口托管。
- 默认端口 `5177`，`GET /api/health` 返回 `{"success": true, "service": "skill-finder"}`。
- 数据库：与 `website` 共用腾讯云 MySQL 上的 `xixi` 库，表结构见 `backend/sql/schema.sql`。首次接入只补建缺失业务表，不删除或重建已有表。
- Java 侧只负责点击启动、健康检测和入口链接（`website` 的 `integration/skillfinder` 包），
  不把业务逻辑改写进 Controller。

## 启动方式

- 主入口：`website` 首页 Dock“Skill Finder”卡片点击启动
  （`POST /api/services/skill-finder/start`），离线时拉起、在线时复用。
- 服务不随 `website` 启动自动拉起；`website` 关闭也不会强杀该服务。
- 手动启动：

```bash
cd website/skill-finder/backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 5177
```

Java 端 Python 命令解析顺序：`backend/.venv/Scripts/python.exe`（Unix 为 `.venv/bin/python`）
→ 回退 `uv run python`（`skill-finder.click-start.command` 默认 `uv`）。
venv 缺失且 uv 不可用时返回明确错误，不做长时间空等。

## 环境准备

```bash
cd website/skill-finder/backend
uv sync

cd ../frontend
npm install
npm run build
```

- `frontend/dist` 是启动前置条件；未构建时启动接口返回“前端尚未构建”错误。
- `uv sync` 安装的 `cryptography` 用于 MySQL `caching_sha2_password` / `sha256_password` 认证，不能省略。
- 数据库默认直接读取 `website/src/main/resources/application.yml` 的 `spring.datasource`，解析 `WEBSITE_DB_URL` / `WEBSITE_DB_USERNAME` / `WEBSITE_DB_PASSWORD`，并转换为 `mysql+asyncmy` 的 utf8mb4 连接串；凭据不打印、不复制到文件。`DATABASE_URL` 环境变量或 `backend/.env` 的显式配置优先于共享配置。
- `backend/.env` 与 `backend/.secrets/` 是本地私有文件，已被 `.gitignore` 排除，禁止提交；
  独立覆盖的数据库连接和 GitHub Token 只放这里或环境变量。
- 忽略 `.venv/`、`node_modules/`、`frontend/dist/`、`__pycache__/`、`.pytest_cache/`、
  `.ruff_cache/`、`*.log`，不要提交这些内容。

## 后端改动约定

- `app/main.py` 顶部维护 `/api/health`、`FRONTEND_DIST_DIR` 静态托管与 MIME 修复：
  `/assets` 挂载构建资源，其余非 `api/` 路径做 SPA fallback 返回 `dist/index.html`，
  并做路径穿越防护；未匹配的 `/api/**` 保持 404。
- Windows 注册表常把 `.js` 标记为 `text/plain`，而 Python `mimetypes` 在 Windows 会读注册表，
  导致 ES module 被浏览器严格 MIME 检查拦截（页面黑屏）。`main.py` 顶部显式
  `mimetypes.add_type("text/javascript", ".js"/".mjs")`，并由
  `test_built_javascript_asset_is_served_with_javascript_mime_type` 回归覆盖，不要删除。
- 数据库 CRUD 走 `app/repositories/` + SQLAlchemy 模型，不在 API 层写裸 SQL。
- 原 `skill_finder` 库的五张业务表数据已复制到 `xixi`，源库保留；后续运行与采集写入 `xixi`。
- 采集任务使用 MySQL 命名锁防并发；改动采集、趋势或 last30days 逻辑时保留失败降级路径。
- 新增 API 或改动路由时，同步更新本文件、`README.md`、`website/AGENTS.md` 与根文档。

## 测试

```bash
cd website/skill-finder/backend
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m pytest -q

cd ../frontend
npm run lint
npm run typecheck
npm run test -- --run
npm run build
```

- `tests/test_health.py` 覆盖 `/api/v1/health`、统一 `/api/health`、未匹配 `/api/**` 的 404、
  dist 构建后 `/` 返回 HTML 与 JS 资源 MIME；测试通过 `TestClient` 直接请求，不连接真实 MySQL。
- `tests/unit/test_website_database_config.py` 覆盖共享 YAML、环境变量解析、凭据转义、显式连接串覆盖与脱敏错误；`test_database_auth.py` 验证 MySQL SHA-2 的 RSA 认证依赖，不连接真实数据库。
- `tests/integration` 需要独立测试库与 `TEST_DATABASE_URL`（fixture 会 DROP 重建表），
  未设置时明确跳过，不得指向生产库。
- 改动启动器（Java 侧）时至少运行：

```bash
mvn -pl website -am test
```

## 文档同步

每次修改本服务的端口、启动方式、环境准备、API、数据文件、测试方式或与
`website` 的集成方式时，必须同步更新本文件、本目录 `README.md`、
`website/AGENTS.md`、`website/README.md` 以及根 `AGENTS.md` / `README.md`。

## Skill Finder 云端日报与视频

`website/skill-finder` 继续作为独立 FastAPI + Vue 微服务，以 love5000 版本为准同步到 `C:/Code/skills-finder`。云端采用 Docker + Nginx，入口 `https://49.232.128.132/skill-finder/`，日报审核 `/skill-finder/daily-reports`，后端仅监听回环 15177，本机开发仍用 5177。复用 xixi 原五张业务表，不重建共享库。

服务器北京时间 07:10 采集、07:30 制作（07:45 重试）、08:00 送达；当前 QQ 按用户要求暂不配置。成品包括文字日报、中文配音、字幕与竖屏视频，GitHub 当日 AI 项目不足十项时如实标注。DeepSeek 使用通用 `INTRO_API_KEY`、`INTRO_API_BASE`、`INTRO_MODEL` 私有配置，不把凭据写入 Git。

新增 API 前缀 `/api/v1/daily-reports`：GET 列表、GET `/{date}`、GET `/{date}/files/{filename}`；管理接口 POST `/generate`、POST `/{date}/review`、POST `/{date}/publish`；抖音登录 POST/GET `/publisher/login` 和受认证的 GET `/publisher/login/screen`。管理接口要求 X-Admin-Key，并只允许 HTTPS 或本机 SSH 隧道。发布必须绑定具体视频、口播和文案的人工批准；未登录不发布，结果不确定不自动重发。

`backend/app/daily/` 管理生成、媒体、审核摘要与发布适配；`backend/data/`、`.secrets/`、云端 `/var/lib/skill-finder/` 为私有运行数据，不提交。`deploy/` 维护 Docker、cron、Nginx 与 IP 证书续签；OpenClaw 在独立 Node 容器内仅监听回环 18789，QQ/抖音必须如实区分未配置、等待登录与已送达/已发布。完整部署、凭据边界与验证见 `website/skill-finder/docs/cloud-daily-report.md`（模块内为 `docs/cloud-daily-report.md`）。本机首页点击启动约定保持不变。
