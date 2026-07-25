# website

## 聚合健康检查

`GET /api/services/health` 使用统一 `ServiceHealthChecker` 并行检查
`lovestory`、`imagetemplate`、`guitar`、`python-a`、`quant-a` 和 `video`。
HTTP 200 表示聚合请求已执行，顶层 `healthy` 表示是否全部在线，`services`
保留配置顺序并包含状态码、耗时和安全失败摘要。默认连接/读取超时为 2000/3000ms。

健康检查聚焦测试：

```bash
mvn -pl website -am '-Dtest=ServiceHealthCheckerTest,ServiceHealthAggregatorTest,ServiceHealthControllerTest,*AutoStartRunnerTest' -DfailIfNoTests=false test
```

`website` 是 `love530` 聚合工程中的个人主页/展示站点 Web 服务，默认端口 `8080`。它同时负责提供博客、提示词控制台、静态首页入口，并在首页放出 Prompt Console 入口，以及 `python-a`、`quant-a`、`video` 三个独立 Python 子服务的自动启动和健康检查。

## 功能

- 个人主页静态站点。
- 单视口电影化服务主页：四段背景视频可切换，支持仅包含登录/注册账户操作的液态玻璃顶栏和 Deep Woods 场景配色。
- 博客 API 和前端页面。
- 提示词控制台和静态提示词库页面。
- 恋爱相册、图片模板、博客、Prompt Console、Guitar、`python-a`、`quant-a`、`video` 共 8 个入口及实时健康状态。
- Web、OSS、Nacos Discovery 示例代码。

## 运行

```bash
mvn -pl website -am spring-boot:run
```

访问：

```text
http://localhost:8080/
```

直接启动 `website` 时，会默认检查并拉起：

```text
http://127.0.0.1:5174/api/health  python-a
http://127.0.0.1:5175/api/health  quant-a
http://127.0.0.1:5176/api/health  video
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
  js/
  media/
  prompt-console/
python-a/
quant-a/
video/
```

首页保持原生 HTML / CSS / JavaScript 架构，不需要额外前端构建。四段远程视频在 1000ms 内交叉淡入淡出；背景资源不可用时自动显示黑色渐变降级背景。顶部只显示登录、注册，登录后切换为退出；不提供额外导航按钮或移动端汉堡菜单。服务 Dock 在桌面横向展示，在窄屏可滑动，并继续每 30 秒刷新一次服务状态。图片模板入口仍要求先通过站点 Session 登录。

## 测试

```bash
mvn -pl website -am test
```

修改 Python 子服务自动启动逻辑时，至少运行对应的 `PythonAAutoStartRunnerTest`、`QuantAAutoStartRunnerTest` 或 `VideoAutoStartRunnerTest`。测试必须关闭外部子进程自动启动。

## 文档维护

每次修改首页入口、提示词控制台、博客、自动启动配置、Python 子服务集成、端口、API、静态资源目录或测试方式时，必须同步更新 `website/AGENTS.md`、本 README，以及根目录 `AGENTS.md` / `README.md` 中相关内容。
