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

- 后端要求 Python 3.14，由 `uv` 自动准备（`.python-version` = 3.14）。
- `playwright install chromium` 会下载 Chromium（约 112MB），是画布功能必需项。
- 前端构建使用已安装的 node/npm；上游脚本使用 bun，本集成不依赖 bun。

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
