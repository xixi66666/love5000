---
project: love530
type: testing
module: all
updated: 2026-05-10
---

# Testing

## 测试框架

- JUnit 5
- Spring Boot Test
- AssertJ
- Maven Surefire 2.22.2

## 必跑命令

```bash
mvn test
mvn -pl common test
mvn -pl lovestory -am test
mvn -pl website -am test
mvn -pl imagetemplate -am test
```

跨模块改动跑 `mvn test`。只改某个模块时优先跑对应模块测试。

## common

```bash
mvn -pl common test
```

- `OssUtil` 写纯单元测试，不依赖真实 OSS。
- 覆盖 `getObjectUrl`、`extractObjectKey`、自定义 CDN 域名、URL query string、空配置和非法配置。
- 新增 OSS 行为时补充 `OssUtilTests`。
- 新增自动配置条件时补充 Spring context 测试。
- `OssUtil` 核心分支目标不低于 80%。

## lovestory

```bash
mvn -pl lovestory -am test
```

- 数据库相关测试 mock DAO、使用内存库或隔离测试配置，不连接远程 MySQL。
- Controller 新增接口时补充 MockMvc 测试。
- DAO/Mapper 新增 SQL 时覆盖成功、空结果、删除失败。
- OSS 不可用时覆盖 `ossUtilProvider.getIfAvailable() == null` 分支。
- 上传接口覆盖空文件、非法后缀、非法分类、正常上传。
- 静态页面修改至少手动访问 `http://localhost:8081/` 验证。

## website

```bash
mvn -pl website -am test
```

- 新增 Controller 时补充 Spring MVC 或 context 测试。
- 新增 DAO/Mapper SQL 时覆盖成功路径、空结果和主要失败路径。
- 修改 Nacos 示例时，测试中不要依赖真实 Nacos 服务。
- 修改数据库相关配置时，测试中不要连接远程 MySQL。
- 修改静态页面后，启动服务并访问 `http://localhost:8080/` 手动验证。

## imagetemplate

```bash
mvn -pl imagetemplate test
mvn -pl imagetemplate -am test
```

- 模板渲染测试覆盖分类、关键词、变量替换、嵌套 JSON、列表字段、`extraInstruction` 和模板不存在。
- 新增模板时更新模板数量断言。
- 新增分类时覆盖 `categorySlug`。
- OpenAI 图片生成测试不得真实调用外部 API。
- OpenAI 相关测试使用 mock 或可注入 HTTP 客户端。
- 新增生成逻辑必须覆盖无 API Key、OpenAI 错误响应、空图片数据响应。

## 覆盖率

- 项目当前没有统一 JaCoCo。
- 如果需要覆盖率门禁，在父 `pom.xml` 统一配置 `jacoco-maven-plugin`。
- 不要只在单模块单独配置覆盖率门禁。

开发规则见 [[Development Rules]]。
