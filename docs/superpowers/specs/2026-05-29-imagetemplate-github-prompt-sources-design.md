# imagetemplate GitHub 提示词来源集成设计

## 背景

用户补充了三个 GPT Image-2 提示词来源仓库：

- `YouMind-OpenLab/awesome-gpt-image-2`
- `EvoLinkAI/awesome-gpt-image-2-prompts`
- `freestylefly/awesome-gpt-image-2`

当前 `imagetemplate` 模板库有 29 个模板，其中 8 个属于 `direct-prompt` 直接提示词分类。项目仍以 `imagetemplate/src/main/resources/templates/image-prompt-templates.json` 作为唯一模板数据源。

## 目标

1. 从三个 GitHub 来源中精选可直接使用或适合结构化改写的提示词方向。
2. 扩充 `direct-prompt` 分类，让页面有更多选中即可生成的提示词。
3. 补充少量结构化模板，继续发挥变量 JSON 的价值。
4. 保留来源 URL，避免引入运行时网络依赖。

## 非目标

1. 不全量同步外部仓库。
2. 不新增自动抓取脚本。
3. 不复制大段外部内容；将来源方向整理为项目内中文模板。
4. 不修改图片生成接口、尺寸规则或前端布局。

## 集成方案

新增 18 个模板：

- 12 个 `direct-prompt` 直接提示词模板。
- 6 个结构化模板，分散到现有分类中。

模板数量从 29 增加到 47。`direct-prompt` 数量从 8 增加到 20。

来源映射：

- YouMind：适合大型多主题直接提示词，贡献创意、摄影、插画、壁纸等方向。
- EvoLinkAI：适合 CC0 方向的直接提示词和实用案例方向。
- freestylefly：适合工业模板和 Prompt-as-Code 风格，贡献结构化模板。

## 数据约定

`direct-prompt` 模板：

- `category`: `直接提示词`
- `categorySlug`: `direct-prompt`
- `jsonTemplate`: `{}`
- `promptTemplate`: 完整中文提示词，长度大于 80，不含 `<...>` 占位符。
- `sourceUrl`: 指向对应 GitHub 仓库。

结构化模板：

- 沿用现有分类。
- `jsonTemplate` 至少包含 5 个稳定字段。
- `promptTemplate` 用中文描述模板用途。
- `sourceUrl` 指向 `freestylefly/awesome-gpt-image-2`。

## 测试策略

更新 `ImagePromptTemplateServiceTest`：

- 总模板数断言改为 47。
- `direct-prompt` 模板数量断言改为 20。
- 新增测试覆盖 GitHub 新来源 URL 被加载。
- 新增测试覆盖结构化模板包含非空 `jsonTemplate` 和稳定分类。

运行：

```bash
mvn -pl imagetemplate -am test
```

## 文档同步

更新：

- 根目录 `AGENTS.md`
- `imagetemplate/AGENTS.md`

同步模板数量、直接提示词数量和外部来源约定。
