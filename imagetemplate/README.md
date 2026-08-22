# imagetemplate

健康检查：`GET /api/health`，返回顶层 `success=true` 和
`service="imagetemplate"`；该接口只检查 HTTP 进程存活，不调用 OpenAI。

`imagetemplate` 是图片提示词模板 Web 服务，默认端口 `8082`。它聚合 47 条精选图片模板和 Prompt Console 的 4409 条公开提示词，总计 4456 条，支持分页检索、prompt 渲染和 OpenAI 图片生成。

大库唯一源码位于 `website/src/main/resources/static/prompt-console/data/prompt-library.json`。Maven 构建时把它复制到 `templates/prompt-console/prompt-library.json`，因此打包后的 imagetemplate jar 可独立运行，不依赖 `website:8080`。

## 功能

- 4456 条聚合模板按“一级功能 + 二级场景”分页浏览；提供 15 个一级功能，其中“编程与技术开发”细分代码生成、调试、前后端、数据库、DevOps、安全等场景。
- 来源与原始分类保留在默认收起的高级筛选中，并可与功能分类、仅图片相关和关键词组合检索。
- 列表默认返回 48 条摘要，最多 100 条；点击卡片后按需加载完整 Prompt。
- 大库加载不完整时显示 `DEGRADED` 告警，不静默退回精选库。
- 结构化变量渲染 prompt；模板解构 JSON 可手工编辑、校验并同步到 Prompt 编导台变量剧本。
- `direct-prompt` 直接提示词模板，支持将手工变量追加到最终 Prompt。
- 自定义图片尺寸校验。
- OpenAI Images API 调用，返回 base64/data URL 图片。
- 原生 HTML/CSS/JavaScript 单页前端，无 npm 构建。
- 黑色调 AI 创作工作台：背景使用本地 `media/background.png` 图片，页面底色为黑色、图片保持原有色调，外层工作区约 6% 雾白膜并仅做约 1px 轻微模糊，面板与卡片为白色透明磨砂玻璃不遮挡背景，以视频可见性优先；信息文字与标签统一使用白色/浅灰层级，主按钮为深灰渐变保留白字；桌面端流程导航使用左侧居中的紧凑悬浮步骤器，窄屏恢复底部横排；灵感大厅采用顶部搜索、左侧分级筛选和右侧结果网格，后续保留模板解构 → Prompt 编导台 → 图片生成舱流程；模板 JSON 与变量剧本均可手工编辑。
- 底部液态玻璃 Dock 切换场景时保留已选模板、Prompt、生成参数和生成结果。
- 支持移动端自然滚动和 `prefers-reduced-motion` 动效降级。

## 运行

```bash
mvn -pl imagetemplate -am spring-boot:run
```

访问：

```text
http://localhost:8082/
```

带 OpenAI Key：

```bash
set OPENAI_API_KEY=sk-your-key
mvn -pl imagetemplate -am spring-boot:run
```

## API

```text
GET  /api/image-templates?page=1&size=48&keyword=&functionCategory=&functionScene=&source=&category=&imageOnly=false
GET  /api/image-templates/meta
GET  /api/image-templates/categories
GET  /api/image-templates/{id}
POST /api/image-templates/{id}/prompt
POST /api/image-templates/{id}/generate
```

列表接口只返回摘要，`size` 最大为 100；详情接口返回完整 `promptTemplate` 和 `jsonTemplate`。`/meta` 返回总量、15 个一级功能及二级场景计数、来源、原始分类及 `READY` / `DEGRADED` 聚合状态。每条模板由 `TemplateFunctionClassifier` 根据 ID、标题、原始分类和标签确定一个主功能与主场景，不扫描完整 Prompt。

## 测试

```bash
mvn -pl imagetemplate -am test
mvn -pl imagetemplate -am clean package -DskipTests
jar tf imagetemplate/target/imagetemplate-0.0.1-SNAPSHOT.jar | Select-String "templates/prompt-console/prompt-library.json"
```

OpenAI 图片生成测试不得真实调用外部 API。聚合测试固定验证 47 + 4409 = 4456、ID 唯一、两级功能分类计数、分页、兼容筛选、详情和降级状态。电影化页面静态契约由 `ImageTemplateHomepageStaticAssetsTest` 覆盖。

## 文档维护

每次修改模板数量、模板字段、API、图片生成参数、尺寸规则、OpenAI 配置、前端控件或测试方式时，必须同步更新 `imagetemplate/AGENTS.md`、本 README，以及根目录 `AGENTS.md` / `README.md` 中相关内容。
