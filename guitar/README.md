# Guitar 服务

`guitar` 是 `love530` 的独立 Spring Boot Web 模块，使用 Java 8、Spring Boot 2.6.13、MyBatis 和 MySQL，默认监听 `8088`。当前提供静态首页、健康检查、手机号注册登录、Session/CSRF 鉴权，以及公开曲谱检索、安全上传、个人曲谱管理、私人多收藏夹和管理员曲谱下架/恢复。

## 启动与测试

从仓库根目录执行：

```bash
mvn -pl guitar -am test
mvn -pl guitar -am '-Dtest=FavoriteServiceTest,FavoriteControllerTest' -DfailIfNoTests=false test
mvn -pl guitar -am '-Dtest=SheetAdminServiceTest,SheetAdminControllerTest' -DfailIfNoTests=false test
mvn -f guitar/pom.xml spring-boot:run
```

数据库连接通过 `GUITAR_DB_URL`、`GUITAR_DB_USERNAME`、`GUITAR_DB_PASSWORD` 配置。首次使用前在目标 MySQL 实例执行 `guitar/src/main/resources/db/guitar-schema.sql`，不要把真实数据库密码提交到仓库。

## 接口

```text
GET  /api/health
GET  /api/sheets
GET  /api/sheets/{id}
POST /api/sheets
PUT  /api/sheets/{id}
PUT  /api/sheets/{id}/files
DELETE /api/sheets/{id}
GET  /api/auth/session
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
PUT  /api/users/me
POST /api/users/me/avatar
GET    /api/favorite-folders
POST   /api/favorite-folders
PUT    /api/favorite-folders/{id}
DELETE /api/favorite-folders/{id}
POST   /api/favorite-folders/{id}/sheets/{sheetId}
DELETE /api/favorite-folders/{id}/sheets/{sheetId}
GET    /api/favorite-folders/{id}/sheets
GET    /api/admin/sheets
POST   /api/admin/sheets/{id}/offline
POST   /api/admin/sheets/{id}/restore
```

`GET /api/sheets` 和 `GET /api/sheets/{id}` 可匿名访问，只返回已发布且未删除的曲谱。列表可使用 `keyword`（歌名、歌手、编配者、关键词）、`songName`、`singer`、`sheetType`、`difficulty`、`keySignature`、`capoPosition`（0-12）、`tuning`、`sort`（`LATEST`、`MOST_FAVORITED`、`MOST_VIEWED`）筛选。分页默认 `page=1`、`size=20`，`size` 为 1-50。详情文件 URL 仅由 OSS 对象键生成，未配置可用 OSS 时返回 `OSS_UNAVAILABLE`，不会返回本地路径；读取详情会同时累计曲谱浏览量和 Asia/Shanghai 当日统计。

`POST /api/sheets` 使用 multipart 的 `metadata` JSON Part 和重复 `files` Part 创建并立即发布曲谱，必须携带当前登录 Session 的 `X-CSRF-Token`。必填元数据包括 `songName`、`singer`、`sheetType`、`difficulty`、`keySignature`、`tuning` 与 `fileMode`；`capoPosition` 只能为 0-12。`fileMode=PDF` 仅允许一个不超过 30MB、扩展名为 `.pdf` 且文件头为 `%PDF` 的文件；`fileMode=IMAGES` 仅允许 1-20 个不超过 10MB、扩展名和 JPEG/PNG/WebP 魔数一致的图片。服务端不信任客户端文件名路径和 Content-Type，使用服务器 UUID 预声明对象键并写入派生 MIME、对象键和排序。OSS 上传和公开 URL 生成均在数据库事务外完成，且 URL 会在持久化前验证；任一阶段失败都会补偿所有已知对象，成功响应只提供文件 URL。

`PUT /api/sheets/{id}` 用 JSON 元数据更新曲谱，`fileMode` 可省略且不会被修改，当前文件 URL 会在数据库提交前解析。`PUT /api/sheets/{id}/files` 用 multipart 表单参数 `mode`（`PDF` 或 `IMAGES`）和重复 `files` Part 替换文件且不修改元数据，`DELETE /api/sheets/{id}` 软删除曲谱并删除其收藏记录。三者只允许上传者本人执行，`OFFLINE` 曲谱保持 `OFFLINE`。每次替换生成新的存储 UUID；事务锁内校验存储版本，冲突返回 HTTP 409 和 `SHEET_VERSION_CONFLICT`。替换或删除会在行锁内读取当前旧文件，并在业务事务内为它们写入 PENDING cleanup outbox；事务失败时业务变更和 outbox 一起回滚，提交后立即清理失败也不会丢失任务。

`guitar_oss_cleanup_task` 在服务启动 60 秒后开始、每 5 分钟轮询一次，单次最多认领 50 条到期任务。每次认领递增 `claim_version` 并记录 `processing_started_at`；成功、重试和失败更新都必须匹配当前 claim 版本，超过 15 分钟的 `PROCESSING` 才会恢复，因此旧 worker 无法覆盖新 worker。失败重试间隔为 5、30、120、720 分钟，第五次失败标记为 `FAILED`。

公开检索的 `keyword`、`songName`、`singer` 最大为 120 个字符，`keySignature` 最大为 20 个字符，`tuning` 最大为 80 个字符。超长参数返回 `VALIDATION_ERROR`，服务不会截断输入。分页偏移量上限为 `5,000,000`，超过时返回 `PAGE_TOO_LARGE`。

`PUT /api/users/me` 请求体为 `{ "nickname": "..." }`；用户 ID 始终来自认证 Session。`POST /api/users/me/avatar` 使用 multipart 字段 `avatar`，只允许不超过 5MB 的 JPG/JPEG、PNG、WebP，并会校验文件魔数。头像对象键存入数据库而非公开 URL，需设置 `LOVE530_OSS_ENABLED=true` 及现有 `LOVE530_OSS_*` 配置后才可上传。旧头像删除失败会持久化到 `guitar_oss_cleanup_task`，不会回滚已成功的头像更新。

收藏夹的新建和更新使用 JSON 请求体 `{ "name": "练习", "sortOrder": 0 }`；`name` 去除首尾空白后必须为 1-50 个字符，`sortOrder` 可选，新建时默认为 0。列表、更新、删除和曲谱操作全部按 Session 用户 ID 查询，接口响应不包含收藏夹 `userId`、曲谱对象键或其他用户数据。他人或不存在的收藏夹统一返回 `FOLDER_NOT_FOUND`；同用户名称重复和同一收藏夹重复收藏分别返回 `FOLDER_NAME_EXISTS`、`FAVORITE_EXISTS`。

只有 `PUBLISHED` 且未删除的曲谱可以加入收藏夹，不符合条件时返回 `SHEET_NOT_FOUND`。新增收藏在同一事务内先写关系再增加 `favorite_count`；移除时先删关系，仅在实际删除一行后递减计数。重复移除幂等成功。删除非空收藏夹会批量取得其曲谱集合、删除该用户的收藏关系并批量递减对应计数，不会删除曲谱；收藏夹曲谱列表也只返回仍公开的曲谱摘要。

`GET /api/admin/sheets` 支持 `keyword`、`status`、`sort`、`page`、`size`，用于按状态分页查询全部曲谱，包括软删除的 `DELETED` 记录；`sort` 仅允许 `LATEST`、`MOST_FAVORITED`、`MOST_VIEWED`。`POST /api/admin/sheets/{id}/offline` 请求体为 `{ "reason": "版权整改" }`，理由 trim 后必须为 1-500 个字符；`POST /api/admin/sheets/{id}/restore` 不需要请求体。状态只允许从 `PUBLISHED` 下架为 `OFFLINE`，或从 `OFFLINE` 恢复为 `PUBLISHED`；重复操作、其他非法转换和恢复 `DELETED` 返回稳定 HTTP 409 错误。

管理员身份和 ID 只读取认证 Session，普通 `USER` 调用任何管理员接口均返回 HTTP 403，两个写接口还必须携带 CSRF Token。服务不采信请求体中的角色/管理员 ID 或任意 `X-Forwarded-For`，审计 IP 使用容器远端地址。下架设置 `offline_reason/offline_by/offline_at`，恢复清空这些字段；曲谱状态和 `guitar_admin_action_log` 在同一事务提交，审计记录管理员、动作、目标、理由、前后状态、IP 和时间。该操作不删除或替换 OSS 文件，也不删除收藏关系。

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
- 静态首页为 `http://127.0.0.1:8088/`，健康检查为 `GET /api/health`。
## Static frontend

`src/main/resources/static/index.html` is the mobile-first sheet search screen. `auth.html` provides login/register tabs. Shared API/session/auth modules are under `static/js/`, with styles in `static/css/app.css`.

Run browser-independent frontend tests from this directory:

```bash
npm.cmd run test:api
npm.cmd run test:auth
```
