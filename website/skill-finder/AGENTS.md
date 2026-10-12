# AGENTS.md

## 服务边界

`website/skill-finder` 是 `love5000` 中的独立 AI 项目趋势追踪微服务（GitHub Trending 采集 + 排行展示），
**不是** Java Maven 模块，不加入父 `pom.xml` 的 `<modules>`，不执行 `mvn -pl skill-finder ...`。

- 后端：`backend/app/main.py`，FastAPI + SQLAlchemy 2（异步）+ APScheduler + Scrapling，Python 3.11+。
- 前端：`frontend/`，Vue 3 + TypeScript + Vite；构建产物 `frontend/dist` 由后端同端口托管。
- 默认端口 `5177`，`GET /api/health` 返回 `{"success": true, "service": "skill-finder"}`。
- 数据库：腾讯云 MySQL 上的 `skill_finder` 库（与 `website` 的 `xixi` 库同机不同库），表结构见 `backend/sql/schema.sql`。
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
- `backend/.env` 与 `backend/.secrets/` 是本地私有文件，已被 `.gitignore` 排除，禁止提交；
  数据库密码、GitHub Token 只放这里或环境变量。
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
