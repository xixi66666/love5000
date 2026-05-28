# AGENTS.md

## 项目概述

`lovestory` 是 `love530` Maven 聚合工程中的恋爱相册 Web 微服务，路径：

```text
C:/Code/Java_Code/love5000/lovestory
```

核心功能：

- 提供恋爱相册静态页面。
- 提供照片上传、列表查询、删除接口。
- 提供吉他视频卡片、视频上传、封面上传、列表查询和删除接口。
- 将照片文件上传到阿里云 OSS。
- 将吉他视频和视频封面上传到阿里云 OSS。
- 使用 MySQL 保存照片记录。
- 使用 MySQL 保存吉他视频记录。
- 提供多个静态小游戏页面，如贪吃蛇、三消、井字棋。

技术栈：

- Java 8
- Maven
- Spring Boot 2.6.13
- Spring MVC
- MyBatis / DAO 接口 + XML Mapper 映射器
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
    │   │   ├── dao/PhotoDao.java
    │   │   ├── model/PhotoRecord.java
    │   │   └── service/
    │   │       ├── uploadPhotoService.java
    │   │       └── uploadPhotoServiceImpl.java
    │   └── resources/
    │       ├── application.properties
    │       ├── application.yml
    │       ├── mapper/PhotoMapper.xml
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
- `controller/GuitarVideoController.java`：吉他视频上传、封面上传、查询、删除 REST API。
- `controller/LoginController.java`：登录相关入口。
- `dao/PhotoDao.java`：MyBatis DAO 接口，定义 `photo` 表 CRUD 方法。
- `dao/GuitarVideoDao.java`：MyBatis DAO 接口，定义 `guitar_video` 表访问方法。
- `resources/mapper/PhotoMapper.xml`：`PhotoDao` 对应的 MyBatis XML Mapper，集中维护照片表 SQL。
- `resources/mapper/GuitarVideoMapper.xml`：`GuitarVideoDao` 对应的 MyBatis XML Mapper，集中维护吉他视频表 SQL。
- `model/PhotoRecord.java`：照片记录模型。
- `model/GuitarVideoRecord.java`：吉他视频记录模型。
- `service/GuitarVideoService.java`、`service/GuitarVideoServiceImpl.java`：吉他视频业务逻辑，包括参数校验、OSS 上传、封面上传、软删除和响应组装。
- `config/WebConfig.java`：Web 配置。
- `static/`：相册页面、登录页、小游戏页面、吉他视频卡片和图片资源。

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

吉他视频接口统一挂载在：

```text
/api/guitar-videos
```

当前接口：

```text
GET    /api/guitar-videos
POST   /api/guitar-videos/upload
POST   /api/guitar-videos/{id}/cover
DELETE /api/guitar-videos/{id}
```

视频上传字段：

```text
file         MultipartFile，必填，视频文件
cover        MultipartFile，可选，封面图；前端未选择时可自动从视频截帧生成
title        string，必填
description  string，可选
tag          string，可选
sortOrder    int，可选
```

允许的视频后缀：

```text
mp4
webm
mov
```

允许的封面图后缀：

```text
jpg
jpeg
png
webp
```

## 数据库约定

当前使用 MySQL，配置在 `src/main/resources/application.yml`。

MyBatis 必须显式配置 XML Mapper 扫描路径：

```yaml
mybatis:
  mapper-locations: classpath*:mapper/**/*.xml
  type-aliases-package: com.ycxandwuqian.love.model
  configuration:
    map-underscore-to-camel-case: true
```

`PhotoDao` 通过 `src/main/resources/mapper/PhotoMapper.xml` 依赖 `photo` 表字段：

```sql
id
path
type
create_time
```

Mapper 中的 SQL：

```sql
insert into photo(path, type) values (?, ?)
select id, path, type, create_time from photo order by create_time desc, id desc
select id, path, type, create_time from photo where id = ?
delete from photo where id = ?
```

`GuitarVideoDao` 通过 `src/main/resources/mapper/GuitarVideoMapper.xml` 依赖 `guitar_video` 表字段：

```sql
id
title
description
tag
video_url
cover_url
duration_seconds
sort_order
status
create_time
update_time
```

推荐建表语句：

```sql
CREATE TABLE `guitar_video` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `title` VARCHAR(100) NOT NULL COMMENT '视频标题或歌曲名',
  `description` VARCHAR(500) DEFAULT NULL COMMENT '想说的话或视频说明',
  `tag` VARCHAR(50) DEFAULT NULL COMMENT '标签，例如吉他弹唱、给xixi、练习版',
  `video_url` VARCHAR(1000) NOT NULL COMMENT 'OSS视频访问地址',
  `cover_url` VARCHAR(1000) DEFAULT NULL COMMENT 'OSS封面图访问地址',
  `duration_seconds` INT DEFAULT NULL COMMENT '视频时长，单位秒，可为空',
  `sort_order` INT NOT NULL DEFAULT 0 COMMENT '排序值，越大越靠前',
  `status` TINYINT NOT NULL DEFAULT 1 COMMENT '状态：1展示，0隐藏',
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_status_sort_time` (`status`, `sort_order`, `create_time`),
  KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='吉他视频卡片表';
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

吉他视频 OSS 路径：

```text
love530/lovestory/videos
love530/lovestory/videos/covers
```

⚠️ 严重警告：不要提交真实数据库密码、OSS AccessKey 或 AccessKeySecret。

## 代码规范

Java 命名：

- 类名使用 `UpperCamelCase`：`UploadPhotoController`、`PhotoDao`。
- 方法名和变量名使用 `lowerCamelCase`：`uploadPhoto`、`photoRecord`。
- 常量使用 `UPPER_SNAKE_CASE`：`ALLOWED_CATEGORIES`、`TIME_FORMATTER`。
- 包名全小写：`com.ycxandwuqian.love`。
- Controller 以 `Controller` 结尾。
- DAO 接口以 `Dao` 结尾。
- MyBatis XML 映射文件以 `Mapper.xml` 结尾，并与 DAO namespace 对齐。
- Service 接口以 `Service` 结尾，实现类以 `ServiceImpl` 结尾。

**关键**：当前历史文件 `uploadPhotoService.java`、`uploadPhotoServiceImpl.java` 不符合 Java 常用类名规范。新增或重命名时使用 `UploadPhotoService`、`UploadPhotoServiceImpl`。

Spring 约定：

- 优先使用构造器注入。
- Controller 只处理 HTTP 参数、响应和异常边界。
- 数据库访问统一通过 MyBatis DAO 接口完成。
- SQL 统一写在 `src/main/resources/mapper` 下的 XML Mapper 中。
- 每个 MyBatis Mapper XML 都必须能被 `application.yml` 中的 `mybatis.mapper-locations: classpath*:mapper/**/*.xml` 扫描到。
- 业务规则优先放入 Service。
- 不在 Controller、Service 或普通 Java 类中硬编码数据库 SQL。
- 不再新增 `JdbcTemplate`、`PreparedStatement`、JPA Repository 或 Java 内联 SQL。
- 不直接实例化 `OssUtil`，通过 Spring 注入或 `ObjectProvider<OssUtil>` 获取。

静态资源约定：

- 页面文件放在 `src/main/resources/static`。
- 图片放在 `src/main/resources/static/images`。
- 吉他视频卡片模块维护在 `src/main/resources/static/index.html`，替代原 `甜蜜回忆 · Memory Cards` 模块。
- 视频卡片数据来自 `/api/guitar-videos`，不要在前端硬编码视频 URL。
- 视频卡片尺寸要保持接近照片墙卡片；当只有一个视频时，不要让 CSS Grid 把单张卡片撑满整行。
- 前端上传视频时，如果用户未选择封面，可以用 `<video>` + `<canvas>` 从本地视频截帧生成封面，并通过 `cover` 字段上传。
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
- DAO/Mapper 新增 SQL 时覆盖成功、空结果、删除失败。
- OSS 不可用时必须覆盖 `ossUtilProvider.getIfAvailable() == null` 分支。
- 上传接口必须覆盖空文件、非法后缀、非法分类、正常上传。
- Spring 上下文测试中 mock `DataSource` 和 `PhotoDao`，避免连接真实数据库。
- Spring 上下文测试中也要 mock `GuitarVideoDao`，避免连接真实数据库。
- 吉他视频逻辑测试集中在 `GuitarVideoServiceImplTests`，覆盖列表、上传、标题为空、非法视频后缀、封面上传、删除和未找到记录等分支。

覆盖率目标：

- `UploadPhotoController` 新增逻辑分支不低于 80%。
- `PhotoDao` / `PhotoMapper.xml` 新增 SQL 分支必须有测试覆盖。
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
- **关键**：数据库字段变更时，同步更新 `PhotoDao`、`PhotoMapper.xml`、模型和测试。
- **关键**：吉他视频表字段变更时，同步更新 `GuitarVideoRecord`、`GuitarVideoDao`、`GuitarVideoMapper.xml`、`GuitarVideoServiceImplTests` 和前端展示字段。
- **关键**：OSS 配置必须支持环境变量。
- ⚠️ 不要提交 `target/` 下的图片或 class 文件。
- ⚠️ 不要在测试中调用真实 OSS 或真实远程数据库。
