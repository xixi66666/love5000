# AGENTS.md

## 项目概述

`love5000` 是一个 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目，父工程 artifactId 为 `love530`，当前包含三个模块：

- `common`：公共能力模块，提供阿里云 OSS 配置、自动装配和上传工具。
- `lovestory`：恋爱相册/小游戏 Web 应用，提供静态页面、照片上传、照片列表和删除接口。
- `website`：个人主页/展示站点 Web 应用，包含静态资源、基础 Web Demo、OSS Demo 和 Nacos Discovery 示例代码。

核心技术栈：

- 语言：Java 8
- 构建工具：Maven
- 后端框架：Spring Boot 2.6.13
- Web：Spring MVC / Spring Boot Starter Web
- 数据库：MySQL
- 数据访问：Spring JDBC / JdbcTemplate
- 连接池：Alibaba Druid
- 对象存储：Aliyun OSS SDK
- 测试：JUnit 5 + Spring Boot Test
- 静态资源：HTML / CSS / JavaScript，放在 `src/main/resources/static`

**关键架构约定**：根目录 `pom.xml` 只负责模块聚合和依赖版本管理，业务代码分别放在 `common`、`lovestory`、`website` 模块中。跨模块复用能力优先放入 `common`，不要在 Web 模块之间复制工具类。

## 开发命令

所有命令默认在仓库根目录执行：

```bash
cd C:/Code/Java_Code/love5000
```

### 安装/编译全部模块

```bash
mvn clean install
```

### 只编译某个模块及其依赖

```bash
mvn -pl common test
```

```bash
mvn -pl lovestory -am test
```

```bash
mvn -pl website -am test
```

### 启动 lovestory 应用

`lovestory` 默认端口为 `8081`，主类是 `com.ycxandwuqian.love.LovestoryApplication`。

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
```

访问：

```text
http://localhost:8081/
```

### 启动 website 应用

`website` 默认端口为 `8080`，主类是 `com.example.website.WebsiteApplication`。

```bash
mvn -pl website -am spring-boot:run
```

访问：

```text
http://localhost:8080/
```

### 运行全部测试

```bash
mvn test
```

### 跳过测试打包

```bash
mvn clean package -DskipTests
```

### 清理构建产物

```bash
mvn clean
```

## 项目结构

```text
love5000/
├── pom.xml
├── AGENTS.md
├── common/
│   ├── pom.xml
│   └── src/
│       ├── main/java/com/example/common/
│       │   ├── config/
│       │   └── util/
│       ├── main/resources/META-INF/spring.factories
│       └── test/java/com/example/common/
├── lovestory/
│   ├── pom.xml
│   └── src/
│       ├── main/java/com/ycxandwuqian/love/
│       │   ├── config/
│       │   ├── controller/
│       │   ├── model/
│       │   ├── repository/
│       │   └── service/
│       ├── main/resources/
│       │   ├── application.properties
│       │   ├── application.yml
│       │   └── static/
│       └── test/java/com/ycxandwuqian/love/
├── website/
│   ├── pom.xml
│   └── src/
│       ├── main/java/com/example/website/
│       │   ├── demos/
│       │   └── nacosdiscovery/
│       ├── main/resources/
│       │   ├── application.properties
│       │   ├── application.yml
│       │   └── static/
│       └── test/java/com/example/website/
└── src/main/resources/static/images/
```

### 模块职责

- `common/src/main/java/com/example/common/config`：公共配置类。`OssAutoConfiguration` 通过 `spring.factories` 自动装配 OSS 工具。
- `common/src/main/java/com/example/common/util`：公共工具类。`OssUtil` 负责上传、删除、生成 OSS URL 和解析 object key。
- `lovestory/controller`：REST API 控制器。照片接口集中在 `/api/photos`。
- `lovestory/repository`：数据库访问层。当前使用 `JdbcTemplate`，不要混入 JPA 风格 Repository。
- `lovestory/model`：数据库记录模型，例如 `PhotoRecord`。
- `lovestory/service`：业务服务层。新增业务逻辑优先放在 service，再由 controller 调用。
- `lovestory/src/main/resources/static`：相册和小游戏静态页面，包括 `index.html`、`login.html`、`snake.html`、`match3.html`、`tic-tac-toe.html`。
- `website/demos`：示例性质的 Web、OSS、Nacos Discovery 代码。
- `website/src/main/resources/static`：个人主页静态资源，包括 CSS、JS、图片、音效和 SVG。

## 配置约定

### 端口

- `lovestory`：`8081`，配置在 `lovestory/src/main/resources/application.properties`
- `website`：`8080`，配置在 `website/src/main/resources/application.properties`

### 数据库

两个 Web 模块都使用 MySQL：

- `lovestory` 数据库：`lovestory`
- `website` 数据库：`ycx_pms`

`lovestory` 的照片表约定字段：

```sql
id, path, type, create_time
```

`PhotoRepository` 依赖该表结构执行：

```sql
insert into photo(path, type) values (?, ?)
select id, path, type, create_time from photo order by create_time desc, id desc
delete from photo where id = ?
```

### OSS

OSS 配置统一使用 `love530.oss` 前缀：

```yaml
love530:
  oss:
    enabled: true
    endpoint: oss-cn-beijing.aliyuncs.com
    access-key-id: ${LOVE530_OSS_ACCESS_KEY_ID}
    access-key-secret: ${LOVE530_OSS_ACCESS_KEY_SECRET}
    bucket-name: lovestory5000
    base-dir: love530/lovestory/photos
```

⚠️ **严重警告**：不要把真实数据库密码、OSS AccessKey、AccessKeySecret 提交到仓库。新增配置时使用环境变量占位，例如 `${LOVE530_OSS_ACCESS_KEY_ID}`。

## 代码规范

### Java 命名规范

- 类名使用 `UpperCamelCase`：`UploadPhotoController`、`PhotoRepository`、`OssUtil`
- 方法名、变量名使用 `lowerCamelCase`：`uploadPhoto`、`photoRepository`、`normalizedCategory`
- 常量使用 `UPPER_SNAKE_CASE`：`ALLOWED_CATEGORIES`、`TIME_FORMATTER`
- 包名全部小写：`com.example.common`、`com.ycxandwuqian.love`
- Controller 类以 `Controller` 结尾
- Repository 类以 `Repository` 结尾
- Service 接口以 `Service` 结尾，实现类以 `ServiceImpl` 结尾

**当前需要修正的历史命名**：`uploadPhotoService` 和 `uploadPhotoServiceImpl` 不符合 Java 类名规范。新增或重命名代码时应使用 `UploadPhotoService` 和 `UploadPhotoServiceImpl`。

### Spring 编码约定

- 优先使用构造器注入，不使用字段注入。
- Controller 只处理 HTTP 参数、响应组装和异常边界，数据库读写放到 Repository，业务规则放到 Service。
- `common` 模块的自动配置必须保持可选：使用 `@ConditionalOnProperty`、`@ConditionalOnClass`、`@ConditionalOnMissingBean`。
- OSS 相关 Bean 必须允许关闭：`love530.oss.enabled=false` 时应用应能启动。
- 新增配置属性时放入 `OssProperties` 或对应的 `@ConfigurationProperties` 类，不要在业务代码里硬编码配置值。
- 静态资源路径保持在 `src/main/resources/static`，不要依赖 `target/classes` 中的构建产物。

### API 约定

`lovestory` 照片接口：

```text
POST   /api/photos/upload
GET    /api/photos
DELETE /api/photos/{id}
```

照片分类只允许：

```text
cat, girl, us
```

上传图片后缀只允许：

```text
jpg, jpeg, png, gif, webp
```

新增接口时保持响应结构清晰，至少包含：

```json
{
  "success": true,
  "message": "Upload succeeded"
}
```

### 静态页面约定

- `lovestory` 的页面以纪念相册和小游戏为主，不要把大量业务逻辑散落到多个重复 HTML 文件中。
- `website` 的主页资源已经分为 `css/style.css` 和 `js/script.js`，新增样式和交互优先放入对应文件。
- 图片、音效、SVG 放在已有资源目录下：`img/`、`soundeffects/`、`svg/`。

## 测试策略

当前测试框架：

- JUnit 5
- Spring Boot Test
- Maven Surefire 2.22.2

### 必跑测试

提交前运行全部测试：

```bash
mvn test
```

修改 `common` 模块时运行：

```bash
mvn -pl common test
```

修改 `lovestory` 或其依赖的 `common` 时运行：

```bash
mvn -pl lovestory -am test
```

修改 `website` 时运行：

```bash
mvn -pl website -am test
```

### 测试编写要求

- `common` 中的工具类必须写纯单元测试，不依赖真实 OSS。
- `lovestory` 中涉及数据库的测试必须 mock `DataSource`、`JdbcTemplate` 或 Repository，不直接连接远程 MySQL。
- Controller 新增接口时优先补充 MockMvc 测试，覆盖成功、参数非法、外部依赖不可用三类场景。
- Repository 新增 SQL 时至少覆盖 SQL 参数、空结果和删除失败分支。
- OSS 上传、删除、URL 生成逻辑必须覆盖：
  - 自定义 CDN 域名
  - 原始 OSS 域名
  - URL 中带 query string 的 object key 解析
  - 空文件名或非法后缀

### 覆盖率要求

项目当前没有配置 JaCoCo。新增测试时按以下目标执行：

- `common` 工具类和配置类：核心分支覆盖率目标不低于 80%
- `lovestory` controller/service/repository：新增逻辑必须覆盖成功路径和主要失败路径
- `website` demo 类：至少保证 Spring 上下文测试通过

如需引入覆盖率检查，优先在父 `pom.xml` 统一配置 `jacoco-maven-plugin`，不要只在单个模块里配置。

## 构建与提交检查清单

提交前按顺序执行：

```bash
mvn clean test
```

如果只改了静态资源，至少确认目标模块能启动：

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
```

```bash
mvn -pl website -am spring-boot:run
```

检查项：

- **关键**：不要提交 `target/`、IDE 缓存、真实密钥、真实数据库密码。
- **关键**：新增公共能力优先放入 `common`，并通过自动配置或显式 Bean 暴露。
- **关键**：修改数据库字段时，同步更新 Repository SQL、模型类和测试。
- **关键**：新增上传类型或照片分类时，同步更新后端校验和前端展示逻辑。
- ⚠️ 不要依赖远程生产 MySQL 或真实 OSS 来通过单元测试。
- ⚠️ 不要把 `lovestory/target/classes/static/images` 中的运行时生成文件当作源码修改。

## 常见任务指南

### 新增照片分类

1. 修改 `UploadPhotoController` 中的 `ALLOWED_CATEGORIES`。
2. 修改 `categoryLabel` 的展示名称。
3. 更新前端上传入口和列表筛选逻辑。
4. 补充 controller 测试，覆盖新分类和非法分类。
5. 运行：

```bash
mvn -pl lovestory -am test
```

### 修改 OSS 行为

1. 优先修改 `common/src/main/java/com/example/common/util/OssUtil.java`。
2. 如需新增配置，修改 `OssProperties`。
3. 保持 `love530.oss.enabled=false` 可用。
4. 补充 `common/src/test/java/com/example/common/util/OssUtilTests.java`。
5. 运行：

```bash
mvn -pl common test
```

### 新增 Web 页面

1. `lovestory` 页面放到 `lovestory/src/main/resources/static`。
2. `website` 页面和资源放到 `website/src/main/resources/static`。
3. 资源文件使用相对路径引用，不引用本机绝对路径。
4. 启动对应模块手动访问确认。

## 代理协作原则

- 先读根 `pom.xml` 和目标模块 `pom.xml`，确认模块边界后再改代码。
- 优先使用已有包结构、已有命名和已有配置前缀。
- 小改动只跑相关模块测试；跨模块改动跑 `mvn test`。
- 修改配置文件时检查是否包含密钥，能改成环境变量就改成环境变量。
- 不修改 `.idea/`、`target/`、运行时生成图片，除非任务明确要求。
- 不引入新框架替代 `JdbcTemplate`、Maven 或 Spring Boot，除非先完成明确的迁移设计。
