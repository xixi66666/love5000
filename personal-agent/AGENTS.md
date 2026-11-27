# 个人长期资料库（5178）

- 登录默认打开 `/#overview`。通用导入 `/#import` 可仅归档或经确认分析。DeepSeek 原件识别通过官方 `/files`，使用根 `model.properties` 的 `deepseek.api-key`，上传设置一小时过期且处理后尝试删除。`/api/documents` 的原件保存在 `99-附件/导入资料/` 并排除在 Quartz 快照之外。

- 体检由独立的 `health` 应用（5180）负责。旧健康链接转向该应用，Quartz 与资料库继续读取已存在的体检 Markdown 和双链。体检原件仍排除出 Quartz。仓库、登录和文件处理基础组件位于 `vault-core`。

- 本模块是 Java 8 + Spring Boot 2.6.13 Maven 模块，主类 PersonalAgentApplication，服务标识保持 personal-agent。只由 website 03 Deep Woods“个人资料库”点击启动已构建 jar，不自动启停。
- 用户已授权替换原 Agent 业务。旧财务/对话/读书/记忆/自动复盘代码与森林背景已移除；旧 agent.mv.db、vault 与 backups 私人目录必须保留，不能自动导入为当前事实。
- 真正的 Obsidian Vault 是主资料源，Windows 默认 `D:/个人资料/Obsidian Vault/`，包含个人记录、AI 报告、Bases、模板和附件，可显式连接已有仓库。非 Windows 默认位于服务数据目录的 `knowledge-vault/`；状态、备份、构建仍在服务数据目录。测试必须显式指定临时 Vault，不得创建或读写 D 盘真实资料，也不得写入 python-a 的 Obsidian 目录。
- VaultService 负责路径约束、安全 YAML、原文与哈希、编辑前备份、初始化、文件检索。禁止另建资料数据库，禁止静默覆盖外部 Obsidian 修改，禁止虚构个人指标。
- QuartzService 调用 quartz/ 中真实 Quartz 5.1 源码构建私有快照。`/library/**`、搜索索引与附件必须登录且 no-store，资料指纹变化应停止提供旧快照。构建输出、输入与日志均为私人内容，不提交、不公开部署。
- 工作台默认深色，仓库与 Quartz 右栏仅在总览显示。笔记目录与链接在阅读页折叠展示，窄屏平铺。`/api/vault/overview` 提供最近笔记和最多 48 篇的双链图，`/api/note` 提供安全 Markdown 预览、双链和反链列表。两者使用同一笔记路径解析规则。Quartz 保留完整图谱、嵌入与 Bases。设计依据见 PRODUCT.md、DESIGN.md。
- AnalysisService 只在用户确认所选资料后调用 AiGateway；先校验内容版本，最多8份、每份2800字符片段。不执行笔记中的指令。排除草稿/归档/更正、AI 报告、模板和 ai_exclude；报告标记 AI 草稿并保留来源哈希，不写回事实。
- 模型复用 common 的 ModelRoutingClient.tryChat；服务原配置只读根 `model.properties`。模型选择器常驻顶部栏（`data-model-picker`，`data-model-scope="personal-agent"`、`data-model-theme="knowledge"`），登录后的总览、目录、健康、分析、设置各页都可直接切换；AI 分析页与设置页保留同一选择器的上下文入口，三处通过 `love530:modelselection` 事件同步。测试必须使用替身，禁止读取真实财务、健康资料或调用真实模型。
- LocalSecurity 保留本机、来源、Session、CSRF、限流及首页顶层跨站导航例外。该例外不得扩大到 API 或嵌入页面；Quartz 仅在专属路径允许所需内联脚本，不放开 unsafe-eval。导入笔记与 Bases 页面需清理活动 HTML。
- 业务保持 Controller 路由/校验、Service 文件/分析/构建职责分离。数据、API、端口、配置和启动方式修改同步根与 website 的 README/AGENTS。
- 运行 `mvn -pl personal-agent -am test`、`node --check personal-agent/src/main/resources/static/app.js`、`node personal-agent/scripts/check-quartz.mjs`；入口变更另跑 HomepageStaticAssetsTest/PersonalAgentControllerTest/PersonalAgentProcessManagerTest。
- Node.js 22+；首次在 quartz/ 执行 npm ci。postinstall 构建本地 D3/Pixi CSP 资源。完整配置与限制见 README.md；第三方核心本地补丁另见 quartz/AGENTS.md。
