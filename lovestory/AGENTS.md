# AGENTS.md

## 项目概述

`lovestory` 是 `love530` Maven 聚合工程中的恋爱相册 Web 微服务，路径：

```text
C:/Code/Java_Code/love5000/lovestory
```

核心功能：

- 提供恋爱相册静态页面。
- 提供照片上传、列表查询、删除接口。
- 将照片文件上传到阿里云 OSS。
- 使用 MySQL 保存照片记录。
- 提供多个静态小游戏页面，如贪吃蛇、三消、井字棋。

技术栈：

- Java 8
- Maven
- Spring Boot 2.6.13
- Spring MVC
- Spring JDBC / JdbcTemplate
- MySQL
- Alibaba Druid 1.2.24
- Aliyun OSS，来自 `common` 模块
- JUnit 5 / Spring Boot Test
- HTML / CSS / JavaScript 静态页面

配置文件：

- `pom.xml`：模块依赖和 Spring Boot 主类配置。
- `src/main/resources/application.properties`：端口和静态资源路径。
- `src/main/resources/application.yml`：MySQL、multipart、OSS 配置。

**关键**：`lovestory` 依赖 `common` 提供 OSS 能力，不要在本模块重新实现 OSS 客户端。

## 开发命令

默认从仓库根目录执行：

```bash
cd C:/Code/Java_Code/love5000
```

安装依赖并编译当前服务：

```bash
mvn -pl lovestory -am clean install
```

启动服务：

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
```

服务地址：

```text
http://localhost:8081/
```

运行当前服务测试：

```bash
mvn -pl lovestory -am test
```

打包当前服务：

```bash
mvn -pl lovestory -am clean package
```

跳过测试打包：

```bash
mvn -pl lovestory -am clean package -DskipTests
```

检查依赖树：

```bash
mvn -pl lovestory dependency:tree
```

从模块目录启动：

```bash
cd C:/Code/Java_Code/love5000/lovestory
mvn spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
```

## 项目结构

```text
lovestory/
├── pom.xml
├── AGENTS.md
└── src/
    ├── main/
    │   ├── java/com/ycxandwuqian/love/
    │   │   ├── LovestoryApplication.java
    │   │   ├── config/WebConfig.java
    │   │   ├── controller/
    │   │   │   ├── LoginController.java
    │   │   │   └── UploadPhotoController.java
    │   │   ├── model/PhotoRecord.java
    │   │   ├── repository/PhotoRepository.java
    │   │   └── service/
    │   │       ├── uploadPhotoService.java
    │   │       └── uploadPhotoServiceImpl.java
    │   └── resources/
    │       ├── application.properties
    │       ├── application.yml
    │       └── static/
    │           ├── index.html
    │           ├── login.html
    │           ├── match3.html
    │           ├── snake.html
    │           ├── tic-tac-toe.html
    │           └── images/
    └── test/java/com/ycxandwuqian/love/
        └── LovestoryApplicationTests.java
```

核心模块职责：

- `controller/UploadPhotoController.java`：照片上传、查询、删除 REST API。
- `controller/LoginController.java`：登录相关入口。
- `repository/PhotoRepository.java`：使用 `JdbcTemplate` 访问 `photo` 表。
- `model/PhotoRecord.java`：照片记录模型。
- `config/WebConfig.java`：Web 配置。
- `static/`：相册页面、登录页、小游戏页面和图片资源。

## API 约定

照片接口统一挂载在：

```text
/api/photos
```

当前接口：

```text
POST   /api/photos/upload
GET    /api/photos
DELETE /api/photos/{id}
```

上传字段：

```text
file        MultipartFile，必填
category    cat | girl | us，必填
description string，可选
```

允许的照片分类：

```text
cat
girl
us
```

允许的图片后缀：

```text
jpg
jpeg
png
gif
webp
```

响应结构保持 `success` 和 `message`：

```json
{
  "success": true,
  "message": "Upload succeeded",
  "url": "https://example.com/photo.png"
}
```

## 数据库约定

当前使用 MySQL，配置在 `src/main/resources/application.yml`。

`PhotoRepository` 依赖 `photo` 表字段：

```sql
id
path
type
create_time
```

仓库中的 SQL：

```sql
insert into photo(path, type) values (?, ?)
select id, path, type, create_time from photo order by create_time desc, id desc
select id, path, type, create_time from photo where id = ?
delete from photo where id = ?
```

⚠️ 严重警告：不要让单元测试依赖远程 MySQL。测试中使用 mock、内存库或独立测试配置。

## OSS 约定

OSS 能力来自 `common` 模块的 `OssUtil`。

配置前缀：

```yaml
love530:
  oss:
    enabled: ${LOVE530_OSS_ENABLED:true}
    endpoint: ${LOVE530_OSS_ENDPOINT:oss-cn-beijing.aliyuncs.com}
    access-key-id: ${LOVE530_OSS_ACCESS_KEY_ID}
    access-key-secret: ${LOVE530_OSS_ACCESS_KEY_SECRET}
    bucket-name: ${LOVE530_OSS_BUCKET_NAME:lovestory5000}
    url-prefix: ${LOVE530_OSS_URL_PREFIX:}
    base-dir: ${LOVE530_OSS_BASE_DIR:love530/lovestory/photos}
```

**关键**：上传路径当前按分类拼接：

```text
love530/lovestory/photos/{category}
```

⚠️ 严重警告：不要提交真实数据库密码、OSS AccessKey 或 AccessKeySecret。

## 代码规范

Java 命名：

- 类名使用 `UpperCamelCase`：`UploadPhotoController`、`PhotoRepository`。
- 方法名和变量名使用 `lowerCamelCase`：`uploadPhoto`、`photoRecord`。
- 常量使用 `UPPER_SNAKE_CASE`：`ALLOWED_CATEGORIES`、`TIME_FORMATTER`。
- 包名全小写：`com.ycxandwuqian.love`。
- Controller 以 `Controller` 结尾。
- Repository 以 `Repository` 结尾。
- Service 接口以 `Service` 结尾，实现类以 `ServiceImpl` 结尾。

**关键**：当前历史文件 `uploadPhotoService.java`、`uploadPhotoServiceImpl.java` 不符合 Java 常用类名规范。新增或重命名时使用 `UploadPhotoService`、`UploadPhotoServiceImpl`。

Spring 约定：

- 优先使用构造器注入。
- Controller 只处理 HTTP 参数、响应和异常边界。
- 数据库访问集中在 Repository。
- 业务规则优先放入 Service。
- 不在 Controller 中硬编码数据库 SQL。
- 不直接实例化 `OssUtil`，通过 Spring 注入或 `ObjectProvider<OssUtil>` 获取。

静态资源约定：

- 页面文件放在 `src/main/resources/static`。
- 图片放在 `src/main/resources/static/images`。
- 不修改 `target/classes/static`，那是构建产物。

## 测试策略

测试框架：

- JUnit 5
- Spring Boot Test

运行测试：

```bash
mvn -pl lovestory -am test
```

当前已有测试：

```text
src/test/java/com/ycxandwuqian/love/LovestoryApplicationTests.java
```

测试要求：

- Controller 新增接口时补充 MockMvc 测试。
- Repository 新增 SQL 时覆盖成功、空结果、删除失败。
- OSS 不可用时必须覆盖 `ossUtilProvider.getIfAvailable() == null` 分支。
- 上传接口必须覆盖空文件、非法后缀、非法分类、正常上传。
- Spring 上下文测试中 mock `DataSource` 和 `PhotoRepository`，避免连接真实数据库。

覆盖率目标：

- `UploadPhotoController` 新增逻辑分支不低于 80%。
- `PhotoRepository` 新增 SQL 分支必须有测试覆盖。
- 静态页面修改至少手动访问 `http://localhost:8081/` 验证。

## 提交前检查

```bash
mvn -pl lovestory -am clean test
```

需要手动启动验证时执行：

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
```

检查清单：

- **关键**：照片分类变更时，同步更新后端校验、前端展示和测试。
- **关键**：数据库字段变更时，同步更新 SQL、模型和测试。
- **关键**：OSS 配置必须支持环境变量。
- ⚠️ 不要提交 `target/` 下的图片或 class 文件。
- ⚠️ 不要在测试中调用真实 OSS 或真实远程数据库。
