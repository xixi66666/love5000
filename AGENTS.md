# AGENTS.md

## 项目概述

`love5000` 是一个 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目，父工程 artifactId 为 `love530`。当前模块：

- `common`：公共能力模块，提供 OSS 自动配置、上传工具，以及通用登录/注册/Session 鉴权能力。
- `lovestory`：恋爱相册 Web 应用，提供静态页面、照片上传、照片列表、删除接口和留言板功能。
- `website`：个人主页/展示站点 Web 应用，包含主页静态资源、Web Demo、OSS Demo、Nacos Discovery 示例和个人博客微应用。
- `imagetemplate`：图片提示词模板 Web 服务，提供模板库检索、prompt 渲染和 OpenAI 图片生成能力。

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
- 测试：JUnit 5 + Spring Boot Test + Maven Surefire 2.22.2
- 前端：原生 HTML / CSS / JavaScript

**关键**：根目录 `pom.xml` 只负责模块聚合、公共版本和依赖管理。业务代码必须放在对应模块内；跨模块公共能力优先放入 `common`。

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

启动 `imagetemplate`，默认端口 `8082`：

```bash
mvn -pl imagetemplate -am spring-boot:run
```

带 OpenAI Key 启动 `imagetemplate`：

```bash
set OPENAI_API_KEY=sk-your-key
mvn -pl imagetemplate -am spring-boot:run
```

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
└── imagetemplate/
    ├── AGENTS.md
    └── src/
        ├── main/java/com/example/imagetemplate/
        │   ├── controller/
        │   ├── dto/
        │   ├── model/
        │   └── service/
        └── main/resources/
            ├── application.yml
            ├── static/
            │   ├── index.html
            │   ├── css/app.css
            │   └── js/app.js
            └── templates/image-prompt-templates.json
```

## 模块职责

- `common/src/main/java/com/example/common/config`：公共配置和自动装配，例如 OSS 自动配置。
- `common/src/main/java/com/example/common/util`：公共工具类，例如 `OssUtil`。
- `common/src/main/java/com/example/common/auth`：公共认证能力，包含 BCrypt 密码哈希、Session 登录状态、`/api/auth` 控制器、`@AuthRequired` 和拦截器。
- `lovestory/controller`：恋爱相册 REST API，照片接口集中在 `/api/photos`，留言接口集中在 `/api/messages`。
- `lovestory/dao`：MyBatis DAO 接口层，照片表访问集中在 `PhotoDao`。
- `lovestory/src/main/resources/mapper`：MyBatis XML Mapper，SQL 写在这里。
- `lovestory/src/main/resources/static`：恋爱相册、小游戏、留言板、照片墙静态页面。
- `website/blog`：个人博客微应用后端，按 Controller、Service、DAO、Model、DTO 分层。
- `website/src/main/resources/static/blog`：博客前端页面和资源。
- `website/demos`：示例性质的 Web、OSS、Nacos Discovery 代码。
- `imagetemplate/controller`：图片模板 API。
- `imagetemplate/service`：模板加载、prompt 渲染、OpenAI 图片生成服务。
- `imagetemplate/src/main/resources/templates`：图片提示词模板 JSON 数据源。
- `imagetemplate/src/main/resources/static`：图片模板库单页前端。

## 配置约定

### 端口

- `website`：`8080`
- `lovestory`：`8081`
- `imagetemplate`：`8082`

### 数据库

- `lovestory` 使用 MySQL 数据库 `lovestory`。
- `website` 使用 MySQL 数据库 `ycx_pms`。
- `imagetemplate` 不使用数据库。

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
- `website` 主页资源放在 `website/src/main/resources/static/css`、`static/js`、`static/img`。
- `website` 博客资源放在 `website/src/main/resources/static/blog`。
- `imagetemplate` 页面放在 `imagetemplate/src/main/resources/static`，模板 JSON 放在 `imagetemplate/src/main/resources/templates`。
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

测试要求：

- `common` 工具类写纯单元测试，不依赖真实 OSS。
- `lovestory` 数据库相关测试 mock DAO 或使用隔离测试配置，不连接远程 MySQL。
- `website/blog` 新增 controller/service/dao 逻辑必须覆盖成功路径和主要失败路径。
- `imagetemplate` 模板渲染测试必须覆盖分类、关键词、变量替换和模板不存在。
- OpenAI 图片生成测试不得真实调用外部 API；使用 mock 或可注入 HTTP 客户端。

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
- **关键**：修改 `imagetemplate` 模板 JSON 时，同步更新模板数量、分类断言和前端展示。
- ⚠️ 不依赖远程生产 MySQL、真实 OSS、真实 OpenAI API 来通过单元测试。

## 常见任务指南

### 新增 imagetemplate 模板

1. 修改 `imagetemplate/src/main/resources/templates/image-prompt-templates.json`。
2. 保证 `id` 唯一、`categorySlug` 稳定。
3. 更新 `ImagePromptTemplateServiceTest` 的数量或分类断言。
4. 运行：

```bash
mvn -pl imagetemplate test
```

### 修改 OpenAI 图片生成逻辑

1. 修改 `ImageGenerationRequest` 或 `ImageGenerationResponse`。
2. 修改 `OpenAiImageGenerationService` 的请求体或响应解析。
3. 修改 `imagetemplate/src/main/resources/static/js/app.js`。
4. 补充无 API Key、OpenAI 错误、空图片数据响应测试。
5. 运行：

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

## 代理协作原则

- 先读根 `pom.xml` 和目标模块 `pom.xml`，确认模块边界后再改代码。
- 优先使用已有包结构、命名和配置前缀。
- 小改动只跑相关模块测试；跨模块改动跑 `mvn test`。
- 修改配置文件时检查是否包含密钥，能改成环境变量就改成环境变量。
- 不修改 `.idea/`、`target/`、运行时生成文件，除非任务明确要求。
- 后续数据库 CRUD 使用 MyBatis DAO + XML Mapper，不新增 `JdbcTemplate`、JPA Repository 或 Java 内联 SQL。
