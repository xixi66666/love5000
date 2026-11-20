# love5000 / love530

> 模型配置已统一：模型目录、密钥和各服务原配置只从项目根目录 `model.properties` 读取（模板 `model.properties.example`）。本文中出现的模型环境变量、`deepseek.local.json`、`INTRO_*` / `MIMO_*` 示例仅作历史说明，不再生效。


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

`love5000` 是一个 Java 8 + Spring Boot 2.6.13 的 Maven 多模块项目，父工程 artifactId 为 `love530`。仓库同时托管五个独立 Python 微应用，用于 A 股研究、量化研究、可视化爬虫、AI 项目趋势追踪和双色球/大乐透数据分析。

## 模块

Maven 聚合模块：

- `common`：公共 OSS 工具、自动配置和通用 Session 认证能力。
- `lovestory`：恋爱相册、照片上传、留言板和吉他视频卡片 Web 应用。
- `website`：电影化个人主页/展示站点、提示词控制台，以及 9 个服务入口、实时健康状态和 Python 子服务自动启动；首页提供四场景视频切换与响应式液态玻璃服务 Dock。
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

四个场景分别支持独立文案与服务目录：01 Golden Hour 保留原诗句和 9 个服务入口；02 Still Water、03 Deep Woods、04 Quiet Dawn 各自使用暂定文案，服务区留空并隐藏，切回 01 恢复原目录。四场景已去除车窗图片覆盖及其晃动动画，仅展示原风景视频，保留视频动画与切换时序；文案在首页各按钮的 `data-scene-title`、`data-scene-statement`、`data-scene-badge` 中配置，新服务沿用 `service-card` 放入各自的 `still-water-service-dock`、`deep-woods-service-dock`、`quiet-dawn-service-dock`。

四段场景片都是 10.04 秒，首帧和末帧不是同一个镜头，浏览器原生 `loop` 会在片尾停帧再瞬间跳回片头，看起来就是“突然顿住 + 硬切”。首页因此在原视频进入最后 1 秒时，用一层同源的 `scene-video--loop` 从第一帧起播并接管画面，两层用 1000ms 交叉淡化完成循环；原视频在自己已经不可见之后才回到片头。**只能让上层补层改变不透明度，下层原视频必须始终不透明**：两层是上下叠放，同时半透明时合成覆盖率只有 `上层 + 下层 × (1 − 上层)`（中点 75%），会透出深色背景，看起来像“突然黑一下”。补层由脚本动态创建、默认暂停且不进入无障碍树，`play()` 被拒绝或片段过短时自动退回原生 `loop`，`prefers-reduced-motion` 下按 1ms 切换，缓推镜头的相位在接管时同步；切换场景会等新视频 `readyState ≥ 2` 再淡入，避免把画面淡成背景。回归命令：`node website/src/test/js/homepage-video-loop.test.js`。

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

首页 Dock 将「Qwen 本地模型」「视频操作台」「H3 音视频模型」合并为「模型与视频」，共8个入口。统一卡片进入 `/local-services/index.html`，首页每30分钟检测管理页可访问性；三个服务仍在管理页分别操作，每30分钟刷新各自状态，统一健康检查清单保留三项探测。

管理页借鉴 MotionSite 网站的排版与动效思路，采用独立设计的深色冰蓝工作台、Geist 字体与紧凑三服务网格；首屏背景使用 MotionSite 背景库的 Pulse 等离子光环静音循环视频，不复用其他操作台的风景素材。桌面三列、平板两列且 H3 横跨整行、手机单列；原有服务按钮、API 和30分钟状态刷新保留。动效集中在 `static/local-services/motion.js`，复用本地 GSAP/ScrollTrigger 3.12.5，提供首屏入场、能力速览切换、文字渐显及几何视觉缩放/淡化。视频与海报位于 `static/local-services/media/`（10秒、1280×720、24fps、约2MB）；支持顶部暂停/播放、隐藏标签页及滚出背景区域自动暂停，视频失败保留 JPG 与 CSS 背景，`prefers-reduced-motion` 下不下载视频。背景播放不依赖 GSAP；动效库缺失时保留可操作页面，无需 npm 构建。

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

## 个人长期资料库（Obsidian + Quartz，03 Deep Woods，5178）

健康档案提供人体热点和健康文档双链图。各资料领域显示自己的双链与近六个月最后编辑统计，复用 `GET /api/vault/overview?domain=...`。

个人资料库总览展示真实 Vault 的最近笔记和至多 48 个节点的双链图（`GET /api/vault/overview`）。`GET /api/note` 同时提供安全 Markdown 阅读预览与反向链接，完整图谱、嵌入和 Bases 仍通过私有 Quartz 浏览页查看。

个人资料总览的通用导入（`/api/documents`）和健康档案（`/api/exams`）支持仅归档或经确认后把原件发给 DeepSeek 官方 Files API，使用 `deepseek-flash` 生成 Markdown 草稿。官方密钥读取根目录 `model.properties` 的 `deepseek.api-key`。体检解读保留指标摘录和历史对照。具体路径和验证见 `personal-agent/README.md`。

`personal-agent/` 是 Java 8 + Spring Boot 2.6.13 Maven 模块，服务标识仍为 `personal-agent`，监听 `127.0.0.1:5178`。内容已替换为真实 Obsidian Vault 的个人长期资料库，覆盖财务、健康、工作、生活等领域；网页提供资料记录、关键词搜索、版本校验编辑，以及用户确认来源后发起的 AI 分析。Quartz 5.1.0 的真实源码位于 `personal-agent/quartz/`，负责阅读、全文搜索、双链图、反向链接与原生 `.base` 视图。

首次执行 `cd personal-agent/quartz && npm ci`（Node.js 22+），再从根目录执行 `mvn -pl personal-agent -am package`。运行主类 `com.example.personalagent.PersonalAgentApplication` 或已构建 jar。03 Dock“个人资料库”点击启动方式、`POST /api/services/personal-agent/start`、`GET /api/services/personal-agent/status` 和健康聚合顺序保持不变；website 不自动启停它。

Windows 默认主资料源为 `D:/个人资料/Obsidian Vault/`，个人记录、AI 报告、Bases、模板与附件统一保存在此。服务状态目录仍为 `%LOCALAPPDATA%/Love530/PersonalAgent/`：`knowledge-state.json` 只保存登录哈希、仓库选择和分析状态，`note-backups/` 保存网页编辑前副本，`quartz-builds/` 保存私有浏览快照与构建日志。非 Windows 默认 Vault 为服务状态目录下的 `knowledge-vault/`。旧 `agent.mv.db`、旧 `vault/` 和备份保留，不自动导入或删除。新空间首次需要设置密码。可用 `PERSONAL_AGENT_DATA_DIR`、`PERSONAL_AGENT_VAULT_DIR`、`PERSONAL_AGENT_QUARTZ_DIR`、`PERSONAL_AGENT_NODE_COMMAND` 覆盖路径或命令；Windows 的 DATA_DIR 不改变默认 Vault。网页已保存的仓库选择优先，修改默认路径不自动搬移旧文件，已有资料需先完整复制再在设置中连接。测试必须显式指定临时 Vault，不能读写 D 盘真实资料。

健康接口仍为 `GET /api/health`，仅返回 `success=true, service=personal-agent`。其余业务 API 为 `/api/vault`、`/api/vault/{connect,initialize}`、`/api/notes`、`/api/note?path=...`、`/api/analyses/preview`、`/api/analyses`、`/api/quartz`、`/api/quartz/build`。API 与 `/library/**`（含搜索索引和附件）均受本机 Session 保护；写请求校验 CSRF。跨本机主机名的首页顶层导航例外保留。资料变化后旧 Quartz 快照停止提供，需点击生成/更新。

AI 沿用统一文本模型入口和 `PERSONAL_AGENT_API_*` 等原配置；先预览并选择最多8份资料，再明确确认发送片段。保留资料日期、来源、版本哈希，排除 AI 报告、草稿、归档、模板及 `ai_exclude: true`。报告写入 `80-AI分析/` 并标记为待核对草稿，不覆盖事实。无后台自动上传。详细 API、属性约定、限制与部署方式见 personal-agent/README.md。

验证：`mvn -pl personal-agent -am test`；website 入口回归 `mvn -pl website -am test -Dtest=HomepageStaticAssetsTest,PersonalAgentControllerTest,PersonalAgentProcessManagerTest -Dsurefire.failIfNoSpecifiedTests=false`；`node --check personal-agent/src/main/resources/static/app.js`。测试使用构造 Vault 与模型替身，不读取私人内容或调用真实模型。
## Skill Finder 云端日报与视频

日报视频现已接入内部 `video-renderer/`（Remotion 4.0.536 + React/TypeScript + Node.js 22+），默认 1080×1920 / 30 FPS；配音默认 MiMo，`MIMO_API_KEY` 仅在私有环境配置，字幕通过实际音轨转写。新增 `DAILY_VIDEO_RENDERER`、`DAILY_TTS_PROVIDER`、`DAILY_NODE_COMMAND`、`DAILY_WHISPER_MODEL`、`DAILY_ASSETS_DIR` 与素材完整性检查；`legacy` 可显式回退。先安装渲染依赖和 `uv sync --extra captions`，样片用 `python -m app.daily.cli sample`。详细配置、数据目录、测试和 Docker 资源要求见 [website/skill-finder/docs/remotion-integration.md](website/skill-finder/docs/remotion-integration.md)。既有 API、端口、Vue 页面与审核发布约定不变。

`website/skill-finder` 继续作为独立 FastAPI + Vue 微服务，以 love5000 版本为准同步到 `C:/Code/skills-finder`。云端采用 Docker + Nginx，入口 `https://49.232.128.132/skill-finder/`，日报审核 `/skill-finder/daily-reports`，后端仅监听回环 15177，本机开发仍用 5177。复用 xixi 原五张业务表，不重建共享库。

服务器北京时间 07:10 采集、07:30 制作（07:45 重试）、08:00 送达；当前 QQ 按用户要求暂不配置。成品包括文字日报、中文配音、字幕与竖屏视频，GitHub 当日 AI 项目不足十项时如实标注。DeepSeek 使用通用 `INTRO_API_KEY`、`INTRO_API_BASE`、`INTRO_MODEL` 私有配置，不把凭据写入 Git。

新增 API 前缀 `/api/v1/daily-reports`：GET 列表、GET `/{date}`、GET `/{date}/files/{filename}`；管理接口 POST `/generate`、POST `/{date}/review`、POST `/{date}/publish`；抖音登录 POST/GET `/publisher/login` 和受认证的 GET `/publisher/login/screen`。管理接口要求 X-Admin-Key，并只允许 HTTPS 或本机 SSH 隧道。发布必须绑定具体视频、口播和文案的人工批准；未登录不发布，结果不确定不自动重发。

`backend/app/daily/` 管理生成、媒体、审核摘要与发布适配；`backend/data/`、`.secrets/`、云端 `/var/lib/skill-finder/` 为私有运行数据，不提交。`deploy/` 维护 Docker、cron、Nginx 与 IP 证书续签；OpenClaw 在独立 Node 容器内仅监听回环 18789，QQ/抖音必须如实区分未配置、等待登录与已送达/已发布。完整部署、凭据边界与验证见 `website/skill-finder/docs/cloud-daily-report.md`（模块内为 `docs/cloud-daily-report.md`）。本机首页点击启动约定保持不变。


## 视频制作操作台

`/daily-reports` 现为一键制作操作台：展示采集、筛选、脚本、素材、配音、字幕、渲染、审核、抖音发布与可选 QQ 通知。真实状态每 5 秒刷新，任务目录中的 `workflow.json` 保存步骤、计数、时间与脱敏错误，`render-progress.json` 保存实际渲染帧数；历史任务无记录时明确标注，不补造进度。素材可从页面上传（MP4/PNG/JPEG，最大 100 MiB，有 HTTPS 来源），只允许本期项目，生成后使用固化副本。新增 GET `/api/v1/daily-reports/console?day=YYYY-MM-DD`、PUT `/{day}/assets/{owner}/{repo}?filename=...&source=...`（原始文件请求体）、POST `/{day}/notify` 与只读样片文件入口 `/samples/{id}/files/{filename}`（均位于 daily-reports 前缀下）；管理写操作继续使用 X-Admin-Key + HTTPS/本机连接，已进入审核的版本不可被一键运行覆盖。操作台“模板编辑”已内置 React/TSX 源码编辑、可视化样式、Remotion Player、编译错误定位、保存启用与版本恢复，入口为 `/daily-reports?panel=template`，无需另开 Studio。仅允许编辑 `src/video.tsx`、`src/demo.tsx`、`src/types.ts`；`root.tsx` 只读。新增 `/api/v1/daily-reports/template` 的 GET/PUT、POST `/preview`、POST `/restore`，源码与编译使用现有管理鉴权。保存前通过类型检查、打包和一帧真实渲染，版本原子切换；新版本只影响后续生成，已有成片和审核不变。不可变源码、样式与预览缓存位于日报目录同级 `video-template/`（默认 `backend/data/video-template/`），使用现有数据持久卷与 5177 端口。完整使用、API 和验证说明见 [操作台说明](website/skill-finder/docs/production-console.md)。


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
website 的 `/api/models` 提供目录核验、选择持久化和文本代理，状态文件为根 `.runtime/model-routing.json`，仅存模型 ID、不存密钥；Java 客户端在 common，Python 公共源码在 website/model-routing，部署副本 _model_routing.py 随各服务打包。原有认证保留。未选择时保留原逻辑，已选择但网关离线时报错。
共享选择器源为 website/src/main/resources/static/model-picker/picker.js，修改后执行 `python scripts/sync-model-picker.py`，React/Vue 修改后重新构建 dist。图片工作台新增独立图片模型下拉与 `OPENAI_IMAGE_MODELS` 白名单，支持 JSON/multipart 的 `model` 字段。
完整盘点、API、边界与验证见 [统一模型入口](docs/model-routing.md)。跨模块验证 `mvn test`；公共 Python 客户端验证 `python -m unittest discover -s website/model-routing`。

### MiMo V2.6 文本接入（2026-10-20）

统一模型目录新增 Xiaomi MiMo 的 `mimo-v2.6-pro`、`mimo-v2.6-flash`。website 优先读取环境变量 `MIMO_API_KEY` / `MIMO_API_BASE` / `MIMO_CHAT_MODELS`，缺失时复用 Skill Finder 私有 `.env`；密钥不复制、不回显。默认地址为官方 `https://api.xiaomimimo.com/v1`，模型列表与真实 `/models` 交集校验，过滤 ASR/TTS、旧版和未显式配置的定制型号。
主页与微服务原有选择器自动展示两个文本模型；原有选择、MiMo TTS 模型与配音保持不变。网关按官方规范将 `max_tokens` 转换为 `max_completion_tokens`，默认关闭深度思考，JSON 模式原样保留；显式开启思考时移除自定义采样参数。回归运行 `mvn -pl website -am test`，详见统一模型入口文档。

## 文本模型调用收敛（2026-10-21）

四个文本服务已使用单次生成协议；原配置直连的公共传输在 common/ai 与 website/model-routing。
生成使用 `POST /api/models/complete/{service}`：200 返回统一模型结果，204 明确使用服务原配置；`effective` 只用于状态展示，旧 `chat` 保留兼容。超时或 HTTP 错误不回退；只有连接被拒绝且状态确认无统一选择时允许离线原配置。
Python 公共源码改动后执行 `python scripts/sync-model-routing.py`，再执行 `--check` 与公共 unittest；副本随服务部署，只改公共源码。回归运行 `mvn -pl website,personal-agent -am test`、python-a/Scrapling unittest 及 Skill Finder pytest；详见 [统一模型入口](docs/model-routing.md)。

## Skill Finder 一键视频质量升级（2026-10-23）

保留 Remotion + FFmpeg/ffprobe + MiMo 和一键制作流程。默认模板升级为分阶段镜头、宽幅来源演示与两行字幕，H.264 使用 CRF 18 / medium；口播清理展示语法，完整句控制在 360 字内并保留限制条件。长字幕仅按实际词边界拆分，音频采用实测双遍响度和整片检测。新增可选 `DAILY_BGM_FILE` / `DAILY_BGM_SOURCE`（本地授权配乐与 HTTPS 来源），配乐在付费 TTS 前预检并固化到本期目录，人声出现时自动压低。结果写入私有 `render-result.json` 的 `audio_mastering`；验收失败不进入待审核。历史视频和私有模板版本不被覆盖；已有私有模板需手工合并新默认源码。配置、数据文件、运行与测试见 [视频质量升级](website/skill-finder/docs/video-quality-upgrade.md)。

## HyperFrames 可切换视频引擎（2026-10-26）

新增内部 `hyperframes-renderer/`（官方 producer/engine/core 0.8.186 + GSAP 3.13.0，Node.js 22+），通过 `DAILY_VIDEO_RENDERER=hyperframes` 选择；默认使用 HyperFrames，Remotion 保留为备用引擎（`DAILY_VIDEO_RENDERER=remotion`），legacy 仍可显式选择，失败不自动换引擎。新增 `HYPERFRAMES_BROWSER_EXECUTABLE` 与 `HYPERFRAMES_CONCURRENCY`（默认 1，范围 1–8），复用原素材、配音、实测字幕、FFmpeg 母带与审核流程。模板编辑 API 增加 engine 标识，HyperFrames 仅编辑 `src/template.html` / `src/demo.html`，版本隔离在日报同级 `video-template/hyperframes/`；原 Remotion 模板保持原位置。临时 `.hyperframes-project-*` 只包含固化媒体与模板，任务结束清理，真实验收后生成正式结果。样片命令按当前引擎生成自身演示，Docker 构建同时包含两套引擎；不新增端口或 Dock。配置、模板 API、数据、测试和部署见 [HyperFrames 接入](website/skill-finder/docs/hyperframes-integration.md)。

## 开奖数据操作台（01 第 9 个入口）

操作台导航提供 `/selection` 选号工具，支持随机、冷热频次、遗漏和时间衰减频率；历史统计不代表中奖优势，详见 `website/lottery/README.md`。

选号方法的逐期历史回测可在仓库根目录运行
`python -X utf8 website/lottery/scripts/selection_backtest.py`；具体方法和限制见
`website/lottery/README.md`。

`website/lottery` 是双色球/大乐透数据分析服务，默认端口 `5179`，由首页 01 Golden Hour 第 09 张卡片
按需启动。提供 6466 期官方开奖的可交互操作台（排序、号码筛选、走势矩阵、分组透视、CSV 导出、
逐期奖级明细）与完整研究报告，页面内「刷新数据」按钮可增量抓取最新开奖并重建页面。

技术：Python 标准库 `http.server` + numpy / pandas / requests，无前端构建；数据为官方接口
（与 500.com 交叉校验）导出的 CSV。

## 统一模型的浏览器跨域预检（2026-11-16）

个人资料库（5178）沿用主页统一模型路由；未单独指定模型时跟随 global，无需复制模型密钥。需要先在8080主页选择一个具体的全局文本模型；如果 global 为空，继承状态为 true 但统一模型未启用，各服务按原配置处理。

`ModelRoutingController` 为 `/api/models/**` 声明受限本机 CORS 来源（8080、5174、5176、5177、5178；localhost/127.0.0.1/IPv6回环），允许 Content-Type 与 X-Love530-Model。真实 OPTIONS 预检由 Spring MVC 在控制器之前处理，不能仅依赖控制器手写响应头。写请求自定义头、本机限制与“浏览器不能直接调用生成接口”的边界继续保留。

验证使用真实 MVC 配置：`mvn -pl website -am test "-Dtest=ModelRoutingControllerTest,ModelRoutingCorsIntegrationTest,ModelRoutingServiceTest,MimoModelRoutingTest" "-Dsurefire.failIfNoSpecifiedTests=false"`。CORS 声明修改后重启 website，再从5178验证 OPTIONS 与模型目录读取。
