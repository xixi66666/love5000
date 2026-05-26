# quant-a 专业多因子量化系统设计

日期：2026-05-26

## 1. 背景与目标

`quant-a` 是 `love5000` 仓库中新增的独立 Python 微服务，用于建设专业、完整、可运行、可回测、可迭代的 A 股多因子量化研究系统。

系统边界：

- 只做量化研究、风险识别、组合候选排序、回测和复盘辅助。
- 不构成投资建议，不承诺收益，不输出确定性买卖结论。
- 不加入 Maven 聚合模块。
- 不把量化业务写入 Java Controller。
- 不与现有 `python-a` 自选股 AI 研究台混写业务逻辑。

第一阶段采用垂直闭环型建设路径：用一个专业但范围可控的 baseline 策略贯通数据、因子、评分、组合、回测、报告、API 和页面。后续扩展沿既有接口自动补强，不推倒重来。

## 2. 已确认选择

- 项目形态：独立微服务 `quant-a`
- 后端框架：FastAPI + Uvicorn
- 默认端口：5175
- 数据源策略：可插拔 Provider
- 第一阶段股票池：指数成分池
- 后续股票池：沪深 A 股全市场
- 存储：DuckDB + Parquet
- 构建路径：方案 3，垂直闭环型
- baseline：价值质量动量型 Value-Quality-Momentum v0.1

## 3. 总体架构

`quant-a` 与现有 `python-a` 并列运行：

```text
love5000/
├── python-a/      # 现有自选股 AI 研究台，端口 5174
├── quant-a/       # 专业多因子量化系统，端口 5175
├── website/       # 主页入口增加 Quant 服务卡片
└── scripts/       # 统一启动脚本支持 quant-a
```

整体链路：

```text
数据源 Provider
-> 数据接入与质量校验
-> DuckDB + Parquet 研究数据仓库
-> 股票池 Universe
-> 因子注册与因子计算
-> 因子处理：缺失、去极值、标准化、行业内排名
-> 价值质量动量 baseline 评分
-> 组合构建与风控约束
-> 月度调仓回测
-> 交易执行模拟：手续费、滑点、涨跌停、停牌
-> 实验记录与版本归档
-> FastAPI 接口
-> Quant 页面工作台
```

核心原则：

1. 数据源可替换，系统内部只依赖统一 Provider 接口。
2. 因子可注册，新增因子不修改回测引擎。
3. 策略可配置，因子权重、股票池、调仓、成本模型都走配置。
4. 回测可复现，每次运行记录 `data_version`、`model_version`、`config_version`、`experiment_id`。
5. 输出有边界，只做研究、排序、风险解释和复盘。

## 4. 目录结构

建议新增目录：

```text
quant-a/
├── README.md
├── requirements.txt
├── main.py
├── configs/
│   ├── app.yaml
│   ├── universe.yaml
│   ├── model_v0_1.yaml
│   └── cost_model.yaml
├── quant/
│   ├── api/
│   ├── providers/
│   ├── storage/
│   ├── calendar/
│   ├── universe/
│   ├── factors/
│   ├── scoring/
│   ├── portfolio/
│   ├── backtest/
│   ├── risk/
│   ├── reports/
│   ├── experiments/
│   └── common/
├── web/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── data/
│   ├── raw/
│   ├── normalized/
│   ├── factors/
│   ├── scores/
│   ├── backtests/
│   ├── reports/
│   └── quant.duckdb
└── tests/
```

## 5. 模块职责

`providers/`

统一数据源接口。第一版实现 `mock_provider` 和 `eastmoney_provider`：`mock_provider` 用于确定性测试与本地演示，`eastmoney_provider` 用于公开行情数据接入。Tushare Pro、AkShare、JoinQuant、Wind 作为后续 Provider。

`storage/`

负责 DuckDB、Parquet、数据版本、表结构、批次写入、查询封装。其他模块不直接操作文件路径。

`calendar/`

负责交易日历、交易日偏移、月度调仓日、财报可用日计算。

`universe/`

根据配置生成某个交易日的股票池。第一版支持指数成分池，后续扩展全市场。

`factors/`

负责因子注册、因子定义、因子计算、缺失处理、去极值、标准化、行业内排名。第一版实现估值、质量、动量三个核心维度，并保留成长、风险、流动性接口。

`scoring/`

按配置合成综合评分。baseline 使用价值质量动量型。

`portfolio/`

根据评分生成目标组合，处理持仓数量、单票权重、行业权重、现金约束。

`backtest/`

负责月度调仓回测、订单生成、成交模拟、手续费、滑点、涨跌停、停牌、每日净值。

`risk/`

负责个股风险标签、组合风险指标、偏差披露、回撤和暴露提示。

`experiments/`

记录每次运行的 `experiment_id`、配置快照、数据版本、模型版本、状态和结论。

`reports/`

生成回测报告 JSON/Markdown，供 API 和页面展示。

`api/`

FastAPI 路由层，只负责任务触发、参数校验和响应，不写因子或回测业务。

`web/`

Quant 页面工作台。第一版展示运行状态、Top N、因子贡献、回测曲线、风险披露和实验记录。

关键边界：

- `main.py` 只启动 FastAPI。
- `api` 只调用 service，不直接计算因子。
- `factors` 不知道回测存在。
- `backtest` 不知道数据源细节，只读取标准化后的行情、评分和交易约束。
- `reports` 不重新计算结果，只聚合已落库结果。

## 6. 数据源 Provider 设计

建议结构：

```text
quant/providers/
├── base.py
├── eastmoney.py
├── akshare_provider.py
├── tushare_provider.py
└── mock_provider.py
```

统一接口至少包含：

```text
get_trade_calendar()
get_stock_basic()
get_daily_bars()
get_valuation()
get_financials()
get_industry_classification()
get_index_members()
get_limit_status()
```

每批数据入库时记录：

```text
provider
source_endpoint
fetch_time
trade_date
available_date
schema_version
data_version
quality_status
```

字段可信度分级：

```text
strict        可用于严谨回测
limited       可用但报告中披露限制
experimental  只用于实验，不进入正式 baseline
missing       暂不可用
```

## 7. 第一版股票池

第一阶段支持：

```text
沪深300
中证500
中证1000
```

配置示例：

```yaml
universe:
  type: index_members
  indexes:
    - CSI300
    - CSI500
  filters:
    include_st: false
    min_listed_days: 120
    min_avg_amount_20d: 50000000
    exclude_suspended: true
```

后续扩展全市场时：

```yaml
universe:
  type: all_a_share
  include_boards:
    - main
    - chi_next
    - star
  filters:
    include_st: false
    min_listed_days: 120
    min_avg_amount_20d: 50000000
```

`UniverseService` 对外只输出某个交易日的可选股票池：

```text
get_universe(trade_date, config) -> List[StockCandidate]
```

因子、评分、回测只消费这个结果，不关心股票池来自指数成分还是全市场。

## 8. 标准化数据字段

第一版最少需要这些标准化数据。

`stock_basic`：

```text
code, name, exchange, list_date, delist_date, status, industry
```

`trade_calendar`：

```text
trade_date, is_open, prev_trade_date, next_trade_date, is_month_end
```

`daily_bar`：

```text
trade_date, code, open, high, low, close, pre_close, volume, amount,
turnover_rate, adj_factor, limit_up, limit_down, suspend_flag,
available_date, data_version
```

`valuation`：

```text
trade_date, code, pe_ttm, pb, ps_ttm, pcf_ttm, dividend_yield,
total_market_value, float_market_value, available_date, data_version
```

`financial`：

```text
code, report_period, announce_date, available_date,
revenue, net_profit, deducted_net_profit, operating_cash_flow,
roe, roa, gross_margin, net_margin, debt_ratio,
data_version
```

`index_member`：

```text
index_code, code, effective_date, expire_date, data_version
```

## 9. Baseline 策略

第一版 baseline：

```text
Value-Quality-Momentum v0.1
```

目标：

```text
可解释
可回测
可复现
可扩展
有风险披露
```

主维度：

```text
价值 Value
质量 Quality
动量 Momentum
```

保留但不强依赖：

```text
成长 Growth
风险 Risk
流动性 Liquidity
```

推荐权重：

```text
价值：30%
质量：35%
动量：25%
风险惩罚：最高扣 10 分，在三维加权总分后扣减
流动性：先作为过滤条件，不作为收益因子
```

第一版因子：

价值：

```text
pb_inverse
pe_ttm_inverse
ps_ttm_inverse
industry_value_rank
```

质量：

```text
roe
operating_cash_flow_to_profit
gross_margin
debt_ratio_inverse
profit_stability_limited
```

动量：

```text
return_60d_exclude_5d
return_120d_exclude_5d
relative_industry_momentum_limited
ma_trend_score
```

风险/过滤：

```text
is_st
is_suspended
listed_days
avg_amount_20d
limit_up_blocked
limit_down_blocked
high_volatility_penalty
financial_missing_penalty
```

## 10. 因子处理与评分输出

每个交易日按股票池截面处理：

```text
原始因子
-> 缺失值检查
-> 极值处理
-> 方向统一
-> 行业内 rank 或全市场 rank
-> 标准化到 0-100
-> 合成维度分
-> 合成总分
```

评分输出：

```text
trade_date
code
name
industry
value_score
quality_score
momentum_score
risk_penalty
liquidity_flag
total_score
rank
factor_raw_values
factor_scores
missing_fields
risk_flags
data_version
model_version
```

## 11. 回测规则

第一版回测规则：

```text
调仓频率：月度
信号日：月末收盘后
成交日：下一交易日
默认持仓数量：30，可配置为 50 或其他正整数
权重：等权，单票上限 5%
行业上限：30%
买入价：T+1 开盘价 + 滑点
卖出价：T+1 开盘价 - 滑点
手续费：可配置
印花税：可配置
涨停：不可买
跌停：不可卖
停牌：不可交易
```

订单级执行结果：

```text
order_id
trade_date
signal_date
code
side
target_amount
target_quantity
filled_quantity
filled_price
commission
tax
transfer_fee
slippage_cost
impact_cost
order_status
reject_reason
```

未成交订单记录：

```text
order_id
first_attempt_date
last_attempt_date
retry_count
remaining_quantity
blocked_reason
next_action
```

## 12. 报告披露要求

每次回测报告必须披露：

```text
数据源限制
是否使用历史指数成分
财报公告日是否可靠
行业分类是否历史口径
成交价是否使用近似
手续费/税费模型版本
未成交订单原因
最大回撤
年度收益
月度收益
换手率
前十大持仓
主要加分因子
主要风险标签
```

偏差披露必须包含：

```text
bias_type
severity
affected_period
affected_fields
impact_description
mitigation
```

## 13. API 设计

健康与状态：

```text
GET /api/health
GET /api/status
```

数据同步：

```text
POST /api/data/sync
GET  /api/data/versions
GET  /api/data/quality
```

股票池：

```text
POST /api/universe/build
GET  /api/universe/latest
GET  /api/universe/{trade_date}
```

因子与评分：

```text
POST /api/factors/run
GET  /api/factors/latest
GET  /api/factors/{trade_date}
POST /api/scores/run
GET  /api/scores/latest
GET  /api/scores/{trade_date}
GET  /api/stocks/{code}/score-detail
```

回测：

```text
POST /api/backtests/run
GET  /api/backtests
GET  /api/backtests/{experiment_id}
GET  /api/backtests/{experiment_id}/report
GET  /api/backtests/{experiment_id}/orders
GET  /api/backtests/{experiment_id}/holdings
```

实验记录：

```text
GET  /api/experiments
GET  /api/experiments/{experiment_id}
POST /api/experiments/{experiment_id}/decision
```

成功响应：

```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

错误响应：

```json
{
  "success": false,
  "message": "具体错误原因"
}
```

## 14. 页面工作台

第一版页面直接进入工作台，不做营销页。

页面区域：

1. 系统状态

```text
服务状态
数据更新时间
当前数据版本
当前模型版本
最近实验 ID
```

2. 数据与任务

```text
同步数据
构建股票池
运行因子
运行评分
运行回测
```

3. Top N 榜单

```text
股票代码
名称
行业
综合分
价值/质量/动量分
风险标签
缺失字段提示
```

4. 单股解释

```text
因子贡献
加分项
扣分项
数据可用性
风险说明
```

5. 回测报告

```text
净值曲线
回撤
年度/月度收益
换手率
订单成交统计
已知偏差披露
```

输出语言边界：

- 允许：综合得分较高、主要贡献来自质量和动量、存在流动性风险。
- 禁止：可以买入、必涨、稳赚、主力必拉。

## 15. 运行方式与项目接入

依赖：

```text
fastapi
uvicorn
pydantic
duckdb
pandas
pyyaml
requests
```

启动：

```bash
cd quant-a
python -m uvicorn main:app --host 127.0.0.1 --port 5175 --reload
```

服务地址：

```text
首页：http://127.0.0.1:5175/
健康检查：http://127.0.0.1:5175/api/health
API 文档：http://127.0.0.1:5175/docs
```

根目录统一启动脚本后续增加可选参数：

```powershell
.\scripts\start-love5000.ps1 -StartQuant
```

`website` 首页新增入口：

```text
Quant · 5175
http://127.0.0.1:5175/
健康检查：http://127.0.0.1:5175/api/health
```

## 16. 与现有项目边界

- `python-a` 不调用 `quant-a` 的内部模块。
- `quant-a` 不写入 `python-a` 的 Obsidian 目录。
- `website` 只作为入口，不实现量化业务。
- Java Maven 聚合模块不加入 `quant-a`。
- 生产统一域名需求后续通过 Nginx、网关或反向代理处理。

## 17. 后续自动扩展路线

第一版闭环完成后，默认按以下路线继续补强：

1. 补 Tushare Pro Provider。
2. 补全市场 Universe。
3. 补数据质量报告页。
4. 补因子有效性分析：IC、Rank IC、分组收益。
5. 补实验对比中心。
6. 补组合优化和行业/风格暴露。
7. 补任务队列和定时更新。
8. 补多源对账和字段血缘。

后续扩展原则：

- 优先补当前最短板链路。
- 保持已有 API 和数据模型兼容。
- 新增能力必须记录版本、配置和已知限制。
- 不为短期展示牺牲回测严谨性。

## 18. 验收标准

第一版完成时必须满足：

1. `quant-a` 可独立启动，并提供 `/api/health`。
2. `website` 首页有 `Quant · 5175` 入口和健康检测。
3. 可通过 Provider 同步或生成基础行情、股票池、估值/财务样例数据。
4. 可构建指数成分股票池。
5. 可运行价值质量动量 baseline 评分。
6. 可执行月度调仓回测。
7. 回测输出净值、持仓、订单、未成交原因和风险披露。
8. 页面可查看系统状态、Top N、单股解释和回测报告。
9. 每次运行记录 `experiment_id`、数据版本、模型版本和配置快照。
10. 测试覆盖交易日偏移、因子方向、评分合成、手续费、涨跌停/停牌和回撤计算。
