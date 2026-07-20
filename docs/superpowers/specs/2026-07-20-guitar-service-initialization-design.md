# Guitar 微服务初始化设计

## 背景

仓库根目录新增了 `guitar` Spring Boot 工程。当前工程使用 Java 8 和 Spring Boot 2.6.13，但仍是独立脚手架状态：包含嵌套 `.git`、生成器示例代码和 OSS 示例，端口为与 `website` 冲突的 `8080`，POM 未继承父工程，也未加入 Maven 聚合。

本次只完成最小可运行初始化，不提前实现 Guitar 业务功能。

## 目标

- 将 `guitar` 接入 `love530` Maven 父工程。
- 使用固定端口 `8088`，支持独立启动和聚合构建。
- 提供可用于总站检测的健康接口和一个正式的基础首页。
- 将 Guitar 入口同步到 `website` 主页及项目文档。
- 清理独立脚手架遗留内容，确保测试不依赖数据库、OSS 或外部网络。

## 非目标

- 不实现曲谱、练习、音视频、上传或用户等 Guitar 业务。
- 不建立空的 Service、DAO、Mapper 分层。
- 不引入数据库、MyBatis、OSS、认证或服务发现。
- 不让 `website` 自动启动或管理 Guitar Java 进程。

## 架构与模块边界

`guitar` 是 `love530` 的标准 Spring Boot 子模块，包名保持 `com.example.guitar`。根 POM 统一管理 Java 8、Spring Boot 2.6.13 和依赖版本；`guitar/pom.xml` 只声明 Web、测试依赖及必要构建插件。

模块保持独立运行边界：

- 单独启动：`mvn -f guitar/pom.xml spring-boot:run`
- 单模块测试：`mvn -pl guitar -am test`
- 聚合构建：参与根目录 `mvn test` 和 `mvn clean install`

`website` 只提供导航、服务卡片和可用性检测，不创建 Guitar 自动启动器。这样避免一个 Java Web 服务负责另一个 Java Web 服务的进程生命周期。

## 初始化内容

### 清理

移除以下脚手架遗留内容：

- `guitar/.git`
- `guitar/HELP.md`
- `guitar/src/main/java/com/example/guitar/demos`
- `guitar/src/main/resources/oss-test.json`
- 原始示例首页
- Guitar POM 中的 Aliyun OSS 依赖和重复版本管理

保留并规范化 `GuitarApplication`、模块 `.gitignore` 和测试目录。

### Maven 接入

- 根 `pom.xml` 的 `<modules>` 增加 `guitar`。
- `guitar/pom.xml` 继承 `com.example:love530:0.0.1-SNAPSHOT`。
- 模块依赖仅保留 `spring-boot-starter-web` 和测试范围的 `spring-boot-starter-test`。
- Spring Boot 插件主类配置为 `com.example.guitar.GuitarApplication`。
- Surefire 使用仓库现有的 `2.22.2`，保证 JUnit 5 测试发现行为一致。

### 运行配置

`guitar/src/main/resources/application.properties` 只保留正式配置：

```properties
spring.application.name=guitar
server.port=8088
```

不添加数据库、OSS、Nacos 或密钥配置。

### HTTP 接口与首页

新增 `HealthController`：

```text
GET /api/health
```

成功响应为 HTTP 200：

```json
{
  "success": true,
  "service": "guitar"
}
```

接口不访问外部资源，因此只反映 Guitar Spring 应用本身是否可达。

`src/main/resources/static/index.html` 改为 Guitar 服务的最小正式首页。首页明确显示服务名称、端口和运行状态，并提供 `/api/health` 入口；不展示尚未实现的业务功能，也不引用本机绝对路径或外部 API。

## Website 集成

按照仓库的微服务主页入口约定，更新：

- `website/src/main/resources/static/index.html`：顶部导航和服务卡片增加 Guitar 入口。
- `website/src/main/resources/static/css/style.css`：增加与现有卡片体系一致的 Guitar 卡片样式。
- `website/src/main/resources/static/js/script.js`：不修改。现有通用健康检测已支持带 `data-health-url` 的卡片。

入口地址为 `http://127.0.0.1:8088/`，检测地址为 `http://127.0.0.1:8088/api/health`，使用现有 `no-cors` 检测模式。跨端口响应不可读时，浏览器返回 opaque response，现有逻辑将其视为网络可达；网络请求失败则显示不可用。

## 文档

- 新增 `guitar/AGENTS.md`，记录模块职责、端口、启动和测试命令、健康接口及后续开发边界。
- 更新根 `AGENTS.md` 的项目概述、模块清单、结构、端口、命令、主页入口和测试清单。

## 错误处理

- 健康接口不包含外部依赖或可恢复分支，正常启动后固定返回 HTTP 200。
- Spring 上下文或端口绑定失败时保留框架的明确启动错误，不增加吞掉异常的降级逻辑。
- Guitar 首页只使用模块内静态资源，避免外部资源失败影响基础可用性。
- Website 仅以网络可达性展示 Guitar 状态，不把 Guitar 不可用升级为 Website 启动失败。

## 测试与验收

Guitar 测试覆盖：

1. Spring Context 能正常加载。
2. `GET /api/health` 返回 HTTP 200、JSON 内容类型、`success=true` 和 `service=guitar`。
3. `GET /` 返回 HTTP 200，并包含 Guitar 服务标识。

实现后依次执行：

```bash
mvn -pl guitar -am test
mvn -pl website -am test
mvn test
```

测试不连接真实 MySQL、OSS、Nacos 或外部服务。手动运行验证使用：

```bash
mvn -f guitar/pom.xml spring-boot:run
```

验收地址：

```text
http://127.0.0.1:8088/
http://127.0.0.1:8088/api/health
```

## 完成标准

- `guitar` 不再是嵌套 Git 仓库，并由根仓库跟踪。
- Guitar 作为父工程模块可独立测试、启动并参与聚合构建。
- `8088` 无现有项目端口冲突。
- 健康接口和基础首页可访问。
- Website 导航、服务卡片和实时状态检测包含 Guitar。
- 根文档与模块文档准确描述 Guitar 边界和开发命令。
- 所有约定测试通过，且未引入真实密钥或外部服务依赖。
