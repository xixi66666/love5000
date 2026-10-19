# 视频制作操作台

入口：本机 `http://127.0.0.1:5177/daily-reports`；云端部署后沿用 `/skill-finder/daily-reports`。
可用 `?stage=render` 直接查看渲染环节，或 `?panel=template` 打开内置模板编辑器；`?date=YYYY-MM-DD` 指定历史报告。
本次只更新本地代码，未部署服务器，也未执行发布或消息发送。

## 操作方式

1. 在「管理连接与环境」查看运行依赖，输入私有 `ADMIN_KEY`。该值只保存在当前页面内存。
2. 点击「一键运行今日流程」。采集、筛选、脚本、素材、配音、字幕和渲染自动执行。
3. 左侧显示真实步骤状态；默认跟随当前环节，手动选中环节后暂停跟随。每 5 秒刷新，页面隐藏时暂停轮询。
4. 素材缺失或校验失败时，查看「准备素材」，按项目上传演示文件与 HTTPS 来源，再重新运行。
5. 在「渲染成片」或「人工审核」预览视频、校对口播、文案与来源，下载音轨、字幕和报告。
6. 明确批准当前视频及文案后，任务才进入抖音发布。未登录时在「抖音发布」扫码；二维码超时可重新获取。
7. 平台提交结果不确定时先人工核查，不自动重复发布。QQ 通知为独立可选环节，未配置时跳过。

重新运行从今日流程开头执行，不是断点续跑，可能再次产生配音费用。已进入待审核、批准、退回、
发布或结果未知状态的报告不可被此按钮覆盖。切换日期可查看历史；按钮始终表示生成「今日」报告。
历史任务没有逐步记录时显示「无历史记录」，不会推算已执行的步骤。

配音和字幕按段交替处理，二者分别显示实际完成段数；渲染显示真实已渲染帧数。
环境检查只确认本地工具或配置存在，不等同于供应商额度、账号会话或网络验证成功。
页面的「接入样片」与本期视频独立，查看样片时不能批准本期报告。

## 数据与接口

运行数据保持在微服务私有 `backend/data/`，或 `DAILY_REPORTS_DIR` 指定目录：

- `<reports>/<date>/report.json`：原报告、审核摘要和发布状态，协议不变。
- `<reports>/<date>/workflow.json`：真实步骤、时间、段数、最近 100 条事件与错误类型。
- `<reports>/<date>/render-progress.json`：Node 渲染器每秒写入的帧数快照。
- `<reports>/.dispatch.lock`：防止 HTTP 重复派发；原 `.pipeline.lock` 继续互斥实际日报任务。
- `DAILY_ASSETS_DIR`：带项目名与随机标识的素材文件、`owner--repo.json` 来源清单。
- `<reports>` 同级 `video-samples/<timestamp>/`：已有接入样片，只公开音视频、封面与字幕白名单。

API 前缀：`/api/v1/daily-reports`。读取接口不携带管理密钥；管理操作要求 `X-Admin-Key` 和 HTTPS 或本机连接。
HTTPS Nginx 示例同步将 `client_max_body_size` 设为 100m；上线时需同时更新代理配置，旧代理仍可能拒绝大素材。

| 方法与路径 | 参数 / 请求体 | 响应与用途 |
| --- | --- | --- |
| GET `/console` | 可选 `day=YYYY-MM-DD`，默认业务时区当天 | `{date,today,timezone,status,recorded,workflow,runtime,assets,artifacts,render_progress,samples,template}` |
| POST `/generate` | 无请求体要求 | 202 `{status:"accepted",date}`；互斥或已进入审核时 409 |
| PUT `/{day}/assets/{owner}/{repo}` | query：`filename`、HTTPS `source`；body：原始文件字节，Content-Type: application/octet-stream | 200 `{project,status:"ready",bytes}`；必须是本期项目；超 100 MiB 为 413，格式/解码/时长不合法为 422，正在执行时 409 |
| POST `/{day}/notify` | 空 JSON 对象 | 202，成片未就绪或 QQ 未配置为 409 |
| GET `/samples/{id}/files/{filename}` | id 格式 YYYYMMDD-HHMMSS；video.mp4/audio.m4a/poster.png/subtitles.srt | 文件响应；其他工作文件一律 404 |

旧列表、报告详情、下载、审核、发布和扫码登录接口继续使用。
口播脚本与文字日报在写入后可查看；未完成任务的半成品视频不会作为审核视频开放。
错误不返回上游响应正文、API Key、数据库连接、配置路径或账号登录文件。
依赖检查的 ready 仅表示配置/工具存在，不承诺远端服务可用；浏览器和模型实际运行仍以对应步骤结果为准。

## Remotion 模板在哪里开发

操作台“模板编辑”中直接修改 React/TSX，或切换“可视化样式”调整颜色、栏目文案、字号、安全区和动效。
右侧使用真实 Remotion Player，源码修改后点击“编译预览”，样式修改即时预览。无需另开编辑器或 Studio。
基线代码目录为 `website/skill-finder/video-renderer/`：

| 文件 | 修改内容 |
| --- | --- |
| `src/video.tsx` | 主模板布局、颜色、动效、字幕、素材与音轨 |
| `src/root.tsx` | Composition 注册、分辨率、帧率与动态时长（页面只读） |
| `src/demo.tsx` | Remotion 自身能力演示 |
| `src/types.ts` | Python 清单与 React 组件间的数据协议 |
| `scripts/render.mjs` | 正式渲染、媒体服务、编码与进度输出 |

首次连接使用原管理密钥。错误按文件、行列展示并支持定位；草稿只在“保存并启用”后成为生效版本。
保存需通过类型检查、打包与真实检查帧渲染。历史版本支持恢复，已有成片与审核不变。
开发预览优先复用样片或日报素材，没有素材时明确显示示例；不会发起配音或发布。
API、私有版本目录、编译边界与操作步骤见 [模板编辑器](template-editor.md)。
可选本地 Studio 仍可通过 `video-renderer` 中的 `pnpm studio` 使用，不随微服务启动。

## 验证

后端：`uv run python -m ruff check .`、`uv run python -m pytest -q`。
`test_daily_console.py` 验证记录持久化、脱敏、任务中断、派发互斥、历史状态、素材身份与大小校验，以及样片下载白名单。
集成测试仍仅使用独立测试库，未配置时跳过。

前端：`npm run lint`、`npm run typecheck`、`npm run test -- --run`、`npm run build`。
`DailyReportsView.test.ts` 验证自动跟随、手动检查、密钥门控、真实帧数以及样片与本期审核区分。
`test_template_editor.py`、`TemplateEditor.test.ts` 覆盖编辑器鉴权、草稿/版本边界、失败保留和沙箱消息。
渲染器目录执行 `pnpm run typecheck` 和 `pnpm test`，包含真实 TSX 编译及导入边界验证。
运行环境准备与渲染配置另见 [Remotion 接入](remotion-integration.md)。
