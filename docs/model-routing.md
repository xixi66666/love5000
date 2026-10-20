# 统一大模型入口

主页“全局模型”设置文本默认模型；各工作台可选择“跟随主页”“服务原配置”或独立模型。
独立覆盖保留到恢复跟随。保存后下一次请求生效，正在执行的任务不切换，无需重启。

## 盘点（2026-10-20）

| 来源 / 能力 | 模型或配置 | 实际状态 |
| --- | --- | --- |
| DeepSeek / 文本 | `deepseek-flash`、`deepseek-v4-pro` | 已用现有私有凭据查询 `/models`，两个模型均被列出，未执行收费生成 |
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
Java 客户端在 `common/ai`；Python 标准库客户端在 `website/model-routing/`，薄适配器在各微服务中。
独立复制部署使用统一入口时，需一并携带该公共 Python 目录。

服务端默认网关 `http://127.0.0.1:8080`，`MODEL_HUB_URL` 可指定其他回环端口。
选择文件默认根 `.runtime/model-routing.json`（gitignored），仅存模型 ID 和覆盖，不存密钥。
`MODEL_ROUTING_STATE` 可指定绝对路径，各服务必须指向同一文件。
website 从根或 website 目录启动均可定位配置；独立 jar 部署通过环境变量提供凭据和共享状态路径。

密钥只从已有环境变量、python-a 私有 JSON、Skill Finder 私有 .env 及其引用文件读取，
不回显、复制或提交。上游地址来自管理员配置，浏览器不能传入任意 URL、密钥或命令。
入口限制回环来源、本机 Host 和已知服务端口 Origin，写请求需 `X-Love530-Model: 1`。
生成代理只允许服务端调用。未选择统一模型时保留原逻辑；已选择但网关离线时报错，不静默换模型。
状态原子保存失败时，不更新内存选择，不谎报成功。

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

手动验证全局默认、局部覆盖、恢复跟随、重启持久化、离线失败、桌面/手机、键盘单选、Esc 和搜索错误状态。
