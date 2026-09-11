# 2026-09-11 Prompt Console 服务端化设计

## 背景

`prompt-console/index.html` 原先直接 fetch 本地 `prompt-library.json`（4409 条、约 12.9MB）并在浏览器端过滤。需求是把数据存到腾讯云 MySQL，改为服务端分页/搜索。

## 决策

- **范围**：只改 prompt-console 页面；`imagetemplate` 维持构建时复制 JSON 快照，不读 MySQL。
- **存储**：腾讯云 MySQL `xixi` 库新建三张表，数据由本地 JSON 一次性导入。
- **数据源**：复用 `website` 现有数据源，默认指向远程 `jdbc:mysql://49.232.128.132:3306/xixi`（JDBC `characterEncoding=UTF-8`，Connector/J 8 自动映射 utf8mb4）；密码走 `WEBSITE_DB_PASSWORD` 环境变量，不提交。
- **搜索**：服务端分页/搜索，`keyword` 用 SQL `LIKE` 匹配标题/正文/标签/小分类，`%`/`_`/`\` 转义；默认 `page=1`、`size=48`，最大 100。
- **分类映射**：大分类 slug 在导入时按 `prompt-category-groups.js` 的同一 `GROUPS` 映射计算后写入 `prompt_entry.group_slug`；该 JS 文件保留为导入工具与 node 测试的数据源，页面运行时不依赖。

## 表结构（MySQL 5.7，utf8mb4）

- `prompt_group(slug PK, name, sort_order)`：10 个大分类。
- `prompt_source(id PK, source_id UNIQUE, name, url, license, summary, status)`：6 个来源。
- `prompt_entry(id PK, entry_key UNIQUE, source_id, title, category, group_slug, prompt MEDIUMTEXT, tags, license, status, source_url)`：4409 条；索引：`source_id`、`category`、`group_slug`、`status`。
- 导入用 `INSERT ... ON DUPLICATE KEY UPDATE` 幂等；JSON 中 9 条重复 `id` 以 `-2` 后缀保留。

## API（`com.example.website.prompt.library`）

```text
GET /api/prompts/meta
  -> { success, total, groups:[{slug,name,count,categories:[{name,count}]}], sources:[{id,name,status,count,license,summary}] }

GET /api/prompts?keyword=&group=&category=&source=&status=&page=1&size=48
  -> { success, total, page, size, entries:[{id,title,category,groupSlug,groupName,sourceName,tags:[],license,status,preview}] }

GET /api/prompts/{id}
  -> { success, entry:{ id, title, category, groupSlug, groupName, sourceName, sourceUrl, tags:[], license, status, prompt } }
```

- 列表 `preview` 为正文前 200 字（SQL `LEFT(...,200)`）；详情返回完整 `prompt`。
- 条目不存在返回 HTTP 404 + `{success:false,message:"提示词不存在"}`。

分层：`PromptLibraryController`（HTTP 入参/响应）→ `PromptLibraryServiceImpl`（分页参数钳制、LIKE 转义、meta 组装、tags 拆分）→ `PromptLibraryDao` + `mapper/prompt/PromptLibraryMapper.xml`。

## 前端

`prompt-console.js` 重写为 API 驱动：

- `loadMeta()` 渲染大分类/小分类/来源筛选与计数；
- 搜索 300ms 防抖，筛选/搜索触发服务端分页请求；
- "加载更多"翻页追加（`currentPage += 1`）；
- 详情弹窗调 `GET /api/prompts/{id}`；
- 原有 class 钩子（`.entry-list`、`.category-chip`、`.source-card`、`.dialog-*` 等）全部保留；
- `prompt-category-groups.js` script 标签从页面移除。

## 测试

- `PromptLibraryServiceTest`：mock DAO，覆盖 meta 组装、分页钳制、LIKE 转义、tags 拆分、preview 回退、详情/未找到。
- `PromptLibraryControllerTest`：standalone MockMvc + mock Service，覆盖 meta/list/detail/404。
- `PromptLibraryStaticPageTest`：断言 JS 已接入 `/api/prompts/meta` 且不再引用本地 JSON。
- `WebsiteApplicationTests`：测试上下文排除 `DataSourceAutoConfiguration`（不连库），新增 `@MockBean PromptLibraryDao`。
- 不连接远程 MySQL 跑单元测试；真实联调用本地启动 website + CDP 无头浏览器验证。

## 验证结果

- 导入后：`prompt_group` 10、`prompt_source` 6、`prompt_entry` 4409；分组分布与 JS 计算一致。
- 真实浏览器（Edge headless + CDP，连远程库）：加载 4409 条、48 卡/页；选大分类 266、选小分类 254、点分类卡片 931；加载更多 48→96；详情弹窗正常；无 JS 异常。
- `mvn -pl website -am test` 60 个用例全部通过。