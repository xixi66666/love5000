# imagetemplate

`imagetemplate` 是图片提示词模板 Web 服务，默认端口 `8082`。它从 classpath JSON 加载提示词模板，支持模板检索、prompt 渲染和 OpenAI 图片生成。

## 功能

- 模板库浏览、分类筛选和关键词检索。
- 结构化变量渲染 prompt。
- `direct-prompt` 直接提示词模板。
- 自定义图片尺寸校验。
- OpenAI Images API 调用，返回 base64/data URL 图片。
- 原生 HTML/CSS/JavaScript 单页前端，无 npm 构建。

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
GET  /api/image-templates
GET  /api/image-templates/categories
GET  /api/image-templates/{id}
POST /api/image-templates/{id}/prompt
POST /api/image-templates/{id}/generate
```

## 测试

```bash
mvn -pl imagetemplate -am test
```

OpenAI 图片生成测试不得真实调用外部 API。新增模板时必须同步更新模板数量、分类断言和前端展示。

## 文档维护

每次修改模板数量、模板字段、API、图片生成参数、尺寸规则、OpenAI 配置、前端控件或测试方式时，必须同步更新 `imagetemplate/AGENTS.md`、本 README，以及根目录 `AGENTS.md` / `README.md` 中相关内容。
