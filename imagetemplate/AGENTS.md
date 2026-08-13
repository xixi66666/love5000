# AGENTS.md

## 健康检查

`GET /api/health` 不调用 OpenAI，返回
`{"success":true,"service":"imagetemplate"}`，供 `website` 的统一健康检查器聚合。

## 项目概述

`imagetemplate` 是 `love530` Maven 聚合工程中的图片提示词模板 Web 服务，项目路径：

```text
C:/Code/Java_Code/love5000/imagetemplate
```

核心功能：

- 提供 GPT Image 提示词模板库页面。
- 从 `templates/image-prompt-templates.json` 加载 47 个精选图片模板，其中包含 20 个 `direct-prompt` 直接提示词模板。
- 聚合构建时复制到 `templates/prompt-console/prompt-library.json` 的 4409 条 Prompt Console 提示词，总计 4456 条。
- 使用 `TemplateFunctionClassifier` 为每条模板确定一个一级功能和一个二级场景；分类只读取 ID、标题、原始分类、标签和低优先级来源默认值，不扫描完整 Prompt。
- 支持按一级功能、二级场景、来源、原始分类、关键词、仅图片相关组合筛选，并以默认 48、最大 100 的分页摘要返回。
- 支持将模板 JSON 和用户变量渲染为可直接传给图片生成接口的 prompt；直接提示词模板选中后使用 `promptTemplate`，并将非空用户变量追加到最终 prompt。
- 支持调用 OpenAI 图片生成接口，返回 base64 图片和 data URL。
- 前端提供模板选择、模板 JSON 与变量剧本编辑、自定义尺寸校验、prompt 复制、图片生成和下载能力，并使用“灵感大厅 → 模板解构 → Prompt 编导台 → 图片生成舱”四场景深色月夜 AI 创作工作台；背景使用本地 `media/moon-wallpaper.mp4` 月亮视频，前景采用深色玻璃拟态与冷蓝月银强调色，视频可见性优先；模板 JSON 进入编导台前必须校验为对象并同步到变量剧本，灵感大厅采用顶部搜索、左侧筛选和右侧结果网格。

技术栈：

- Java 8
- Maven
- Spring Boot 2.6.13
- Spring MVC / Spring Boot Starter Web
- Jackson JSON
- RestTemplate
- OpenAI Images API
- JUnit 5 / Spring Boot Test / AssertJ
- 原生 HTML / CSS / JavaScript

配置文件：

- `pom.xml`：Maven 模块依赖、Java 8 编译配置、Spring Boot 打包配置。
- `src/main/resources/application.yml`：端口、静态资源路径、OpenAI API、超时和代理配置。
- `src/main/resources/templates/image-prompt-templates.json`：47 条精选图片模板数据源。
- `../website/src/main/resources/static/prompt-console/data/prompt-library.json`：4409 条大库唯一源码，Maven 构建时复制到模块 classpath。

**关键**：该模块没有数据库，不依赖 MySQL、MyBatis、OSS 或 `common` 模块。运行时从两份 classpath JSON 聚合模板，打包后的 jar 不依赖 website 服务；图片生成通过 OpenAI API 完成。

**文档同步约定**：每次修改 `imagetemplate` 的模板数量、模板字段、API、图片生成参数、尺寸规则、OpenAI 配置、前端控件或测试方式时，必须同步更新本文件、`imagetemplate/README.md`，以及根目录 `AGENTS.md` / `README.md` 中相关内容。

## 开发命令

默认从仓库根目录执行：

```bash
cd C:/Code/Java_Code/love5000
```

安装并编译当前模块及其依赖：

```bash
mvn -pl imagetemplate -am clean install
```

启动服务：

```bash
mvn -pl imagetemplate -am spring-boot:run
```

服务地址：

```text
http://localhost:8082/
```

运行当前模块测试：

```bash
mvn -pl imagetemplate test
```

运行当前模块并同时构建父工程依赖：

```bash
mvn -pl imagetemplate -am test
```

打包当前模块：

```bash
mvn -pl imagetemplate -am clean package
```

跳过测试打包：

```bash
mvn -pl imagetemplate -am clean package -DskipTests
```

验证独立 jar 包含聚合大库：

```powershell
jar tf imagetemplate/target/imagetemplate-0.0.1-SNAPSHOT.jar | Select-String "templates/prompt-console/prompt-library.json"
```

检查依赖树：

```bash
mvn -pl imagetemplate dependency:tree
```

从模块目录启动：

```bash
cd C:/Code/Java_Code/love5000/imagetemplate
mvn spring-boot:run
```

带 OpenAI Key 启动：

```bash
set OPENAI_API_KEY=sk-your-key
mvn -pl imagetemplate -am spring-boot:run
```

带代理启动：

```bash
set OPENAI_API_KEY=sk-your-key
set OPENAI_PROXY_HOST=127.0.0.1
set OPENAI_PROXY_PORT=7890
mvn -pl imagetemplate -am spring-boot:run
```

## 项目结构

```text
imagetemplate/
├── pom.xml
├── AGENTS.md
└── src/
    ├── main/
    │   ├── java/com/example/imagetemplate/
    │   │   ├── ImageTemplateApplication.java
    │   │   ├── controller/
    │   │   │   └── ImagePromptTemplateController.java
    │   │   ├── dto/
    │   │   │   ├── ImageGenerationRequest.java
    │   │   │   ├── ImageGenerationResponse.java
    │   │   │   ├── PromptRenderRequest.java
    │   │   │   ├── PromptRenderResponse.java
    │   │   │   ├── ReferenceImageInput.java
    │   │   │   └── TemplateCategoryResponse.java
    │   │   ├── model/
    │   │   │   └── ImagePromptTemplate.java
    │   │   └── service/
    │   │       ├── ImagePromptTemplateService.java
    │   │       ├── OpenAiImageGenerationService.java
    │   │       ├── ImageGenerationException.java
    │   │       └── ImagePromptTemplateNotFoundException.java
    │   └── resources/
    │       ├── application.yml
    │       ├── static/
    │       │   ├── index.html
    │       │   ├── css/app.css
    │       │   └── js/app.js
    │       └── templates/
    │           └── image-prompt-templates.json
    └── test/java/com/example/imagetemplate/
        └── service/ImagePromptTemplateServiceTest.java
```

核心职责：

- `ImageTemplateApplication.java`：Spring Boot 启动类。
- `controller/ImagePromptTemplateController.java`：模板分页查询、聚合元数据、详情、prompt 渲染和图片生成 API。
- `service/PromptLibraryLoader.java`：加载并验证 4409 条 Prompt Console 大库，失败时返回可诊断降级结果。
- `service/ImagePromptTemplateAdapter.java`：将大库条目映射为 DIRECT 模板，生成稳定唯一 ID 和图片相关标记。
- `service/TemplateFunctionClassifier.java`：维护 15 个一级功能、二级场景和确定性匹配规则；“编程与技术开发”覆盖代码生成、重构、调试、测试、前后端、移动端、架构、数据库、DevOps、安全和自动化脚本。
- `service/ImagePromptTemplateService.java`：聚合 47 + 4409 条模板，负责过滤、分页、元数据、详情和两种 prompt 渲染。
- `service/OpenAiImageGenerationService.java`：读取 OpenAI 配置，调用 `/images/generations`，解析 `b64_json`。
- `model/ImagePromptTemplate.java`：模板模型，对应 JSON 中的 `id`、`title`、`categorySlug`、`jsonTemplate`、`promptTemplate` 等字段。
- `dto/*`：前后端请求和响应对象。
- `static/index.html`、`static/css/app.css`、`static/js/app.js`：深色月夜 AI 创作风格的四场景单视口前端，不使用 npm 构建；背景使用本地 `media/moon-wallpaper.mp4` 月亮视频，工作区以视频可见性优先：外层约 6% 冷蓝通明膜并仅做约 1px 轻微模糊，面板与卡片玻璃 40%-60% 不透明，搜索与 Prompt 输入保留较高不透明度以确保可读性；信息文字、说明、统计和标签使用月白/灰蓝层级，主按钮保留白字，交互状态使用月银蓝，错误态使用暗红玻璃；并保留 `prefers-reduced-motion` 装饰动画降级；流程导航在桌面端使用页面左侧居中的紧凑悬浮步骤器，900px 以下恢复为底部横向排列；灵感大厅顶部常驻搜索、仅图片开关和清除筛选，内容区左侧集中展示一级功能、二级场景及默认收起的来源/原始分类，右侧为结果网格，同时保留 300ms 防抖、加载更多和详情按需加载；模板解构 JSON 使用可编辑文本域，修改后进入 Prompt 编导台时校验并同步，变量剧本对所有模板类型保持可编辑；移动端改为单列自然滚动；流程导航切换场景时不得清空模板、Prompt、生成参数或结果状态。
- `templates/image-prompt-templates.json`：精选库数据源。
- `templates/prompt-console/prompt-library.json`：构建产物中的聚合大库，不在 imagetemplate 源码中维护。

## 配置约定

默认端口：

```yaml
server:
  port: 8082
```

静态资源路径：

```yaml
spring:
  web:
    resources:
      static-locations:
        - classpath:/static/
```

OpenAI 配置：

```yaml
openai:
  api-key: ${OPENAI_API_KEY:}
  base-url: ${OPENAI_BASE_URL:https://api.openai.com/v1}
  image-model: ${OPENAI_IMAGE_MODEL:gpt-image-2}
  connect-timeout-ms: ${OPENAI_CONNECT_TIMEOUT_MS:30000}
  read-timeout-ms: ${OPENAI_READ_TIMEOUT_MS:180000}
  proxy:
    type: ${OPENAI_PROXY_TYPE:HTTP}
    host: ${OPENAI_PROXY_HOST:}
    port: ${OPENAI_PROXY_PORT:0}
```

⚠️ **严重警告**：不要把真实 OpenAI API Key 写入 `application.yml`、前端 JS、测试文件或提交记录。服务端优先读取 `OPENAI_API_KEY`，页面也支持通过 `X-OpenAI-Api-Key` 临时传入用户 Key。

## API 约定

模板接口统一挂载在：

```text
/api/image-templates
```

当前接口：

```text
GET  /api/image-templates?page=1&size=48&keyword=&functionCategory=&functionScene=&source=&category=&imageOnly=false
GET  /api/image-templates/meta
GET  /api/image-templates/categories
GET  /api/image-templates/{id}
POST /api/image-templates/{id}/prompt
POST /api/image-templates/{id}/generate
```

列表接口只返回摘要字段，不返回完整 `promptTemplate` 和 `jsonTemplate`；`size` 最大为 100。详情接口返回完整模板。`/meta` 返回 4456 总量、15 个一级功能及二级场景计数、7 个来源、原始分类计数、图片相关数量和 `READY` / `DEGRADED` 聚合状态；功能树一级计数总和必须等于实际模板总数。加载不完整时页面必须显示预期数量、实际数量和错误原因。

列表查询参数：

```text
category
functionCategory
functionScene
keyword
```

渲染 prompt 请求示例：

```json
{
  "variables": {
    "product_name": "月光玻璃杯",
    "campaign_text": "新品首发"
  },
  "extraInstruction": "竖版 4:5，背景更干净。"
}
```

图片生成请求示例：

```json
{
  "variables": {
    "product_name": "月光玻璃杯"
  },
  "extraInstruction": "电商海报，干净背景。",
  "size": "3840x2160",
  "quality": "low",
  "outputFormat": "png",
  "background": "auto"
}
```

图片尺寸规则：

- `size` 使用 `宽x高` 格式，例如 `1024x1024`、`3840x2160`、`2160x3840`。
- 宽高必须是正整数，且都必须是 16 的倍数。
- 单边最大不超过 `3840px`。
- 最长边与最短边比例不能超过 `3:1`。
- 总像素必须在 `655360` 到 `8294400` 之间。
- `2560x1440` 及以上属于 2K/4K 实验尺寸，前端需要提示生成可能更慢或稳定性略低。
- 前端和后端必须保持同一套尺寸校验；非法尺寸要在真实调用 OpenAI 前拦截。

图片生成可选请求头：

```text
X-OpenAI-Api-Key: sk-your-key
```

响应结构必须包含明确的成功状态：

```json
{
  "success": true
}
```

错误响应由 controller 的异常处理器统一返回：

```json
{
  "success": false,
  "message": "error detail"
}
```

## 模板数据约定

精选模板文件：

```text
src/main/resources/templates/image-prompt-templates.json
```

精选模板每条必须包含：

```json
{
  "id": "commerce-product-poster",
  "title": "商品海报 / 电商图生成",
  "category": "商业与电商",
  "categorySlug": "commerce",
  "summary": "模板说明",
  "tags": ["海报", "电商"],
  "sourceUrl": "https://example.com/source",
  "jsonTemplate": {},
  "promptTemplate": "常规模板文本"
}
```

约定：

- `id` 必须全局唯一，使用小写英文、数字和连字符。
- `categorySlug` 使用小写英文，前端分类筛选依赖该字段。
- `jsonTemplate` 是结构化模板，字段名要稳定；用户变量通过同名 key 覆盖默认值。
- `promptTemplate` 是自然语言模板，用于展示和渲染 prompt。
- `direct-prompt` 分类用于直接提示词模板：`category` 固定为 `直接提示词`，`categorySlug` 固定为 `direct-prompt`，`jsonTemplate` 使用 `{}`，`promptTemplate` 必须是可直接用于图片生成的完整中文提示词，不使用 `<...>` 占位符；用户手工填写的非空变量会以“用户变量”段落追加到最终 prompt。
- 外部提示词来源优先使用 GitHub 仓库并保留 `sourceUrl`，当前已集成来源包括 `YouMind-OpenLab/awesome-gpt-image-2`、`EvoLinkAI/awesome-gpt-image-2-prompts`、`freestylefly/awesome-gpt-image-2`。
- 新增精选模板后必须更新 47 条精选数量和 4456 条聚合总量断言。

Prompt Console 大库唯一源码：

```text
../website/src/main/resources/static/prompt-console/data/prompt-library.json
```

- 当前包含 4409 条、6 个来源；构建时复制到 `templates/prompt-console/prompt-library.json`。
- 不删除重复内容；适配层用来源、原始 ID、内容指纹和出现次序生成稳定唯一 ID。
- 三个图片专用来源固定标记为图片相关，其他来源依据分类和标签关键词判定。
- 大库条目映射为 `templateKind=DIRECT`，非图片专用条目可编辑并生成，但前端必须提示。
- 大库缺失、非法或数量异常时返回 `DEGRADED`，不得静默假装 47 条就是完整数据。

## 代码规范

Java 命名：

- 类名使用 `UpperCamelCase`：`ImagePromptTemplateController`、`OpenAiImageGenerationService`。
- 方法名和变量名使用 `lowerCamelCase`：`renderPrompt`、`imageModel`。
- 常量使用 `UPPER_SNAKE_CASE`。
- 包名全小写：`com.example.imagetemplate`。
- Controller 类以 `Controller` 结尾。
- Service 类以 `Service` 结尾。
- Exception 类以 `Exception` 结尾。
- DTO 类以 `Request`、`Response` 结尾。

Spring 约定：

- 使用构造器注入，不使用字段注入。
- Controller 只处理 HTTP 入参、响应和异常映射。
- 模板加载、过滤、渲染逻辑放在 `ImagePromptTemplateService`。
- OpenAI 网络调用只放在 `OpenAiImageGenerationService`。
- 不在前端直接调用 OpenAI API；前端调用本模块 `/api/image-templates/{id}/generate`。
- 不引入数据库访问层；模板持久化仍以 JSON 文件为数据源。

前端约定：

- 不使用 npm、webpack、vite 等前端构建工具。
- 页面结构放在 `static/index.html`。
- 样式放在 `static/css/app.css`。
- 交互逻辑放在 `static/js/app.js`。
- API 路径保持相对路径；前端先请求 `/api/image-templates/meta`，再分页请求 `/api/image-templates`，点击卡片后请求详情。
- 禁止一次请求或渲染全部 4456 条；默认 48 条、加载更多追加下一页，搜索防抖固定为 300ms。
- 大库状态为 `DEGRADED` 时必须显示聚合告警，不能只显示 47 条而不解释。
- 前端保存 API Key 时只允许使用会话级或用户明确选择的浏览器存储，不写入源码。
- 四个场景固定为 `discover`、`deconstruct`、`direct`、`render`；场景导航只管理可见性、焦点、Dock 进度和无障碍状态。
- 桌面端保持单视口，移动端允许场景内容自然滚动；CSS 必须保留 `prefers-reduced-motion` 降级。

## 测试策略

当前测试框架：

- JUnit 5
- Spring Boot Test
- AssertJ
- Maven Surefire 2.22.2

运行测试：

```bash
mvn -pl imagetemplate test
```

跨父工程运行：

```bash
mvn -pl imagetemplate -am test
```

当前测试文件：

```text
src/test/java/com/example/imagetemplate/service/ImagePromptTemplateServiceTest.java
src/test/java/com/example/imagetemplate/service/PromptLibraryLoaderTest.java
src/test/java/com/example/imagetemplate/service/ImagePromptTemplateAdapterTest.java
src/test/java/com/example/imagetemplate/controller/ImagePromptTemplateControllerTest.java
src/test/java/com/example/imagetemplate/PromptLibraryPackagingTest.java
src/test/java/com/example/imagetemplate/service/OpenAiImageGenerationServiceTest.java
src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java
```

测试要求：

- 新增精选模板或更新大库时，更新 47、4409、4456 三层数量断言。
- 聚合测试必须覆盖所有 ID 唯一、精选优先、分页默认 48/最大 100、来源/分类/关键词/图片筛选、摘要不泄露完整 Prompt、详情和 `DEGRADED`。
- 新增分类时，测试必须覆盖 `categorySlug`。
- 新增 `direct-prompt` 模板时，测试必须覆盖分类名、分类 slug、模板数量、空 `jsonTemplate`、GitHub `sourceUrl` 和可直接使用的中文 `promptTemplate`。
- 修改 prompt 渲染规则时，必须覆盖变量替换、嵌套 JSON、列表字段和 `extraInstruction`。
- 修改图片尺寸规则时，必须覆盖合法 4K、非法格式、非 16 倍数、单边超限、像素过少、像素过多、比例超限，以及生成入口在触网前拦截非法尺寸。
- OpenAI 图片生成测试不得真实调用外部 API；需要 mock `RestTemplate` 或拆出可注入 HTTP 客户端后再测。
- 配置代理、超时或模型名逻辑变更时，至少补充服务构造或配置解析测试。

覆盖率目标：

- `ImagePromptTemplateService` 核心分支覆盖率不低于 80%。
- Controller 新增接口覆盖成功、模板不存在、外部生成失败三类场景。
- `OpenAiImageGenerationService` 新增逻辑必须覆盖无 API Key、OpenAI 错误响应、空图片数据响应。

项目当前没有 JaCoCo。若需要强制覆盖率，在父 `pom.xml` 统一引入 `jacoco-maven-plugin`，不要只在单模块单独配置。

## 提交前检查

提交前执行：

```bash
mvn -pl imagetemplate -am clean test
```

如果修改了前端页面，启动后手动访问：

```bash
mvn -pl imagetemplate -am spring-boot:run
```

访问：

```text
http://localhost:8082/
```

检查清单：

- **关键**：修改模板数量、模板字段、API、图片生成参数、尺寸规则、OpenAI 配置、前端控件或测试方式时，同步更新 `imagetemplate/AGENTS.md`、`imagetemplate/README.md` 和根文档。
- **关键**：不要提交 `target/`、IDE 缓存、真实 OpenAI API Key。
- **关键**：模板 JSON 必须保持合法 JSON，不能有注释或尾逗号。
- **关键**：4409 条大库只维护 website 唯一源码；禁止在 imagetemplate 源目录复制第二份大文件，更新后重新构建模块。
- **关键**：新增模板字段时，同步更新 `ImagePromptTemplate`、前端渲染和测试。
- **关键**：新增或修改图片尺寸选项时，必须同步更新前端校验、后端校验和 `OpenAiImageGenerationServiceTest`。
- **关键**：生成图片接口失败时必须返回可读 `message`，不要吞掉 OpenAI 错误。
- ⚠️ 不要让单元测试依赖真实 OpenAI API、真实代理或外网。
- ⚠️ 不要把生成图片的 base64 结果写入源码目录或提交到仓库。

## 常见任务指南

### 新增图片提示词模板

1. 修改 `src/main/resources/templates/image-prompt-templates.json`。
2. 确保 `id` 唯一、`categorySlug` 稳定。
3. 如新增分类，确认 `/api/image-templates/categories` 能统计到该分类。
4. 如更新公开大库，只修改 `../website/src/main/resources/static/prompt-console/data/prompt-library.json`。
5. 更新 `ImagePromptTemplateServiceTest` 中的精选数量、聚合总量或分类断言。
6. 运行：

```bash
mvn -pl imagetemplate test
```

### 修改 OpenAI 图片生成参数

1. 修改 `ImageGenerationRequest` 增加字段。
2. 修改 `OpenAiImageGenerationService` 将字段写入请求体。
3. 修改 `static/js/app.js` 增加前端控件和请求参数。
4. 修改 `ImageGenerationResponse`，仅在确实需要返回新字段时添加。
5. 如果修改 `size`，保持前后端规则一致，并补充尺寸边界测试。
6. 补充无 API Key、请求失败、响应缺字段测试。

### 调整前端交互

1. 页面结构改 `static/index.html`。
2. 样式改 `static/css/app.css`。
3. API 调用和状态管理改 `static/js/app.js`。
4. 启动模块手动验证模板列表、prompt 渲染、图片生成按钮状态。
