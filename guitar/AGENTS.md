# AGENTS.md

## 模块概述

`guitar` 是 `love530` 的 Java 8 + Spring Boot 2.6.13 Web 子模块，默认端口为 `8088`。当前提供基础静态首页、健康检查、手机号注册登录、Session/CSRF 鉴权，以及 Guitar 曲谱平台的公开检索、安全上传和 MySQL 数据基础。

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
- 认证代码放在 `com.example.guitar.auth`，用户模型和 DAO 放在 `com.example.guitar.user`；密码哈希复用 `common` 的 `AuthPasswordService`。数据库创建和登录时间更新必须经过独立事务服务，事务提交成功后才能轮换 Session。
- 认证 Session 属性名固定为 `GUITAR_AUTH_USER`；所有 POST/PUT/PATCH/DELETE 请求都必须校验 `X-CSRF-Token`。
- `/api/users/**`、`/api/favorite-folders/**` 和非 GET `/api/sheets/**` 要求登录，`/api/admin/**` 要求 ADMIN。
- `GET /api/sheets` 和 `GET /api/sheets/{id}` 保持公开访问，只查询 `PUBLISHED` 且未删除的曲谱；详情访问才累计曲谱和 Asia/Shanghai 当日浏览量。
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

## 用户资料与头像

```text
PUT  /api/users/me
POST /api/users/me/avatar
```

上述接口从认证 Session 获取用户 ID，禁止客户端传入 `userId`。昵称去除首尾空白后必须为 1-30 个字符。头像 multipart 字段为 `avatar`，限制 5MB，且仅接受魔数和扩展名一致的 JPG/JPEG、PNG、WebP。OSS 未启用时返回 `OSS_UNAVAILABLE` 且不写数据库；已替换的旧头像删除失败会写入 `guitar_oss_cleanup_task`，不回滚已成功的资料更新。

## 公开曲谱接口

```text
GET /api/sheets
GET /api/sheets/{id}
POST /api/sheets
PUT  /api/sheets/{id}
PUT  /api/sheets/{id}/files
DELETE /api/sheets/{id}
```

### Public sheet query limits

- `keyword`, `songName`, and `singer` are limited to 120 characters; `keySignature` is limited to 20; `tuning` is limited to 80. Overlong values return `VALIDATION_ERROR` and are never truncated.
- `page` defaults to 1 and `size` defaults to 20 (valid range 1-50). The calculated SQL offset is capped at `5,000,000`; requests above the cap return `PAGE_TOO_LARGE`.

### Safe sheet upload

- `POST /api/sheets` requires the authenticated Session and `X-CSRF-Token`; it accepts a JSON `metadata` part plus repeated `files` parts.
- `fileMode=PDF` accepts exactly one `.pdf` no larger than 30MB with a `%PDF` header. `fileMode=IMAGES` accepts 1-20 JPG/JPEG, PNG, or WebP files no larger than 10MB each, with matching magic bytes.
- Ignore client Content-Type and path segments. Derive the stored MIME type and extension, predeclare server-only object keys under `love530/guitar/sheets/{storageUuid}/pdf` or `/images`, upload outside the database transaction, and persist only those confirmed keys.
- Precompute every public file URL before persistence. If upload, URL generation, or transactional persistence fails, compensate every predeclared object through `OssCleanupService`; cleanup failures are logged and attached to the original failure. Never expose `storageUuid` or object keys in API responses.

### Owner sheet mutations and cleanup retry

- `PUT /api/sheets/{id}` accepts JSON metadata and only updates the authenticated uploader's non-deleted sheet. `OFFLINE` remains `OFFLINE`; an ADMIN role does not bypass ownership.
- `PUT /api/sheets/{id}/files` accepts a multipart `mode` parameter plus repeated `files` and does not update metadata. It generates a new storage UUID for every replacement; `storage_uuid`, `file_mode`, and file rows switch in one transaction. Upload and URL precomputation occur before that transaction, and old OSS objects are deleted or queued only after commit.
- `DELETE /api/sheets/{id}` soft-deletes the sheet, removes favorites, and sets the favorite count to zero in one transaction. A repeated delete returns `SHEET_NOT_FOUND`; post-commit cleanup never restores the row.
- `OssCleanupRetryService` starts after 60 seconds and runs every 5 minutes. It selects at most 50 due PENDING rows, claims each with an expected-state update, recovers PROCESSING rows older than 15 minutes, and uses retry delays of 5, 30, 120, and 720 minutes before marking the fifth failure `FAILED`.

列表参数为 `keyword`、`songName`、`singer`、`sheetType`、`difficulty`、`keySignature`、`capoPosition`、`tuning`、`sort`、`page`、`size`。`keyword` 覆盖歌名、歌手、编配者和关键词；`sheetType`、`difficulty`、`sort` 必须是稳定模型枚举，`sort` 仅允许 `LATEST`、`MOST_FAVORITED`、`MOST_VIEWED`。分页默认为 `page=1`、`size=20`，大小范围为 1-50，变调夹范围为 0-12。文件 URL 只从对象键生成，公开基础 URL 和 OSS 都不可用时返回稳定的 `OSS_UNAVAILABLE`，禁止泄露本地文件路径。静态首页仍为 `/`，健康检查仍为 `/api/health`。
