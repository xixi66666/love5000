# love5000 / love530

`love5000` 是一个 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目，父工程 artifactId 为 `love530`。仓库同时托管三个独立 Python 微应用，用于 A 股研究、量化研究和 AI 动漫短片生成。

## 模块

Maven 聚合模块：

- `common`：公共 OSS 工具、自动配置和通用 Session 认证能力。
- `lovestory`：恋爱相册、照片上传、留言板和吉他视频卡片 Web 应用。
- `website`：个人主页/展示站点、博客、提示词控制台，以及 Python 子服务入口和自动启动。
- `imagetemplate`：图片提示词模板库和 OpenAI Images API 生成服务。

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
```

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
