# AI 项目趋势追踪站设计说明

## 1. 项目目标

构建一个公开可访问的网站，每天自动发现并追踪 GitHub 上与 AI Agent、Agent Skill 和 MCP 相关的高 Star 开源仓库。网站默认按最近 1 天 Star 增量展示热度，同时提供 7 天增量和总 Star 排行，帮助用户发现近期快速增长的项目。

首版只完成数据采集、趋势计算、排行榜、筛选和项目详情，不包含部署脚本、用户系统、收藏、通知或 AI 模型分类。

## 2. 技术选型

### 2.1 后端

- Python 3.12
- FastAPI
- SQLAlchemy 2 异步模式
- asyncmy
- Pydantic Settings
- APScheduler
- HTTPX
- MySQL 8.0

### 2.2 前端

- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia（仅存储主题和筛选偏好）
- Axios
- Lucide Vue Next

### 2.3 测试

- pytest、pytest-asyncio、respx
- Vitest、Vue Test Utils
- Playwright

## 3. 系统架构

后端按职责拆分为以下模块：

- `api`：处理 HTTP 路由、参数校验和响应 DTO，不包含复杂业务逻辑。
- `services`：处理排行榜、仓库详情、筛选和统计业务。
- `collector`：调用 GitHub API，执行搜索、分页、去重和仓库详情更新。
- `classifier`：根据仓库名称、简介和 Topics 执行透明的规则分类。
- `snapshot`：保存每日 Star 快照并计算 1 日、7 日增量。
- `repositories`：封装 MySQL 数据访问。
- `scheduler`：按配置时间触发采集，并使用 MySQL 命名锁避免重复执行。

前端由首页、仓库详情页、通用状态组件和 API 客户端组成。前后端通过 `/api/v1` 下的 JSON API 通信。

## 4. 数据模型

项目提供 `backend/sql/schema.sql`，由使用者手工执行。应用启动时检查必要数据表是否存在，但不自动建表或修改表结构。

### 4.1 repositories

保存 GitHub 仓库当前状态，主要字段包括：

- GitHub Repository ID（唯一）
- owner、name、full_name、html_url
- description、homepage
- language、topics（JSON）
- stars_count、forks_count、open_issues_count
- categories（JSON）和 matched_rules（JSON）
- archived、disabled、available
- github_created_at、github_updated_at、last_synced_at
- created_at、updated_at

`full_name` 和 GitHub Repository ID 均建立唯一索引；排行榜常用的 Star、语言和同步时间字段建立普通索引。

### 4.2 star_snapshots

保存仓库每日 Star 快照，主要字段包括 repository_id、snapshot_date、stars_count、created_at。`repository_id + snapshot_date` 建立联合唯一索引。

### 4.3 collection_runs

保存采集任务审计信息，包括开始和结束时间、状态、触发方式、查询数量、发现数量、更新数量、失败数量、GitHub 限流信息和脱敏后的错误摘要。

所有时间使用 UTC 存储；`snapshot_date` 按配置的业务时区（默认 `Asia/Shanghai`）确定自然日。

## 5. 发现与分类规则

每日通过 GitHub Search API 组合搜索以下主题与关键词：

- AI Agent：`ai-agent`、`agent-framework`、`agentic-ai`、`autonomous-agent`
- Skill：`agent-skills`、`ai-skills`、`claude-skills`、`codex-skills`
- MCP：`mcp-server`、`model-context-protocol`

查询词在配置文件中集中维护。候选仓库默认要求总 Star 不低于 100，并排除 Fork、Archived 和 Disabled 仓库。多个查询结果按 GitHub Repository ID 去重。

分类器根据名称、简介和 Topics 命中规则，可产生 `AGENT`、`SKILL`、`MCP` 多个分类，并保存具体命中规则供页面展示和问题排查。首版不调用 AI 模型。

已经收录的可用仓库每天继续刷新，即使当天未进入关键词搜索结果，也保留连续趋势。已删除、转为私有或长期无法访问的仓库标记为不可用，不删除历史快照。

## 6. 增量计算

- 1 日增量：最新快照减去前一自然日的最近有效快照。
- 7 日增量：最新快照减去 7 个自然日前及之前最近的有效快照。
- 若不存在历史基线，则返回 `null`，前端显示 `--`。
- Star 减少时保留负数，真实反映仓库变化。
- 首次采集只建立基线，不把仓库总 Star 当作新增 Star。

## 7. 定时任务与并发控制

默认每天北京时间 02:00 执行，可通过环境变量配置时区和 Cron 表达式。调度器在执行前获取 MySQL `GET_LOCK()` 命名锁；未获取锁时跳过本次执行并记录状态。任务结束后在 `finally` 中释放锁。

同时提供受保护的手动触发接口。接口要求 `X-Admin-Key`，管理密钥只从环境变量读取，并使用常量时间比较。自动任务和手动任务共享同一把数据库锁。

## 8. API 设计

统一前缀为 `/api/v1`，统一错误响应包含 `code`、`message` 和 `request_id`，不返回内部堆栈或敏感配置。

- `GET /repositories`：支持页码、每页数量、搜索词、分类、语言、最低 Star 和排序；排序值包括 `daily_stars`、`weekly_stars`、`total_stars`。
- `GET /repositories/{owner}/{name}`：返回仓库详情、分类依据和最近 30 天趋势。
- `GET /languages`：返回可筛选语言与当前可用仓库数量。
- `GET /stats`：返回仓库总数、今日有增量的仓库数、最后成功采集时间及最近任务状态。
- `POST /admin/collections`：验证管理密钥后触发后台采集；已有任务运行时返回冲突状态。
- `GET /health`：返回应用状态和数据库连通性。

列表接口默认每页 20 条，最大 100 条。所有字符串参数限制长度并执行白名单校验，SQL 查询只使用 SQLAlchemy 参数绑定。

## 9. 页面设计

界面采用 GitHub 风格的信息密度和交互习惯，但不复制 GitHub Logo 或冒充官方产品。

### 9.1 首页

- 顶部深色导航：产品名称、全局搜索、明暗主题切换。
- 标题区：收录仓库数量、最后成功更新时间和采集状态。
- 左侧筛选：全部、Agent、Skill、MCP，编程语言和最低 Star。
- 主列表顶部：今日增长、7 日增长、总 Star 三个排序标签。
- 仓库列表项：名称、简介、分类、Topics、语言色点、总 Star、1 日和 7 日增量、更新时间、30 天迷你趋势线。
- 仓库名称进入站内详情；外链图标按钮打开 GitHub，并带有 Tooltip 和可访问名称。

移动端将筛选栏收进抽屉，保持核心指标可扫描。固定格式控件使用稳定尺寸，动态内容不得导致明显布局跳动。

### 9.2 详情页

展示仓库基本信息、分类依据、Topics、语言、总 Star、Fork 和 Issue 数量，以及最近 30 天 Star 折线趋势。提供返回排行榜和访问 GitHub 两个明确操作。

### 9.3 状态与可访问性

提供骨架加载、空结果、首次无历史数据、数据过期、API 异常和重试状态。页面支持键盘操作、可见焦点、语义化标题、ARIA 标签、明暗主题和减少动态效果偏好。

## 10. 异常与安全

- GitHub Token、数据库连接和管理密钥仅通过环境变量读取，`.env` 不提交版本库。
- GitHub API 限流时读取限流响应头，任务标记为部分成功并保留已有数据。
- 单个仓库失败不会中断整批采集；全局认证失败或数据库失败会终止任务。
- 日志对 Token、数据库密码和请求头进行脱敏。
- 前端不持有 GitHub Token 或管理密钥。
- 仓库简介和 Topics 以纯文本渲染，禁止注入 HTML。
- 外部链接使用 `noopener noreferrer`。

## 11. 测试与验收

后端单元测试覆盖分类、去重、增量计算、参数校验、限流和部分失败；使用 Mock GitHub 响应，不依赖真实 API。MySQL 集成测试验证建表脚本、联合唯一索引、JSON 字段、排行榜查询和命名锁。

前端测试覆盖筛选、排序、分页、主题偏好和主要状态组件。Playwright 在桌面端和移动端验证首页、详情页、筛选、搜索、主题切换与错误恢复流程，并检查无明显内容重叠或溢出。

验收标准：

1. 执行 `schema.sql` 后，后端能连接 MySQL 并通过健康检查。
2. 配置有效 GitHub Token 后可完成首次采集并建立 Star 基线。
3. 第二个自然日采集后能显示真实 1 日增量。
4. 首页可按日增、7 日增和总 Star 排序，并组合使用分类、语言和关键词筛选。
5. 详情页显示最近 30 天已有快照，不伪造缺失日期数据。
6. GitHub API 部分失败时，已有榜单仍可访问且页面显示最后成功更新时间。
7. 自动采集和手动采集并发触发时只执行一个任务。

## 12. 项目交付内容

- 可运行的 FastAPI 后端与 Vue 3 前端源码。
- 完整 MySQL 8.0 建表脚本 `backend/sql/schema.sql`。
- `.env.example`，不包含任何真实凭据。
- 后端、前端和端到端测试。
- `README.md`，说明数据库建表、环境配置、依赖安装、开发启动、首次采集和测试方法。
- 不提供特定云平台、域名、HTTPS 或生产服务器部署脚本。
