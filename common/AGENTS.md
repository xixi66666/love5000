# AGENTS.md

## 项目概述

`common` 是 `love530` Maven 聚合工程中的公共能力微服务模块，路径：

```text
C:/Code/Java_Code/love5000/common
```

该模块不是独立 Web 服务，职责是向其他模块提供可复用的基础能力，当前核心功能是阿里云 OSS 自动配置、文件上传、文件删除、OSS URL 生成和 object key 解析。

技术栈：

- Java 8
- Maven
- Spring Boot 2.6.13
- Spring Boot AutoConfiguration
- Aliyun OSS SDK 3.1.0
- Spring Web
- Spring Boot Configuration Processor
- JUnit 5 / Spring Boot Test

配置文件：

- `pom.xml`：模块依赖、Java 8 编译配置、Surefire 测试配置。
- `src/main/resources/META-INF/spring.factories`：注册 `OssAutoConfiguration`。

**关键**：`common` 必须保持低耦合。不要在该模块中依赖 `lovestory` 或 `website` 的业务类。

## 开发命令

默认从仓库根目录执行：

```bash
cd C:/Code/Java_Code/love5000
```

安装父工程和当前模块依赖：

```bash
mvn -pl common -am clean install
```

运行 `common` 模块测试：

```bash
mvn -pl common test
```

打包 `common` 模块：

```bash
mvn -pl common -am clean package
```

跳过测试打包：

```bash
mvn -pl common -am clean package -DskipTests
```

检查 Maven 依赖树：

```bash
mvn -pl common dependency:tree
```

从模块目录执行测试：

```bash
cd C:/Code/Java_Code/love5000/common
mvn test
```

**关键**：`common` 的 `spring-boot-maven-plugin` 配置了 `<skip>true</skip>`，不要把它当作独立服务启动。

## 项目结构

```text
common/
├── pom.xml
├── AGENTS.md
└── src/
    ├── main/
    │   ├── java/com/example/common/
    │   │   ├── CommonApplication.java
    │   │   ├── config/
    │   │   │   ├── OssAutoConfiguration.java
    │   │   │   └── OssProperties.java
    │   │   └── util/
    │   │       ├── OssUploadResult.java
    │   │       └── OssUtil.java
    │   └── resources/META-INF/spring.factories
    └── test/java/com/example/common/
        ├── CommonApplicationTests.java
        └── util/OssUtilTests.java
```

核心模块职责：

- `config/OssAutoConfiguration.java`：根据 `love530.oss.enabled` 自动创建 `OssUtil` Bean。
- `config/OssProperties.java`：承载 `love530.oss` 配置项。
- `util/OssUtil.java`：封装 OSS 上传、删除、URL 拼接和 object key 解析。
- `util/OssUploadResult.java`：上传结果 DTO。
- `META-INF/spring.factories`：Spring Boot 2.x 自动配置入口。

## 配置约定

OSS 配置统一使用 `love530.oss` 前缀：

```yaml
love530:
  oss:
    enabled: true
    endpoint: oss-cn-beijing.aliyuncs.com
    access-key-id: ${LOVE530_OSS_ACCESS_KEY_ID}
    access-key-secret: ${LOVE530_OSS_ACCESS_KEY_SECRET}
    bucket-name: lovestory5000
    url-prefix: ${LOVE530_OSS_URL_PREFIX:}
    base-dir: love530/lovestory/photos
```

⚠️ 严重警告：不要把真实 `access-key-id`、`access-key-secret`、Bucket 写死在测试或源码中。

## 代码规范

- 包名使用全小写：`com.example.common.config`、`com.example.common.util`。
- 类名使用 `UpperCamelCase`：`OssAutoConfiguration`、`OssProperties`、`OssUtil`。
- 方法名和变量名使用 `lowerCamelCase`：`getObjectUrl`、`extractObjectKey`。
- 常量使用 `UPPER_SNAKE_CASE`。
- 配置属性类使用 `@ConfigurationProperties`，不要在工具类里直接读取环境变量。
- 自动配置必须使用条件注解，避免污染业务模块上下文：

```java
@ConditionalOnClass(OSSClientBuilder.class)
@ConditionalOnProperty(prefix = "love530.oss", name = "enabled", havingValue = "true")
@ConditionalOnMissingBean
```

**关键**：`love530.oss.enabled=false` 时，依赖 `common` 的服务必须仍然可以启动。

## 测试策略

测试框架：

- JUnit 5
- Spring Boot Test
- Maven Surefire 2.22.2

运行测试：

```bash
mvn -pl common test
```

重点测试范围：

- `OssUtil#getObjectUrl`
- `OssUtil#extractObjectKey`
- 自定义 CDN 域名场景
- URL 带 query string 的 object key 解析
- 空配置和非法配置校验

测试要求：

- 不连接真实阿里云 OSS。
- 不使用真实 AccessKey。
- 新增 OSS 行为时必须补充 `OssUtilTests`。
- 新增自动配置条件时必须补充 Spring context 测试。

覆盖率目标：

- `OssUtil` 核心分支不低于 80%。
- `OssAutoConfiguration` 的开启和关闭场景都要覆盖。

## 提交前检查

```bash
mvn -pl common clean test
```

检查清单：

- **关键**：不要新增对业务模块的依赖。
- **关键**：不要破坏 `spring.factories` 自动配置入口。
- **关键**：不要提交真实 OSS 密钥。
- ⚠️ 不要在测试中上传真实文件到 OSS。
