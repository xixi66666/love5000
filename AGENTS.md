# AGENTS.md

## 项目概述

`love5000` 是一个 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目，父工程 artifactId 为 `love530`，当前包含三个模块：

- `common`：公共能力模块，提供阿里云 OSS 配置、自动装配、上传工具，以及通用登录/注册/Session 鉴权能力。
- `lovestory`：恋爱相册/小游戏 Web 应用，提供静态页面、照片上传、照片列表和删除接口。
- `website`：个人主页/展示站点 Web 应用，包含主页静态资源、Web Demo、OSS Demo、Nacos Discovery 示例代码，以及个人博客微应用 `blog`。

核心技术栈：

- 语言：Java 8
- 构建工具：Maven
- 后端框架：Spring Boot 2.6.13
- Web：Spring MVC / Spring Boot Starter Web
- 数据库：MySQL
- 数据访问：MyBatis / DAO 接口 + XML Mapper 映射器
- 连接池：Alibaba Druid
- 对象存储：Aliyun OSS SDK
- 测试：JUnit 5 + Spring Boot Test
- 静态资源：HTML / CSS / JavaScript

根目录 `pom.xml` 只负责模块聚合和依赖版本管理，业务代码分别放在 `common`、`lovestory`、`website` 模块中。跨模块复用能力优先放入 `common`，不要在 Web 模块之间复制工具类。

## 开发命令

所有命令默认在仓库根目录执行：

```bash
cd C:/Code/Java_Code/love5000
```

安装/编译全部模块：

```bash
mvn clean install
```

只编译某个模块及其依赖：

```bash
mvn -pl common test
mvn -pl lovestory -am test
mvn -pl website -am test
```

启动 `lovestory` 应用，默认端口 `8081`：

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
```

启动 `website` 应用，默认端口 `8080`：

```bash
mvn -pl website -am spring-boot:run
```

运行全部测试：

```bash
mvn test
```

跳过测试打包：

```bash
mvn clean package -DskipTests
```

## 项目结构

```text
love5000/
├── pom.xml
├── AGENTS.md
├── common/
├── lovestory/
└── website/
    └── src/
        ├── main/java/com/example/website/
        │   ├── blog/
        │   │   ├── config/
        │   │   ├── controller/
        │   │   ├── dto/
        │   │   ├── model/
        │   │   ├── dao/
        │   │   └── service/
        │   ├── demos/
        │   └── nacosdiscovery/
        └── main/resources/
            ├── index.html
            ├── mapper/
            └── static/
                ├── blog/
                ├── css/
                ├── img/
                ├── js/
                ├── soundeffects/
                └── svg/
```

## 模块职责

- `common/src/main/java/com/example/common/config`：公共配置类。`OssAutoConfiguration` 通过 `spring.factories` 自动装配 OSS 工具。
- `common/src/main/java/com/example/common/util`：公共工具类。`OssUtil` 负责上传、删除、生成 OSS URL 和解析 object key。
- `common/src/main/java/com/example/common/auth`：公共认证能力。提供 BCrypt 密码哈希、Session 登录态、`/api/auth` 控制器、`@AuthRequired` 注解和拦截器。
- `lovestory/controller`：REST API 控制器。照片接口集中在 `/api/photos`。
- `lovestory/dao`：MyBatis DAO 接口层。照片表访问集中在 `PhotoDao`，SQL 写在 `lovestory/src/main/resources/mapper/PhotoMapper.xml`。
- `lovestory/service`：业务服务层。新增业务逻辑优先放在 service，再由 controller 调用。
- `website/blog`：个人博客微应用后端，按 Controller、Service、DAO、Model、DTO 分层实现。
- `website/auth/dao`：`website` 认证用户表的 MyBatis DAO。`WebsiteAuthUserRepository` 仅作为 `common` 认证接口的适配层，不直接写 SQL。
- `website/src/main/resources/mapper`：MyBatis XML Mapper 存放目录。所有数据库 CRUD SQL 都应写在这里。
- `website/src/main/resources/index.html`：个人网站主页面。
- `website/src/main/resources/static/blog`：个人博客微应用前端页面和资源。
- `website/demos`：示例性质的 Web、OSS、Nacos Discovery 代码。

## 配置约定

### 端口

- `lovestory`：`8081`
- `website`：`8080`

### 数据库

两个 Web 模块都使用 MySQL：

- `lovestory` 数据库：`lovestory`
- `website` 数据库：`ycx_pms`

不要把真实数据库密码、OSS AccessKey、AccessKeySecret 提交到仓库。新增配置时使用环境变量占位，例如 `${LOVE530_OSS_ACCESS_KEY_ID}`。

### lovestory 照片表

照片表约定字段：

```sql
id, path, type, create_time
```

`PhotoDao` 通过 `mapper/PhotoMapper.xml` 依赖该表结构执行：

```sql
select id, path, type, create_time from photo order by create_time desc, id desc
select id, path, type, create_time from photo where id = ?
insert into photo(path, type) values (?, ?)
delete from photo where id = ?
```

### website 博客表

`blog` 微应用使用 `blog_article` 表。数据库表由开发者或运维提前创建，Java 代码不负责启动建表、补字段或写入种子数据。对应的手动建表和种子数据脚本位于：

```text
website/src/main/resources/db/blog.sql
```

`website` 的登录/注册使用 `auth_user` 表。公共认证逻辑在 `common`，`website` 通过 `WebsiteAuthUserRepository` 适配 `AuthUserRepository`，实际数据库读写由 `WebsiteAuthUserDao` 和 `mapper/auth/WebsiteAuthUserMapper.xml` 完成。

核心字段：

```sql
id, username, display_name, password_hash, role, enabled, created_at, updated_at
```

认证方案：

- 使用服务端 Session + HttpOnly Cookie 保存登录态。
- `website` 配置 Session Cookie 为 HttpOnly + SameSite Strict。
- 密码使用 BCrypt 哈希，不保存明文密码。
- 登录、注册、退出、当前用户接口由 `common` 自动装配。
- 需要登录的业务接口使用 `@AuthRequired` 标注。

核心字段：

```sql
id, title, slug, summary, content_html, category, tags,
word_count, read_minutes, published_at, created_at, updated_at
```

约定：

- `slug` 唯一，用于文章详情路径。
- `content_html` 存储文章 HTML 正文。
- `tags` 使用英文逗号分隔，例如 `Java,Spring Boot,工程化`。
- 读取接口只返回已入库文章，前端不得维护静态文章数组作为主要数据源。

## API 约定

`lovestory` 照片接口：

```text
POST   /api/photos/upload
GET    /api/photos
DELETE /api/photos/{id}
```

`website` 博客接口：

```text
GET /api/blog/articles
GET /api/blog/articles/{slug}
POST /api/blog/articles
GET /api/blog/categories
GET /api/blog/tags
```

文章列表支持查询参数：

```text
keyword, category, tag
```

`POST /api/blog/articles` 需要登录。请求体至少包含：

```json
{
  "title": "文章标题",
  "slug": "optional-slug",
  "summary": "文章摘要",
  "contentHtml": "<p>正文</p>",
  "category": "技术教程",
  "tags": ["Java", "Spring Boot"]
}
```

公共认证接口：

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

新增接口时保持响应结构清晰，至少包含：

```json
{
  "success": true
}
```

## 静态页面约定

- `lovestory` 页面放在 `lovestory/src/main/resources/static`。
- `website` 主页资源优先放入 `website/src/main/resources/static/css` 和 `website/src/main/resources/static/js`。
- `website` 的博客微应用资源放在 `website/src/main/resources/static/blog`，不要把博客样式混入主页 CSS。
- 图片、音效、SVG 放在已有资源目录下：`img/`、`soundeffects/`、`svg/`。
- 静态资源使用相对路径引用，不引用本机绝对路径。

## 代码规范

### Java 命名规范

- 类名使用 `UpperCamelCase`：`BlogController`、`BlogServiceImpl`、`PhotoDao`。
- 方法名、变量名使用 `lowerCamelCase`：`listArticles`、`blogArticleDao`。
- 常量使用 `UPPER_SNAKE_CASE`。
- 包名全部小写。
- Controller 类以 `Controller` 结尾。
- DAO 接口以 `Dao` 结尾。
- MyBatis XML 映射文件以 `Mapper.xml` 结尾。
- Repository 只用于适配既有跨模块接口，例如 `WebsiteAuthUserRepository` 适配 `AuthUserRepository`；新增业务数据库访问不要创建 Repository。
- Service 接口以 `Service` 结尾，实现类以 `ServiceImpl` 结尾。

历史命名 `uploadPhotoService` 和 `uploadPhotoServiceImpl` 不符合 Java 类名规范。新增或重命名代码时应使用 `UploadPhotoService` 和 `UploadPhotoServiceImpl`。

### Spring 编码约定

- 优先使用构造器注入，不使用字段注入。
- Controller 只处理 HTTP 参数、响应组装和异常边界。
- 数据库读写统一使用 MyBatis DAO 接口 + XML Mapper 映射器。
- 业务规则放到 Service。
- DAO 接口放在 `dao` 包，类名以 `Dao` 结尾，例如 `BlogArticleDao`、`PhotoDao`。
- Mapper XML 放在模块 `src/main/resources/mapper` 下，文件名以 `Mapper.xml` 结尾，并与 DAO namespace 对齐。
- Java 代码中不要直接使用 `JdbcTemplate`、手写 `PreparedStatement` 或把 SQL 拼在 Service/Controller 中。
- 不引入 JPA 风格 Repository。只有为了适配 `common` 既有接口时才保留 Repository，且 Repository 不直接写 SQL。
- `common` 模块的自动配置必须保持可选：使用 `@ConditionalOnProperty`、`@ConditionalOnClass`、`@ConditionalOnMissingBean`。
- OSS 相关 Bean 必须允许关闭：`love530.oss.enabled=false` 时应用应能启动。

## 测试策略

当前测试框架：

- JUnit 5
- Spring Boot Test
- Maven Surefire 2.22.2

必跑测试：

```bash
mvn test
mvn -pl common test
mvn -pl lovestory -am test
mvn -pl website -am test
```

测试要求：

- `common` 工具类必须写纯单元测试，不依赖真实 OSS。
- `lovestory` 涉及数据库的测试必须 mock DAO 或使用隔离测试配置，不直接连接远程 MySQL。
- `website/blog` controller/service/dao 新增逻辑必须覆盖成功路径和主要失败路径。
- `website` 的 Spring 上下文测试不得依赖远程 MySQL。
- Controller 新增接口优先补充 MockMvc 或直接 controller 单元测试，覆盖成功、参数非法、外部依赖不可用三类场景。

## 构建与提交检查清单

提交前按顺序执行：

```bash
mvn clean test
```

如果只改了静态资源，至少确认目标模块能启动：

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
mvn -pl website -am spring-boot:run
```

检查项：

- 不提交 `target/`、IDE 缓存、真实密钥、真实数据库密码。
- 新增公共能力优先放入 `common`，并通过自动配置或显式 Bean 暴露。
- 修改数据库字段时，同步更新 Mapper XML、DAO、模型类和测试。
- 新增博客字段时，同步更新 `BlogArticle`、`BlogArticleDao`、`BlogArticleMapper.xml`、DTO、前端渲染和测试。
- 不依赖远程生产 MySQL 或真实 OSS 来通过单元测试。
- 不把 `lovestory/target/classes/static/images` 中的运行时生成文件当作源码修改。

## 常见任务指南

### 新增博客文章字段

1. 修改 `BlogArticle`。
2. 修改 `BlogArticleDao` 的方法签名。
3. 修改 `website/src/main/resources/mapper/blog/BlogArticleMapper.xml` 的查询、插入、更新映射。
4. 如涉及接口响应，修改 `BlogArticleResponse`。
5. 修改 `static/blog/blog.js` 的渲染逻辑。
6. 补充或更新 `website` 测试。
7. 运行：

```bash
mvn -pl website -am test
```

### 新增博客前端功能

1. 页面放在 `website/src/main/resources/static/blog`。
2. 后端数据通过 `/api/blog` 接口获取。
3. 不在前端维护主要文章数据。
4. 若需要新数据维度，先补后端接口和测试，再改前端。

### 修改 OSS 行为

1. 优先修改 `common/src/main/java/com/example/common/util/OssUtil.java`。
2. 如需新增配置，修改 `OssProperties`。
3. 保持 `love530.oss.enabled=false` 可用。
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
- 不修改 `.idea/`、`target/`、运行时生成图片，除非任务明确要求。
- 后续所有数据库 CRUD 开发都使用 MyBatis DAO + XML Mapper 映射器，不再新增 `JdbcTemplate`、JPA Repository 或 Java 内联 SQL。
