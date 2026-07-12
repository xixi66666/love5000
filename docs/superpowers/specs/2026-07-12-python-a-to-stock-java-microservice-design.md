# Python-A 到 Stock Java 微服务迁移设计

## 背景

`website/python-a` 当前是 A 股自选股 AI 研究台，使用 Python 标准库 `ThreadingHTTPServer` 提供静态页面和 `/api/**` 接口，默认端口为 `5174`。它维护自选股、行情分析、AI 维度分析、交易复盘账本、截图解析草稿、Obsidian 长期记忆和知识图谱。

本次迁移的目标不是改变业务能力，而是将后端运行时统一为 Java 8 + Spring Boot 2.6.13，并把服务调整为与 `website` 平级的独立 Maven 微服务。前端体验、API、端口、文件数据和 Obsidian 内容保持兼容。

## 目标

1. 新增根目录平级模块 `stock`，artifactId 为 `stock`，包名为 `com.example.stock`。
2. 使用 Spring Boot 替换 Python HTTP 后端，默认继续监听 `5174`。
3. 保持现有页面、用户操作、API 路径、请求字段、响应字段和主要错误语义。
4. 保持现有 JSON 文件名、字段、ID、日期格式和 Obsidian Markdown 结构。
5. 保持东方财富、DeepSeek、Vision、Tushare 和 SpringAI 的现有功能边界。
6. 让 `stock` 能独立构建、测试、启动和部署，`website` 只保留入口和健康检测。

## 非目标

- 不重新设计前端页面。
- 不引入 MySQL，也不把现有 JSON 数据改成数据库表。
- 不增加多用户、权限、JWT 或共享 Session。
- 不改变投资研究提示、风险边界或非投资建议声明。
- 不合并 `stock` 与 `quant-a`，也不改变 `quant-a` 的目录和数据边界。
- 不在本次迁移中升级 Java 或 Spring Boot 主版本。

## 总体架构

```text
love5000/
├── common/
├── website/                    # 主页服务，8080
├── lovestory/
├── imagetemplate/
├── stock/                      # A 股研究 Java 微服务，5174
│   ├── pom.xml
│   ├── AGENTS.md
│   ├── README.md
│   ├── src/main/java/com/example/stock/
│   ├── src/main/resources/static/
│   ├── src/test/java/com/example/stock/
│   └── obsidian-vault/A股AI/
├── pom.xml
└── scripts/start-love5000.ps1
```

`stock` 加入父 `pom.xml` 的 `<modules>`，按需依赖 `common`，但不依赖 `website` 业务代码。`website` 不调用 `stock` 的 Java 类，只通过浏览器入口和 HTTP 健康检查感知服务。

开发环境由根目录启动脚本编排 `stock` 和 `website`。生产环境将两个 Spring Boot 应用作为独立进程部署。

## Java 模块结构

```text
stock/src/main/java/com/example/stock/
├── StockApplication.java
├── config/          # 数据目录、外部 API、超时和模型配置
├── controller/      # HTTP 参数、响应和异常映射
├── dto/             # 请求与响应契约
├── model/           # 行情、账户、交易、草稿和元数据模型
├── service/         # 业务规则和服务编排
├── client/          # 东方财富、DeepSeek、Vision、Tushare HTTP 客户端
├── repository/      # JSON 文件兼容存储
└── obsidian/        # Markdown、双链和知识图谱写入
```

Controller 不实现行情计算、文件读写或外部 HTTP 调用。Service 负责业务规则，Client 负责外部接口，Repository 负责结构化 JSON 数据，Obsidian 组件负责 Markdown 输出。

## 前端兼容

原 `index.html`、`app.js` 和 `styles.css` 迁移到 `stock/src/main/resources/static/`，页面仍从 `/` 加载。第一版不进行视觉或交互重构。

前端继续使用相对路径访问 `stock` 的 `/api/**`。现有 SpringAI Agent `http://127.0.0.1:8090/api/agent/reports/stock` 调用保持原样，以避免本次后端迁移扩大到另一个服务。

## API 兼容

以下接口必须保留：

```text
GET    /api/health
GET    /api/watchlist
POST   /api/watchlist
DELETE /api/watchlist?code={code}
GET    /api/stock?code={code}
POST   /api/ai/dimension-analysis
POST   /api/obsidian/stock-daily-review
POST   /api/obsidian/daily-review
GET    /api/trading/dashboard?date={yyyy-MM-dd}
GET    /api/trading/capital-flows
POST   /api/trading/capital-flows
GET    /api/trading/account-snapshots
POST   /api/trading/account-snapshots
GET    /api/trading/trades?date={yyyy-MM-dd}
POST   /api/trading/trades
POST   /api/trading/parse/account-screenshot
POST   /api/trading/parse/trades-screenshot
GET    /api/trading/parse-drafts
POST   /api/trading/parse-drafts/{id}/confirm
POST   /api/trading/parse-drafts/{id}/reject
POST   /api/trading/daily-review
POST   /api/trading/insights/update
POST   /api/trading/stock-match
```

请求方法、查询参数、JSON 字段和 multipart 字段保持现有格式。响应保留现有 `ok`、`success`、`error` 和 `message` 字段。`/api/health` 保留 `ok: true`，并补充项目统一要求的 `success: true`。

全局异常处理负责把参数错误、数据错误、外部接口错误和未知错误映射为兼容响应。行情外部接口不可用时维持当前失败或降级策略，不能因为单个元数据来源失败导致整个页面不可用。

## 行情和外部 API

东方财富 Client 保留当前请求头、连接超时、读取超时、重试次数和数据有效性检查。行情计算继续保留价格缩放、涨跌幅、均线、换手分位、趋势评分、派发评分、风险等级和观察状态等规则。

DeepSeek Client 保留现有模型、API Base、超时、JSON 提示词和非确定性投资表达约束。Vision Client 保留账户截图与成交截图两种提示词；原图仍不保存，解析结果必须确认后才写入账本。Tushare 仍作为可选元数据补充来源。

所有外部 Client 通过构造器注入，单元测试使用替身，不访问真实东方财富、DeepSeek、Vision、Tushare 或 SpringAI 服务。

## JSON 数据兼容

结构化数据继续保存在 `obsidian-vault/A股AI/data/`：

```text
watchlist.json
capital_flows.json
account_snapshots.json
trades.json
parse_drafts.json
stock_name_mappings.json
stock-metadata/*.json
```

Jackson 读写必须兼容现有 UTF-8 JSON，保留字段名、ID 生成方式、日期格式、默认值和列表排序。写入使用同目录临时文件与原子替换。每个数据文件使用进程内读写锁，将读取、修改、写回作为一个临界区，避免并发请求覆盖更新。

配置同时支持：

```text
STOCK_OBSIDIAN_ROOT
ASHARE_OBSIDIAN_ROOT
```

`STOCK_OBSIDIAN_ROOT` 优先，旧变量作为兼容回退。未配置时默认使用 `stock/obsidian-vault/A股AI/`。

## Obsidian 兼容

Java 版本继续生成以下内容：

```text
股票/{股票代码}-{股票名称}.md
操作记录/{日期}-{股票代码}-{股票名称}.md
每日复盘/{日期}-交易复盘.md
交易心得总纲.md
知识图谱/行业/*.md
知识图谱/概念/*.md
知识图谱/技术形态/*.md
知识图谱/风险模式/*.md
知识图谱/交易错误/*.md
知识图谱/观察计划/*.md
```

Markdown 标题、frontmatter、章节顺序、风险提示、人工维护区和 Obsidian 双链格式保持兼容。更新单股长期文件时必须保留人工维护区，不能覆盖用户手写内容。

## 数据迁移与切换

切换前停止 Python 服务写入，然后把 `website/python-a/obsidian-vault/A股AI/` 原样迁移到 `stock/obsidian-vault/A股AI/`。迁移不转换文件内容，不覆盖目标目录中的已有文件，并在复制后校验文件数量和关键 JSON 可解析性。

切换步骤：

1. Java 单元测试、契约测试和构建通过。
2. 使用临时目录和临时端口执行 Java 冒烟测试。
3. 停止 Python `5174` 服务，避免双写。
4. 原样迁移 Obsidian 和 JSON 数据并校验。
5. 启动 Java `stock` 服务监听 `5174`。
6. 验证首页、健康检查、自选股读取、行情、交易写入和 Obsidian 输出。
7. 更新根启动脚本、主页健康检测说明和相关文档。
8. Python 代码短期保留为只读回退，但不再作为默认运行入口。

工作区现有未跟踪的 Python 文件属于用户改动，迁移过程不得删除、覆盖或移动这些文件。

## 启动与集成

新增模块命令：

```bash
mvn -pl stock -am test
mvn -pl stock -am spring-boot:run
```

根启动脚本先检查 `http://127.0.0.1:5174/api/health`；不可用时启动 `stock`，健康检查通过后再启动 `website`。`website` 首页继续链接 `http://127.0.0.1:5174/`。

`website` 不再负责启动 Python 解释器。现有 `PythonAAutoStartRunner` 在切换时删除或替换为不包含业务依赖的开发期 Java 服务启动适配器；生产环境不由一个业务服务管理另一个业务服务的生命周期。

## 测试策略

### 服务单元测试

将现有 28 个 Python 测试覆盖的业务规则迁移为 JUnit 5 测试，包括：

- 本金、账户快照和盈亏计算。
- 交易规范化、日期过滤和解析草稿确认/拒绝。
- 股票名称唯一匹配、未知匹配和人工映射。
- JSON 缺失、损坏备份、UTF-8 和原子写入。
- Obsidian 每日复盘、单股文件人工区保留和知识图谱节点。
- 截图提示词与未配置 API Key 的错误。
- 中文研究字段和非投资建议表达边界。

### 文件兼容测试

测试使用临时目录读取现有格式的 JSON fixture，执行一次业务写入后验证字段、ID、日期和排序。Markdown golden file 测试验证标题、章节、frontmatter、双链和风险提示。

### HTTP 契约测试

使用 MockMvc 覆盖全部 `/api/**` 路由的请求方法、参数、状态码和响应字段。外部 Client 使用 mock，不能调用真实服务。

### 冒烟测试

Java 服务使用非 `5174` 临时端口启动，验证：

- `/` 返回研究台页面。
- `/api/health` 返回 `ok: true` 和 `success: true`。
- 自选股可以从兼容 JSON 读取。
- 交易写入临时数据目录。
- 每日复盘写入临时 Obsidian 目录。

## 文档同步

实现时必须同步更新：

- 根 `AGENTS.md` 和 `README.md`。
- `website/AGENTS.md` 和 `website/README.md`。
- 新增 `stock/AGENTS.md` 和 `stock/README.md`。
- 根启动脚本中的服务名称、启动命令和健康检查说明。
- 父 `pom.xml` 模块列表和主页服务入口说明。

文档统一使用 `stock` 表示 Java 微服务，`python-a` 仅表示迁移前的旧实现。

## 验收标准

1. `stock` 是父 Maven 工程中与 `website` 平级的模块。
2. Java 服务在 `5174` 提供原首页和全部现有 API。
3. 原 JSON 和 Obsidian 数据无需内容转换即可被 Java 服务读取。
4. Java 写出的 JSON 和 Markdown 与既有格式兼容。
5. 前端主要工作流不需要用户重新学习或修改配置。
6. 外部服务失败不会破坏本地数据，错误响应保持兼容。
7. Java 测试不依赖真实外部行情、AI、MySQL 或 OSS。
8. `website` 与 `stock` 可以独立构建、启动和停止。
9. 根文档、模块文档、启动脚本和代码保持一致。
