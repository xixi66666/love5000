# python-a 交易复盘账本设计

## 背景

`website/python-a` 当前定位是 A 股自选股 AI 研究台，核心能力是自选股维护、东方财富行情获取、多维度股票分析、AI 对话和 Obsidian 写入。用户的新需求是把它扩展为自我炒股记录网页，重点记录账户资金、每笔交易、截图解析结果、每日复盘和长期交易心得。

本设计保留现有股票研究功能和默认入口，不删除现有 API，不改变 `python-a` 作为独立 Python 微应用的边界。

## 目标

1. 新增交易复盘模块，支持每日收盘后记录账户资金、资本金流水、交易流水、持仓快照和复盘心得。
2. 支持上传账户资金截图和历史成交截图，调用外部 AI 视觉模型解析字段。
3. AI 解析结果必须进入待确认状态，用户确认后才写入真实账本。
4. 原始截图不落盘，只保存解析草稿、确认后的结构化数据和 Obsidian 复盘文件。
5. 本金通过手动维护初始本金、入金、出金和资金修正流水计算。
6. 成交截图缺少股票代码时，系统按股票名称自动匹配代码，无法唯一匹配时要求人工补全。
7. 使用 JSON 保存结构化账本数据，使用 Obsidian 保存可读复盘、股票长期文件和交易心得总纲。
8. 保留现有自选股、行情、图表、多维度分析、AI 对话和 Obsidian 写入功能。

## 非目标

1. 第一版不引入 SQLite、FastAPI、Flask、Django 或数据库。
2. 第一版不做策略回测、收益曲线、胜率、盈亏比等复杂统计。
3. 第一版不保存原始截图。
4. 第一版不保证公开接口能补齐完整基本面数据，缺失时明确展示数据不足。
5. AI 只做解析、整理和复盘辅助，不输出确定性买卖建议。

## 总体方案

采用模块化重构方案。保留 `server.py` 作为 HTTP 入口，将行情、账本、交易、截图解析、AI 复盘和 Obsidian 写入拆到独立服务模块。

页面默认仍展示旧股票研究页。新增顶部标签：

```text
股票研究 | 交易复盘
```

`股票研究` 保留现有功能。`交易复盘` 按每日收盘后的工作流组织：

```text
日期选择
账户资金区
本金流水区
截图解析区
待确认区
今日交易区
今日复盘区
心得更新区
```

## 后端结构

建议新增目录：

```text
website/python-a/
├── server.py
├── services/
│   ├── __init__.py
│   ├── storage_service.py
│   ├── account_service.py
│   ├── trade_service.py
│   ├── vision_parse_service.py
│   ├── stock_match_service.py
│   ├── market_service.py
│   ├── ai_review_service.py
│   └── obsidian_service.py
```

模块职责：

- `storage_service.py`：JSON 文件读写、原子写入、ID 生成、日期过滤、基础校验。
- `account_service.py`：本金流水、账户快照、持仓快照、账户收益和收益率计算。
- `trade_service.py`：交易记录新增、确认、去重、按日期和股票统计。
- `vision_parse_service.py`：调用外部 AI 视觉模型解析账户截图和成交截图，不保存原图。
- `stock_match_service.py`：根据股票名称匹配 A 股或 ETF 代码，返回唯一匹配、候选列表或未匹配。
- `market_service.py`：承接现有东方财富行情能力，扩展板块、概念、行业和基础公开数据获取。
- `ai_review_service.py`：生成每日复盘辅助文本、心得总纲更新草稿、个股经验摘要。
- `obsidian_service.py`：写入每日复盘、账户总览、股票长期文件和交易心得总纲。

`server.py` 只负责 HTTP 路由、请求解析、响应组装和静态文件服务，不承载复杂业务逻辑。

## 数据存储

结构化数据保存在：

```text
website/python-a/obsidian-vault/A股AI/data/
├── capital_flows.json
├── account_snapshots.json
├── trades.json
├── parse_drafts.json
└── review_state.json
```

### capital_flows.json

用于计算本金。

字段：

```json
{
  "id": "cf_20260605_001",
  "date": "2026-06-05",
  "type": "initial|deposit|withdraw|adjustment",
  "amount": 10000.0,
  "note": "初始本金",
  "created_at": "2026-06-05T15:30:00+08:00"
}
```

本金计算：

```text
本金 = 初始本金 + 入金 - 出金 + 资金修正
账户收益 = 当前总资产 - 本金
账户收益率 = 账户收益 / 本金
```

### account_snapshots.json

保存每日账户资金快照。

字段：

```json
{
  "id": "as_20260605_001",
  "trade_date": "2026-06-05",
  "broker": "西南证券",
  "account_alias": "**7763",
  "total_assets": 15909.86,
  "principal": 16000.0,
  "account_profit": -90.14,
  "account_profit_rate": -0.0056,
  "daily_profit": -378.0,
  "floating_profit": 391.57,
  "market_value": 15480.0,
  "available_cash": 429.86,
  "withdrawable_cash": 429.86,
  "position_ratio": 0.973,
  "positions": [],
  "source": "manual|ai_parse",
  "confirmed": true,
  "note": ""
}
```

持仓字段：

```json
{
  "stock_code": "601991",
  "stock_name": "大唐发电",
  "market_value": 15480.0,
  "floating_profit": 391.57,
  "profit_rate": 0.0259,
  "holding_quantity": 1800,
  "available_quantity": 1800,
  "cost_price": 8.382,
  "current_price": 8.6,
  "position_ratio": 0.973
}
```

### trades.json

保存确认后的交易流水。

字段：

```json
{
  "id": "tr_20260604_001",
  "trade_datetime": "2026-06-04T14:40:20+08:00",
  "trade_date": "2026-06-04",
  "stock_code": "601991",
  "stock_name": "大唐发电",
  "side": "buy|sell",
  "price": 8.99,
  "quantity": 300,
  "amount": 2697.0,
  "fee": null,
  "stamp_tax": null,
  "transfer_fee": null,
  "reason": "",
  "plan": "",
  "emotion": "",
  "planned_trade": null,
  "source": "manual|ai_parse",
  "confirmed": true,
  "created_at": "2026-06-05T15:30:00+08:00"
}
```

### parse_drafts.json

保存 AI 解析后、用户确认前的草稿。原始截图不保存。

字段：

```json
{
  "id": "pd_20260605_001",
  "type": "account_screenshot|trades_screenshot",
  "trade_date": "2026-06-05",
  "status": "pending|confirmed|rejected",
  "parsed": {},
  "warnings": ["股票代码未唯一匹配"],
  "created_at": "2026-06-05T15:30:00+08:00"
}
```

## Obsidian 结构

新增或维护：

```text
website/python-a/obsidian-vault/A股AI/
├── 账户/
│   └── 账户资金总览.md
├── 每日复盘/
│   └── 2026-06-05-交易复盘.md
├── 股票/
│   └── 601991-大唐发电.md
└── 交易心得总纲.md
```

### 每日复盘文件

包含：

- 当日账户快照。
- 当日交易列表。
- 今日操作总结。
- 做对的地方。
- 做错的地方。
- 买入是否符合计划。
- 卖出是否符合计划。
- 仓位是否合理。
- 情绪是否影响操作。
- 明日观察计划。
- 自由心得。
- 非投资建议提示。

### 股票长期文件

股票文件采用混合型结构：

```text
# 601991 大唐发电

## 系统维护区

### 交易统计
### 最近交易
### 复盘索引
### AI 个股经验摘要
### 后续观察计划

## 我的手写心得

这里由用户自由维护，系统不覆盖。
```

系统只更新 `系统维护区`，保留 `我的手写心得`。

### 交易心得总纲

`交易心得总纲.md` 包含：

- 最近更新摘要。
- 高频错误模式。
- 有效操作模式。
- 情绪和纪律问题。
- 仓位管理教训。
- 买入前检查清单。
- 卖出前检查清单。
- 仍待验证的策略假设。

更新流程：

```text
读取旧交易心得总纲
读取今日账户快照、今日交易、今日复盘
AI 生成更新草稿
用户确认
覆盖或更新交易心得总纲.md
```

## 前端交互

默认仍进入股票研究页。新增标签切换，不改变旧页面默认入口。

交易复盘页区域：

1. 日期选择：默认当天，可切换历史日期。
2. 账户资金区：展示总资产、本金、账户收益、账户收益率、当日参考盈亏、浮动盈亏、总市值、可用、可取、仓位。
3. 本金流水区：新增初始本金、入金、出金、资金修正。
4. 截图解析区：上传账户截图、上传成交截图。
5. 待确认区：展示解析草稿，允许修改字段、补股票代码、确认或拒绝。
6. 今日交易区：展示已确认交易，支持手动新增和编辑。
7. 今日复盘区：填写复盘字段。
8. 心得更新区：生成并确认交易心得总纲和个股文件更新。

页面必须明确提示：

```text
截图解析会将图片发送给外部 AI 视觉接口；原图不会保存到本地项目目录。
```

## 截图解析

支持两类截图：

1. 账户资金截图。
2. 历史成交截图。

### 账户资金截图解析字段

- 券商。
- 账户尾号或账户别名。
- 总资产。
- 浮动盈亏。
- 当日参考盈亏。
- 总市值。
- 可用资金。
- 可取资金。
- 仓位。
- 持仓股票名称。
- 持仓市值。
- 持仓盈亏。
- 持仓收益率。
- 持仓数量。
- 可用数量。
- 成本价。
- 现价。

### 成交截图解析字段

- 交易日期范围。
- 股票名称。
- 买卖方向。
- 成交时间。
- 成交价格。
- 成交数量。
- 成交金额。

截图中没有股票代码和手续费时，解析草稿保留空值或候选项，由用户确认。

## 股票匹配

成交截图中通常只有股票名称。匹配规则：

1. 先查已确认交易、持仓快照和自选股中的名称代码映射。
2. 再调用公开行情搜索或本地缓存匹配 A 股和 ETF。
3. 唯一匹配时预填代码。
4. 多候选或无匹配时进入待补全状态。
5. 用户确认后将名称代码映射写入缓存，后续优先使用。

## 股票分析增强

旧多维度分析保留，但在交易复盘中作为辅助能力。公开数据自动补充：

- 技术面：日 K、均线、涨跌幅、成交额、换手率。
- 量价结构：放量、缩量、换手分位、趋势强弱。
- 板块和概念：行业、概念归属、板块涨跌，取决于公开接口可用性。
- 基本面：只补可获得的基础公开资料，缺失时显示数据不足。

AI 分析必须基于已获取数据，不编造公告、财报和新闻。

## API 设计

新增接口：

```text
GET  /api/trading/dashboard?date=2026-06-05
GET  /api/trading/capital-flows
POST /api/trading/capital-flows
GET  /api/trading/account-snapshots
POST /api/trading/account-snapshots
GET  /api/trading/trades?date=2026-06-05
POST /api/trading/trades
POST /api/trading/parse/account-screenshot
POST /api/trading/parse/trades-screenshot
GET  /api/trading/parse-drafts
POST /api/trading/parse-drafts/{id}/confirm
POST /api/trading/parse-drafts/{id}/reject
POST /api/trading/daily-review
POST /api/trading/insights/update
```

旧接口保留：

```text
GET    /api/health
GET    /api/watchlist
POST   /api/watchlist
DELETE /api/watchlist?code={code}
GET    /api/stock?code={code}
POST   /api/ai/dimension-analysis
POST   /api/obsidian/stock-daily-review
POST   /api/obsidian/daily-review
```

响应格式继续保持至少包含：

```json
{
  "success": true
}
```

兼容旧代码时可同时保留 `ok` 字段。

## AI 配置

继续支持现有 DeepSeek 文本分析配置。截图视觉解析需要新增独立配置，优先使用环境变量：

```text
VISION_API_KEY
VISION_API_BASE
VISION_MODEL
```

如果未配置视觉模型，上传截图接口返回明确错误，前端仍允许人工录入。

## 错误处理

1. AI 视觉接口不可用：返回错误提示，不保存原图，允许人工录入。
2. AI 解析字段缺失：生成草稿并标记 warning。
3. 股票代码无法匹配：草稿状态保持 pending，用户补全后才能确认。
4. JSON 文件损坏：保留备份，返回错误提示，避免覆盖原数据。
5. Obsidian 写入失败：结构化数据已确认时不回滚，但提示用户复盘文件未写入。
6. 公开行情接口失败：展示数据不足，AI 不基于缺失数据推断。

## 测试与验证

第一版至少覆盖：

1. 本金流水计算：初始本金、入金、出金、修正。
2. 账户快照保存和收益率计算。
3. 交易记录保存、日期过滤、基础去重。
4. 解析草稿确认和拒绝流程。
5. 股票名称唯一匹配、多候选、无匹配。
6. Obsidian 股票长期文件更新时保留 `我的手写心得` 区。
7. 视觉 API 未配置时，上传接口返回可理解错误。
8. 旧接口 `/api/health`、`/api/watchlist`、`/api/stock` 仍可用。

验证命令：

```bash
cd website/python-a
python server.py
```

访问：

```text
http://127.0.0.1:5174/
http://127.0.0.1:5174/api/health
```

## 风险与边界

1. 账户截图属于敏感信息。用户已接受发送给外部 AI 视觉接口，但页面必须明确提示。
2. 原图不保存，后续无法回放解析过程，只能依据解析草稿和确认数据追溯。
3. 免费公开行情接口可能不稳定，板块和基本面数据不保证完整。
4. AI 解析不能直接入账，必须人工确认。
5. 投资复盘内容必须保留非投资建议边界。

## 实施顺序建议

1. 拆分后端服务模块，保证旧接口仍通过。
2. 新增 JSON 存储和账本 API。
3. 新增交易复盘标签页和人工录入功能。
4. 新增解析草稿流程。
5. 接入 AI 视觉解析。
6. 新增 Obsidian 每日复盘、股票长期文件和交易心得总纲更新。
7. 增强公开行情、板块和基础资料补充。
8. 补充测试和手动验证。
