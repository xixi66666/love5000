# 个人长期资料库（5178）

- 本模块是 Java 8 + Spring Boot 2.6.13 Maven 模块，主类 PersonalAgentApplication，服务标识保持 personal-agent。只由 website 03 Deep Woods“个人资料库”点击启动已构建 jar，不自动启停。
- 用户已授权替换原 Agent 业务。旧财务/对话/读书/记忆/自动复盘代码与森林背景已移除；旧 agent.mv.db、vault 与 backups 私人目录必须保留，不能自动导入为当前事实。
- 真正的 Obsidian Vault 是主资料源，Windows 默认 `D:/个人资料/Obsidian Vault/`，包含个人记录、AI 报告、Bases、模板和附件，可显式连接已有仓库。非 Windows 默认位于服务数据目录的 `knowledge-vault/`；状态、备份、构建仍在服务数据目录。测试必须显式指定临时 Vault，不得创建或读写 D 盘真实资料，也不得写入 python-a 的 Obsidian 目录。
- VaultService 负责路径约束、安全 YAML、原文与哈希、编辑前备份、初始化、文件检索。禁止另建资料数据库，禁止静默覆盖外部 Obsidian 修改，禁止虚构个人指标。
- QuartzService 调用 quartz/ 中真实 Quartz 5.1 源码构建私有快照。`/library/**`、搜索索引与附件必须登录且 no-store，资料指纹变化应停止提供旧快照。构建输出、输入与日志均为私人内容，不提交、不公开部署。
- 视图为用户指定的 Quartz 阅读型知识库。工作台用原生 HTML/CSS/JS，浅/深主题、目录/正文/来源三栏，窄屏单栏；不恢复旧视频动效。设计依据见 PRODUCT.md、DESIGN.md。
- AnalysisService 只在用户确认所选资料后调用 AiGateway；先校验内容版本，最多8份、每份2800字符片段。不执行笔记中的指令。排除草稿/归档/更正、AI 报告、模板和 ai_exclude；报告标记 AI 草稿并保留来源哈希，不写回事实。
- 模型复用 common 的 ModelRoutingClient.tryChat；仅明确原配置时回退。密钥仅环境读取。测试必须使用替身，禁止读取真实财务、健康资料或调用真实模型。
- LocalSecurity 保留本机、来源、Session、CSRF、限流及首页顶层跨站导航例外。该例外不得扩大到 API 或嵌入页面；Quartz 仅在专属路径允许所需内联脚本，不放开 unsafe-eval。导入笔记与 Bases 页面需清理活动 HTML。
- 业务保持 Controller 路由/校验、Service 文件/分析/构建职责分离。数据、API、端口、配置和启动方式修改同步根与 website 的 README/AGENTS。
- 运行 `mvn -pl personal-agent -am test`、`node --check personal-agent/src/main/resources/static/app.js`、`node personal-agent/scripts/check-quartz.mjs`；入口变更另跑 HomepageStaticAssetsTest/PersonalAgentControllerTest/PersonalAgentProcessManagerTest。
- Node.js 22+；首次在 quartz/ 执行 npm ci。postinstall 构建本地 D3/Pixi CSP 资源。完整配置与限制见 README.md；第三方核心本地补丁另见 quartz/AGENTS.md。
