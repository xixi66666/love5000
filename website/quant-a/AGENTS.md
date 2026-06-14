# AGENTS.md

## 项目概述

`website/quant-a` 是 `love5000` 当前接入的 A 股多因子量化研究台，作为独立 FastAPI 微服务运行，默认端口 `5175`。它不是 Java Maven 模块，不加入父 `pom.xml` 的 `<modules>`。

## 模块边界

- 服务入口是 `main.py`。
- API 路由集中在 `quant/api/`。
- 量化核心在 `quant/`，包括 Provider、因子、评分、回测、组合、风控、报告、存储和服务编排。
- 前端页面在 `web/`。
- 配置在 `configs/`。
- 测试在 `tests/`，使用 `pytest` 和 FastAPI TestClient。
- 数据、配置、缓存和报告保持在 `website/quant-a/` 内，不写入 `website/python-a/obsidian-vault/`。
- Java 侧只负责入口链接、健康检查和自动启动，不把 Quant 业务逻辑改写进 Controller。

## 命令

```bash
cd website/quant-a
python -m pytest -v
python -m uvicorn main:app --host 127.0.0.1 --port 5175
```

健康检查：

```text
GET http://127.0.0.1:5175/api/health
```

## 配置与安全

- 运行配置优先使用环境变量或 `configs/` 下配置文件。
- `TUSHARE_TOKEN` 等真实 Token 只能使用环境变量或本机私有配置。
- 不提交 `.venv/`、`.pytest_cache/`、`__pycache__/`、`data/`、运行时数据库、缓存或生成报告。
- 评分、回测和报告输出必须保留风险提示和非投资建议边界。

## 文档同步

每次修改 API、配置文件、数据目录、Provider、因子、回测、组合、报告输出、测试方式或与 `website` 的自动启动集成时，必须同步更新本文件、本目录 README，以及根目录和 `website` 模块的 `AGENTS.md` / `README.md`。
