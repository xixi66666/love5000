# website resources

本目录是 `website` 模块的 Spring Boot 资源目录，不再是独立 HomePage 模板项目。

## 内容

- `application.yml`：端口、数据库（默认腾讯云 `xixi` 库）、MyBatis、静态资源路径和 Python 子服务自动启动配置。
- `mapper/`：MyBatis XML Mapper。
- `db/`：数据库建表或示例 SQL。
- `static/index.html`：主页入口。
- `static/prompt-console/`：提示词控制台前端和静态提示词库，动效依赖本地 `static/js/vendor/gsap.min.js` 与 `ScrollTrigger.min.js`（均 3.12.5）。
- `static/css/`、`static/js/`、`static/img/`：主页资源；场景视频由首页显式引用外部 URL，并保留黑色渐变降级背景。四段片首尾不是同一镜头，`script.js` 会为当前场景动态创建 `.scene-video--loop` 补层，用 1000ms 交叉淡化盖住原生 `loop` 的硬切（不新增本地视频文件，也不改写 `index.html` 里的四个 URL）。

## 约定

- 静态页面引用资源时使用相对路径或站内路径，不使用本机绝对路径。
- 不修改 `target/classes/` 下的构建产物。
- 修改首页入口、服务卡片、提示词控制台或媒体素材时，同步更新 `website/AGENTS.md`、`website/README.md` 和根文档。
