# Guitar 吉他谱平台设计

## 1. 背景

`guitar` 当前是 `love530` 父工程中的 Java 8 + Spring Boot 2.6.13 Web 模块，默认端口为 `8088`，只提供基础首页和 `GET /api/health`。

本次目标是把该模块建设为可独立使用的吉他谱网站，提供手机号注册登录、曲谱检索与在线预览、曲谱收藏、用户上传和个人管理能力。曲谱文件与头像存放在阿里云 OSS，MySQL 只保存业务数据、OSS 对象路径和文件元数据。

项目分两期交付。第一期形成完整用户端闭环和最小管理员治理能力；第二期完成用户封禁、完整后台和统计分析。两期范围都纳入本设计和后续实施计划。

## 2. 已确认的产品决策

- 注册方式为手机号 + 密码，不接入短信验证码。
- 游客可以搜索和查看公开曲谱；登录后才能收藏、上传和管理曲谱。
- 用户资料包含手机号、BCrypt 密码哈希、昵称和头像。
- 曲谱支持 PDF、JPG、JPEG、PNG、WebP。
- 一份曲谱只能是单个 PDF，或 1 至 20 张有序图片，不能混用。
- 用户上传后立即公开，不经过管理员审核。
- 用户可以修改曲谱信息、替换谱文件、删除自己上传的曲谱。
- 同一首歌允许存在多个独立曲谱版本。
- 上传来源字段可选，页面显示平台免责声明。
- 查询支持歌名、歌手、关键词、曲谱类型、难度、调式、变调夹位置和调弦方式。
- 收藏功能支持多个私人收藏夹，第一期不支持收藏夹公开分享。
- 第一阶段 OSS 使用公共读；数据库只保存对象路径，后续可以切换私有签名 URL。
- 管理员账号由普通账号注册后通过 SQL 或数据库运维赋予 `ADMIN` 角色，不内置默认管理员密码。

## 3. 范围

### 3.1 第一期

- 手机号注册、登录、退出和当前会话查询。
- 用户昵称和头像管理。
- 公开曲谱分页查询、专业筛选、排序和详情预览。
- PDF 或多图片曲谱上传。
- 上传者修改元数据、替换文件和删除自己的曲谱。
- 多收藏夹的新建、重命名、删除、排序和曲谱收藏管理。
- 管理员查询全部曲谱、下架和恢复曲谱。
- 管理操作原因和审计记录。
- OSS 删除失败后的持久化清理重试。
- 完整用户端页面和最小管理员页面。

### 3.2 第二期

- 管理员查询用户、封禁和解封用户。
- 被封禁用户禁止登录和执行写操作。
- 完整管理后台，包括用户、曲谱、收藏和上传数据查询。
- 新增用户、上传量、浏览量、收藏量的每日聚合统计。
- 数据概览、趋势图和完整审计日志页面。
- 聚合任务幂等、失败重算和回归测试。

### 3.3 非目标

- 短信验证码登录或注册。
- 第三方 OAuth 登录。
- 曲谱在线编辑器、自动转谱或音频识别。
- 收藏夹公开分享和社交关注。
- 上传前人工审核。
- Elasticsearch 等独立搜索基础设施。
- 第一阶段 OSS 私有读和签名 URL。

## 4. 总体架构

`guitar` 使用单体分层架构，保持现有 Maven 多模块边界：

```text
Browser
  -> Controller / DTO validation
  -> Service / transaction / authorization
  -> DAO interface
  -> MyBatis XML Mapper
  -> MySQL

Service
  -> common OssUtil
  -> Aliyun OSS
```

各层职责如下：

- Controller：处理 HTTP 参数、Multipart 请求、会话读取和响应组装，不写复杂业务逻辑。
- Service：处理认证、授权、曲谱状态、收藏事务、OSS 补偿和管理员操作。
- DAO + XML Mapper：只负责数据库访问，SQL 使用参数绑定，不使用 JPA、JdbcTemplate 或 Java 内联 SQL。
- Entity：映射数据库记录。
- DTO：承载请求参数。
- VO：返回前端所需字段，不直接暴露 Entity。
- 前端：原生 HTML、CSS、JavaScript，多页面共享 API、会话和 UI 工具模块。

`guitar` 依赖 `common`，复用以下能力：

- `AuthPasswordService` 的 BCrypt 哈希能力。
- `OssUtil`、`OssUploadResult` 和 OSS 自动配置。

手机号认证、用户表、会话和权限规则由 `guitar` 自己实现，不修改 Website 现有用户名认证语义。

## 5. 认证与授权

### 5.1 账号规则

- 手机号必须符合中国大陆 11 位手机号格式 `^1[3-9]\d{9}$`。
- 手机号在数据库中唯一。
- 密码长度为 8 至 72 个字符，至少包含一个英文字母和一个数字，不允许空白字符。
- 密码只保存 BCrypt 哈希。
- 昵称必填，去除首尾空格后长度为 1 至 30 个字符。
- 头像可选，未上传时使用前端默认头像样式。

### 5.2 会话

- 使用服务端 HttpSession 和 HttpOnly Cookie。
- 登录成功后销毁旧 Session 并创建新 Session，防止 Session Fixation。
- Cookie 使用 `HttpOnly`、`SameSite=Lax`；生产 HTTPS 环境启用 `Secure`。
- `GET /api/auth/session` 返回当前用户和 CSRF Token。
- 所有写接口必须通过 `X-CSRF-Token` 请求头提交 Token。

### 5.3 权限

```text
游客：查询、查看 PUBLISHED 曲谱
USER：游客权限 + 收藏 + 上传 + 管理本人曲谱 + 修改个人资料
ADMIN：USER 权限 + 查询全部曲谱 + 下架/恢复；第二期增加用户和统计管理
```

任何修改、替换和删除操作都同时检查登录状态与资源所有权。管理员下架不改变曲谱所有权。

## 6. 数据模型

数据库使用独立的 `guitar` schema，字符集为 `utf8mb4`。

DDL 兼容 MySQL 5.7+，统一使用 InnoDB。用户、曲谱、文件、收藏夹和收藏关系之间使用明确外键；审计日志保留业务目标 ID 快照，不因业务记录软删除而丢失。第二期字段和表在一次性 DDL 中预建，第一期代码不开放对应功能。

### 6.1 guitar_user

主要字段：

- `id`：主键。
- `phone`：手机号，唯一。
- `password_hash`：BCrypt 哈希。
- `nickname`：昵称。
- `avatar_object_key`：OSS 对象路径。
- `role`：`USER`、`ADMIN`。
- `status`：`ENABLED`、`BANNED`。
- `ban_reason`、`banned_by`、`banned_at`、`ban_expires_at`：第二期封禁信息。
- `last_login_at`、`create_time`、`update_time`。

索引：

- 唯一索引 `uk_guitar_user_phone(phone)`。
- 普通索引 `idx_guitar_user_status_role(status, role)`。

### 6.2 guitar_sheet

主要字段：

- `id`：主键。
- `uploader_id`：上传用户。
- `song_name`：歌名。
- `singer`：歌手。
- `arranger`：编配者或来源，可空。
- `description`：说明和免责声明补充文本。
- `keywords`：搜索关键词。
- `sheet_type`：`CHORD`、`TAB`、`FINGERSTYLE`、`BASS`、`OTHER`。
- `difficulty`：`BEGINNER`、`EASY`、`INTERMEDIATE`、`ADVANCED`。
- `key_signature`：调式。
- `capo_position`：0 至 12，可空。
- `tuning`：`STANDARD`、`DROP_D`、`DADGAD` 或自定义文本。
- `file_mode`：`PDF`、`IMAGES`。
- `storage_uuid`：OSS 目录 UUID，唯一。
- `status`：`PUBLISHED`、`OFFLINE`、`DELETED`。
- `offline_reason`、`offline_by`、`offline_at`。
- `view_count`、`favorite_count`。
- `create_time`、`update_time`、`deleted_at`。

索引：

- 唯一索引 `uk_guitar_sheet_storage_uuid(storage_uuid)`。
- 普通索引覆盖公开列表、上传者列表、状态、类型、难度、调式和时间排序。
- 关键词搜索第一期使用 MyBatis 参数化 `LIKE`，不引入独立搜索引擎。

### 6.3 guitar_sheet_file

主要字段：

- `id`、`sheet_id`。
- `object_key`：OSS 对象路径，不保存带域名 URL。
- `original_filename`：原始文件名，只用于展示。
- `mime_type`、`file_extension`、`file_size`。
- `sort_order`：PDF 固定为 1，多图从 1 开始连续排序。
- `create_time`。

约束：

- 唯一索引 `uk_guitar_sheet_file_order(sheet_id, sort_order)`。
- PDF 模式只能有一条记录；图片模式允许 1 至 20 条，由 Service 校验。

### 6.4 guitar_favorite_folder

主要字段：`id`、`user_id`、`name`、`sort_order`、`create_time`、`update_time`。

约束：唯一索引 `uk_guitar_favorite_folder_name(user_id, name)`。

### 6.5 guitar_favorite

主要字段：`id`、`user_id`、`folder_id`、`sheet_id`、`create_time`。

约束：唯一索引 `uk_guitar_favorite(folder_id, sheet_id)`。同一曲谱可以加入同一用户的多个收藏夹，但不能在同一收藏夹重复添加。

### 6.6 guitar_admin_action_log

记录管理员、操作类型、目标类型、目标 ID、操作原因、操作前后状态、IP 和时间。第一期记录曲谱下架与恢复，第二期扩展用户封禁、解封和其他后台操作。

### 6.7 guitar_oss_cleanup_task

记录待删除的 OSS `object_key`、业务类型、重试次数、下次重试时间、最后错误和任务状态。用于处理替换、删除或数据库补偿过程中的 OSS 临时失败。

### 6.8 guitar_daily_stat

第二期使用，按日期保存新增用户数、上传数、浏览数、收藏数、下架数。日期唯一，聚合任务重复执行时覆盖当天结果，保证幂等。

## 7. OSS 设计

对象目录：

```text
love530/guitar/avatars/{userId}/{uuid}.{ext}
love530/guitar/sheets/{storageUuid}/pdf/{uuid}.pdf
love530/guitar/sheets/{storageUuid}/images/{pageNumber}-{uuid}.{ext}
```

用户提供的文件名不能参与 OSS 路径拼接。后端生成 UUID 文件名，只保留经过清理的原始文件名作为数据库展示信息。

第一期使用公共读 Bucket。前端 URL 由 `SheetFileUrlService` 根据 `object_key` 和 OSS 配置动态生成。Controller 和数据库不依赖公共 URL 格式，后续切换私有读时只替换 URL 服务实现。

## 8. 上传与一致性

### 8.1 文件限制

```text
PDF：单文件，最大 30MB
图片：1-20 张，单张最大 10MB
头像：单文件，最大 5MB
```

允许扩展名：`pdf`、`jpg`、`jpeg`、`png`、`webp`。除扩展名和 Content-Type 外，后端必须检查文件魔数：PDF 检查 `%PDF`，图片检查 JPEG、PNG、RIFF/WEBP 文件头。禁止 SVG、HTML 和其他可执行内容。

### 8.2 新增曲谱

1. 校验用户、元数据、文件模式、数量、大小和文件头。
2. 生成 `storage_uuid` 和服务端文件名。
3. 把全部文件上传至 OSS。
4. 在一个 MySQL 事务中插入 `guitar_sheet` 和 `guitar_sheet_file`。
5. 数据库失败时补偿删除本次上传对象；删除失败则写入 `guitar_oss_cleanup_task`。

### 8.3 替换曲谱文件

1. 校验所有权和新文件。
2. 先上传全部新文件。
3. 数据库事务切换文件记录和 `file_mode`。
4. 事务提交后删除旧 OSS 对象。
5. 数据库失败则删除新对象；任何 OSS 删除失败都进入清理任务。

### 8.4 删除曲谱

- 数据库将状态改为 `DELETED` 并记录删除时间。
- 删除收藏关系并在事务中修正计数。
- 事务提交后清理 OSS 对象。
- OSS 清理失败不回滚数据库软删除，改由清理任务重试。

## 9. 查询与收藏

公开查询只返回 `PUBLISHED` 曲谱，支持：

- `keyword`：匹配歌名、歌手、编配者和关键词。
- `songName`、`singer`。
- `sheetType`、`difficulty`、`keySignature`。
- `capoPosition`、`tuning`。
- `sort`：`LATEST`、`MOST_FAVORITED`、`MOST_VIEWED`。
- `page`、`size`：默认 20，最大 50。

管理员查询可以包含全部状态。收藏新增和删除与 `favorite_count` 更新处于同一数据库事务，唯一索引负责最终防重。

详情访问增加浏览计数。浏览量仅用于产品排序和第二期聚合，不作为安全或计费依据。

## 10. API

### 10.1 认证与用户

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/session
PUT  /api/users/me
POST /api/users/me/avatar
GET  /api/users/me/sheets
```

### 10.2 曲谱

```text
GET    /api/sheets
GET    /api/sheets/{id}
POST   /api/sheets
PUT    /api/sheets/{id}
PUT    /api/sheets/{id}/files
DELETE /api/sheets/{id}
```

`POST /api/sheets` 和文件替换接口使用 `multipart/form-data`。元数据使用独立 JSON Part，文件统一使用 `files` Part。

### 10.3 收藏夹

```text
GET    /api/favorite-folders
POST   /api/favorite-folders
PUT    /api/favorite-folders/{id}
DELETE /api/favorite-folders/{id}
POST   /api/favorite-folders/{id}/sheets/{sheetId}
DELETE /api/favorite-folders/{id}/sheets/{sheetId}
GET    /api/favorite-folders/{id}/sheets
```

### 10.4 第一期管理员

```text
GET  /api/admin/sheets
POST /api/admin/sheets/{id}/offline
POST /api/admin/sheets/{id}/restore
```

### 10.5 第二期管理员

```text
GET  /api/admin/users
POST /api/admin/users/{id}/ban
POST /api/admin/users/{id}/unban
GET  /api/admin/statistics/overview
GET  /api/admin/statistics/trends
GET  /api/admin/audit-logs
```

## 11. 响应与错误处理

成功响应：

```json
{
  "success": true,
  "data": {}
}
```

失败响应：

```json
{
  "success": false,
  "code": "SHEET_NOT_FOUND",
  "message": "曲谱不存在或已下架"
}
```

稳定错误码至少覆盖：

- `VALIDATION_ERROR`
- `PHONE_INVALID`
- `PHONE_EXISTS`
- `PASSWORD_INVALID`
- `AUTH_REQUIRED`
- `AUTH_FAILED`
- `CSRF_INVALID`
- `FORBIDDEN`
- `USER_BANNED`
- `SHEET_NOT_FOUND`
- `SHEET_FILE_INVALID`
- `UPLOAD_LIMIT_EXCEEDED`
- `OSS_UNAVAILABLE`
- `DATABASE_ERROR`

使用 `@RestControllerAdvice` 统一映射异常，不向客户端返回堆栈、SQL、数据库地址、OSS Endpoint 或密钥。

## 12. 前端设计

前端使用原生 HTML、CSS、JavaScript，拆分为：

```text
index.html       搜索、专业筛选、排序和列表
sheet.html       详情与在线预览
auth.html        登录与注册
upload.html      上传与编辑
favorites.html   收藏夹
profile.html     个人资料与我的上传
admin.html       管理后台
```

首页直接提供曲谱搜索和结果，不制作营销落地页。桌面端为顶部搜索、左侧筛选和右侧结果；移动端使用筛选抽屉。

详情页以实际曲谱内容为主体。PDF 使用浏览器内嵌预览并提供下载；多图按页序连续展示并懒加载。收藏按钮打开收藏夹菜单，上传者看到编辑、替换和删除，管理员看到下架或恢复。

上传页使用 PDF/多图分段控件。多图支持拖放、缩略图、页序调整和逐文件状态。提交期间锁定重复操作。

收藏页使用收藏夹列表和曲谱结果区域。删除非空收藏夹前二次确认，只删除收藏关系。

第一期管理员页提供曲谱搜索、状态筛选、下架、恢复和原因输入。第二期增加用户管理、统计概览、趋势图和审计日志。

实现阶段使用 `ui-ux-pro-max` 细化设计系统和响应式交互，并使用 `playwright-cli` 验证桌面、移动、空状态、错误状态和文本溢出。视觉采用中性工作台风格，以白色和深灰为主体，红色表示危险操作，绿色表示正常状态，琥珀色表示下架状态，组件圆角不超过 8px。

## 13. 配置

数据库和 OSS 配置全部通过环境变量或已有公共配置注入，不提交真实值。建议配置项：

```text
GUITAR_DB_URL
GUITAR_DB_USERNAME
GUITAR_DB_PASSWORD
LOVE530_OSS_ENDPOINT
LOVE530_OSS_BUCKET
LOVE530_OSS_ACCESS_KEY_ID
LOVE530_OSS_ACCESS_KEY_SECRET
GUITAR_OSS_PUBLIC_BASE_URL
```

Spring Multipart 同时设置框架上限，业务 Service 再按文件类型执行更严格限制。

## 14. SQL 交付

实施阶段生成：

```text
guitar/src/main/resources/db/guitar-schema.sql
```

DDL 兼容 MySQL 5.7+，使用 `utf8mb4` 和 InnoDB，包含两期全部表、字段注释、明确外键、唯一索引和查询索引。脚本不包含真实账号、密码或密钥。

管理员赋权只提供参数化示例，执行者自行替换手机号：

```sql
UPDATE guitar_user
SET role = 'ADMIN', update_time = CURRENT_TIMESTAMP
WHERE phone = '<registered-phone>';
```

## 15. 测试策略

### 15.1 第一期

- 手机号格式、重复注册、密码规则、登录失败、Session 更新和退出。
- 游客、普通用户、所有者和管理员权限矩阵。
- PDF、多图片、WebP、文件伪装、超限和混合上传。
- OSS 上传失败、数据库失败补偿、替换文件和清理任务重试。
- 曲谱查询、筛选、分页、排序和下架隐藏。
- 多收藏夹、重复收藏、收藏计数和收藏夹删除。
- Controller 使用 MockMvc。
- Service mock DAO 和 OSS，不依赖真实 MySQL、OSS 或外部网络。
- 前端关键表单和 API 错误处理测试。
- Playwright 桌面和移动端页面验收。

### 15.2 第二期

- 用户封禁、解封和写操作拦截。
- 管理员角色、越权防护和审计日志。
- 每日聚合幂等、失败重算和日期边界。
- 后台查询、分页、筛选和趋势数据。

至少执行：

```bash
mvn -pl guitar -am test
```

## 16. 文档同步

实现中涉及模块职责、数据库、API、启动配置、测试方式和部署入口，必须同步更新：

- 根 `AGENTS.md`。
- 根 `README.md`。
- `guitar/AGENTS.md`。
- `guitar/README.md`。
- Website 首页入口说明；端口和健康接口保持 `8088`、`/api/health`。

## 17. 分期实施顺序

### 第一期

1. Maven 依赖、配置、DDL 和测试基础设施。
2. 手机号认证、Session、CSRF 和个人资料。
3. 曲谱模型、查询、详情和权限。
4. OSS 上传、替换、删除和补偿清理。
5. 收藏夹与收藏计数。
6. 管理员下架、恢复和审计。
7. 完整用户端 UI、最小管理员 UI 和响应式验收。
8. 文档、全量测试和运行验证。

### 第二期

1. 用户管理、封禁和解封。
2. 完整后台查询和权限回归。
3. 每日统计聚合与重算。
4. 数据概览和趋势页面。
5. 审计完善、全量回归和文档更新。

## 18. 验收标准

第一期完成时：

- 游客可以查询和预览公开曲谱。
- 用户可以用手机号和密码注册登录、维护昵称头像。
- 登录用户可以上传 PDF 或多图曲谱，并管理自己的曲谱。
- 登录用户可以创建多个收藏夹并管理收藏。
- 管理员可以下架和恢复曲谱，普通用户不能调用管理员接口。
- MySQL 只保存 OSS 对象路径，上传替换删除具备失败补偿。
- 目标测试通过，不依赖真实外部服务。
- 桌面和移动端页面可用且无明显溢出、遮挡或不可达操作。

第二期完成时：

- 管理员可以查询、封禁和解封用户。
- 被封禁用户不能登录或执行写操作。
- 管理后台可以查看核心统计和趋势。
- 统计任务可重复执行且结果一致。
- 管理操作具备完整审计记录。
