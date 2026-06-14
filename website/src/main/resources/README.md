# website resources

本目录是 `website` 模块的 Spring Boot 资源目录，不再是独立 HomePage 模板项目。

## 内容

- `application.properties`：端口和历史示例配置。
- `application.yml`：数据库、MyBatis、静态资源路径和 Python 子服务自动启动配置。
- `mapper/`：MyBatis XML Mapper。
- `db/`：数据库建表或示例 SQL。
- `static/index.html`：主页入口。
- `static/blog/`：博客前端页面和资源。
- `static/prompt-console/`：提示词控制台前端和静态提示词库。
- `static/css/`、`static/js/`、`static/img/`、`static/svg/`、`static/soundeffects/`：主页资源。
- `static/media/`：主页视频、海报等媒体素材。

## 约定

- 静态页面引用资源时使用相对路径或站内路径，不使用本机绝对路径。
- 不修改 `target/classes/` 下的构建产物。
- 修改首页入口、服务卡片、提示词控制台或媒体素材时，同步更新 `website/AGENTS.md`、`website/README.md` 和根文档。
