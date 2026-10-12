# AI 项目趋势追踪站实施计划

> **执行约束：** 按任务顺序执行并使用复选框跟踪进度。项目实施采用当前会话内联执行，不使用 `using-superpowers` skill。

**目标：** 构建一个每天自动发现并追踪 GitHub AI Agent、Skill 与 MCP 高 Star 仓库的公开网站，提供真实的 1 日、7 日增长排行与 30 天趋势。

**架构：** FastAPI 后端负责 GitHub 数据采集、MySQL 持久化、趋势计算和 REST API；Vue 3 单页应用负责排行榜、筛选与详情展示。采集器采用“关键词自动发现 + 已收录仓库持续追踪”，MySQL 命名锁保证自动任务和手动任务不会重复运行。

**技术栈：** Python 3.12、FastAPI、SQLAlchemy 2、asyncmy、HTTPX、APScheduler、MySQL 8.0、Vue 3、TypeScript、Vite、Pinia、Axios、Vitest、pytest、Playwright。

---

## 一、计划文件结构

```text
skill-finder/
├── .editorconfig
├── .gitignore
├── README.md
├── docs/
│   ├── plans/2026-08-10-ai-project-tracker-implementation.md
│   └── specs/2026-08-10-ai-project-tracker-design.md
├── backend/
│   ├── .env.example
│   ├── pyproject.toml
│   ├── sql/schema.sql
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   ├── errors.py
│   │   │   └── v1/{health,repositories,stats,admin}.py
│   │   ├── collector/
│   │   │   ├── classifier.py
│   │   │   ├── github_client.py
│   │   │   └── service.py
│   │   ├── core/{config,logging,scheduler}.py
│   │   ├── db/{base,models,session}.py
│   │   ├── repositories/{collection_runs,repositories,snapshots}.py
│   │   ├── schemas/{common,repository,stats}.py
│   │   └── services/{repository_service,stats_service,trend}.py
│   └── tests/
│       ├── conftest.py
│       ├── unit/
│       └── integration/
└── frontend/
    ├── .env.example
    ├── package.json
    ├── vite.config.ts
    ├── playwright.config.ts
    ├── src/
    │   ├── main.ts
    │   ├── App.vue
    │   ├── api/{client,repositories}.ts
    │   ├── assets/styles/{tokens,base}.css
    │   ├── components/{AppHeader,FilterSidebar,RepositoryListItem,SparklineChart,StatePanel}.vue
    │   ├── router/index.ts
    │   ├── stores/preferences.ts
    │   ├── types/api.ts
    │   └── views/{HomeView,RepositoryDetailView}.vue
    └── tests/
        ├── unit/
        └── e2e/
```

## 二、实施任务

### Task 1：初始化仓库与后端最小应用

**文件：**

- 创建：`.editorconfig`
- 创建：`.gitignore`
- 创建：`backend/pyproject.toml`
- 创建：`backend/app/__init__.py`
- 创建：`backend/app/main.py`
- 创建：`backend/app/api/v1/health.py`
- 创建：`backend/tests/test_health.py`

- [ ] **Step 1：初始化 Git 并创建基础忽略规则**

运行：

```powershell
git init
```

`.gitignore` 至少包含：

```gitignore
.env
__pycache__/
.pytest_cache/
.ruff_cache/
.venv/
*.pyc
frontend/node_modules/
frontend/dist/
frontend/playwright-report/
frontend/test-results/
.idea/
.vscode/
```

预期：`git status --short` 只显示项目源码和文档，不显示环境文件或构建产物。

- [ ] **Step 2：声明后端依赖与工具配置**

`backend/pyproject.toml` 声明 Python `>=3.12`，运行依赖包含：

```toml
[project]
name = "skill-finder-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.116,<1",
  "uvicorn[standard]>=0.35,<1",
  "sqlalchemy>=2.0.40,<3",
  "asyncmy>=0.2.10,<1",
  "httpx>=0.28,<1",
  "apscheduler>=3.11,<4",
  "pydantic-settings>=2.10,<3",
]

[dependency-groups]
dev = [
  "pytest>=8.4,<9",
  "pytest-asyncio>=1.1,<2",
  "respx>=0.22,<1",
  "ruff>=0.12,<1",
]
```

同时配置 Ruff 行宽 100、目标版本 `py312`，pytest 使用 `asyncio_mode = "auto"`。

- [ ] **Step 3：先写健康检查失败测试**

`backend/tests/test_health.py`：

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

运行：

```powershell
cd backend
python -m pytest tests/test_health.py -v
```

预期：因 `app.main` 尚无应用对象而失败。

- [ ] **Step 4：实现最小 FastAPI 应用并让测试通过**

`health.py` 提供 `/health`，`main.py` 创建 `FastAPI(title="Skill Finder API")` 并挂载 `/api/v1` 路由。再次运行测试，预期 `1 passed`。

- [ ] **Step 5：执行质量检查并提交**

```powershell
python -m ruff check .
python -m pytest -q
git add .editorconfig .gitignore backend docs
git commit -m "chore: initialize skill finder project"
```

预期：Ruff 无错误，测试通过，生成首个提交。

### Task 2：MySQL 建表脚本、配置与数据库会话

**文件：**

- 创建：`backend/.env.example`
- 创建：`backend/sql/schema.sql`
- 创建：`backend/app/core/config.py`
- 创建：`backend/app/db/base.py`
- 创建：`backend/app/db/models.py`
- 创建：`backend/app/db/session.py`
- 创建：`backend/tests/unit/test_config.py`
- 创建：`backend/tests/integration/test_schema.py`

- [ ] **Step 1：为环境配置编写失败测试**

覆盖以下断言：默认业务时区为 `Asia/Shanghai`、最低 Star 为 100、调度器默认关闭、GitHub Token 和数据库地址不得出现在 `repr(settings)` 中。

```python
def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "mysql+asyncmy://user:pass@localhost/db")
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    settings = Settings(_env_file=None)
    assert settings.business_timezone == "Asia/Shanghai"
    assert settings.min_stars == 100
    assert settings.scheduler_enabled is False
    assert "secret-token" not in repr(settings)
```

运行 `python -m pytest tests/unit/test_config.py -v`，预期导入失败。

- [ ] **Step 2：实现强类型配置**

`Settings` 必须包含：`database_url`、`github_token`、`admin_key`、`business_timezone`、`collection_cron`、`scheduler_enabled`、`min_stars`、`cors_origins`。使用 `SecretStr` 保存三个敏感值，环境变量前缀为空，`.env.example` 只提供虚构示例：

```dotenv
DATABASE_URL=mysql+asyncmy://skill_finder:change_me@127.0.0.1:3306/skill_finder?charset=utf8mb4
GITHUB_TOKEN=github_token_here
ADMIN_KEY=replace_with_a_long_random_value
BUSINESS_TIMEZONE=Asia/Shanghai
COLLECTION_CRON=0 2 * * *
SCHEDULER_ENABLED=false
MIN_STARS=100
CORS_ORIGINS=http://localhost:10002
```

- [ ] **Step 3：编写完整 MySQL 8.0 建表脚本**

`schema.sql` 使用 `utf8mb4_0900_ai_ci`、InnoDB、UTC 会话时区，创建三张表。关键约束必须是：

```sql
CREATE TABLE repositories (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  github_id BIGINT UNSIGNED NOT NULL,
  owner VARCHAR(100) NOT NULL,
  name VARCHAR(100) NOT NULL,
  full_name VARCHAR(201) NOT NULL,
  html_url VARCHAR(512) NOT NULL,
  homepage VARCHAR(512) NULL,
  description TEXT NULL,
  language VARCHAR(100) NULL,
  topics JSON NOT NULL,
  categories JSON NOT NULL,
  matched_rules JSON NOT NULL,
  stars_count INT UNSIGNED NOT NULL DEFAULT 0,
  forks_count INT UNSIGNED NOT NULL DEFAULT 0,
  open_issues_count INT UNSIGNED NOT NULL DEFAULT 0,
  archived BOOLEAN NOT NULL DEFAULT FALSE,
  disabled BOOLEAN NOT NULL DEFAULT FALSE,
  available BOOLEAN NOT NULL DEFAULT TRUE,
  github_created_at DATETIME(6) NOT NULL,
  github_updated_at DATETIME(6) NOT NULL,
  last_synced_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uk_repositories_github_id (github_id),
  UNIQUE KEY uk_repositories_full_name (full_name),
  KEY idx_repositories_stars (stars_count),
  KEY idx_repositories_language (language),
  KEY idx_repositories_available_synced (available, last_synced_at)
) ENGINE=InnoDB;
```

`star_snapshots` 使用 `UNIQUE KEY(repository_id, snapshot_date)`；`collection_runs` 使用枚举替代方案 `VARCHAR(32)` 和普通索引，不使用难迁移的 MySQL ENUM。

- [ ] **Step 4：实现 SQLAlchemy 模型和异步会话**

模型字段名、长度、可空性和索引必须与 SQL 完全一致。`session.py` 提供 `create_async_engine`、`async_sessionmaker` 和 `get_db_session()`；应用禁止调用 `Base.metadata.create_all()`。

- [ ] **Step 5：验证脚本与模型一致性**

当设置了 `TEST_DATABASE_URL` 时执行集成测试：运行 `schema.sql` 后查询 `information_schema.tables` 和 `statistics`，确认三张表及联合唯一索引存在。未设置测试库时明确 `skip`，不能误报通过。

```powershell
python -m pytest tests/unit/test_config.py tests/integration/test_schema.py -v
git add backend
git commit -m "feat: add mysql schema and database foundation"
```

### Task 3：分类规则与趋势计算领域逻辑

**文件：**

- 创建：`backend/app/collector/classifier.py`
- 创建：`backend/app/services/trend.py`
- 创建：`backend/tests/unit/test_classifier.py`
- 创建：`backend/tests/unit/test_trend.py`

- [ ] **Step 1：先编写分类器测试**

至少覆盖：Topic 精确命中、名称/简介单词边界命中、多分类、大小写不敏感、`skill` 作为普通英文单词不误判。

```python
def test_classifies_agent_and_mcp_from_topics() -> None:
    result = classify_repository(
        name="agent-hub",
        description="Composable tools",
        topics=["ai-agent", "model-context-protocol"],
    )
    assert result.categories == ("AGENT", "MCP")
    assert "topic:ai-agent" in result.matched_rules
```

- [ ] **Step 2：实现不可变分类结果和集中规则表**

定义 `Classification(categories: tuple[str, ...], matched_rules: tuple[str, ...])`。Topic 采用精确匹配；名称和简介只匹配明确短语，如 `agent framework`、`agent skills`、`mcp server`，不对单独的 `agent` 或 `skill` 进行宽泛匹配。

- [ ] **Step 3：先编写趋势计算测试**

覆盖：连续日期、缺失某天、首次快照、Star 下降、7 日边界。固定输入：

```python
snapshots = [
    SnapshotPoint(date(2026, 8, 1), 100),
    SnapshotPoint(date(2026, 8, 2), 104),
    SnapshotPoint(date(2026, 8, 9), 121),
]
assert calculate_growth(snapshots, date(2026, 8, 9)).daily == 17
assert calculate_growth(snapshots, date(2026, 8, 9)).weekly == 17
```

规则：若前一自然日没有快照，日增量使用目标日前最近快照；若此前完全无基线则为 `None`。

- [ ] **Step 4：实现纯函数并执行测试**

趋势模块不依赖数据库和 FastAPI，仅接收已排序的快照值。运行：

```powershell
python -m pytest tests/unit/test_classifier.py tests/unit/test_trend.py -v
git add backend/app/collector/classifier.py backend/app/services/trend.py backend/tests/unit
git commit -m "feat: add repository classification and trend calculation"
```

### Task 4：GitHub API 客户端

**文件：**

- 创建：`backend/app/collector/github_client.py`
- 创建：`backend/tests/unit/test_github_client.py`

- [ ] **Step 1：用 respx 编写搜索分页失败测试**

测试客户端发送 `Accept: application/vnd.github+json`、`Authorization: Bearer <配置的 Token>` 和 `X-GitHub-Api-Version: 2022-11-28`；每页 100 条，读取 `Link` 头翻页，最多读取 GitHub 搜索允许的 1000 条。

- [ ] **Step 2：定义稳定的 GitHub DTO 与异常类型**

定义 `GitHubRepository`、`RateLimit`、`GitHubAuthError`、`GitHubRateLimitError(reset_at)`、`GitHubRequestError`。只解析项目实际使用字段；未知字段必须忽略。

- [ ] **Step 3：实现搜索和批量刷新接口**

客户端公开三个异步方法：`search_repositories(query, min_stars) -> list[GitHubRepository]`、`get_repository(full_name) -> GitHubRepository | None` 和 `get_rate_limit() -> RateLimit`。三个方法都通过同一个受控 `httpx.AsyncClient` 发出请求，并由客户端的异步上下文管理器统一关闭连接。

搜索查询追加 `stars:>=N fork:false archived:false`，排序使用 `stars desc`。404 返回 `None`；401/403 认证失败与限流必须区分；5xx 最多重试 3 次，间隔为 0.5、1、2 秒，测试通过注入零延迟函数保持快速。

- [ ] **Step 4：验证限流与部分失败行为**

测试 403 且 `X-RateLimit-Remaining: 0` 时抛出带 UTC 重置时间的限流异常；单仓库 404 返回 `None`；500 三次后抛出请求异常。

```powershell
python -m pytest tests/unit/test_github_client.py -v
git add backend/app/collector/github_client.py backend/tests/unit/test_github_client.py
git commit -m "feat: add resilient github api client"
```

### Task 5：数据仓储与完整采集流程

**文件：**

- 创建：`backend/app/repositories/repositories.py`
- 创建：`backend/app/repositories/snapshots.py`
- 创建：`backend/app/repositories/collection_runs.py`
- 创建：`backend/app/collector/service.py`
- 创建：`backend/tests/unit/test_collection_service.py`
- 创建：`backend/tests/integration/test_repository_storage.py`

- [ ] **Step 1：先测试发现结果去重和过滤**

构造两个查询都返回同一 GitHub ID，以及 Fork、Archived、低 Star 项目；断言只持久化符合条件的唯一项目，并记录所有命中分类。

- [ ] **Step 2：实现仓储接口**

`RepositoryStore` 提供按 `github_id` upsert、列出当前可用仓库、标记不可用；`SnapshotStore` 使用 MySQL 的 `INSERT` 加 `ON DUPLICATE KEY UPDATE` 冲突更新语法写入当日快照；`CollectionRunStore` 创建运行记录并更新最终状态。

Upsert 只能覆盖 GitHub 当前字段和同步字段，不能重置 `created_at` 或删除历史快照。

- [ ] **Step 3：实现采集服务编排**

采集顺序固定为：创建 RUNNING 日志 → 执行全部发现查询 → GitHub ID 去重 → 分类与过滤 → upsert → 刷新历史可用仓库 → 写入业务日期快照 → 更新 SUCCESS/PARTIAL/FAILED 日志。

搜索词集中定义：

```python
DISCOVERY_QUERIES = (
    "topic:ai-agent",
    '"agent framework" in:name,description',
    "topic:agentic-ai",
    "topic:agent-skills",
    '"agent skills" in:name,description',
    "topic:mcp-server",
    "topic:model-context-protocol",
)
```

- [ ] **Step 4：测试失败隔离和状态归档**

单仓库刷新失败时继续处理剩余仓库，最终为 `PARTIAL`；Token 无效或数据库错误为 `FAILED` 并重新抛出；错误摘要只保存异常类型和无敏感信息的消息。

- [ ] **Step 5：运行单元与 MySQL 集成测试**

```powershell
python -m pytest tests/unit/test_collection_service.py tests/integration/test_repository_storage.py -v
git add backend/app backend/tests
git commit -m "feat: persist repositories and daily collection snapshots"
```

### Task 6：调度器、MySQL 命名锁与手动触发接口

**文件：**

- 创建：`backend/app/core/scheduler.py`
- 创建：`backend/app/api/dependencies.py`
- 创建：`backend/app/api/v1/admin.py`
- 修改：`backend/app/main.py`
- 创建：`backend/tests/unit/test_admin_api.py`
- 创建：`backend/tests/integration/test_collection_lock.py`

- [ ] **Step 1：先测试管理密钥校验**

断言缺少或错误 `X-Admin-Key` 返回 401，正确密钥返回 202；测试不得在断言或日志输出真实密钥。

- [ ] **Step 2：实现可移交给后台任务的 MySQL 锁租约**

使用独占数据库连接执行：

```sql
SELECT GET_LOCK('skill_finder_collection', 0);
SELECT RELEASE_LOCK('skill_finder_collection');
```

定义 `CollectionLockLease` 保存获取锁的专用 `AsyncConnection`。`acquire_collection_lock()` 在当前请求或调度回调中打开连接并获取锁；锁必须在获取它的同一连接上释放，`release()` 在 `finally` 中依次执行 `RELEASE_LOCK` 和关闭连接。获取失败返回 `None`，调用方返回 HTTP 409 或记录 `SKIPPED_LOCKED`。

- [ ] **Step 3：实现后台手动触发**

使用 `secrets.compare_digest()` 校验密钥。接口在返回响应前获取 `CollectionLockLease`，锁冲突立即返回统一错误 `COLLECTION_ALREADY_RUNNING`；获取成功后把租约传给 FastAPI `BackgroundTasks`，后台采集结束时释放同一连接上的锁，202 响应为 `{"status":"accepted"}`。这样不会出现已返回 202 后才发现锁冲突的竞态。

- [ ] **Step 4：挂载 APScheduler 生命周期**

仅当 `SCHEDULER_ENABLED=true` 时启动；使用配置的 Cron 和业务时区。应用 shutdown 时关闭调度器。调度回调先获取 `CollectionLockLease`，再调用与手动接口相同的 `run_collection(lease)`，结束时由该函数释放租约。

- [ ] **Step 5：验证并发锁与提交**

集成测试用两个独立连接同时争抢锁，断言只有一个成功。运行：

```powershell
python -m pytest tests/unit/test_admin_api.py tests/integration/test_collection_lock.py -v
git add backend
git commit -m "feat: schedule and protect collection runs"
```

### Task 7：排行榜、统计和详情 API

**文件：**

- 创建：`backend/app/schemas/common.py`
- 创建：`backend/app/schemas/repository.py`
- 创建：`backend/app/schemas/stats.py`
- 创建：`backend/app/services/repository_service.py`
- 创建：`backend/app/services/stats_service.py`
- 创建：`backend/app/api/errors.py`
- 创建：`backend/app/api/v1/repositories.py`
- 创建：`backend/app/api/v1/stats.py`
- 修改：`backend/app/main.py`
- 创建：`backend/tests/unit/test_repository_api.py`
- 创建：`backend/tests/integration/test_ranking_queries.py`

- [ ] **Step 1：先定义并测试 API 契约**

列表响应固定结构：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "last_successful_collection_at": null
}
```

测试 page 最小为 1、page_size 最大为 100、sort 只允许 `daily_stars|weekly_stars|total_stars`、category 只允许 `AGENT|SKILL|MCP`，非法值返回 422。

- [ ] **Step 2：实现排行 SQL**

查询使用当前仓库表、最新快照、前一自然日最近快照、7 个自然日前最近快照进行 LEFT JOIN。无基线的增长值为 NULL，排序时 NULL 放末尾，再按总 Star 和 GitHub ID 稳定排序。分类筛选使用 MySQL `JSON_CONTAINS`，搜索仅匹配 owner、name、description，并全部参数化。

- [ ] **Step 3：实现 DTO 和路由**

仓库列表项包含 `owner`、`name`、`description`、`html_url`、`language`、`topics`、`categories`、`stars_count`、`daily_stars`、`weekly_stars`、`last_synced_at`、`trend`。详情额外包含 30 天快照、Fork、Issue、主页和命中规则。

- [ ] **Step 4：实现统计接口和统一错误响应**

`/stats` 返回仓库总数、今日产生正增长的数量、最后成功采集时间和最近一次任务状态。`/languages` 返回当前可用仓库中非空语言及数量，并按数量降序、语言名称升序排列。404、409、500 转为 `code/message/request_id`；日志通过 request ID 关联，响应不暴露堆栈。

- [ ] **Step 5：验证组合筛选和提交**

集成测试插入固定仓库和快照，验证日增、周增、负增长、无基线、分类+语言+关键词组合、分页稳定性。

```powershell
python -m pytest tests/unit/test_repository_api.py tests/integration/test_ranking_queries.py -v
git add backend
git commit -m "feat: expose repository ranking and detail api"
```

### Task 8：Vue 工程、设计令牌与 API 客户端

**文件：**

- 创建：`frontend/package.json`
- 创建：`frontend/vite.config.ts`
- 创建：`frontend/tsconfig.json`
- 创建：`frontend/index.html`
- 创建：`frontend/.env.example`
- 创建：`frontend/src/main.ts`
- 创建：`frontend/src/App.vue`
- 创建：`frontend/src/assets/styles/tokens.css`
- 创建：`frontend/src/assets/styles/base.css`
- 创建：`frontend/src/api/client.ts`
- 创建：`frontend/src/api/repositories.ts`
- 创建：`frontend/src/types/api.ts`
- 创建：`frontend/src/stores/preferences.ts`
- 创建：`frontend/src/router/index.ts`
- 创建：`frontend/tests/unit/api-client.test.ts`

- [ ] **Step 1：初始化 Vue 3 TypeScript 工程依赖**

依赖包含 Vue、Vue Router、Pinia、Axios、Lucide Vue Next；开发依赖包含 Vite、TypeScript、Vitest、Vue Test Utils、jsdom、Playwright、ESLint 和 Prettier。脚本统一为 `dev`、`build`、`typecheck`、`test`、`test:e2e`、`lint`。

- [ ] **Step 2：先测试 API 错误归一化**

测试 Axios 422/500、网络中断和请求取消分别转换为 `ApiError`，其中用户消息可显示、内部响应不直接渲染。

- [ ] **Step 3：实现 API 类型与客户端**

类型字段与 Task 7 DTO 完全一致；日期保留 ISO 字符串，格式化只在组件层发生。`VITE_API_BASE_URL` 默认 `/api/v1`，请求超时 15 秒。

- [ ] **Step 4：建立 GitHub 风格设计令牌**

CSS 自定义属性至少包括背景、画布、边框、主次文本、强调蓝、成功绿、危险红、焦点环、阴影和语言色。明暗主题均满足正文 4.5:1 对比度；字体使用系统字体栈；卡片圆角不超过 6px；letter-spacing 固定为 0。

- [ ] **Step 5：实现路由和主题偏好并验证**

路由为 `/` 和 `/repositories/:owner/:name`。Pinia 只保存主题和最近筛选项，使用受控 localStorage 读写。

```powershell
cd frontend
npm install
npm run typecheck
npm run test -- --run
git add frontend
git commit -m "feat: initialize vue application foundation"
```

### Task 9：首页排行榜与筛选交互

**文件：**

- 创建：`frontend/src/components/AppHeader.vue`
- 创建：`frontend/src/components/FilterSidebar.vue`
- 创建：`frontend/src/components/RepositoryListItem.vue`
- 创建：`frontend/src/components/SparklineChart.vue`
- 创建：`frontend/src/components/StatePanel.vue`
- 创建：`frontend/src/views/HomeView.vue`
- 创建：`frontend/tests/unit/HomeView.test.ts`
- 创建：`frontend/tests/unit/RepositoryListItem.test.ts`

- [ ] **Step 1：先测试首页数据状态**

测试首次加载显示骨架、成功显示仓库、空结果显示清空筛选动作、失败显示重试、切换排序重新请求第一页。Mock API 必须断言实际查询参数。

- [ ] **Step 2：实现 URL 驱动的筛选状态**

`sort`、`category`、`language`、`min_stars`、`q`、`page` 写入 query string，浏览器前进后退可恢复。搜索输入使用 300ms 防抖；改变筛选重置到第一页。

- [ ] **Step 3：实现紧凑仓库列表**

列表项使用语义化 `<article>`，显示名称、简介、最多 4 个 Topics、分类、语言色点、总 Star、日增、周增和迷你趋势线。增长为 `null` 显示 `--`，负值保留负号。外链按钮使用 Lucide `ExternalLink`、Tooltip、`aria-label` 和 `rel="noopener noreferrer"`。

- [ ] **Step 4：实现响应式筛选与主题切换**

桌面端左侧固定宽度筛选栏，移动端使用按钮打开抽屉；Escape 关闭抽屉并恢复焦点。顶部栏不放说明性文案，主题按钮只使用图标和 Tooltip。

- [ ] **Step 5：运行组件测试与构建**

```powershell
npm run test -- --run HomeView RepositoryListItem
npm run typecheck
npm run build
git add frontend/src frontend/tests
git commit -m "feat: build repository trend leaderboard"
```

### Task 10：仓库详情与 30 天趋势

**文件：**

- 创建：`frontend/src/views/RepositoryDetailView.vue`
- 创建：`frontend/src/components/TrendChart.vue`
- 创建：`frontend/tests/unit/RepositoryDetailView.test.ts`
- 修改：`frontend/src/api/repositories.ts`

- [ ] **Step 1：先测试详情页状态**

覆盖成功、404、网络错误、空趋势和部分日期缺失；断言缺失日期不会被补成虚假 Star 数。

- [ ] **Step 2：实现详情请求和路由参数编码**

owner、name 分别使用 `encodeURIComponent`；组件卸载时取消请求，快速切换详情不会显示旧响应。

- [ ] **Step 3：实现无第三方图表依赖的 SVG 趋势图**

根据实际快照计算 viewBox 坐标，单点显示圆点，无数据显示 StatePanel；折线不使用渐变。SVG 提供标题与文本摘要，鼠标悬停和键盘聚焦均可读取日期与 Star 数。

- [ ] **Step 4：完成详情信息布局并验证**

展示分类依据、Topics、语言、Star、Fork、Issue、主页、最后同步时间。长仓库名使用换行与动态宽度约束，不能溢出。

```powershell
npm run test -- --run RepositoryDetailView
npm run typecheck
npm run build
git add frontend
git commit -m "feat: add repository detail and star trend view"
```

### Task 11：端到端流程、视觉与可访问性验证

**文件：**

- 创建：`frontend/playwright.config.ts`
- 创建：`frontend/tests/e2e/leaderboard.spec.ts`
- 创建：`frontend/tests/e2e/detail.spec.ts`
- 创建：`frontend/tests/e2e/responsive.spec.ts`
- 修改：`frontend/src/App.vue`
- 修改：`frontend/src/views/HomeView.vue`
- 修改：`frontend/src/views/RepositoryDetailView.vue`
- 修改：`frontend/src/components/AppHeader.vue`
- 修改：`frontend/src/components/FilterSidebar.vue`
- 修改：`frontend/src/components/RepositoryListItem.vue`
- 修改：`frontend/src/components/SparklineChart.vue`
- 修改：`frontend/src/components/TrendChart.vue`
- 修改：`frontend/src/assets/styles/tokens.css`
- 修改：`frontend/src/assets/styles/base.css`

- [ ] **Step 1：配置稳定的 API Mock 端到端环境**

Playwright 对 `/api/v1/**` 路由返回固定 JSON，使测试不依赖 GitHub 或 MySQL。测试桌面 `1440x900` 和移动 `390x844` 两个 viewport。

- [ ] **Step 2：覆盖核心用户流程**

验证默认日增排序、切换 7 日排行、分类与语言组合筛选、搜索防抖、分页、打开详情、返回后恢复筛选、主题切换和外链属性。

- [ ] **Step 3：验证布局和画布内容**

截图首页与详情页；断言页面 `scrollWidth <= clientWidth`，按钮文字不截断，抽屉不遮挡关闭按钮，趋势 SVG 的非背景像素数量大于阈值，避免空白图表。

- [ ] **Step 4：验证键盘和可访问性**

只用 Tab、Enter、Escape 完成搜索、打开筛选、选择分类、关闭抽屉和进入详情；检查每个图标按钮都有可访问名称，焦点可见，`prefers-reduced-motion` 下无非必要动画。

- [ ] **Step 5：按截图迭代并提交**

```powershell
npx playwright install chromium
npm run test:e2e
npm run lint
npm run typecheck
npm run build
git add frontend
git commit -m "test: verify responsive leaderboard workflows"
```

预期：桌面和移动用例全部通过，无横向滚动、重叠、空白趋势图或控制台错误。

### Task 12：README、全量验证与本地运行交付

**文件：**

- 创建：`README.md`
- 修改：`backend/.env.example`
- 修改：`frontend/.env.example`

- [ ] **Step 1：编写从零启动说明**

README 必须按以下顺序提供可执行命令：安装 MySQL 8.0 → 创建数据库用户 → 执行 `backend/sql/schema.sql` → 复制环境变量 → 安装后端依赖 → 启动 FastAPI → 安装前端依赖 → 启动 Vite → 调用手动采集接口 → 运行测试。

手动采集示例不得包含真实密钥：

```powershell
$headers = @{ "X-Admin-Key" = "replace_with_your_admin_key" }
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/admin/collections" -Headers $headers
```

- [ ] **Step 2：运行后端全量验证**

```powershell
cd backend
python -m ruff check .
python -m pytest -q
```

预期：Ruff 退出码 0；无 MySQL 测试环境时仅集成测试明确 skip，其余全部通过。

- [ ] **Step 3：运行前端全量验证**

```powershell
cd frontend
npm run lint
npm run typecheck
npm run test -- --run
npm run build
npm run test:e2e
```

预期：Lint、类型、单元测试、生产构建和端到端测试全部退出码 0。

- [ ] **Step 4：使用真实 MySQL 验证最小闭环**

执行建表脚本，启动后端和前端；先验证 `/api/v1/health`，再使用个人 GitHub Token 手动采集，确认 `collection_runs`、`repositories`、`star_snapshots` 均产生记录；首页显示仓库但首次日增为 `--`。

- [ ] **Step 5：执行安全与敏感信息扫描**

```powershell
rg -n "ghp_|github_pat_|mysql\+asyncmy://[^:]+:[^@]+@|X-Admin-Key.*[A-Za-z0-9]{20}" . -g '!docs/plans/**' -g '!*.example'
git status --short
git diff --check
```

预期：敏感信息扫描无结果；无意外生成文件；`git diff --check` 无空白错误。

- [ ] **Step 6：提交最终文档与修复**

```powershell
git add README.md backend frontend docs
git commit -m "docs: add local setup and verification guide"
git log --oneline --max-count=12
```

预期：每个主要能力均有独立提交，工作区干净。

## 三、完成定义

满足以下条件才可声明首版完成：

- MySQL 8.0 建表脚本可重复用于空数据库，应用不自动建表。
- 有效 GitHub Token 能完成自动发现、历史仓库刷新和当日快照写入。
- 首次采集不会伪造日增数据，后续快照可计算真实 1 日和 7 日增长。
- 首页、组合筛选、三种排序、分页和详情页均使用真实 API 数据。
- GitHub 限流、单仓库失败、任务并发、空数据和网络错误均有明确行为。
- 后端测试、前端测试、构建和 Playwright 桌面/移动验证全部通过。
- 源码、示例配置、README 和日志中不存在真实 Token、密码或管理密钥。
- 本地开发服务器可启动，并向用户提供实际访问地址。
