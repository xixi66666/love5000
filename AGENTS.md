# AGENTS.md

## 项目概述

`love5000` 是一个 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目，父工程 artifactId 为 `love530`。当前模块：

- `common`：公共能力模块，提供 OSS 自动配置、上传工具，以及通用登录/注册/Session 鉴权能力。
- `lovestory`：恋爱相册 Web 应用，提供静态页面、照片上传、照片列表、删除接口、留言板功能和吉他视频卡片模块。
- `website`：个人主页/展示站点 Web 应用，包含主页静态资源、Web Demo、OSS Demo、Nacos Discovery 示例和个人博客微应用。
- `imagetemplate`：图片提示词模板 Web 服务，提供模板库检索、prompt 渲染、直接提示词模板和 OpenAI 图片生成能力。
- `python-a`：A 股自选股 AI 研究台，作为独立 Python 微应用接入，不加入 Maven 聚合模块。
- `quant-a`：A 股量化研究台，作为独立 FastAPI 微服务接入，不加入 Maven 聚合模块，不写入 `python-a` 的 Obsidian 目录。

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

**关键**：`python-a` 是独立 Python 微应用，不是 Java Maven 模块，不要把它加入父 `pom.xml` 的 `<modules>`。Java 侧只负责入口链接、反向代理或接口转发，不把 Python 业务逻辑改写进 Controller。

**关键**：`quant-a` 是独立 FastAPI 微服务，不是 Java Maven 模块，不要把它加入父 `pom.xml` 的 `<modules>`。它的数据、配置和测试保持在 `quant-a/` 内，不写入 `python-a/obsidian-vault/`。

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

`website` 启动时会默认自动检查并启动 `python-a`。如果本机 `http://127.0.0.1:5174/api/health` 已可用，则直接复用已有 Python 服务，不重复启动。

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

带 OpenAI Key 启动 `imagetemplate`：

```bash
set OPENAI_API_KEY=sk-your-key
mvn -pl imagetemplate -am spring-boot:run
```

启动 `python-a`，默认端口 `5174`：

```bash
cd python-a
npm run start
```

也可以直接启动 Python 服务：

```bash
cd python-a
python server.py
```

指定端口启动：

```bash
cd python-a
set PORT=5174
python server.py
```

配置 DeepSeek Key 后启动：

```bash
cd python-a
set DEEPSEEK_API_KEY=your-key
python server.py
```

启动 `quant-a`，默认端口 `5175`：

```bash
cd quant-a
python -m uvicorn main:app --host 127.0.0.1 --port 5175
```

运行 `quant-a` 测试：

```bash
cd quant-a
python -m pytest
```

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
├── python-a/
    ├── README.md
    ├── package.json
    ├── server.py
    ├── index.html
    ├── app.js
    ├── styles.css
    └── obsidian-vault/
└── quant-a/
    ├── main.py
    ├── requirements.txt
    ├── configs/
    ├── quant/
    ├── tests/
    └── web/
```

`python-a` 不参与 Maven 构建，下面结构只表示其独立应用边界：

```text
python-a/
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
quant-a/
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

## 模块职责

- `common/src/main/java/com/example/common/config`：公共配置和自动装配，例如 OSS 自动配置。
- `common/src/main/java/com/example/common/util`：公共工具类，例如 `OssUtil`。
- `common/src/main/java/com/example/common/auth`：公共认证能力，包含 BCrypt 密码哈希、Session 登录状态、`/api/auth` 控制器、`@AuthRequired` 和拦截器。
- `lovestory/controller`：恋爱相册 REST API，照片接口集中在 `/api/photos`，留言接口集中在 `/api/messages`，吉他视频接口集中在 `/api/guitar-videos`。
- `lovestory/dao`：MyBatis DAO 接口层，照片表访问集中在 `PhotoDao`，吉他视频表访问集中在 `GuitarVideoDao`。
- `lovestory/service`：业务逻辑层，吉他视频上传、封面上传、OSS 删除和响应组装集中在 `GuitarVideoService` / `GuitarVideoServiceImpl`。
- `lovestory/src/main/resources/mapper`：MyBatis XML Mapper，SQL 写在这里。
- `lovestory/src/main/resources/static`：恋爱相册、小游戏、留言板、照片墙和吉他视频卡片静态页面。
- `website/blog`：个人博客微应用后端，按 Controller、Service、DAO、Model、DTO 分层。
- `website/src/main/resources/static/blog`：博客前端页面和资源。
- `website/demos`：示例性质的 Web、OSS、Nacos Discovery 代码。
- `imagetemplate/controller`：图片模板 API。
- `imagetemplate/service`：模板加载、prompt 渲染、OpenAI 图片生成服务。
- `imagetemplate/src/main/resources/templates`：图片提示词模板 JSON 数据源。
- `imagetemplate/src/main/resources/static`：图片模板库单页前端。
- `python-a/server.py`：Python 微应用后端，负责静态页面服务、东方财富行情网关、DeepSeek 调用和 Obsidian 写入。
- `python-a/index.html`、`python-a/app.js`、`python-a/styles.css`：A 股自选股 AI 研究台前端页面、交互和样式。
- `python-a/obsidian-vault/A股AI`：Python 微应用默认写入的 Obsidian 研究记录和自选股数据目录。
- `quant-a/main.py`：Quant FastAPI 应用入口，挂载前端静态资源并注册 `/api/**` 路由。
- `quant-a/quant`：量化研究核心代码，包含 API、因子、回测、组合、行情提供方、服务编排和存储。
- `quant-a/tests`：Quant 微服务测试，使用 pytest 和 FastAPI TestClient。
- `quant-a/web`：Quant 研究台前端页面和静态资源。

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
- 推荐命令：`python -m uvicorn main:app --host 127.0.0.1 --port 5175`，工作目录为 `quant-a/`。
- `website` 只提供入口链接和健康检测，不把 `quant-a` 业务逻辑改写进 Java Controller。
- 生产部署如需统一域名，使用 Nginx、网关或 Spring 反向代理把 `/quant-a/` 转发到 `127.0.0.1:5175`。
- `quant-a` 的 `/api/**` 默认由 FastAPI 服务自己处理。没有明确需求时，不要在 Java Controller 中重复实现这些接口。
- `quant-a` 不是 Maven 模块，不执行 `mvn -pl quant-a ...`，也不要写入 `python-a/obsidian-vault/`。

## 微服务主页入口约定

- 新增任何 Java 模块、Python 微应用或独立微服务时，必须同步更新 `website/src/main/resources/static/index.html` 的主页面入口。
- 主页面入口需要包含服务名称、端口或访问标识，并配置实时可用性检测地址。
- 入口样式和状态点维护在 `website/src/main/resources/static/css/style.css`，健康检测逻辑维护在 `website/src/main/resources/static/js/script.js`。
- 如果新增服务没有专门健康检查接口，优先使用其首页或登录页作为检测地址；跨端口检测可使用前端 `no-cors` 方式，只把网络失败视为不可用。
- 新增入口后同步检查顶部导航是否需要增加跳转链接，避免主页入口和导航信息不一致。

## 配置约定

### 端口

- `website`：`8080`
- `lovestory`：`8081`
- `imagetemplate`：`8082`
- `python-a`：`5174`
- `quant-a`：`5175`

### 数据库

- `lovestory` 使用 MySQL 数据库 `lovestory`。
- `website` 使用 MySQL 数据库 `ycx_pms`。
- `imagetemplate` 不使用数据库。
- `python-a` 不使用 MySQL；默认写入本地 `python-a/obsidian-vault/A股AI/`。
- `quant-a` 不使用 MySQL；默认使用 `quant-a/` 内部数据、配置和存储目录，不写入 `python-a` 的 Obsidian 目录。

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
GET  /api/image-templates
GET  /api/image-templates/categories
GET  /api/image-templates/{id}
POST /api/image-templates/{id}/prompt
POST /api/image-templates/{id}/generate
```

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
```

`quant-a` Quant 研究台接口：

```text
GET  /api/health
GET  /api/status
POST /api/data/sync
POST /api/scores/run
POST /api/backtests/run
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
- `imagetemplate` 页面放在 `imagetemplate/src/main/resources/static`，模板 JSON 放在 `imagetemplate/src/main/resources/templates`。
- `python-a` 页面放在 `python-a/index.html`、`python-a/app.js`、`python-a/styles.css`，由 `python-a/server.py` 直接提供静态访问。
- `quant-a` 页面放在 `quant-a/web`，由 `quant-a/main.py` 通过 FastAPI 静态资源能力提供访问。
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
- 股票研究输出必须保留风险提示和非投资建议边界，避免确定性买卖结论。
- 涉及网络请求、文件写入和 Obsidian 写入时要保留异常处理，不能因为单个外部接口失败导致页面整体不可用。
- `quant-a` 使用 FastAPI + Uvicorn，运行配置优先使用环境变量或 `quant-a/configs` 内配置文件；不要把 `quant-a` 加入 Maven modules，不要复用或写入 `python-a/obsidian-vault/`。
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

`python-a` 当前没有单元测试框架。修改后至少执行：

```bash
cd python-a
python server.py
```

再访问：

```text
http://127.0.0.1:5174/
http://127.0.0.1:5174/api/health
```

`quant-a` 修改后至少执行：

```bash
cd quant-a
python -m pytest
python -m uvicorn main:app --host 127.0.0.1 --port 5175
```

再访问：

```text
http://127.0.0.1:5175/
http://127.0.0.1:5175/api/health
```

测试要求：

- `common` 工具类写纯单元测试，不依赖真实 OSS。
- `lovestory` 数据库相关测试 mock DAO 或使用隔离测试配置，不连接远程 MySQL。
- `lovestory` 吉他视频新增或修改逻辑时，覆盖上传成功、标题为空、非法视频后缀、封面上传、删除和 OSS 不可用等主要分支。
- `website/blog` 新增 controller/service/dao 逻辑必须覆盖成功路径和主要失败路径。
- `imagetemplate` 模板渲染测试必须覆盖分类、关键词、变量替换和模板不存在。
- `imagetemplate` 图片尺寸测试必须覆盖合法 4K、非法格式、非 16 倍数、单边超限、像素过少、像素过多和比例超限。
- OpenAI 图片生成测试不得真实调用外部 API；使用 mock 或可注入 HTTP 客户端。
- `quant-a` 新增 API、因子、回测、组合或服务编排逻辑时，使用 pytest 覆盖成功路径和主要失败路径，不依赖真实外部行情接口。

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

- **关键**：不提交 `target/`、IDE 缓存、真实密钥、真实数据库密码、生成图片 base64 文件。
- **关键**：新增公共能力优先放入 `common`。
- **关键**：修改数据库字段时，同步更新 Mapper XML、DAO、模型类和测试。
- **关键**：修改 `lovestory` 吉他视频表字段时，同步更新 `GuitarVideoRecord`、`GuitarVideoDao`、`GuitarVideoMapper.xml`、`GuitarVideoServiceImplTests` 和前端展示字段。
- **关键**：修改 `imagetemplate` 模板 JSON 时，同步更新模板数量、分类断言和前端展示；当前模板库包含 `direct-prompt` / “直接提示词”分类。
- **关键**：修改 `imagetemplate` 图片尺寸选项或规则时，同步更新前端校验、后端校验和 `OpenAiImageGenerationServiceTest`。
- **关键**：修改 `python-a` 时不要提交 `deepseek.local.json`、`.env`、`__pycache__/`、`server.err.log`、`server.out.log`。
- **关键**：修改 `quant-a` 时不要提交 `.env`、`__pycache__/`、`.pytest_cache/`、运行时数据库、缓存或生成报告；不要写入 `python-a/obsidian-vault/`。
- ⚠️ 不依赖远程生产 MySQL、真实 OSS、真实 OpenAI API 来通过单元测试。

## 常见任务指南

### 新增 imagetemplate 模板

1. 修改 `imagetemplate/src/main/resources/templates/image-prompt-templates.json`。
2. 保证 `id` 唯一、`categorySlug` 稳定。
3. 如新增 `direct-prompt` 直接提示词模板，`category` 固定为 `直接提示词`，`categorySlug` 固定为 `direct-prompt`，`jsonTemplate` 使用 `{}`，`promptTemplate` 必须是可直接用于图片生成的完整中文提示词，不使用 `<...>` 占位符。
4. 更新 `ImagePromptTemplateServiceTest` 的数量或分类断言。
5. 运行：

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

1. 修改 `python-a/server.py`、`python-a/app.js`、`python-a/index.html` 或 `python-a/styles.css`。
2. 保持 `python-a` 作为独立 Python 服务，不加入父 `pom.xml`。
3. 如果新增配置，优先使用环境变量，并同步更新 `python-a/README.md` 和根 `AGENTS.md`。
4. 如果新增 API，同步更新本文件的 `python-a` 接口列表。
5. 运行：

```bash
cd python-a
python server.py
```

6. 验证：

```text
GET http://127.0.0.1:5174/api/health
```

## 代理协作原则

- 先读根 `pom.xml` 和目标模块 `pom.xml`，确认模块边界后再改代码。
- 优先使用已有包结构、命名和配置前缀。
- 小改动只跑相关模块测试；跨模块改动跑 `mvn test`。
- 只改 `python-a` 时，不需要跑 Maven 测试；优先启动 Python 服务并验证 `/api/health` 和主要页面流程。
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
