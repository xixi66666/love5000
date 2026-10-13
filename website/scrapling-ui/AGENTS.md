# AGENTS.md

## 服务边界

`website/scrapling-ui` 是 `love5000` 中的独立可视化爬虫微服务，**不是** Java Maven 模块，
不加入父 `pom.xml` 的 `<modules>`，不执行 `mvn -pl scrapling-ui ...`。

- 后端：`backend/main.py`，FastAPI + Playwright + APScheduler，Python 3.12+（uv 默认管理 3.14）。
- 前端：`frontend/`，React + TypeScript + Vite，已汉化；构建产物 `frontend/dist` 由后端同端口托管。
- 默认端口 `5176`，`GET /api/health` 返回 `{"success": true, "service": "scrapling-ui"}`。
- Java 侧只负责点击启动、健康检测和入口链接（`website` 的 `integration.scrapling` 包），
  不把业务逻辑改写进 Controller。

## 启动方式

- 主入口：`website` 首页 Dock“Scrapling 抓取工坊”卡片点击启动
  （`POST /api/services/scrapling-ui/start`），离线时拉起、在线时复用。
- 服务不随 `website` 启动自动拉起；`website` 关闭也不会强杀该服务。
- 手动启动：

```bash
cd website/scrapling-ui/backend
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 5176
```

Java 端 `scrapling-ui.click-start.command` 可由 `SCRAPLING_UI_COMMAND` 覆盖，默认 `uv`。
uv 模式优先 `backend/.venv/Scripts/python.exe`（Unix 为 `.venv/bin/python`），
缺失时回退 `uv run python`。显式指定 Python 命令或完整路径时直接执行
`<python> -m uvicorn`，绕过 `.venv`，支持全局 Python 3.12+（Python 3.9 不支持）。
在 backend 目录执行 `uv pip install --python <python完整路径> -r pyproject.toml`
和 `<python> -m playwright install chromium` 准备全局依赖；设置用户环境变量后重启终端或 IDE。
全局模式测试使用 `<python> -m unittest discover -s tests -v`。

## 环境准备

```bash
cd website/scrapling-ui/backend
uv sync
uv run playwright install chromium

cd ../frontend
npm install
npm run build
```

- `frontend/dist` 是启动前置条件；未构建时启动接口返回“前端尚未构建”错误。
- `website/scrapling-ui/.gitignore` 忽略 `.venv/`、`node_modules/`、`frontend/dist/`、
  `backend/jobs.db`、`*.log`；不要提交这些内容。

## 后端改动约定

- `main.py` 顶部维护 `/api/health` 与 `FRONTEND_DIST_DIR` 静态托管：
  `/assets` 挂载构建资源，其余非 `api/` 路径做 SPA fallback 返回 `dist/index.html`，
  并做路径穿越防护；未匹配的 `/api/**` 保持 404。
- Windows 注册表常把 `.js` 标记为 `text/plain`，而 Python `mimetypes` 在 Windows 会读注册表，
  导致 ES module 被浏览器严格 MIME 检查拦截（页面黑屏）。`main.py` 顶部显式
  `mimetypes.add_type("text/javascript", ".js"/".mjs")`，并由
  `test_built_javascript_asset_is_served_with_javascript_mime_type` 回归覆盖，不要删除。
- 定时任务数据写入 `backend/jobs.db`（SQLite），属运行时文件，不提交。
- 路线图面板读写项目根目录 `todo_list.md`。
- Windows GBK 控制台下部分 emoji 日志会触发 `UnicodeEncodeError`；
  Java 启动器已注入 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`PYTHONUNBUFFERED=1`，
  手动启动时建议同样设置，不要在业务代码里为此改写日志格式。
- 新增 API 或改动路由时，同步更新本文件、`README.md`、`website/AGENTS.md` 与根文档。

## 测试

```bash
cd website/scrapling-ui/backend
uv run python -m unittest discover -s tests -v
```

- `tests/test_health.py` 覆盖 `/api/health`、未匹配 `/api/**` 的 404、
  以及 dist 构建后 `/` 返回 HTML；测试通过 `TestClient` 直接请求，
  不使用上下文管理器，因此不会启动 Playwright 浏览器。
- 改动启动器（Java 侧）时至少运行：

```bash
mvn -pl website -am test
```

## 文档同步

每次修改本服务的端口、启动方式、环境准备、API、数据文件、测试方式或与
`website` 的集成方式时，必须同步更新本文件、本目录 `README.md`、
`website/AGENTS.md`、`website/README.md` 以及根 `AGENTS.md` / `README.md`。
