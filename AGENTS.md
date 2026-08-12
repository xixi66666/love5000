# AGENTS.md

## 统一服务健康检查

六个独立服务 `lovestory`、`imagetemplate`、`guitar`、`python-a`、`quant-a`、`video`
均提供 `GET /api/health`，响应顶层必须包含布尔值 `success=true` 和稳定的 `service`
标识。`website` 使用 `ServiceHealthChecker` 统一探测，并通过
`GET /api/services/health` 并行返回配置顺序一致的聚合结果；HTTP 200 表示聚合执行成功，
顶层 `healthy` 表示是否所有服务均在线。连接/读取超时默认分别为 2000/3000ms。

## 项目概述

`love5000` 是一个 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目，父工程 artifactId 为 `love530`。当前模块：

- `common`：公共能力模块，提供 OSS 自动配置、上传工具，以及通用登录/注册/Session 鉴权能力。
- `lovestory`：恋爱相册 Web 应用，提供静态页面、照片上传、照片列表、删除接口、留言板功能和吉他视频卡片模块。
- `website`：个人主页/展示站点 Web 应用，包含主页静态资源、Web Demo、OSS Demo、Nacos Discovery 示例、提示词控制台入口和个人博客微应用。
- `imagetemplate`：图片提示词模板 Web 服务，聚合 47 条精选模板和 Prompt Console 的 4409 条公开提示词，总计 4456 条，按 15 个一级功能与二级场景导航，提供分页检索、按需详情、prompt 渲染、直接提示词和 OpenAI 图片生成能力；前端采用亮色 AI 创作工作台，灵感大厅使用顶部搜索、左侧筛选和右侧结果网格。
- `guitar`：Guitar 曲谱平台 Web 微服务，提供基础首页、健康检查、手机号注册登录、Session/CSRF 鉴权、公开曲谱检索详情、安全上传、管理员曲谱下架/恢复和 MySQL 持久化基础能力。
- `python-a`：A 股自选股 AI 研究台，作为独立 Python 微应用接入，不加入 Maven 聚合模块。
- `quant-a`：A 股量化研究台，作为独立 FastAPI 微服务接入，不加入 Maven 聚合模块，不写入 `website/python-a` 的 Obsidian 目录。
- `video`：AI 原创动漫短片生成工作台，作为独立 Python 微应用接入，不加入 Maven 聚合模块。

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

**关键**：`website/video` 是独立 Python 微应用，不是 Java Maven 模块，不要把它加入父 `pom.xml` 的 `<modules>`。Java 侧只负责入口链接、健康检测或反向代理，不把视频生成、FFmpeg 调用、OpenAI 调用等业务逻辑改写进 Controller。

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
mvn -pl guitar -am test
```

启动 `lovestory`，默认端口 `8081`：

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
```

启动 `website`，默认端口 `8080`：

```bash
mvn -pl website -am spring-boot:run
```

`website` 启动时会默认自动检查并启动 `python-a`、`quant-a` 和 `video`。如果本机对应健康检查已可用，则直接复用已有服务，不重复启动。三个 Python 子服务默认把 stdout/stderr 输出到 `website` 的同一个控制台，便于在 IDEA Run/Terminal 中直接查看运行日志和接口访问日志。

统一启动 `python-a` + `website`：

```powershell
.\scripts\start-love5000.ps1
```

指定 Java 模块或 Python 端口：

```powershell
.\scripts\start-love5000.ps1 -JavaModule website -PythonPort 5174
```

可选启动 `quant-a` + `python-a` + `website`：

```powershell
.\scripts\start-love5000.ps1 -StartQuant
```

指定 Quant 端口：

```powershell
.\scripts\start-love5000.ps1 -StartQuant -QuantPort 5175
```

启动 `imagetemplate`，默认端口 `8082`：

```bash
mvn -pl imagetemplate -am spring-boot:run
```

启动 `guitar`，默认端口 `8088`：

```bash
mvn -f guitar/pom.xml spring-boot:run
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

启动 `video`，默认端口 `5176`：

```bash
cd website/video
python web_server.py
```

验证 `video`：

```bash
cd website/video
python web_server.py
```

再访问 `http://127.0.0.1:5176/api/health` 和 `http://127.0.0.1:5176/api/config`。

日常本地联调优先使用根目录统一启动脚本，避免忘记先启动 Python 微应用。

## 项目结构

```text
love5000/
├── pom.xml
├── AGENTS.md
├── scripts/
│   └── start-love5000.ps1
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
│           │   ├── css/app.css
│           │   └── js/app.js
│           └── templates/image-prompt-templates.json
├── guitar/
│   ├── AGENTS.md
│   └── src/
│       ├── main/java/com/example/guitar/
│       ├── main/resources/static/index.html
│       └── test/java/com/example/guitar/
├── website/python-a/
    ├── README.md
    ├── package.json
    ├── server.py
    ├── index.html
    ├── app.js
    ├── styles.css
    └── obsidian-vault/
├── website/quant-a/
    ├── main.py
    ├── requirements.txt
    ├── configs/
    ├── quant/
    ├── tests/
    └── web/
└── website/video/
    ├── anime_cli.py
    ├── web_server.py
    ├── anime_tools/
    ├── anime_projects/
    ├── tests/
    └── web/
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

`video` 不参与 Maven 构建，下面结构只表示其独立 Python 微应用边界：

```text
website/video/
    ├── anime_cli.py
    ├── web_server.py
    ├── config/
    │   ├── config.example.json
    │   └── config.local.json  # 本地私有配置，禁止提交
    ├── python/
    │   ├── anime_tools/
    │   ├── cli/
    │   ├── server/
    │   └── scripts/
    ├── anime_projects/        # 本地生成产物，禁止提交
    ├── assets/
    └── web/
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
- `website/blog`：个人博客微应用后端，按 Controller、Service、DAO、Model、DTO 分层。
- `website/src/main/resources/static/blog`：博客前端页面和资源。
- `website/src/main/resources/static/prompt-console`：静态提示词库页面、数据和两级分类映射。`prompt-category-groups.js` 维护“大分类 -> 小分类”映射，新增提示词小类时优先补充该文件；未映射小类自动归入“其他”。
- `website/demos`：示例性质的 Web、OSS、Nacos Discovery 代码。
- `imagetemplate/controller`：图片模板 API。
- `imagetemplate/service`：精选模板加载、大库加载适配、两级功能分类、聚合分页、prompt 渲染和 OpenAI 图片生成服务；功能规则集中在 `TemplateFunctionClassifier`，不扫描完整 Prompt。
- `imagetemplate/src/main/resources/templates/image-prompt-templates.json`：47 条精选图片模板数据源。
- `website/src/main/resources/static/prompt-console/data/prompt-library.json`：4409 条 Prompt Console 大库唯一源码；Maven 构建 imagetemplate 时复制到 classpath 的 `templates/prompt-console/prompt-library.json`。
- `imagetemplate/src/main/resources/static`：图片模板库亮色 AI 创作单页前端，复用 website 首页 `03 Deep Woods` 的同一段森林视频背景，工作区以视频可见性优先：外层约 6% 雾白色膜、约 1px 轻微模糊，结果区约 3%、卡片约 16%，输入控件保留较高底色；信息文字、说明、统计和标签统一使用近黑色层级，深色操作按钮保留白字，“加载更多提示词”与工作区使用相同透明玻璃；并保留 `prefers-reduced-motion` 装饰动画降级；按“灵感大厅 → 模板解构 → Prompt 编导台 → 图片生成舱”组织，桌面端使用页面左侧居中的紧凑悬浮步骤器，900px 以下恢复为底部横向流程；灵感大厅顶部常驻搜索、仅图片开关和清除筛选，内容区左侧集中展示一级功能、二级场景及默认收起的来源/原始分类，右侧为默认 48 条的结果网格，支持搜索防抖和加载更多；模板解构 JSON 与编导台变量均允许手工编辑，JSON 在进入编导台前校验并同步；流程导航只切换场景、不清空用户状态。
- `guitar/src/main/java/com/example/guitar/controller`：Guitar 基础 HTTP 接口，当前提供 `/api/health`。
- `guitar/src/main/java/com/example/guitar/auth`：Guitar 手机号注册登录、Session、CSRF 和 API 权限拦截能力；数据库写入由独立事务服务提交成功后，认证服务才轮换 Session。
- `guitar/src/main/java/com/example/guitar/user`：Guitar 用户模型和 MyBatis DAO，SQL 位于 `guitar/src/main/resources/mapper/user`。
- `guitar/src/main/java/com/example/guitar/sheet`：Guitar 曲谱公开检索、详情、安全上传、文件 URL 服务和 MyBatis DAO；OSS 上传在事务外完成，曲谱和文件记录由独立事务服务写入，SQL 位于 `guitar/src/main/resources/mapper/sheet`。
- `guitar/src/main/java/com/example/guitar/favorite`：Guitar 私人多收藏夹、收藏关系、所有权校验和收藏计数事务；SQL 位于 `guitar/src/main/resources/mapper/favorite`，接口不得返回收藏夹 `userId` 或曲谱对象键。
- `guitar/src/main/java/com/example/guitar/admin`：Guitar 管理员曲谱查询、下架/恢复状态机和审计事务；管理员身份只取认证 Session，SQL 位于 `guitar/src/main/resources/mapper/admin`。
- `guitar/src/main/resources/static`：Guitar 基础首页，默认由 Spring Boot 静态资源能力提供。
- `website/python-a/server.py`：Python 微应用后端，负责静态页面服务、东方财富行情网关、DeepSeek 调用和 Obsidian 写入。
- `website/python-a/services/stock_metadata_service.py`：股票行业、板块和概念元数据缓存与降级读取。
- `website/python-a/services/knowledge_graph_service.py`：Obsidian 知识图谱节点、复盘双链和风险模式链接生成。
- `website/python-a/index.html`、`website/python-a/app.js`、`website/python-a/styles.css`：A 股自选股 AI 研究台前端页面、交互和样式。
- `website/python-a/obsidian-vault/A股AI`：Python 微应用默认写入的 Obsidian 研究记录和自选股数据目录。
- `website/quant-a/main.py`：Quant FastAPI 应用入口，挂载前端静态资源并注册 `/api/**` 路由。
- `website/quant-a/quant`：量化研究核心代码，包含 API、因子、回测、组合、行情提供方、服务编排和存储。
- `website/quant-a/tests`：Quant 微服务测试，使用 pytest 和 FastAPI TestClient。
- `website/quant-a/web`：Quant 研究台前端页面和静态资源。
- `website/video/web_server.py`：Video 微应用本地 HTTP 服务入口，默认监听 `127.0.0.1:5176`。
- `website/video/anime_cli.py`：Video 命令行兼容入口，转调 `website/video/python/cli/anime_cli.py`。
- `website/video/python/anime_tools`：视频生成核心代码，包含项目管理、OpenAI 兼容接口调用、FFmpeg 合成、任务管理和 Web API。
- `website/video/python/scripts`：手动验证和辅助脚本，外部接口冒烟脚本使用 `smoke_*.py` 命名。
- `website/video/config`：Video 配置模板和本地私有配置目录，`config.local.json` 禁止提交。
- `website/video/web`：Video 工作台前端页面和静态资源。
- `website/video/anime_projects`：Video 本地生成项目和视频产物目录，默认不提交。

## Guitar 服务入口方式

`guitar` 作为父工程中的独立 Java Web 模块接入 `love5000`：

- 本地开发入口：启动后访问 `http://127.0.0.1:8088/`。
- 健康检查入口：`GET http://127.0.0.1:8088/api/health`，响应中的 `success` 必须为 `true`。
- 推荐命令：`mvn -f guitar/pom.xml spring-boot:run`，工作目录为仓库根目录。
- `website` 只提供入口链接和浏览器端健康检测，不负责启动或管理 Guitar Java 进程。
- 用户数据使用 MySQL 数据库 `guitar`，数据访问保持 MyBatis DAO + XML Mapper；当前 OSS 默认关闭，不使用 Nacos。
- 所有写请求必须携带从 `GET /api/auth/session` 获取的 `X-CSRF-Token`，受保护接口返回 JSON 401/403，不跳转页面。

## Python 微应用入口方式

`python-a` 以独立服务方式接入 `love5000`：

- 推荐本地统一入口：在根目录执行 `.\scripts\start-love5000.ps1`，脚本会先启动或复用 `python-a`，健康检查通过后再启动 `website`。
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
- 根目录脚本 `.\scripts\start-love5000.ps1` 仍保留显式 `-StartQuant` 参数，用于不经过 Java 自动启动器时手动拉起 Quant 服务。
- 本地开发入口：启动 `quant-a` 后访问 `http://127.0.0.1:5175/`。
- 健康检查入口：`GET http://127.0.0.1:5175/api/health`，响应中的 `success` 必须为 `true`。
- 推荐命令：`python -m uvicorn main:app --host 127.0.0.1 --port 5175`，工作目录为 `website/quant-a/`。
- `website` 只提供入口链接和健康检测，不把 `quant-a` 业务逻辑改写进 Java Controller。
- 生产部署如需统一域名，使用 Nginx、网关或 Spring 反向代理把 `/quant-a/` 转发到 `127.0.0.1:5175`。
- `quant-a` 的 `/api/**` 默认由 FastAPI 服务自己处理。没有明确需求时，不要在 Java Controller 中重复实现这些接口。
- `quant-a` 不是 Maven 模块，不执行 `mvn -pl quant-a ...`，也不要写入 `website/python-a/obsidian-vault/`。

## Video 微应用入口方式

`video` 以独立 Python 服务方式接入 `love5000`：

- 本地开发入口：启动 `video` 后访问 `http://127.0.0.1:5176/`。
- 健康检查入口：`GET http://127.0.0.1:5176/api/health`，响应中的 `success` 必须为 `true`。
- 推荐命令：`python web_server.py`，工作目录为 `website/video/`。
- `website` 内置 `VideoAutoStartRunner`，默认配置为 `video.auto-start.enabled=true`。直接启动 `website` 时会自动拉起或复用 `video`。
- `website` 只提供入口链接、自动启动和健康检测，不把 `video` 的视频生成、FFmpeg 调用或 OpenAI 调用逻辑改写进 Java Controller。
- 生产部署如需统一域名，使用 Nginx、网关或 Spring 反向代理把 `/video/` 转发到 `127.0.0.1:5176`。
- `video` 的 `/api/**` 默认由 Python 服务自己处理。没有明确需求时，不要在 Java Controller 中重复实现这些接口。
- `video` 不是 Maven 模块，不执行 `mvn -pl video ...`。

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
- `guitar`：`8088`
- `python-a`：`5174`
- `quant-a`：`5175`
- `video`：`5176`

### 数据库

- `lovestory` 使用 MySQL 数据库 `lovestory`。
- `website` 使用 MySQL 数据库 `ycx_pms`。
- `imagetemplate` 不使用数据库。
- `guitar` 使用 MySQL 数据库 `guitar`，用户及曲谱平台表结构位于 `guitar/src/main/resources/db/guitar-schema.sql`。
- `python-a` 不使用 MySQL；默认写入本地 `website/python-a/obsidian-vault/A股AI/`。
- `quant-a` 不使用 MySQL；默认使用 `website/quant-a/` 内部数据、配置和存储目录，不写入 `website/python-a` 的 Obsidian 目录。
- `video` 不使用 MySQL；默认使用 `website/video/anime_projects/` 保存本地生成项目和视频产物。

⚠️ **严重警告**：不要提交真实数据库密码、OSS AccessKey、OpenAI API Key。新增配置优先使用环境变量，例如 `${OPENAI_API_KEY:}`、`${LOVE530_OSS_ACCESS_KEY_ID:}`。

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
  image-model: ${OPENAI_IMAGE_MODEL:gpt-image-2}
  connect-timeout-ms: ${OPENAI_CONNECT_TIMEOUT_MS:30000}
  read-timeout-ms: ${OPENAI_READ_TIMEOUT_MS:180000}
```

`imagetemplate` 的 `gpt-image-2` 图片尺寸支持自定义合法尺寸，前后端必须使用同一套校验规则：

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

### Guitar 用户资料与头像

```text
PUT  /api/users/me
POST /api/users/me/avatar
```

这两个接口均从认证 Session 读取用户 ID，禁止接收或信任客户端 `userId`。`PUT /api/users/me` 请求体为 `{ "nickname": "..." }`，昵称会去首尾空白并限制为 1-30 个字符。头像上传字段名为 `avatar`，只允许实际内容与扩展名一致的 JPG/JPEG、PNG、WebP，单文件最大 5MB。启用 `LOVE530_OSS_ENABLED=true` 后，头像对象键保存在 `guitar_user.avatar_object_key`，旧对象删除失败会写入 `guitar_oss_cleanup_task`，由后续清理任务处理。

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

`website` 博客接口：

```text
GET  /api/blog/articles
GET  /api/blog/articles/{slug}
POST /api/blog/articles
GET  /api/blog/categories
GET  /api/blog/tags
```

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

`guitar` 接口：

```text
GET /api/health
GET  /api/sheets
GET  /api/sheets/{id}
POST /api/sheets
PUT  /api/sheets/{id}
PUT  /api/sheets/{id}/files
DELETE /api/sheets/{id}
GET  /api/auth/session
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET    /api/favorite-folders
POST   /api/favorite-folders
PUT    /api/favorite-folders/{id}
DELETE /api/favorite-folders/{id}
POST   /api/favorite-folders/{id}/sheets/{sheetId}
DELETE /api/favorite-folders/{id}/sheets/{sheetId}
GET    /api/favorite-folders/{id}/sheets
GET    /api/admin/sheets
POST   /api/admin/sheets/{id}/offline
POST   /api/admin/sheets/{id}/restore
```

`POST` 注册、登录和注销均需先请求 `GET /api/auth/session` 创建 Session，并在请求头携带返回的 `X-CSRF-Token`。认证 Session 属性名为 `GUITAR_AUTH_USER`。

`GET /api/sheets` 和 `GET /api/sheets/{id}` 可匿名访问，列表仅返回 `PUBLISHED` 且未删除的曲谱。列表支持 `keyword`、`songName`、`singer`、`sheetType`、`difficulty`、`keySignature`、`capoPosition`、`tuning`、`sort`、`page`、`size`；`sort` 仅允许 `LATEST`、`MOST_FAVORITED`、`MOST_VIEWED`，分页默认 `page=1`、`size=20` 且 `size` 最大为 50。详情按 `sort_order` 返回文件 URL，URL 只能由 OSS 对象键生成；读取详情同时更新曲谱浏览量和 Asia/Shanghai 当日统计。

`POST /api/sheets` 是受 Session 和 CSRF 保护的 multipart 上传接口：`metadata` 为 JSON Part，`files` 为重复文件 Part。元数据要求有效的 `sheetType`、`difficulty`、`keySignature`、`tuning` 与 `fileMode`，`fileMode=PDF` 仅允许一个不超过 30MB 的 `%PDF` PDF，`fileMode=IMAGES` 仅允许 1-20 个不超过 10MB 且魔数匹配 JPG/JPEG、PNG、WebP 的图片。客户端 Content-Type 不可信，服务端会派生 MIME 和扩展名，并在 OSS 调用前生成 `love530/guitar/sheets/{storageUuid}/pdf` 或 `/images` 下的服务器对象键；所有 URL 在持久化前生成验证，再由独立事务写入曲谱和文件记录。上传、URL 生成或持久化失败会通过 OSS 清理队列补偿全部已知对象；清理失败必须记录并附加到原始异常，成功响应只返回经文件 URL 服务生成的 URL，不暴露对象键或存储 UUID。

`PUT /api/sheets/{id}` 使用 JSON 元数据更新所有者自己的未删除曲谱，`fileMode` 不要求提供且不会被该接口修改；当前文件 URL 必须在数据库提交前完成解析。`PUT /api/sheets/{id}/files` 使用 multipart 表单参数 `mode` 和重复 `files` Part 替换文件且不修改元数据，`DELETE /api/sheets/{id}` 软删除并清除该曲谱收藏。三个接口均从 Session 读取用户 ID 并要求 CSRF；Service 必须先校验所有权再校验元数据或文件，`OFFLINE` 所有者仍可编辑或替换且状态保持不变，管理员不绕过所有者校验。每次替换必须生成与旧值不同的新 `storageUuid`，在文件行切换的同一事务内更新 `guitar_sheet.storage_uuid` 和 `file_mode`；事务锁内必须校验请求开始时观察到的 `storageUuid`，版本已变化时返回 HTTP 409 和 `SHEET_VERSION_CONFLICT`，且只补偿本请求的新对象，不得清理任何已提交版本。替换和删除必须在取得曲谱行锁后读取当前文件快照，并在同一事务内为旧对象写入 PENDING cleanup outbox；提交后的立即删除只作加速，进程中断时 scheduler 仍可接管。`guitar_oss_cleanup_task` 使用 `claim_version` 和 `processing_started_at` 隔离 worker lease；认领递增版本，成功、重试和失败更新均须匹配当前版本，15 分钟以上的 PROCESSING 才可恢复。任务在启动 60 秒后、每 5 分钟最多处理 50 项，失败退避依次为 5、30、120、720 分钟，第五次失败标记 `FAILED`。

公开曲谱检索的文本参数必须在入库字段边界内：`keyword`、`songName`、`singer` 最大 120 个字符，`keySignature` 最大 20 个字符，`tuning` 最大 80 个字符；超长请求返回 `VALIDATION_ERROR`，不得静默截断。`page` 和 `size` 计算出的偏移量最大为 `5,000,000`（默认 `page=1`、`size=20`，`size` 为 1-50）；超过上限返回 `PAGE_TOO_LARGE`。

收藏夹写接口和收藏夹曲谱查询只使用认证 Session 的用户 ID。新建/更新请求体为 `{ "name": "练习", "sortOrder": 0 }`，`name` 去除首尾空白后为 1-50 个字符，`sortOrder` 可选；同用户重名返回 `FOLDER_NAME_EXISTS`，同一收藏夹重复加入同一曲谱返回 `FAVORITE_EXISTS`。他人或不存在的收藏夹统一返回 `FOLDER_NOT_FOUND`，避免泄露所有权；仅 `PUBLISHED` 且未删除曲谱可加入，否则返回 `SHEET_NOT_FOUND`。删除不存在的收藏关系幂等成功且不修改计数；删除非空收藏夹必须在单一事务内先删除关系，再按关系集合批量递减 `favorite_count`，不得删除曲谱。

`/api/admin/**` 仅允许 Session 中角色为 `ADMIN` 的用户访问，普通 `USER` 返回 HTTP 403；所有管理员写接口仍要求 `X-CSRF-Token`。`GET /api/admin/sheets` 支持 `keyword`、`status`、`sort`、`page`、`size`，可分页查看 `DRAFT`、`PUBLISHED`、`OFFLINE`、`DELETED`，排序白名单为 `LATEST`、`MOST_FAVORITED`、`MOST_VIEWED`。下架请求体为 `{ "reason": "..." }`，理由 trim 后必须为 1-500 个字符；状态机只允许 `PUBLISHED -> OFFLINE` 和 `OFFLINE -> PUBLISHED`，重复操作或恢复 `DELETED` 返回稳定 HTTP 409 业务错误。下架填写 `offline_reason/offline_by/offline_at`，恢复清空这些字段；状态更新和 `guitar_admin_action_log` 写入处于同一事务，审计记录管理员、动作、目标、理由、前后状态、容器远端 IP 和时间。管理员身份不从请求体读取，IP 不采信任意 `X-Forwarded-For`；操作不修改 OSS 文件和收藏关系。

Task 7 聚焦测试命令为 `mvn -pl guitar -am '-Dtest=FavoriteServiceTest,FavoriteControllerTest' -DfailIfNoTests=false test`；Task 8 聚焦测试命令为 `mvn -pl guitar -am '-Dtest=SheetAdminServiceTest,SheetAdminControllerTest' -DfailIfNoTests=false test`；完整回归仍运行 `mvn -pl guitar -am test`。

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

`video` 动漫短片工作台接口：

```text
GET  /api/health
GET  /api/projects
GET  /api/projects/{project_name}
POST /api/projects/auto
POST /api/projects/{project_name}/resume
POST /api/projects/{project_name}/storyboard
POST /api/projects/{project_name}/shots/{shot_id}/regenerate-keyframe
POST /api/projects/{project_name}/subtitles
POST /api/projects/{project_name}/render
GET  /api/tasks/{task_id}
GET  /api/assets/{project_name}/keyframes/{file_name}
GET  /api/assets/{project_name}/video/final
```

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
- `website` 博客资源放在 `website/src/main/resources/static/blog`。
- `website` 静态提示词库资源放在 `website/src/main/resources/static/prompt-console`，分类采用“大分类 -> 小分类”两级结构。
- `imagetemplate` 页面放在 `imagetemplate/src/main/resources/static`；47 条精选模板位于模块 `templates`，4409 条大库由 Maven 从 website 唯一源复制进 classpath。页面保持原生 HTML/CSS/JavaScript 四场景单视口结构，列表禁止一次请求或渲染全部 4456 条，移动端和 `prefers-reduced-motion` 必须可用。
- `guitar` 页面放在 `guitar/src/main/resources/static`，健康接口放在 `com.example.guitar.controller`。
- `python-a` 页面放在 `website/python-a/index.html`、`website/python-a/app.js`、`website/python-a/styles.css`，由 `website/python-a/server.py` 直接提供静态访问。
- `quant-a` 页面放在 `website/quant-a/web`，由 `website/quant-a/main.py` 通过 FastAPI 静态资源能力提供访问。
- `video` 页面放在 `website/video/web`，由 `website/video/web_server.py` 通过 Python `http.server` 提供静态访问。
- 静态资源使用相对路径或明确的外部 URL，不引用本机绝对路径。
- 不修改 `target/` 下的构建产物。

## 代码规范

Java 命名：

- 类名使用 `UpperCamelCase`：`BlogController`、`PhotoDao`、`ImagePromptTemplateService`。
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
- `website` 自动启动 `video` 的配置位于 `website/src/main/resources/application.yml` 的 `video.auto-start`。单元测试必须关闭该开关，避免测试启动外部进程。
- 三个 Python 子服务的 `*.auto-start.log-to-console` 默认值为 `true`，会把子进程日志直接输出到 `website` 控制台；如需恢复文件日志，可设为 `false`，日志会写入各自目录下的 `server.out.log` 和 `server.err.log`。
- 股票研究输出必须保留风险提示和非投资建议边界，避免确定性买卖结论。
- 涉及网络请求、文件写入和 Obsidian 写入时要保留异常处理，不能因为单个外部接口失败导致页面整体不可用。
- `quant-a` 使用 FastAPI + Uvicorn，运行配置优先使用环境变量或 `website/quant-a/configs` 内配置文件；不要把 `quant-a` 加入 Maven modules，不要复用或写入 `website/python-a/obsidian-vault/`。
- `quant-a` 的量化评分、回测和报告输出必须保留风险提示和非投资建议边界，避免确定性买卖结论。
- `video` 使用 Python 标准库 `http.server` 提供本地工作台，运行配置优先使用 `website/video/config/config.local.json` 或命令行参数；不要把 `video` 加入 Maven modules。
- `website/video/config/config.local.json` 和历史兼容位置 `website/video/config.local.json` 禁止提交真实 API Key；`website/video/anime_projects/`、`website/video/.vendor/`、`__pycache__/` 和生成的视频、音频、图片产物默认不提交。
- `video` 的视频生成输出必须保留 AI 生成内容和非真实拍摄素材边界，避免误导为真实影像。

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
mvn -pl guitar -am test
```

`guitar` 修改后至少执行：

```bash
mvn -pl guitar -am test
mvn -f guitar/pom.xml spring-boot:run
```

再访问：

```text
http://127.0.0.1:8088/
http://127.0.0.1:8088/api/health
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

`video` 修改后至少执行：

```bash
cd website/video
python web_server.py
```

再访问：

```text
http://127.0.0.1:5176/
http://127.0.0.1:5176/api/health
http://127.0.0.1:5176/api/config
```

测试要求：

- `common` 工具类写纯单元测试，不依赖真实 OSS。
- `lovestory` 数据库相关测试 mock DAO 或使用隔离测试配置，不连接远程 MySQL。
- `lovestory` 吉他视频新增或修改逻辑时，覆盖上传成功、标题为空、非法视频后缀、封面上传、删除和 OSS 不可用等主要分支。
- `website/blog` 新增 controller/service/dao 逻辑必须覆盖成功路径和主要失败路径。
- `imagetemplate` 模板聚合测试必须覆盖 47 + 4409 = 4456、ID 唯一、全部模板具有一级功能和二级场景、功能树计数闭合、编程分类样例、功能/来源/原始分类/关键词/仅图片相关筛选、分页摘要、详情、DIRECT/STRUCTURED 渲染、`DEGRADED` 降级和模板不存在。
- `imagetemplate` 图片尺寸测试必须覆盖合法 4K、非法格式、非 16 倍数、单边超限、像素过少、像素过多和比例超限。
- `guitar` 新增 Controller 时使用 Spring Boot Test + MockMvc 覆盖状态码和响应结构，不依赖数据库或外部服务。
- OpenAI 图片生成测试不得真实调用外部 API；使用 mock 或可注入 HTTP 客户端。
- `quant-a` 新增 API、因子、回测、组合或服务编排逻辑时，使用 pytest 覆盖成功路径和主要失败路径，不依赖真实外部行情接口。
- `video` 新增 API、任务管理、分镜保存、关键帧生成或合成逻辑时，使用 unittest 覆盖成功路径和主要失败路径，不依赖真实 OpenAI 或真实外部服务。

覆盖率目标：

- `common` 工具类核心分支不低于 80%。
- `lovestory` controller/service 新增逻辑不低于 80%。
- `website/blog` controller/service/dao 新增逻辑覆盖成功路径和主要失败路径。
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
- **关键**：修改 `guitar` 的端口、名称或健康接口时，同步更新 Website 主页入口、根 `AGENTS.md` 和 `guitar/AGENTS.md`。
- **关键**：修改 `website/python-a` 时不要提交 `deepseek.local.json`、`.env`、`__pycache__/`、`server.err.log`、`server.out.log`。
- **关键**：修改 `website/quant-a` 时不要提交 `.env`、`__pycache__/`、`.pytest_cache/`、运行时数据库、缓存或生成报告；不要写入 `website/python-a/obsidian-vault/`。
- **关键**：修改 `website/video` 时不要提交 `config/config.local.json`、`config.local.json`、`.vendor/`、`__pycache__/`、`.pytest_cache/`、`anime_projects/`、生成的视频、音频、图片产物或真实 API Key。
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

### 修改 video 微应用

1. 修改 `website/video/web_server.py`、`website/video/anime_cli.py`、`website/video/python/anime_tools/`、`website/video/python/scripts/`、`website/video/config/` 或 `website/video/web/`。
2. 保持 `video` 作为独立 Python 服务，不加入父 `pom.xml`。
3. 如果新增配置，优先使用 `config/config.example.json` 模板和本地 `config/config.local.json`，并同步更新 `website/video/README.md` 和根 `AGENTS.md`。
4. 如果新增 API，同步更新本文件的 `video` 接口列表。
5. 运行：

```bash
cd website/video
python web_server.py
```

6. 验证：

```text
GET http://127.0.0.1:5176/api/health
GET http://127.0.0.1:5176/api/config
```

## 代理协作原则

- 先读根 `pom.xml` 和目标模块 `pom.xml`，确认模块边界后再改代码。
- 优先使用已有包结构、命名和配置前缀。
- 小改动只跑相关模块测试；跨模块改动跑 `mvn test`。
- 只改 `python-a` 时，不需要跑 Maven 测试；优先启动 Python 服务并验证 `/api/health` 和主要页面流程。
- 只改 `video` 时，不需要跑 Maven 测试；运行 `cd website/video && python -m pytest`，并验证 `/api/health`、`/api/config` 和主要页面流程。
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

## Guitar frontend

第一期工作台页面包括 `guitar/src/main/resources/static/upload.html`（上传/编辑）、`favorites.html`（私人收藏夹）、`profile.html`（资料与我的公开上传）和 `admin.html`（管理员下架/恢复）。Node 校验脚本为 `npm.cmd run test:upload`、`npm.cmd run test:favorites`，Java 静态资源断言使用 `mvn -pl guitar -am -Dtest=GuitarApplicationTests -DfailIfNoTests=false test`。

The Guitar homepage source lives in `guitar/src/main/frontend/` as a React/Vite app. Run `npm.cmd run dev` from `guitar/` for local frontend preview, `npm.cmd run build` to emit the served `/index.html` and hashed assets into `guitar/src/main/resources/static/`, and `npm.cmd run test:homepage` for the homepage-specific static checks. Public detail is `sheet.html`, authentication is `auth.html`, with shared ES modules in `static/js/`. Run frontend checks from `guitar/` using `npm.cmd run test:api`, `npm.cmd run test:auth`, and `npm.cmd run test:search`; Java static-resource assertions run with the Guitar Maven test command.


