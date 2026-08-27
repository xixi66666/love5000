# website

## 聚合健康检查

`GET /api/services/health` 使用统一 `ServiceHealthChecker` 并行检查
`lovestory`、`imagetemplate`、`guitar`、`python-a` 和 `quant-a`。
HTTP 200 表示聚合请求已执行，顶层 `healthy` 表示是否全部在线，`services`
保留配置顺序并包含状态码、耗时和安全失败摘要。默认连接/读取超时为 2000/3000ms。

健康检查聚焦测试：

```bash
mvn -pl website -am '-Dtest=ServiceHealthCheckerTest,ServiceHealthAggregatorTest,ServiceHealthControllerTest,*AutoStartRunnerTest' -DfailIfNoTests=false test
```

`website` 是 `love530` 聚合工程中的个人主页/展示站点 Web 服务，默认端口 `8080`。它同时负责提供博客、提示词控制台、静态首页入口，并在首页放出 Prompt Console 入口，以及 `python-a`、`quant-a` 两个独立 Python 子服务的自动启动和健康检查。

## 功能

- 个人主页静态站点。
- 单视口电影化服务主页：四段背景视频可切换，支持仅包含登录/注册账户操作的液态玻璃顶栏和 Deep Woods 场景配色。
- 博客 API 和前端页面。
- 提示词控制台和静态提示词库页面。
- 恋爱相册、图片模板、博客、Prompt Console、Guitar、`python-a`、`quant-a` 共 7 个入口及实时健康状态。
- Web、OSS、Nacos Discovery 示例代码。

## 运行

```bash
mvn -pl website -am spring-boot:run
```

访问：

```text
http://localhost:8080/
```

数据库默认连接本机 `ycx_pms`，可通过 `WEBSITE_DB_URL`、`WEBSITE_DB_USERNAME`、`WEBSITE_DB_PASSWORD` 覆盖。仓库不提供远程数据库地址或真实密码默认值。

直接启动 `website` 时，会默认检查并拉起：

```text
http://127.0.0.1:5174/api/health  python-a
http://127.0.0.1:5175/api/health  quant-a
```

## 主要目录

```text
src/main/java/com/example/website/
  auth/         common 认证适配
  blog/         博客 API
  demos/        示例代码
  integration/  Python 子服务自动启动
  prompt/       提示词控制台后端
src/main/resources/static/
  index.html
  blog/
  css/
  img/
  js/
  prompt-console/
python-a/
quant-a/
```

首页保持原生 HTML / CSS / JavaScript 架构，不需要额外前端构建。四段远程视频在 1000ms 内交叉淡入淡出；背景资源不可用时自动显示黑色渐变降级背景。顶部只显示登录、注册，登录后切换为退出；不提供额外导航按钮或移动端汉堡菜单。服务 Dock 在桌面横向展示，在窄屏可滑动，并继续每 30 秒刷新一次服务状态。图片模板入口仍要求先通过站点 Session 登录。GSAP 动效库本地化在 `static/js/vendor/gsap.min.js`，用于首页入场动画与场景切换文案交叉淡化，`prefers-reduced-motion` 或加载失败时自动降级。首页 8 个服务卡片由 `script.js` 的 `setupServiceFx` 注入 WebGL canvas 渲染 GLSL 环境流光（SDF 圆角矩形柔化边框流光带 + 卡片内部宽幅流光与环境反光 + hover 指针光泽），并用弹簧物理驱动克制的卡片反馈（idle 呼吸波浪、hover 轻抬、点击压缩、健康状态 online 上跳脉冲）；四个视频场景分别映射暮霞、山湖、雪林、晨光草甸中等偏高饱和度色板，切换时 WebGL 颜色平滑插值，`prefers-reduced-motion`、WebGL 不可用或初始化失败时降级为随场景换色的 CSS hover。

## 测试

```bash
mvn -pl website -am test
node website/src/test/js/homepage-motion.test.js
```

修改 Python 子服务自动启动逻辑时，至少运行对应的 `PythonAAutoStartRunnerTest` 或 `QuantAAutoStartRunnerTest`。测试必须关闭外部子进程自动启动。

## 文档维护

每次修改首页入口、提示词控制台、博客、自动启动配置、Python 子服务集成、端口、API、静态资源目录或测试方式时，必须同步更新 `website/AGENTS.md`、本 README，以及根目录 `AGENTS.md` / `README.md` 中相关内容。
