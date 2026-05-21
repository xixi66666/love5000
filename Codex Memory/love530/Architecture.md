---
project: love530
type: architecture
module: all
updated: 2026-05-10
---

# Architecture

父工程 `love530` 是 Maven 聚合工程，模块包括 `website`、`lovestory`、`common`、`imagetemplate`。根 `pom.xml` 管理 Java 8、Spring Boot 2.6.13、MyBatis Spring Boot 2.2.2、Spring Cloud Alibaba 2021.0.5.0 和 Aliyun Spring Boot 1.0.0 等公共版本。

## 模块边界

- `common` 保持低耦合，只提供公共接口、模型、服务契约、自动配置、OSS 工具和认证能力；不得依赖 `lovestory`、`website` 等业务模块。
- `lovestory` 依赖 `common` 的 OSS 能力，负责相册页面、照片接口、照片 MyBatis DAO、照片 Mapper 和小游戏静态页面。
- `website` 依赖 `common`，负责个人主页、博客微应用、认证用户仓储适配、Web/OSS/Nacos 示例。
- `imagetemplate` 不依赖 MySQL、MyBatis、OSS 或 `common`，模板数据来自 classpath JSON，图片生成由服务端调用 OpenAI API。

## 分层约定

- Controller：处理 HTTP 入参、响应组装和异常映射。
- Service：承载业务规则、事务边界、模板渲染、外部 API 调用等业务逻辑。
- DAO：只定义 MyBatis 数据访问接口。
- Mapper XML：集中维护 SQL，放在模块 `src/main/resources/mapper` 下。
- DTO：承载前后端请求和响应对象。
- Model：承载数据库记录或模板数据模型。

## 关键包结构

- `common/src/main/java/com/example/common/config`：公共配置和自动装配，例如 `OssAutoConfiguration`、`OssProperties`。
- `common/src/main/java/com/example/common/util`：公共工具类，例如 `OssUtil`、`OssUploadResult`。
- `common/src/main/java/com/example/common/auth`：公共认证能力，包括 BCrypt、Session、`/api/auth`、`@AuthRequired` 和拦截器。
- `lovestory/src/main/java/com/ycxandwuqian/love/controller`：相册 REST API。
- `lovestory/src/main/java/com/ycxandwuqian/love/dao`：`PhotoDao`。
- `lovestory/src/main/resources/mapper`：`PhotoMapper.xml`。
- `website/src/main/java/com/example/website/blog`：博客 Controller、Service、DAO、Model、DTO。
- `website/src/main/resources/mapper/auth`：认证用户 Mapper。
- `website/src/main/resources/mapper/blog`：博客 Mapper。
- `imagetemplate/src/main/java/com/example/imagetemplate/controller`：图片模板 API。
- `imagetemplate/src/main/java/com/example/imagetemplate/service`：模板加载、prompt 渲染、OpenAI 图片生成。

## 静态资源

- `lovestory/src/main/resources/static`：相册、登录页、小游戏、留言板、照片墙页面。
- `website/src/main/resources/static`：主页 CSS、JS、图片、SVG、音效。
- `website/src/main/resources/static/blog`：博客前端页面和资源。
- `imagetemplate/src/main/resources/static`：图片模板库单页前端。

相关规则见 [[Development Rules]]，测试要求见 [[Testing]]。
