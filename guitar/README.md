# Guitar 服务

`guitar` 是 `love530` 的独立 Spring Boot Web 模块，使用 Java 8、Spring Boot 2.6.13、MyBatis 和 MySQL，默认监听 `8088`。当前提供基础首页、健康检查，以及手机号注册登录、Session 和 CSRF 鉴权能力。

## 启动与测试

从仓库根目录执行：

```bash
mvn -pl guitar -am test
mvn -f guitar/pom.xml spring-boot:run
```

数据库连接通过 `GUITAR_DB_URL`、`GUITAR_DB_USERNAME`、`GUITAR_DB_PASSWORD` 配置。首次使用前在目标 MySQL 实例执行 `guitar/src/main/resources/db/guitar-schema.sql`，不要把真实数据库密码提交到仓库。

## 接口

```text
GET  /api/health
GET  /api/auth/session
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
```

注册请求体：

```json
{
  "phone": "13800138000",
  "password": "guitar123",
  "nickname": "旋律"
}
```

登录请求体：

```json
{
  "phone": "13800138000",
  "password": "guitar123"
}
```

注册时手机号会先去除首尾空格，再按 `^1[3-9]\d{9}$` 校验；密码长度必须为 8-72 个字符、UTF-8 编码后不超过 72 字节，至少包含一个 ASCII 字母和一个数字且不能包含空白字符；昵称去除首尾空格后必须为 1-30 个字符。重复手机号返回稳定错误码 `PHONE_EXISTS`，手机号或密码错误统一返回 `AUTH_FAILED`，已封禁账号仅在密码正确后返回 `USER_BANNED`。

先调用 `GET /api/auth/session` 创建 Session 并读取响应中的 `data.csrfToken`。所有 POST、PUT、PATCH、DELETE 请求都必须在同一 Session 下携带：

```text
X-CSRF-Token: <data.csrfToken>
```

注册或登录的数据库事务提交成功后才会轮换 Session，因此后续写请求前应重新调用 `GET /api/auth/session` 获取新令牌。事务或登录时间更新失败不会创建认证 Session。接口统一返回 `success/data`，错误返回 `success=false/code/message`。

## 权限边界

- `/api/users/**`、`/api/favorite-folders/**` 和非 GET `/api/sheets/**` 要求登录。
- `/api/admin/**` 要求 `ADMIN` 角色。
- 未登录和权限不足分别返回 JSON 401、403，不进行页面跳转。
