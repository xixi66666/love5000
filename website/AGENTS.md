# AGENTS.md

## 项目概述

`website` 是 `love530` Maven 聚合工程中的个人主页/展示站点 Web 微服务，路径：

```text
C:/Code/Java_Code/love5000/website
```

核心功能：

- 提供个人主页静态站点。
- 提供基础 Spring MVC Web Demo。
- 保留 OSS Demo 和 Nacos Discovery 示例代码。
- 使用 MySQL 和 Druid 作为后端数据源配置。

技术栈：

- Java 8
- Maven
- Spring Boot 2.6.13
- Spring MVC
- MySQL Connector/J
- Alibaba Druid 1.1.22
- JUnit 5 / Spring Boot Test
- HTML / CSS / JavaScript

配置文件：

- `pom.xml`：模块依赖、Java 8 编译配置、Spring Boot 主类。
- `src/main/resources/application.properties`：端口和历史示例配置。
- `src/main/resources/application.yml`：MySQL、Druid、静态资源路径。

**关键**：`website` 是可独立启动的 Web 服务，默认端口为 `8080`。

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

## 项目结构

```text
website/
├── pom.xml
├── AGENTS.md
└── src/
    ├── main/
    │   ├── java/com/example/website/
    │   │   ├── WebsiteApplication.java
    │   │   ├── demos/
    │   │   │   ├── nacosdiscoveryconsumer/
    │   │   │   ├── nacosdiscoveryprovider/
    │   │   │   ├── oss/
    │   │   │   └── web/
    │   │   └── nacosdiscovery/
    │   └── resources/
    │       ├── application.properties
    │       ├── application.yml
    │       ├── index.html
    │       ├── README.md
    │       └── static/
    │           ├── css/style.css
    │           ├── js/script.js
    │           ├── img/
    │           ├── soundeffects/
    │           └── svg/
    └── test/java/com/example/website/
        └── WebsiteApplicationTests.java
```

核心模块职责：

- `WebsiteApplication.java`：Spring Boot 启动类。
- `demos/web`：基础 Web Controller 示例。
- `demos/oss`：OSS 示例代码。
- `demos/nacosdiscoveryconsumer`：Nacos 消费者示例。
- `demos/nacosdiscoveryprovider`：Nacos 提供者示例。
- `nacosdiscovery`：Nacos Discovery 配置。
- `static/css/style.css`：站点样式。
- `static/js/script.js`：站点交互。
- `static/img`、`static/svg`、`static/soundeffects`：图片、图标、音效资源。

## 配置约定

默认端口：

```properties
server.port=8080
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

⚠️ 严重警告：不要提交真实数据库密码。新增配置时使用环境变量，例如 `${WEBSITE_DB_PASSWORD}`。

## 代码规范

Java 命名：

- 类名使用 `UpperCamelCase`：`WebsiteApplication`、`BasicController`。
- 方法名和变量名使用 `lowerCamelCase`。
- 常量使用 `UPPER_SNAKE_CASE`。
- 包名全小写：`com.example.website`。
- Controller 类以 `Controller` 结尾。
- Configuration 类以 `Configuration` 或 `Config` 结尾。

Spring 约定：

- Controller 只放 HTTP 示例或页面接口，不承载复杂业务逻辑。
- 示例代码放在 `demos` 包下，生产化代码不要继续塞进 `demos`。
- Nacos 相关代码集中在 `nacosdiscovery` 和 `demos/nacosdiscovery*`。
- 新增配置优先写入 `application.yml`，端口等简单开关可保留在 `application.properties`。

前端静态资源约定：

- CSS 修改放在 `src/main/resources/static/css/style.css`。
- JS 修改放在 `src/main/resources/static/js/script.js`。
- 图片放在 `src/main/resources/static/img`。
- SVG 图标放在 `src/main/resources/static/svg`。
- 音效放在 `src/main/resources/static/soundeffects`。
- 页面引用资源时使用相对路径，不使用本机绝对路径。

## 测试策略

测试框架：

- JUnit 5
- Spring Boot Test

运行测试：

```bash
mvn -pl website -am test
```

当前已有测试：

```text
src/test/java/com/example/website/WebsiteApplicationTests.java
```

测试要求：

- 新增 Controller 时补充 Spring MVC 或 context 测试。
- 修改 Nacos 示例时，测试中不要依赖真实 Nacos 服务。
- 修改数据库相关配置时，测试中不要连接远程 MySQL。
- 修改静态页面后，启动服务并访问 `http://localhost:8080/` 手动验证。

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

- **关键**：不要把正式业务代码继续放进 `demos` 包。
- **关键**：静态资源路径必须能从 `classpath:/static/` 加载。
- **关键**：数据库密码和 Nacos 密码使用环境变量。
- ⚠️ 不要在单元测试中连接真实 Nacos、真实 MySQL 或外部 OSS。
- ⚠️ 不要提交 `target/`、IDE 缓存或运行时生成文件。
