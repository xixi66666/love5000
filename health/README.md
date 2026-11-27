# 健康管理（5180）

从 `website` 的 **03 Deep Woods → 健康管理** 点击启动，或者在仓库根目录直接运行：

```powershell
mvn -pl health -am package
java -jar health/target/health-0.0.1-SNAPSHOT.jar
```

打开 [健康管理](http://127.0.0.1:5180/)。服务在本机回环地址监听，`GET /api/health` 返回 `success=true, service=health`。首页使用 `POST /api/services/health/start` 和 `GET /api/services/health/status`。

原件和草稿继续使用原来的 Obsidian Vault 路径。首次启动从旧个人资料库的运行状态读取已连接仓库与登录密码哈希，在独立目录保存。健康管理使用独立登录会话，现有密码可用于登录。档案设置可连接已由 Obsidian 打开的仓库。Windows 默认运行状态目录为 `%LOCALAPPDATA%/Love530/Health`，可用 `HEALTH_DATA_DIR` 或 `agent.data-dir` 指定，必须与个人资料库状态目录不同。可用 `HEALTH_VAULT_DIR` 指定初始仓库。本机 Python 组件路径和模型配置见下文。

个人资料库保留健康笔记、Quartz 与图谱阅读。受管理的体检资料由本应用写入，文本模型仍使用统一选择器的 `personal-agent` scope，OCR 使用根 `model.properties` 的 `vision.*`。


### 安装 Mirobody 解析组件

在项目根目录用 Python 3.12+ 创建 `health/exam-engine/.venv`，安装固定版本的解析依赖。Windows PowerShell 示例：

```powershell
py -3.12 -m venv health/exam-engine/.venv
./health/exam-engine/.venv/Scripts/python.exe -m pip install -r health/exam-engine/requirements.txt
```

Linux 用 `python3.12 -m venv health/exam-engine/.venv` 创建环境，用 `health/exam-engine/.venv/bin/python -m pip` 安装同一清单。由仓库根目录或 `health` 启动 jar 时可自动找到组件。组件通过本机子进程运行，Obsidian Vault 继续作为原件和结果的资料源。Mirobody 代码为 Apache-2.0，内置词表许可见其 [第三方数据许可](https://github.com/thetahealth/mirobody/blob/1.6.3/LICENSE-3RD-PARTY)。

### 解析与历年对照

登录后从左侧选择 **导入报告**。可一次选多份不同年份的 PDF，每份单独核对检查日期。只有文件名含唯一有效完整日期时才预填。点击 **归档报告** 后逐份保存，每份最多 12 MB。失败项可以在当前页面重试，已归档的报告可以按年份查看。展开逐页文字可检查报告的数值、单位和列是否对齐。

可搜索 PDF 按页提取文字，确认之后通过统一模型路由发送提取结果。文字可能含姓名等个人信息。系统将指标、重点发现和原报告建议的摘录匹配到 PDF 文字层，按原件定位页码。扫描 PDF、有不可读页的混合 PDF，或需要查看表格版面、图表的 PDF，可以确认将完整文件发给 DeepSeek Flash 做版面识别。识别所得摘录和位置需要对照原件核实。PDF 最多 50 页、提取文字最多 40,000 字符，超限请拆分。导入和本地预览期间原件保存在 Vault，解析或分析失败后可打开已归档的记录处理。

健康页先展示历年健康关联，再展示单次检查。两处都优先展示异常指标，其次是正常指标，缺少可用判定依据的指标显示为「待核对」。系统优先使用摘录中明确的原报告标记，其次按该次报告的可解析参考范围比较原值。外部参考仅供查阅。分类在读取草稿时生成，旧稿可直接使用。

点 **本机解析表格** 可以从带文字层的 PDF、DOCX、XLSX 收录最多 400 项有表格原文支持的指标。扫描 PDF 或 PNG/JPEG/WebP 可选择 **同意发送图片并识别**，PDF 在本机按页渲染后交给根 `model.properties` 的 `vision.*` 所配置的视觉模型，限制 10 页。视觉转录结果保存为待核对稿。已有文本 AI 解读仍可继续生成，且可搜索 PDF 的新版解读会合并本机表格与经过页行核验的模型结果。

历年关联读取每份报告最近一版有已核对摘录的草稿。Mirobody 离线生成 LOINC 编码和可确认的比较单位，单次详情可查看原文与编码。有明确同一编码、兼容比较单位且当次唯一的结果可合并，换算用于跨单位差值，原始值与判断依据始终随记录展示。无法解析的指标作为独立结果。未安装 Mirobody 时使用原有的有限别名与同单位匹配。日期相同的检查保留为独立记录，存在重复日期时省略首末差值。任一次异常的序列列入异常组，所有记录均正常的序列列入正常组。

新版可搜索 PDF 解读要求模型引用原件的页码与行号，由本机回填原文。指标字段必须出现在同一原件行，无法定位或字段不一致的条目省略并给出数量。单次报告按原报告建议、影像所见、化验发现、体格与专科检查、沟通问题和资料局限组织。已登记的旧稿可以直接参与本地关联，也可在重新确认后生成新版。页面底部可打开人体示意图及笔记双链。

参考范围单元格优先展示原报告范围。范围未收录且与已核验项目名和单位匹配时，直接填入外部参考数值及来源链接，适用条件及核验日期可在详情查看。原报告标记为空时显示短横线。已验证的旧草稿中形如 `>90mL/min/1.73m^2` 的 eGFR 连写字段可从同一原件行恢复。补充信息在读取时呈现。当前覆盖中国一般成人 BMI、中国成人诊室血压以及 KDIGO eGFR 指南分级。

| Vault 中的文件 | 用途 |
|---|---|
| `99-附件/体检/<id>.<ext>` | 原件保留在本地；Markdown 原件以 `.txt` 保存。下载校验 SHA-256；Quartz 不复制该目录。 |
| `30-健康/体检/<id>.md` | 历史记录，包含检查日期、原件双链和哈希。 |
| `80-AI分析/体检/<id>-<来源版本>-v4.md` | 新版 AI 草稿，`ai_exclude: true`。同一来源版本已有新版时复用。 |
| `80-AI分析/体检/<id>-<来源版本>-v5.md`、`-v6.md`、`-v7.md` | 本机表格、授权分页视觉识别、启用 Mirobody 后的 AI 解读，均排除在普通 AI 来源之外。 |
| `80-AI分析/体检/<id>-<来源版本>-v3.md`、`-v2.md` 和无版本后缀的草稿 | 保留的旧版草稿。在生成新版前展示最近一版，可从新版详情打开上一版。 |

接口均为本机登录 Session，写入需要 `X-CSRF-Token`。JSON 成功为 `{success:true,data:...}`，失败为 `{success:false,message:...}`。

| 方法及路径 | 输入 → 结果 |
|---|---|
| `GET /api/exams` | 当前 `workspace` 和按检查日期倒序的 `reports`（`id/date/title/ready`） |
| `GET /api/exams/timeline` | 仅登录本机读取。返回 `reports`、`verified_report_count`、跨日期指标 `metrics`、独立指标记录 `individual_metrics` 与关联主题 `topics`。序列与各次指标记录的 `status` 为 `abnormal`、`normal` 或 `unknown`。各次记录附原件摘录、位置及页码校验状态，可按 `exam_id` 回查。 |
| `POST /api/exams` | multipart `file/date/workspace/mode` → `id/revision/path`。批量界面逐份调用此接口。归档模式可传 `import_id`（UUID v4），重试相同日期及原件时返回同一记录。分析模式须传 `consent=true`，原件已归档但分析失败时返回 `warning`。 |
| `GET /api/exams/{id}` | 来源、`analysis_version`（0 无草稿，1 至 7 为草稿版本）、`latest_analysis_version`、`findings`、草稿及上一版路径。已核对指标可附 `standardization`，并各自返回分类 `status`。 |
| `GET /api/exams/{id}/preview` | 只在本机读取。返回 `mode`、`message`、`page_count`、`readable_pages`、`pages`（`page/text`）和 `local_document/page_ocr/is_pdf`。 |
| `POST /api/exams/{id}/analysis` | JSON `{workspace,revision,consent,evidence_mode}` → 同详情。`mirobody_local` 全程本机可用 `consent:false`。`mirobody_ocr`、`pdf_text` 或 `original` 均需 `consent:true`。旧客户端可省略模式，后端按文件类型选取。 |
| `GET /api/exams/{id}/original` | 以下载附件返回原件，禁止缓存 |

验证使用 `mvn -pl health -am package` 和 `node --check health/src/main/resources/static/health-app.js`。Python 组件安装后，在 `exam-engine` 运行 `.venv/Scripts/python.exe -B -X utf8 -m unittest -v test_engine`（Linux 用 `.venv/bin/python`）核验合成 PDF、DOCX、XLSX 和模拟 OCR 转录。集成测试使用临时 Vault 和模型替身。更新 jar 后重启已有的 5180 进程。
