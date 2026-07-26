# Imagetemplate 全量提示词库聚合设计

## 背景

仓库目前存在两套互不连通的提示词数据：

- `imagetemplate/src/main/resources/templates/image-prompt-templates.json`：47 条图片生成精选模板。
- `website/src/main/resources/static/prompt-console/data/prompt-library.json`：4409 条 Prompt Console 提示词，来自 6 个公开来源。

`ImagePromptTemplateService` 只加载第一份数据，因此 `imagetemplate` 页面和 `/api/image-templates` 只能看到 47 条。四千多条数据没有丢失，但未被该服务聚合。

## 目标

1. `imagetemplate` 默认展示全部 4409 条大库提示词，并保留现有 47 条精选模板。
2. 聚合结果保留全部 4456 行，不因内容重复而删除数据。
3. 继续支持精选模板的结构化变量渲染和现有图片生成能力。
4. 大库条目作为直接提示词进入 Prompt 编辑区，允许用户修改后生成图片。
5. 通过分页、摘要列表、详情按需加载和搜索防抖，避免一次传输 13MB JSON 或渲染四千多个 DOM 卡片。
6. 数据加载不完整时必须明确告警，不能静默退回 47 条。

## 非目标

1. 不修改 Prompt Console 的导入来源、授权信息或数据生成脚本。
2. 不删除大库中的重复内容。
3. 不把通用文本提示词自动改写为图片提示词。
4. 不新增数据库、搜索引擎、Redis 或前端构建工具。
5. 不要求运行 `website` 才能使用 `imagetemplate`。

## 方案选择

采用“构建时共享数据 + 运行时适配聚合”。

`imagetemplate/pom.xml` 增加一项只读 Maven resource，将：

```text
website/src/main/resources/static/prompt-console/data/prompt-library.json
```

在构建时复制到 `imagetemplate` 的 classpath：

```text
templates/prompt-console/prompt-library.json
```

源仓库仍只维护一份 12.9MB 大库文件；打包后的 `imagetemplate` jar 自带该文件，可以独立运行，不依赖 `website:8080`。

不采用运行时 HTTP 聚合，因为它会让 `imagetemplate` 的可用性依赖 `website`。不采用源码复制，因为两份大文件会产生数据漂移。

## 聚合模型

### 精选模板

现有 47 条保持原样，标记：

```text
sourceId=curated
sourceName=精选模板
templateKind=STRUCTURED 或 DIRECT
imageRelated=true
curated=true
```

现有 `direct-prompt` 分类映射为 `templateKind=DIRECT`，其他精选模板映射为 `STRUCTURED`。

### 大库模板

4409 条 `PromptLibraryEntry` 映射到 `ImagePromptTemplate`：

| 大库字段 | 聚合字段 |
| --- | --- |
| `id` | 参与生成稳定聚合 ID |
| `sourceId` | `sourceId` |
| `sourceName` | `sourceName` |
| `sourceUrl` | `sourceUrl` |
| `title` | `title` |
| `category` | `category` |
| `tags` | `tags` |
| `prompt` | `promptTemplate` |
| 固定空对象 | `jsonTemplate` |
| 固定值 | `templateKind=DIRECT` |
| 来源和分类判定 | `imageRelated` |
| 固定值 | `curated=false` |

大库条目的 `summary` 从 Prompt 的首段提取，去除多余空白并限制展示长度；完整 Prompt 只由详情接口返回。

### 图片相关判定

以下三个来源的条目固定为图片相关：

```text
youmind-awesome-gpt-image-2
freestylefly-awesome-gpt-image-2
evolink-awesome-gpt-image-2-prompts
```

其他来源如分类或标签命中图片、视觉、海报、摄影、UI、插画、Logo、电商、角色视觉等既定关键词，也标记为图片相关。现有数据中三个图片专用来源共有 957 条；最终“仅图片相关”数量还包括 47 条精选模板和其他来源中命中规则的条目，因此由服务启动时计算，不在代码中硬编码总数。

## 唯一 ID

大库当前有 4409 行、4400 个不同原始 ID，其中 9 个 ID 重复。聚合层不得覆盖任何一行。

每条大库记录生成：

```text
library-{sourceId}-{normalizedOriginalId}-{fingerprint}
```

`fingerprint` 使用 `sourceId + originalId + title + category + prompt` 的 SHA-256 短摘要。若完整指纹仍重复，则按源文件出现顺序追加 `-2`、`-3`。该规则：

- 保留全部条目；
- 避免 9 个重复原始 ID 互相覆盖；
- 在源内容不变时保持 ID 稳定；
- 不影响现有 47 条精选模板 ID。

## 后端组件

### PromptLibraryLoader

职责：

- 从 `templates/prompt-console/prompt-library.json` 读取顶层元数据、来源和 4409 条 entries；
- 校验根结构、来源、必需字段和条目数量；
- 返回原始大库对象和加载状态；
- 不负责搜索、分页或图片生成。

### ImagePromptTemplateAdapter

职责：

- 将大库 entry 映射为 `ImagePromptTemplate`；
- 生成稳定唯一 ID；
- 提取摘要；
- 判断 `imageRelated`；
- 保留来源元数据。

### ImagePromptTemplateService

职责：

- 聚合 47 条精选模板和适配后的 4409 条大库模板；
- 顺序固定为精选模板优先，大库保持源文件顺序；
- 提供过滤、分页、详情查找、分类统计和来源统计；
- DIRECT 模板渲染时直接返回原 Prompt，并在有导演备注时追加备注；
- STRUCTURED 模板继续沿用现有 JSON 变量渲染。

### LibraryAggregationStatus

记录：

```text
status=READY 或 DEGRADED
expectedCuratedCount=47
loadedCuratedCount
expectedLibraryCount=4409
loadedLibraryCount
total
message
```

大库加载失败时保留精选模板以便页面打开，但状态必须为 `DEGRADED`，接口和页面同时显示错误原因。健康接口仍表示 HTTP 进程存活；聚合完整性由模板元数据接口提供。

## API

### 模板分页列表

```text
GET /api/image-templates
```

参数：

```text
page       默认 1
size       默认 48，最大 100
keyword    可选
source     可选，curated 或六个 sourceId
category   可选
imageOnly  默认 false
```

响应：

```json
{
  "success": true,
  "total": 4456,
  "page": 1,
  "size": 48,
  "hasMore": true,
  "libraryStatus": "READY",
  "message": "",
  "templates": [
    {
      "id": "template-id",
      "title": "模板标题",
      "summary": "摘要",
      "category": "分类",
      "tags": ["标签"],
      "sourceId": "curated",
      "sourceName": "精选模板",
      "templateKind": "STRUCTURED",
      "imageRelated": true,
      "curated": true
    }
  ]
}
```

列表不返回 `jsonTemplate` 和完整 `promptTemplate`。

### 聚合元数据

```text
GET /api/image-templates/meta
```

返回聚合状态、总数、精选数量、大库数量、来源列表及计数、95 个大库分类与精选分类的合并统计。

### 模板详情

```text
GET /api/image-templates/{id}
```

保持现有路径，返回完整 `jsonTemplate`、`promptTemplate`、来源和类型字段。

### Prompt 与生成

```text
POST /api/image-templates/{id}/prompt
POST /api/image-templates/{id}/generate
```

保持现有路径和请求结构。DIRECT 模板默认使用完整 `promptTemplate`；用户编辑后的 `prompt` 仍优先用于生成。通用提示词允许进入生成接口，但前端显示“非图片专用，请先调整 Prompt”的提醒。

## 前端行为

### 灵感大厅

- 总数显示聚合后的 4456，而不是当前页长度。
- 来源使用 7 个横向筛选项：精选模板和 6 个大库来源。
- 95 个大库分类与精选分类放入可搜索或原生分类下拉框，不再渲染为 95 个横向标签。
- 增加“仅图片相关”开关，默认关闭，确保全部条目可见。
- 首次加载 48 条，底部“加载更多”每次追加下一页。
- 搜索输入防抖 300ms；修改来源、分类、关键词或图片开关时重置为第一页。
- 列表加载期间显示骨架状态；无结果时提供清除筛选操作。

### 模板选择

- 点击摘要卡片后请求详情接口。
- 详情加载成功后更新模板解构、Prompt 编导台和生成舱。
- 详情加载失败时保留当前模板，显示就地重试，不清空用户已经编辑的 Prompt。
- 精选模板显示“精选”徽章；其他模板显示来源名称。
- 非图片专用条目显示“通用提示词”提示，但不禁止进入后续场景。

### Prompt 编导台

- STRUCTURED 模板继续展示变量 JSON 和导演备注。
- DIRECT 模板隐藏或禁用无意义的变量 JSON，将完整 Prompt 直接填入最终 Prompt。
- DIRECT 模板的“生成 Prompt”操作只应用导演备注，不改写原文结构。

## 性能边界

- 服务启动时允许一次性解析约 13MB JSON，聚合数据保存在只读内存集合中。
- 列表接口只返回摘要 DTO，禁止返回完整 Prompt。
- `size` 最大为 100。
- 前端禁止一次请求或渲染全部 4456 条。
- 搜索在服务内存中执行，第一版不引入数据库或全文索引。
- 搜索范围包括标题、摘要、分类、标签、来源名和完整 Prompt；300ms 防抖避免每次按键都请求。

## 错误处理

- 大库资源缺失、JSON 非法或条目数异常：状态为 `DEGRADED`，页面显示预期值与实际值。
- 单条数据缺少标题或 Prompt：计入加载错误并在状态消息中给出数量，不静默当作完整成功。
- 页码、页大小非法：返回稳定的参数校验错误，页大小不得超过 100。
- 重复 ID：通过聚合 ID 规则解决，不丢弃条目。
- 详情 ID 不存在：沿用模板不存在错误。
- 生成失败：保持现有 Prompt、参数、选择状态和来源信息。

## 测试

### 服务测试

- 精选模板加载数量为 47。
- 大库加载数量为 4409。
- 聚合总数为 4456。
- 4456 条聚合 ID 全部唯一。
- 重复原始 ID 对应多个可访问详情。
- DIRECT 和 STRUCTURED 渲染行为分别正确。
- 来源、分类、关键词和 `imageOnly` 过滤正确。
- 分页默认 48、最大 100、`hasMore` 和总数正确。
- 大库缺失或非法时返回 `DEGRADED`，并保留精选模板。

### Controller 测试

- 列表只返回摘要字段，不返回完整 Prompt 和 JSON。
- 元数据接口返回来源、分类、计数和加载状态。
- 详情返回完整 Prompt。
- 非法分页参数返回稳定错误响应。

### 静态页面测试

- 来源筛选、分类下拉、图片开关、加载更多和聚合告警节点存在。
- JavaScript 包含 300ms 防抖、分页重置、详情按需加载和追加列表逻辑。
- 四场景和现有生成控件继续存在。

### 浏览器验收

- 首页显示总数 4456。
- 默认首屏只渲染 48 张模板卡片。
- 加载更多追加数据且不重复。
- 搜索、来源、分类和仅图片筛选组合工作正常。
- 第 4409 条大库记录可以通过搜索打开详情。
- 精选结构化模板和大库直接提示词都能进入对应 Prompt 流程。
- 桌面端和 390px 移动端无横向页面溢出。
- 大库状态异常时页面明确显示告警。

## 文档同步

实现时同步更新：

- 根 `AGENTS.md`
- 根 `README.md`
- `imagetemplate/AGENTS.md`
- `imagetemplate/README.md`

文档需要说明：

- 聚合总数、来源和构建时资源共享方式；
- 新增分页与元数据接口；
- `website` 的大库仍是唯一源文件；
- 更新大库后重新构建 `imagetemplate` 即可同步；
- 聚合加载状态和测试命令。
