# lovestory

`lovestory` 是 `love530` 聚合工程中的恋爱相册 Web 应用，默认端口 `8081`。它提供相册静态页面、照片上传、留言板、小游戏页面和吉他视频卡片模块。

## 功能

- 照片上传、列表查询和删除。
- 留言板读取、新增和清空。
- 吉他视频上传、封面上传、列表展示和删除。
- 静态页面：相册首页、登录页、贪吃蛇、三消、井字棋等。
- 通过 `common` 模块使用阿里云 OSS。
- 使用 MySQL + MyBatis DAO/XML Mapper 保存照片和吉他视频记录。

## 运行

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
```

访问：

```text
http://localhost:8081/
```

## API

```text
POST   /api/photos/upload
GET    /api/photos
DELETE /api/photos/{id}

GET    /api/messages
POST   /api/messages
DELETE /api/messages

GET    /api/guitar-videos
POST   /api/guitar-videos/upload
POST   /api/guitar-videos/{id}/cover
DELETE /api/guitar-videos/{id}
```

## 测试

```bash
mvn -pl lovestory -am test
```

新增上传、数据库或 OSS 行为时，测试不得连接真实远程 MySQL 或真实 OSS。

## 文档维护

每次修改页面入口、API、上传字段、数据库字段、OSS 路径、静态资源、启动方式或测试方式时，必须同步更新 `lovestory/AGENTS.md`、本 README，以及根目录 `AGENTS.md` / `README.md` 中相关内容。
