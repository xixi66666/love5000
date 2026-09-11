# website resources

本目录是 `website` 模块的 Spring Boot 资源目录，不再是独立 HomePage 模板项目。

## 内容

- `application.yml`：端口、数据库（默认腾讯云 `xixi` 库）、MyBatis、静态资源路径和 Python 子服务自动启动配置。
- `mapper/`：MyBatis XML Mapper。
- `db/`：数据库建表或示例 SQL。
- `static/index.html`：主页入口。
- `static/prompt-console/`：提示词控制台前端和静态提示词库，动效依赖本地 `static/js/vendor/gsap.min.js` 与 `ScrollTrigger.min.js`（均 3.12.5）。
- `static/css/`、`static/js/`、`static/img/`：主页资源；场景视频和覆盖图当前由首页显式引用外部 URL，并保留黑色渐变降级背景。

## 约定

- 静态页面引用资源时使用相对路径或站内路径，不使用本机绝对路径。
- 不修改 `target/classes/` 下的构建产物。
- 修改首页入口、服务卡片、提示词控制台或媒体素材时，同步更新 `website/AGENTS.md`、`website/README.md` 和根文档。
