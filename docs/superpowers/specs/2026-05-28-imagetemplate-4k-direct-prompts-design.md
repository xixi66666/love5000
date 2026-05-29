# imagetemplate 4K 尺寸与直接提示词设计

## 背景

`imagetemplate` 当前图片生成尺寸只在前端提供 `1024x1024`、`1024x1536`、`1536x1024` 三个选项。当前接入的 `gpt-image-2` 网关支持更灵活的自定义尺寸，用户希望可以直接生成最高 4K 图片，而不是只做下载后放大。

项目当前模板库以 `image-prompt-templates.json` 为唯一数据源，每个模板包含结构化 `jsonTemplate` 和自然语言 `promptTemplate`。页面会把 `jsonTemplate` 展示给用户，并提供“变量 JSON”输入框覆盖同名字段后再渲染最终 prompt。

## 目标

1. 支持 `gpt-image-2` 合法自定义尺寸，包含常用 4K 横版和竖版尺寸。
2. 新增“直接提示词”模板分类，选中后可直接生成图片，不强迫用户填写变量 JSON。
3. 保留变量 JSON 能力，但把它定位为结构化模板的高级编辑能力。
4. 前后端都校验尺寸，避免非法参数传入图片生成接口。

## 非目标

1. 不新增数据库，模板仍存放在 classpath JSON 文件中。
2. 不真实调用 OpenAI 或第三方网关做自动测试。
3. 不实现图片后处理放大，因为本次目标是原生请求合法 4K 尺寸。
4. 不把 GitHub 外部仓库作为运行时依赖，提示词会整理后静态写入模板 JSON。

## 尺寸规则

前后端统一使用以下规则校验：

- 宽高必须是正整数。
- 宽和高都必须是 16 的倍数。
- 单边最大值为 `3840px`。
- 最长边与最短边比例不能超过 `3:1`。
- 总像素范围为 `655360` 到 `8294400`。
- `2560x1440` 及以上标记为实验范围，页面提醒生成速度、费用和稳定性可能受影响。

推荐尺寸直接放入前端下拉：

- `1024x1024`
- `2048x2048`
- `1536x1024`
- `1024x1536`
- `1920x1088`
- `2560x1440`
- `3840x2160`
- `1088x1920`
- `1440x2560`
- `2160x3840`

同时提供“自定义尺寸”输入，格式为 `宽x高`，例如 `1280x720`。

## 直接提示词分类

新增分类：

- `category`: `直接提示词`
- `categorySlug`: `direct-prompt`

这类模板的约定：

- `jsonTemplate` 使用 `{}`。
- `promptTemplate` 保存完整可直接使用的图片生成 prompt。
- 前端选中后自动把 `promptTemplate` 填入“生成结果”文本框。
- 变量 JSON 区域显示为非重点状态，或提示该模板无需变量 JSON。

提示词来源会从 GitHub 热门或相关提示词项目中整理，写入 `sourceUrl` 字段。优先来源包括：

- `ZeroLu/awesome-gpt-image`
- `ai-boost/awesome-prompts`
- `f/prompts.chat`

整理时只写入适合图片生成的 prompt，不引入项目无关的聊天、代码、文案类 prompt。

## 变量 JSON 的定位

变量 JSON 当前有实际作用：后端会把 `variables` 中的同名 key 覆盖到模板的 `jsonTemplate`，再把解析后的结构化字段拼成最终 prompt。它适合商品图、海报、角色一致性、信息图等参数较多的模板。

主要问题是交互成本高：用户需要理解 JSON 格式，并知道哪些 key 可以覆盖。对“直接提示词”模板而言，变量 JSON 基本没有收益。

因此本次保留变量 JSON，但前端根据模板类型调整体验：

- 普通结构化模板：继续显示 JSON 模板、变量 JSON 和 prompt 渲染按钮。
- 直接提示词模板：自动填入 prompt，不要求变量 JSON；变量 JSON 可以保留为空对象。

## 后端设计

新增尺寸校验逻辑，放在 `OpenAiImageGenerationService` 或独立私有方法中。生成接口接收 `size` 后先规范化，再校验：

- 空值默认 `1024x1024`。
- 合法值直接传给 OpenAI 请求体。
- 非法值抛出 `ImageGenerationException`，返回可读错误信息。

JSON 请求和 multipart 参考图请求共用同一套尺寸校验。

## 前端设计

`index.html` 中将尺寸选择改成：

- 推荐尺寸下拉。
- 自定义尺寸输入框。
- 实验尺寸提示文案。

`app.js` 中新增前端尺寸校验：

- 根据当前选择计算最终 `size`。
- 在点击生成前校验。
- 非法时在 `imageStatusLine` 显示错误，不发起请求。
- 合法自定义尺寸传给后端。

选中直接提示词模板时：

- `renderedPrompt` 直接填入 `promptTemplate`。
- `variablesInput` 设为 `{}`。
- 不需要用户点击“生成 Prompt”。

## 测试与验证

后端测试：

- `ImagePromptTemplateServiceTest` 更新模板数量和分类断言，覆盖 `direct-prompt`。
- 新增或扩展图片生成服务尺寸校验测试，覆盖合法 4K、非法非 16 倍数、非法超像素、非法比例。

前端验证：

- 启动 `imagetemplate` 后访问 `http://localhost:8082/`。
- 检查推荐尺寸下拉包含 4K 横版和竖版。
- 输入非法自定义尺寸时页面阻止提交并显示错误。
- 选择“直接提示词”分类模板时，prompt 自动填入且变量 JSON 为空。

必跑命令：

```bash
mvn -pl imagetemplate -am test
```
