# love5000 / love530

`love5000` 是一个 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目，父工程 artifactId 为 `love530`。仓库同时托管三个独立 Python 微应用，用于 A 股研究、量化研究和 AI 动漫短片生成。

## 模块

Maven 聚合模块：

- `common`：公共 OSS 工具、自动配置和通用 Session 认证能力。
- `lovestory`：恋爱相册、照片上传、留言板和吉他视频卡片 Web 应用。
- `website`：个人主页/展示站点、博客、提示词控制台，以及 Python 子服务入口和自动启动。
- `imagetemplate`：图片提示词模板库和 OpenAI Images API 生成服务。
- `guitar`：Guitar 曲谱平台，提供手机号注册登录、Session/CSRF 鉴权、公开曲谱检索、安全上传、个人曲谱管理、多收藏夹和管理员曲谱下架/恢复，默认端口 `8088`。

独立 Python 微应用：

- `website/python-a`：A 股自选股 AI 研究台，默认端口 `5174`。
- `website/quant-a`：A 股多因子量化研究台，默认端口 `5175`。
- `website/video`：AI 原创动漫短片生成工作台，默认端口 `5176`。

根目录下的 `python-a/`、`quant-a/` 不是当前主要接入路径；当前运行和文档维护以 `website/` 下的三个子服务为准。

## 快速开始

从仓库根目录执行：

```bash
cd C:/Code/Java_Code/love5000
mvn test
```

启动 `website`：

```bash
mvn -pl website -am spring-boot:run
```

`website` 默认端口为 `8080`，启动时会检查并自动拉起 `website/python-a`、`website/quant-a` 和 `website/video`。如果对应健康检查已经可用，会复用已有服务。

其他服务：

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
mvn -pl imagetemplate -am spring-boot:run
mvn -f guitar/pom.xml spring-boot:run
```

Python 子服务可单独启动：

```bash
cd website/python-a && python server.py
cd website/quant-a && python -m uvicorn main:app --host 127.0.0.1 --port 5175
cd website/video && python web_server.py
```

## 端口

- `website`：`8080`
- `lovestory`：`8081`
- `imagetemplate`：`8082`
- `guitar`：`8088`
- `python-a`：`5174`
- `quant-a`：`5175`
- `video`：`5176`

## 测试

Java 模块：

```bash
mvn test
mvn -pl common test
mvn -pl lovestory -am test
mvn -pl website -am test
mvn -pl imagetemplate -am test
mvn -pl guitar -am test
mvn -pl guitar -am '-Dtest=FavoriteServiceTest,FavoriteControllerTest' -DfailIfNoTests=false test
mvn -pl guitar -am '-Dtest=SheetAdminServiceTest,SheetAdminControllerTest' -DfailIfNoTests=false test
```

Guitar 认证流程先调用 `GET http://127.0.0.1:8088/api/auth/session` 获取 Session 和 `csrfToken`，再把令牌放入所有写请求的 `X-CSRF-Token` 请求头。注册、登录和注销接口分别为 `POST /api/auth/register`、`POST /api/auth/login`、`POST /api/auth/logout`。注册和登录的数据库事务提交成功后才会轮换认证 Session。

Guitar 已提供 `PUT /api/users/me` 更新昵称和 `POST /api/users/me/avatar` 上传头像。两个接口只使用认证 Session 中的用户身份；头像字段名为 `avatar`，限制为不超过 5MB 的 JPG/JPEG、PNG 或 WebP，并校验文件魔数。头像 OSS 存储通过 `LOVE530_OSS_ENABLED=true` 及现有 `LOVE530_OSS_*` 环境变量启用，数据库仅保存对象键；旧对象删除失败会落入 `guitar_oss_cleanup_task` 等待后续清理。

Guitar 的 `GET /api/sheets` 和 `GET /api/sheets/{id}` 可匿名访问。列表仅返回已发布且未删除的曲谱，支持 `keyword`、`songName`、`singer`、`sheetType`、`difficulty`、`keySignature`、`capoPosition`、`tuning` 和 `sort`（`LATEST`、`MOST_FAVORITED`、`MOST_VIEWED`）；分页默认 `page=1`、`size=20`，`size` 最大为 50。详情按文件排序返回可公开访问的文件 URL，并在亚洲/上海日期桶中记录浏览量。静态首页仍为 `http://127.0.0.1:8088/`，健康检查为 `GET /api/health`。

`POST /api/sheets` 使用 multipart 的 `metadata` JSON Part 和重复 `files` Part 创建并立即发布曲谱，必须使用登录 Session 和 `X-CSRF-Token`。`fileMode=PDF` 仅接受一个不超过 30MB、扩展名和 `%PDF` 文件头一致的 PDF；`fileMode=IMAGES` 接受 1-20 个不超过 10MB、扩展名和 JPEG/PNG/WebP 魔数一致的图片。服务端忽略客户端 MIME，预先生成服务器 UUID 对象键并使用校验后的类型上传到 `love530/guitar/sheets/{uuid}/pdf` 或 `/images`；公开 URL 在数据库写入前完成验证。OSS、URL 或数据库失败时会补偿所有已知对象，且清理失败会保留在原始异常中。

曲谱所有者可通过 `PUT /api/sheets/{id}` 更新元数据，通过 multipart `PUT /api/sheets/{id}/files` 替换文件，或通过 `DELETE /api/sheets/{id}` 软删除曲谱。元数据更新不要求 `fileMode`，也不会修改文件模式；响应中的当前文件 URL 会在数据库提交前解析。文件替换请求只包含表单参数 `mode` 和重复 `files`；每次替换使用全新的存储 UUID 目录，并在文件行切换的同一事务内更新 `storage_uuid`。并发版本冲突返回 HTTP 409 和 `SHEET_VERSION_CONFLICT`，并发或重复删除稳定返回 `SHEET_NOT_FOUND`。替换和删除会在行锁内确定旧文件，并与业务变更在同一事务写入 PENDING `guitar_oss_cleanup_task`；提交后立即删除失败或进程中断时 scheduler 仍可接管。cleanup lease 通过 `claim_version` 和 `processing_started_at` fencing，陈旧 worker 无法覆盖新 worker；服务启动 60 秒后开始、每 5 分钟轮询最多 50 项，采用 5、30、120、720 分钟退避，连续第五次失败标记为 `FAILED`。

Guitar 多收藏夹 API 位于 `/api/favorite-folders`，支持列表、新建、重命名/排序、删除，以及加入、移除和列出收藏曲谱。收藏夹请求体为 `{ "name": "练习", "sortOrder": 0 }`，名称去除首尾空白后必须为 1-50 个字符；所有用户身份只取自 Session。重复名称和同一收藏夹重复收藏分别返回 `FOLDER_NAME_EXISTS`、`FAVORITE_EXISTS`，不可访问的收藏夹统一返回 `FOLDER_NOT_FOUND`。只有 `PUBLISHED` 且未删除的曲谱可加入，移除不存在的收藏关系幂等成功；删除非空收藏夹只删除关系并在同一事务批量修正曲谱收藏计数，不删除曲谱。

Guitar 管理员接口为 `GET /api/admin/sheets`、`POST /api/admin/sheets/{id}/offline` 和 `POST /api/admin/sheets/{id}/restore`。列表支持 `keyword`、`status`、`sort`、`page`、`size`；`status` 使用曲谱状态枚举，`sort` 仅允许 `LATEST`、`MOST_FAVORITED`、`MOST_VIEWED`。下架 JSON 请求体为 `{ "reason": "版权整改" }`，理由 trim 后为 1-500 个字符。仅 Session 中的 `ADMIN` 可访问，普通用户返回 HTTP 403，写请求还需 CSRF Token。状态只允许 `PUBLISHED -> OFFLINE` 和 `OFFLINE -> PUBLISHED`；重复或非法转换返回 HTTP 409，`DELETED` 不可恢复。下架/恢复与包含管理员、理由、前后状态、容器远端 IP 和时间的审计日志在同一事务提交，不修改曲谱文件、OSS 对象或收藏关系。

Python 子服务：

```bash
cd website/python-a && python -m unittest discover -s tests -v
cd website/quant-a && python -m pytest -v
cd website/video && python -m unittest discover -s tests -v
```

## 配置与安全

不要提交真实数据库密码、OSS AccessKey、OpenAI API Key、DeepSeek Key、Tushare Token、腾讯云密钥或 DashScope Key。新增配置优先使用环境变量或本地私有配置文件。

常见私有文件已在 `.gitignore` 中忽略，例如：

- `website/python-a/deepseek.local.json`
- `website/quant-a/data/`
- `website/video/config/config.local.json`
- `website/video/anime_projects/`
- `.env`、`.venv/`、`__pycache__/`、`.pytest_cache/`、`*.log`

## 文档维护规则

每次修改项目结构、模块职责、启动命令、端口、配置项、API、数据目录、测试方式或部署入口时，必须同步更新根 `AGENTS.md` / `README.md`，以及受影响模块或微应用目录下的 `AGENTS.md` / `README.md`。文档和代码不一致时，本次改动不能视为完成。

开发代理细节、模块边界、API 清单和测试要求见根目录 `AGENTS.md`，模块目录下的 `AGENTS.md` / `README.md` 以各自模块为准。

## 代码提交
本地代码提交到远程仓库时，通常会遇到网络问题导致提交失败，不用处理，直接进行重试，直到成功为止。

## Guitar 前端

Guitar 的静态曲谱搜索首页位于 `guitar/src/main/resources/static/index.html`，详情页为 `sheet.html`，认证页为 `auth.html`；共享 API、Session、搜索与详情模块位于 `static/js/`，检索页样式位于 `static/css/discovery.css`。前端 Node 测试从 `guitar/` 执行 `npm.cmd run test:api`、`npm.cmd run test:auth` 和 `npm.cmd run test:search`，Java 静态资源断言使用 Guitar 模块 Maven 测试命令。
