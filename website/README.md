# website

## 聚合健康检查

`GET /api/services/health` 使用统一 `ServiceHealthChecker` 并行检查
`lovestory`、`imagetemplate`、`python-a`、`quant-a` 和 `scrapling-ui`。
HTTP 200 表示聚合请求已执行，顶层 `healthy` 表示是否全部在线，`services`
保留配置顺序并包含状态码、耗时和安全失败摘要。默认连接/读取超时为 2000/3000ms。

健康检查聚焦测试：

```bash
mvn -pl website -am '-Dtest=ServiceHealthCheckerTest,ServiceHealthAggregatorTest,ServiceHealthControllerTest,*AutoStartRunnerTest,ScraplingUiProcessManagerTest,ScraplingUiControllerTest' -DfailIfNoTests=false test
```

`website` 是 `love530` 聚合工程中的个人主页/展示站点 Web 服务，默认端口 `8080`。它同时负责提供提示词控制台、静态首页入口，并在首页放出 Prompt Console 入口，以及 `python-a`、`quant-a` 两个独立 Python 子服务的自动启动和健康检查；`scrapling-ui` 可视化爬虫工作台由首页按钮点击启动。

## 功能

- 个人主页静态站点。
- 单视口电影化服务主页：四段背景视频可切换，支持仅包含登录/注册账户操作的液态玻璃顶栏和 Deep Woods 场景配色。
- 提示词控制台和静态提示词库页面（深色影院式设计，本地 GSAP + ScrollTrigger 动效，`prefers-reduced-motion` 可降级）。
- 恋爱相册、图片模板、Prompt Console、`python-a`、`quant-a`、`scrapling-ui` 共 6 个入口及实时健康状态。
- `scrapling-ui` 卡片是“点击启动”按钮：离线时点击拉起服务并自动打开工作台，在线时点击直接打开。
- Web、OSS、Nacos Discovery 示例代码。

## 运行

```bash
mvn -pl website -am spring-boot:run
```

访问：

```text
http://localhost:8080/
```

数据库默认连接腾讯云 `xixi` 库（`jdbc:mysql://49.232.128.132:3306/xixi`），可通过 `WEBSITE_DB_URL`、`WEBSITE_DB_USERNAME`、`WEBSITE_DB_PASSWORD` 覆盖。提示词库（`prompt_entry`/`prompt_source`/`prompt_group`）与认证（`auth_user`）共用该数据源；仓库不提供真实密码默认值，密码走环境变量。

提示词库接口（服务端分页/搜索 + 手动添加）：

```text
GET  /api/prompts/meta
GET  /api/prompts?keyword=&group=&category=&source=&status=&page=1&size=48
GET  /api/prompts/{id}
POST /api/prompts
```

页面 `prompt-console/index.html` 通过这些接口读取 MySQL 数据，不再直接 fetch 本地 JSON；"添加提示词"按钮弹出表单，提交后写入 `prompt_entry`（大分类自动推导，来源默认"手动添加"），成功后刷新列表并弹出新条目以便复制。当前添加接口不加鉴权。

直接启动 `website` 时，会默认检查并拉起：

```text
http://127.0.0.1:5174/api/health  python-a
http://127.0.0.1:5175/api/health  quant-a
```

`scrapling-ui` 不随 `website` 启动自动拉起，由首页 Dock“Scrapling 抓取工坊”卡片点击启动：

```text
POST /api/services/scrapling-ui/start
GET  /api/services/scrapling-ui/status
```

启动成功后页面为 `http://127.0.0.1:5176/`（后端同端口托管前端构建产物）。首次使用需准备环境：

```bash
cd website/scrapling-ui/backend
uv sync
uv run playwright install chromium

cd ../frontend
npm install
npm run build
```

## 主要目录

```text
src/main/java/com/example/website/
  auth/         common 认证适配
  demos/        示例代码
  integration/  Python 子服务自动启动（python-a / quant-a）
  integration/scrapling/  scrapling-ui 点击启动与状态接口
  prompt/       提示词控制台后端
src/main/resources/static/
  index.html
  css/
  img/
  js/
  prompt-console/
python-a/
quant-a/
scrapling-ui/
```

首页保持原生 HTML / CSS / JavaScript 架构，不需要额外前端构建。四段远程视频在 1000ms 内交叉淡入淡出；背景资源不可用时自动显示黑色渐变降级背景。顶部只显示登录、注册，登录后切换为退出；不提供额外导航按钮或移动端汉堡菜单。服务 Dock 在桌面横向展示，在窄屏可滑动，并继续每 30 秒刷新一次服务状态。图片模板入口仍要求先通过站点 Session 登录。GSAP 动效库本地化在 `static/js/vendor/gsap.min.js`，用于首页入场动画与场景切换文案交叉淡化，`prefers-reduced-motion` 或加载失败时自动降级。首页 6 个服务卡片由 `script.js` 的 `setupServiceFx` 注入 WebGL canvas 渲染 GLSL 环境流光（SDF 圆角矩形柔化边框流光带 + 卡片内部宽幅流光与环境反光 + hover 指针光泽），并用弹簧物理驱动克制的卡片反馈（idle 呼吸波浪、hover 轻抬、点击压缩、健康状态 online 上跳脉冲）；四个视频场景分别映射暮霞、山湖、雪林、晨光草甸中等偏高饱和度色板，切换时 WebGL 颜色平滑插值，`prefers-reduced-motion`、WebGL 不可用或初始化失败时降级为随场景换色的 CSS hover。`scrapling-ui` 卡片离线时点击会进入“启动中”状态（橙色脉冲状态点），调用启动接口成功后自动打开工作台。

## 测试

```bash
mvn -pl website -am test
node website/src/test/js/homepage-motion.test.js
cd website/scrapling-ui/backend && uv run python -m unittest discover -s tests -v
```

修改 Python 子服务自动启动逻辑时，至少运行对应的 `PythonAAutoStartRunnerTest` 或 `QuantAAutoStartRunnerTest`；修改 `scrapling-ui` 点击启动逻辑时运行 `ScraplingUiProcessManagerTest` 和 `ScraplingUiControllerTest`。测试必须关闭外部子进程自动启动，且不得启动真实浏览器。

## 文档维护

每次修改首页入口、提示词控制台、自动启动配置、Python 子服务集成、端口、API、静态资源目录或测试方式时，必须同步更新 `website/AGENTS.md`、本 README，以及根目录 `AGENTS.md` / `README.md` 中相关内容。
