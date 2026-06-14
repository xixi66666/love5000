# AGENTS.md

## 项目概述

`website/python-a` 是 `love5000` 当前接入的 A 股自选股 AI 研究台，作为独立 Python 微应用运行，默认端口 `5174`。它不是 Java Maven 模块，不加入父 `pom.xml` 的 `<modules>`。

## 模块边界

- 后端入口是 `server.py`，使用 Python 标准库 `ThreadingHTTPServer`。
- 前端入口是 `index.html`、`app.js`、`styles.css`。
- 业务服务拆分在 `services/`，包括账户、交易、存储、Obsidian、股票匹配和截图解析。
- 测试在 `tests/`，使用 `unittest`。
- 默认写入 `obsidian-vault/A股AI/`，不写入 `website/quant-a/`。
- Java 侧只负责入口链接、健康检查和自动启动，不把 Python 业务逻辑改写进 Controller。

## 命令

```bash
cd website/python-a
python server.py
python -m unittest discover -s tests -v
```

健康检查：

```text
GET http://127.0.0.1:5174/api/health
```

## 配置

- DeepSeek Key 优先使用环境变量 `DEEPSEEK_API_KEY`。
- 本地私有配置只能写入 `deepseek.local.json`，禁止提交。
- 截图解析相关 Key 使用环境变量，不写入源码、README 或测试。

## 文档同步

每次修改页面入口、API、服务拆分、运行配置、环境变量、Obsidian 写入结构、测试方式或与 `website` 的自动启动集成时，必须同步更新本文件、本目录 README，以及根目录和 `website` 模块的 `AGENTS.md` / `README.md`。
