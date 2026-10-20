# AGENTS.md

## 健康检查协议

`GET /api/health` 顶层返回 `success=true` 和 `service="python-a"`，同时保留已有
`ok` 与运行信息字段。`website` 的 `ServiceHealthChecker` 使用该统一协议判断是否复用或启动进程。

## 项目概述

`website/python-a` 是 `love5000` 当前接入的 A 股自选股 AI 研究台，作为独立 Python 微应用运行，默认端口 `5174`。它不是 Java Maven 模块，不加入父 `pom.xml` 的 `<modules>`。

## 模块边界

- 后端入口是 `server.py`，使用 Python 标准库 `ThreadingHTTPServer`。
- 前端入口是 `index.html`、`app.js`、`styles.css`。
- 业务服务拆分在 `services/`，包括账户、交易、存储、Obsidian、股票匹配、股票元数据、知识图谱和截图解析。
- `services/stock_metadata_service.py` 必须保持无网络启动依赖：读取 `data/stock-metadata/{code}.json`，缓存缺失或损坏时返回调用方提供的降级元数据。
- `services/knowledge_graph_service.py` 负责生成 Obsidian 双链和知识图谱节点，所有节点文件名必须过滤 Windows 非法字符。
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

## 统一模型入口（2026-10-20）

主页提供全局文本模型选择，python-a、scrapling-ui、skill-finder、personal-agent 提供“跟随主页 / 服务原配置 / 独立模型”，下一次请求生效。图片、视觉、语音和视频保留专用模型；quant-a 与 lovestory 当前没有文本模型调用。
website 的 `/api/models` 提供目录核验、选择持久化和文本代理，状态文件为根 `.runtime/model-routing.json`，仅存模型 ID、不存密钥；Java 客户端在 common，Python 公共客户端在 website/model-routing，独立部署使用统一入口时需一并携带。原有认证保留。未选择时保留原逻辑，已选择但网关离线时报错。
共享选择器源为 website/src/main/resources/static/model-picker/picker.js，修改后执行 `python scripts/sync-model-picker.py`，React/Vue 修改后重新构建 dist。图片工作台新增独立图片模型下拉与 `OPENAI_IMAGE_MODELS` 白名单，支持 JSON/multipart 的 `model` 字段。
完整盘点、API、边界与验证见 [统一模型入口](../../docs/model-routing.md)。跨模块验证 `mvn test`；公共 Python 客户端验证 `python -m unittest discover -s website/model-routing`。
