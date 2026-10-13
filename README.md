# love5000 / love530

## 统一健康检查

`lovestory`、`imagetemplate`、`python-a`、`quant-a`、`scrapling-ui` 和 `skill-finder`
统一提供 `GET /api/health`，响应顶层包含 `success=true` 与稳定的 `service`。
启动 `website` 后可访问 `GET http://127.0.0.1:8080/api/services/health` 并行查看八个服务；
HTTP 200 表示聚合成功，`healthy` 表示是否全部在线。Java 探测默认连接/读取超时为
2000/3000ms。

相关 Java 回归命令：

```bash
mvn -pl website,lovestory,imagetemplate -am test
```

`love5000` 是一个 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目，父工程 artifactId 为 `love530`。仓库同时托管四个独立 Python 微应用，用于 A 股研究、量化研究、可视化爬虫和 AI 项目趋势追踪。

## 模块

Maven 聚合模块：

- `common`：公共 OSS 工具、自动配置和通用 Session 认证能力。
- `lovestory`：恋爱相册、照片上传、留言板和吉他视频卡片 Web 应用。
- `website`：电影化个人主页/展示站点、提示词控制台，以及 8 个服务入口、实时健康状态和 Python 子服务自动启动；首页提供四场景视频切换与响应式液态玻璃服务 Dock。
- `imagetemplate`：聚合 47 条精选图片模板和 Prompt Console 的 4409 条公开提示词，总计 4456 条，并按 15 个一级功能与二级场景检索；提供按需详情和 OpenAI Images API 生成服务（默认模型 `gpt-image-2.5-sunburst`），前端采用虎主题编辑式黑色工作台、橙色高对比操作、dense 模板展廊和本地 GSAP 滚动动效，模板 JSON 与变量剧本均可手工编辑。

独立 Python 微应用：

- `website/python-a`：A 股自选股 AI 研究台，默认端口 `5174`，随 `website` 自动拉起。
- `website/quant-a`：A 股多因子量化研究台，默认端口 `5175`，随 `website` 自动拉起。
- `website/scrapling-ui`：基于 Scrapling + Playwright 的可视化爬虫工作台（汉化版），默认端口 `5176`，由首页 Dock 卡片点击启动，不随 `website` 自动拉起。
- `website/skill-finder`：AI 项目趋势追踪站（GitHub Trending 采集 + 排行展示），默认端口 `5177`，由首页 Dock 卡片点击启动，不随 `website` 自动拉起；数据库与 `website` 共用腾讯云 MySQL 的 `xixi` 库。

根目录下的 `python-a/`、`quant-a/` 不是当前主要接入路径；当前运行和文档维护以 `website/` 下的两个子服务为准。

## 快速开始

从仓库根目录执行：

```bash
cd C:/Code/Java_Code/love5000
mvn test
```

启动 `website`：

```bash
mvn -pl website -am spring-boot:run
```

`website` 默认端口为 `8080`，启动时会检查并自动拉起 `website/python-a` 和 `website/quant-a`。如果对应健康检查已经可用，会复用已有服务。`website/scrapling-ui` 和 `website/skill-finder` 不随启动拉起，由首页 Dock 卡片点击启动：离线时点击调用 `POST /api/services/scrapling-ui/start` 或 `POST /api/services/skill-finder/start` 拉起服务，启动过程只在卡片内提示“启动中…”（不打开中间页面）；就绪后自动打开对应页面，若浏览器拦截新窗口，卡片会显示“已启动 · 点击打开”，再点一次即可打开。在线时点击直接打开。

首页是无需前端构建的单视口原生页面，集中展示恋爱相册、图片模板、Prompt Console、A 股研究台、Quant 研究台、Scrapling 抓取工坊和 Skill Finder。每个入口保留端口标识和实时状态；顶部只保留登录、注册账户操作，登录后切换为退出，移动端继续使用横向可滑动服务 Dock。

四个场景分别支持独立文案与服务目录：01 Golden Hour 保留原诗句和 8 个服务入口；02 Still Water、03 Deep Woods、04 Quiet Dawn 各自使用暂定文案，服务区留空并隐藏，切回 01 恢复原目录。背景视频和动画不变；文案在首页各按钮的 `data-scene-title`、`data-scene-statement`、`data-scene-badge` 中配置，新服务沿用 `service-card` 放入各自的 `still-water-service-dock`、`deep-woods-service-dock`、`quiet-dawn-service-dock`。

`imagetemplate` 首页同样无需前端构建，按“灵感大厅 → 模板解构 → Prompt 编导台 → 图片生成舱”组织为编辑式黑色 AI 创作工作台。页面使用本地虎主题背景、宽幅分屏首屏、内嵌图像标题、创作理念轮播、橙色高对比操作和三段横向交互面板；灵感大厅默认每页 48 条，顶部常驻搜索、仅图片开关、结果计数和清除筛选，桌面端左侧集中展示“一级功能 + 二级场景”及高级筛选，右侧使用 dense 密排结果网格。页面支持 300ms 搜索防抖、加载更多和详情按需读取；模板解构中的 JSON 可直接编辑并校验，进入 Prompt 编导台时同步到可继续修改的变量剧本。GSAP 3.13.0 与 ScrollTrigger 从模块本地静态资源加载，并对脚本缺失及 `prefers-reduced-motion` 提供静态降级；窄屏流程恢复为底部横向排列，切换场景保留已选模板、Prompt、生成参数和结果。

Prompt Console 大库的唯一源码是 `website/src/main/resources/static/prompt-console/data/prompt-library.json`。构建 imagetemplate 时 Maven 会将它复制到 jar 的 `templates/prompt-console/prompt-library.json`，运行时不要求 website 服务在线；`GET /api/image-templates/meta` 可检查 4456 条聚合数据、功能分类树及其 `READY` 状态。

Prompt Console 页面（`prompt-console/index.html`）的数据已服务端化：4409 条提示词、10 个大分类和 6 个来源导入 MySQL `xixi` 库的 `prompt_entry`/`prompt_source`/`prompt_group` 三张表，页面通过 `GET /api/prompts/meta`、`GET /api/prompts`（服务端分页/搜索，`size` 默认 48 最大 100）和 `GET /api/prompts/{id}` 读取，不再直接 fetch 本地 JSON。页面提供"添加提示词"按钮，通过 `POST /api/prompts` 手动写入（大分类按库中既有归属自动推导，未知小分类归入"其他"，来源默认"手动添加"）；当前添加接口不加鉴权。大分类 slug 在导入时按 `prompt-category-groups.js` 的同一映射写入，`prompt-category-groups.js` 保留为导入工具与 node 测试的数据源。

其他服务：

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
mvn -pl imagetemplate -am spring-boot:run
```

Python 子服务可单独启动：

```bash
cd website/python-a && python server.py
cd website/quant-a && python -m uvicorn main:app --host 127.0.0.1 --port 5175
```

`scrapling-ui` 首次使用前准备环境，之后可手动启动：

```bash
cd website/scrapling-ui/backend
uv sync
uv run playwright install chromium

cd ../frontend
npm install
npm run build

cd ../backend
.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 5176
```

`skill-finder` 默认直接复用 `website/src/main/resources/application.yml` 的 `spring.datasource` 配置，解析其中的 `WEBSITE_DB_*` 环境变量，无需独立配置数据库；`DATABASE_URL` 环境变量或 `backend/.env` 可显式覆盖。GitHub Token 放 `backend/.secrets/`，私有文件均已 gitignore。原 `skill_finder` 库的五张业务表数据已复制到 `xixi`，源库保留。后端依赖包含 MySQL SHA-2 认证所需的 `cryptography`，通过 `uv sync` 安装；首次接入只补建缺失的业务表，集成测试使用独立测试库：

```bash
cd website/skill-finder/backend
uv sync

cd ../frontend
npm install
npm run build

cd ../backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 5177
```

也可使用已安装的全局 Python 3.12+（默认 `python` 若是 3.9 则不能使用）。
在 backend 目录执行 `uv pip install --python <python完整路径> -r pyproject.toml`
和 `<python> -m playwright install chromium`，再将 `SCRAPLING_UI_COMMAND` 环境变量
设为该解释器完整路径，重启 `website` 所在终端或 IDE。启动器会直接执行
`<python> -m uvicorn` 并绕过 `.venv`。未设置时仍保留原 uv 启动方式。

## 端口

- `website`：`8080`
- `lovestory`：`8081`
- `imagetemplate`：`8082`
- `python-a`：`5174`
- `quant-a`：`5175`
- `scrapling-ui`：`5176`
- `skill-finder`：`5177`

## 测试

Java 模块：

```bash
mvn test
mvn -pl common test
mvn -pl lovestory -am test
mvn -pl website -am test
mvn -pl imagetemplate -am test
```

验证 imagetemplate 独立包包含聚合大库：

```powershell
mvn -pl imagetemplate -am clean package -DskipTests
jar tf imagetemplate/target/imagetemplate-0.0.1-SNAPSHOT.jar | Select-String "templates/prompt-console/prompt-library.json"
```

Python 子服务：

```bash
cd website/python-a && python -m unittest discover -s tests -v
cd website/quant-a && python -m pytest -v
cd website/scrapling-ui/backend && uv run python -m unittest discover -s tests -v
cd website/skill-finder/backend && .venv/Scripts/python.exe -m pytest -q
cd website/skill-finder/frontend && npm run test -- --run
```

## 配置与安全

不要提交真实数据库密码、OSS AccessKey、OpenAI API Key、DeepSeek Key、Tushare Token、腾讯云密钥或 DashScope Key。新增配置优先使用环境变量或本地私有配置文件。

`lovestory` 默认连接本机 `lovestory` 数据库并关闭 OSS。需要连接其他数据库或启用 OSS 时，使用 `LOVESTORY_DB_URL`、`LOVESTORY_DB_USERNAME`、`LOVESTORY_DB_PASSWORD` 和 `LOVE530_OSS_*` 环境变量覆盖。`website` 数据库使用 `WEBSITE_DB_URL`、`WEBSITE_DB_USERNAME`、`WEBSITE_DB_PASSWORD` 覆盖，默认指向腾讯云 `xixi` 库（`jdbc:mysql://49.232.128.132:3306/xixi`），提示词库和认证共用该数据源；密码必须走环境变量，仓库内不提供真实凭据默认值。

常见私有文件已在 `.gitignore` 中忽略，例如：

- `website/python-a/deepseek.local.json`
- `website/quant-a/data/`
- `website/scrapling-ui/backend/jobs.db`、`website/scrapling-ui/frontend/dist/`
- `website/skill-finder/backend/.env`、`website/skill-finder/backend/.secrets/`、`website/skill-finder/frontend/dist/`
- `.env`、`.venv/`、`__pycache__/`、`.pytest_cache/`、`*.log`

## 文档维护规则

每次修改项目结构、模块职责、启动命令、端口、配置项、API、数据目录、测试方式或部署入口时，必须同步更新根 `AGENTS.md` / `README.md`，以及受影响模块或微应用目录下的 `AGENTS.md` / `README.md`。文档和代码不一致时，本次改动不能视为完成。

开发代理细节、模块边界、API 清单和测试要求见根目录 `AGENTS.md`，模块目录下的 `AGENTS.md` / `README.md` 以各自模块为准。

## 代码提交
本地代码提交到远程仓库时，通常会遇到网络问题导致提交失败，不用处理，直接进行重试，直到成功为止。

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

website接口：`POST /api/services/personal-agent/start`（返回 `{success,status,url}`）、`GET /api/services/personal-agent/status`；配置 `personal-agent.click-start.{enabled,work-dir,command,port,health-path,startup-timeout-seconds,log-to-console}`，默认目录 `personal-agent`，从仓库根或website启动都能定位；`PERSONAL_AGENT_COMMAND`可指定Java程序路径，默认java.home/bin/java。统一健康清单末尾追加个人Agent，保留已有顺序。

私人数据默认 `%LOCALAPPDATA%/Love530/PersonalAgent/`，可用 `PERSONAL_AGENT_DATA_DIR`覆盖；本地H2账本经MyBatis DAO+XML持久化，金额BigDecimal，不使用远程MySQL。`vault/`可用Obsidian直接打开；历史按录入年月存放，按事件时间/录入时间/UUID查看，手工修改受哈希保护。默认DeepSeek，可通过环境变量配置Key/模型/HTTPS地址，密钥不回显或进入Git。

功能包括对话、书籍与生活记录、长期记忆、想法行动、完整财务、事件触发复盘与网页未读提醒；接口及验证范围见 [personal-agent README](personal-agent/README.md)。验证：`mvn -pl personal-agent -am test`、`mvn -pl website -am test`、`node --check personal-agent/src/main/resources/static/app.js`。不要在测试使用真实财富或模型密钥。
