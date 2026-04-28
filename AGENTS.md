# AGENTS.md

## 项目概述

**love530** 是一个多模块 Maven Spring Boot 项目，包含照片分享网站和互动小游戏。

- **类型**: Web 应用（服务端渲染 + REST API）
- **语言**: Java 8
- **框架**: Spring Boot 2.6.13 + Spring Cloud Alibaba 2021.0.5.0
- **前端**: 原生 HTML/CSS/JS，无框架，静态文件内联在 HTML 中
- **数据库**: MySQL（阿里云远程实例），通过 JdbcTemplate 直接操作
- **存储**: 阿里云 OSS（对象存储），由 common 模块提供自动配置
- **构建**: Maven，多模块父子结构

### 三模块架构

| 模块 | 端口 | 职责 | 启动类 |
|------|------|------|--------|
| `lovestory` | 8081 | 主应用：登录门禁、照片上传/展示/删除、贪吃蛇/消消乐/井字棋小游戏 | `com.ycxandwuqian.love.LovestoryApplication` |
| `website` | 8080 | 辅助应用：静态页面、Demo 控制器、Nacos 演示（已注释） | `com.example.website.WebsiteApplication` |
| `common` | — | 公共库：OSS 上传/删除/URL 生成工具、自动配置 | 不可独立运行 |

**模块依赖**: `lovestory` → `common`，`website` 独立（不依赖 `common`）。

---

## 开发命令

### 构建

```bash
# 全量构建（含测试）
mvn clean package

# 跳过测试构建
mvn clean package -DskipTests

# 仅构建 lovestory 及其依赖
mvn clean package -pl lovestory -am

# 仅构建 common 模块
mvn clean package -pl common
```

### 运行

```bash
# 启动 lovestory（端口 8081）
mvn spring-boot:run -pl lovestory

# 启动 website（端口 8080）
mvn spring-boot:run -pl website
```

⚠️ **启动需要连接远程 MySQL 数据库**（`49.232.128.132:3306`），本地无法连接时应用会启动失败。

### 测试

```bash
# 运行全部测试
mvn test

# 运行 common 模块的 OSS 工具测试
mvn test -pl common -Dtest=OssUtilTests

# 运行 lovestory 模块测试
mvn test -pl lovestory
```

### 打包产物

```bash
# lovestory 的 Spring Boot 可执行 jar
java -jar lovestory/target/lovestory-0.0.1-SNAPSHOT.jar
```

---

## 项目结构

```
love5000/
├── pom.xml                          # 父 POM（pom 打包，管理版本）
├── lovestory/                       # ★ 主应用模块（最活跃）
│   ├── pom.xml
│   └── src/
│       ├── main/java/com/ycxandwuqian/love/
│       │   ├── LovestoryApplication.java
│       │   ├── config/WebConfig.java              # MVC 视图控制器 + 静态资源映射
│       │   ├── controller/
│       │   │   ├── LoginController.java           # GET /login, POST /api/login/verify
│       │   │   └── UploadPhotoController.java     # POST/GET/DELETE /api/photos/*
│       │   ├── model/PhotoRecord.java             # 照片实体（手写 getter/setter）
│       │   ├── repository/PhotoRepository.java    # JdbcTemplate CRUD
│       │   └── service/
│       │       ├── uploadPhotoService.java        # 接口（目前是空壳）
│       │       └── uploadPhotoServiceImpl.java
│       ├── main/resources/
│       │   ├── application.yml                    # 数据库、OSS、文件上传配置
│       │   ├── application.properties             # server.port=8081
│       │   └── static/                            # ★ 前端文件全部在这里
│       │       ├── index.html                     # 主页（照片廊 + 游戏入口）
│       │       ├── login.html                     # 登录页面
│       │       ├── snake.html                     # 贪吃蛇
│       │       ├── match3.html                    # 消消乐
│       │       ├── tic-tac-toe.html               # 井字棋
│       │       └── images/                        # 本地照片素材
│       └── test/
├── website/                         # 辅助 Web 应用
│   ├── pom.xml
│   └── src/main/java/com/example/website/
│       ├── WebsiteApplication.java
│       └── demos/                   # 各种 Demo 代码
├── common/                          # 公共工具库（OSS 自动配置）
│   ├── pom.xml
│   └── src/main/java/com/example/common/
│       ├── config/
│       │   ├── OssAutoConfiguration.java   # @ConditionalOnProperty("love530.oss.enabled")
│       │   └── OssProperties.java          # @ConfigurationProperties("love530.oss")
│       └── util/
│           ├── OssUtil.java                # 上传、删除、URL 生成、存在性检查
│           └── OssUploadResult.java
└── src/                             # 父级空壳目录，可忽略
```

---

## 代码规范

### Java 命名规范

遵循 **Oracle 官方 Java 命名约定**，以下结合本项目的具体示例说明。

#### 类名（PascalCase，大驼峰）

每个单词首字母大写，使用名词或名词短语。

| ✅ 正确 | ❌ 错误（本项目存在的反例） |
|----------|----------|
| `UploadPhotoController` | — |
| `PhotoRepository` | — |
| `UploadPhotoService` | `uploadPhotoService`（接口名小写开头） |
| `UploadPhotoServiceImpl` | `uploadPhotoServiceImpl`（实现类名小写开头） |

⚠️ **当前项目中 `lovestory` 模块的 `uploadPhotoService` 和 `uploadPhotoServiceImpl` 命名不符合规范**，新建 Service 时请使用正确命名。

#### 接口（PascalCase，与类相同）

接口名与类名规则一致，**不加 `I` 前缀**。实现类名 = 接口名 + `Impl`。

```java
// ✅ 正确
public interface UploadPhotoService { ... }
public class UploadPhotoServiceImpl implements UploadPhotoService { ... }

// ❌ 错误
public interface uploadPhotoService { ... }      // 小写开头
public interface IUploadPhotoService { ... }     // 不用 I 前缀
public class UploadPhotoServiceImp { ... }       // 用完整 Impl 而非 Imp
```

#### 方法名（camelCase，小驼峰）

首字母小写，使用动词或动词短语。

| ✅ 正确 | ❌ 错误 |
|----------|----------|
| `findById(Long id)` | `FindById(Long id)` |
| `deleteById(Long id)` | `DeleteById(Long id)` |
| `getObjectUrl(String key)` | `GetObjectUrl(String key)` |
| `isSupportedImage(String name)` | `IsSupportedImage(String name)` |

#### 变量名（camelCase，小驼峰）

局部变量、成员变量、方法参数均用小驼峰。

```java
// ✅ 正确
private final JdbcTemplate jdbcTemplate;
private final ObjectProvider<OssUtil> ossUtilProvider;
String originalFilename = file.getOriginalFilename();
OssUploadResult uploadResult = ossUtil.upload(file, baseDir);

// ❌ 错误
private final JdbcTemplate JdbcTemplate;       // 变量名不能大驼峰
String OriginalFilename = ...;                  // 局部变量不能大驼峰
```

#### 常量（UPPER_SNAKE_CASE，全大写+下划线）

`static final` 修饰的不可变常量使用全大写，下划线分隔。

```java
// ✅ 正确（当前项目已遵循）
private static final String CORRECT_ANSWER = "我爱你的很";
private static final Set<String> ALLOWED_CATEGORIES = ...;
private static final DateTimeFormatter TIME_FORMATTER = ...;
private static final RowMapper<PhotoRecord> PHOTO_ROW_MAPPER = ...;
```

#### 包名（全小写）

包名全部小写，使用点分隔。各模块包名如下：

| 模块 | 包名 |
|------|------|
| `lovestory` | `com.ycxandwuqian.love` |
| `website` | `com.example.website` |
| `common` | `com.example.common` |

**新增类必须放在对应模块的现有包名下**，子包按类型划分：`controller`、`service`、`repository`、`model`、`config`。

#### 文件命名

文件名必须与其中唯一的 `public` 类名完全一致（含大小写）：

```
UploadPhotoController.java  →  public class UploadPhotoController
PhotoRecord.java            →  public class PhotoRecord
uploadPhotoService.java     →  public interface uploadPhotoService  ⚠️ 类名和文件名需同步改为大驼峰
```

---

### Java 其他规范

- **Java 版本**: 1.8——不能使用 `var`、`record`、`switch` 表达式等新版语法。
- **Bean**: 手写 getter/setter，**不使用 Lombok**（common 模块的 Lombok 依赖标记为 `optional:true`，实际未使用）。
- **依赖注入**: 使用构造器注入（如 `PhotoRepository(JdbcTemplate)`），不使用 `@Autowired` 字段注入。
- **数据访问**: 直接使用 `JdbcTemplate`，无 ORM（无 JPA、无 MyBatis）。SQL 内嵌在 Java 代码中。
- **响应格式**: API 统一返回 `Map<String, Object>`，包含 `success`（boolean）和 `message`（String）字段。
- **异常处理**: try-catch 捕获 `IllegalArgumentException`、`IllegalStateException`、`DataAccessException` 后返回错误 Map。
- **控制器**: JSON 接口用 `@RestController`，页面跳转用 `@Controller` 返回视图名。
- **注释和提交消息**: 使用中文。

### 前端

- **无框架**: 所有页面使用原生 HTML/CSS/JS，不引入任何第三方前端库。
- **单文件**: CSS 和 JS 全部内联在 HTML 文件的 `<style>` 和 `<script>` 标签中，不创建单独的 `.css`/`.js` 文件。
- **静态资源**: 放在 `lovestory/src/main/resources/static/` 目录下，通过类路径直接访问。

### 配置

- **OSS 配置**: 通过 `love530.oss.*` 前缀配置，支持环境变量覆盖（如 `${LOVE530_OSS_ENABLED:true}`）。
- **common 模块自动配置**: 使用 `spring.factories` 注册（`META-INF/spring.factories`），通过 `love530.oss.enabled=true/false` 控制启用。
- **模块端口**: lovestory → 8081，website → 8080。

---

## 测试策略

- **框架**: JUnit 5 + Spring Boot Test + Mockito
- **当前测试极少**: 仅 `common` 模块有 2 个针对 `OssUtil` 的单元测试，`lovestory` 有一个 Mock DataSource 的上下文加载测试
- **添加新代码时**: 为 `controller`（使用 `@WebMvcTest`）和 `service/repository`（使用 `@DataJdbcTest` 或纯 Mockito）添加测试
- **OSS 相关测试不需要真实连接**: 使用 Mock 替换 `OssUtil`
- **运行**: `mvn test` 在根目录执行全部测试

---

## 关键约定

### OSS 文件操作模式

上传照片的标准流程：
1. `OssUtil.upload(file, baseDir)` → 上传到 OSS，返回 `OssUploadResult`（含 objectKey 和 URL）
2. `PhotoRepository.save(objectKey, category)` → 将记录写入数据库
3. 返回 URL 给前端展示

删除照片的反向流程：
1. `OssUtil.delete(objectKey)` → 从 OSS 删除文件
2. `PhotoRepository.deleteById(id)` → 从数据库删除记录

### `OssUtil` 获取方式

`OssUtil` 是可选 Bean（通过 `@ConditionalOnProperty` 控制），在 `lovestory` 中使用 `ObjectProvider<OssUtil>` 获取：

```java
OssUtil ossUtil = ossUtilProvider.getIfAvailable();
if (ossUtil == null) {
    // OSS 未配置时的降级逻辑
}
```

### ⚠️ 安全警告

`application.yml` 中包含数据库密码和 OSS AccessKey。**不要将这些凭据提交到公开仓库**，已提交的历史凭据建议在阿里云控制台轮换。

---

## Git 工作流

- **单分支**: 所有开发在 `master` 分支进行，无 feature 分支、无 PR 流程
- **提交消息**: 中文，格式为 `日期 简要描述`（如 `04.27 优化上传功能`）
- **提交前检查**: 确保 `mvn clean package` 构建通过
