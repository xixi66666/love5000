# AGENTS.md

## 模块概述

`guitar` 是 `love530` 的 Java 8 + Spring Boot 2.6.13 Web 子模块，默认端口为 `8088`。当前提供基础首页、健康检查、手机号注册登录、Session/CSRF 鉴权，以及 Guitar 曲谱平台 MySQL 数据基础。

## 开发命令

从仓库根目录运行：

```bash
mvn -pl guitar -am test
mvn -f guitar/pom.xml spring-boot:run
```

访问地址：

```text
http://127.0.0.1:8088/
http://127.0.0.1:8088/api/health
```

## 模块边界

- 正式代码放在 `com.example.guitar` 下，不把业务代码放入 `demos`。
- 新增跨模块公共能力时优先复用或扩展 `common`。
- 用户和业务数据使用 MySQL 数据库 `guitar`，数据访问遵循 DAO + XML Mapper 约定，不使用 JPA、JdbcTemplate 或 Java 内联 SQL。
- 认证代码放在 `com.example.guitar.auth`，用户模型和 DAO 放在 `com.example.guitar.user`；密码哈希复用 `common` 的 `AuthPasswordService`。
- 认证 Session 属性名固定为 `GUITAR_AUTH_USER`；所有 POST/PUT/PATCH/DELETE 请求都必须校验 `X-CSRF-Token`。
- `/api/users/**`、`/api/favorite-folders/**` 和非 GET `/api/sheets/**` 要求登录，`/api/admin/**` 要求 ADMIN。
- OSS 默认关闭，未明确需要前不引入 Nacos 或其他外部服务。
- 新增接口响应至少包含 `success` 字段，并覆盖成功路径和主要失败路径。
- 不提交密钥、`target/`、IDE 缓存或运行日志。

## 验证要求

- 修改 Java 代码后运行 `mvn -pl guitar -am test`。
- 修改首页后启动服务并验证 `/` 与 `/api/health`。
- 修改端口、名称或健康地址时，同步更新根 `AGENTS.md` 和 Website 主页入口。

## 认证接口

```text
GET  /api/auth/session
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
```

客户端先调用 `GET /api/auth/session` 创建 Session 并获取 `csrfToken`，再将其作为 `X-CSRF-Token` 请求头发送到注册、登录、注销及其他写接口。
