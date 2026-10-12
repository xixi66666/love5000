# 采集改造设计：GitHub Trending Top 10

## 1. 背景与目标

现有采集器通过 GitHub Search API 用 7 组关键词全量搜索（每组最多 1000 条），并每天刷新所有已收录仓库，随后基于每日快照计算 1 日 / 7 日增量。

改造目标：不再拉取大量项目，改为直接抓取 GitHub Trending 日 / 周 / 月三张榜单，过滤 AI 相关项目，每期取 Top 10（按期内涨星），再补全详情入库。

保留：首页排行榜、分类 / 语言 / 关键词筛选、详情页、30 天趋势图、手动刷新与冷却、last30days 模块、MySQL 存储与采集审计。

非目标：不改前端整体布局，不改 last30days 模块，不引入用户系统。

## 2. 采集流程

1. 用 `scrapling.fetchers.AsyncFetcher`（curl_cffi，无需浏览器）请求：
   - `https://github.com/trending?since=daily`
   - `https://github.com/trending?since=weekly`
   - `https://github.com/trending?since=monthly`
   - 支持 `trending_proxy` 配置。
2. 解析每个条目的 owner/name、描述、语言、总 Star、期内涨星（`N stars today/this week/this month`）。
3. 过滤：仓库名称或描述命中 AI 关键词表（`trending_ai_keywords`，逗号分隔，可配置）才保留。
4. 按期内涨星降序取前 `trending_top_n`（默认 10）。
5. 三张榜合并去重（最多 30 个仓库），用现有 `GitHubClient.get_repository` 逐个补全 github_id / topics / forks / created_at 等字段。
   - 单个仓库失败：跳过并计入 `failed_count`。
   - 整体认证失败 / 限流：任务记为 `FAILED` / `PARTIAL`，错误摘要写入 `collection_runs`。
6. 入库后记录 `collection_runs` 审计；保留 MySQL 命名锁与手动触发 + 冷却逻辑。

删除：`DISCOVERY_QUERIES` 全量搜索、对已收录仓库的每日全量刷新、`min_stars` 过滤（趋势榜已天然筛选）。

## 3. 数据模型

新增 `trending_entries` 表（追加到 `backend/sql/schema.sql`，并提供独立迁移文件 `backend/sql/migrate-trending.sql`）：

```sql
CREATE TABLE trending_entries (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  repository_id BIGINT UNSIGNED NOT NULL,
  period VARCHAR(16) NOT NULL,          -- daily | weekly | monthly
  rank_position INT UNSIGNED NOT NULL,
  stars_gained INT NOT NULL,
  stars_total INT UNSIGNED NOT NULL,
  fetched_at DATETIME NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_trending_entries_period_repo (period, repository_id),
  KEY idx_trending_entries_period_rank (period, rank_position),
  CONSTRAINT fk_trending_entries_repository
    FOREIGN KEY (repository_id) REFERENCES repositories (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

每次采集按 period 先删除旧行再插入本期 Top 10。掉榜仓库的旧值被清除，榜单显示 `--`，但仓库记录保留在列表底部（按其总 Star 排序）。

`star_snapshots` 继续记录总 Star（每期榜单合并后的仓库每天一条），供详情页 30 天趋势图。

另提供 `backend/sql/purge-existing-data.sql`（手动执行）：清空 `repositories`、`star_snapshots`、`collection_runs`、`trending_entries`。

## 4. 榜单与 API

- 排序维度：`daily_stars` / `weekly_stars` / `monthly_stars` / `total_stars`。
- 日 / 周 / 月增量直接读 `trending_entries.stars_gained`，缺失返回 `null`；排序时 null 排最后。
- 分类新增 `PLUGIN`，规则如 `claude plugin` / `codex plugin` / `opencode plugin` / `ai plugin` / `copilot extension`；保留 AGENT / SKILL / MCP。
- 详情的日 / 周 / 月增量优先读 `trending_entries`，缺失时回退到快照差值；趋势图不变。

## 5. 前端变化

- 首页排序 tab：今日 / 本周 / 本月 / 总 Star。
- 列表项与详情页新增「本月 +N」。
- 筛选栏新增「插件」分类。
- 类型定义、mock-api、单元测试与 E2E 同步更新。

## 6. 配置与依赖

- `backend/pyproject.toml` 增加 `scrapling[fetchers]`（Python >= 3.10；AsyncFetcher 不需要下载浏览器）。
- 新配置：`trending_top_n=10`、`trending_ai_keywords=...`、`trending_proxy=`。
- 移除 `min_stars` 配置及其在采集器中的使用。
- README 更新：迁移 SQL、清理 SQL、新采集说明。

## 7. 错误处理

- 抓取失败（网络 / HTML 结构变化）：任务 `FAILED` 并记录错误摘要，已有榜单数据保留。
- 部分 period 抓取成功：任务 `PARTIAL`。
- API 限流 / 认证失败：任务 `FAILED`，错误摘要写入 `collection_runs`，不写半成品数据。
- 前端采集状态轮询与手动刷新逻辑复用现有实现。

## 8. 测试

后端：

- Trending HTML fixture 解析（名称、描述、语言、总 Star、期内涨星）。
- AI 过滤与 Top 10 截断、三榜去重。
- 采集服务使用 fake fetcher / fake GitHubClient，不联网；覆盖部分失败与跳过逻辑。
- 分类器新增 PLUGIN 规则。
- API：`monthly_stars` 排序、`PLUGIN` 分类参数校验。
- 更新受影响的旧测试（collector / classifier / config / repository API / ranking 集成测试）。

前端：

- HomeView 四个 tab 切换与月榜排序参数。
- 列表项月增量展示、插件筛选。
- `npm run lint`、`typecheck`、`test -- --run`、`build` 全部通过。

## 9. 手工步骤

1. 对数据库执行 `backend/sql/migrate-trending.sql`（仅新增表）。
2. 可选执行 `backend/sql/purge-existing-data.sql` 清空旧全量数据。
3. 后端安装新依赖：`.\.venv\Scripts\python.exe -m pip install -e .` 或 `pip install "scrapling[fetchers]"`。
4. 在 `.env` 按需配置 `TRENDING_PROXY` / `TRENDING_AI_KEYWORDS` / `TRENDING_TOP_N`。
