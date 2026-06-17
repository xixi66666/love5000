# A 股自选股 AI 研究台

> 当前版本：2026-06-14
> 定位：围绕用户自己维护的少量 A 股自选股，做行情跟踪、多维度股票分析、AI 研究辅助和 Obsidian 长期记忆写入。
> 边界：本项目只做研究辅助、信息整理、风险提示和复盘沉淀，不构成投资建议，不承诺收益，也不替代人工判断。

## 当前状态

这是 `love5000/website` 下的轻量级独立 Python 微应用。用户先维护自己的自选股池，系统从东方财富公开接口抓取行情、日 K、行业和题材标签，并可选使用 Tushare Pro 补充元数据，再通过 DeepSeek 生成多维度分析草稿，并可写入 Obsidian 长期记忆和知识图谱节点。

当前默认自选股为空，不再内置示例股票。首次使用时请在左侧手动加入股票代码。

## 功能

- 自选股池维护：新增、删除、按分组筛选。
- 实时行情：最新价、涨跌幅、今开、最高/最低、昨收、成交额、换手率。
- 技术图表：5/10/30 日均线和换手柱状图。
- 量化指标：趋势评分、换手分位、风险等级、派发风险提示。
- DeepSeek 多维分析：自动生成技术结构、量能与换手、基本面与板块、风险与反证、观察计划。
- AI 对话分析：围绕当前股票继续提问，结果可加入复盘草稿。
- Obsidian 写入：保存当前股票的多维度分析到 `obsidian-vault/A股AI/`，并自动生成股票、行业、概念、技术形态、风险模式、交易错误和观察计划的双链节点。
- 交易复盘账本：记录本金流水、账户快照、成交记录和每日复盘。
- 截图解析草稿：支持账户资金截图和历史成交截图 AI 解析，确认后才入账。
- 交易心得沉淀：写入每日复盘、每股长期文件和 `交易心得总纲.md`。
- 响应式布局：桌面和移动端都可使用。

## 多因子选股系统规划

专业多因子选股系统的目标、数据层、因子层、打分层、回测层、风控层、展示层、回测规则和迭代规范见：

```text
quant/README.md
```

## 技术栈

```text
HTML / CSS / 原生 JavaScript
Python 3.9+
ThreadingHTTPServer
unittest
东方财富公开行情接口
东方财富 F10 题材接口
Tushare Pro 可选补充接口
DeepSeek Chat Completions API
外部 AI 视觉解析接口
Obsidian Markdown
```

## 文件结构

```text
index.html                         页面入口
styles.css                         页面样式
app.js                             前端交互、图表渲染、AI 生成按钮、Obsidian 草稿
server.py                          本地后端：行情网关、DeepSeek 调用、Obsidian 写入
package.json                       启动脚本
services/                          账户、交易、存储、Obsidian、截图解析等服务拆分
tests/                             unittest 测试
deepseek.local.json                本地 DeepSeek API key 配置，已被 .gitignore 忽略
obsidian-vault/A股AI/data/          自选股数据
obsidian-vault/A股AI/data/stock-metadata/  股票行业/概念缓存
obsidian-vault/A股AI/股票/          单股长期记忆
obsidian-vault/A股AI/操作记录/      每次保存生成的多维度分析记录
obsidian-vault/A股AI/知识图谱/      自动生成的 Obsidian 双链概念节点
```

## 运行

从仓库根目录进入当前服务目录后执行：

```bash
cd website/python-a
npm run start
```

然后访问：

```text
http://127.0.0.1:5174
```

也可以直接打开 `index.html`，但离线打开时无法联网取数、无法调用 DeepSeek，也无法写入 Obsidian。

直接启动 `website` 时，Java 侧会自动检查 `http://127.0.0.1:5174/api/health`。如果 `python-a` 已经可用，会直接复用；如果不可用，会在 `website/python-a/` 目录下自动执行 `python server.py` 拉起服务。IDEA 中运行 `website` 时，`python-a` 的标准输出和错误输出默认会显示在 `website` 的同一个控制台。

## DeepSeek 配置

后端优先读取环境变量：

```text
DEEPSEEK_API_KEY
DEEPSEEK_API_BASE
DEEPSEEK_MODEL
```

默认配置：

```text
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
```

也可以使用本地私有配置文件 `deepseek.local.json`：

```json
{
  "DEEPSEEK_API_KEY": "你的 key"
}
```

`deepseek.local.json` 已加入 `.gitignore`，不要把 API key 提交到仓库。

## 行业和题材元数据

默认不需要任何 token。后端优先使用东方财富 F10 题材公开接口补充行业和题材：

```text
datacenter.eastmoney.com/securities/api/data/v1/get
reportName=RPT_F10_CORETHEME_BOARDTYPE
```

如果你以后有 Tushare Pro token，也可以设置环境变量作为补充数据源：

```text
TUSHARE_TOKEN
```

Tushare 当前用途：

- `stock_basic`：补充股票名称、交易所和行业。
- `ths_hot`：优先提取股票关联概念标签。
- `ths_member` / `concept_detail`：作为概念标签补充尝试。

如果东方财富接口、Tushare 接口或网络不可用，系统会自动降级为自选股字段和复盘文本规则，不影响行情查看和 Obsidian 保存。成功获取的数据会缓存到：

```text
obsidian-vault/A股AI/data/stock-metadata/{股票代码}.json
```

## 使用流程

1. 启动服务并打开页面。
2. 在左侧加入需要研究的股票代码。
3. 选择股票后查看行情、均线、换手分位和风险提示。
4. 在右侧选择分析重点。
5. 点击 `AI 生成维度分析`，系统会调用 DeepSeek 自动填写五个分析维度。
6. 如需继续追问，在中间下方的 AI 对话框提问。
7. 确认草稿后点击保存，写入该股票的 Obsidian 长期记忆。

## 多维度分析字段

DeepSeek 会生成以下字段：

- 技术结构：趋势、均线、关键位置、形态、有效/无效信号。
- 量能与换手：成交额、换手分位、放量/缩量、承接和抛压。
- 基本面与板块：行业、板块共振、公司事件、估值和叙事变化。
- 风险与反证：失效条件、潜在利空、交易分歧、待核验信息。
- 观察计划：下一步观察点、触发条件、需要补充的数据和决策边界。

提示词要求模型只输出严格 JSON，不输出确定性买卖指令，不编造未提供的公告、新闻或财务数据。

## 本地 API

```text
GET  /api/health
GET  /api/watchlist
GET  /api/stock?code=002580
POST /api/watchlist
DELETE /api/watchlist?code=002580
POST /api/ai/dimension-analysis
POST /api/obsidian/stock-daily-review
POST /api/obsidian/daily-review
```

## 交易复盘 API

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

截图解析会将图片发送给外部 AI 视觉接口。原图不保存，解析草稿必须确认后才写入账本。未配置 `VISION_API_KEY` 时，截图解析接口会返回明确错误，仍可人工录入本金流水、账户快照和交易记录。

## 测试

```bash
cd website/python-a
python -m unittest discover -s tests -v
```

测试覆盖账户服务、交易服务、存储服务、Obsidian 写入、股票代码匹配、上传解析和研究语言边界。测试不得真实调用 DeepSeek、视觉接口或外部行情服务。

## 数据来源

行情数据来自东方财富公开网络接口：

```text
实时行情：push2.eastmoney.com/api/qt/stock/get
历史日 K：push2his.eastmoney.com/api/qt/stock/kline/get
```

行业和题材标签优先来自东方财富 F10 题材接口，可选使用 Tushare Pro 补充；接口不可用时使用本地自选股字段和文本规则降级。后端会记录数据来源、抓取时间和最新交易日。交易前仍应与交易软件、交易所公告和上市公司公告交叉核对。

## Obsidian 写入

默认写入目录：

```text
obsidian-vault/A股AI/
```

主要输出：

```text
股票/{股票代码}-{股票名称}.md
操作记录/{日期}-{股票代码}-{股票名称}.md
每日复盘/{日期}-交易复盘.md
交易心得总纲.md
data/capital_flows.json
data/account_snapshots.json
data/trades.json
data/parse_drafts.json
data/stock-metadata/{股票代码}.json
知识图谱/行业/*.md
知识图谱/概念/*.md
知识图谱/技术形态/*.md
知识图谱/风险模式/*.md
知识图谱/交易错误/*.md
知识图谱/观察计划/*.md
```

保存内容包括行情快照、分析重点、技术结构、量能与换手、基本面与板块、风险与反证、观察计划、AI 维度分析、研究结论、AI 对话记录和知识图谱链接。交易复盘模块额外保存本金流水、账户快照、成交记录、每日复盘和交易心得总纲。

## 安全与合规边界

系统应使用概率化、证据化、可验证的表述：

```text
建议：换手率处于高分位，且高位放量滞涨，需要观察次日承接。
建议：当前技术结构仍强，但风险等级偏高，必须写清失效条件。
建议：基本面信息不足，需要补充公告、财报和行业景气度数据。
```

避免确定性表述：

```text
错误：主力明天一定拉升。
错误：这只股票必然出货。
错误：现在可以买入。
```

所有结论都应包含证据、置信度、反证条件和后续验证窗口。

## 文档维护

每次修改页面入口、API、服务拆分、运行配置、环境变量、Obsidian 写入结构、测试方式或与 `website` 的自动启动集成时，必须同步更新本 README、`website/python-a/AGENTS.md`，以及根目录和 `website` 模块的 `AGENTS.md` / `README.md`。

