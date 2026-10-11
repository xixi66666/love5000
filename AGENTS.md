# AGENTS.md

## 统一服务健康检查

五个独立服务 `lovestory`、`imagetemplate`、`python-a`、`quant-a`、`scrapling-ui`
均提供 `GET /api/health`，响应顶层必须包含布尔值 `success=true` 和稳定的 `service`
标识。`website` 使用 `ServiceHealthChecker` 统一探测，并通过
`GET /api/services/health` 并行返回配置顺序一致的聚合结果；HTTP 200 表示聚合执行成功，
顶层 `healthy` 表示是否所有服务均在线。连接/读取超时默认分别为 2000/3000ms。

## 项目概述

`love5000` 是一个 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目，父工程 artifactId 为 `love530`。当前模块：

- `common`：公共能力模块，提供 OSS 自动配置、上传工具，以及通用登录/注册/Session 鉴权能力。
- `lovestory`：恋爱相册 Web 应用，提供静态页面、照片上传、照片列表、删除接口、留言板功能和吉他视频卡片模块。
- `website`：个人主页/展示站点 Web 应用，包含主页静态资源、Web Demo、OSS Demo、Nacos Discovery 示例和提示词控制台入口。
- `imagetemplate`：图片提示词模板 Web 服务，聚合 47 条精选模板和 Prompt Console 的 4409 条公开提示词，总计 4456 条，按 15 个一级功能与二级场景导航，提供分页检索、按需详情、prompt 渲染、直接提示词和 OpenAI 图片生成能力；前端采用虎主题编辑式黑色工作台、橙色高对比操作、本地 GSAP 动效和 dense 结果网格。
- `python-a`：A 股自选股 AI 研究台，作为独立 Python 微应用接入，不加入 Maven 聚合模块。
- `quant-a`：A 股量化研究台，作为独立 FastAPI 微服务接入，不加入 Maven 聚合模块，不写入 `website/python-a` 的 Obsidian 目录。
- `scrapling-ui`：基于 Scrapling + Playwright 的可视化爬虫工作台（汉化版），作为独立 FastAPI + React 微服务接入，不加入 Maven 聚合模块；`website` 首页 Dock 卡片点击启动，不随 `website` 自动拉起。

核心技术栈：

- 语言：Java 8
- 构建工具：Maven
- 后端框架：Spring Boot 2.6.13
- Web：Spring MVC / Spring Boot Starter Web
- 数据库：MySQL
- 数据访问：MyBatis DAO + XML Mapper
- 连接池：Alibaba Druid
- 对象存储：Aliyun OSS SDK
- 图片生成：OpenAI Images API
- Python 微应用：Python 3.9+ / ThreadingHTTPServer / FastAPI / Uvicorn / DeepSeek Chat Completions API / 东方财富公开行情接口 / Obsidian Markdown
- 测试：JUnit 5 + Spring Boot Test + Maven Surefire 2.22.2
- 前端：原生 HTML / CSS / JavaScript

**关键**：根目录 `pom.xml` 只负责模块聚合、公共版本和依赖管理。业务代码必须放在对应模块内；跨模块公共能力优先放入 `common`。

**关键**：`website/python-a` 是独立 Python 微应用，不是 Java Maven 模块，不要把它加入父 `pom.xml` 的 `<modules>`。Java 侧只负责入口链接、反向代理或接口转发，不把 Python 业务逻辑改写进 Controller。

**关键**：`quant-a` 是独立 FastAPI 微服务，不是 Java Maven 模块，不要把它加入父 `pom.xml` 的 `<modules>`。它的数据、配置和测试保持在 `website/quant-a/` 内，不写入 `website/python-a/obsidian-vault/`。

**关键**：`scrapling-ui` 是独立 FastAPI + React 微服务，不是 Java Maven 模块，不要把它加入父 `pom.xml` 的 `<modules>`。它只由 `website` 首页 Dock 的“Scrapling 抓取工坊”卡片点击启动（`POST /api/services/scrapling-ui/start`），不随 `website` 启动自动拉起，`website` 关闭也不强杀；`website` 只提供启动接口、健康检测和入口链接，不把抓取业务逻辑改写进 Java Controller。

**关键**：每次修改项目结构、模块职责、启动命令、端口、配置项、API、数据目录、测试方式或部署入口时，必须同步更新根 `AGENTS.md` / `README.md`，以及受影响模块或微应用目录下的 `AGENTS.md` / `README.md`。文档和代码不一致时，本次改动不能视为完成。

## 开发命令

默认从仓库根目录执行：

```bash
cd C:/Code/Java_Code/love5000
```

安装/编译全部模块：

```bash
mvn clean install
```

运行全部测试：

```bash
mvn test
```

跳过测试打包：

```bash
mvn clean package -DskipTests
```

按模块运行测试：

```bash
mvn -pl common test
mvn -pl lovestory -am test
mvn -pl website -am test
mvn -pl imagetemplate -am test
```

启动 `lovestory`，默认端口 `8081`：

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
```

启动 `website`，默认端口 `8080`：

```bash
mvn -pl website -am spring-boot:run
```

`website` 启动时会默认自动检查并启动 `python-a` 和 `quant-a`。如果本机对应健康检查已可用，则直接复用已有服务，不重复启动。两个 Python 子服务默认把 stdout/stderr 输出到 `website` 的同一个控制台，便于在 IDEA Run/Terminal 中直接查看运行日志和接口访问日志。`scrapling-ui` 不随 `website` 自动拉起，只由首页 Dock“Scrapling 抓取工坊”卡片点击启动。

启动 `imagetemplate`，默认端口 `8082`：

```bash
mvn -pl imagetemplate -am spring-boot:run
```

带 OpenAI Key 启动 `imagetemplate`：

```bash
set OPENAI_API_KEY=sk-your-key
mvn -pl imagetemplate -am spring-boot:run
```

启动 `python-a`，默认端口 `5174`：

```bash
cd website/python-a
npm run start
```

也可以直接启动 Python 服务：

```bash
cd website/python-a
python server.py
```

指定端口启动：

```bash
cd website/python-a
set PORT=5174
python server.py
```

配置 DeepSeek Key 后启动：

```bash
cd website/python-a
set DEEPSEEK_API_KEY=your-key
python server.py
```

启动 `quant-a`，默认端口 `5175`：

```bash
cd website/quant-a
python -m uvicorn main:app --host 127.0.0.1 --port 5175
```

运行 `quant-a` 测试：

```bash
cd website/quant-a
python -m pytest
```

首次准备 `scrapling-ui` 环境（Python 3.14 由 uv 管理，浏览器约 112MB）：

```bash
cd website/scrapling-ui/backend
uv sync
uv run playwright install chromium

cd website/scrapling-ui/frontend
npm install
npm run build
```

单独启动 `scrapling-ui`（前端已构建后），默认端口 `5176`：

```bash
cd website/scrapling-ui/backend
.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 5176
```

运行 `scrapling-ui` 测试：

```bash
cd website/scrapling-ui/backend
uv run python -m unittest discover -s tests -v
```

日常本地联调直接启动 `website`：它会自动检查并拉起 `python-a` 和 `quant-a`；`scrapling-ui` 由首页按钮点击启动，首次使用前完成一次上面的环境准备即可。

## 项目结构

```text
love5000/
├── pom.xml
├── AGENTS.md
├── common/
│   ├── AGENTS.md
│   └── src/main/java/com/example/common/
├── lovestory/
│   ├── AGENTS.md
│   └── src/main/
├── website/
│   ├── AGENTS.md
│   └── src/main/
├── imagetemplate/
│   ├── AGENTS.md
│   └── src/
│       ├── main/java/com/example/imagetemplate/
│       │   ├── controller/
│       │   ├── dto/
│       │   ├── model/
│       │   └── service/
│       └── main/resources/
│           ├── application.yml
│           ├── static/
│           │   ├── index.html
│       │           ├── css/app.css
│           │           └── js/app.js
│           └── templates/image-prompt-templates.json
├── website/python-a/
    ├── README.md
    ├── package.json
    ├── server.py
    ├── index.html
    ├── app.js
    ├── styles.css
    └── obsidian-vault/
└── website/quant-a/
    ├── main.py
    ├── requirements.txt
    ├── configs/
    ├── quant/
    ├── tests/
    └── web/
├── website/scrapling-ui/
    ├── README.md
    ├── backend/            # FastAPI + Playwright（Python 3.14，uv 管理）
    │   ├── main.py
    │   ├── core/
    │   ├── services/
    │   └── tests/
    └── frontend/           # React + TypeScript + Vite（已汉化）
        ├── src/
        └── dist/           # npm run build 产物，gitignored
```

`python-a` 不参与 Maven 构建，下面结构只表示其独立应用边界：

```text
website/python-a/
    ├── README.md
    ├── package.json
    ├── server.py
    ├── index.html
    ├── app.js
    ├── styles.css
    ├── deepseek.local.json      # 本地私有配置，禁止提交
    └── obsidian-vault/A股AI/
```

`quant-a` 不参与 Maven 构建，下面结构只表示其独立 FastAPI 微服务边界：

```text
website/quant-a/
    ├── main.py
    ├── requirements.txt
    ├── configs/
    ├── quant/
    │   ├── api/
    │   ├── backtest/
    │   ├── factors/
    │   ├── portfolio/
    │   ├── providers/
    │   └── services/
    ├── tests/
    └── web/
```

`scrapling-ui` 不参与 Maven 构建，下面结构只表示其独立 FastAPI + React 微服务边界：

```text
website/scrapling-ui/
    ├── README.md
    ├── todo_list.md             # 工作台路线图面板读写
    ├── backend/                 # FastAPI + Playwright（Python 3.14，uv 管理）
    │   ├── main.py              # API + /api/health + 前端 dist 静态托管
    │   ├── models.py
    │   ├── core/                # 浏览器管理、会话、DOM 提取、SQLite
    │   ├── services/            # 代码生成、代码执行、调度器、AI 修复
    │   ├── tests/               # unittest 健康与静态托管测试
    │   ├── pyproject.toml / uv.lock
    │   └── jobs.db              # 运行时 SQLite，禁止提交
    └── frontend/                # React + TypeScript + Vite（已汉化）
        ├── src/
        ├── public/
        ├── dist/                # npm run build 产物，gitignored
        └── package.json / package-lock.json
```

## 模块职责

- `common/src/main/java/com/example/common/config`：公共配置和自动装配，例如 OSS 自动配置。
- `common/src/main/java/com/example/common/util`：公共工具类，例如 `OssUtil`；预声明对象键上传必须先通过其格式校验。
- `common/src/main/java/com/example/common/auth`：公共认证能力，包含 BCrypt 密码哈希、Session 登录状态、`/api/auth` 控制器、`@AuthRequired` 和拦截器。
- `lovestory/controller`：恋爱相册 REST API，照片接口集中在 `/api/photos`，留言接口集中在 `/api/messages`，吉他视频接口集中在 `/api/guitar-videos`。
- `lovestory/dao`：MyBatis DAO 接口层，照片表访问集中在 `PhotoDao`，吉他视频表访问集中在 `GuitarVideoDao`。
- `lovestory/service`：业务逻辑层，吉他视频上传、封面上传、OSS 删除和响应组装集中在 `GuitarVideoService` / `GuitarVideoServiceImpl`。
- `lovestory/src/main/resources/mapper`：MyBatis XML Mapper，SQL 写在这里。
- `lovestory/src/main/resources/static`：恋爱相册、小游戏、留言板、照片墙和吉他视频卡片静态页面。
- `website/src/main/resources/static/prompt-console`：静态提示词库页面、两级分类交互和服务端数据接入。页面采用深色影院式设计：置顶玻璃胶囊导航、全出血电影化 Hero、capabilities 无缝 Bento、两级分类 bento、无限跑马灯与巨型 CTA 页脚；动效集中在 `prompt-console-motion.js`（GSAP + ScrollTrigger，本地 `js/vendor/gsap.min.js` 与 `js/vendor/ScrollTrigger.min.js` 均为 3.12.5），`prefers-reduced-motion` 或脚本缺失时自动降级为静态布局与 CSS 动画。数据通过 `/api/prompts` 系列接口从 MySQL 读取（服务端分页/搜索），不再直接 fetch 本地 JSON；`prompt-category-groups.js` 保留为导入工具与 node 测试的“大分类 -> 小分类”映射数据源，页面运行时不依赖它。
- `website/demos`：示例性质的 Web、OSS、Nacos Discovery 代码。
- `imagetemplate/controller`：图片模板 API。
- `imagetemplate/service`：精选模板加载、大库加载适配、两级功能分类、聚合分页、prompt 渲染和 OpenAI 图片生成服务；功能规则集中在 `TemplateFunctionClassifier`，不扫描完整 Prompt。
- `imagetemplate/src/main/resources/templates/image-prompt-templates.json`：47 条精选图片模板数据源。
- `website/src/main/resources/static/prompt-console/data/prompt-library.json`：4409 条 Prompt Console 大库唯一源码；Maven 构建 imagetemplate 时复制到 classpath 的 `templates/prompt-console/prompt-library.json`，同时是 MySQL 导入（`prompt_entry/prompt_source/prompt_group` 三张表）的数据来源。
- `website/src/main/java/com/example/website/prompt/library`：提示词库服务端化代码。`PromptLibraryController` 暴露 `/api/prompts` 系列接口（含 `POST /api/prompts` 手动添加）；`PromptLibraryServiceImpl` 负责 meta 组装、分页搜索、LIKE 转义、详情映射和添加校验/大分类推导；`PromptLibraryDao` + `mapper/prompt/PromptLibraryMapper.xml` 访问 MySQL 的 `prompt_entry`、`prompt_source`、`prompt_group` 表。
- `imagetemplate/src/main/resources/static`：图片模板库编辑式黑色 AI 创作单页前端，使用本地虎主题背景、宽幅分屏首屏、内嵌图像标题、橙色高对比操作和三段横向交互面板；按“灵感大厅 → 模板解构 → Prompt 编导台 → 图片生成舱”组织。灵感大厅顶部常驻搜索、仅图片开关、结果计数和清除筛选，左侧展示两级功能及高级筛选，右侧为默认 48 条的 dense 密排结果网格；本地 GSAP 3.13.0 与 ScrollTrigger 提供渐进增强动效，并保留脚本缺失和 `prefers-reduced-motion` 静态降级。模板解构 JSON 与编导台变量允许手工编辑，JSON 在进入编导台前校验并同步；流程导航只切换场景、不清空用户状态。
- `website/python-a/server.py`：Python 微应用后端，负责静态页面服务、东方财富行情网关、DeepSeek 调用和 Obsidian 写入。
- `website/python-a/services/stock_metadata_service.py`：股票行业、板块和概念元数据缓存与降级读取。
- `website/python-a/services/knowledge_graph_service.py`：Obsidian 知识图谱节点、复盘双链和风险模式链接生成。
- `website/python-a/index.html`、`website/python-a/app.js`、`website/python-a/styles.css`：A 股自选股 AI 研究台前端页面、交互和样式。
- `website/python-a/obsidian-vault/A股AI`：Python 微应用默认写入的 Obsidian 研究记录和自选股数据目录。
- `website/quant-a/main.py`：Quant FastAPI 应用入口，挂载前端静态资源并注册 `/api/**` 路由。
- `website/quant-a/quant`：量化研究核心代码，包含 API、因子、回测、组合、行情提供方、服务编排和存储。
- `website/quant-a/tests`：Quant 微服务测试，使用 pytest 和 FastAPI TestClient。
- `website/quant-a/web`：Quant 研究台前端页面和静态资源。
- `website/scrapling-ui/backend/main.py`：可视化爬虫工作台后端入口，注册抓取会话、选择器、代码生成/执行、调度、路线图和 AI 修复 API，并提供 `/api/health` 与 `frontend/dist` 静态托管（SPA fallback）。
- `website/scrapling-ui/backend/core`：Playwright 浏览器管理、会话与历史回放、DOM 提取脚本和 SQLite 访问。
- `website/scrapling-ui/backend/services`：配方代码生成、代码执行、APScheduler 调度和 DeepSeek 选择器修复。
- `website/scrapling-ui/backend/tests`：unittest 测试，覆盖 `/api/health`、`/api/**` 404 和 dist 静态托管。
- `website/scrapling-ui/frontend`：已汉化的 React + TypeScript + Vite 工作台前端；`dist` 为 `npm run build` 产物，由后端同端口托管。
- `website/src/main/java/com/example/website/integration/scrapling`：`ScraplingUiProcessManager` + `ScraplingUiController`，提供点击启动与状态接口；优先 `backend/.venv`，回退 `uv run python`，等待健康默认 90s，不做启动时自动拉起。

## Python 微应用入口方式

`python-a` 以独立服务方式接入 `love5000`：

- 本地开发入口：启动 `python-a` 后访问 `http://127.0.0.1:5174/`。
- 健康检查入口：`GET http://127.0.0.1:5174/api/health`。
- `website` 内置 `PythonAAutoStartRunner`，默认配置为 `python-a.auto-start.enabled=true`。直接启动 `website` 时会自动拉起 `python-a`。
- `website` 内置 `QuantAAutoStartRunner`，默认配置为 `quant-a.auto-start.enabled=true`。直接启动 `website` 时会自动拉起或复用 `quant-a`。
- `website` 如需提供统一首页入口，只添加跳转链接，例如“ A 股自选股 AI 研究台 -> http://127.0.0.1:5174/ ”。
- 生产部署如需统一域名，使用 Nginx、网关或 Spring 反向代理把 `/python-a/` 转发到 `127.0.0.1:5174`。
- `python-a` 的 `/api/**` 默认由 Python 服务自己处理。没有明确需求时，不要在 Java Controller 中重复实现这些接口。
- `python-a` 不是 Maven 模块，不执行 `mvn -pl python-a ...`。

## Quant 微服务入口方式

`quant-a` 以独立 FastAPI 服务方式接入 `love5000`：

- 直接启动 `website` 时会默认自动检查并启动 `quant-a`。如果本机 `http://127.0.0.1:5175/api/health` 已可用，则直接复用已有 Quant 服务，不重复启动。
- 本地开发入口：启动 `quant-a` 后访问 `http://127.0.0.1:5175/`。
- 健康检查入口：`GET http://127.0.0.1:5175/api/health`，响应中的 `success` 必须为 `true`。
- 推荐命令：`python -m uvicorn main:app --host 127.0.0.1 --port 5175`，工作目录为 `website/quant-a/`。
- `website` 只提供入口链接和健康检测，不把 `quant-a` 业务逻辑改写进 Java Controller。
- 生产部署如需统一域名，使用 Nginx、网关或 Spring 反向代理把 `/quant-a/` 转发到 `127.0.0.1:5175`。
- `quant-a` 的 `/api/**` 默认由 FastAPI 服务自己处理。没有明确需求时，不要在 Java Controller 中重复实现这些接口。
- `quant-a` 不是 Maven 模块，不执行 `mvn -pl quant-a ...`，也不要写入 `website/python-a/obsidian-vault/`。

## Scrapling UI 微服务入口方式

`scrapling-ui` 以独立 FastAPI + React 服务方式接入 `love5000`：

- 只由 `website` 首页 Dock“Scrapling 抓取工坊”卡片点击启动，**不随** `website` 启动自动拉起，`website` 关闭也不强杀。
- 启动接口：`POST http://127.0.0.1:8080/api/services/scrapling-ui/start`，返回 `{success, status, url}`；`status` 为 `started` 或 `already-running`。
- 状态接口：`GET http://127.0.0.1:8080/api/services/scrapling-ui/status`。
- 本地开发入口：启动后访问 `http://127.0.0.1:5176/`。
- 健康检查入口：`GET http://127.0.0.1:5176/api/health`，响应中的 `success` 必须为 `true`。
- 前端构建产物由后端同端口托管，运行时只有一个进程；首次使用需完成 `uv sync`、`playwright install chromium`、`npm install && npm run build`。
- `website` 只提供启动接口、健康检测和入口链接，不把抓取业务逻辑改写进 Java Controller。
- 生产部署如需统一域名，使用 Nginx、网关或 Spring 反向代理把 `/scrapling-ui/` 转发到 `127.0.0.1:5176`。
- `scrapling-ui` 不是 Maven 模块，不执行 `mvn -pl scrapling-ui ...`；数据目录为其自身 `backend/jobs.db`，不写入其他微服务目录。

## 微服务主页入口约定

- 新增任何 Java 模块、Python 微应用或独立微服务时，必须同步更新 `website/src/main/resources/static/index.html` 的主页面入口。
- 当前主页面采用四场景电影化单视口布局，服务入口位于底部液态玻璃 Dock；新增入口时沿用现有 `service-card` 结构，并验证桌面宽度和移动端横向滚动。
- 主页面入口需要包含服务名称、端口或访问标识，并配置实时可用性检测地址。
- 入口样式和状态点维护在 `website/src/main/resources/static/css/style.css`，健康检测逻辑维护在 `website/src/main/resources/static/js/script.js`。
- 如果新增服务没有专门健康检查接口，优先使用其首页或登录页作为检测地址；跨端口检测可使用前端 `no-cors` 方式，只把网络失败视为不可用。
- 顶部导航只保留登录、注册账户操作；登录成功后切换为退出。新增服务入口只加入底部服务 Dock，不在顶部增加按钮或汉堡菜单。

## 配置约定

### 端口

- `website`：`8080`
- `lovestory`：`8081`
- `imagetemplate`：`8082`
- `python-a`：`5174`
- `quant-a`：`5175`
- `scrapling-ui`：`5176`

### 数据库

- `lovestory` 使用 MySQL 数据库 `lovestory`。
- `website` 使用 MySQL 数据库 `xixi`（腾讯云远程库，默认地址为 `jdbc:mysql://49.232.128.132:3306/xixi`），包含 `prompt_entry`、`prompt_source`、`prompt_group`、`auth_user` 等表。
- `imagetemplate` 不使用数据库。
- `python-a` 不使用 MySQL；默认写入本地 `website/python-a/obsidian-vault/A股AI/`。
- `quant-a` 不使用 MySQL；默认使用 `website/quant-a/` 内部数据、配置和存储目录，不写入 `website/python-a` 的 Obsidian 目录。
- `scrapling-ui` 不使用 MySQL；运行时数据只有自身 `backend/jobs.db`（SQLite，调度任务）和项目根 `todo_list.md`（路线图），不写入其他微服务目录。

⚠️ **严重警告**：不要提交真实数据库密码、OSS AccessKey、OpenAI API Key。新增配置优先使用环境变量，例如 `${OPENAI_API_KEY:}`、`${LOVE530_OSS_ACCESS_KEY_ID:}`。

`lovestory` 数据库连接通过 `LOVESTORY_DB_URL`、`LOVESTORY_DB_USERNAME`、`LOVESTORY_DB_PASSWORD` 覆盖；默认仅指向本机 `lovestory` 数据库。`website` 使用 `WEBSITE_DB_URL`、`WEBSITE_DB_USERNAME`、`WEBSITE_DB_PASSWORD`，默认指向腾讯云 `xixi` 库（JDBC 使用 `characterEncoding=UTF-8`，Connector/J 8 会自动映射 utf8mb4）。密码必须走环境变量，禁止提交真实密码。OSS 默认关闭，只有显式设置 `LOVE530_OSS_ENABLED=true` 并提供 `LOVE530_OSS_*` 凭据后才启用。

### MyBatis

使用数据库的 Web 模块必须显式配置：

```yaml
mybatis:
  mapper-locations: classpath*:mapper/**/*.xml
  configuration:
    map-underscore-to-camel-case: true
```

数据库 CRUD 使用 DAO + XML Mapper。不要新增 `JdbcTemplate`、JPA Repository 或 Java 内联 SQL。

### OpenAI

`imagetemplate` 使用以下配置：

```yaml
openai:
  api-key: ${OPENAI_API_KEY:}
  base-url: ${OPENAI_BASE_URL:https://api.openai.com/v1}
  image-model: ${OPENAI_IMAGE_MODEL:gpt-image-2.5-sunburst}
  connect-timeout-ms: ${OPENAI_CONNECT_TIMEOUT_MS:30000}
  read-timeout-ms: ${OPENAI_READ_TIMEOUT_MS:180000}
```

`imagetemplate` 默认使用 OpenAI `gpt-image-2.5-sunburst`（GPT Image 2.5 质量优先模型；另有快速模型 `gpt-image-2.5-flare`，可用 `OPENAI_IMAGE_MODEL` 切换），图片尺寸支持自定义合法尺寸，前后端必须使用同一套校验规则：

- `size` 使用 `宽x高` 格式，例如 `1024x1024`、`3840x2160`、`2160x3840`。
- 宽高必须是正整数，且都必须是 16 的倍数。
- 单边最大不超过 `3840px`。
- 最长边与最短边比例不能超过 `3:1`。
- 总像素必须在 `655360` 到 `8294400` 之间。
- `2560x1440` 及以上属于 2K/4K 实验尺寸，前端需要提示生成可能更慢或稳定性略低。
- 非法尺寸必须在真实调用 OpenAI 前被后端拦截，前端也要提前阻止提交。

代理配置：

```yaml
openai:
  proxy:
    type: ${OPENAI_PROXY_TYPE:HTTP}
    host: ${OPENAI_PROXY_HOST:}
    port: ${OPENAI_PROXY_PORT:0}
```

## API 约定

`lovestory` 照片接口：

```text
POST   /api/photos/upload
GET    /api/photos
DELETE /api/photos/{id}
```

`lovestory` 留言接口：

```text
GET    /api/messages
POST   /api/messages
DELETE /api/messages
```

`lovestory` 吉他视频接口：

```text
GET    /api/guitar-videos
POST   /api/guitar-videos/upload
POST   /api/guitar-videos/{id}/cover
DELETE /api/guitar-videos/{id}
```

`/api/guitar-videos/upload` 上传字段：

```text
file         MultipartFile，必填，视频文件
cover        MultipartFile，可选，封面图；前端未选择时可自动从视频截帧生成
title        string，必填
description  string，可选
tag          string，可选
sortOrder    int，可选
```

视频文件后缀限制为 `mp4`、`webm`、`mov`。封面图后缀限制为 `jpg`、`jpeg`、`png`、`webp`。

公共认证接口：

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

`imagetemplate` 图片模板接口：

```text
GET  /api/image-templates?page=1&size=48&keyword=&functionCategory=&functionScene=&source=&category=&imageOnly=false
GET  /api/image-templates/meta
GET  /api/image-templates/categories
GET  /api/image-templates/{id}
POST /api/image-templates/{id}/prompt
POST /api/image-templates/{id}/generate
```

`GET /api/image-templates` 默认 `page=1`、`size=48`，`size` 最大为 100，列表只返回摘要；`functionCategory` 和 `functionScene` 分别按一级功能与二级场景 slug 筛选，旧 `source` 和 `category` 参数继续兼容。完整 Prompt 由详情接口按需返回。`GET /api/image-templates/meta` 返回 4456 总量、15 个一级功能及二级场景树、7 个来源、原始分类计数和 `READY` / `DEGRADED` 聚合状态。大库异常时页面必须显示预期数量、实际数量和错误原因。

`website` 提示词库接口（服务端分页/搜索，数据源为 MySQL `xixi` 库的 `prompt_entry`、`prompt_source`、`prompt_group` 三张表）：

```text
GET  /api/prompts/meta
GET  /api/prompts?keyword=&group=&category=&source=&status=&page=1&size=48
GET  /api/prompts/{id}
POST /api/prompts
```

`GET /api/prompts/meta` 返回总数、大分类（slug/name/count/小分类列表）和来源（id/name/status/count/license/summary）。列表接口默认 `page=1`、`size=48`，`size` 最大 100；`keyword` 用 SQL LIKE 匹配标题/正文/标签/小分类（`%`、`_`、`\` 会转义），列表只返回摘要（`preview` 为正文前 200 字）。详情接口返回完整 prompt；条目不存在时返回 HTTP 404 与 `{ "success": false, "message": "提示词不存在" }`。

`POST /api/prompts` 用于手动添加提示词，请求体为 `{ "title": "...", "category": "...", "prompt": "...", "tags": "...", "sourceUrl": "...", "license": "..." }`；`title`、`category`、`prompt` 必填（标题 512、小分类 128、正文 60000、标签 1000、来源链接 512、授权 255 字符上限），校验失败返回 HTTP 400 与 `{ "success": false, "message": "..." }`。服务端按库中该小分类的既有大分类归属自动写入 `group_slug`（未知小分类归入 `other`），首次添加时自动创建 `manual`（手动添加）来源，`entry_key` 使用 `manual-{uuid}`，`status` 默认 `imported`；成功后返回 `{ "success": true, "entry": { ...完整详情 } }`。当前不加鉴权。

`python-a` A 股研究台接口：

```text
GET    /api/health
GET    /api/watchlist
POST   /api/watchlist
DELETE /api/watchlist?code={code}
GET    /api/stock?code={code}
POST   /api/ai/dimension-analysis
POST   /api/obsidian/stock-daily-review
POST   /api/obsidian/daily-review
GET    /api/trading/dashboard?date={yyyy-MM-dd}
GET    /api/trading/capital-flows
POST   /api/trading/capital-flows
GET    /api/trading/account-snapshots
POST   /api/trading/account-snapshots
GET    /api/trading/trades?date={yyyy-MM-dd}
POST   /api/trading/trades
POST   /api/trading/parse/account-screenshot
POST   /api/trading/parse/trades-screenshot
GET    /api/trading/parse-drafts
POST   /api/trading/parse-drafts/{id}/confirm
POST   /api/trading/parse-drafts/{id}/reject
POST   /api/trading/daily-review
POST   /api/trading/insights/update
```

`quant-a` Quant 研究台接口：

```text
GET  /api/health
GET  /api/status
POST /api/data/sync
POST /api/scores/run
POST /api/backtests/run
```

`scrapling-ui` 爬虫工作台接口：

```text
GET    /api/health
POST   /api/session/start
POST   /api/session/action
POST   /api/session/update-history
POST   /api/session/close
POST   /api/session/query-selector
POST   /api/generate-code
POST   /api/run-code
POST   /api/ai/heal-selector
GET    /api/todo
POST   /api/todo
GET    /api/scheduler/jobs
POST   /api/scheduler/jobs
POST   /api/scheduler/jobs/{job_id}/toggle
DELETE /api/scheduler/jobs/{job_id}
POST   /api/scheduler/jobs/{job_id}/run
```

`website` 侧点击启动与状态接口见“Scrapling UI 微服务入口方式”。

新增接口响应至少包含：

```json
{
  "success": true
}
```

错误响应至少包含：

```json
{
  "success": false,
  "message": "error detail"
}
```

## 静态资源约定

- `lovestory` 页面放在 `lovestory/src/main/resources/static`。
- `lovestory` 吉他视频卡片模块维护在 `lovestory/src/main/resources/static/index.html`，替代原 `甜蜜回忆 · Memory Cards` 模块；视频卡片数据来自 `/api/guitar-videos`，不要再硬编码视频 URL。
- `website` 主页资源放在 `website/src/main/resources/static/css`、`static/js`、`static/img`。
- `website` 静态提示词库资源放在 `website/src/main/resources/static/prompt-console`，分类采用“大分类 -> 小分类”两级结构；页面动效使用本地 `js/vendor/gsap.min.js` + `js/vendor/ScrollTrigger.min.js`（均为 3.12.5）与 `prompt-console-motion.js`，脚本缺失或 `prefers-reduced-motion` 时降级为静态。页面数据通过 `/api/prompts` 系列接口从 MySQL 读取（服务端分页/搜索），不再直接 fetch 本地 JSON。
- `imagetemplate` 页面放在 `imagetemplate/src/main/resources/static`；47 条精选模板位于模块 `templates`，4409 条大库由 Maven 从 website 唯一源复制进 classpath。页面保持原生 HTML/CSS/JavaScript 四场景单视口结构，列表禁止一次请求或渲染全部 4456 条，移动端和 `prefers-reduced-motion` 必须可用。
- `python-a` 页面放在 `website/python-a/index.html`、`website/python-a/app.js`、`website/python-a/styles.css`，由 `website/python-a/server.py` 直接提供静态访问。
- `quant-a` 页面放在 `website/quant-a/web`，由 `website/quant-a/main.py` 通过 FastAPI 静态资源能力提供访问。
- `scrapling-ui` 前端源码放在 `website/scrapling-ui/frontend`，构建产物 `frontend/dist` 由 `backend/main.py` 同端口托管（`/assets` 挂载 + SPA fallback）；`dist` 不提交，本地用 `npm run build` 生成。
- 静态资源使用相对路径或明确的外部 URL，不引用本机绝对路径。
- 不修改 `target/` 下的构建产物。

## 代码规范

Java 命名：

- 类名使用 `UpperCamelCase`：`PhotoDao`、`ImagePromptTemplateService`。
- 方法名和变量名使用 `lowerCamelCase`：`listArticles`、`renderPrompt`。
- 常量使用 `UPPER_SNAKE_CASE`。
- 包名全部小写。
- Controller 类以 `Controller` 结尾。
- DAO 接口以 `Dao` 结尾。
- MyBatis XML 文件以 `Mapper.xml` 结尾。
- Service 接口或类以 `Service` 结尾，实现类以 `ServiceImpl` 结尾。
- DTO 类以 `Request`、`Response` 结尾。
- Exception 类以 `Exception` 结尾。

Spring 约定：

- 优先使用构造器注入，不使用字段注入。
- Controller 只处理 HTTP 入参、响应组装和异常映射。
- 业务规则放在 Service。
- 数据库访问放在 DAO + XML Mapper。
- 外部 API 调用封装在独立 Service，例如 `OpenAiImageGenerationService`。
- `common` 自动配置必须保持可选，使用 `@ConditionalOnProperty`、`@ConditionalOnClass`、`@ConditionalOnMissingBean`。

Python 约定：

- `python-a` 优先保持轻量，不引入 Django、Flask、FastAPI，除非有明确功能收益。
- DeepSeek Key 优先使用环境变量 `DEEPSEEK_API_KEY`；本地私有配置文件只能使用 `deepseek.local.json`，禁止提交真实 Key。
- `PORT`、`DEEPSEEK_API_BASE`、`DEEPSEEK_MODEL` 等运行配置优先使用环境变量。
- `website` 自动启动 `python-a` 的配置位于 `website/src/main/resources/application.yml` 的 `python-a.auto-start`。单元测试必须关闭该开关，避免测试启动外部进程。
- `website` 自动启动 `quant-a` 的配置位于 `website/src/main/resources/application.yml` 的 `quant-a.auto-start`。单元测试必须关闭该开关，避免测试启动外部进程。
- 两个 Python 子服务的 `*.auto-start.log-to-console` 默认值为 `true`，会把子进程日志直接输出到 `website` 控制台；如需恢复文件日志，可设为 `false`，日志会写入各自目录下的 `server.out.log` 和 `server.err.log`。
- 股票研究输出必须保留风险提示和非投资建议边界，避免确定性买卖结论。
- 涉及网络请求、文件写入和 Obsidian 写入时要保留异常处理，不能因为单个外部接口失败导致页面整体不可用。
- `quant-a` 使用 FastAPI + Uvicorn，运行配置优先使用环境变量或 `website/quant-a/configs` 内配置文件；不要把 `quant-a` 加入 Maven modules，不要复用或写入 `website/python-a/obsidian-vault/`。
- `quant-a` 的量化评分、回测和报告输出必须保留风险提示和非投资建议边界，避免确定性买卖结论。

## 测试策略

当前测试框架：

- JUnit 5
- Spring Boot Test
- AssertJ
- Maven Surefire 2.22.2

必跑命令：

```bash
mvn test
mvn -pl common test
mvn -pl lovestory -am test
mvn -pl website -am test
mvn -pl imagetemplate -am test
```

修改 `website/src/main/resources/static/prompt-console` 的提示词分类映射后，至少执行：

```bash
node website/src/test/js/prompt-console/prompt-category-groups.test.js
```

`python-a` 使用 Python `unittest` 测试服务拆分逻辑，修改后至少执行：

```bash
cd website/python-a
python -m unittest discover -s tests -v
```

涉及页面或接口联调时再启动服务：

```bash
cd website/python-a
python server.py
```

再访问：

```text
http://127.0.0.1:5174/
http://127.0.0.1:5174/api/health
```

`quant-a` 修改后至少执行：

```bash
cd website/quant-a
python -m pytest
python -m uvicorn main:app --host 127.0.0.1 --port 5175
```

再访问：

```text
http://127.0.0.1:5175/
http://127.0.0.1:5175/api/health
```

`scrapling-ui` 修改后至少执行：

```bash
cd website/scrapling-ui/backend
uv run python -m unittest discover -s tests -v
```

涉及 Java 点击启动逻辑时：

```bash
mvn -pl website -am test
```

测试要求：

- `common` 工具类写纯单元测试，不依赖真实 OSS。
- `lovestory` 数据库相关测试 mock DAO 或使用隔离测试配置，不连接远程 MySQL。
- `website` 提示词库（`prompt.library`）Service/Controller 使用 mock DAO 单测，不连接远程 MySQL；`PromptLibraryStaticPageTest` 断言页面已接入 `/api/prompts` 系列接口。
- `lovestory` 吉他视频新增或修改逻辑时，覆盖上传成功、标题为空、非法视频后缀、封面上传、删除和 OSS 不可用等主要分支。
- `imagetemplate` 模板聚合测试必须覆盖 47 + 4409 = 4456、ID 唯一、全部模板具有一级功能和二级场景、功能树计数闭合、编程分类样例、功能/来源/原始分类/关键词/仅图片相关筛选、分页摘要、详情、DIRECT/STRUCTURED 渲染、`DEGRADED` 降级和模板不存在。
- `imagetemplate` 图片尺寸测试必须覆盖合法 4K、非法格式、非 16 倍数、单边超限、像素过少、像素过多和比例超限。
- OpenAI 图片生成测试不得真实调用外部 API；使用 mock 或可注入 HTTP 客户端。
- `quant-a` 新增 API、因子、回测、组合或服务编排逻辑时，使用 pytest 覆盖成功路径和主要失败路径，不依赖真实外部行情接口。
- `scrapling-ui` 后端测试使用 unittest + FastAPI TestClient，不启动 Playwright 浏览器；`website` 点击启动逻辑测试不启动真实 Python 进程、不连接真实端口。

覆盖率目标：

- `common` 工具类核心分支不低于 80%。
- `lovestory` controller/service 新增逻辑不低于 80%。
- `imagetemplate` 的 `ImagePromptTemplateService` 核心分支不低于 80%。

项目当前没有统一 JaCoCo。需要覆盖率门禁时，在父 `pom.xml` 统一配置 `jacoco-maven-plugin`。

## 构建与提交检查清单

提交前执行：

```bash
mvn clean test
```

只改某个模块时执行对应模块测试：

```bash
mvn -pl imagetemplate -am test
```

检查项：

- **关键**：每次修改项目结构、模块职责、启动命令、端口、配置项、API、数据目录、测试方式或部署入口时，同步更新根 `AGENTS.md` / `README.md` 和受影响目录的 `AGENTS.md` / `README.md`。
- **关键**：不提交 `target/`、IDE 缓存、真实密钥、真实数据库密码、生成图片 base64 文件。
- **关键**：新增公共能力优先放入 `common`。
- **关键**：修改数据库字段时，同步更新 Mapper XML、DAO、模型类和测试。
- **关键**：修改 `lovestory` 吉他视频表字段时，同步更新 `GuitarVideoRecord`、`GuitarVideoDao`、`GuitarVideoMapper.xml`、`GuitarVideoServiceImplTests` 和前端展示字段。
- **关键**：`imagetemplate` 当前聚合总量为 4456：47 条精选模板（其中 20 条属于 `direct-prompt`）+ 4409 条 Prompt Console 大库。精选库修改时同步数量和分类断言；大库只修改 website 唯一源，重新构建 imagetemplate 即可同步，禁止在模块源码中复制第二份 12.9MB 文件。
- **关键**：修改 `imagetemplate` 图片尺寸选项或规则时，同步更新前端校验、后端校验和 `OpenAiImageGenerationServiceTest`。
- **关键**：修改 `website/python-a` 时不要提交 `deepseek.local.json`、`.env`、`__pycache__/`、`server.err.log`、`server.out.log`。
- **关键**：修改 `website/quant-a` 时不要提交 `.env`、`__pycache__/`、`.pytest_cache/`、运行时数据库、缓存或生成报告；不要写入 `website/python-a/obsidian-vault/`。
- **关键**：修改 `website/scrapling-ui` 时不要提交 `backend/.venv/`、`backend/jobs.db`、`frontend/node_modules/`、`frontend/dist/`、`*.log`；前端改动后重新 `npm run build`。
- ⚠️ 不依赖远程生产 MySQL、真实 OSS、真实 OpenAI API 来通过单元测试。

## 常见任务指南

### 新增 imagetemplate 模板

1. 修改 `imagetemplate/src/main/resources/templates/image-prompt-templates.json`。
2. 保证 `id` 唯一、`categorySlug` 稳定。
3. 如果更新 4409 条公开大库，只修改 `website/src/main/resources/static/prompt-console/data/prompt-library.json`；不要手工修改 `target/classes` 或在 imagetemplate 源码中复制大库。
4. 如新增 `direct-prompt` 直接提示词模板，`category` 固定为 `直接提示词`，`categorySlug` 固定为 `direct-prompt`，`jsonTemplate` 使用 `{}`，`promptTemplate` 必须是可直接用于图片生成的完整中文提示词，不使用 `<...>` 占位符。
5. 外部提示词来源优先使用 GitHub 仓库并保留 `sourceUrl`，当前已集成来源包括 `YouMind-OpenLab/awesome-gpt-image-2`、`EvoLinkAI/awesome-gpt-image-2-prompts`、`freestylefly/awesome-gpt-image-2`。
6. 更新 `ImagePromptTemplateServiceTest` 的聚合数量或分类断言。
7. 运行：

```bash
mvn -pl imagetemplate test
```

### 修改 OpenAI 图片生成逻辑

1. 修改 `ImageGenerationRequest` 或 `ImageGenerationResponse`。
2. 修改 `OpenAiImageGenerationService` 的请求体或响应解析。
3. 修改 `imagetemplate/src/main/resources/static/js/app.js`。
4. 如果修改 `size`，必须保持前端和后端尺寸规则一致，并补充 `OpenAiImageGenerationServiceTest` 边界测试。
5. 补充无 API Key、OpenAI 错误、空图片数据响应测试。
6. 运行：

```bash
mvn -pl imagetemplate -am test
```

### 修改 OSS 行为

1. 优先修改 `common/src/main/java/com/example/common/util/OssUtil.java`。
2. 如需新增配置，修改对应 `@ConfigurationProperties` 类。
3. 保持 OSS 可关闭。
4. 补充 `common` 测试。
5. 运行：

```bash
mvn -pl common test
```

### 修改 lovestory 吉他视频模块

1. 后端接口集中在 `lovestory/src/main/java/com/ycxandwuqian/love/controller/GuitarVideoController.java`。
2. 业务逻辑集中在 `GuitarVideoService` / `GuitarVideoServiceImpl`，Controller 不写上传校验、OSS 删除等复杂逻辑。
3. 数据库访问使用 `GuitarVideoDao` + `lovestory/src/main/resources/mapper/GuitarVideoMapper.xml`，不要新增 `JdbcTemplate`、JPA Repository 或 Java 内联 SQL。
4. 表名为 `guitar_video`，核心字段为 `title`、`description`、`tag`、`video_url`、`cover_url`、`duration_seconds`、`sort_order`、`status`、`create_time`、`update_time`。
5. 视频上传到 OSS 目录 `love530/lovestory/videos`，封面上传到 `love530/lovestory/videos/covers`。
6. 前端上传视频时，如果用户没有选择封面，可以从本地视频自动截帧生成封面并通过 `cover` 字段一起上传。
7. 修改后运行：

```bash
mvn -pl lovestory -am test
```

### 修改 python-a 微应用

1. 修改 `website/python-a/server.py`、`website/python-a/app.js`、`website/python-a/index.html` 或 `website/python-a/styles.css`。
2. 保持 `python-a` 作为独立 Python 服务，不加入父 `pom.xml`。
3. 如果新增配置，优先使用环境变量，并同步更新 `website/python-a/README.md` 和根 `AGENTS.md`。
4. 如果新增 API，同步更新本文件的 `python-a` 接口列表。
5. 运行：

```bash
cd website/python-a
python server.py
```

6. 验证：

```text
GET http://127.0.0.1:5174/api/health
```

### 修改 scrapling-ui 微服务

1. 后端改 `website/scrapling-ui/backend`，前端改 `website/scrapling-ui/frontend/src`；保持它作为独立 FastAPI + React 服务，不加入父 `pom.xml`。
2. 前端改动后必须重新构建：`cd website/scrapling-ui/frontend && npm run build`；`dist` 不提交。
3. 启动链路改动（端口、健康路径、启动命令、等待超时）时，同步更新 `website/src/main/resources/application.yml` 的 `scrapling-ui.click-start`、`ScraplingUiProperties` 默认值和 `ScraplingUiProcessManagerTest`。
4. 新增或修改后端 API 时，同步更新 `website/scrapling-ui/AGENTS.md`、`website/scrapling-ui/README.md` 和本文件的 `scrapling-ui` 接口列表。
5. 运行测试：

```bash
cd website/scrapling-ui/backend
uv run python -m unittest discover -s tests -v
mvn -pl website -am test
```

6. 验证：

```text
GET http://127.0.0.1:5176/api/health
POST http://127.0.0.1:8080/api/services/scrapling-ui/start
```

## 代理协作原则

- 先读根 `pom.xml` 和目标模块 `pom.xml`，确认模块边界后再改代码。
- 优先使用已有包结构、命名和配置前缀。
- 小改动只跑相关模块测试；跨模块改动跑 `mvn test`。
- 只改 `python-a` 时，不需要跑 Maven 测试；优先启动 Python 服务并验证 `/api/health` 和主要页面流程。
- 只改 `scrapling-ui` 后端或前端时，优先运行其后端 unittest；改动 Java 点击启动逻辑时再跑 `mvn -pl website -am test`。
- 修改配置文件时检查是否包含密钥，能改成环境变量就改成环境变量。
- 不修改 `.idea/`、`target/`、运行时生成文件，除非任务明确要求。
- 后续数据库 CRUD 使用 MyBatis DAO + XML Mapper，不新增 `JdbcTemplate`、JPA Repository 或 Java 内联 SQL。

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues for `xixi66666/love5000`, using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default five-label triage vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: root `CONTEXT.md` and `docs/adr/`, created lazily when needed. See `docs/agents/domain.md`.

## 本机模型与视频服务管理（2026-10-11）

首页 Dock 增加「Qwen 本地模型」「视频操作台」「H3 音视频模型」，共9个入口。三张新卡片进入 `/local-services/index.html` 的对应区块；页面每15秒显示服务状态，首页每30秒更新状态。

| 服务 | 本机目录 | 端口 | 管理操作 |
| --- | --- | --- | --- |
| Strata / Qwen3.8-Flash-Next IQ3_S | `F:/model/Strata` | 9999 | 只启动服务、加载模型、卸载模型、关闭服务 |
| AIMedia 视频操作台 | `D:/Code/Java_Code/AIMedia` | 8190 | 启动、关闭、打开操作台 |
| H3 / ComfyUI 生成引擎 | `D:/Code/Java_Code/AIMedia/ComfyUI` | 8189 | 启动引擎、释放模型内存、关闭引擎、打开 ComfyUI |

三个应用继续独立运行，不加入 Maven modules，不随 website 自动启动或关闭。`website.local-services` 配置本机目录、端口和180秒启动等待；目录可通过 `STRATA_HOME`、`AIMEDIA_HOME` 覆盖。入口仅适用于运行这些应用的 Windows 主机；使用 UU 远程操作主机上的浏览器也可管理。

API：`GET /api/services/local/{strata|aimedia|h3}/status`；同路径 `/health` 在在线时返回HTTP200、`success=true`和稳定的`service`标识，离线时HTTP503。`POST /api/services/local/{service}/{start|load|unload|stop}` 执行操作，只有Strata支持load，AIMedia不支持unload。修改请求需 `X-Love530-Local: 1`；仅允许回环地址、localhost/127.0.0.1/::1 Host与同源Origin，不能传入自定义命令或PID。统一 `/api/services/health` 清单在原五个服务后追加strata、aimedia、h3三个适配健康检查，共八项。

Strata以`--lazy`启动服务，第一条生成请求或「加载模型」按钮才加载权重；「卸载模型」保留API和权重文件。AIMedia通过已有GPU Python环境直接启动操作台后端，不在这里顺带启动H3。H3在提交生成任务后才加载权重，页面不把「引擎在线」或「权重已安装」谎报为「模型已加载」。释放调用ComfyUI `/free`，是异步请求，作用于该引擎缓存的模型，不删除权重和作品。视频队列或操作台作业忙碌时返回409，无法确认队列时拒绝释放/停止。启动生成任务前先卸载Qwen，避免两个大型模型争用内存和显存。

后端位于 `website/src/main/java/com/example/website/integration/local/`，停止脚本为classpath中的 `local-services/stop-service.ps1`。只停止命令同时匹配项目路径、脚本与端口的Python进程，拒绝停止占用端口的其他应用。日志在启动应用的工作目录中，文件名`love530-service.log`。新页面不需要npm构建。

验证：`mvn -pl website -am test -Dtest=LocalServicesManagerTest,LocalServicesControllerTest,ServiceHealthPropertiesTest,ServiceHealthAggregatorTest,ServiceHealthCheckerTest,ServiceHealthControllerTest,HomepageStaticAssetsTest,WebsiteApplicationTests -Dsurefire.failIfNoSpecifiedTests=false`；`node --check website/src/main/resources/static/local-services/app.js`；`node website/src/test/js/homepage-motion.test.js`。单元测试不加载真实模型、不生成视频、不连接真实数据库。
