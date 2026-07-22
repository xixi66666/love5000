# love5000 / love530

`love5000` 是一个 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目，父工程 artifactId 为 `love530`。仓库同时托管三个独立 Python 微应用，用于 A 股研究、量化研究和 AI 动漫短片生成。

## 模块

Maven 聚合模块：

- `common`：公共 OSS 工具、自动配置和通用 Session 认证能力。
- `lovestory`：恋爱相册、照片上传、留言板和吉他视频卡片 Web 应用。
- `website`：个人主页/展示站点、博客、提示词控制台，以及 Python 子服务入口和自动启动。
- `imagetemplate`：图片提示词模板库和 OpenAI Images API 生成服务。
- `guitar`：Guitar 曲谱平台，提供手机号注册登录、Session/CSRF 鉴权、公开曲谱检索和详情查询，默认端口 `8088`。

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
```

Guitar 认证流程先调用 `GET http://127.0.0.1:8088/api/auth/session` 获取 Session 和 `csrfToken`，再把令牌放入所有写请求的 `X-CSRF-Token` 请求头。注册、登录和注销接口分别为 `POST /api/auth/register`、`POST /api/auth/login`、`POST /api/auth/logout`。注册和登录的数据库事务提交成功后才会轮换认证 Session。

Guitar 已提供 `PUT /api/users/me` 更新昵称和 `POST /api/users/me/avatar` 上传头像。两个接口只使用认证 Session 中的用户身份；头像字段名为 `avatar`，限制为不超过 5MB 的 JPG/JPEG、PNG 或 WebP，并校验文件魔数。头像 OSS 存储通过 `LOVE530_OSS_ENABLED=true` 及现有 `LOVE530_OSS_*` 环境变量启用，数据库仅保存对象键；旧对象删除失败会落入 `guitar_oss_cleanup_task` 等待后续清理。

Guitar 的 `GET /api/sheets` 和 `GET /api/sheets/{id}` 可匿名访问。列表仅返回已发布且未删除的曲谱，支持 `keyword`、`songName`、`singer`、`sheetType`、`difficulty`、`keySignature`、`capoPosition`、`tuning` 和 `sort`（`LATEST`、`MOST_FAVORITED`、`MOST_VIEWED`）；分页默认 `page=1`、`size=20`，`size` 最大为 50。详情按文件排序返回可公开访问的文件 URL，并在亚洲/上海日期桶中记录浏览量。静态首页仍为 `http://127.0.0.1:8088/`，健康检查为 `GET /api/health`。

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
