# Skill Finder — AI 项目趋势追踪站

一个公开网站，每天抓取 GitHub Trending 日/周/月榜单，过滤出 AI Agent、Skill、MCP、插件等 AI 相关项目，每期取 Star 增长 Top 10，展示真实的 1 日、7 日、30 日 Star 增长排行与 30 天趋势。

- **后端**：Python 3.11+、FastAPI、SQLAlchemy 2（异步）、asyncmy、MySQL、APScheduler、HTTPX、Scrapling
- **前端**：Vue 3、TypeScript、Vite、Pinia、Vue Router、Axios
- **测试**：pytest / pytest-asyncio / respx、Vitest / Vue Test Utils、Playwright

## 在 love5000 中的接入方式

- 独立微服务，**不是** Java Maven 模块，不加入父 `pom.xml` 的 `<modules>`。
- 默认端口 `5177`，`GET /api/health` 返回 `{"success": true, "service": "skill-finder"}`。
- 前端 `frontend/dist` 由后端同端口托管：`/assets` 挂载构建资源，其余非 `api/` 路径做 SPA fallback。
- 只由 `website` 首页 Dock“Skill Finder”卡片点击启动：
  - `POST http://127.0.0.1:8080/api/services/skill-finder/start`
  - `GET  http://127.0.0.1:8080/api/services/skill-finder/status`
- 不随 `website` 启动自动拉起，`website` 关闭也不强杀；重复点击复用已有进程。
- Java 启动器（`website` 的 `integration/skillfinder` 包）优先使用 `backend/.venv/Scripts/python.exe`，缺失时回退 `uv run python`；启动前要求 `frontend/dist/index.html` 已构建。
- 数据库与 `website` 共用腾讯云 MySQL 实例上的 `xixi` 库，建表脚本见 `backend/sql/schema.sql`。

## 功能

- 每日用 Scrapling 抓取 `github.com/trending` 的日/周/月榜，AI 关键词过滤后每期取 Top 10（默认，可配置）
- 按 1 日增量、7 日增量、30 日增量、总 Star 排序
- 分类（Agent / Skill / MCP / 插件）、语言、最低 Star、关键词组合筛选
- 仓库详情页：分类依据、Topics、30 天 Star 趋势图
- 主页一键“刷新数据”：手动触发采集，完成后自动刷新榜单（30 分钟冷却防滥用）
- 近 30 天最热：基于 last30days 多源研究的 Agent / Skill 方向 Top 20 榜单（手动刷新 + 结果缓存）
- 电影化趋势主页：非对称 Hero、浮动榜单卡片、横向手风琴分类、bento 榜单网格、固定分栏“增长最快”、信号轮播与巨型 CTA 页脚
- 明暗主题、响应式布局、键盘与无障碍支持
- 手动触发采集接口，MySQL 命名锁防并发

前端动效使用本地 `gsap` + `ScrollTrigger`（npm 依赖），对 `prefers-reduced-motion`、WebGL 不可用和脚本缺失提供静态降级；仓库封面使用 GitHub 官方 OpenGraph 预览卡（含名称、描述、头像与 Star 数），加载失败时回退 `picsum.photos` 种子图；信号轮播使用项目所有者头像。Vite dev 模式默认把 `/api` 代理到 `http://127.0.0.1:5177`，可用 `VITE_PROXY_TARGET` 覆盖。

## 环境准备

后端（Python 3.11+，推荐 uv）：

```bash
cd website/skill-finder/backend
uv sync
```

也可以使用标准 venv + pip 安装 `pyproject.toml` 依赖。依赖包含 `cryptography`，用于 MySQL `caching_sha2_password` / `sha256_password` 的 RSA 认证；缺失时重新执行 `uv sync`。

前端（Node.js 18+）：

```bash
cd website/skill-finder/frontend
npm install
npm run build
```

`frontend/dist` 是启动前置条件，未构建时启动接口返回“前端尚未构建”错误。

数据库默认直接读取 `website/src/main/resources/application.yml` 的 `spring.datasource`，并解析 `WEBSITE_DB_URL` / `WEBSITE_DB_USERNAME` / `WEBSITE_DB_PASSWORD`；JDBC URL 转换为 `mysql+asyncmy` 连接串，字符集使用 utf8mb4，凭据自动 URL 编码，不打印或复制到文件。无需另建数据库 `.env`。显式 `DATABASE_URL` 环境变量或 `backend/.env` 配置优先于共享数据源。

如需独立覆盖数据库或其他设置，可配置 `backend/.env`（本地私有文件，已被 `.gitignore` 排除，禁止提交）：

```dotenv
DATABASE_URL=mysql+asyncmy://YOUR_USERNAME_HERE:YOUR_PASSWORD_HERE@49.232.128.132:3306/xixi?charset=utf8mb4
ADMIN_KEY=replace_with_a_long_random_value
BUSINESS_TIMEZONE=Asia/Shanghai
COLLECTION_CRON=0 2 * * *
SCHEDULER_ENABLED=false
```

GitHub Token 保存在 `backend/.secrets/github_token`（单行、无换行，已被 `.gitignore` 排除），也可通过环境变量 `GITHUB_TOKEN` 提供，文件优先级更高。若本机访问 `github.com` 需要代理，在 `.env` 中设置 `TRENDING_PROXY`。

## 手动启动

```bash
cd website/skill-finder/backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 5177
```

访问 http://127.0.0.1:5177/ 。日常联调直接启动 `website` 后点击首页卡片即可。

## API

统一前缀 `/api/v1`，统一错误响应 `{ "code", "message", "request_id" }`。

| 接口 | 说明 |
| --- | --- |
| `GET /api/health` | 统一健康检查（`success=true` + `service=skill-finder`） |
| `GET /api/v1/health` | 应用状态 |
| `GET /api/v1/repositories` | 排行榜，支持 `page`、`page_size`、`sort`（`daily_stars` / `weekly_stars` / `monthly_stars` / `total_stars`）、`category`（`AGENT` / `SKILL` / `MCP` / `PLUGIN`）、`language`、`min_stars`、`q` |
| `GET /api/v1/repositories/{owner}/{name}` | 仓库详情 + 30 天趋势 |
| `GET /api/v1/languages` | 可筛选语言及仓库数 |
| `GET /api/v1/stats` | 统计信息 |
| `POST /api/v1/collections/refresh` | 手动触发采集（公开，30 分钟冷却；采集中重复触发返回 409） |
| `GET /api/v1/last30days/rankings?direction=agent\|skill` | 近 30 天最热榜单缓存（Agent / Skill 方向 Top 20） |
| `POST /api/v1/last30days/rankings/refresh` | 手动刷新指定方向榜单（同步执行，可能需要几分钟） |
| `GET /api/v1/last30days/status` | last30days 引擎诊断与可用来源 |
| `POST /api/v1/last30days` | 自由主题研究（调试用，页面不再使用） |
| `POST /api/v1/admin/collections` | 手动触发采集（需 `X-Admin-Key`） |

> 首次接入 `xixi` 时，按 `backend/sql/schema.sql` 仅补建缺失的 `collection_runs`、`last30days_reports`、`repositories`、`star_snapshots`、`trending_entries` 五张业务表，不删除或重建已有表。已有同名表应先核对结构。

原 `skill_finder` 库的这五张表数据已复制到 `xixi`，保留原始 ID、关联关系和缓存内容，源库保留；后续运行与采集写入 `xixi`。

## 运行测试

后端：

```bash
cd website/skill-finder/backend
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m pytest -q
```

> **警告**：MySQL 集成测试的 fixture 会 **DROP 并重建业务数据表**。必须使用**独立测试库**，严禁指向运行库 `xixi`。
>
> 先创建测试库并执行建表脚本，再设置 `TEST_DATABASE_URL`：
>
> ```powershell
> mysql -u root -p -e "CREATE DATABASE skill_finder_test CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
> Get-Content backend/sql/schema.sql -Raw | mysql -u root -p skill_finder_test
> $env:TEST_DATABASE_URL = "mysql+asyncmy://user:pass@127.0.0.1:3306/skill_finder_test?charset=utf8mb4"
> .\.venv\Scripts\python.exe -m pytest tests/integration -q
> ```
>
> 未设置 `TEST_DATABASE_URL` 时集成测试明确跳过，不触碰任何数据库。

前端：

```bash
cd website/skill-finder/frontend
npm run lint
npm run typecheck
npm run test -- --run
npm run build
npm run test:e2e   # 需要先安装 Chromium：npx playwright install chromium
```

## 采集任务

默认每天北京时间 02:00 自动采集（`COLLECTION_CRON=0 2 * * *`，`SCHEDULER_ENABLED=false` 时关闭）。每次采集流程：

1. 用 Scrapling 抓取 `github.com/trending?since=daily|weekly|monthly` 三张榜（支持 `TRENDING_PROXY`）。
2. 按 `TRENDING_AI_KEYWORDS` 过滤（不区分大小写、按词边界匹配名称与描述）。
3. 每期按期内涨星降序取前 `TRENDING_TOP_N`（默认 10），三张榜合并去重。
4. 用 GitHub API 逐个补全 github_id、topics、forks 等字段（每期约 10 个请求，token 消耗很小）。
5. 写入 `repositories`、当日 `star_snapshots` 与 `trending_entries`；某期抓取失败时保留该期旧数据并标记任务为 `PARTIAL`。

自动与手动任务共享同一把 MySQL 命名锁，并发触发只执行一个任务。掉出榜单的仓库仍保留在列表底部（增量显示 `--`），按总 Star 排序时仍可查看。

## 目录结构

```text
website/skill-finder/
├── backend/            FastAPI 后端（Trending 采集、趋势计算、REST API、dist 托管）
│   ├── app/            应用源码
│   ├── sql/            MySQL 建表与迁移脚本
│   ├── tests/          pytest 测试（unit + integration）
│   ├── .env            本地私有配置，禁止提交
│   ├── .secrets/       GitHub Token，禁止提交
│   └── pyproject.toml / uv.lock
├── frontend/           Vue 3 前端（排行榜、筛选、详情）
│   ├── src/
│   ├── tests/unit/     Vitest 单元测试
│   ├── tests/e2e/      Playwright 端到端测试
│   └── dist/           npm run build 产物，gitignored
├── db/                 早期建表 SQL 参考
└── docs/               设计说明与实施计划
```

## 安全说明

- 所有密钥仅通过 `.env` / `.secrets/` / 环境变量读取，且均已被 `.gitignore` 排除，不提交版本库
- 源码与日志中的凭据均已脱敏
- 前端不持有 GitHub Token 或管理密钥

## Skill Finder 云端日报与视频

日报视频现已接入内部 `video-renderer/`（Remotion 4.0.536 + React/TypeScript + Node.js 22+），默认 1080×1920 / 30 FPS；配音默认 MiMo，`MIMO_API_KEY` 仅在私有环境配置，字幕通过实际音轨转写。新增 `DAILY_VIDEO_RENDERER`、`DAILY_TTS_PROVIDER`、`DAILY_NODE_COMMAND`、`DAILY_WHISPER_MODEL`、`DAILY_ASSETS_DIR` 与素材完整性检查；`legacy` 可显式回退。先安装渲染依赖和 `uv sync --extra captions`，样片用 `python -m app.daily.cli sample`。详细配置、数据目录、测试和 Docker 资源要求见 [docs/remotion-integration.md](docs/remotion-integration.md)。既有 API、端口、Vue 页面与审核发布约定不变。

后续视频制作目标为“快节奏工具推荐”：短句讲清用途和效果，真实演示配合动态编排，
自然中文配音、按真实时间戳同步的字幕和混音，正式目标 1080×1920 / 30 FPS。
详见 [视频制作与验收规范](docs/video-production-standard.md)。
Remotion 与 MiMo TTS 已接入，旧 Pillow + Edge TTS 路径保留为显式 legacy 回退。
配音风格、素材质量和镜头节奏仍先通过约 30 秒真实项目样片确认，不把技术接通等同质量验收。

`website/skill-finder` 继续作为独立 FastAPI + Vue 微服务，以 love5000 版本为准同步到 `C:/Code/skills-finder`。云端采用 Docker + Nginx，入口 `https://49.232.128.132/skill-finder/`，日报审核 `/skill-finder/daily-reports`，后端仅监听回环 15177，本机开发仍用 5177。复用 xixi 原五张业务表，不重建共享库。

服务器北京时间 07:10 采集、07:30 制作（07:45 重试）、08:00 送达；当前 QQ 按用户要求暂不配置。成品包括文字日报、中文配音、字幕与竖屏视频，GitHub 当日 AI 项目不足十项时如实标注。DeepSeek 使用通用 `INTRO_API_KEY`、`INTRO_API_BASE`、`INTRO_MODEL` 私有配置，不把凭据写入 Git。

新增 API 前缀 `/api/v1/daily-reports`：GET 列表、GET `/{date}`、GET `/{date}/files/{filename}`；管理接口 POST `/generate`、POST `/{date}/review`、POST `/{date}/publish`；抖音登录 POST/GET `/publisher/login` 和受认证的 GET `/publisher/login/screen`。管理接口要求 X-Admin-Key，并只允许 HTTPS 或本机 SSH 隧道。发布必须绑定具体视频、口播和文案的人工批准；未登录不发布，结果不确定不自动重发。

`backend/app/daily/` 管理生成、媒体、审核摘要与发布适配；`backend/data/`、`.secrets/`、云端 `/var/lib/skill-finder/` 为私有运行数据，不提交。`deploy/` 维护 Docker、cron、Nginx 与 IP 证书续签；OpenClaw 在独立 Node 容器内仅监听回环 18789，QQ/抖音必须如实区分未配置、等待登录与已送达/已发布。完整部署、凭据边界与验证见 `website/skill-finder/docs/cloud-daily-report.md`（模块内为 `docs/cloud-daily-report.md`）。本机首页点击启动约定保持不变。


## 视频制作操作台

`/daily-reports` 现为一键制作操作台：展示采集、筛选、脚本、素材、配音、字幕、渲染、审核、抖音发布与可选 QQ 通知。真实状态每 5 秒刷新，任务目录中的 `workflow.json` 保存步骤、计数、时间与脱敏错误，`render-progress.json` 保存实际渲染帧数；历史任务无记录时明确标注，不补造进度。素材可从页面上传（MP4/PNG/JPEG，最大 100 MiB，有 HTTPS 来源），只允许本期项目，生成后使用固化副本。新增 GET `/api/v1/daily-reports/console?day=YYYY-MM-DD`、PUT `/{day}/assets/{owner}/{repo}?filename=...&source=...`（原始文件请求体）、POST `/{day}/notify` 与只读样片文件入口 `/samples/{id}/files/{filename}`（均位于 daily-reports 前缀下）；管理写操作继续使用 X-Admin-Key + HTTPS/本机连接，已进入审核的版本不可被一键运行覆盖。操作台“模板编辑”已内置 React/TSX 源码编辑、可视化样式、Remotion Player、编译错误定位、保存启用与版本恢复，入口为 `/daily-reports?panel=template`，无需另开 Studio。仅允许编辑 `src/video.tsx`、`src/demo.tsx`、`src/types.ts`；`root.tsx` 只读。新增 `/api/v1/daily-reports/template` 的 GET/PUT、POST `/preview`、POST `/restore`，源码与编译使用现有管理鉴权。保存前通过类型检查、打包和一帧真实渲染，版本原子切换；新版本只影响后续生成，已有成片和审核不变。不可变源码、样式与预览缓存位于日报目录同级 `video-template/`（默认 `backend/data/video-template/`），使用现有数据持久卷与 5177 端口。完整使用、API 和验证说明见 [操作台说明](docs/production-console.md)。
