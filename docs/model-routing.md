# 统一大模型入口

主页“全局模型”设置文本默认模型；各工作台可选择“跟随主页”“服务原配置”或独立模型。
独立覆盖保留到恢复跟随。保存后下一次请求生效，正在执行的任务不切换，无需重启。

## 盘点（2026-10-20）

| 来源 / 能力 | 模型或配置 | 实际状态 |
| --- | --- | --- |
| DeepSeek / 文本 | `deepseek-flash`、`deepseek-v4-pro` | 已用现有私有凭据查询 `/models`，两个模型均被列出，未执行收费生成 |
| Xiaomi MiMo / 文本 | `mimo-v2.6-pro`、`mimo-v2.6-flash` | 复用现有私有 MiMo Key；目录核验及统一网关真实生成均已通过（Pro JSON、Flash 文本），支持全局选择和局部覆盖 |
| Strata / 本机文本 | Qwen3.8-Flash-Next IQ3_S，9999 | 当前离线；安装完整时可从选择器启动，读取真实模型 ID，首次生成加载权重 |
| Skill Finder / 文本 | `INTRO_API_BASE`、`INTRO_MODEL` | 读取私有 .env 及引用的密钥文件；相同地址与密钥来源合并展示 |
| 个人 Agent / 文本 | `PERSONAL_AGENT_*` | 显式配置提供方时纳入目录，也可直接使用统一 DeepSeek |
| OpenAI 兼容 / 文本 | `OPENAI_BASE_URL`、`OPENAI_API_KEY` | 当前环境未配置 Key，配置后读取真实目录 |
| 图片工作台 / 图片 | `gpt-image-2.5-sunburst`、`gpt-image-2.5-flare` | 配置预设，未用提供方密钥核验；工作台独立选择 |
| Python A / 截图 | `VISION_MODEL`，默认 `gpt-4o-mini` | 保留原视觉配置 |
| Skill Finder / 语音 | MiMo TTS、Whisper 字幕 | 保留专用音频配置 |
| AIMedia / 视频 | H3 / ComfyUI，8189 | 继续由“模型与视频”页管理 |

“目录已验证”只表示接口可访问、模型被列出，不代表余额充足、实际生成成功或 GPU 权重已加载。
目录缓存30分钟，可手动刷新。连接失败或未配置的来源显示原因，不允许直接选中。

## 接入范围

python-a 的研究分析、Scrapling 的选择器修复、Skill Finder 的中文介绍与补全、
个人 Agent 的对话/记忆/复盘接入统一文本路由。原有 Session、CSRF、采集和失败降级保持。
Scrapling 使用统一模型时不需要填写旧页面 Key。

图片、截图、语音、视频有不同能力要求，保持专用模型；图片工作台提供独立下拉，
JSON/multipart 生成请求均使用所选模型，后端白名单校验。
quant-a、lovestory、Prompt Console 当前没有文本模型调用，不放置无效按钮。
last30days 的外部 skill/CLI 编排保持原配置，未伪称已经接入统一路由。

## 配置与边界

website `integration/models` 提供目录、选择与文本代理，不承接微服务业务。
Java 客户端和 JSON 传输在 `common/ai`；Python 公共源码在 `website/model-routing/`，
薄适配器只绑定服务标识与同步/异步方式。Python 部署副本 `_model_routing.py` 随各服务打包，
Docker 或独立复制服务不再依赖仓库目录；只维护公共源码，运行 `python scripts/sync-model-routing.py` 同步，
`python scripts/sync-model-routing.py --check` 检查三个副本，公共客户端测试也会检查一致性。

服务端默认网关 `http://127.0.0.1:8080`，`MODEL_HUB_URL` 可指定其他回环端口。
选择文件默认根 `.runtime/model-routing.json`（gitignored），仅存模型 ID 和覆盖，不存密钥。
`MODEL_ROUTING_STATE` 可指定绝对路径，各服务必须指向同一文件。
website 从根或 website 目录启动均可定位配置；独立 jar 部署通过环境变量提供凭据和共享状态路径。

密钥只从已有环境变量、python-a 私有 JSON、Skill Finder 私有 .env 及其引用文件读取，
不回显、复制或提交。上游地址来自管理员配置，浏览器不能传入任意 URL、密钥或命令。
入口限制回环来源、本机 Host 和已知服务端口 Origin，写请求需 `X-Love530-Model: 1`。
生成代理只允许服务端调用。未选择统一模型时保留原逻辑；已选择但网关离线时报错，不静默换模型。
状态原子保存失败时，不更新内存选择，不谎报成功。

### 单次生成与公共传输（2026-10-21）

四个文本服务直接请求 `POST /api/models/complete/{service}`，不再先查询 `effective`。
网关在一次请求中确定全局/局部选择：统一模型返回 HTTP 200 和 Chat Completions JSON；
明确使用服务原配置时返回 HTTP 204（空响应），且不会调用任何提供方。
旧 `/chat/{service}` 保留兼容，原配置仍返回 409；`effective` 只用于页面状态展示。

收到 204 后，原配置的提供方地址、密钥、模型名仍由各业务服务解析，
HTTP 鉴权、JSON 编解码、禁止重定向、响应大小限制及错误脱敏改用公共传输。
python-a 使用标准库传输，Scrapling/Skill Finder 复用已有异步连接池；
Skill Finder 的原生模型重试/降级和个人 Agent 的等待配置任务状态保留。
原配置凭据不发送给统一网关，统一模型请求也不会读取原配置密钥。

只有连接明确被拒绝且持久化状态没有统一模型（或本服务显式为 `native`）时，允许离线使用原配置。
读取超时、HTTP 4xx/5xx、重定向、无效响应和损坏状态文件均报错，不自动改用其他模型，
避免已被上游接受的请求在超时后又产生一次原模型调用。

目录探测使用独立刷新锁，完成后一次性发布不可变快照，不占用选择锁。
已有目录快照时生成直接使用快照；页面目录请求按 30 分钟有效期刷新，也可手动刷新。
刷新期间，生效模型查询、已有模型生成和恢复原配置继续执行；首次启动尚无快照时需要等待首次探测。
选择在请求开始时确定，正在执行的请求不随页面切换而改变。

本次升级先重启已重新打包的 website，再重启 personal-agent、python-a、Scrapling 和 Skill Finder。
新客户端依赖 `/complete` 协议；旧网关返回 404 时会明确报错，不静默绕过统一选择。
本次未修改前端资源，无需重新构建 React/Vue；图片、视觉、语音与视频入口保持原配置。

### MiMo V2.6 文本模型

统一入口自动读取 `MIMO_API_KEY`、`MIMO_API_BASE` 和 `MIMO_CHAT_MODELS`：环境变量优先，
没有设置时复用 `website/skill-finder/backend/.env`，不复制密钥。
默认官方 OpenAI 兼容地址 `https://api.xiaomimimo.com/v1`，使用官方支持的 `Authorization: Bearer` 鉴权。
默认文本列表为 `mimo-v2.6-pro,mimo-v2.6-flash`，还会与实时 `/models` 结果取交集，认证失败时不能选择。
目录中的 ASR/TTS 不进入文本列表；即将下线的 V2.5 与定制 Ultraspeed 也不自动加入。
如已购买定制服务，可显式扩展 `MIMO_CHAT_MODELS`，最终仍需模型目录核验。

模型 ID 为 `mimo:mimo-v2.6-pro` / `mimo:mimo-v2.6-flash`，直接复用现有主页和工作台选择器。
接入不会修改已经保存的全局或局部选择；需要使用时在页面选择对应 MiMo 型号即可。
现有 `MIMO_TTS_MODEL=mimo-v2.5-tts`、音色和配音流程保留。

网关将现有微服务的 `max_tokens` 映射为 MiMo 官方 `max_completion_tokens`；已显式传入后者时优先保留。
未指定预算时使用8192；默认 `thinking.type=disabled`，适配短输出选择器修复与 JSON 解析。
服务端请求可以显式开启思考；此时按官方约束移除自定义 `temperature` / `top_p`，
预算同时覆盖思考和最终输出。`response_format=json_object` 原样传递，提示词仍须要求输出正确 JSON 结构。
鉴权、JSON 和模型选择失败均沿用已有脱敏错误，不回显密钥，不自动切换其他提供方。

官方资料：[首次调用](https://mimo.mi.com/docs/zh-CN/quick-start/summary/first-api-call)、
[模型列表](https://mimo.mi.com/docs/zh-CN/quick-start/summary/model)、
[深度思考](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/text-generation/deep-thinking)、
[结构化输出](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/text-generation/structured-output)。

浏览器默认本机8080，改端口需配置宿主 `data-model-hub` 并更新已知 Origin 清单。
云端独立服务保持原配置，此入口不扩大为远程管理接口。

## API

| 请求 | 用途 |
| --- | --- |
| `GET /api/models` | 脱敏目录、检查时间、选择和服务清单 |
| `POST /api/models/refresh` | 重读配置与真实模型目录，不执行生成 |
| `GET /api/models/effective/{service}` | `active`、`modelId`、`selection`、`inherited` |
| `PUT /api/models/selection/{service}` | JSON `{"modelId":"deepseek:deepseek-flash"}`；空串跟随主页，`native` 使用原配置 |
| `POST /api/models/local/strata/start` | 复用固定启动器并刷新目录 |
| `POST /api/models/chat/{service}` | 服务端非流式文本 Chat Completions 代理 |
| `POST /api/models/complete/{service}` | 单次路由与生成：200 为统一模型结果，204 为服务原配置，其他错误不回退 |
| `GET :8082/api/image-templates/models` | 图片预设、默认值与未核验说明 |

服务标识：global（仅选择）、python-a、scrapling-ui、skill-finder、personal-agent。
错误返回 `success=false` 和脱敏 `message`：400参数、403来源、409不可选模型或原配置、
502上游失败、503保存失败或已选模型不可用。

图片原生成接口新增可选 JSON/表单 `model` 字段。省略使用 `OPENAI_IMAGE_MODEL`；
`OPENAI_IMAGE_MODELS` 配置逗号白名单，自动包含默认模型。浏览器只在 `imagetemplate.model` 保存名称。

## 验证

修改共享选择器后执行 `python scripts/sync-model-picker.py`。首次接入运行 `mvn test`，
重新构建并重启 website、personal-agent、imagetemplate 和修改过的 Python 服务；后续模型切换无需重启。
Skill Finder 运行前端 lint/typecheck/test/build、后端 pytest/ruff；Scrapling 重建前端并运行后端 unittest。
公共客户端回归：`python -m unittest discover -s website/model-routing -p 'test_*.py'`。
公共客户端改动后先运行 `python scripts/sync-model-routing.py`，再运行上述测试与 `--check`。
调用链收敛回归：`mvn -pl website,personal-agent -am test`、python-a/Scrapling unittest、Skill Finder pytest；
覆盖单次请求、204 原配置、超时不回退、原配置认证/重试、缺少密钥任务状态及慢目录刷新期间的并发生成。

手动验证全局默认、局部覆盖、恢复跟随、重启持久化、离线失败、桌面/手机、键盘单选、Esc 和搜索错误状态。

MiMo 回归：`mvn -pl website -am test`，`MimoModelRoutingTest` 覆盖私有配置复用与环境变量优先、
TTS/ASR/旧型号过滤、全局/局部路由、令牌字段转换、思考模式和失败脱敏。

2026-10-20 验证结果：website/common 共166项测试通过，website jar 已重新打包。
隔离网关使用真实私有凭据验证 Pro 的 JSON 输出与 Flash 的普通文本输出均成功；
两次请求只包含公开测试文本，未切换实际业务服务的全局/局部选择，也未修改 TTS 配置。
