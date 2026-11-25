# website

> 模型配置已统一：模型目录、密钥和各服务原配置只从项目根目录 `model.properties` 读取（模板 `model.properties.example`）。本文中出现的模型环境变量、`deepseek.local.json`、`INTRO_*` / `MIMO_*` 示例仅作历史说明，不再生效。


## 聚合健康检查

`GET /api/services/health` 返回最近一次并行巡检结果。默认在启动时巡检一次，之后间隔 30 分钟。默认 11 个目标包括：
`lovestory`、`imagetemplate`、`python-a`、`quant-a`、`scrapling-ui`、`skill-finder`、
经 `website` 适配的 `strata`、`aimedia`、`h3`（`/api/services/local/{service}/health`），
以及 `personal-agent`、`lottery`；顺序以 `src/main/resources/application.yml` 的
`website.service-health.services` 为准。HTTP 200 表示成功返回聚合响应。
顶层 `success=true` 表示巡检已生成汇总，即使全部目标离线仍可为 true，`healthy` 表示是否全部在线，`services` 包含状态码、耗时和失败摘要。
单个目标在 HTTP 2xx 且响应顶层布尔值 `success=true` 时判定为健康。默认连接超时 2000ms，读取超时 3000ms。

健康检查聚焦测试：

```bash
mvn -pl website -am '-Dtest=ServiceHealthCheckerTest,ServiceHealthAggregatorTest,ServiceHealthControllerTest,*AutoStartRunnerTest,ScraplingUiProcessManagerTest,ScraplingUiControllerTest,SkillFinderProcessManagerTest,SkillFinderControllerTest' -DfailIfNoTests=false test
```

`website` 是 `love530` 聚合工程中的个人主页/展示站点 Web 服务，默认端口 `8080`。它同时负责提供提示词控制台、静态首页入口，并在首页放出 Prompt Console 入口，以及 `python-a`、`quant-a` 两个独立 Python 子服务的自动启动和健康检查；`scrapling-ui`、`skill-finder`、`lottery` 和 03 Deep Woods 的 `personal-agent` 由首页按钮点击启动。

## 功能

- 个人主页静态站点。
- 单视口电影化服务主页：四段背景视频可切换，支持仅包含登录/注册账户操作的液态玻璃顶栏和 Deep Woods 场景配色。
- 提示词控制台和静态提示词库页面（深色影院式设计，本地 GSAP + ScrollTrigger 动效，`prefers-reduced-motion` 可降级）。
- 01 Golden Hour 展示恋爱相册、图片模板、Prompt Console、`python-a`、`quant-a`、`scrapling-ui`、`skill-finder`、模型与视频、`lottery` 共 9 个入口及实时健康状态；03 Deep Woods 展示“个人资料库”（`personal-agent`，5178）。
- `scrapling-ui` 卡片是“点击启动”按钮：离线时点击拉起服务并在卡片内显示“启动中…”，就绪后自动打开工作台；若浏览器拦截新窗口则提示“已启动 · 点击打开”。在线时点击直接打开。
- `skill-finder` 卡片同样是“点击启动”按钮：离线时点击拉起服务并在卡片内显示“启动中…”，就绪后自动打开趋势站；若浏览器拦截新窗口则提示“已启动 · 点击打开”。在线时点击直接打开。
- `lottery` 卡片和 03 Deep Woods 的“个人资料库”卡片也由首页点击启动，接口分别为 `POST /api/services/lottery/start` 与 `POST /api/services/personal-agent/start`，启动表现与上面两张卡片一致。
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
  integration/  Python 子服务自动启动（python-a / quant-a）与健康聚合
  integration/health/  ServiceHealthChecker、聚合器与 /api/services/health
  integration/scrapling/  scrapling-ui 点击启动与状态接口
  integration/skillfinder/  skill-finder 点击启动与状态接口
  integration/lottery/  lottery 点击启动与状态接口
  integration/personalagent/  personal-agent 点击启动与状态接口
  integration/local/  strata / aimedia / h3 本机健康适配与启停
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
lottery/
```

首页保持原生 HTML / CSS / JavaScript 架构，不需要额外前端构建。四段远程视频在 1000ms 内交叉淡入淡出；背景资源不可用时自动显示黑色渐变降级背景。顶部只显示登录、注册，登录后切换为退出；不提供额外导航按钮或移动端汉堡菜单。服务 Dock 在桌面以单行 9 列展示且 9 个入口一屏全部可见（列宽自适应收缩，不产生横向滚动），1180px 及以下才切换为可滑动的定宽列，并继续每 30 分钟读取缓存并刷新一次服务状态。图片模板入口仍要求先通过站点 Session 登录。GSAP 动效库本地化在 `static/js/vendor/gsap.min.js`，用于首页入场动画与场景切换文案交叉淡化，`prefers-reduced-motion` 或加载失败时自动降级。首页 9 个服务卡片由 `script.js` 的 `setupServiceFx` 注入 WebGL canvas 渲染 GLSL 环境流光（SDF 圆角矩形柔化边框流光带 + 卡片内部宽幅流光与环境反光 + hover 指针光泽），并用弹簧物理驱动克制的卡片反馈（idle 呼吸波浪、hover 轻抬、点击压缩、健康状态 online 上跳脉冲）；四个视频场景分别映射暮霞、山湖、雪林、晨光草甸中等偏高饱和度色板，切换时 WebGL 颜色平滑插值，`prefers-reduced-motion`、WebGL 不可用或初始化失败时降级为随场景换色的 CSS hover。`scrapling-ui`、`skill-finder`、`lottery` 卡片以及 03 Deep Woods 的“个人资料库”卡片离线时点击会进入“启动中”状态（橙色脉冲状态点 + 卡片内文案，不打开中间页面），就绪后自动打开对应工作台；若浏览器拦截新窗口，卡片显示“已启动 · 点击打开”。

全局 Python 模式：支持 Python 3.12+。在 `scrapling-ui/backend` 目录执行
`uv pip install --python <python完整路径> -r pyproject.toml` 和
`<python> -m playwright install chromium`，再将 `SCRAPLING_UI_COMMAND` 环境变量设为
该解释器完整路径，重启 `website` 所在终端或 IDE。显式 Python 配置直接执行
`<python> -m uvicorn`，不使用 `.venv`；未设置时仍保留 uv 模式。

首页场景内容在 `index.html` 的四个场景按钮上分别配置：`data-scene-title` 为主句、`data-scene-statement` 为副句、`data-scene-badge` 为上方提示，`data-scene-dock` 指定服务目录。01 Golden Hour 保持原诗句和九个入口；03 Deep Woods 的 `deep-woods-service-dock` 展示“个人资料库”（5178，点击启动）；02 Still Water、04 Quiet Dawn 各自使用暂定文案和独立目录，目录为空时不显示 Dock，也不显示指向隐藏目录的跳转链接；切回 01 恢复原服务。暂定主句分别为“让心事慢慢沉静”“把故事写进林间”“等晨光轻轻落下”，可独立替换为个人文案。新入口直接放入各自的 `service-grid` 并沿用 `service-card` 结构、健康检测和按需启动属性；四场景移除独立车窗覆盖图及其晃动动画，仅展示原风景视频，保留暗角、颗粒、四段视频动画和 1000ms 切换时序。

四段场景片均为 10.04 秒且首尾不是同一个镜头，原生 `loop` 会在片尾停帧再跳回第一帧，观感就是“突然顿住 + 硬切”。`setupVideoSwitcher` 因此为当前场景额外创建一层同源补层（`.scene-video--loop`，`static/js` 动态创建，不写进 `index.html`），在原视频进入最后 1 秒时从第一帧起播并接管画面，用 1000ms 交叉淡化完成循环；原视频在自己不可见之后才回到片头。

**这里有一个必须守住的不变量**：补层与原视频是上下叠放，只能让上层补层改变 `opacity`，下层原视频始终保持不透明。两层同时半透明时，合成覆盖率是 `上层 + 下层 × (1 − 上层)`，中点只有 75%，会透出深色背景——实测亮度从 Y=74.5 掉到 66.2，观感就是每 9 秒“突然黑一下”。所以不要给原视频加淡出类，`stopLoop()` 也只收掉补层的可见状态。

补层默认 `paused + preload="none"`、不进入无障碍树，`video.play()` 被拒绝或片段过短时自动退回原生 `loop`，`prefers-reduced-motion` 下按 1ms 切换。缓推镜头（`ken-burns`）在接管时同步相位，避免淡化过程中出现缩放抖动。场景切换会先等新视频 `readyState ≥ 2`（最多 2000ms）再淡入，否则旧画面已经淡出、新视频还没出帧，中间只剩背景。回归用例为 `node website/src/test/js/homepage-video-loop.test.js`。

## 测试

```bash
mvn -pl website -am test
node website/src/test/js/homepage-motion.test.js
node website/src/test/js/homepage-video-loop.test.js
cd website/scrapling-ui/backend && uv run python -m unittest discover -s tests -v
cd website/skill-finder/backend && .venv/Scripts/python.exe -m pytest -q
cd website/skill-finder/frontend && npm run test -- --run
```

### 一键离线回归

从仓库根目录运行以下命令。若当前在其他目录，传入脚本的绝对路径。

```bash
python scripts/run-regression.py
```

脚本依次运行 `website/src/test/js` 下的四份 Node 测试（首页 `homepage-motion.test.js`、`homepage-video-loop.test.js`、`service-health.test.js` 与提示词 `prompt-console/prompt-category-groups.test.js`）、`python -m unittest discover -s website/model-routing`、`python scripts/sync-model-picker.py --check`、`python scripts/sync-model-routing.py --check`，最后执行 Maven 离线白名单测试 `mvn -o -pl website,personal-agent -am -Dtest=ServiceHealthCheckerTest,ServiceHealthAggregatorTest,ServiceHealthControllerTest,ModelRoutingServiceTest,KnowledgeIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false test`。

两个 `--check` 只读比较部署副本。Java 测试使用 Maven 本地仓库以及测试替身。全部通过返回 0，检查失败返回 1，只有运行工具缺失时返回 2。

可使用[本地服务诊断台](../tools/service-doctor/README.md)查询聚合接口和各服务的健康接口。

修改 Python 子服务自动启动逻辑时，至少运行对应的 `PythonAAutoStartRunnerTest` 或 `QuantAAutoStartRunnerTest`；修改 `scrapling-ui` 点击启动逻辑时运行 `ScraplingUiProcessManagerTest` 和 `ScraplingUiControllerTest`；修改 `skill-finder` 点击启动逻辑时运行 `SkillFinderProcessManagerTest` 和 `SkillFinderControllerTest`。测试必须关闭外部子进程自动启动，且不得启动真实浏览器或连接真实端口。

## 文档维护

每次修改首页入口、提示词控制台、自动启动配置、Python 子服务集成、端口、API、静态资源目录或测试方式时，必须同步更新 `website/AGENTS.md`、本 README，以及根目录 `AGENTS.md` / `README.md` 中相关内容。

## 本机模型与视频服务管理（2026-10-11）

首页 Dock 将「Qwen 本地模型」「视频操作台」「H3 音视频模型」合并为「模型与视频」，共8个入口。统一卡片进入 `/local-services/index.html`，首页每30分钟检测管理页可访问性；三个服务仍在管理页分别操作，每30分钟刷新各自状态，统一健康检查清单保留三项探测。

管理页借鉴 MotionSite 网站的排版与动效思路，采用独立设计的深色冰蓝工作台、Geist 字体与紧凑三服务网格；首屏背景使用 MotionSite 背景库的 Pulse 等离子光环静音循环视频，不复用其他操作台的风景素材。桌面三列、平板两列且 H3 横跨整行、手机单列；原有服务按钮、API 和30分钟状态刷新保留。动效集中在 `static/local-services/motion.js`，复用本地 GSAP/ScrollTrigger 3.12.5，提供首屏入场、能力速览切换、文字渐显及几何视觉缩放/淡化。视频与海报位于 `static/local-services/media/`（10秒、1280×720、24fps、约2MB）；支持顶部暂停/播放、隐藏标签页及滚出背景区域自动暂停，视频失败保留 JPG 与 CSS 背景，`prefers-reduced-motion` 下不下载视频。背景播放不依赖 GSAP；动效库缺失时保留可操作页面，无需 npm 构建。

| 服务 | 本机目录 | 端口 | 管理操作 |
| --- | --- | --- | --- |
| Strata / Qwen3.8-Flash-Next IQ3_S | `F:/model/Strata` | 9999 | 只启动服务、加载模型、卸载模型、关闭服务 |
| AIMedia 视频操作台 | `D:/Code/Java_Code/AIMedia` | 8190 | 启动、关闭、打开操作台 |
| H3 / ComfyUI 生成引擎 | `D:/Code/Java_Code/AIMedia/ComfyUI` | 8189 | 启动引擎、释放模型内存、关闭引擎、打开 ComfyUI |

三个应用继续独立运行，不加入 Maven modules，不随 website 自动启动或关闭。`website.local-services` 配置本机目录、端口和180秒启动等待；目录可通过 `STRATA_HOME`、`AIMEDIA_HOME` 覆盖。入口仅适用于运行这些应用的 Windows 主机；使用 UU 远程操作主机上的浏览器也可管理。

API：`GET /api/services/local/{strata|aimedia|h3}/status`；同路径 `/health` 在在线时返回HTTP200、`success=true`和稳定的`service`标识，离线时HTTP503。`POST /api/services/local/{service}/{start|load|unload|stop}` 执行操作，只有Strata支持load，AIMedia不支持unload。修改请求需 `X-Love530-Local: 1`；仅允许回环地址、localhost/127.0.0.1/::1 Host与同源Origin，不能传入自定义命令或PID。统一 `/api/services/health` 默认检查 11 个目标，包括上述三个本机适配与八个独立服务。

Strata以`--lazy`启动服务，第一条生成请求或「加载模型」按钮才加载权重；「卸载模型」保留API和权重文件。AIMedia通过已有GPU Python环境直接启动操作台后端，不在这里顺带启动H3。H3在提交生成任务后才加载权重，页面不把「引擎在线」或「权重已安装」谎报为「模型已加载」。释放调用ComfyUI `/free`，是异步请求，作用于该引擎缓存的模型，不删除权重和作品。视频队列或操作台作业忙碌时返回409，无法确认队列时拒绝释放/停止。启动生成任务前先卸载Qwen，避免两个大型模型争用内存和显存。

后端位于 `website/src/main/java/com/example/website/integration/local/`，停止脚本为classpath中的 `local-services/stop-service.ps1`。只停止命令同时匹配项目路径、脚本与端口的Python进程，拒绝停止占用端口的其他应用。日志在启动应用的工作目录中，文件名`love530-service.log`。新页面不需要npm构建。

验证：`mvn -pl website -am test -Dtest=LocalServicesManagerTest,LocalServicesControllerTest,ServiceHealthPropertiesTest,ServiceHealthAggregatorTest,ServiceHealthCheckerTest,ServiceHealthControllerTest,HomepageStaticAssetsTest,WebsiteApplicationTests -Dsurefire.failIfNoSpecifiedTests=false`；`node --check website/src/main/resources/static/local-services/app.js`；`node website/src/test/js/homepage-motion.test.js`。单元测试不加载真实模型、不生成视频、不连接真实数据库。

## 个人长期资料库（Obsidian + Quartz，03 Deep Woods，5178）

健康档案默认展示最近检查、可核对的摘录、原报告建议和各次报告原值对照；人体图默认显示在报告选择器下方，健康文档双链可展开查看。详情的 `analysis_version` 区分空档、旧稿和新版。各资料领域通过 `GET /api/vault/overview?domain=...` 读取双链与编辑统计。

个人资料库总览展示真实 Vault 的最近笔记和至多 48 个节点的双链图（`GET /api/vault/overview`）。`GET /api/note` 同时提供安全 Markdown 阅读预览与反向链接，完整图谱、嵌入和 Bases 仍通过私有 Quartz 浏览页查看。

个人资料总览的通用导入（`/api/documents`）和健康档案（`/api/exams`）支持仅归档或经确认后把原件发给 DeepSeek 官方 Files API，使用 `deepseek-flash` 生成 Markdown 草稿。官方密钥读取根目录 `model.properties` 的 `deepseek.api-key`。体检解读保留指标摘录和历史对照。具体路径和验证见 `personal-agent/README.md`。

`personal-agent/` 是 Java 8 + Spring Boot 2.6.13 Maven 模块，服务标识仍为 `personal-agent`，监听 `127.0.0.1:5178`。内容已替换为真实 Obsidian Vault 的个人长期资料库，覆盖财务、健康、工作、生活等领域；网页提供资料记录、关键词搜索、版本校验编辑，以及用户确认来源后发起的 AI 分析。Quartz 5.1.0 的真实源码位于 `personal-agent/quartz/`，负责阅读、全文搜索、双链图、反向链接与原生 `.base` 视图。

首次执行 `cd personal-agent/quartz && npm ci`（Node.js 22+），再从根目录执行 `mvn -pl personal-agent -am package`。运行主类 `com.example.personalagent.PersonalAgentApplication` 或已构建 jar。03 Dock“个人资料库”点击启动方式、`POST /api/services/personal-agent/start`、`GET /api/services/personal-agent/status` 和健康聚合顺序保持不变；website 不自动启停它。

Windows 默认主资料源为 `D:/个人资料/Obsidian Vault/`，个人记录、AI 报告、Bases、模板与附件统一保存在此。服务状态目录仍为 `%LOCALAPPDATA%/Love530/PersonalAgent/`：`knowledge-state.json` 只保存登录哈希、仓库选择和分析状态，`note-backups/` 保存网页编辑前副本，`quartz-builds/` 保存私有浏览快照与构建日志。非 Windows 默认 Vault 为服务状态目录下的 `knowledge-vault/`。旧 `agent.mv.db`、旧 `vault/` 和备份保留，不自动导入或删除。新空间首次需要设置密码。可用 `PERSONAL_AGENT_DATA_DIR`、`PERSONAL_AGENT_VAULT_DIR`、`PERSONAL_AGENT_QUARTZ_DIR`、`PERSONAL_AGENT_NODE_COMMAND` 覆盖路径或命令；Windows 的 DATA_DIR 不改变默认 Vault。网页已保存的仓库选择优先，修改默认路径不自动搬移旧文件，已有资料需先完整复制再在设置中连接。测试必须显式指定临时 Vault，不能读写 D 盘真实资料。

健康接口仍为 `GET /api/health`，仅返回 `success=true, service=personal-agent`。其余业务 API 为 `/api/vault`、`/api/vault/{connect,initialize}`、`/api/notes`、`/api/note?path=...`、`/api/analyses/preview`、`/api/analyses`、`/api/quartz`、`/api/quartz/build`。API 与 `/library/**`（含搜索索引和附件）均受本机 Session 保护；写请求校验 CSRF。跨本机主机名的首页顶层导航例外保留。资料变化后旧 Quartz 快照停止提供，需点击生成/更新。

AI 沿用统一文本模型入口和 `PERSONAL_AGENT_API_*` 等原配置；先预览并选择最多8份资料，再明确确认发送片段。保留资料日期、来源、版本哈希，排除 AI 报告、草稿、归档、模板及 `ai_exclude: true`。报告写入 `80-AI分析/` 并标记为待核对草稿，不覆盖事实。无后台自动上传。详细 API、属性约定、限制与部署方式见 personal-agent/README.md。

验证：`mvn -pl personal-agent -am test`；website 入口回归 `mvn -pl website -am test -Dtest=HomepageStaticAssetsTest,PersonalAgentControllerTest,PersonalAgentProcessManagerTest -Dsurefire.failIfNoSpecifiedTests=false`；`node --check personal-agent/src/main/resources/static/app.js`。测试使用构造 Vault 与模型替身，不读取私人内容或调用真实模型。
## Skill Finder 云端日报与视频

日报视频现已接入内部 `video-renderer/`（Remotion 4.0.536 + React/TypeScript + Node.js 22+），默认 1080×1920 / 30 FPS；配音默认 MiMo，`MIMO_API_KEY` 仅在私有环境配置，字幕通过实际音轨转写。新增 `DAILY_VIDEO_RENDERER`、`DAILY_TTS_PROVIDER`、`DAILY_NODE_COMMAND`、`DAILY_WHISPER_MODEL`、`DAILY_ASSETS_DIR` 与素材完整性检查；`legacy` 可显式回退。先安装渲染依赖和 `uv sync --extra captions`，样片用 `python -m app.daily.cli sample`。详细配置、数据目录、测试和 Docker 资源要求见 [skill-finder/docs/remotion-integration.md](skill-finder/docs/remotion-integration.md)。既有 API、端口、Vue 页面与审核发布约定不变。

`website/skill-finder` 继续作为独立 FastAPI + Vue 微服务，以 love5000 版本为准同步到 `C:/Code/skills-finder`。云端采用 Docker + Nginx，入口 `https://49.232.128.132/skill-finder/`，日报审核 `/skill-finder/daily-reports`，后端仅监听回环 15177，本机开发仍用 5177。复用 xixi 原五张业务表，不重建共享库。

服务器北京时间 07:10 采集、07:30 制作（07:45 重试）、08:00 送达；当前 QQ 按用户要求暂不配置。成品包括文字日报、中文配音、字幕与竖屏视频，GitHub 当日 AI 项目不足十项时如实标注。DeepSeek 使用通用 `INTRO_API_KEY`、`INTRO_API_BASE`、`INTRO_MODEL` 私有配置，不把凭据写入 Git。

新增 API 前缀 `/api/v1/daily-reports`：GET 列表、GET `/{date}`、GET `/{date}/files/{filename}`；管理接口 POST `/generate`、POST `/{date}/review`、POST `/{date}/publish`；抖音登录 POST/GET `/publisher/login` 和受认证的 GET `/publisher/login/screen`。管理接口要求 X-Admin-Key，并只允许 HTTPS 或本机 SSH 隧道。发布必须绑定具体视频、口播和文案的人工批准；未登录不发布，结果不确定不自动重发。

`backend/app/daily/` 管理生成、媒体、审核摘要与发布适配；`backend/data/`、`.secrets/`、云端 `/var/lib/skill-finder/` 为私有运行数据，不提交。`deploy/` 维护 Docker、cron、Nginx 与 IP 证书续签；OpenClaw 在独立 Node 容器内仅监听回环 18789，QQ/抖音必须如实区分未配置、等待登录与已送达/已发布。完整部署、凭据边界与验证见 `website/skill-finder/docs/cloud-daily-report.md`（模块内为 `docs/cloud-daily-report.md`）。本机首页点击启动约定保持不变。


## 视频制作操作台

`/daily-reports` 现为一键制作操作台：展示采集、筛选、脚本、素材、配音、字幕、渲染、审核、抖音发布与可选 QQ 通知。真实状态每 5 秒刷新，任务目录中的 `workflow.json` 保存步骤、计数、时间与脱敏错误，`render-progress.json` 保存实际渲染帧数；历史任务无记录时明确标注，不补造进度。素材可从页面上传（MP4/PNG/JPEG，最大 100 MiB，有 HTTPS 来源），只允许本期项目，生成后使用固化副本。新增 GET `/api/v1/daily-reports/console?day=YYYY-MM-DD`、PUT `/{day}/assets/{owner}/{repo}?filename=...&source=...`（原始文件请求体）、POST `/{day}/notify` 与只读样片文件入口 `/samples/{id}/files/{filename}`（均位于 daily-reports 前缀下）；管理写操作继续使用 X-Admin-Key + HTTPS/本机连接，已进入审核的版本不可被一键运行覆盖。操作台“模板编辑”已内置 React/TSX 源码编辑、可视化样式、Remotion Player、编译错误定位、保存启用与版本恢复，入口为 `/daily-reports?panel=template`，无需另开 Studio。仅允许编辑 `src/video.tsx`、`src/demo.tsx`、`src/types.ts`；`root.tsx` 只读。新增 `/api/v1/daily-reports/template` 的 GET/PUT、POST `/preview`、POST `/restore`，源码与编译使用现有管理鉴权。保存前通过类型检查、打包和一帧真实渲染，版本原子切换；新版本只影响后续生成，已有成片和审核不变。不可变源码、样式与预览缓存位于日报目录同级 `video-template/`（默认 `backend/data/video-template/`），使用现有数据持久卷与 5177 端口。完整使用、API 和验证说明见 [操作台说明](skill-finder/docs/production-console.md)。


## 榜单刷新状态与网络故障处理

`GET /api/v1/stats` 在原有字段外返回 `last_run_id`（最新任务编号，可空）与
`last_run_error`（失败时的固定用户提示，可空）；错误提示不包含原始异常、凭据或连接串。
采集启动后先提交 `RUNNING`，首页提交刷新前记录最新任务编号，每 5 秒轮询，
即使没看到中间运行状态也能识别新任务的失败，恢复按钮并显示原因。历史失败不会误判为本次失败，
请求提交期间禁止重复点击，离开页面后停止轮询。
成功及部分成功任务保留原 30 分钟冷却；`FAILED` 允许立即重试，MySQL 命名锁继续防止并发采集。
`backend/.env` 的 `TRENDING_PROXY` 同时用于 GitHub Trending、GitHub API 与 README 请求；
按本机网络填写可用代理，不在仓库中写入私人代理凭据。连接超时保留已有榜单，不伪造采集成功。

验证：后端运行 `python -m pytest -q` 与 `python -m ruff check .`；
前端运行 `npm run lint`、`npm run typecheck`、`npm run test -- --run`、`npm run build`。
修改前端后重建 `frontend/dist`，后端修改后重启 5177 服务。

中文简介服务缺少密钥或返回 HTTP 401 时立即停止本轮简介生成，不再换模型、拆分批次或去掉 README 重试；榜单与 Star 数据正常保存。其他内容失败仍保留原降级逻辑，更新私有密钥后后续采集可继续补全简介。


## 健康巡检频率与 IDEA 日志

`ServiceHealthMonitor` 在 website 的 `ApplicationReadyEvent` 后统一巡检一次，完成后每半小时巡检；
`GET /api/services/health` 返回最近结果，打开或刷新多个首页不会额外请求子服务。
首页按 `data-health-service` 项目名匹配聚合结果，每半小时读取一次；website 自身页面入口仍检查页面可达性。
本机模型管理页首次进入读取状态，此后每半小时自动刷新，手动启停、加载及卸载后立即更新状态。
后台巡检不依赖浏览器是否打开。启动子服务时必要的就绪确认保留，不使用半小时周期等待启动。

配置在 `website/src/main/resources/application.yml`：
`website.service-health.check-interval-ms: 1800000`（毫秒），
`website.service-health.scheduled-enabled: true`；测试设置后者为 false，避免后台访问真实服务。
健康日志统一包含 `[健康检查][项目=skill-finder]` 等明确项目名，以及状态、HTTP 状态码和耗时；
本机模型状态日志也携带 strata / aimedia / h3 项目名，不记录凭据。
IDEA 中重新运行 `WebsiteApplication` 后生效，浏览器刷新首页以加载新脚本。
验证：`mvn -pl website -am test`、`node website/src/test/js/service-health.test.js`、
`node website/src/test/js/homepage-motion.test.js`。定时测试通过捕获调度回调模拟半小时流逝，无需实际等待。


## 中文介绍生成与完成状态

中文介绍在采集阶段生成、写入数据库，详情页只读取已保存的介绍，不在访问详情时自动调用模型。
启用 `INTRO_ENABLED` 后，介绍认证失败或缺失输出会将采集标记为 `PARTIAL`，保留真实榜单，
并在现有 `collection_runs.error_summary` 记录 `INTRO_AUTH_FAILED` / `INTRO_GENERATION_FAILED` 与缺失数量。
`GET /api/v1/stats` 增加可空字段 `last_run_warning`；首页部分完成时更新榜单并显示警告。
详情页缺失介绍显示“暂未生成中文介绍”，不把缺失误称为正在生成。

配置可使用 `INTRO_API_BASE=https://api.deepseek.com`、`INTRO_MODEL=deepseek-flash`，
或显式指定其他实际可用模型。`INTRO_API_KEY_FILE` 可引用已有本机私有密钥文件，优先于 `INTRO_API_KEY`；
支持纯文本或 JSON 中的 `INTRO_API_KEY`、`DEEPSEEK_API_KEY`、`intro_api_key`、`deepseek_api_key`、`api_key`。
只读取、不复制密钥文件内容，不向日志或响应输出密钥、私有路径或文件内容；私有配置不提交。
修复配置后可通过已有受鉴权的 `POST /api/v1/admin/introductions?limit=100&order=daily` 补全缺失介绍，
不必重新采集榜单；接口继续返回 accepted，由原后台补全逻辑保存结果，不改写已有介绍。
前端改动后运行 lint/typecheck/test/build，后端运行 pytest 与相关 Ruff 检查，重启 5177 后生效。

## 统一模型入口（2026-10-20）

主页提供全局文本模型选择，python-a、scrapling-ui、skill-finder、personal-agent 提供“跟随主页 / 服务原配置 / 独立模型”，下一次请求生效。图片、视觉、语音和视频保留专用模型；quant-a 与 lovestory 当前没有文本模型调用。

OpenCode Go 在根目录私有 `model.properties` 中按模板填写 `opencode-go.api-key`，使用 `https://opencode.ai/inference/go/openai/v1`。在主页模型选择器点 ↻ 后，可选择通过目录探测的 `deepseek-v4.1-flash`。
website 的 `/api/models` 提供目录核验、选择持久化和文本代理，状态文件为根 `.runtime/model-routing.json`，仅存模型 ID、不存密钥；Java 客户端在 common，Python 公共源码在 website/model-routing，部署副本 _model_routing.py 随各服务打包。原有认证保留。未选择时保留原逻辑，已选择但网关离线时报错。
共享选择器源为 website/src/main/resources/static/model-picker/picker.js，修改后执行 `python scripts/sync-model-picker.py`，或用 `python scripts/sync-model-picker.py --check` 只读校验；React/Vue 修改后重新构建 dist。图片工作台新增独立图片模型下拉与 `OPENAI_IMAGE_MODELS` 白名单，支持 JSON/multipart 的 `model` 字段。
完整盘点、API、边界与验证见 [统一模型入口](../docs/model-routing.md)。跨模块验证 `mvn test`；公共 Python 客户端验证 `python -m unittest discover -s website/model-routing`。

### MiMo V2.6 文本接入（2026-10-20）

统一模型目录新增 Xiaomi MiMo 的 `mimo-v2.6-pro`、`mimo-v2.6-flash`。website 优先读取环境变量 `MIMO_API_KEY` / `MIMO_API_BASE` / `MIMO_CHAT_MODELS`，缺失时复用 Skill Finder 私有 `.env`；密钥不复制、不回显。默认地址为官方 `https://api.xiaomimimo.com/v1`，模型列表与真实 `/models` 交集校验，过滤 ASR/TTS、旧版和未显式配置的定制型号。
主页与微服务原有选择器自动展示两个文本模型；原有选择、MiMo TTS 模型与配音保持不变。网关按官方规范将 `max_tokens` 转换为 `max_completion_tokens`，默认关闭深度思考，JSON 模式原样保留；显式开启思考时移除自定义采样参数。回归运行 `mvn -pl website -am test`，详见统一模型入口文档。

## 文本模型调用收敛（2026-10-21）

integration/models 增加 POST /api/models/complete/{service}；目录探测使用独立锁并发布不可变快照，已有模型查询/生成不被慢速刷新阻塞。
生成使用 `POST /api/models/complete/{service}`：200 返回统一模型结果，204 明确使用服务原配置；`effective` 只用于状态展示，旧 `chat` 保留兼容。超时或 HTTP 错误不回退；只有连接被拒绝且状态确认无统一选择时允许离线原配置。
Python 公共源码改动后执行 `python scripts/sync-model-routing.py`，再执行 `--check` 与公共 unittest；副本随服务部署，只改公共源码。回归运行 `mvn -pl website,personal-agent -am test`、python-a/Scrapling unittest 及 Skill Finder pytest；详见 [统一模型入口](../docs/model-routing.md)。

## Skill Finder 一键视频质量升级（2026-10-23）

保留 Remotion + FFmpeg/ffprobe + MiMo 和一键制作流程。默认模板升级为分阶段镜头、宽幅来源演示与两行字幕，H.264 使用 CRF 18 / medium；口播清理展示语法，完整句控制在 360 字内并保留限制条件。长字幕仅按实际词边界拆分，音频采用实测双遍响度和整片检测。新增可选 `DAILY_BGM_FILE` / `DAILY_BGM_SOURCE`（本地授权配乐与 HTTPS 来源），配乐在付费 TTS 前预检并固化到本期目录，人声出现时自动压低。结果写入私有 `render-result.json` 的 `audio_mastering`；验收失败不进入待审核。历史视频和私有模板版本不被覆盖；已有私有模板需手工合并新默认源码。配置、数据文件、运行与测试见 [视频质量升级](skill-finder/docs/video-quality-upgrade.md)。

## HyperFrames 可切换视频引擎（2026-10-26）

新增内部 `hyperframes-renderer/`（官方 producer/engine/core 0.8.186 + GSAP 3.13.0，Node.js 22+），通过 `DAILY_VIDEO_RENDERER=hyperframes` 选择；默认使用 HyperFrames，Remotion 保留为备用引擎（`DAILY_VIDEO_RENDERER=remotion`），legacy 仍可显式选择，失败不自动换引擎。新增 `HYPERFRAMES_BROWSER_EXECUTABLE` 与 `HYPERFRAMES_CONCURRENCY`（默认 1，范围 1–8），复用原素材、配音、实测字幕、FFmpeg 母带与审核流程。模板编辑 API 增加 engine 标识，HyperFrames 仅编辑 `src/template.html` / `src/demo.html`，版本隔离在日报同级 `video-template/hyperframes/`；原 Remotion 模板保持原位置。临时 `.hyperframes-project-*` 只包含固化媒体与模板，任务结束清理，真实验收后生成正式结果。样片命令按当前引擎生成自身演示，Docker 构建同时包含两套引擎；不新增端口或 Dock。配置、模板 API、数据、测试和部署见 [HyperFrames 接入](skill-finder/docs/hyperframes-integration.md)。

## 开奖数据操作台（01 第 9 个入口，5179）

操作台导航提供 `/selection` 选号工具及 `GET /api/selection`，按历史统计或随机方式生成候选号码；说明和测试方式见 `lottery/README.md`。

在仓库根目录执行 `python -X utf8 website/lottery/scripts/selection_backtest.py`
可只读回测选号方法；方法、参数和限制见 `lottery/README.md`。

首页 01 Golden Hour 新增「开奖数据操作台」卡片（第 09 个入口，Dock 同步改为 9 列）。点击后由
`integration/lottery` 启动 `website/lottery`：`python server.py --port 5179`，健康检查
`GET /api/health`，页面为该目录下 `output/console.html`。

服务内容：双色球 3523 期 + 大乐透 2944 期官方开奖；四种视图（数据表、走势矩阵、统计、分组透视），
支持任意列排序、号码必含/排除、区间筛选、CSV 导出与逐期奖级明细。页面顶部「刷新数据」按钮调用
`POST /api/update` 增量抓取官方接口，有新期次时备份、追加并重建操作台，完成后自动刷新页面。

首次启动会自动构建 `output/console.html`（约 3 秒）；日常更新只需点按钮，也可在
`website/lottery` 下执行 `python scripts/update_daily.py`。数据与产物：`data/` 提交，
`output/`、`cache/`、`logs/`、`data/backup/` 为本地生成。

## 统一模型的浏览器跨域预检（2026-11-16）

个人资料库（5178）沿用主页统一模型路由；未单独指定模型时跟随 global，无需复制模型密钥。需要先在8080主页选择一个具体的全局文本模型；如果 global 为空，继承状态为 true 但统一模型未启用，各服务按原配置处理。

`ModelRoutingController` 为 `/api/models/**` 声明受限本机 CORS 来源（8080、5174、5176、5177、5178；localhost/127.0.0.1/IPv6回环），允许 Content-Type 与 X-Love530-Model。真实 OPTIONS 预检由 Spring MVC 在控制器之前处理，不能仅依赖控制器手写响应头。写请求自定义头、本机限制与“浏览器不能直接调用生成接口”的边界继续保留。

验证使用真实 MVC 配置：`mvn -pl website -am test "-Dtest=ModelRoutingControllerTest,ModelRoutingCorsIntegrationTest,ModelRoutingServiceTest,MimoModelRoutingTest" "-Dsurefire.failIfNoSpecifiedTests=false"`。CORS 声明修改后重启 website，再从5178验证 OPTIONS 与模型目录读取。
