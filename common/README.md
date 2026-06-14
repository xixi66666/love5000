# common

`common` 是 `love530` Maven 聚合工程的公共能力模块，不作为独立 Web 服务启动。它为业务模块提供 OSS 自动配置、上传工具和通用 Session 认证能力。

## 功能

- `love530.oss` OSS 配置绑定与 `OssUtil` 自动装配。
- OSS 上传、删除、URL 生成和 object key 解析。
- 通用认证接口：注册、登录、登出、当前用户。
- BCrypt 密码哈希、Session 登录态、`@AuthRequired` 和 `AuthInterceptor`。
- `AuthUserRepository` 契约，由业务模块适配自己的用户表。

## 运行命令

```bash
mvn -pl common test
mvn -pl common -am clean install
```

`common` 的 `spring-boot-maven-plugin` 配置了 `<skip>true</skip>`，不要用它启动独立服务。

## 主要结构

```text
src/main/java/com/example/common/
  auth/       通用认证能力
  config/     OSS 自动配置
  util/       OSS 工具和上传结果 DTO
src/main/resources/META-INF/spring.factories
src/test/java/com/example/common/
```

## 配置

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

不要提交真实 OSS AccessKey。`love530.oss.enabled=false` 时，依赖 `common` 的业务模块也必须能正常启动。

## 测试

```bash
mvn -pl common test
```

新增 OSS 行为时补充 `OssUtilTests`；新增认证流程时补充 `AuthServiceImplTests`。测试不得连接真实 OSS 或使用真实密钥。

## 文档维护

每次修改公共 API、自动配置、配置前缀、认证能力、OSS 行为、测试方式或模块边界时，必须同步更新 `common/AGENTS.md`、本 README，以及根目录 `AGENTS.md` / `README.md` 中相关内容。
