# AGENTS.md — tools/prompt-casebench

本目录维护独立的提示词模板回归 CLI。

## 工作边界

- 不调用任何模型，不发起网络请求。
- 不读取真实 Prompt 私料、`model.properties`、`.env`、数据库配置、密钥、凭据或用户目录。
- 除 `baseline --output` 显式创建的新文件外只读：不写回用例文件，不修改模板。
- 不引入第三方 Python 依赖、前端运行时或构建步骤；保持 Python 3.9+ 标准库可运行。
- 不加入 Maven 模块，不依赖 Spring、Node 或浏览器。
- 所有工作限定在本目录，不提交。

## 必须保持的契约

1. 模板只允许单一占位符语法：`dollar`（`${var}`）或 `brace`（`{{var}}`），两者不可混用。
2. 不支持转义、默认值、过滤器或任何控制逻辑；变量名只允许 `[A-Za-z_][A-Za-z0-9_]*`。
3. 渲染采用“先切 text/var 片段、后拼接”，替换值中的 `$`、`{`、`}` 等字面符号不得被二次解释。
4. 缺失变量是错误，多余变量是警告（不导致失败）。
5. 用例文件必须是显式 JSON 文件（不接受目录），UTF-8，不超过 1 MiB；cases 非空且不超过 512。
6. 退出码固定：`0` 正常，`1` 校验/渲染失败或 compare 不一致，`2` 配置错误（文件不存在、坏 JSON、非法参数）。
7. 顶层字段固定为 `name`/`syntax`/`template`/`cases`，用例字段固定为 `id`/`variables`/`expected`。
8. `compare` 缺少 `expected` 的用例默认记为“跳过”，不导致失败；加 `--strict` 时改为 `[失败]` 并返回 `1`。
9. `compare --baseline PATH` 按文件命令行顺序和用例 `id` 匹配基准；目标用例可没有 `expected`，此时基准值取 baseline 的 `rendered`。基准缺少用例时，默认跳过，`--strict` 下失败。
10. `baseline` 必须显式指定 `--output`，输出文件必须不存在；使用独占创建（`xb`），绝不覆盖已有文件。所有读取、结构校验、变量校验、渲染和 JSON 序列化必须先完成，任何失败都不得留下输出文件或半成品。
11. baseline 输出格式固定为 `format`/`format_version`/`tool_version`/`files`；每个文件保留 `path`/`name`/`syntax`/`template`/`template_variables`/`cases`，每个用例保留 `id`/`variables`/`expected` 并增加 `rendered`。输入文件永远不被修改。
12. 逐用例 diff 使用 `difflib.unified_diff`，输出不改写用例文件。

## 当前文件职责

- `prompt_casebench.py`：CLI、模板扫描、片段渲染、用例文件加载与校验、lint/render/baseline/compare 子命令、baseline 加载与独占写入。
- `examples/*.example.json`：合成示例用例文件，覆盖 dollar、brace、字面符号与升级前后对比。
- `tests/test_prompt_casebench.py`：unittest 测试，不得读取真实 Prompt 或外部文件。
- `README.md`：用户使用说明、用例格式、语法、严格模式、baseline 流程、退出码。
- `AGENTS.md`：本文件，维护边界与不变量。

## 修改与验证要求

- 修改退出码、语法规则、顶层/用例字段、校验语义、baseline 格式或输出格式时，同步更新 `README.md` 和本文件。
- 新增校验分类时，必须同时更新 `lint` 输出、汇总逻辑和测试。
- 修改后从仓库根目录执行：

```bash
python -m unittest discover -s tools/prompt-casebench/tests -v
python -m py_compile tools/prompt-casebench/prompt_casebench.py
```

- 不通过读取真实 Prompt 库或访问网络来让测试通过；测试必须使用临时目录内的合成数据。
- 涉及 baseline 的测试必须同时断言：输入字节未变、输出文件存在/不存在符合预期、失败路径没有半成品。
