# 个人 Agent

与 `website`、`lovestory` 同级的 **Java 8 + Spring Boot 2.6.13 Maven 模块**，默认只监听 `127.0.0.1:5178`。原生 HTML/CSS/JavaScript 由服务同端口托管，无 Python、Node 或前端构建依赖。

页面参考本机 `D:/Code/rea/_reference/motionsites/free-prompts/original-prompts.md` 的第3（黑白AI）、第10（玻璃仪表盘）、第11（双栏注册）份原创提示词，采用银白波浪、冰蓝点缀与玻璃面板。登录为双栏，工作台突出对话、真实记录数量、想法和复盘；七个工作区共享图标导航，手机端使用可展开导航。视觉素材和图标均为模块内SVG，不依赖外部图片/字体/CDN。快捷建议仅填入对话框，用户确认后才发送；减少动态效果偏好会关闭装饰动画。

## 启动

从仓库根目录构建：

```powershell
mvn -pl personal-agent -am package -DskipTests
java -jar personal-agent/target/personal-agent-0.0.1-SNAPSHOT.jar
```

也可以在 IDEA 运行 `com.example.personalagent.PersonalAgentApplication`。访问 `http://127.0.0.1:5178/`，首次设置个人空间密码（8–128字符）。之后只需登录此空间。该会话独立于 website，密码以随机盐 PBKDF2-HMAC-SHA256 哈希保存，写入 API 校验 CSRF。

重启 website 后，点击 **03 Deep Woods → 个人 Agent** 可启动已构建的 jar；已在线则复用。website 不自动运行 Maven、不自动启动 Agent，也不会在关闭时强杀它。端口被其他程序占用时拒绝启动，不停止其他应用。01 保留原文案、八个入口和背景，四个背景动画均未修改。

开发中可使用：

```powershell
mvn -pl personal-agent spring-boot:run
```

## 私人资料与 Obsidian

默认数据目录：`%LOCALAPPDATA%/Love530/PersonalAgent/`（非 Windows 为 `~/.local/share/Love530/PersonalAgent/`）。`PERSONAL_AGENT_DATA_DIR` 可以指定其他本地目录。不要将真实私人目录放入 Git。

```text
PersonalAgent/
├── agent.mv.db                 # H2 本地持久账本与记录、记忆、作业、配置
├── vault/                      # 可直接用 Obsidian 打开的 Markdown 仓库
│   ├── 00-导航/                # 首页、Bases 视图、最近历史备用页
│   ├── 10-我的资料/            # 当前档案、当前目标、历史更正
│   ├── 20-阅读与知识/          # 书籍、阅读笔记、原始笔记
│   ├── 30-生活与见解/          # 记录、人工心得
│   ├── 40-想法与行动/          # 想法、行动、进展、结果
│   ├── 50-财富/                # 当前概览、快照、复盘
│   ├── 60-对话与复盘/          # 对话、综合复盘
│   ├── 90-模板/
│   └── 99-附件/
└── backups/                    # 本地 zip 备份，包含业务状态与 Vault
```

在 Obsidian 桌面端选择“打开文件夹作为仓库”，打开 `vault`。服务关闭后，已经发布的记忆、记录和复盘仍可阅读。网页“设置与资料”显示真实路径。

目录按主题组织；事件文件按**录入年月**存放，文件名使用 UUID，不受重名、改标题或补录旧事影响。视图按**事件时间 → 录入时间 → ID**倒序排序。未知事件时间明确采用录入时间，页面标注“发生时间未注明”。当前实体与历史事件分开；修改产生更正历史，归档通过属性完成，不搬移旧文件。网页采用带数据版本的分页，新增、修改或删除后旧游标返回409，需回到最新列表。

网页维护系统记录和财务状态。Obsidian 可自由编辑 `30-生活与见解/人工心得`、`20-阅读与知识/原始笔记`，网页点击“重新整理资料索引”后可检索。系统生成文件采用临时文件原子替换和内容哈希校验；手工修改过则进入待核对，保留修改，不静默覆盖。`POST /api/data/conflicts/{id}/resolve` 的 `keep_manual=true` 会先另存手工副本再发布网页版本。当前汇总页冲突也会显示，需手工保留副本再恢复文件，不支持反向编辑系统字段。

Bases 使用 `.base` 表格、显式 sort 与属性过滤；没有 Bases 时仍能阅读普通 Markdown 和 `00-导航/最近历史.md`。该备用页最多展示最近500条，完整历史通过网页分页或 Obsidian 文件搜索查看。尚未在本机 Obsidian 实际加载 Bases 验证。

## 七个工作区

- **个人工作台**：展示真实记录与记忆数量、近期想法、对话及复盘。保存对话并按需调用云端模型，引用检索来源；没有密钥时原始消息仍保存，任务显示等待配置，可重试。
- **想法与行动**：先放入待选；选中后填写预期结果、验证标准、最小尝试及投入边界，跟踪行动、进展和证据。没有证据不允许确认成功或失败，未知默认待验证。
- **阅读与生活**：书籍资料、摘录、生活记录、个人见解；允许补录实际发生时间、关联书籍、标记重要。
- **我的财富**：本地账户、持仓、手工资产、负债、收支和交易；CSV先预览、再提交，可撤销批次；提供覆盖程度、截至时间、资产分类和快照。
- **长期记忆**：提炼明确提供的事实、偏好、观点和目标，保留原话证据及来源；可更正、停用、删除。
- **历史与复盘**：分页、类型/文字过滤、来源回看、复盘报告和未读提醒。
- **设置与资料**：模型名称与服务地址、复盘阈值/间隔/预算、公开资料开关、目录、待核对、索引和备份。

删除记忆保留独立原始记录，并记下来源排除项，避免同一来源再次提炼已删除记忆。删除原始来源同时删除直接关联的修改历史、记忆和派生报告副本及其文件。备份可能包含删除前的内容，删除前备份应由用户自行清理。设置中的“查看与恢复备份”可恢复本机ZIP；恢复前自动备份当前状态，并重应用删除墓碑和记忆排除项，防止旧备份复活已删除来源。恢复最多25,000文件、解压总量250MB、单文件100MB；拒绝越界路径，AI任务运行时等待其完成。恢复后的登录密码以所选备份中的个人空间密码为准。

更正来源正文/事件时间时，原记忆进入待核对，尚未完成的旧分析取消，关联报告保留当时依据并标记来源已更正；重新确认记忆后才继续作为当前事实。单个私人目录持有进程写锁，避免多个服务实例同时修改同一账本。

## 模型、书源与公开信息

密钥只从环境变量读取，不通过网页回显或写入数据库：

| 环境变量 | 作用 |
|---|---|
| `PERSONAL_AGENT_DATA_DIR` | 私人数据目录 |
| `PERSONAL_AGENT_PORT` | 默认5178 |
| `PERSONAL_AGENT_API_BASE` | 默认 `https://api.deepseek.com` |
| `PERSONAL_AGENT_MODEL` | 默认 `deepseek-flash`，可配置 |
| `PERSONAL_AGENT_API_KEY` | 当前模型供应商密钥 |
| `DEEPSEEK_API_KEY` | 仅在官方 DeepSeek 地址且没有专用 Key 时回退使用 |
| `PERSONAL_AGENT_SKILL_ROOTS` | 允许的 skill 根目录，Windows 用分号分隔；默认 `~/.codex/skills` |
| `PERSONAL_AGENT_BOOK_ROOTS` | 允许的书源根目录，默认 `D:/codex-book/books` |
| `PERSONAL_AGENT_BACKGROUND` | 默认true；false停用后台AI作业/复盘/行情周期 |

切换供应商地址时，同时通过环境变量配置对应地址和专用 Key 后重启；网页改变地址与原环境不一致时暂停调用，避免把旧供应商密钥发往新地址。网页设置保存非敏感字段，优先于环境中的模型名称与地址。模型名称是否对当前账户可用需由供应商确认；已验证模拟返回和无密钥行为，未使用真实密钥验证云端回答。

现有三本读书 skill（howard-marks-cycle、naval-wisdom、nison-candlestick）可先发现，再由用户选择导入。读取 `SKILL.md`、书源映射和受允许目录内的 Markdown 章节/主题索引，不执行 skill 的脚本。书源支持 Markdown/TXT，单文件最多5MB、一次书源最多50MB/500章；PDF/EPUB解析和语义向量检索未实现。新增书也可直接保存资料与个人笔记。检索支持中文子串，包括1–2字关键词，并返回书源路径、片段、稳定来源ID；当前为本地关键词检索，不依赖外部向量服务。

开启公开资料后，可补充官方 OpenAI 新闻 RSS 与美联储公开新闻 RSS，附链接、发布日期、抓取时间。请求固定公开地址，不传用户问题、私人事实或持仓作为搜索词；源不可用时继续基于本地资料回答，不编造实时信息。当前是有限的公开信息补充，并非任意互联网搜索引擎。

## 财务口径

金额与数量使用规范十进制字符串持久化，Java `BigDecimal` 运算；不使用浮点数算钱。账户/持仓初始记录区分期初与观测截至时间，观测不会重复叠加之前的收支。

- 转账只改变两个账户，投资买卖本金不记为收入/支出，手续费记费用。
- 借款增加现金和负债；偿还本金减少现金和债务，利息单列费用。
- 房产、股权、其他资产手工估值；支持账户余额、持仓和负债观测调整。
- 缺价格或汇率时总净资产为未覆盖，显示已覆盖部分，绝不按0价格或1汇率补齐。汇率目前手工录入 `POST /api/finance/rates`。
- 腾讯公开行情支持沪深A股及已明确代码的场内ETF；其他基金、港美股、房产等使用手工估值。行情网络失败保留旧值并标明过时；疑似大幅跳价/公司行为暂停市场变化触发，需持仓观测核对。
- 外部ID按来源和账户范围去重；CSV整批校验/提交，错误不部分入账。撤销停用原事件/检查点并重放后续真实变动，保留审计记录。
- 服务运行时按配置间隔刷新行情；重大记录/结果及财富阈值触发复盘，先合并近期变化、检查冷却和每日预算。财富比较基线不随每次报价重置；缺价、过时、未知和异常情况下暂停财富触发。零或负净资产不使用净资产百分比规则。网页报告生成后以未读提示呈现，无定时日报、外部推送或自动下单。

## API 与验证

业务成功统一 `{success:true,data:...}`；失败 `{success:false,message:...}`。列表通常 `{items,next_cursor,revision}`，财务列表使用 `{items,total,limit,offset}`。健康接口仅返回 `{success:true,service:"personal-agent"}`。

主要路由：`/api/auth/{status,setup,login,logout}`、`/api/settings`、`/api/chat/messages`、`/api/conversations`、`/api/jobs`、`/api/notes`、`/api/books`、`/api/search`、`/api/ideas`、`/api/actions`、`/api/memories`、`/api/timeline`、`/api/reviews`、`/api/notifications`、`/api/data/{status,reindex,backup,backups,restore}`；`/api/finance/{accounts,assets,events,summary,snapshots,imports,quotes/refresh,rates}`。写入需要登录及 `X-CSRF-Token`。

```powershell
mvn -pl personal-agent -am test
mvn -pl website -am test
node --check personal-agent/src/main/resources/static/app.js
node --check website/src/main/resources/static/js/script.js
```

测试使用本地临时目录、构造财务数据与模型/行情替身，不读取真实财务或调用真实云端API。已涵盖10年/10,000条历史分页、不重复与游标失效、来源删除、手工笔记保护、短中文检索、重启持久化与备份。账本版本缓存减少重复重算，但 Store 的事务修改会复制当前文档集合；10万财务事件性能目标尚未验证，不宣称500ms或100ms指标已经达成。

2026-10-13 验证：新服务34项JUnit通过，website138项测试通过，common回归通过；原生脚本语法与主页动效检查通过。实际浏览器验证了初始化、想法/行动、账户及财富汇总，桌面与390px移动端无横向溢出。正式5178已启动且空间未初始化，测试账户只在独立15178测试目录。

本地 H2 文件不提供网络数据库服务/控制台；DAO + XML Mapper 负责持久化。版本升级涉及存储模式时先备份、增加明确迁移，禁止删库重建。当前仅 schema v1，不含自动跨版本迁移；备份恢复只支持当前存储格式。
