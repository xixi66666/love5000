# website

## 聚合健康检查

`GET /api/services/health` 使用统一 `ServiceHealthChecker` 并行检查
`lovestory`、`imagetemplate`、`python-a`、`quant-a`、`scrapling-ui` 和 `skill-finder`。
HTTP 200 表示聚合请求已执行，顶层 `healthy` 表示是否全部在线，`services`
保留配置顺序并包含状态码、耗时和安全失败摘要。默认连接/读取超时为 2000/3000ms。

健康检查聚焦测试：

```bash
mvn -pl website -am '-Dtest=ServiceHealthCheckerTest,ServiceHealthAggregatorTest,ServiceHealthControllerTest,*AutoStartRunnerTest,ScraplingUiProcessManagerTest,ScraplingUiControllerTest,SkillFinderProcessManagerTest,SkillFinderControllerTest' -DfailIfNoTests=false test
```

`website` 是 `love530` 聚合工程中的个人主页/展示站点 Web 服务，默认端口 `8080`。它同时负责提供提示词控制台、静态首页入口，并在首页放出 Prompt Console 入口，以及 `python-a`、`quant-a` 两个独立 Python 子服务的自动启动和健康检查；`scrapling-ui` 可视化爬虫工作台和 `skill-finder` AI 趋势追踪站由首页按钮点击启动。

## 功能

- 个人主页静态站点。
- 单视口电影化服务主页：四段背景视频可切换，支持仅包含登录/注册账户操作的液态玻璃顶栏和 Deep Woods 场景配色。
- 提示词控制台和静态提示词库页面（深色影院式设计，本地 GSAP + ScrollTrigger 动效，`prefers-reduced-motion` 可降级）。
- 恋爱相册、图片模板、Prompt Console、`python-a`、`quant-a`、`scrapling-ui`、`skill-finder`、模型与视频共 8 个入口及实时健康状态。
- `scrapling-ui` 卡片是“点击启动”按钮：离线时点击拉起服务并在卡片内显示“启动中…”，就绪后自动打开工作台；若浏览器拦截新窗口则提示“已启动 · 点击打开”。在线时点击直接打开。
- `skill-finder` 卡片同样是“点击启动”按钮：离线时点击拉起服务并在卡片内显示“启动中…”，就绪后自动打开趋势站；若浏览器拦截新窗口则提示“已启动 · 点击打开”。在线时点击直接打开。
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

`skill-finder` 同样不随 `website` 启动自动拉起，由首页 Dock“Skill Finder”卡片点击启动：

```text
POST /api/services/skill-finder/start
GET  /api/services/skill-finder/status
```

启动成功后页面为 `http://127.0.0.1:5177/`（后端同端口托管前端构建产物，数据库与 `website` 共用腾讯云 `xixi` 库）。默认直接读取 `src/main/resources/application.yml` 的 `spring.datasource`，解析 `WEBSITE_DB_*` 环境变量，无需单独填写连接串；`DATABASE_URL` 环境变量或 `skill-finder/backend/.env` 可显式覆盖。原 `skill_finder` 的五张业务表数据已复制到 `xixi`，源库保留。`uv sync` 会安装 MySQL SHA-2 认证所需的 `cryptography`。首次接入只补建缺失业务表，集成测试使用独立测试库。首次使用需准备环境：

```bash
cd website/skill-finder/backend
uv sync

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
  integration/skillfinder/  skill-finder 点击启动与状态接口
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
skill-finder/
```

首页保持原生 HTML / CSS / JavaScript 架构，不需要额外前端构建。四段远程视频在 1000ms 内交叉淡入淡出；背景资源不可用时自动显示黑色渐变降级背景。顶部只显示登录、注册，登录后切换为退出；不提供额外导航按钮或移动端汉堡菜单。服务 Dock 在桌面以单行 8 列展示且 8 个入口一屏全部可见（列宽自适应收缩，不产生横向滚动），1180px 及以下才切换为可滑动的定宽列，并继续每 30 秒刷新一次服务状态。图片模板入口仍要求先通过站点 Session 登录。GSAP 动效库本地化在 `static/js/vendor/gsap.min.js`，用于首页入场动画与场景切换文案交叉淡化，`prefers-reduced-motion` 或加载失败时自动降级。首页 8 个服务卡片由 `script.js` 的 `setupServiceFx` 注入 WebGL canvas 渲染 GLSL 环境流光（SDF 圆角矩形柔化边框流光带 + 卡片内部宽幅流光与环境反光 + hover 指针光泽），并用弹簧物理驱动克制的卡片反馈（idle 呼吸波浪、hover 轻抬、点击压缩、健康状态 online 上跳脉冲）；四个视频场景分别映射暮霞、山湖、雪林、晨光草甸中等偏高饱和度色板，切换时 WebGL 颜色平滑插值，`prefers-reduced-motion`、WebGL 不可用或初始化失败时降级为随场景换色的 CSS hover。`scrapling-ui` 和 `skill-finder` 卡片离线时点击会进入“启动中”状态（橙色脉冲状态点 + 卡片内文案，不打开中间页面），就绪后自动打开对应工作台；若浏览器拦截新窗口，卡片显示“已启动 · 点击打开”。

全局 Python 模式：支持 Python 3.12+。在 `scrapling-ui/backend` 目录执行
`uv pip install --python <python完整路径> -r pyproject.toml` 和
`<python> -m playwright install chromium`，再将 `SCRAPLING_UI_COMMAND` 环境变量设为
该解释器完整路径，重启 `website` 所在终端或 IDE。显式 Python 配置直接执行
`<python> -m uvicorn`，不使用 `.venv`；未设置时仍保留 uv 模式。

首页场景内容在 `index.html` 的四个场景按钮上分别配置：`data-scene-title` 为主句、`data-scene-statement` 为副句、`data-scene-badge` 为上方提示，`data-scene-dock` 指定服务目录。01 Golden Hour 保持原诗句和八个入口；02 Still Water、03 Deep Woods、04 Quiet Dawn 各自使用暂定文案和独立的 `still-water-service-dock`、`deep-woods-service-dock`、`quiet-dawn-service-dock`，目录为空时不显示 Dock，也不显示指向隐藏目录的跳转链接；切回 01 恢复原服务。暂定主句分别为“让心事慢慢沉静”“把故事写进林间”“等晨光轻轻落下”，可独立替换为个人文案。新入口直接放入各自的 `service-grid` 并沿用 `service-card` 结构、健康检测和按需启动属性；四场景移除独立车窗覆盖图及其晃动动画，仅展示原风景视频，保留暗角、颗粒、四段视频动画和 1000ms 切换时序。

## 测试

```bash
mvn -pl website -am test
node website/src/test/js/homepage-motion.test.js
cd website/scrapling-ui/backend && uv run python -m unittest discover -s tests -v
cd website/skill-finder/backend && .venv/Scripts/python.exe -m pytest -q
cd website/skill-finder/frontend && npm run test -- --run
```

修改 Python 子服务自动启动逻辑时，至少运行对应的 `PythonAAutoStartRunnerTest` 或 `QuantAAutoStartRunnerTest`；修改 `scrapling-ui` 点击启动逻辑时运行 `ScraplingUiProcessManagerTest` 和 `ScraplingUiControllerTest`；修改 `skill-finder` 点击启动逻辑时运行 `SkillFinderProcessManagerTest` 和 `SkillFinderControllerTest`。测试必须关闭外部子进程自动启动，且不得启动真实浏览器或连接真实端口。

## 文档维护

每次修改首页入口、提示词控制台、自动启动配置、Python 子服务集成、端口、API、静态资源目录或测试方式时，必须同步更新 `website/AGENTS.md`、本 README，以及根目录 `AGENTS.md` / `README.md` 中相关内容。

## 本机模型与视频服务管理（2026-10-11）

首页 Dock 将「Qwen 本地模型」「视频操作台」「H3 音视频模型」合并为「模型与视频」，共8个入口。统一卡片进入 `/local-services/index.html`，首页每30秒检测管理页可访问性；三个服务仍在管理页分别操作，每15秒刷新各自状态，统一健康检查清单保留三项探测。

管理页借鉴 MotionSite 网站的排版与动效思路，采用独立设计的深色冰蓝工作台、Geist 字体与紧凑三服务网格；首屏背景使用 MotionSite 背景库的 Pulse 等离子光环静音循环视频，不复用其他操作台的风景素材。桌面三列、平板两列且 H3 横跨整行、手机单列；原有服务按钮、API 和15秒状态刷新保留。动效集中在 `static/local-services/motion.js`，复用本地 GSAP/ScrollTrigger 3.12.5，提供首屏入场、能力速览切换、文字渐显及几何视觉缩放/淡化。视频与海报位于 `static/local-services/media/`（10秒、1280×720、24fps、约2MB）；支持顶部暂停/播放、隐藏标签页及滚出背景区域自动暂停，视频失败保留 JPG 与 CSS 背景，`prefers-reduced-motion` 下不下载视频。背景播放不依赖 GSAP；动效库缺失时保留可操作页面，无需 npm 构建。

| 服务 | 本机目录 | 端口 | 管理操作 |
| --- | --- | --- | --- |
| Strata / Qwen3.8-Flash-Next IQ3_S | `F:/model/Strata` | 9999 | 只启动服务、加载模型、卸载模型、关闭服务 |
| AIMedia 视频操作台 | `D:/Code/Java_Code/AIMedia` | 8190 | 启动、关闭、打开操作台 |
| H3 / ComfyUI 生成引擎 | `D:/Code/Java_Code/AIMedia/ComfyUI` | 8189 | 启动引擎、释放模型内存、关闭引擎、打开 ComfyUI |

三个应用继续独立运行，不加入 Maven modules，不随 website 自动启动或关闭。`website.local-services` 配置本机目录、端口和180秒启动等待；目录可通过 `STRATA_HOME`、`AIMEDIA_HOME` 覆盖。入口仅适用于运行这些应用的 Windows 主机；使用 UU 远程操作主机上的浏览器也可管理。

API：`GET /api/services/local/{strata|aimedia|h3}/status`；同路径 `/health` 在在线时返回HTTP200、`success=true`和稳定的`service`标识，离线时HTTP503。`POST /api/services/local/{service}/{start|load|unload|stop}` 执行操作，只有Strata支持load，AIMedia不支持unload。修改请求需 `X-Love530-Local: 1`；仅允许回环地址、localhost/127.0.0.1/::1 Host与同源Origin，不能传入自定义命令或PID。统一 `/api/services/health` 清单在原五个服务后追加strata、aimedia、h3三个适配健康检查，共八项。

Strata以`--lazy`启动服务，第一条生成请求或「加载模型」按钮才加载权重；「卸载模型」保留API和权重文件。AIMedia通过已有GPU Python环境直接启动操作台后端，不在这里顺带启动H3。H3在提交生成任务后才加载权重，页面不把「引擎在线」或「权重已安装」谎报为「模型已加载」。释放调用ComfyUI `/free`，是异步请求，作用于该引擎缓存的模型，不删除权重和作品。视频队列或操作台作业忙碌时返回409，无法确认队列时拒绝释放/停止。启动生成任务前先卸载Qwen，避免两个大型模型争用内存和显存。

后端位于 `website/src/main/java/com/example/website/integration/local/`，停止脚本为classpath中的 `local-services/stop-service.ps1`。只停止命令同时匹配项目路径、脚本与端口的Python进程，拒绝停止占用端口的其他应用。日志在启动应用的工作目录中，文件名`love530-service.log`。新页面不需要npm构建。

验证：`mvn -pl website -am test -Dtest=LocalServicesManagerTest,LocalServicesControllerTest,ServiceHealthPropertiesTest,ServiceHealthAggregatorTest,ServiceHealthCheckerTest,ServiceHealthControllerTest,HomepageStaticAssetsTest,WebsiteApplicationTests -Dsurefire.failIfNoSpecifiedTests=false`；`node --check website/src/main/resources/static/local-services/app.js`；`node website/src/test/js/homepage-motion.test.js`。单元测试不加载真实模型、不生成视频、不连接真实数据库。

## Personal Agent Java 微服务（03 Deep Woods）

`personal-agent/` 与 `website/`、`lovestory/` 同级，是 Java8 + Spring Boot2.6.13 的 Maven 模块，已加入父 pom。默认仅监听 `127.0.0.1:5178`。原生前端与业务 API 在模块内；website 只提供03服务卡片、健康聚合及点击启动，不改01的8个入口或四个背景动画。

首次从仓库根目录执行 `mvn -pl personal-agent -am package -DskipTests`。可在IDEA运行 `com.example.personalagent.PersonalAgentApplication`，或执行 `java -jar personal-agent/target/personal-agent-0.0.1-SNAPSHOT.jar`。重启website后点击03个人Agent，启动器运行已构建jar（不自动Maven），验证 `success=true` + `service=personal-agent` 后打开；已在线则复用，陌生端口占用则拒绝。website启动/关闭不自动启停它。

入口支持从 `http://localhost:8080/` 跳转到 `http://127.0.0.1:5178/`：仅允许无Origin的首页（`/`、`/index.html`）顶层GET文档导航跨站进入，API及嵌入页面仍拒绝跨站请求，登录和CSRF校验保持。更新此校验后需重启个人Agent；通过首页启动jar时应先重新构建。

website接口：`POST /api/services/personal-agent/start`（返回 `{success,status,url}`）、`GET /api/services/personal-agent/status`；配置 `personal-agent.click-start.{enabled,work-dir,command,port,health-path,startup-timeout-seconds,log-to-console}`，默认目录 `personal-agent`，从仓库根或website启动都能定位；`PERSONAL_AGENT_COMMAND`可指定Java程序路径，默认java.home/bin/java。统一健康清单末尾追加个人Agent，保留已有顺序。

私人数据默认 `%LOCALAPPDATA%/Love530/PersonalAgent/`，可用 `PERSONAL_AGENT_DATA_DIR`覆盖；本地H2账本经MyBatis DAO+XML持久化，金额BigDecimal，不使用远程MySQL。`vault/`可用Obsidian直接打开；历史按录入年月存放，按事件时间/录入时间/UUID查看，手工修改受哈希保护。默认DeepSeek，可通过环境变量配置Key/模型/HTTPS地址，密钥不回显或进入Git。

功能包括对话、书籍与生活记录、长期记忆、想法行动、完整财务、事件触发复盘与网页未读提醒；接口及验证范围见 [personal-agent README](../personal-agent/README.md)。验证：`mvn -pl personal-agent -am test`、`mvn -pl website -am test`、`node --check personal-agent/src/main/resources/static/app.js`。不要在测试使用真实财富或模型密钥。

## Skill Finder 云端日报与视频

`website/skill-finder` 继续作为独立 FastAPI + Vue 微服务，以 love5000 版本为准同步到 `C:/Code/skills-finder`。云端采用 Docker + Nginx，入口 `https://49.232.128.132/skill-finder/`，日报审核 `/skill-finder/daily-reports`，后端仅监听回环 15177，本机开发仍用 5177。复用 xixi 原五张业务表，不重建共享库。

服务器北京时间 07:10 采集、07:30 制作（07:45 重试）、08:00 送达；当前 QQ 按用户要求暂不配置。成品包括文字日报、中文配音、字幕与竖屏视频，GitHub 当日 AI 项目不足十项时如实标注。DeepSeek 使用通用 `INTRO_API_KEY`、`INTRO_API_BASE`、`INTRO_MODEL` 私有配置，不把凭据写入 Git。

新增 API 前缀 `/api/v1/daily-reports`：GET 列表、GET `/{date}`、GET `/{date}/files/{filename}`；管理接口 POST `/generate`、POST `/{date}/review`、POST `/{date}/publish`；抖音登录 POST/GET `/publisher/login` 和受认证的 GET `/publisher/login/screen`。管理接口要求 X-Admin-Key，并只允许 HTTPS 或本机 SSH 隧道。发布必须绑定具体视频、口播和文案的人工批准；未登录不发布，结果不确定不自动重发。

`backend/app/daily/` 管理生成、媒体、审核摘要与发布适配；`backend/data/`、`.secrets/`、云端 `/var/lib/skill-finder/` 为私有运行数据，不提交。`deploy/` 维护 Docker、cron、Nginx 与 IP 证书续签；OpenClaw 在独立 Node 容器内仅监听回环 18789，QQ/抖音必须如实区分未配置、等待登录与已送达/已发布。完整部署、凭据边界与验证见 `website/skill-finder/docs/cloud-daily-report.md`（模块内为 `docs/cloud-daily-report.md`）。本机首页点击启动约定保持不变。
