# AGENTS.md

## 统一健康检查职责

`integration/health` 维护 `ServiceHealthChecker`、配置化服务清单、并行聚合器和
`GET /api/services/health`。默认聚合 11 个目标，顺序以
`src/main/resources/application.yml` 的 `website.service-health.services` 为准：
`lovestory:8081`、`imagetemplate:8082`、`python-a:5174`、`quant-a:5175`、
`scrapling-ui:5176`、`skill-finder:5177`，`strata`、`aimedia`、`h3`
通过 `/api/services/local/{service}/health` 适配，然后是 `personal-agent:5178`、`lottery:5179`。
远程响应只有在 HTTP 2xx 且顶层布尔值 `success=true` 时才健康；连接/读取超时默认 2000/3000ms。
`GET /api/services/health` 读取最近一次巡检结果。默认启动时巡检一次，后续间隔 30 分钟。
HTTP 200 表示成功返回聚合响应，顶层 `success=true` 表示巡检已生成汇总，即使全部目标离线仍可为 true，`healthy` 表示是否全部在线。
`website` 启动时仍只自动启动 `python-a`、`quant-a` 两个 Python 服务；
`scrapling-ui`、`skill-finder`、`lottery` 和 03 Deep Woods 的 `personal-agent`
只通过首页按钮点击启动（`integration/scrapling`、`integration/skillfinder`、
`integration/lottery`、`integration/personalagent`）。

## 项目概述

`website` 是 `love530` Maven 聚合工程中的个人主页/展示站点 Web 微服务，路径：

```text
C:/Code/Java_Code/love5000/website
```

核心功能：

- 提供个人主页静态站点。
- 个人主页采用单视口电影化布局，包含四场景视频切换、只提供登录/注册的液态玻璃账户顶栏和 9 个带实时状态的服务入口。
- 统一承载 `python-a`、`quant-a`、`scrapling-ui`、`skill-finder`、`lottery` 五个独立 Python 子服务的代码目录、首页入口、健康检测；前两者启动时自动拉起，`scrapling-ui`、`skill-finder`、`lottery` 由首页按钮点击启动。
- 提供提示词控制台和静态提示词库页面，并在首页提供 Prompt Console 入口。
- 提供基础 Spring MVC Web Demo。
- 保留 OSS Demo 和 Nacos Discovery 示例代码。
- 使用 MySQL 和 Druid 作为后端数据源配置。

技术栈：

- Java 8
- Maven
- Spring Boot 2.6.13
- Spring MVC
- MyBatis / DAO 接口 + XML Mapper 映射器
- MySQL Connector/J
- Alibaba Druid 1.1.22
- JUnit 5 / Spring Boot Test
- HTML / CSS / JavaScript

配置文件：

- `pom.xml`：模块依赖、Java 8 编译配置、Spring Boot 主类。
- `src/main/resources/application.yml`：端口、MySQL、Druid、静态资源路径，以及两个 Python 子服务的自动启动配置和 `scrapling-ui`、`skill-finder`、`personal-agent`、`lottery` 的点击启动配置。

**关键**：`website` 是可独立启动的 Web 服务，默认端口为 `8080`。

**关键**：`python-a`、`quant-a`、`scrapling-ui`、`skill-finder` 放在 `website/` 目录下，但仍然是独立 Python 服务，不是 Java Maven 模块，不加入父 `pom.xml` 的 `<modules>`。

**关键**：直接启动 `website` 时会自动检查并拉起 `website/python-a`、`website/quant-a`。默认会把两个 Python 子服务的 stdout/stderr 继承到 `website` 控制台，便于在 IDEA Run/Terminal 中查看运行日志和接口访问日志。

**关键**：`website/scrapling-ui` 不随 `website` 启动自动拉起。首页 Dock 的“Scrapling 抓取工坊”卡片是启动按钮：在线时直接打开，离线时调用 `POST /api/services/scrapling-ui/start` 拉起服务，启动过程只在卡片内显示“启动中…”（不打开中间页面），就绪后自动打开 `http://127.0.0.1:5176/`；若浏览器拦截新窗口，卡片提示“已启动 · 点击打开”；`website` 关闭不会强杀该服务，重复点击会复用已有进程。

**关键**：`website/skill-finder` 同样不随 `website` 启动自动拉起。首页 Dock 的“Skill Finder”卡片是启动按钮：在线时直接打开，离线时调用 `POST /api/services/skill-finder/start` 拉起服务，启动过程只在卡片内显示“启动中…”，就绪后自动打开 `http://127.0.0.1:5177/`；若浏览器拦截新窗口，卡片提示“已启动 · 点击打开”；启动前要求 `frontend/dist` 已构建；`website` 关闭不会强杀该服务，重复点击会复用已有进程。

**文档同步约定**：每次修改 `website` 的首页入口、提示词控制台、自动启动配置、Python 子服务集成、端口、API、静态资源目录或测试方式时，必须同步更新本文件、`website/README.md`，以及根目录 `AGENTS.md` / `README.md` 中相关内容。

## 开发命令

默认从仓库根目录执行：

```bash
cd C:/Code/Java_Code/love5000
```

安装依赖并编译当前服务：

```bash
mvn -pl website -am clean install
```

启动服务：

```bash
mvn -pl website -am spring-boot:run
```

服务地址：

```text
http://localhost:8080/
```

运行当前服务测试：

```bash
mvn -pl website -am test
```

打包当前服务：

```bash
mvn -pl website -am clean package
```

跳过测试打包：

```bash
mvn -pl website -am clean package -DskipTests
```

检查依赖树：

```bash
mvn -pl website dependency:tree
```

从模块目录启动：

```bash
cd C:/Code/Java_Code/love5000/website
mvn spring-boot:run
```

单独启动 `python-a`：

```bash
cd C:/Code/Java_Code/love5000/website/python-a
python server.py
```

单独启动 `quant-a`：

```bash
cd C:/Code/Java_Code/love5000/website/quant-a
python -m uvicorn main:app --host 127.0.0.1 --port 5175
```

首次准备 `scrapling-ui` 环境：

```bash
cd C:/Code/Java_Code/love5000/website/scrapling-ui/backend
uv sync
uv run playwright install chromium

cd C:/Code/Java_Code/love5000/website/scrapling-ui/frontend
npm install
npm run build
```

单独启动 `scrapling-ui`（前端已构建后）：

```bash
cd C:/Code/Java_Code/love5000/website/scrapling-ui/backend
.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 5176
```

首次准备 `skill-finder` 环境：

```bash
cd C:/Code/Java_Code/love5000/website/skill-finder/backend
uv sync

cd C:/Code/Java_Code/love5000/website/skill-finder/frontend
npm install
npm run build
```

单独启动 `skill-finder`（前端已构建后）：

```bash
cd C:/Code/Java_Code/love5000/website/skill-finder/backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 5177
```

## 项目结构

```text
website/
├── pom.xml
├── AGENTS.md
├── python-a/
│   ├── server.py
│   ├── index.html
│   ├── app.js
│   └── obsidian-vault/
├── quant-a/
│   ├── main.py
│   ├── quant/
│   ├── tests/
│   └── web/
├── scrapling-ui/
│   ├── backend/
│   │   ├── main.py
│   │   ├── core/
│   │   ├── services/
│   │   └── tests/
│   └── frontend/
│       ├── src/
│       └── dist/          # npm run build 产物，gitignored
├── skill-finder/
│   ├── backend/
│   │   ├── app/           # FastAPI 应用（采集、趋势、API、dist 托管）
│   │   ├── sql/
│   │   ├── tests/
│   │   └── .env / .secrets/   # 本地私有，gitignored
│   ├── frontend/
│   │   ├── src/
│   │   └── dist/          # npm run build 产物，gitignored
│   └── docs/
├── lottery/
│   ├── server.py          # 本地服务：静态托管 + /api/health + /api/update
│   ├── main.py            # --console-only 只重建操作台
│   ├── src/lottery/       # 数据加载、组合分布、检验、回测、操作台与报告生成
│   ├── scripts/           # update_daily.py 增量更新、fetch_*.py 全量回填
│   ├── data/              # 双色球/大乐透官方开奖 CSV
│   └── output/            # console.html 等产物（gitignored，首次启动自动构建）
└── src/
    ├── main/
    │   ├── java/com/example/website/
    │   │   ├── WebsiteApplication.java
    │   │   ├── auth/
    │   │   │   ├── WebsiteAuthUserRepository.java
    │   │   │   └── dao/WebsiteAuthUserDao.java
    │   │   ├── demos/
    │   │   │   ├── nacosdiscoveryconsumer/
    │   │   │   ├── nacosdiscoveryprovider/
    │   │   │   ├── oss/
    │   │   │   └── web/
    │   │   ├── integration/
    │   │   │   ├── PythonAAutoStartRunner.java
    │   │   │   ├── QuantAAutoStartRunner.java
    │   │   │   ├── health/
    │   │   │   ├── local/
    │   │   │   ├── lottery/
    │   │   │   ├── personalagent/
    │   │   │   ├── scrapling/
    │   │   │   └── skillfinder/
    │   │   ├── nacosdiscovery/
    │   │   └── prompt/
    │   └── resources/
    │       ├── application.yml
    │       ├── mapper/
    │       │   └── auth/WebsiteAuthUserMapper.xml
    │       ├── README.md
    │       └── static/
    │           ├── css/style.css
    │           ├── js/script.js
    │           ├── img/
    │           └── prompt-console/
    └── test/java/com/example/website/
        └── WebsiteApplicationTests.java
```

核心模块职责：

- `WebsiteApplication.java`：Spring Boot 启动类。
- `integration/PythonAAutoStartRunner.java`：启动或复用 `website/python-a`，健康检查地址为 `http://127.0.0.1:5174/api/health`。
- `integration/QuantAAutoStartRunner.java`：启动或复用 `website/quant-a`，健康检查地址为 `http://127.0.0.1:5175/api/health`。
- `integration/scrapling`：`ScraplingUiProcessManager` 负责按需启动/复用 `website/scrapling-ui`（优先 `backend/.venv`，回退 `uv run python`，等待健康默认 90s），`ScraplingUiController` 暴露 `POST /api/services/scrapling-ui/start` 与 `GET /api/services/scrapling-ui/status`；只由首页按钮点击触发，不做启动时自动拉起，也不在 `website` 关闭时强杀。
- `integration/skillfinder`：`SkillFinderProcessManager` 负责按需启动/复用 `website/skill-finder`（优先 `backend/.venv`，回退 `uv run python`，uvicorn 模块为 `app.main:app`，等待健康默认 90s），`SkillFinderController` 暴露 `POST /api/services/skill-finder/start` 与 `GET /api/services/skill-finder/status`；同样只由首页按钮点击触发，不做启动时自动拉起，也不在 `website` 关闭时强杀。
- `auth/WebsiteAuthUserRepository.java`：适配 `common` 的 `AuthUserRepository`，不直接写 SQL。
- `auth/dao/WebsiteAuthUserDao.java`：认证用户表 MyBatis DAO。
- `mapper/auth`：MyBatis XML Mapper，集中维护数据库 CRUD SQL。
- `demos/web`：基础 Web Controller 示例。
- `demos/oss`：OSS 示例代码。
- `demos/nacosdiscoveryconsumer`：Nacos 消费者示例。
- `demos/nacosdiscoveryprovider`：Nacos 提供者示例。
- `nacosdiscovery`：Nacos Discovery 配置。
- `prompt/controller/PromptConsoleController.java`：提示词控制台 API。
- `prompt/service`：提示词来源拉取、摘要、组合和注册服务。
- `prompt/library`：提示词库服务端化代码。`PromptLibraryController` 暴露 `/api/prompts/meta`、`/api/prompts`（服务端分页/搜索）、`/api/prompts/{id}` 与 `POST /api/prompts`（手动添加）；`PromptLibraryServiceImpl` 负责 meta 组装、LIKE 转义、详情映射和添加校验/大分类推导；`PromptLibraryDao` + `mapper/prompt/PromptLibraryMapper.xml` 访问 MySQL 的 `prompt_entry`/`prompt_source`/`prompt_group` 表。添加时未知小分类归入 `other`，首次添加自动创建 `manual` 来源，`entry_key` 为 `manual-{uuid}`，当前不加鉴权。
- `static/prompt-console`：提示词控制台前端和静态提示词库数据。页面为深色影院式设计，动效集中在 `prompt-console-motion.js`（本地 `js/vendor/gsap.min.js` + `js/vendor/ScrollTrigger.min.js`，均 3.12.5），`prefers-reduced-motion` 或脚本缺失时降级为静态。数据通过 `/api/prompts` 系列接口从 MySQL 读取，不再直接 fetch 本地 JSON；`prompt-category-groups.js` 保留为导入工具与 node 测试的映射数据源。
- `static/css/style.css`：站点样式。
- `static/js/script.js`：站点交互、四场景视频切换、登录注册和首页服务卡片健康检测；顶部不得增加账户操作以外的按钮或移动菜单。
- `static/img`：主页图标资源。
- `python-a/`：A 股自选股 AI 研究台，独立 ThreadingHTTPServer 服务，默认端口 `5174`。
- `quant-a/`：A 股量化研究台，独立 FastAPI 服务，默认端口 `5175`。
- `scrapling-ui/`：可视化爬虫工作台（汉化版 Scrapling UI），独立 FastAPI + React 服务，默认端口 `5176`，前端 dist 由后端托管，首页按钮点击启动。
- `skill-finder/`：AI 项目趋势追踪站（GitHub Trending 采集 + 排行展示），独立 FastAPI + Vue 3 服务，默认端口 `5177`，前端 dist 由后端托管，首页按钮点击启动；数据库与 `website` 共用腾讯云 MySQL 的 `xixi` 库，默认直接读取 `src/main/resources/application.yml` 的 `spring.datasource` 并解析 `WEBSITE_DB_*`，可用 `DATABASE_URL` 环境变量或自身 `backend/.env` 覆盖。原 `skill_finder` 的五张业务表数据已复制到 `xixi`，源库保留。`uv sync` 安装的 `cryptography` 用于 MySQL SHA-2 认证；首次接入仅补建缺失业务表，集成测试使用独立测试库。
- `integration/lottery`：`LotteryProcessManager` 负责按需启动/复用 `website/lottery`
  （执行 `python server.py --port 5179`，等待健康默认 60s），`LotteryController` 暴露
  `POST /api/services/lottery/start` 与 `GET /api/services/lottery/status`；只由首页按钮点击触发，
  不做启动时自动拉起，也不在 `website` 关闭时强杀。
- `integration/personalagent`：`PersonalAgentProcessManager` 负责按需启动/复用根目录 `personal-agent`
  （默认端口 5178，等待健康默认 90s），`PersonalAgentController` 暴露
  `POST /api/services/personal-agent/start` 与 `GET /api/services/personal-agent/status`；
  只由 03 Deep Woods 的“个人资料库”卡片点击触发，不做启动时自动拉起。
- `integration/local`：本机模型与视频服务管理，提供 strata / aimedia / h3 的状态、健康适配和启停接口。

## 配置约定

默认端口：

```properties
server.port=8080
```

子服务端口：

```text
python-a: 5174
quant-a: 5175
scrapling-ui: 5176
skill-finder: 5177
lottery: 5179
```

静态资源路径：

```yaml
spring:
  web:
    resources:
      static-locations:
        - classpath:/static/
```

数据库配置：

```yaml
spring:
  datasource:
    type: com.alibaba.druid.pool.DruidDataSource
    driver-class-name: com.mysql.cj.jdbc.Driver
```

连接参数使用 `WEBSITE_DB_URL`、`WEBSITE_DB_USERNAME`、`WEBSITE_DB_PASSWORD` 环境变量覆盖；默认指向腾讯云 `xixi` 库（`jdbc:mysql://49.232.128.132:3306/xixi`，JDBC 使用 `characterEncoding=UTF-8`），提示词库（`prompt_entry`/`prompt_source`/`prompt_group`）与认证（`auth_user`）共用该数据源。密码必须走环境变量，禁止提交真实密码。

⚠️ 严重警告：不要提交真实数据库密码。新增配置时使用环境变量，例如 `${WEBSITE_DB_PASSWORD}`。

数据库访问约定：

- 所有数据库 CRUD 都使用 MyBatis DAO 接口 + XML Mapper 映射器。
- DAO 接口放在对应业务包的 `dao` 子包中，类名以 `Dao` 结尾。
- Mapper XML 放在 `src/main/resources/mapper` 下，文件名以 `Mapper.xml` 结尾。
- 必须在 `application.yml` 显式配置 XML Mapper 扫描路径：

```yaml
mybatis:
  mapper-locations: classpath*:mapper/**/*.xml
  type-aliases-package: com.example.common.auth.model
  configuration:
    map-underscore-to-camel-case: true
```

- SQL 不写在 Controller、Service 或普通 Java 类里。
- 不再新增 `JdbcTemplate`、`PreparedStatement`、JPA Repository 或 Java 内联 SQL。
- 数据库表由开发者或运维提前创建，Java 启动流程不负责建表、补字段或写种子数据。

Python 子服务自动启动约定：

```yaml
python-a:
  auto-start:
    work-dir: website/python-a
    log-to-console: true

quant-a:
  auto-start:
    work-dir: website/quant-a
    log-to-console: true
```

- `log-to-console: true` 时，子服务日志会直接进入 `website` 的控制台。
- `log-to-console: false` 时，日志写入对应子服务目录下的 `server.out.log` 和 `server.err.log`。
- 单元测试必须关闭两个自动启动开关，避免测试启动外部 Python 进程。

`scrapling-ui` 点击启动约定：

```yaml
scrapling-ui:
  click-start:
    enabled: true
    work-dir: website/scrapling-ui
    command: ${SCRAPLING_UI_COMMAND:uv}
    port: 5176
    health-path: /api/health
    startup-timeout-seconds: 90
    log-to-console: true
```

- 不使用 `ApplicationRunner` 自动启动，只在首页按钮点击时调用启动接口。
- `command` 可由 `SCRAPLING_UI_COMMAND` 覆盖。默认 `uv` 时优先
  `backend/.venv/Scripts/python.exe`，缺失时执行 `uv run python`。
- 显式指定 Python 命令或完整路径时直接执行 `<python> -m uvicorn`，绕过 `.venv`；
  支持全局 Python 3.12+，不支持默认的 Python 3.9。在 backend 目录使用
  `uv pip install --python <python完整路径> -r pyproject.toml` 准备全局依赖，
  再运行 `<python> -m playwright install chromium`；设置用户环境变量后重启终端或 IDE。
- 启动器注入 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`PYTHONUNBUFFERED=1`，
  规避 Windows GBK 控制台 emoji 日志崩溃。
- `website.service-health.services` 聚合清单必须包含 `scrapling-ui`
  （`http://127.0.0.1:5176/api/health`），但聚合探测不触发启动。

`skill-finder` 点击启动约定：

```yaml
skill-finder:
  click-start:
    enabled: true
    work-dir: website/skill-finder
    command: uv
    port: 5177
    health-path: /api/health
    startup-timeout-seconds: 90
    log-to-console: true
```

- 不使用 `ApplicationRunner` 自动启动，只在首页按钮点击时调用启动接口。
- 启动命令为 `.venv/Scripts/python.exe -m uvicorn app.main:app`（venv 缺失时回退
  `uv run python -m uvicorn app.main:app`）；启动前要求 `frontend/dist/index.html` 已构建。
- `website.service-health.services` 聚合清单必须包含 `skill-finder`
  （`http://127.0.0.1:5177/api/health`），但聚合探测不触发启动。
`lottery` 点击启动约定：

```yaml
lottery:
  click-start:
    enabled: true
    work-dir: website/lottery
    command: ${LOTTERY_COMMAND:python}
    port: 5179
    health-path: /api/health
    startup-timeout-seconds: 60
    log-to-console: true
```

- 不使用 `ApplicationRunner` 自动启动，只在首页卡片点击时调用启动接口。
- 启动命令为 `python server.py --port 5179`，工作目录 `website/lottery`；启动器注入
  `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`PYTHONUNBUFFERED=1`、`LOTTERY_PORT`。
- 依赖 numpy / pandas / requests；首次启动若 `output/console.html` 不存在，会先执行
  `python main.py --console-only --port 5179` 构建（约 3 秒），再监听端口。
- `website.service-health.services` 聚合清单必须包含 `lottery`
  （`http://127.0.0.1:5179/api/health`），但聚合探测不触发启动。

## 代码规范

Java 命名：

- 类名使用 `UpperCamelCase`：`WebsiteApplication`、`BasicController`。
- 方法名和变量名使用 `lowerCamelCase`。
- 常量使用 `UPPER_SNAKE_CASE`。
- 包名全小写：`com.example.website`。
- Controller 类以 `Controller` 结尾。
- DAO 接口以 `Dao` 结尾。
- Configuration 类以 `Configuration` 或 `Config` 结尾。

Spring 约定：

- Controller 只放 HTTP 示例或页面接口，不承载复杂业务逻辑。
- 示例代码放在 `demos` 包下，生产化代码不要继续塞进 `demos`。
- 业务数据库访问放在 DAO + Mapper XML 中，Service 只处理业务规则和事务边界。
- Nacos 相关代码集中在 `nacosdiscovery` 和 `demos/nacosdiscovery*`。
- 新增配置写入 `application.yml`，不要重新引入重复的 `application.properties`。

前端静态资源约定：

- CSS 修改放在 `src/main/resources/static/css/style.css`。
- JS 修改放在 `src/main/resources/static/js/script.js`。
- 图片放在 `src/main/resources/static/img`。
- 提示词控制台放在 `src/main/resources/static/prompt-console`。
- 页面引用资源时使用相对路径，不使用本机绝对路径。
- 首页各场景的文案配置在 `index.html` 对应按钮的 `data-scene-title` / `data-scene-statement` / `data-scene-badge`；`data-scene-dock` 指向该场景的服务目录，`setupSceneContent` 监听现有 `xixiscenechange` 事件切换内容。01 Golden Hour 保持原诗句、布局和 9 个入口；03 Deep Woods 的 `deep-woods-service-dock` 展示“个人资料库”（5178，点击启动）；02 Still Water、04 Quiet Dawn 使用各自独立目录，空目录隐藏，新增服务沿用 `service-card`。不要修改四场景的背景动画。
- 首页四段远程场景视频保持原样，仅展示风景，不添加车窗图片覆盖或车窗晃动动画；保留文字可读的暗角、颗粒和黑色/渐变降级背景，外部媒体失败不得影响服务入口、鉴权或健康检测。
- 四段场景片各 10.04 秒且首尾不是同一镜头，原生 `loop` 会先停帧再跳回第一帧。循环必须继续走 `setupVideoSwitcher` 的交叉淡化补层：`.scene-video--loop` 由脚本动态创建（不写进 `index.html`，保持四段原视频与 URL 不变）、默认 `paused` + `preload="none"` + `aria-hidden`，在最后 1 秒从第一帧起播并接管，`loopFadeMs = 1000` 必须与 `.scene-video--loop` 的 `opacity` 过渡一致；`video.play()` 被拒绝、`readyState` 不足或片段短于 2.5 个淡化区间时退回原生 `loop`。**关键**：补层排在全部场景视频之上、`.scene-shade` 之下，两层是上下叠放，只允许上层补层改变不透明度，下层 `.scene-video.is-active` 必须始终保持 `opacity: 1`——两层同时半透明时合成覆盖率只有 `上层 + 下层 × (1 − 上层)`（中点 75%），会透出深色背景，观感就是“突然黑一下”；不要重新引入 `is-loop-hidden` 之类的原视频淡出。切换场景必须在 `reveal()` 里等新视频 `readyState ≥ 2`（最多 `sceneRevealTimeoutMs = 2000`）再执行 `showVideo()`，否则会把旧画面淡出到只剩背景；接管时用 `getAnimations()` 同步 `ken-burns` 相位。改动该逻辑后运行 `node website/src/test/js/homepage-video-loop.test.js`。
- 首页保持单个 `100svh` 视口且不产生页面级滚动；服务 Dock 桌面端为单行 9 列且 9 个入口一屏全部可见（列宽用 `repeat(9, minmax(0, 1fr))` 随容器自适应收缩，不产生横向滚动），1180px 及以下才切换为定宽列并只允许服务 Dock 自身横向滚动，任何宽度都不允许换行成两排。
- `script.js` 的点击启动不得再打开“正在启动”中间页面：启动进度只在服务卡片内展示（“启动中…”→ 就绪后自动打开或提示“已启动 · 点击打开”）。

## 测试策略

测试框架：

- JUnit 5
- Spring Boot Test

运行测试：

```bash
mvn -pl website -am test
```

### 一键离线回归

从仓库根目录执行 `python scripts/run-regression.py`。若当前在其他目录，传入脚本的绝对路径。脚本运行四份 Node 测试、模型路由 unittest、两个部署副本只读检查以及健康检查、模型路由和个人资料库的 Maven 离线测试。全部通过返回 0，检查失败返回 1，只有运行工具缺失时返回 2。独立的本地健康诊断 CLI 见 `tools/service-doctor/README.md`。

当前已有测试：

```text
src/test/java/com/example/website/WebsiteApplicationTests.java
src/test/java/com/example/website/integration/PythonAAutoStartRunnerTest.java
src/test/java/com/example/website/integration/QuantAAutoStartRunnerTest.java
src/test/java/com/example/website/integration/scrapling/ScraplingUiProcessManagerTest.java
src/test/java/com/example/website/integration/scrapling/ScraplingUiControllerTest.java
src/test/java/com/example/website/integration/skillfinder/SkillFinderProcessManagerTest.java
src/test/java/com/example/website/integration/skillfinder/SkillFinderControllerTest.java
src/test/java/com/example/website/integration/lottery/LotteryProcessManagerTest.java
src/test/java/com/example/website/integration/lottery/LotteryControllerTest.java
src/test/java/com/example/website/integration/health/*.java
```

测试要求：

- 新增 Controller 时补充 Spring MVC 或 context 测试。
- 新增 DAO/Mapper SQL 时覆盖成功路径、空结果和主要失败路径。
- 修改 Nacos 示例时，测试中不要依赖真实 Nacos 服务。
- 修改数据库相关配置时，测试中不要连接远程 MySQL。
- 修改静态页面后，启动服务并访问 `http://localhost:8080/` 手动验证。
- `HomepageStaticAssetsTest` 断言首页 Dock 卡片数 = `website.service-health.services` 条数 - `GROUPED_LOCAL_SERVICES`（当前 3：Strata、AIMedia、H3 合并入口）+ `LOCAL_ONLY_ENTRIES`（当前 2：Prompt Console、模型与视频管理页）。调整入口时同步 `index.html`、布局和测试常量；仅合并入口时保留 `application.yml` 中各服务的独立健康探测。
- 修改两个 Python 子服务自动启动逻辑时，至少运行对应 `*AutoStartRunnerTest`，并确认工作目录解析仍支持从仓库根目录和 `website/` 模块目录启动。
- 修改 `scrapling-ui` 点击启动逻辑时，至少运行 `ScraplingUiProcessManagerTest` 和 `ScraplingUiControllerTest`；测试不得启动真实 Python 进程或浏览器，不得连接真实端口。
- 修改 `scrapling-ui` 后端时，运行 `cd website/scrapling-ui/backend && uv run python -m unittest discover -s tests -v`。
- 修改 `skill-finder` 点击启动逻辑时，至少运行 `SkillFinderProcessManagerTest` 和 `SkillFinderControllerTest`；测试不得启动真实 Python 进程，不得连接真实端口。
- 修改 `skill-finder` 后端时，运行 `cd website/skill-finder/backend && .venv/Scripts/python.exe -m pytest -q` 和 `ruff check .`；修改前端时运行 `npm run lint && npm run typecheck && npm run test -- --run && npm run build`。

覆盖率目标：

- Controller 新增分支不低于 70%。
- 配置类至少覆盖 Spring context 能正常启动。
- 纯静态资源改动不强制覆盖率，但必须手动验证页面可访问。

## 提交前检查

```bash
mvn -pl website -am clean test
```

需要手动启动验证时执行：

```bash
mvn -pl website -am spring-boot:run
```

检查清单：

- **关键**：修改首页入口、提示词控制台、自动启动配置、Python 子服务集成、端口、API、静态资源目录或测试方式时，同步更新 `website/AGENTS.md`、`website/README.md` 和根文档。
- **关键**：不要把正式业务代码继续放进 `demos` 包。
- **关键**：新增或修改数据库 CRUD 时同步更新 DAO、Mapper XML、模型和测试。
- **关键**：静态资源路径必须能从 `classpath:/static/` 加载。
- **关键**：五个 Python 子服务必须保留在 `website/python-a`、`website/quant-a`、`website/scrapling-ui`、`website/skill-finder`、`website/lottery` 下，但不要加入 Maven modules；`scrapling-ui`、`skill-finder` 和 `lottery` 只由首页按钮点击启动。
- **关键**：`scrapling-ui` 的 `.venv/`、`node_modules/`、`frontend/dist/`、`backend/jobs.db`、`*.log` 不提交；前端 dist 由 `npm run build` 生成。
- **关键**：`skill-finder` 的 `.venv/`、`node_modules/`、`frontend/dist/`、`backend/.env`、`backend/.secrets/`、`*.log` 不提交；前端 dist 由 `npm run build` 生成。
- **关键**：数据库密码和 Nacos 密码使用环境变量。
- ⚠️ 不要在单元测试中连接真实 Nacos、真实 MySQL 或外部 OSS。
- ⚠️ 不要提交 `target/`、IDE 缓存、Python `__pycache__/`、`.pytest_cache/`、本地密钥或服务日志。

## 本机模型与视频服务管理（2026-10-11）

首页 Dock 将「Qwen 本地模型」「视频操作台」「H3 音视频模型」合并为「模型与视频」，共8个入口。统一卡片进入 `/local-services/index.html`，首页每30分钟检测管理页可访问性；三个服务仍在管理页分别操作，每30分钟刷新各自状态，统一健康检查清单保留三项探测。

管理页借鉴 MotionSite 网站的排版与动效思路，采用独立设计的深色冰蓝工作台、Geist 字体与紧凑三服务网格；首屏背景使用 MotionSite 背景库的 Pulse 等离子光环静音循环视频，不复用其他操作台的风景素材。桌面三列、平板两列且 H3 横跨整行、手机单列；原有服务按钮、API 和30分钟状态刷新保留。动效集中在 `static/local-services/motion.js`，复用本地 GSAP/ScrollTrigger 3.12.5，提供首屏入场、能力速览切换、文字渐显及几何视觉缩放/淡化。视频与海报位于 `static/local-services/media/`（10秒、1280×720、24fps、约2MB）；支持顶部暂停/播放、隐藏标签页及滚出背景区域自动暂停，视频失败保留 JPG 与 CSS 背景，`prefers-reduced-motion` 下不下载视频。背景播放不依赖 GSAP；动效库缺失时保留可操作页面，无需 npm 构建。

| 服务 | 本机目录 | 端口 | 管理操作 |
| --- | --- | --- | --- |
| Strata / Qwen3.8-Flash-Next IQ3_S | `F:/model/Strata` | 9999 | 只启动服务、加载模型、卸载模型、关闭服务 |
| AIMedia 视频操作台 | `D:/Code/Java_Code/AIMedia` | 8190 | 启动、关闭、打开操作台 |
| H3 / ComfyUI 生成引擎 | `D:/Code/Java_Code/AIMedia/ComfyUI` | 8189 | 启动引擎、释放模型内存、关闭引擎、打开 ComfyUI |

三个应用继续独立运行，不加入 Maven modules，不随 website 自动启动或关闭。`website.local-services` 配置本机目录、端口和180秒启动等待；目录可通过 `STRATA_HOME`、`AIMEDIA_HOME` 覆盖。入口仅适用于运行这些应用的 Windows 主机；使用 UU 远程操作主机上的浏览器也可管理。

API：`GET /api/services/local/{strata|aimedia|h3}/status`；同路径 `/health` 在在线时返回HTTP200、`success=true`和稳定的`service`标识，离线时HTTP503。`POST /api/services/local/{service}/{start|load|unload|stop}` 执行操作，只有Strata支持load，AIMedia不支持unload。修改请求需 `X-Love530-Local: 1`；仅允许回环地址、localhost/127.0.0.1/::1 Host与同源Origin，不能传入自定义命令或PID。统一 `/api/services/health` 默认检查 11 个目标，包括上述三个本机适配与八个独立服务。

Strata以`--lazy`启动服务，第一条生成请求或「加载模型」按钮才加载权重；「卸载模型」保留API和权重文件。AIMedia通过已有GPU Python环境直接启动操作台后端，不在这里顺带启动H3。H3在提交生成任务后才加载权重，页面不把「引擎在线」或「权重已安装」谎报为「模型已加载」。释放调用ComfyUI `/free`，是异步请求，作用于该引擎缓存的模型，不删除权重和作品。视频队列或操作台作业忙碌时返回409，无法确认队列时拒绝释放/停止。启动生成任务前先卸载Qwen，避免两个大型模型争用内存和显存。

后端位于 `website/src/main/java/com/example/website/integration/local/`，停止脚本为classpath中的 `local-services/stop-service.ps1`。只停止命令同时匹配项目路径、脚本与端口的Python进程，拒绝停止占用端口的其他应用。日志在启动应用的工作目录中，文件名`love530-service.log`。新页面不需要npm构建。

验证：`mvn -pl website -am test -Dtest=LocalServicesManagerTest,LocalServicesControllerTest,ServiceHealthPropertiesTest,ServiceHealthAggregatorTest,ServiceHealthCheckerTest,ServiceHealthControllerTest,HomepageStaticAssetsTest,WebsiteApplicationTests -Dsurefire.failIfNoSpecifiedTests=false`；`node --check website/src/main/resources/static/local-services/app.js`；`node website/src/test/js/homepage-motion.test.js`。单元测试不加载真实模型、不生成视频、不连接真实数据库。

## 个人长期资料库（Obsidian + Quartz，03 Deep Woods，5178）

健康档案默认展示最近检查、可核对的摘录、原报告建议和各次报告原值对照；人体图默认显示在报告选择器下方，健康文档双链可展开查看。详情的 `analysis_version` 区分空档、旧稿和新版。各资料领域通过 `GET /api/vault/overview?domain=...` 读取双链与编辑统计。

个人资料库总览展示真实 Vault 的最近笔记和至多 48 个节点的双链图（`GET /api/vault/overview`）。`GET /api/note` 同时提供安全 Markdown 阅读预览与反向链接，完整图谱、嵌入和 Bases 仍通过私有 Quartz 浏览页查看。

个人资料总览可一次导入多份体检报告，每份单独确认检查日期，归档失败项可重试。健康档案按年份分组，使用 `/api/exams` 逐份归档，经 `GET /api/exams/{id}/preview` 本地预览 PDF 文字。确认后可将按页提取的文字交给所选文本模型，后端校验摘录与页码。扫描件和复杂版面可确认发送完整 PDF 给 DeepSeek Flash。旧解读可重新生成新版，原件和历次草稿保留。通用导入使用 `/api/documents`。具体路径和验证见 `personal-agent/README.md`。

`personal-agent/` 是 Java 8 + Spring Boot 2.6.13 Maven 模块，服务标识仍为 `personal-agent`，监听 `127.0.0.1:5178`。内容已替换为真实 Obsidian Vault 的个人长期资料库，覆盖财务、健康、工作、生活等领域；网页提供资料记录、关键词搜索、版本校验编辑，以及用户确认来源后发起的 AI 分析。Quartz 5.1.0 的真实源码位于 `personal-agent/quartz/`，负责阅读、全文搜索、双链图、反向链接与原生 `.base` 视图。

首次执行 `cd personal-agent/quartz && npm ci`（Node.js 22+），再从根目录执行 `mvn -pl personal-agent -am package`。运行主类 `com.example.personalagent.PersonalAgentApplication` 或已构建 jar。03 Dock“个人资料库”点击启动方式、`POST /api/services/personal-agent/start`、`GET /api/services/personal-agent/status` 和健康聚合顺序保持不变；website 不自动启停它。

Windows 默认主资料源为 `D:/个人资料/Obsidian Vault/`，个人记录、AI 报告、Bases、模板与附件统一保存在此。服务状态目录仍为 `%LOCALAPPDATA%/Love530/PersonalAgent/`：`knowledge-state.json` 只保存登录哈希、仓库选择和分析状态，`note-backups/` 保存网页编辑前副本，`quartz-builds/` 保存私有浏览快照与构建日志。非 Windows 默认 Vault 为服务状态目录下的 `knowledge-vault/`。旧 `agent.mv.db`、旧 `vault/` 和备份保留，不自动导入或删除。新空间首次需要设置密码。可用 `PERSONAL_AGENT_DATA_DIR`、`PERSONAL_AGENT_VAULT_DIR`、`PERSONAL_AGENT_QUARTZ_DIR`、`PERSONAL_AGENT_NODE_COMMAND` 覆盖路径或命令；Windows 的 DATA_DIR 不改变默认 Vault。网页已保存的仓库选择优先，修改默认路径不自动搬移旧文件，已有资料需先完整复制再在设置中连接。测试必须显式指定临时 Vault，不能读写 D 盘真实资料。

健康接口仍为 `GET /api/health`，仅返回 `success=true, service=personal-agent`。其余业务 API 为 `/api/vault`、`/api/vault/{connect,initialize}`、`/api/notes`、`/api/note?path=...`、`/api/analyses/preview`、`/api/analyses`、`/api/quartz`、`/api/quartz/build`。API 与 `/library/**`（含搜索索引和附件）均受本机 Session 保护；写请求校验 CSRF。跨本机主机名的首页顶层导航例外保留。资料变化后旧 Quartz 快照停止提供，需点击生成/更新。

AI 沿用统一文本模型入口；服务原配置由根目录 `model.properties` 的 `service.personal-agent` 提供。先预览并选择最多8份资料，再明确确认发送片段。保留资料日期、来源、版本哈希，排除 AI 报告、草稿、归档、模板及 `ai_exclude: true`。报告写入 `80-AI分析/` 并标记为待核对草稿，不覆盖事实。无后台自动上传。详细 API、属性约定、限制与部署方式见 personal-agent/README.md。

验证：`mvn -pl personal-agent -am test`；website 入口回归 `mvn -pl website -am test -Dtest=HomepageStaticAssetsTest,PersonalAgentControllerTest,PersonalAgentProcessManagerTest -Dsurefire.failIfNoSpecifiedTests=false`；`node --check personal-agent/src/main/resources/static/app.js`。测试使用构造 Vault 与模型替身，不读取私人内容或调用真实模型。
## Skill Finder 云端日报与视频

日报视频现已接入内部 `video-renderer/`（Remotion 4.0.536 + React/TypeScript + Node.js 22+），默认 1080×1920 / 30 FPS；配音默认 MiMo，`MIMO_API_KEY` 仅在私有环境配置，字幕通过实际音轨转写。新增 `DAILY_VIDEO_RENDERER`、`DAILY_TTS_PROVIDER`、`DAILY_NODE_COMMAND`、`DAILY_WHISPER_MODEL`、`DAILY_ASSETS_DIR` 与素材完整性检查；`legacy` 可显式回退。先安装渲染依赖和 `uv sync --extra captions`，样片用 `python -m app.daily.cli sample`。详细配置、数据目录、测试和 Docker 资源要求见 [skill-finder/docs/remotion-integration.md](skill-finder/docs/remotion-integration.md)。既有 API、端口、Vue 页面与审核发布约定不变。

`website/skill-finder` 继续作为独立 FastAPI + Vue 微服务，以 love5000 版本为准同步到 `C:/Code/skills-finder`。云端采用 Docker + Nginx，入口 `https://49.232.128.132/skill-finder/`，日报审核 `/skill-finder/daily-reports`，后端仅监听回环 15177，本机开发仍用 5177。复用 xixi 原五张业务表，不重建共享库。

服务器北京时间 07:10 采集、07:30 制作（07:45 重试）、08:00 送达；当前 QQ 按用户要求暂不配置。成品包括文字日报、中文配音、字幕与竖屏视频，GitHub 当日 AI 项目不足十项时如实标注。DeepSeek 使用通用 `INTRO_API_KEY`、`INTRO_API_BASE`、`INTRO_MODEL` 私有配置，不把凭据写入 Git。

新增 API 前缀 `/api/v1/daily-reports`：GET 列表、GET `/{date}`、GET `/{date}/files/{filename}`；管理接口 POST `/generate`、POST `/{date}/review`、POST `/{date}/publish`；抖音登录 POST/GET `/publisher/login` 和受认证的 GET `/publisher/login/screen`。管理接口要求 X-Admin-Key，并只允许 HTTPS 或本机 SSH 隧道。发布必须绑定具体视频、口播和文案的人工批准；未登录不发布，结果不确定不自动重发。

`backend/app/daily/` 管理生成、媒体、审核摘要与发布适配；`backend/data/`、`.secrets/`、云端 `/var/lib/skill-finder/` 为私有运行数据，不提交。`deploy/` 维护 Docker、cron、Nginx 与 IP 证书续签；OpenClaw 在独立 Node 容器内仅监听回环 18789，QQ/抖音必须如实区分未配置、等待登录与已送达/已发布。完整部署、凭据边界与验证见 `website/skill-finder/docs/cloud-daily-report.md`（模块内为 `docs/cloud-daily-report.md`）。本机首页点击启动约定保持不变。


## 视频制作操作台

`/daily-reports` 现为一键制作操作台：展示采集、筛选、脚本、素材、配音、字幕、渲染、审核、抖音发布与可选 QQ 通知。真实状态每 5 秒刷新，任务目录中的 `workflow.json` 保存步骤、计数、时间与脱敏错误，`render-progress.json` 保存实际渲染帧数；历史任务无记录时明确标注，不补造进度。素材可从页面上传（MP4/PNG/JPEG，最大 100 MiB，有 HTTPS 来源），只允许本期项目，生成后使用固化副本。新增 GET `/api/v1/daily-reports/console?day=YYYY-MM-DD`、PUT `/{day}/assets/{owner}/{repo}?filename=...&source=...`（原始文件请求体）、POST `/{day}/notify` 与只读样片文件入口 `/samples/{id}/files/{filename}`（均位于 daily-reports 前缀下）；管理写操作继续使用 X-Admin-Key + HTTPS/本机连接，已进入审核的版本不可被一键运行覆盖。操作台“模板编辑”已内置 React/TSX 源码编辑、可视化样式、Remotion Player、编译错误定位、保存启用与版本恢复，入口为 `/daily-reports?panel=template`，无需另开 Studio。仅允许编辑 `src/video.tsx`、`src/demo.tsx`、`src/types.ts`；`root.tsx` 只读。新增 `/api/v1/daily-reports/template` 的 GET/PUT、POST `/preview`、POST `/restore`，源码与编译使用现有管理鉴权。保存前通过类型检查、打包和一帧真实渲染，版本原子切换；新版本只影响后续生成，已有成片和审核不变。不可变源码、样式与预览缓存位于日报目录同级 `video-template/`（默认 `backend/data/video-template/`），使用现有数据持久卷与 5177 端口。完整使用、API 和验证说明见 [操作台说明](skill-finder/docs/production-console.md)。


## 榜单刷新状态与网络故障处理

`GET /api/v1/stats` 在原有字段外返回 `last_run_id`（最新任务编号，可空）与
`last_run_error`（失败时的固定用户提示，可空）；错误提示不包含原始异常、凭据或连接串。
采集启动后先提交 `RUNNING`，首页提交刷新前记录最新任务编号，每 5 秒轮询，
即使没看到中间运行状态也能识别新任务的失败，恢复按钮并显示原因。历史失败不会误判为本次失败，
请求提交期间禁止重复点击，离开页面后停止轮询。
成功及部分成功任务保留原 30 分钟冷却；`FAILED` 允许立即重试，MySQL 命名锁继续防止并发采集。
`backend/.env` 的 `TRENDING_PROXY` 同时用于 GitHub Trending、GitHub API 与 README 请求；
按本机网络填写可用代理，不在仓库中写入私人代理凭据。连接超时保留已有榜单，不伪造采集成功。

验证：后端运行 `python -m pytest -q` 与 `python -m ruff check .`；
前端运行 `npm run lint`、`npm run typecheck`、`npm run test -- --run`、`npm run build`。
修改前端后重建 `frontend/dist`，后端修改后重启 5177 服务。

中文简介服务缺少密钥或返回 HTTP 401 时立即停止本轮简介生成，不再换模型、拆分批次或去掉 README 重试；榜单与 Star 数据正常保存。其他内容失败仍保留原降级逻辑，更新私有密钥后后续采集可继续补全简介。


## 健康巡检频率与 IDEA 日志

`ServiceHealthMonitor` 在 website 的 `ApplicationReadyEvent` 后统一巡检一次，完成后每半小时巡检；
`GET /api/services/health` 返回最近结果，打开或刷新多个首页不会额外请求子服务。
首页按 `data-health-service` 项目名匹配聚合结果，每半小时读取一次；website 自身页面入口仍检查页面可达性。
本机模型管理页首次进入读取状态，此后每半小时自动刷新，手动启停、加载及卸载后立即更新状态。
后台巡检不依赖浏览器是否打开。启动子服务时必要的就绪确认保留，不使用半小时周期等待启动。

配置在 `website/src/main/resources/application.yml`：
`website.service-health.check-interval-ms: 1800000`（毫秒），
`website.service-health.scheduled-enabled: true`；测试设置后者为 false，避免后台访问真实服务。
健康日志统一包含 `[健康检查][项目=skill-finder]` 等明确项目名，以及状态、HTTP 状态码和耗时；
本机模型状态日志也携带 strata / aimedia / h3 项目名，不记录凭据。
IDEA 中重新运行 `WebsiteApplication` 后生效，浏览器刷新首页以加载新脚本。
验证：`mvn -pl website -am test`、`node website/src/test/js/service-health.test.js`、
`node website/src/test/js/homepage-motion.test.js`。定时测试通过捕获调度回调模拟半小时流逝，无需实际等待。


## 中文介绍生成与完成状态

中文介绍在采集阶段生成、写入数据库，详情页只读取已保存的介绍，不在访问详情时自动调用模型。
启用 `INTRO_ENABLED` 后，介绍认证失败或缺失输出会将采集标记为 `PARTIAL`，保留真实榜单，
并在现有 `collection_runs.error_summary` 记录 `INTRO_AUTH_FAILED` / `INTRO_GENERATION_FAILED` 与缺失数量。
`GET /api/v1/stats` 增加可空字段 `last_run_warning`；首页部分完成时更新榜单并显示警告。
详情页缺失介绍显示“暂未生成中文介绍”，不把缺失误称为正在生成。

配置可使用 `INTRO_API_BASE=https://api.deepseek.com`、`INTRO_MODEL=deepseek-flash`，
或显式指定其他实际可用模型。`INTRO_API_KEY_FILE` 可引用已有本机私有密钥文件，优先于 `INTRO_API_KEY`；
支持纯文本或 JSON 中的 `INTRO_API_KEY`、`DEEPSEEK_API_KEY`、`intro_api_key`、`deepseek_api_key`、`api_key`。
只读取、不复制密钥文件内容，不向日志或响应输出密钥、私有路径或文件内容；私有配置不提交。
修复配置后可通过已有受鉴权的 `POST /api/v1/admin/introductions?limit=100&order=daily` 补全缺失介绍，
不必重新采集榜单；接口继续返回 accepted，由原后台补全逻辑保存结果，不改写已有介绍。
前端改动后运行 lint/typecheck/test/build，后端运行 pytest 与相关 Ruff 检查，重启 5177 后生效。

## 统一模型入口（2026-10-20）

主页提供全局文本模型选择，python-a、scrapling-ui、skill-finder、personal-agent 提供“跟随主页 / 服务原配置 / 独立模型”，下一次请求生效。图片、视觉、语音和视频保留专用模型；quant-a 与 lovestory 当前没有文本模型调用。

OpenCode Go 从根目录私有 `model.properties` 的 `opencode-go.*` 读取，使用 OpenAI 兼容的 `/models` 探测与 `/chat/completions` 生成，请求模型 ID 为 `deepseek-v4.1-flash`。生成请求携带本站客户端标识和独立的 `X-OpenCode-Session`。该域名位于 Cloudflare 之后，缺省 Java 客户端标识会被以 HTTP 403 `error code: 1010` 拒绝，因此**目录探测与生成都必须走 `ModelHttp#requestOpenCodeGo`**（附带 `User-Agent: love5000-website/1.0` 与 `X-OpenCode-Session`），否则选择器里的 `deepseek-v4.1-flash` 会一直显示“未就绪”。
website 的 `/api/models` 提供目录核验、选择持久化和文本代理，状态文件为根 `.runtime/model-routing.json`，仅存模型 ID、不存密钥；Java 客户端在 common，Python 公共源码在 website/model-routing，部署副本 _model_routing.py 随各服务打包。原有认证保留。未选择时保留原逻辑，已选择但网关离线时报错。
共享选择器源为 website/src/main/resources/static/model-picker/picker.js，修改后执行 `python scripts/sync-model-picker.py`，或用 `python scripts/sync-model-picker.py --check` 只读校验；React/Vue 修改后重新构建 dist。图片工作台新增独立图片模型下拉与 `OPENAI_IMAGE_MODELS` 白名单，支持 JSON/multipart 的 `model` 字段。
完整盘点、API、边界与验证见 [统一模型入口](../docs/model-routing.md)。跨模块验证 `mvn test`；公共 Python 客户端验证 `python -m unittest discover -s website/model-routing`。

### MiMo V2.6 文本接入（2026-10-20）

统一模型目录新增 Xiaomi MiMo 的 `mimo-v2.6-pro`、`mimo-v2.6-flash`。website 优先读取环境变量 `MIMO_API_KEY` / `MIMO_API_BASE` / `MIMO_CHAT_MODELS`，缺失时复用 Skill Finder 私有 `.env`；密钥不复制、不回显。默认地址为官方 `https://api.xiaomimimo.com/v1`，模型列表与真实 `/models` 交集校验，过滤 ASR/TTS、旧版和未显式配置的定制型号。
主页与微服务原有选择器自动展示两个文本模型；原有选择、MiMo TTS 模型与配音保持不变。网关按官方规范将 `max_tokens` 转换为 `max_completion_tokens`，默认关闭深度思考，JSON 模式原样保留；显式开启思考时移除自定义采样参数。回归运行 `mvn -pl website -am test`，详见统一模型入口文档。

## 文本模型调用收敛（2026-10-21）

integration/models 增加 POST /api/models/complete/{service}；目录探测使用独立锁并发布不可变快照，已有模型查询/生成不被慢速刷新阻塞。
生成使用 `POST /api/models/complete/{service}`：200 返回统一模型结果，204 明确使用服务原配置；`effective` 只用于状态展示，旧 `chat` 保留兼容。超时或 HTTP 错误不回退；只有连接被拒绝且状态确认无统一选择时允许离线原配置。
Python 公共源码改动后执行 `python scripts/sync-model-routing.py`，再执行 `--check` 与公共 unittest；副本随服务部署，只改公共源码。回归运行 `mvn -pl website,personal-agent -am test`、python-a/Scrapling unittest 及 Skill Finder pytest；详见 [统一模型入口](../docs/model-routing.md)。

## Skill Finder 一键视频质量升级（2026-10-23）

保留 Remotion + FFmpeg/ffprobe + MiMo 和一键制作流程。默认模板升级为分阶段镜头、宽幅来源演示与两行字幕，H.264 使用 CRF 18 / medium；口播清理展示语法，完整句控制在 360 字内并保留限制条件。长字幕仅按实际词边界拆分，音频采用实测双遍响度和整片检测。新增可选 `DAILY_BGM_FILE` / `DAILY_BGM_SOURCE`（本地授权配乐与 HTTPS 来源），配乐在付费 TTS 前预检并固化到本期目录，人声出现时自动压低。结果写入私有 `render-result.json` 的 `audio_mastering`；验收失败不进入待审核。历史视频和私有模板版本不被覆盖；已有私有模板需手工合并新默认源码。配置、数据文件、运行与测试见 [视频质量升级](skill-finder/docs/video-quality-upgrade.md)。

## HyperFrames 可切换视频引擎（2026-10-26）

新增内部 `hyperframes-renderer/`（官方 producer/engine/core 0.8.186 + GSAP 3.13.0，Node.js 22+），通过 `DAILY_VIDEO_RENDERER=hyperframes` 选择；默认使用 HyperFrames，Remotion 保留为备用引擎（`DAILY_VIDEO_RENDERER=remotion`），legacy 仍可显式选择，失败不自动换引擎。新增 `HYPERFRAMES_BROWSER_EXECUTABLE` 与 `HYPERFRAMES_CONCURRENCY`（默认 1，范围 1–8），复用原素材、配音、实测字幕、FFmpeg 母带与审核流程。模板编辑 API 增加 engine 标识，HyperFrames 仅编辑 `src/template.html` / `src/demo.html`，版本隔离在日报同级 `video-template/hyperframes/`；原 Remotion 模板保持原位置。临时 `.hyperframes-project-*` 只包含固化媒体与模板，任务结束清理，真实验收后生成正式结果。样片命令按当前引擎生成自身演示，Docker 构建同时包含两套引擎；不新增端口或 Dock。配置、模板 API、数据、测试和部署见 [HyperFrames 接入](skill-finder/docs/hyperframes-integration.md)。

## 开奖数据操作台（01 第 9 个入口，5179）

`lottery` 的 `/selection` 选号工具调用 `GET /api/selection`；它只读历史 CSV，支持随机、冷热、遗漏和时间衰减方法。接口和测试见 `lottery/README.md`。

从仓库根目录运行 `python -X utf8 website/lottery/scripts/selection_backtest.py`
可只读回测选号方法；方法、参数和限制见 `lottery/README.md`。

`website/lottery` 是独立 Python 服务，提供双色球/大乐透历史数据操作台与研究报告：
6466 期官方开奖（双色球 3523 期、大乐透 2944 期）、精确组合分布、假设检验与多重比较校正、
8 种选号策略的时间外回测、期望值与蒙特卡洛，以及可任意排序/筛选/走势/透视的前端。

`GET /api/health` 返回 `success=true` 与当前数据截止期次；`POST /api/update` 增量抓取官方最新一页，
校验后追加、备份并只重建操作台，日志以纯文本流回页面；同源页面（`http://127.0.0.1:5179/`）的
「刷新数据」按钮直接调用该接口，`file://` 打开时按钮只提示通过服务访问。更新走
`scripts/update_daily.py`（`--build-target console --console-port 5179`），异常时不动现有数据；
每次写入前备份到 `data/backup/<时间戳>/`。

首页 01 Golden Hour 由 8 个入口扩为 9 个（第 09 张卡片 `data-health-service="lottery"`），
Dock 列宽改为 `repeat(9, minmax(0, 1fr))`，徽标文案同步为“9 个入口”。新增或调整入口后需
同步 `HomepageStaticAssetsTest` 中的卡片数与健康清单末尾断言。

验证：`mvn -pl website -am test -Dtest=HomepageStaticAssetsTest,LotteryProcessManagerTest,LotteryControllerTest -Dsurefire.failIfNoSpecifiedTests=false`；
服务本身可用 `cd website/lottery && python server.py` 单独启动，访问 `http://127.0.0.1:5179/api/health`。

## 统一模型的浏览器跨域预检（2026-11-16）

个人资料库（5178）沿用主页统一模型路由；未单独指定模型时跟随 global，无需复制模型密钥。需要先在8080主页选择一个具体的全局文本模型；如果 global 为空，继承状态为 true 但统一模型未启用，各服务按原配置处理。

`ModelRoutingController` 为 `/api/models/**` 声明受限本机 CORS 来源（8080、5174、5176、5177、5178；localhost/127.0.0.1/IPv6回环），允许 Content-Type 与 X-Love530-Model。真实 OPTIONS 预检由 Spring MVC 在控制器之前处理，不能仅依赖控制器手写响应头。写请求自定义头、本机限制与“浏览器不能直接调用生成接口”的边界继续保留。

验证使用真实 MVC 配置：`mvn -pl website -am test "-Dtest=ModelRoutingControllerTest,ModelRoutingCorsIntegrationTest,ModelRoutingServiceTest,MimoModelRoutingTest" "-Dsurefire.failIfNoSpecifiedTests=false"`。CORS 声明修改后重启 website，再从5178验证 OPTIONS 与模型目录读取。
