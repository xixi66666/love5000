# AGENTS.md

## 模块概述

`guitar` 是 `love530` 的 Java 8 + Spring Boot 2.6.13 Web 子模块，默认端口为 `8088`。当前只提供基础首页和健康检查，不使用数据库、OSS、认证或外部服务。

## 开发命令

从仓库根目录运行：

```bash
mvn -pl guitar -am test
mvn -pl guitar -am spring-boot:run
```

访问地址：

```text
http://127.0.0.1:8088/
http://127.0.0.1:8088/api/health
```

## 模块边界

- 正式代码放在 `com.example.guitar` 下，不把业务代码放入 `demos`。
- 新增跨模块公共能力时优先复用或扩展 `common`。
- 未明确需要前，不引入数据库、MyBatis、OSS、Nacos 或认证。
- 新增数据库能力时遵循根目录 DAO + XML Mapper 约定，不使用 JPA、JdbcTemplate 或 Java 内联 SQL。
- 新增接口响应至少包含 `success` 字段，并覆盖成功路径和主要失败路径。
- 不提交密钥、`target/`、IDE 缓存或运行日志。

## 验证要求

- 修改 Java 代码后运行 `mvn -pl guitar -am test`。
- 修改首页后启动服务并验证 `/` 与 `/api/health`。
- 修改端口、名称或健康地址时，同步更新根 `AGENTS.md` 和 Website 主页入口。
