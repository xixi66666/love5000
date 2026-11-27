# 个人长期资料库 · Obsidian + Quartz + AI

## 资料总览与通用导入

打开裸地址、首次设置密码或重新登录后进入资料总览（`/#overview`）。已有会话可通过带片段的地址直达笔记或子页面。每个方向提供能收录的材料、当前笔记数和可直接带入分析页的问题。除个人档案、财务、健康、工作、生活、目标与复盘外，新增学习与技能（`45-学习与技能/`）、家庭与关系（`55-家庭与关系/`）、居住与物品（`65-居住与物品/`）、证件与合同（`70-证件与合同/`）。资料目录仍在 `/#notes`，总览末尾可发起跨领域复盘。

总览按文件编辑时间展示最近五篇，并以最近编辑的最多 48 篇非模板笔记绘制双链图。鼠标或键盘聚焦节点可查看标题，点击进入笔记阅读。阅读页支持常见 Markdown 与表格、可点击的 `[[双链]]`、标题目录、反向链接、属性、Markdown 全文切换和 Obsidian 原笔记入口。完整 Vault 图谱、附件嵌入及 Bases 在生成后的 Quartz 浏览页查看。工作台默认深色，可切换浅色。

`GET /api/vault/overview` 返回 `recent/nodes/edges/edits/total`，可传 `domain` 查看该领域。各领域目录显示局部双链图、最近笔记及近六个月按最后编辑月份统计的笔记数。健康图谱额外包含体检解读草稿，连线来自实际 Obsidian 双链。`GET /api/note` 保留原有字段并附带 `reading_html/reading_truncated/incoming/outgoing/modified_at`。阅读预览最多 120,000 字符，转义笔记里的 HTML，嵌入图片留给 Quartz 或 Obsidian 查看。两个接口均需本机会话并禁止缓存。

打开「导入资料」选择领域和文件，点击「同意发送原件并分析」后，分析跟随顶部栏模型选择器：选中 DeepSeek 型号时，服务把完整原件发给 DeepSeek 官方 `/files`，再以该型号（默认 `deepseek-flash`）生成 Markdown 草稿；项目根 `model.properties` 的 `deepseek.api-key` 必须是官方密钥。选中其他提供方时，只有 txt/md/csv 等文本类附件改走统一模型入口，PDF、图片与 Office 原件会被拒绝（HTTP 422）并提示切换到 DeepSeek，因为只有官方文件接口能读取这些原件。普通笔记分析同样使用模型选择器。上传时设置一小时过期，模型调用结束后尝试删除远端临时文件。发送前可自行遮盖文件里的敏感内容。

支持 PDF、PNG/JPEG/GIF/WebP、TXT/Markdown、Word、PowerPoint、Excel 和 CSV，单份不超过 12 MB。也可选择「仅归档」，此时只写入 Vault。原件在 `99-附件/导入资料/`，Markdown 在选定领域。原件通过登录后的下载接口获取，Quartz 构建跳过该目录。自动生成的笔记标记为待核对草稿，排除在普通 AI 来源之外。

| 方法与路径 | 输入与用途 |
|---|---|
| `POST /api/documents` | multipart `file/workspace/domain/title/mode`，可选 `date` → Markdown `path`。`mode=analyze` 另须 `consent=true`，`mode=archive` 仅归档。 |
| `GET /api/documents/original?path=...` | 按导入笔记路径下载经校验的原件 |
| `POST /api/analyses/preview` | JSON `question/domain`；可选 `source_path` 指定只预览一份来源 |

写请求使用原有 Session 和 `X-CSRF-Token`。构建及测试使用 `mvn -pl personal-agent -am package`，前端可用 `node --check` 检查 `areas.js`、`import.js` 和 `app.js`。

## 健康管理入口

体检已迁入同一 Vault 上的独立 [健康管理](../health/README.md)（5180）。`/#health` 和 `/#health-import` 分别跳转到档案总览和导入。个人资料库继续索引体检笔记和草稿，其文件写入由健康管理负责。

> 模型配置已统一：模型目录、密钥和各服务原配置只从项目根目录 `model.properties` 读取（模板 `model.properties.example`）。本文中出现的模型环境变量、`deepseek.local.json`、`INTRO_*` / `MIMO_*` 示例仅作历史说明，不再生效。


`personal-agent` 已从原来的个人 Agent 重构为个人长期资料库。以真实 Obsidian Vault 为资料原本，Quartz 5.1.0 提供阅读、全文搜索、双链图、反向链接和 Bases 多视图；Java 服务提供本机认证、资料记录、编辑版本保护与主动式 AI 分析。默认访问 `http://127.0.0.1:5178/`。

## 启动与首次使用

需要 Java 8+、Maven、Node.js 22+（本次使用 Node 24 验证）。Quartz 核心源码随本模块提供，首次安装依赖：

```powershell
cd personal-agent/quartz
npm ci
cd ../..
mvn -pl personal-agent -am package
java -jar personal-agent/target/personal-agent-0.0.1-SNAPSHOT.jar
```

也可在 IDEA 运行 `com.example.personalagent.PersonalAgentApplication`。开发命令为 `mvn -pl personal-agent spring-boot:run`（先安装 common 或从 IDEA 运行）。

1. 打开5178，首次设置新的资料空间密码（8–128字符）。原服务密码不自动从旧 H2 导入。
2. 点击“初始化目录与模板”。Windows 默认 Vault 在 `D:/个人资料/Obsidian Vault/`。首次需要在 Obsidian 中选择“打开文件夹作为仓库”，打开这一目录，之后网页深链可以直接打开笔记。
3. 在 Obsidian 编辑，或在网页“记录资料”录入财务、健康、工作等记录。网页编辑旧笔记时使用 SHA-256 版本校验，原文变化则返回409，需重新加载、合并。
4. 点击“生成 / 更新浏览页”，完成后打开 `/library/`。Quartz 是实际构建的资料页，不是仿制界面。修改任何已扫描资料后，旧快照停止提供，重新生成即可。
5. 在“AI 分析”输入问题，先检索、预览和勾选来源，再确认发送，报告保存到 Vault。

website 的 **03 Deep Woods → 个人资料库** 仍只在点击时启动已构建 jar；模块名、健康标识和启动 API 保持兼容。不会自动运行 Maven，不随 website 自动启停。更新 jar 后需重启已在运行的旧实例。

## 真实资料与目录

```text
D:/个人资料/Obsidian Vault/      # Windows 默认真实 Obsidian Vault
├── .obsidian/
├── index.md
├── 00-导航/个人资料.base       # 全部、卡片、财务、健康、工作等视图
├── 10-个人档案/
├── 20-财务/
├── 30-健康/
├── 40-工作/
├── 50-生活/
├── 60-目标与复盘/
├── 80-AI分析/                 # 带来源与哈希的 AI 草稿
├── 90-模板/
└── 99-附件/

%LOCALAPPDATA%/Love530/PersonalAgent/
├── knowledge-state.json       # 登录哈希、仓库选择、分析任务状态；不保存模型密钥
├── .knowledge.lock            # 防止多个新服务同时操作同一资料空间
├── note-backups/              # 每次网页编辑前的原始 Markdown 副本
├── quartz-builds/<UUID>/
│   ├── source/                # 经过文件边界校验的私有输入快照
│   ├── site/                  # HTML、搜索索引、附件与图谱资源
│   └── build.log              # 本地构建日志，可能含私人标题，禁止公开
├── agent.mv.db                # 旧 H2，保留；新服务不读取、迁移或删除
├── vault/                     # 旧 Vault，保留；不会当作新的当前事实自动导入
└── backups/                   # 旧备份，保留
```

Windows 的资料原本与服务状态分别存放：全部个人记录、AI 报告、Bases、模板和附件位于 D 盘 Vault；登录状态、网页编辑前副本与 Quartz 构建快照仍在服务状态目录。非 Windows 服务状态默认为 `~/.local/share/Love530/PersonalAgent/`，默认 Vault 为其下的 `knowledge-vault/`。修改 `PERSONAL_AGENT_DATA_DIR` 不会改变 Windows 默认 Vault；可用 `PERSONAL_AGENT_VAULT_DIR` 单独覆盖。网页已保存的仓库选择优先于默认路径和环境变量；已有用户如需切换，先完整复制原 Vault，再在设置中连接新目录。修改默认路径不会自动迁移或删除旧文件。分析或构建运行时禁止切换。

初始化只添加缺失的目录、说明与模板，不写入虚构的资产、健康指标或工作成果。文件名使用 UUID，标题保存在属性中；Obsidian 的文件移动与外部编辑会在下一次请求/刷新时被读取。不依赖 MySQL、H2 或另一份资料数据库。

### 属性约定

```yaml
---
title: 月末财务快照
domain: finance
record_type: observation
observed_at: "2026-11-16"
recorded_at: "2026-11-16T08:00:00Z"
status: current
source: 本人核对后的账户记录
ai_exclude: false
tags: [财务, 快照]
---
```

以上仅为结构示例，不包含真实资产值。`domain` 常用值为 profile、finance、health、work、life、goals、analysis；支持在 Obsidian 中继续扩展属性和目录。

- `observed_at`：事实发生/截至时间；未知时留空，不能用文件修改时间代替。
- `recorded_at`：录入时间。历史记录使用 `status: historical`，可以用于回顾，但不能当作今天状态。
- `status: draft / archived / corrected`：不会作为 AI 事实来源自动检索。AI 报告另有 `origin: ai_generated`，默认也排除。
- `source`：来源、材料名称或核对方式。健康指标写明单位、参考范围与就诊日期；财务金额建议用带币种的十进制字符串，不累加多份资产快照。
- `ai_exclude: true`：这篇笔记不出现在 AI 来源候选中。90-模板目录始终排除。
- 正文使用 Markdown、`[[双链]]` 和 Obsidian 属性。网页保存原文，不把模型建议自动写成事实。

## AI 分析

调用链沿用 common 的 `ModelRoutingClient.tryChat("personal-agent", ...)`。登录后每个页面的顶部栏都常驻模型选择器（AI 分析页与“仓库与设置”另有同一选择器的上下文入口，三处同步），无需进入某个页面才能切换。默认跟随8080主页；请先在主页选择具体的全局文本模型，在5178选择“跟随主页”，无需重复配置密钥。页面展示的“服务原配置”只是回退说明，不表示当前必须使用该配置。可跟随主页或选择独立文本模型；统一入口明确返回原配置时才使用专用环境配置。缺密钥任务显示 `waiting_configuration`，不会捏造回答。网络错误不会擅自换模型。

每次分析先在本地按关键词与时间排序检索，最多选择8份资料；每份正文片段最多2800字符，预览会标明截断，用户确认后才发送。此实现是有明确范围的本地关键词检索，不是全库向量 RAG 或无限上下文分析。应按领域/时间拆分过大的问题。

分析会检查所选内容哈希；检索后资料发生变化则返回409，需重新选择。报告记录来源路径、SHA-256 与引用编号，标记为 `draft`。生成期间其他资料变化会在报告中提示；无效引用编号会标记为待核验。报告不代表模型结论已经被证实。

模型提示要求区分事实、推测、缺失和建议，保留历史时点、相互矛盾的资料、金额币种与指标单位；健康建议限定为趋势整理和就医沟通，不代替诊断或用药；财务不保证收益。没有自动交易、后台定时上传、任意联网搜索、医疗诊断或外部消息推送。

## 配置

| 环境变量 | 默认/作用 |
|---|---|
| `PERSONAL_AGENT_PORT` | 5178 |
| `PERSONAL_AGENT_DATA_DIR` | 私人服务状态、备份和构建目录；Windows 默认 `%LOCALAPPDATA%/Love530/PersonalAgent/` |
| `PERSONAL_AGENT_VAULT_DIR` | 覆盖初始 Vault 路径；Windows 默认 `D:/个人资料/Obsidian Vault/`；网页已保存的连接选择优先 |
| `PERSONAL_AGENT_QUARTZ_DIR` | Quartz 源码目录；默认从当前/上级目录定位 `personal-agent/quartz` |
| `PERSONAL_AGENT_NODE_COMMAND` | node；可指定解释器完整路径 |
| `PERSONAL_AGENT_API_BASE` / `PERSONAL_AGENT_MODEL` / `PERSONAL_AGENT_API_KEY` | 已移除；服务原配置改由根目录 `model.properties` 的 `service.personal-agent` 提供 |
| `DEEPSEEK_API_KEY` / `MODEL_HUB_URL` / `MODEL_ROUTING_STATE` | 已移除；模型只读 `model.properties`，网关与选择状态路径固定 |

旧 `PERSONAL_AGENT_BOOK_ROOTS`、`PERSONAL_AGENT_SKILL_ROOTS`、`PERSONAL_AGENT_BACKGROUND` 已不再使用。

## API

成功统一 `{success:true,data:...}`；失败 `{success:false,message:...}`。除 `/api/health` 和登录状态/初始化/登录外均要求本机 Session，写请求加 `X-CSRF-Token`。没有跨域私人 API。认证后响应及资料页使用 `no-store`。

| 方法 | 地址 | 请求/用途 |
|---|---|---|
| GET | `/api/health` | `{success:true,service:"personal-agent"}`，不含私人字段 |
| GET | `/api/auth/status` | initialized、authenticated、csrf_token |
| POST | `/api/auth/setup`、`/api/auth/login` | `{password}` |
| POST | `/api/auth/logout` | 锁定空间 |
| GET | `/api/vault` | 当前路径、领域数量、可分析数量、资料指纹 |
| POST | `/api/vault/connect` | `{path}`，连接已有仓库 |
| POST | `/api/vault/initialize` | 添加缺失说明、模板与 Bases |
| GET | `/api/notes?q=&domain=&offset=0&limit=40` | 本地标题/正文检索，最大每页100 |
| GET | `/api/note?path=...` | 原文、属性、版本、双链与反向链接 |
| POST | `/api/notes` | `{domain,content}` 创建，或 `{path,content,expected_revision}` 编辑 |
| GET | `/api/settings` | 当前目录、服务原模型与 Quartz 状态，不回显密钥 |
| POST | `/api/analyses/preview` | `{question,domain}`，返回待确认来源与版本 |
| POST | `/api/analyses` | `{question,domain,sources:[{path,revision}],consent:true}`，排队执行 |
| GET | `/api/analyses` | 分析状态、引用清单与报告路径 |
| GET | `/api/quartz` | 安装、构建、同步状态 |
| POST | `/api/quartz/build` | 使用当前快照异步生成，最长180秒 |
| GET | `/library/**` | 登录后读取真实 Quartz 产物，包含搜索索引与附件 |

原对话、财务账本、读书 skill 导入、自动记忆与复盘、旧备份恢复 API 已移除。归档通过编辑笔记 status 完成，没有网页批量删除接口。

## 边界、备份与部署

只监听回环地址。保留独立 Session、PBKDF2 密码哈希、CSRF、来源校验与 localhost → 127.0.0.1 首页导航兼容。`.obsidian`、`.git`、隐藏目录和链接不进入扫描；笔记路径须限制在所选根目录。单文本5MB、扫描最多20,000文件/500MB，超限明确失败，不把部分扫描当成完整数据。

Quartz 的 Markdown/虚拟页面经过 HTML 清理；D3/Pixi 为锁定的本地资源，Pixi 使用 CSP 兼容实现，保留禁止 `unsafe-eval`。统计、远程字体、远程数学/Mermaid 和社交嵌入关闭。原生 Obsidian 插件并不会自动运行在 Quartz 中；Dataview 查询、插件专有视图、PDF/图片 OCR、语义向量检索和任意 Bases 公式的完全兼容均不作保证。

网页编辑会备份原文；Obsidian 外部编辑需由 Obsidian 文件恢复、系统备份或你自己的同步方案保护。服务不把私人 Vault 推送 GitHub。应独立备份所选 Vault、knowledge-state.json、note-backups；旧备份格式不自动恢复到新服务。成功构建后清理过期的生成快照，日志和构建产物也属于私人内容。大容量长期库的性能尚未做规模基准。

可以用[离线 Vault 快照工具](../tools/vault-snapshot/README.md)给显式指定的 Vault 创建和校验归档，并在新目录演练恢复。服务状态和笔记编辑备份放在独立的数据目录，需要按实际位置单独备份。

部署需同时保留 jar、`quartz/` 源码及其 npm 依赖；不能只拷贝 jar 后期待生成资料页。目录移动时可通过上述环境变量明确指定。生产公网访问还需单独设计 HTTPS 和认证部署，本版本按本机个人使用实现。

## 验证

```powershell
mvn -pl personal-agent -am test
mvn -pl website -am test "-Dtest=HomepageStaticAssetsTest,PersonalAgentControllerTest,PersonalAgentProcessManagerTest" "-Dsurefire.failIfNoSpecifiedTests=false"
node --check personal-agent/src/main/resources/static/app.js
node personal-agent/scripts/check-quartz.mjs
```

JUnit 使用构造 Vault 和模型替身，覆盖本机认证、CSRF、导航来源、外部修改、YAML 安全解析、目录越界、来源确认/版本、无模型状态、报告引用、过期快照拒绝和仓库切换。Windows 未授予创建符号链接权限时该项会明确跳过。Quartz 脚本实际生成笔记、Bases、双链与索引，并检查活动 HTML 和远程图谱脚本。浏览器验收使用独立15178测试空间，不读取私人记录或调用真实模型。

上游 [Quartz](https://github.com/jackyzha0/quartz) v5.1.0，MIT 许可证见 `quartz/LICENSE.txt`；本地适配见 `quartz/AGENTS.md`。
