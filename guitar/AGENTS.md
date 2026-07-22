# AGENTS.md

## 模块概述

`guitar` 是 `love530` 的 Java 8 + Spring Boot 2.6.13 Web 子模块，默认端口为 `8088`。当前提供基础静态首页、健康检查、手机号注册登录、Session/CSRF 鉴权，以及 Guitar 曲谱平台的公开检索、安全上传、个人曲谱管理、私人多收藏夹、管理员曲谱下架/恢复和 MySQL 数据基础。

## 开发命令

从仓库根目录运行：

```bash
mvn -pl guitar -am test
mvn -pl guitar -am '-Dtest=FavoriteServiceTest,FavoriteControllerTest' -DfailIfNoTests=false test
mvn -pl guitar -am '-Dtest=SheetAdminServiceTest,SheetAdminControllerTest' -DfailIfNoTests=false test
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
- 收藏功能放在 `com.example.guitar.favorite`，按 Controller、Service、DAO + XML Mapper 分层；所有收藏夹查询必须同时携带 Session 用户 ID 作为 SQL 条件，响应不得暴露收藏夹 `userId`、曲谱对象键或其他用户数据。
- 管理员曲谱功能放在 `com.example.guitar.admin`，按 Controller、Service、DAO + XML Mapper 分层；管理员 ID 和角色只从认证 Session 获取，状态更新和审计日志必须在同一事务。
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

- `PUT /api/sheets/{id}` accepts JSON metadata and only updates the authenticated uploader's non-deleted sheet. `fileMode` is optional and unchanged; current file URLs are resolved before the database transaction commits. `OFFLINE` remains `OFFLINE`; an ADMIN role does not bypass ownership.
- `PUT /api/sheets/{id}/files` accepts a multipart `mode` parameter plus repeated `files` and does not update metadata. It generates a new storage UUID for every replacement; `storage_uuid`, `file_mode`, file rows, and PENDING cleanup tasks for the locked old-file snapshot commit in one transaction. A stale version returns HTTP 409 with `SHEET_VERSION_CONFLICT` and compensates only that request's new objects.
- `DELETE /api/sheets/{id}` locks and reads the current files, inserts their PENDING cleanup tasks, soft-deletes the sheet, removes favorites, and sets the favorite count to zero in one transaction. Concurrent or repeated deletion returns `SHEET_NOT_FOUND`.
- Post-commit immediate deletion must claim the already-persisted task; it never creates the first durable record. `OssCleanupRetryService` starts after 60 seconds and runs every 5 minutes. Claims increment `claim_version` and set `processing_started_at`; success, reschedule, and failure updates fence on task ID, PROCESSING status, and claim version. Processing older than 15 minutes is recovered, stale workers affect zero rows, and retry delays are 5, 30, 120, and 720 minutes before the fifth failure becomes `FAILED`.

列表参数为 `keyword`、`songName`、`singer`、`sheetType`、`difficulty`、`keySignature`、`capoPosition`、`tuning`、`sort`、`page`、`size`。`keyword` 覆盖歌名、歌手、编配者和关键词；`sheetType`、`difficulty`、`sort` 必须是稳定模型枚举，`sort` 仅允许 `LATEST`、`MOST_FAVORITED`、`MOST_VIEWED`。分页默认为 `page=1`、`size=20`，大小范围为 1-50，变调夹范围为 0-12。文件 URL 只从对象键生成，公开基础 URL 和 OSS 都不可用时返回稳定的 `OSS_UNAVAILABLE`，禁止泄露本地文件路径。静态首页仍为 `/`，健康检查仍为 `/api/health`。

## 多收藏夹接口

```text
GET    /api/favorite-folders
POST   /api/favorite-folders
PUT    /api/favorite-folders/{id}
DELETE /api/favorite-folders/{id}
POST   /api/favorite-folders/{id}/sheets/{sheetId}
DELETE /api/favorite-folders/{id}/sheets/{sheetId}
GET    /api/favorite-folders/{id}/sheets
```

新建/更新请求体为 `{ "name": "练习", "sortOrder": 0 }`。名称 trim 后必须为 1-50 个字符；同用户名称唯一，冲突返回 `FOLDER_NAME_EXISTS`。他人和不存在的收藏夹统一返回 `FOLDER_NOT_FOUND`；仅公开未删除曲谱可新增收藏，重复收藏返回 `FAVORITE_EXISTS`。新增和实际删除收藏关系必须与计数变化处于同一事务，递减 SQL 必须保证计数不小于 0。移除不存在的收藏关系幂等成功；删除非空收藏夹只删除关系并按集合批量修正计数，不删除曲谱。

## 管理员曲谱接口

```text
GET  /api/admin/sheets
POST /api/admin/sheets/{id}/offline
POST /api/admin/sheets/{id}/restore
```

`GET /api/admin/sheets` 支持 `keyword`、`status`、`sort`、`page`、`size`，可查询 `DRAFT`、`PUBLISHED`、`OFFLINE`、`DELETED`；`sort` 仅允许 `LATEST`、`MOST_FAVORITED`、`MOST_VIEWED`，分页默认 1/20、`size` 最大 50、偏移量最大 5,000,000。下架请求体为 `{ "reason": "..." }`，理由 trim 后必须为 1-500 个字符。状态机仅允许 `PUBLISHED -> OFFLINE` 与 `OFFLINE -> PUBLISHED`，重复或非法转换返回 HTTP 409，`DELETED` 不可恢复。

所有 `/api/admin/**` 只允许认证 Session 中角色为 `ADMIN` 的用户访问，普通 `USER` 返回 HTTP 403；写接口继续要求 CSRF Token。Controller 不接收客户端 `adminUserId` 或 `role`，审计 IP 只使用容器提供的 `request.getRemoteAddr()`，不信任任意转发头。下架填写离线原因、管理员和时间，恢复清空离线信息；状态更新和 `guitar_admin_action_log` 插入同一事务提交，日志至少记录管理员、动作、目标、理由、前后状态、IP 和时间。管理员操作不删除 OSS 文件、不修改收藏关系。

## Frontend foundation

The static application lives in `src/main/resources/static/index.html` with shared styles in `css/app.css`. Authentication is provided by `auth.html` and the ES modules `js/api.js`, `js/session.js`, and `js/auth.js`. API requests use same-origin credentials, in-memory/session-storage CSRF, and redirect JSON 401 responses to `auth.html`.

Run frontend checks from `guitar/` with `npm.cmd run test:api` and `npm.cmd run test:auth`. The Java static-resource checks are included in `mvn -pl guitar -am -Dtest=GuitarApplicationTests -DfailIfNoTests=false test`.
