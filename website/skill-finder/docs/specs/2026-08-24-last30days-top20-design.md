# last30days 模块改造：近 30 天最热 Top 20 榜单设计说明

## 1. 背景与目标

现有 `/last30days` 页面是一个"自由查询研究台"：用户输入主题、实时运行用户级 last30days 引擎并查看研究结果。实际使用中不符合预期。

改造目标：将该模块变为面向 **Agent / Skill 两个方向**的"近 30 天最热 Top 20"榜单页。数据由 last30days 引擎产出，**手动触发刷新 + 结果存库缓存**，页面打开即读缓存；呈现风格对齐主页排行榜。

非目标：不做自动定时刷新；不做方向的可配置化；不改动主页与仓库详情页；保留后端自由查询 API（`POST /api/v1/last30days`）供调试，前端不再使用。

## 2. 总体方案

### 2.1 数据流

1. 用户打开 `/last30days`，前端按当前方向 tab 调用 `GET /api/v1/last30days/rankings?direction=agent|skill`，后端从 MySQL 读取缓存榜单并返回。
2. 用户点击"刷新榜单"，前端调用 `POST /api/v1/last30days/rankings/refresh`（body 含方向），后端同步运行 last30days 引擎（复用现有 subprocess 适配层与固定主题查询词），对结果按互动量总和降序取 Top 20，upsert 入库后返回榜单。单次刷新可能耗时数分钟，前端展示加载态。
3. 每个方向独立缓存、独立刷新，互不影响。

### 2.2 方向定义

后端 `app/last30days/service.py` 内置常量：

| direction | 引擎查询词 |
| --- | --- |
| `agent` | `AI agents` |
| `skill` | `AI agent skills` |

## 3. 后端设计

### 3.1 数据表 `last30days_reports`

追加到 `backend/sql/schema.sql`（MySQL 5.5 兼容语法，应用不自动建表，需使用者手工执行一次）：

| 列 | 类型 | 说明 |
| --- | --- | --- |
| `direction` | `VARCHAR(32) PRIMARY KEY` | `agent` / `skill` |
| `status` | `VARCHAR(16) NOT NULL` | 引擎运行状态（working / partial / error 等） |
| `payload` | `MEDIUMTEXT NOT NULL` | 榜单 JSON：`{"items": [...], "clusters": [...], "sources": [...], "source_status": {...}}` |
| `message` | `VARCHAR(512) NULL` | 部分来源不可用等提示 |
| `fetched_at` | `DATETIME NOT NULL` | 榜单生成时间（UTC） |
| `created_at` / `updated_at` | `TIMESTAMP` | 与现有表风格一致 |

### 3.2 Service 层（`app/last30days/service.py` 扩展）

- `DIRECTION_QUERIES: dict[str, str]`：方向 → 查询词常量。
- `rank_items(items, limit=20)`：对 engagement 字典中的数值求和，降序排序取前 `limit` 条。
- `refresh_ranking(direction)`：
  - 校验方向合法性；
  - 模块禁用 / 引擎未配置 / 执行失败时返回对应状态，**不写库**；
  - 成功后取 Top 20 存入 `last30days_reports`（upsert），返回完整榜单；
  - 每方向一把 `asyncio.Lock`，防止并发刷新。
- `get_ranking(direction)`：读缓存；无记录时返回 `status="no-results"`、空 items 与提示文案；表不存在等数据库异常时同样降级为空态并附提示，不抛 500。

### 3.3 API（`app/api/v1/last30days.py` 扩展）

| 接口 | 说明 |
| --- | --- |
| `GET /last30days/status` | 现有，保留：引擎诊断与可用来源 |
| `POST /last30days` | 现有，保留：自由查询（前端不再使用） |
| `GET /last30days/rankings?direction=` | 新增：读缓存榜单 |
| `POST /last30days/rankings/refresh` | 新增：手动刷新指定方向榜单（同步等待） |

新增/复用 schema：`Last30DaysRankingResponse`（direction、status、items、clusters、sources、fetched_at、message）；刷新请求体 `{ "direction": "agent" }`，direction 用 `Literal["agent", "skill"]` 校验。

## 4. 前端设计

### 4.1 API 客户端（`src/api/last30days.ts` 扩展）

- 新增 `Last30DaysDirection = 'agent' | 'skill'`、`Last30DaysRankingResponse` 类型。
- 新增 `fetchLast30daysRankings(direction)` 与 `refreshLast30daysRankings(direction)`。

### 4.2 页面（重写 `src/views/Last30DaysView.vue`）

布局与视觉语言对齐主页：

- **页头**：eyebrow `MULTI-SOURCE RESEARCH`、标题"近 30 天最热"、描述文案；右侧保留引擎状态徽章（沿用 `GET /last30days/status`）。
- **方向 tab**：`Agent` / `Skill`，样式复用主页 sort-tabs；切换 tab 即加载对应缓存榜单。
- **工具行**：左侧 `最近更新：<fetched_at>`，右侧"刷新榜单"按钮；刷新中转圈禁用，并提示"完整研究可能需要几分钟"。
- **榜单列表**：卡片式排名列表（风格对齐 `RepositoryListItem`）：排名序号（1–20）、标题（外链新窗口打开）、来源 chip（GitHub / Reddit / X / YouTube / Hacker News / Web 等标签映射沿用现有 `SOURCE_LABELS`）、发布日期、摘要文本、互动量总和。
- **状态**：加载骨架 / 错误重试 / 空态（"还没有榜单数据，点击刷新按钮生成"）复用现有 `StatePanel` 组件；`partial` 状态沿用 notice 提示。
- **移除**：自由查询表单、clusters"讨论焦点"区块。
- 顶部导航文案（`AppHeader.vue`）："近 30 天研究" → "近 30 天最热"。

### 4.3 响应式与无障碍

沿用现有媒体查询与 aria 约定（tab 用 `role="tablist"`、状态区用 `role="status"/"alert"`）。

## 5. 错误处理

- 引擎未配置 / 诊断失败：页头徽章显示"需要配置 / 诊断失败"，刷新按钮点击后返回错误 notice，缓存数据照常展示（如有）。
- 引擎超时或执行失败：返回 error 状态与中文提示，不写库。
- 部分来源失败：`partial` 状态 + notice 提示，展示已获取结果。
- 表不存在等数据库异常：GET 降级为空态提示；refresh 返回错误提示。

## 6. 测试

### 6.1 后端（pytest，遵循现有 tests 结构）

- `rank_items` 排序与截断（engagement 求和、非数值忽略、不足 20 条）。
- `refresh_ranking`：正常写库并返回 Top 20；非法方向；模块禁用 / 未配置 / 执行失败不写库；并发刷新受锁保护（可选）。
- `get_ranking`：有缓存 / 无缓存空态。
- API 层：两个新端点的参数校验与响应结构。
- 数据库访问用 fake/内存实现或 monkeypatch，不依赖真实 MySQL（集成测试按现有约定在设置 `TEST_DATABASE_URL` 时另议）。

### 6.2 前端

- 重写 `tests/unit/Last30DaysView.test.ts`：tab 切换加载、刷新流程（loading→渲染）、空态、错误态、partial 提示。
- 更新 `tests/e2e/last30days.spec.ts`：mock 新端点，验证 tab、榜单渲染与刷新。
- `npm run lint`、`typecheck`、`test -- --run`、`build` 全部通过。

## 7. 交付后手工步骤

对数据库执行一次追加后的 `backend/sql/schema.sql`（仅创建新表 `last30days_reports`，不影响既有表）。
