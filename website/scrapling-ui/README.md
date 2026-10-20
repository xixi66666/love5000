# Scrapling UI（love5000 集成版）

基于 **Scrapling** + **Playwright** 的交互式可视化爬虫工作台（汉化版 v1.2.0）。
在无头浏览器画布中加载任意网页，悬停/点选元素自动生成 CSS Selector 与 XPath，
嗅探网络请求，录制交互时间线并实时生成可运行的 Python Scrapling 脚本。

## 与 love5000 的集成方式

- 位于 `website/scrapling-ui/`，是独立 Python 微服务，**不是** Maven 模块，
  不加入父 `pom.xml` 的 `<modules>`。
- 默认端口 `5176`，提供 `GET /api/health`：
  `{"success": true, "service": "scrapling-ui"}`。
- 前端构建产物由 FastAPI 后端同端口托管，运行时只有**一个进程**：
  打开 `http://127.0.0.1:5176/` 即是完整工作台。
- `website` 首页服务 Dock 第 6 张卡片“Scrapling 抓取工坊”是启动按钮：
  在线时点击直接打开；离线时点击调用
  `POST /api/services/scrapling-ui/start` 拉起服务，健康后自动打开页面。
- 服务**不随** `website` 启动自动拉起，只由用户点击或手动命令启动；
  启动后的服务在 `website` 重启后继续存活，下次点击会直接复用。

## 功能概览

- 交互式无头画布：输入 URL 后在浏览器会话中点击、填表、滚动，整页截图可滚动查看。
- 元素选择与选择器生成：自动生成 CSS Selector / XPath，数字 ID 使用
  `[id="..."]` 安全形式。
- 列表批量提取：点选列表项后泛化选择器，实时预览多行数据表格。
- 网络嗅探：查看 Fetch/XHR 等请求与响应详情。
- 可视化配方（Visual Recipe）：时间线可拖动排序、删除并自动回放重建。
- 反爬与提速开关：Cloudflare 绕过、广告拦截、Speed Mode 同步到生成代码。
- 多框架导出：Async Scrapling、原生 Playwright（Python / Node.js）、Scrapy。
- 定时任务：APScheduler 后台调度，支持 cron、启停、立即运行（SQLite `jobs.db`）。
- AI 选择器修复：可选 DeepSeek Key 对失效选择器给出修复建议。

## 目录结构

```text
website/scrapling-ui/
├── backend/                 FastAPI + Playwright 后端（Python 3.14，uv 管理）
│   ├── main.py              入口：API 路由 + /api/health + 前端静态托管
│   ├── models.py            Pydantic 请求/响应模型
│   ├── core/                浏览器管理、会话、DOM 提取、SQLite
│   ├── services/            代码生成、代码执行、调度器、AI 修复
│   ├── tests/               unittest 健康与静态托管测试
│   ├── pyproject.toml / uv.lock
│   └── .venv/               本地虚拟环境（gitignored）
├── frontend/                React + TypeScript + Vite 前端（已汉化）
│   ├── src/
│   ├── public/
│   ├── dist/                构建产物（gitignored，本地需构建）
│   └── package.json / package-lock.json
├── start.sh                 上游一键脚本（bash，保留作参考）
└── todo_list.md             工作台内“路线图”面板读写的数据文件
```

## 首次环境准备

```bash
cd website/scrapling-ui/backend
uv sync
uv run playwright install chromium

cd ../frontend
npm install
npm run build
```

- 后端支持 Python 3.12+，`uv` 默认自动准备 Python 3.14（`.python-version` = 3.14）。
- `playwright install chromium` 会下载 Chromium（约 112MB），是画布功能必需项。
- 前端构建使用已安装的 node/npm；上游脚本使用 bun，本集成不依赖 bun。

使用全局 Python 时，在 backend 目录执行
`uv pip install --python <python完整路径> -r pyproject.toml` 和
`<python> -m playwright install chromium`。将 `SCRAPLING_UI_COMMAND` 环境变量设为
该解释器完整路径，重启 `website` 所在终端或 IDE；启动器会直接执行
`<python> -m uvicorn`，即使 `.venv` 存在也不会使用它。默认 Python 3.9 不支持。
全局模式手动启动：`<python> -m uvicorn main:app --host 127.0.0.1 --port 5176`；
测试：`<python> -m unittest discover -s tests -v`。未设置环境变量时仍保留 uv 模式。

## 启动与访问

推荐在 `website` 首页点击“Scrapling 抓取工坊”卡片启动。

手动启动：

```bash
cd website/scrapling-ui/backend
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 5176
```

访问：

```text
http://127.0.0.1:5176/
http://127.0.0.1:5176/api/health
```

开发模式（Vite 热更新，`/api` 代理到 5176）：

```bash
cd website/scrapling-ui/frontend
npm run dev
```

## 测试

```bash
cd website/scrapling-ui/backend
uv run python -m unittest discover -s tests -v
```

## 数据与安全

- 定时任务数据保存在 `backend/jobs.db`（SQLite，gitignored）。
- AI 选择器修复使用前端传入的 DeepSeek Key，不在服务端落盘。
- 不提交 `.venv/`、`node_modules/`、`frontend/dist/`、`jobs.db`、`*.log`。

## 统一模型入口（2026-10-20）

主页提供全局文本模型选择，python-a、scrapling-ui、skill-finder、personal-agent 提供“跟随主页 / 服务原配置 / 独立模型”，下一次请求生效。图片、视觉、语音和视频保留专用模型；quant-a 与 lovestory 当前没有文本模型调用。
website 的 `/api/models` 提供目录核验、选择持久化和文本代理，状态文件为根 `.runtime/model-routing.json`，仅存模型 ID、不存密钥；Java 客户端在 common，Python 公共客户端在 website/model-routing，独立部署使用统一入口时需一并携带。原有认证保留。未选择时保留原逻辑，已选择但网关离线时报错。
共享选择器源为 website/src/main/resources/static/model-picker/picker.js，修改后执行 `python scripts/sync-model-picker.py`，React/Vue 修改后重新构建 dist。图片工作台新增独立图片模型下拉与 `OPENAI_IMAGE_MODELS` 白名单，支持 JSON/multipart 的 `model` 字段。
完整盘点、API、边界与验证见 [统一模型入口](../../docs/model-routing.md)。跨模块验证 `mvn test`；公共 Python 客户端验证 `python -m unittest discover -s website/model-routing`。
