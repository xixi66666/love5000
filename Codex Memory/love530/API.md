---
project: love530
type: api
module: all
updated: 2026-05-10
---

# API

新增接口响应至少包含：

```json
{
  "success": true
}
```

错误响应至少包含：

```json
{
  "success": false,
  "message": "error detail"
}
```

## common auth

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

认证能力位于 `common`，包含 BCrypt 密码哈希、Session 登录状态、`/api/auth` 控制器、`@AuthRequired` 和拦截器。具体持久化由业务模块适配。

## lovestory photos

统一挂载：

```text
/api/photos
```

接口：

```text
POST   /api/photos/upload
GET    /api/photos
DELETE /api/photos/{id}
```

上传字段：

```text
file        MultipartFile，必填
category    cat | girl | us，必填
description string，可选
```

允许图片后缀：

```text
jpg
jpeg
png
gif
webp
```

## lovestory messages

```text
GET    /api/messages
POST   /api/messages
DELETE /api/messages
```

## website blog

```text
GET  /api/blog/articles
GET  /api/blog/articles/{slug}
POST /api/blog/articles
GET  /api/blog/categories
GET  /api/blog/tags
```

博客后端按 Controller、Service、DAO、Model、DTO 分层，数据库访问使用 MyBatis DAO + XML Mapper。

## imagetemplate

统一挂载：

```text
/api/image-templates
```

接口：

```text
GET  /api/image-templates
GET  /api/image-templates/categories
GET  /api/image-templates/{id}
POST /api/image-templates/{id}/prompt
POST /api/image-templates/{id}/generate
```

列表查询参数：

```text
category
keyword
```

图片生成可选请求头：

```text
X-OpenAI-Api-Key: sk-your-key
```

OpenAI API Key 不得写入源码、前端 JS、测试文件或提交记录。

相关架构见 [[Architecture]]，测试要求见 [[Testing]]。
