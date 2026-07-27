# Guitar 吉他社曲谱本地导入设计

## 目标

在 `guitar` 模块内增加吉他社单一来源导入能力。首批最多导入 50 份以中文流行歌曲为主的吉他谱，保存实际 PDF 或谱图文件到本地，并通过现有曲谱首页和详情接口直接以 `PUBLISHED` 状态展示。

用户确认已取得目标内容的抓取与保存授权。实现仍不得绕过登录、验证码、付费墙、访问控制或站点反爬措施。

## 范围

首期只支持 `jitashe.org`：

- 从“最新吉他谱”入口发现候选条目。
- 解析歌曲、歌手、编配者、谱类型、来源条目 ID、详情 URL 和文件列表。
- 下载无需登录、验证码或付费操作即可访问的 PDF、JPEG、PNG、WebP。
- 单次运行最多成功导入 50 份。
- 成功导入后直接发布。

首期不包含：

- 小红书或其他来源。
- 绕过登录、验证码、付费或反爬限制。
- 定时调度、分布式任务或管理后台抓取界面。
- OCR、谱面内容识别或自动纠错。
- 对现有无关业务代码的重构。

## 架构

抓取能力放在 `guitar` 模块独立的 `crawler` 包中：

- `JitasheSourceClient`：负责限速 HTTP 访问，设置明确 User-Agent、连接/读取超时、重试边界和最大响应大小。
- `JitasheParser`：把列表页和详情页 HTML 转换为统一候选模型。
- `SheetImportService`：编排下载、格式校验、哈希计算、去重、本地存储和数据库事务。
- `LocalSheetStorage`：将文件先写入临时目录，完成后原子移动到正式目录。
- `LocalSheetFileController`：按数据库文件记录提供受控下载 URL，不接受客户端文件系统路径。
- `CrawlerCommandRunner`：仅在显式启用时运行，默认关闭。

HTML 解析使用 Jsoup。该依赖只用于来源页面解析，不引入通用爬虫框架。

## 配置

新增配置使用环境变量覆盖，默认值保持安全：

```yaml
guitar:
  crawler:
    enabled: ${GUITAR_CRAWLER_ENABLED:false}
    source: ${GUITAR_CRAWLER_SOURCE:jitashe}
    max-items: ${GUITAR_CRAWLER_MAX_ITEMS:50}
    uploader-id: ${GUITAR_CRAWLER_UPLOADER_ID:0}
    request-delay-ms: ${GUITAR_CRAWLER_REQUEST_DELAY_MS:1500}
    connect-timeout-ms: ${GUITAR_CRAWLER_CONNECT_TIMEOUT_MS:3000}
    read-timeout-ms: ${GUITAR_CRAWLER_READ_TIMEOUT_MS:10000}
  local-storage:
    root: ${GUITAR_LOCAL_STORAGE_ROOT:./data/sheets}
```

`uploader-id` 必须对应现有 `guitar_user`。未配置有效上传者时，导入器快速失败且不下载文件。`max-items` 在配置绑定层限制为 1 至 50。

本地数据目录加入 `.gitignore`，生成文件不提交仓库。

## 数据模型

现有 `guitar_sheet` 和 `guitar_sheet_file` 继续作为公开查询的唯一业务数据源。新增 `guitar_sheet_source`：

```text
id
sheet_id
source_site
source_item_id
source_url
authorization_note
content_hash
fetched_at
create_time
update_time
```

约束：

- `sheet_id` 唯一并外键关联 `guitar_sheet`。
- `(source_site, source_item_id)` 唯一，防止同一来源条目重复导入。
- `content_hash` 保存整组文件的稳定 SHA-256 摘要，用于识别内容重复。
- `authorization_note` 只保存非敏感授权说明，不保存账号、Cookie、Token 或授权凭证正文。

文件记录继续写入 `guitar_sheet_file`。对象键字段保存相对于本地存储根目录的服务器生成键，不保存绝对路径。

## 数据映射

- 标题映射到 `song_name`，去除站点装饰文字后遵守现有字段长度。
- 艺人映射到 `singer`。
- 发布者或页面明确的编配者映射到 `arranger`，缺失时使用来源发布者或“吉他社授权导入”。
- 分类映射到现有 `sheet_type`；无法可靠识别时使用最接近的稳定枚举。
- 难度、调弦和调性缺失时使用项目约定的保守默认值，并在关键词中保留来源分类。
- 单个 PDF 映射为 `PDF`；一组谱图映射为 `IMAGES`。
- 成功记录状态为 `PUBLISHED`。

解析后仍不满足现有曲谱元数据校验的条目跳过，不通过截断或伪造内容强行入库。

## 导入流程

1. 校验配置、上传者和本地目录。
2. 获取最新曲谱列表，按页面顺序发现候选条目。
3. 使用来源条目 ID 查询 `guitar_sheet_source`，已存在则跳过。
4. 获取详情并解析文件 URL。
5. 逐个下载到本次运行的临时目录。
6. 校验响应大小、文件魔数、文件数量和扩展名；不信任远端 Content-Type 或 URL 后缀。
7. 计算每个文件 SHA-256，并生成整组内容摘要。
8. 若相同内容摘要已存在，记录为重复并跳过。
9. 原子移动到 `data/sheets/{storageUuid}/pdf` 或 `images`。
10. 在单一数据库事务中写入曲谱、文件和来源记录。
11. 数据库失败时删除本次正式目录；清理失败写入现有清理任务机制或明确的可重试本地清理记录。
12. 达到 50 份成功导入或候选耗尽后结束，输出不含敏感内容的摘要。

单条失败不终止整批任务。网站正常启动不依赖抓取成功。

## 本地文件访问

新增本地文件 URL 服务，与现有 OSS URL 服务通过配置或存储类型选择：

- URL 只包含数据库文件 ID 或不可猜测的服务器键。
- Controller 从数据库读取文件记录，再在配置根目录下解析目标。
- 解析后的规范化路径必须仍位于存储根目录内。
- 响应设置正确的内容类型、长度和安全下载文件名。
- 不公开绝对路径，不提供目录列表，不接受 `..`、盘符或任意路径参数。

现有上传接口仍按原有 OSS 规则工作。本次只为授权导入内容增加本地存储读取能力，不改变普通用户上传的安全契约。

## 限速与错误处理

- 默认请求间隔 1500ms，不并发访问吉他社。
- 仅对连接中断、超时和 HTTP 5xx 进行有限重试；4xx、验证码页、登录页和付费页不重试。
- HTML、单文件和单批次设置大小上限，避免内存或磁盘失控。
- 检测到页面结构不匹配时停止继续发现新条目，避免批量写入错误数据。
- 日志只记录来源条目 ID、URL、阶段和异常摘要，不记录响应正文、Cookie 或认证头。

## 测试与验收

自动测试使用固定 HTML 和文件样本，不连接真实吉他社：

- 列表页与详情页解析。
- 中文歌曲、歌手、编配者和类型映射。
- PDF/JPEG/PNG/WebP 魔数校验及伪装文件拒绝。
- 1 至 50 条配置边界。
- 来源 ID 去重和内容哈希去重。
- 临时写入、原子移动、数据库失败回滚和残留清理。
- 路径穿越和绝对路径访问拒绝。
- 抓取默认关闭，失败不阻止应用启动。
- 导入后公开列表和详情返回 `PUBLISHED` 曲谱及可访问本地文件 URL。

手工验收：

1. 使用测试数据库准备专用上传者。
2. 显式开启导入器并限制为较小数量进行冒烟。
3. 检查文件落盘、数据库来源记录和首页展示。
4. 再执行一次，确认重复条目不会新增。
5. 将上限调整为 50 完成首批导入。

## 文档同步

实现时同步更新：

- 根目录 `AGENTS.md` 与 `README.md`。
- `guitar/AGENTS.md` 与 `guitar/README.md`。
- `guitar/src/main/resources/db/guitar-schema.sql`。
- 配置示例、启动命令、本地数据目录和测试命令。

