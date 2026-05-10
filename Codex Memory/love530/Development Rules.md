---
project: love530
type: rules
module: all
updated: 2026-05-10
---

# Development Rules

## 总则

- 根目录 `pom.xml` 只负责模块聚合、公共版本和依赖管理。
- 业务代码必须放在对应模块内。
- 跨模块公共能力优先放入 `common`。
- 不修改 `.idea/`、`target/`、运行时生成文件，除非任务明确要求。
- 不提交真实数据库密码、OSS AccessKey、OpenAI API Key、生成图片 base64 文件。

## Java 命名

- 类名使用 `UpperCamelCase`。
- 方法名和变量名使用 `lowerCamelCase`。
- 常量使用 `UPPER_SNAKE_CASE`。
- 包名全部小写。
- Controller 类以 `Controller` 结尾。
- DAO 接口以 `Dao` 结尾。
- MyBatis XML 文件以 `Mapper.xml` 结尾。
- Service 接口或类以 `Service` 结尾，实现类以 `ServiceImpl` 结尾。
- DTO 类以 `Request`、`Response` 结尾。
- Exception 类以 `Exception` 结尾。

## Spring 约定

- 优先使用构造器注入，不使用字段注入。
- Controller 只处理 HTTP 入参、响应组装和异常映射。
- 业务规则放在 Service。
- 数据库访问放在 DAO + XML Mapper。
- 外部 API 调用封装在独立 Service，例如 `OpenAiImageGenerationService`。
- `common` 自动配置必须保持可选，使用 `@ConditionalOnProperty`、`@ConditionalOnClass`、`@ConditionalOnMissingBean`。
- `love530.oss.enabled=false` 时，依赖 `common` 的服务必须仍然可以启动。

## MyBatis 约定

使用数据库的 Web 模块必须显式配置：

```yaml
mybatis:
  mapper-locations: classpath*:mapper/**/*.xml
  configuration:
    map-underscore-to-camel-case: true
```

- 数据库 CRUD 使用 DAO + XML Mapper。
- 不新增 `JdbcTemplate`、`PreparedStatement`、JPA Repository 或 Java 内联 SQL。
- 数据库字段变更时，同步更新 Mapper XML、DAO、模型类和测试。
- 数据库表由开发者或运维提前创建，Java 启动流程不负责建表、补字段或写种子数据。

## 配置安全

- 新增配置优先使用环境变量。
- OSS 配置使用 `love530.oss` 前缀。
- OpenAI 配置使用 `openai` 前缀，并优先读取 `OPENAI_API_KEY`。
- `website` 数据库密码使用环境变量，例如 `${WEBSITE_DB_PASSWORD}`。
- `lovestory` OSS 和数据库配置不得写入真实密钥。

## 静态资源

- 静态资源使用相对路径或明确外部 URL，不引用本机绝对路径。
- `lovestory` 页面放在 `lovestory/src/main/resources/static`。
- `website` 主页资源放在 `website/src/main/resources/static/css`、`static/js`、`static/img`。
- `website` 博客资源放在 `website/src/main/resources/static/blog`。
- `imagetemplate` 页面放在 `imagetemplate/src/main/resources/static`，模板 JSON 放在 `imagetemplate/src/main/resources/templates`。

## 模块注意事项

- `common` 不作为独立服务启动，`spring-boot-maven-plugin` 配置了 `<skip>true</skip>`。
- `lovestory` 不重新实现 OSS 客户端，必须使用 `common` 的 `OssUtil`。
- `website` 生产化代码不要继续放进 `demos` 包。
- `imagetemplate` 不引入数据库访问层，模板持久化保持 JSON 文件。

相关结构见 [[Architecture]]，测试要求见 [[Testing]]。
