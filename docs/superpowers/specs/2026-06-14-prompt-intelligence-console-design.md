# Prompt Intelligence Console 设计

## 背景

用户希望新增一个提示词页面，核心用途有两个：

1. 集中跳转到常用提示词网站和开源提示词库。
2. 输入简单场景后，通过多来源比对生成高质量提示词。

用户指定 `https://prompt123.cn/?utm_source=novatools.cn` 作为示例来源，并接受从 GitHub 上补充公开提示词库。页面应优美、有科技感，并优先做成可实际使用的工具台，而不是展示型落地页。

当前项目中 `website` 是个人主页和微服务入口模块，静态资源位于 `website/src/main/resources/static`。本设计将新页面放入 `website`，并在主页新增入口。实时比对需要后端代理能力，避免浏览器端被跨域、反爬和登录墙直接阻断。

## 目标

1. 新增一个 `Prompt Intelligence Console` 页面，作为提示词网站导航、来源状态查看和场景生成工作台。
2. 支持白名单提示词来源，包括用户指定的 Prompt123 和若干 GitHub 开源提示词库。
3. 后端提供受控抓取、缓存、摘要和降级能力，禁止任意 URL 抓取。
4. 用户输入简单场景后，页面输出多版本提示词，并展示来源对照依据。
5. 第一版无需真实调用大模型，通过规则化综合生成保证稳定可测。
6. 新增入口同步更新 `website` 主页导航、服务卡片样式和前端脚本。

## 非目标

1. 第一版不做全网搜索或开放 URL 抓取。
2. 第一版不绕过登录、付费墙、验证码或网站反爬限制。
3. 第一版不长期保存外部网站全文，只保存短摘要、状态、来源 URL 和缓存时间。
4. 第一版不调用 OpenAI、DeepSeek 或其他大模型生成提示词。
5. 第一版不复刻外部网站内容，不大段复制第三方提示词。
6. 第一版不把该页面加入 `imagetemplate` 模块；`imagetemplate` 继续负责图片模板库和图片生成。

## 默认白名单来源

第一批来源建议：

```text
Prompt123
https://prompt123.cn/?utm_source=novatools.cn

prompts.chat / f/awesome-chatgpt-prompts
https://github.com/f/awesome-chatgpt-prompts

ai-boost/awesome-prompts
https://github.com/ai-boost/awesome-prompts

YouMind-OpenLab/awesome-gpt-image-2
https://github.com/YouMind-OpenLab/awesome-gpt-image-2

freestylefly/awesome-gpt-image-2
https://github.com/freestylefly/awesome-gpt-image-2

EvoLinkAI/awesome-gpt-image-2-prompts
https://github.com/EvoLinkAI/awesome-gpt-image-2-prompts
```

来源分类：

- `general`: 通用角色、任务和文本提示词。
- `prompt-engineering`: 提示词工程方法、框架和最佳实践。
- `image-generation`: 图片生成提示词、视觉案例和负面限制。
- `website`: 外部提示词站点入口和实时抓取候选。

## 页面方案

采用用户确认的 `C 情报工作台`。

页面首屏即工具本体，采用双栏或三栏工作台布局：

```text
顶部：品牌 / 返回主页 / 刷新来源 / 缓存状态

左侧：来源雷达
  - 来源卡片
  - 来源分类
  - 跳转按钮
  - 实时抓取状态
  - 最近摘要

右侧：场景生成器
  - 场景输入
  - 用途选择
  - 语气 / 风格 / 输出长度
  - 多源比对生成按钮
  - 复制按钮

底部或右侧下半区：来源对照与生成结果
  - 每个来源提炼出的写法要点
  - 通用增强版
  - 图片生成版
  - 视频 / 分镜版
  - 商业海报版
  - 短提示词版
```

移动端布局改为纵向：

```text
来源状态摘要
场景输入
生成结果
来源对照
完整来源列表
```

## 视觉设计

整体风格：深色科技感、信息工作台、轻量情报系统。

设计约束：

- 背景使用黑色、石墨、深海军蓝中性色，不做单一蓝紫大面积渐变。
- 强调色使用青色、绿色、紫色和琥珀色，分别表示抓取中、可用、内置摘要和警告。
- 卡片圆角不超过 8px。
- 不使用可见说明文字来解释功能玩法；控件本身要足够清楚。
- 使用原生 HTML/CSS/JavaScript，不引入前端框架。
- 交互控件最小高度不低于 44px。
- 按钮、复制、刷新、跳转等操作需要明确 hover、focus 和 loading 状态。
- 支持 `prefers-reduced-motion`，减少扫描线、发光和过渡动画。

视觉模块：

- `source-card`: 来源卡片，展示状态点、标签、名称、摘要和跳转。
- `scenario-panel`: 场景输入面板。
- `mode-segment`: 用途分段控件。
- `prompt-result`: 输出结果块，包含标题、来源贡献和复制按钮。
- `source-insight-timeline`: 来源对照时间线。

## API 设计

新增接口位于 `website` 模块。

```text
GET  /api/prompt-sources
POST /api/prompt-sources/refresh
POST /api/prompts/compose
```

### GET /api/prompt-sources

返回所有白名单来源、缓存状态和摘要。

响应：

```json
{
  "success": true,
  "sources": [
    {
      "id": "prompt123",
      "name": "Prompt123",
      "url": "https://prompt123.cn/?utm_source=novatools.cn",
      "type": "website",
      "tags": ["提示词网站", "导航", "实时抓取候选"],
      "status": "cached|live|fallback|failed",
      "summary": "来源摘要",
      "lastFetchedAt": "2026-06-14T12:00:00+08:00",
      "message": ""
    }
  ]
}
```

### POST /api/prompt-sources/refresh

触发白名单来源刷新。请求可以指定来源 ID；不指定则刷新全部来源。

请求：

```json
{
  "sourceIds": ["prompt123", "awesome-chatgpt-prompts"]
}
```

响应至少包含：

```json
{
  "success": true,
  "sources": []
}
```

### POST /api/prompts/compose

根据场景、用途和来源摘要生成多版本提示词。

请求：

```json
{
  "scene": "雨夜城市街巷，想做一张电影感海报",
  "purpose": "image|video|poster|ui|character|copywriting",
  "tone": "cinematic",
  "length": "short|balanced|detailed",
  "sourceIds": ["prompt123", "awesome-chatgpt-prompts", "awesome-gpt-image-2"]
}
```

响应：

```json
{
  "success": true,
  "results": [
    {
      "type": "general",
      "title": "通用增强版",
      "prompt": "生成一张...",
      "sourceIds": ["prompt123", "awesome-prompts"],
      "sections": ["主体", "场景", "风格", "限制"]
    }
  ],
  "insights": [
    {
      "sourceId": "awesome-gpt-image-2",
      "points": ["补充镜头、光线、构图和负面限制"]
    }
  ]
}
```

错误响应：

```json
{
  "success": false,
  "message": "场景不能为空"
}
```

## 后端结构

建议新增包：

```text
website/src/main/java/com/example/website/prompt/
├── controller/
│   └── PromptConsoleController.java
├── dto/
│   ├── PromptSourceResponse.java
│   ├── PromptSourceRefreshRequest.java
│   ├── PromptComposeRequest.java
│   └── PromptComposeResponse.java
├── model/
│   ├── PromptSource.java
│   ├── PromptSourceSnapshot.java
│   └── PromptVariant.java
└── service/
    ├── PromptSourceRegistry.java
    ├── PromptSourceFetchService.java
    ├── PromptSourceSummaryService.java
    └── PromptComposeService.java
```

职责：

- `PromptSourceRegistry`: 管理白名单来源、默认摘要、分类和标签。
- `PromptSourceFetchService`: 只抓取白名单来源，设置超时、User-Agent、大小限制和错误处理。
- `PromptSourceSummaryService`: 将 HTML、Markdown 或纯文本压缩为短摘要和方法论要点。
- `PromptComposeService`: 基于场景、用途、来源摘要和规则模板生成多版本提示词。
- `PromptConsoleController`: 只负责 HTTP 入参、响应组装和错误映射。

## 抓取与降级

抓取规则：

1. 只允许 `PromptSourceRegistry` 中注册的来源 URL。
2. 禁止请求内网、文件协议、本机端口和用户提交的任意 URL。
3. 单来源超时建议 3 到 5 秒。
4. 单来源响应大小设置上限，避免抓取巨大页面。
5. GitHub 来源优先抓 README 或 raw markdown；普通网站抓 HTML 后提取标题、meta description、主要文本片段。
6. 抓取失败时使用内置摘要，状态为 `fallback`。
7. 所有来源失败时，`compose` 仍可基于内置方法论生成提示词。

缓存：

- 第一版可以使用内存缓存。
- 缓存字段包括来源 ID、摘要、状态、错误消息和最后抓取时间。
- 后续如需要持久化，再放入 `website/src/main/resources` 或本地 JSON，但第一版不需要。

## 生成规则

第一版使用规则化综合生成，不调用大模型。

基础结构：

```text
主体：从用户场景提取核心对象。
场景：扩展环境、时间、空间关系。
风格：根据用途和 tone 选择视觉或文本风格。
镜头 / 结构：图片和视频用途补充镜头、光线、构图、节奏。
质量要求：清晰度、可读性、真实感、一致性。
负面限制：不要乱码文字、水印、额外 logo、错乱肢体、无关元素。
输出规格：根据用途补充比例、用途说明或分镜格式。
```

输出版本：

- `general`: 通用增强版。
- `image`: 图片生成版。
- `video`: 视频 / 分镜版。
- `poster`: 商业海报版。
- `short`: 短提示词版。

根据 `purpose` 将最相关版本置顶，但保留其他版本供比较。

## 前端交互

新增静态资源建议：

```text
website/src/main/resources/static/prompt-console/index.html
website/src/main/resources/static/prompt-console/prompt-console.css
website/src/main/resources/static/prompt-console/prompt-console.js
```

交互流程：

1. 页面加载时请求 `/api/prompt-sources`。
2. 左侧渲染来源卡片，显示 `live`、`cached`、`fallback`、`failed` 状态。
3. 用户可点击来源卡片的跳转按钮打开原站。
4. 用户输入场景，选择用途、语气、长度和来源。
5. 点击生成后调用 `/api/prompts/compose`。
6. 结果区渲染多个提示词版本，每个版本提供复制按钮。
7. 来源对照区展示各来源贡献的提示词写法要点。
8. 刷新来源按钮调用 `/api/prompt-sources/refresh`，刷新期间禁用按钮并展示 loading。

页面文案边界：

- 抓取失败时显示：`实时抓取失败，已使用内置来源摘要。`
- 没有选择来源时显示：`将使用全部可用来源摘要生成。`
- 场景为空时显示：`先写一个简单场景，再生成提示词。`

## 主页入口

根据项目约定，新增微服务或独立工具入口时需要同步主页入口。

修改：

```text
website/src/main/resources/static/index.html
website/src/main/resources/static/css/style.css
website/src/main/resources/static/js/script.js
```

主页新增一个服务卡片：

```text
Prompt Console · 8080
href="/prompt-console/index.html"
data-health-url="/prompt-console/index.html"
```

顶部导航新增 `Prompt` 或 `Prompts` 链接。

## 错误处理

1. 来源抓取失败：不中断页面，使用内置摘要并标记 `fallback`。
2. 来源全部失败：`compose` 继续使用内置默认方法论。
3. 非白名单刷新请求：返回 `success: false` 和明确消息。
4. 场景为空：返回 `success: false` 和明确消息。
5. 外部响应过大或超时：记录来源状态，不向前端暴露长堆栈。
6. 前端请求失败：展示错误消息，并保留用户输入。

## 测试策略

Java 测试：

```bash
mvn -pl website -am test
```

覆盖：

1. `PromptSourceRegistry` 只返回白名单来源。
2. 非白名单来源刷新被拒绝。
3. `PromptSourceFetchService` 抓取失败时返回 fallback snapshot。
4. `PromptComposeService` 对空场景返回错误。
5. `PromptComposeService` 对有效场景返回多版本提示词。
6. 图片用途结果包含镜头、光线、构图和负面限制。
7. 视频用途结果包含分镜、运动、节奏和连续性。
8. Controller 响应至少包含 `success` 字段。

前端手动验证：

1. 访问 `http://localhost:8080/prompt-console/index.html`。
2. 桌面端检查双栏布局、来源卡片、生成结果和复制按钮。
3. 375px 宽度检查纵向布局无横向滚动、文字不重叠。
4. 断网或后端抓取失败时，页面显示 fallback 状态且仍可生成。
5. 主页入口和顶部导航可以打开页面。

## 风险与边界

1. 外部网站结构会变化，实时抓取只能作为增强能力，不能作为生成唯一依赖。
2. Prompt123 等普通网站可能存在跨域、反爬或登录限制，第一版只做受控抓取和降级。
3. GitHub raw 或 README 请求可能受网络限制，失败时必须使用内置摘要。
4. 规则化生成不如大模型灵活，但更稳定、可测、无需密钥。
5. 来源摘要必须保持方法论级别，避免大量复制第三方内容。

## 实施顺序建议

1. 新增后端 prompt 包和白名单来源注册。
2. 以 TDD 覆盖白名单、降级和 compose 生成逻辑。
3. 新增 API Controller。
4. 新增前端静态页面、样式和脚本。
5. 更新 `website` 主页入口、样式和健康检测。
6. 运行 `mvn -pl website -am test`。
7. 启动 `website` 并手动验证页面。
