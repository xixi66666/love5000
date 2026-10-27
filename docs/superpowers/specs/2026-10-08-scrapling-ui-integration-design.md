# Scrapling UI 集成设计

## 背景

本地已有一份汉化后的 **Scrapling UI v1.2.0**（交互式可视化爬虫工作台）：
React + TypeScript + Vite 前端，FastAPI + Playwright + APScheduler 后端，
后端依赖 `scrapling[fetchers]`，前端上游使用 bun、后端使用 uv 管理 Python 3.14。

当前它以临时目录形式存在于本机（`%TEMP%\opencode\scrapling-ui-run\`），没有
纳入版本库，也没有接入 `love5000` 的统一入口、健康检查和端口约定。用户希望把它
集成进项目：在 `website` 首页服务 Dock 增加一个按钮，**点击一次即启动服务并打开
Scrapling UI 页面**，不随 `website` 启动自动拉起。

## 目标

- 将汉化的 Scrapling UI 作为独立微服务收入 `website/scrapling-ui/`，不加入 Maven 模块。
- 后端固定端口 `5176`，同时托管构建后的前端静态页面，单进程运行。
- 后端提供 `GET /api/health`：`{"success": true, "service": "scrapling-ui"}`。
- `website` 首页 Dock 新增第 6 个服务入口（按钮语义）：
  - 服务在线时点击直接打开 `http://127.0.0.1:5176/`。
  - 服务离线时点击调用 `website` 后端启动接口，卡片显示“启动中”，健康后自动打开。
- 服务**不在** `website` 启动时自动拉起；只由用户点击触发。
- 同步更新根目录与 `website` 的 `AGENTS.md` / `README.md`，并新增
  `website/scrapling-ui/AGENTS.md` / `README.md`。

## 非目标

- 不重构 Scrapling UI 的业务功能（抓取会话、选择器测试、网络分析、调度器等保持原样）。
- 不把 `scrapling-ui` 加入父 `pom.xml` 的 `<modules>`，不重写进 Java Controller。
- 不引入 bun；前端构建使用已安装的 node/npm。
- 不改动 `python-a`、`quant-a` 的自动启动行为。
- 不提交 `backend/.venv`、`frontend/node_modules`、`frontend/dist`、日志与 `jobs.db`。

## 现状事实（集成约束）

- 后端 `requires-python >= 3.14`，用 uv 创建的 `backend/.venv`（Python 3.14.8），
  全局 Python 3.11 无法运行，必须沿用项目 venv 或 `uv run`。
- 本机无 bun；node v24 + npm 可用。
- 前端所有请求使用相对路径 `/api/...`，同端口静态托管时天然可用。
- 后端 `main.py` 启动时 `lifespan` 会拉起 Playwright 浏览器与 APScheduler，
  启动耗时高于普通 Python 服务，等待健康超时需放宽（默认 90s）。
- Windows 控制台为 GBK 时，后端部分 emoji 日志会触发 `UnicodeEncodeError`
  （已有历史日志佐证），通过启动环境变量 `PYTHONUTF8=1` /
  `PYTHONIOENCODING=utf-8` / `PYTHONUNBUFFERED=1` 规避，不改业务代码。
- Playwright Chromium 未随包安装，需要 `playwright install chromium`。

## 目录与运行方式

```text
website/scrapling-ui/
├── README.md            # love5000 集成版说明（保留上游功能概览）
├── AGENTS.md            # 微服务边界、启动、端口、测试
├── todo_list.md         # 上游运行时任务清单（保留）
├── start.sh             # 上游脚本，保留作参考（Windows 主路径为 Java 启动）
├── backend/
│   ├── main.py          # 增加 /api/health + 静态托管
│   ├── models.py
│   ├── core/            # browser_manager / session / dom_extractor / db
│   ├── services/        # code_generator / code_runner / scheduler / deepseek_healer
│   ├── pyproject.toml / uv.lock
│   └── tests/           # 新增轻量健康测试
└── frontend/
    ├── src/             # 已汉化的 React 源码
    ├── package.json / package-lock.json
    └── dist/            # npm run build 产物（gitignored，本地保留）
```

- 复制来源为本地汉化版，排除 `.venv`、`node_modules`、`dist`、日志、
  `__pycache__`、`jobs.db`。
- 前端构建：`npm ci && npm run build`，产物由后端托管。
- 后端运行：`backend/.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 5176`。

## Scrapling UI 代码改动

保持最小改动，仅两点 + 文档：

1. `backend/main.py`
   - `GET /api/health` 返回 `{"success": true, "service": "scrapling-ui"}`。
   - 前端静态托管：挂载 `/assets` 到 `frontend/dist/assets`；
     其余 GET 路径做 SPA fallback 返回 `dist/index.html`，先检查同名实体文件；
     排除 `api/` 前缀（未匹配的 API 仍返回 404）；防路径穿越；
     `dist` 缺失时返回清晰错误（HTTP 503 + 提示先构建前端）。
2. `frontend/vite.config.ts`：dev proxy 目标端口同步为 `5176`（仅开发用）。
3. `README.md`：重写为 love5000 集成版。

## Java 端设计（website 模块）

### 配置

```yaml
scrapling-ui:
  click-start:
    enabled: true
    work-dir: website/scrapling-ui
    command: uv
    port: 5176
    health-path: /api/health
    startup-timeout-seconds: 90
    log-to-console: true
```

`command` 是 venv 缺失时的回退启动器（默认 `uv`，执行 `uv run python`）。

`website.service-health.services` 清单追加：

```yaml
- name: scrapling-ui
  url: http://127.0.0.1:5176/api/health
```

### 组件

- `integration/scrapling/ScraplingUiProperties`：绑定 `scrapling-ui.click-start`，
  默认值与应用配置一致。
- `integration/scrapling/ScraplingUiProcessManager`：
  1. 先经 `ServiceHealthChecker` 探测；已在线直接返回 `already-running`。
  2. 校验 `backend/` 与前端 `dist/index.html` 存在，缺失返回可读错误。
  3. 解析 Python 命令：优先 `backend/.venv/Scripts/python.exe`（Unix 对应 `.venv/bin/python`）；
     缺失时回退 `uv run python`（`command` 默认 `uv`，可在本机按 uv.lock 自动准备环境）；
     两者都不可用时返回明确错误，不做 90s 无谓等待。
  4. `ProcessBuilder` 在 `backend/` 工作目录启动
     `[-m uvicorn main:app --host 127.0.0.1 --port {port}]`，
     注入 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`PYTHONUNBUFFERED=1`；
     `log-to-console=true` 时 `inheritIO()`，否则追加写
     `server.out.log` / `server.err.log`。
  5. 用统一健康检查按秒轮询直到就绪或超时；保存进程引用，重复点击不重复启动。
  6. 不实现 `@PreDestroy` 强杀：用户点击启动的服务应在 `website` 重启后继续存活，
     下次点击探测到健康则直接复用。
- `integration/scrapling/ScraplingUiController`：只做 HTTP 入参、响应组装和异常映射。

### API

```text
POST /api/services/scrapling-ui/start
GET  /api/services/scrapling-ui/status
```

`start` 成功（无论新启动还是已在线）：

```json
{ "success": true, "status": "started", "url": "http://127.0.0.1:5176/" }
```

`status` 取值：`started`（本次启动成功）、`already-running`（直接复用）。
失败：HTTP 503 + `{ "success": false, "message": "..." }`（消息不含堆栈与本机密钥）。

`status` 接口返回当前在线状态与访问 URL，供前端轮询兜底。

## 首页按钮交互

- `index.html`：Dock 新增 `service-card` 结构的 Scrapling 卡片
  （“Scrapling 抓取工坊 / SCRAPLING UI · 5176”），带
  `data-health-url="http://127.0.0.1:5176/api/health"`、
  `data-health-mode="no-cors"`、`data-start-url="/api/services/scrapling-ui/start"`、
  `data-app-url="http://127.0.0.1:5176/"`。
- `script.js`：
  - 在线：点击新标签打开 `data-app-url`，不被阻止。
  - 离线：阻止默认跳转，卡片进入 `is-starting` 状态（文案“启动中…”），
    `POST data-start-url`，成功后打开 `data-app-url`；失败恢复并展示提示。
  - 启动请求进行中不重复触发。
  - 30s 健康轮询与现有 5 张卡片一致。
- `style.css`：新增 `is-starting` 状态点样式（橙色脉冲），沿用现有
  `is-online` / `is-offline` 语义。

## 错误处理

- 健康探测失败、venv 缺失、dist 缺失、启动超时、进程内未捕获异常统一转换为
  `success=false` + 可读 `message`，不暴露堆栈、绝对路径细节以外的敏感信息。
- 启动失败不影响 `website` 本身与其他服务。
- 重复点击/并发点击只启动一次（进程引用 + 健康探测双重保护）。

## 测试

Java（不启动真实进程，mock 检查器/进程构造）：

- `ScraplingUiProcessManagerTest`：已在线复用、命令解析（venv 优先/回退）、
  工作目录解析（仓库根与 `website/` 模块目录两种启动位置）、dist 缺失、
  启动成功、超时失败。
- `ScraplingUiControllerTest`：start/status 成功与失败响应结构。

Python：

- `backend/tests/test_health.py`：`/api/health` 返回 `success=true` 与
  `service=scrapling-ui`；不启动浏览器（不使用 TestClient 上下文管理器）。

验证命令：

```bash
mvn -pl website -am test
cd website/scrapling-ui/backend && uv run python -m unittest discover -s tests -v
```

## 一次性环境准备（集成时执行并写入文档）

```bash
cd website/scrapling-ui/backend
uv sync
uv run playwright install chromium

cd ../frontend
npm ci
npm run build
```

## 文档同步

- 根 `AGENTS.md` / `README.md`：微服务列表、端口表、结构树、健康检查段、
  启动与测试命令、数据目录约定。
- `website/AGENTS.md` / `README.md`：点击启动流程、配置、API、Dock 第 6 卡片、
  测试要求。
- 新增 `website/scrapling-ui/AGENTS.md` / `README.md`。
- 顺带更正根文档中已删除的 `scripts/start-love5000.ps1` 引用（与实际仓库一致）。

## 风险与对策

- **venv 未创建** → 优先回退 `uv run`；uv 也不可用时启动接口返回明确提示，
  文档给出 `uv sync` 步骤。
- **Chromium 未安装** → 文档要求 `playwright install chromium`；
  session 启动失败时前端已有报错路径。
- **端口 5176 被占用** → 健康探测自然失败；消息提示检查端口占用。
- **GBK 控制台 emoji** → 启动环境变量已规避。
- **前端 dist 丢失** → `git pull` 后按文档重新 `npm run build`。
