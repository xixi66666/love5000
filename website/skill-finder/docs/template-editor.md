# 操作台内的 Remotion 模板编辑器

入口：`http://127.0.0.1:5177/daily-reports?panel=template`，与制作流程共用原有管理密钥。
在同一页面完成 React/TypeScript 源码修改、样式调整、编译预览、保存启用和版本恢复，无需额外启动 Studio。

## 使用

1. 输入管理密钥，点击“连接模板编辑器”。首次连接会载入当前生效版本，并编译预览。
2. 在“React 源码”中选择文件编辑，支持 Tab 缩进、行号与 Ctrl/Cmd+S 保存；编译错误可点击文件和行号定位。
3. “可视化样式”可调整颜色、栏目文案、字号、安全区、素材位置和动效强度，立即传入右侧播放器。自定义代码使用 `props.theme` 读取这些参数。
4. 修改源码后点击“编译预览”。播放器使用真正的 `@remotion/player`，支持播放、暂停与时间轴；可切换主视频和工程动画演示。
5. 点击“保存并启用”，后端重新检查 TypeScript、打包并实际渲染一帧。全部成功后才切换版本，后续生成任务使用新模板。
6. 历史版本中选择版本并恢复；有未保存草稿时先保存或放弃。离开页面前会提示未保存的修改。

预览优先复用最新能力样片清单中的媒体，其次使用最新日报；没有清单时使用明确标注的无声示例。
预览不会调用 TTS、生成日报、发布抖音或发送消息。保存模板也不会修改已有成片与审核记录。
切换操作台环节会保留当前编辑区草稿；刷新或关闭后未保存草稿不持久化。

## 文件与运行方式

基线工程位于 `video-renderer/`。页面允许编辑 `src/video.tsx`、`src/demo.tsx`、`src/types.ts`；
`src/root.tsx` 只读，保持 1080×1920、30 FPS 与现有数据协议。桥接入口与构建脚本由工程维护。
版本目录复制固定源码集合，复用工程的锁定依赖，不允许通过编辑器安装依赖或修改构建配置。

私有数据位于 `DAILY_REPORTS_DIR` 同级的 `video-template/`，默认 `backend/data/video-template/`：

```text
video-template/
├── active.json                 # 原子切换的生效版本指针
├── versions/<sha256>/src/       # 不可变源码快照
├── versions/<sha256>/version.json
└── previews/<random-id>/        # 编译缓存、预览媒体与检查帧
```

新建编译前清理旧缓存，最多保留最近 12 个草稿目录；历史模板版本不参与清理。
备份时保留 `video-template/versions` 和 `active.json`。容器沿用现有 data 持久卷，无需开放额外端口。
正式渲染清单记录 `theme` 和 `template_revision`；渲染器通过可信的 `REMOTION_TEMPLATE_DIR` 指向选中版本。
无生效指针时使用工程基线；版本内容校验失败时终止，避免静默替换模板。

## API

下列地址以 `/api/v1/daily-reports/template` 为前缀。源码读写与编译均需 `X-Admin-Key`，并使用 HTTPS 或本机连接。

| 方法与路径 | 参数 / 请求体 | 返回 |
| --- | --- | --- |
| GET 空路径 | 无 | `{revision,theme,defaults,fields,sources,versions}`；sources 包含 path/code/editable |
| POST `/preview` | `{expected_revision,sources,theme}` | `{id,revision,created_at,props}`，只编译草稿 |
| PUT 空路径 | 同上 | 当前模板文档与 `preview`，编译、渲染检查通过后启用 |
| POST `/restore` | `{expected_revision,revision}` | 恢复后的模板文档 |
| GET `/previews/{id}/{filename}` | 随机能力地址，filename 仅允许 index.html、app.js 或 media 白名单 | 沙箱预览产物 |

`sources` 必须且只能包含三个可编辑文件，每个最大 128 KiB；样式参数由严格 schema 校验。
编译失败返回 422 与 `{code,message,diagnostics:[{file,line,column,message}]}`，行列从 1 开始。
保存/恢复遇到版本冲突或任务锁返回 409，编译依赖不可用返回 503；错误保留草稿，旧生效版本不变。
保存和恢复与制作任务共用互斥锁，防止生成过程中切换模板。

## 预览边界与验证

网页播放器位于仅允许脚本的 sandbox iframe，不允许同源访问、表单或新窗口。
管理密钥不进入 iframe、不写入浏览器存储；消息只传递场景与样式。媒体仅复制清单内文件，
随机预览地址不提供源码、配置或整个报告目录。CSP 限制资源和连接到本服务。
编译器拒绝越界路径、未允许的包与计算式动态导入；不在 Node 中执行草稿源码。
模板属于管理员维护的程序，保存前的一帧检查不能替代整条视频的人工观看与审核。

后端 `test_template_editor.py` 覆盖鉴权、路径与参数边界、错误定位、运行检查失败不启用、版本冲突、恢复和成片不变。
前端 `TemplateEditor.test.ts` 覆盖鉴权门控、沙箱、编译/保存区分、错误保留与不向预览传密钥。
渲染器 `pnpm test` 覆盖真实 React 草稿编译、错误行列和导入边界。
完整命令见 [制作操作台](production-console.md#验证)。
