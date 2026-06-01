# quant-a

`quant-a` 是 `love5000/website` 下独立运行的 FastAPI A 股多因子量化研究微服务，用于本地量化研究台、评分实验、组合候选排序和回测辅助。它不是 Java Maven 模块，不加入根目录 `pom.xml` 的 `<modules>`，也不执行 `mvn -pl quant-a ...`。

## 服务边界

- 仅用于量化研究、风险识别、组合候选排序和回测辅助。
- 不构成任何投资建议，不承诺收益，不输出确定性买入、卖出或持有结论。
- 评分、回测和报告输出都应保留风险提示与偏差披露。
- 数据、配置、缓存、测试和报告都保持在 `website/quant-a/` 内，不写入 `website/python-a/obsidian-vault/`。
- 与 `website` 的集成以入口链接、健康检测或反向代理为主，不把 `quant-a` 业务逻辑改写进 Java Controller。

## 环境准备

建议使用 Python 3.9+，本机开发可直接在 `quant-a` 目录安装依赖：

```bash
cd website/quant-a
python -m pip install -r requirements.txt
```

主要依赖包括 FastAPI、Uvicorn、Pydantic、DuckDB、Pandas、PyYAML、Requests、Pytest 和 HTTPX。

## 真实行情源配置

第一阶段推荐继续使用 `provider.active=akshare` 作为真实行情源验证入口；`mock` 仍用于单元测试和离线演示。Tushare 已保留 Provider 接口位，后续在 token 和权限到位后，可以把配置切换为：

```yaml
provider:
  active: tushare
  tushare:
    token_env: TUSHARE_TOKEN
    timeout_seconds: 15
```

Tushare 使用环境变量读取 token：

```powershell
$env:TUSHARE_TOKEN="your-token"
```

不要把 `TUSHARE_TOKEN` 写入代码、配置文件、README 示例之外的真实值或 Git 提交记录。当前 `TushareProvider` 只实现股票基础信息、交易日历、日行情和估值数据的接口骨架；财务数据和指数成分需要对应 Tushare 权限后再扩展映射。测试使用 mock 的 `tushare` 模块和环境变量，不会真实联网。

## 本地运行

```bash
cd website/quant-a
python -m uvicorn main:app --host 127.0.0.1 --port 5175 --reload
```

启动后访问：

- `http://127.0.0.1:5175/`
- `http://127.0.0.1:5175/docs`
- `http://127.0.0.1:5175/api/health`

直接启动 `website` 时，Java 侧会自动检查 `http://127.0.0.1:5175/api/health`。如果 `quant-a` 已经可用，会直接复用；如果不可用，会在 `website/quant-a/` 目录下自动执行 Uvicorn 拉起服务。IDEA 中运行 `website` 时，`quant-a` 的标准输出和错误输出默认会显示在 `website` 的同一个控制台。

## 测试

```bash
cd website/quant-a
python -m pytest -v
```

本仓库任务验证时可使用明确的 Python 解释器：

```powershell
cd website/quant-a
& 'C:\Users\xixixiaozi\AppData\Local\Programs\Python\Python311\python.exe' -m pytest tests -v
```

## 主要入口

| 路径 | 方法 | 说明 |
| --- | --- | --- |
| `/` | `GET` | Quant 研究台前端页面 |
| `/api/health` | `GET` | 健康检查，返回服务可用状态 |
| `/api/status` | `GET` | 返回当前配置、数据和研究台状态摘要 |
| `/api/data/sync` | `POST` | 同步或刷新研究数据 |
| `/api/scores/run` | `POST` | 执行多因子评分与候选排序 |
| `/api/backtests/run` | `POST` | 执行回测任务并返回结果摘要 |
| `/docs` | `GET` | FastAPI 自动生成的 Swagger 文档 |

接口响应约定至少包含：

```json
{
  "success": true
}
```

错误响应至少包含：

```json
{
  "success": false,
  "message": "error detail"
}
```

## 第一版 baseline

第一版以可验证、可替换、可隔离为目标：

- 数据 Provider：运行配置默认使用 `akshare` 接入真实全市场行情；`mock_provider` 保留给稳定测试和离线演示，避免单元测试依赖真实外部行情接口。
- 存储：使用 DuckDB 保存本地研究数据，运行时数据库和缓存不提交到 Git。
- 配置：使用 `website/quant-a/configs/` 下的本地配置，运行参数优先支持环境变量或配置文件覆盖。
- 因子模型：`Value-Quality-Momentum v0.1`，先覆盖价值、质量、动量三个基础维度。
- 回测：提供月度调仓回测，用于观察组合候选排序的历史表现和风险特征。
- 披露：报告中保留风险、偏差、样本、数据质量和非投资建议说明，避免把历史回测结果表达成未来收益承诺。

## 后续扩展方向

扩展到全市场数据和更复杂策略前，需要优先补齐以下工程边界：

- Provider 扩展：把真实行情、财务、指数成分、交易日历等数据源封装为可替换 Provider，保持接口稳定。
- 数据可用日：所有因子和回测必须记录数据可见日期，避免使用当时不可获得的数据。
- 数据版本：对行情、财务、因子结果和回测输入建立版本或快照，保证结果可复现。
- 避免未来函数：回测只能读取调仓日之前已经可用的数据，财报、复权、停牌和成分股变化都要按时间点处理。
- 测试隔离：单元测试继续优先使用 mock provider 和临时存储，不依赖真实网络、真实外部行情接口或本地运行产物。

