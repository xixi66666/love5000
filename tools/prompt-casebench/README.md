# prompt-casebench 提示词用例回归台

独立、离线的提示词模板回归 CLI。面向提示词模板维护者：**在不调用任何模型**的前提下，严格校验模板变量、用固定用例渲染模板，并逐用例比较模板升级前后的实际输出差异。除 `baseline` 显式创建的一个新输出文件外，全程只读。

仅使用 Python 3.9+ 标准库，无第三方依赖、无网络、不读取真实 Prompt 私料或密钥。

## 目录内容

```text
tools/prompt-casebench/
├── prompt_casebench.py           # CLI 与全部实现
├── examples/
│   ├── image-style.example.json  # dollar 语法示例
│   ├── greeting.example.json     # brace 语法 + 字面符号示例
│   ├── upgrade-old.example.json  # 升级前基准
│   └── upgrade-new.example.json  # 升级后模板
├── tests/
│   ├── __init__.py
│   └── test_prompt_casebench.py
├── README.md
└── AGENTS.md
```

## 快速开始

在仓库根目录运行以下命令。

```bash
python tools/prompt-casebench/prompt_casebench.py lint tools/prompt-casebench/examples/image-style.example.json
python tools/prompt-casebench/prompt_casebench.py render tools/prompt-casebench/examples/image-style.example.json
python tools/prompt-casebench/prompt_casebench.py compare tools/prompt-casebench/examples/upgrade-old.example.json
python tools/prompt-casebench/prompt_casebench.py compare --strict tools/prompt-casebench/examples/upgrade-old.example.json
```

四个子命令：

| 命令 | 作用 |
| --- | --- |
| `lint` | 校验用例文件结构、模板语法、缺失/多余变量 |
| `render` | 用用例变量渲染模板，输出实际文本（可 `--json`） |
| `baseline` | 复用渲染逻辑，把全部渲染结果写入一个必须尚不存在的新 JSON |
| `compare` | 渲染用例并与 `expected` 或 `--baseline` 基准逐用例 diff |

## 用例文件格式

用例文件是显式 JSON：

```json
{
  "name": "图片风格模板",
  "syntax": "dollar",
  "template": "画一张${style}风格的${subject}，光线${lighting}。",
  "cases": [
    {
      "id": "minimal",
      "variables": {"style": "水彩", "subject": "海边灯塔", "lighting": "黄昏逆光"},
      "expected": "画一张水彩风格的海边灯塔，光线黄昏逆光。"
    }
  ]
}
```

顶层字段 `name`（可选，缺省用文件名）、`syntax`、`template`、`cases`（必填，非空数组，最多 512 项）。每个用例只允许 `id`、`variables`、`expected` 三个字段；`id` 必须唯一，`variables` 的值必须是字符串，`expected` 为可选基准文本。

## 变量语法

模板只允许**单一**占位符语法，且不能混用：

- `dollar`：`${variable}`
- `brace`：`{{variable}}`

不支持转义、默认值、过滤器或任何控制逻辑。变量名只允许字母、数字、下划线，且不能以数字开头。

## 校验规则

`lint` 覆盖：

- 坏 JSON、非 UTF-8、文件过大（> 1 MiB）、路径是目录 → 配置错误。
- 顶层/用例出现未知字段、缺必填字段、`syntax` 非法、模板占位符未闭合或变量名非法。
- **缺失变量**：模板用了但用例没提供 → 错误。
- **多余变量**：用例提供但模板未使用 → 警告（不导致失败）。
- 用例 `id` 重复、`variables` 值非字符串 → 错误。

## 严格模式（CI 门禁）

`compare` 的默认行为保持兼容：缺少 `expected` 的用例记为“跳过”，不影响退出码。

CI 中加 `--strict`：

- 未使用 `--baseline` 时，缺少 `expected` 的用例记为 `[失败]`，退出码为 `1`，不再跳过。
- 使用 `--baseline` 时，基准文件里没有对应用例记为失败；目标用例自身没有 `expected` 是允许的，基准值来自 baseline。
- 多余变量仍只是警告，不影响退出码。

## 基准文件（baseline）

`baseline` 复用 `render` 的模板扫描和渲染逻辑，把每个输入文件的模板、语法、变量以及每个用例的 `rendered` 写入一个由 `--output` 显式指定的新 JSON。用例的 `id`/`variables` 和已有 `expected` 都会保留（没有 `expected` 时写为 `null`）；比较时以 `rendered` 为基准值。

```bash
python tools/prompt-casebench/prompt_casebench.py baseline \
  tools/prompt-casebench/examples/upgrade-old.example.json \
  --output /tmp/prompt-casebench-old.baseline.json
```

生成的文件是工具专用的快照，不是可直接传给 `lint`/`render` 的用例文件；请通过 `compare --baseline` 读取。文件结构：

```json
{
  "format": "prompt-casebench-baseline",
  "format_version": 1,
  "tool_version": "1.1.0",
  "files": [
    {
      "path": "tools/prompt-casebench/examples/upgrade-old.example.json",
      "name": "upgrade 前后对比示例（旧版模板）",
      "syntax": "dollar",
      "template": "请用${tone}的语气写一段${topic}的简介。",
      "template_variables": ["tone", "topic"],
      "cases": [
        {
          "id": "intro",
          "variables": {"tone": "专业", "topic": "量子计算"},
          "expected": "请用专业的语气写一段量子计算的简介。",
          "rendered": "请用专业的语气写一段量子计算的简介。"
        }
      ]
    }
  ]
}
```

安全保证：

- `--output` 必填；文件必须尚不存在，已存在直接退出 `2`，绝不覆盖。
- 所有读取、结构校验、变量校验和渲染先完成，再以独占模式（`xb`）创建文件；任何校验或渲染失败都不会留下输出文件或半成品。
- 写入过程中发生 I/O 错误时会尝试删除本次创建的文件；不会删除任何原有文件。
- 输入文件永远只读，不会被写回或修改；输出路径若与已有输入文件相同，会因“已存在”被拒绝。
- baseline 不是追加式文件；要重新生成，请删除旧基准或换一个新的输出路径。

## 用 baseline 比较新旧模板

```bash
# 旧模板 + 旧用例 -> 冻结基准（只新建 baseline，不改输入）
python tools/prompt-casebench/prompt_casebench.py baseline old.json --output old.baseline.json

# 新模板 + 新用例 -> 与旧基准逐用例比较
python tools/prompt-casebench/prompt_casebench.py compare new.json --baseline old.baseline.json --strict
```

约定：

- baseline 与目标文件按命令行顺序一一对应，文件数量必须相同；用例按 `id` 匹配。
- 提供 `--baseline` 时，目标文件自身的 `expected` 不参与比较，基准值取 baseline 的 `rendered`。
- 基准缺少某个用例：默认记为“跳过”，加 `--strict` 记为“失败”。
- 不一致时输出 `difflib.unified_diff`，标签为 `baseline（基准渲染）` 与 `rendered（当前渲染）`。

## 可复现示例：从旧版本生成基准再比较

以下命令均从仓库根目录执行，只使用 `examples/` 下的合成示例，不读取真实 Prompt。输出路径位于系统临时目录；`baseline` 拒绝覆盖，所以先删除旧文件。

POSIX shell：

```bash
OUT="${TMPDIR:-/tmp}/prompt-casebench-upgrade-old.baseline.json"
rm -f "$OUT"

# 1) 旧版本 -> 基准（退出码 0）
python tools/prompt-casebench/prompt_casebench.py baseline \
  tools/prompt-casebench/examples/upgrade-old.example.json \
  --output "$OUT"

# 2) 旧版本对旧基准 -> 全部一致（退出码 0）
python tools/prompt-casebench/prompt_casebench.py compare \
  tools/prompt-casebench/examples/upgrade-old.example.json \
  --baseline "$OUT" --strict

# 3) 新版本对旧基准 -> 输出 diff，退出码 1（这是预期的回归信号）
python tools/prompt-casebench/prompt_casebench.py compare \
  tools/prompt-casebench/examples/upgrade-new.example.json \
  --baseline "$OUT" --strict
```

PowerShell：

```powershell
$out = Join-Path $env:TEMP 'prompt-casebench-upgrade-old.baseline.json'
Remove-Item -LiteralPath $out -ErrorAction SilentlyContinue

python tools/prompt-casebench/prompt_casebench.py baseline tools/prompt-casebench/examples/upgrade-old.example.json --output $out
python tools/prompt-casebench/prompt_casebench.py compare tools/prompt-casebench/examples/upgrade-old.example.json --baseline $out --strict
python tools/prompt-casebench/prompt_casebench.py compare tools/prompt-casebench/examples/upgrade-new.example.json --baseline $out --strict
"new_compare_exit=$LASTEXITCODE"
```

预期结果：

- 第 1 步 `baseline` 退出 `0`，临时目录出现基准 JSON，`examples/` 文件字节不变。
- 第 2 步退出 `0`，输出 `1 一致，0 不一致，0 失败，0 跳过`。
- 第 3 步退出 `1`，显示 `[不一致] 用例 intro` 和 diff：新版在旧版文本上增加了“关于”和“控制在200字以内”。CI 应把这一步当作模板行为变化；确认变化符合预期后，再用新版本重新生成基准并评审差异。

CI 门禁可按顺序执行：`lint` → `compare --strict`（可配合已保存的 baseline）。退出码 `1` 表示校验、渲染或输出不一致，退出码 `2` 表示配置错误，均可直接阻断流水线。

## 字面符号安全

变量值里出现 `$`、`{`、`}` 等字面符号时，**不会**被二次解释成占位符。例如模板 `Hello ${name}` 配 `{"name": "${not_a_var} $500 {{x}}"}`，渲染结果是字面文本 `Hello ${not_a_var} $500 {{x}}`，不会递归扫描。这是基于“先切成 text/var 片段，再拼接”实现的，而非反复 `str.replace`。

## 退出码

可脚本化：

| 退出码 | 含义 |
| --- | --- |
| `0` | 全部正常（`compare` 全部一致 / `lint` 无错误 / `render` 全部成功 / `baseline` 写入成功） |
| `1` | 校验发现错误、渲染失败、`compare` 存在不一致，或严格模式下缺少基准 |
| `2` | 配置错误：文件不存在、坏 JSON、非法参数、输出文件已存在/父目录不存在、baseline 格式非法 |

多余变量是警告，不影响退出码。`compare` 默认将缺少 `expected` 的用例记为“跳过”；`--strict` 时改为失败。

## 子命令参数

```text
lint     files...                              # 一个或多个 JSON 用例文件
render   files... [--case ID] [--json]         # 可只渲染指定用例，或以 JSON 输出
baseline files... --output PATH                # PATH 必须不存在；独占创建，不覆盖
compare  files... [--context N] [--strict] [--baseline PATH]
                                                # diff 上下文默认 3，范围 0–20
```

## 测试

```bash
python -m unittest discover -s tools/prompt-casebench/tests -v
python -m py_compile tools/prompt-casebench/prompt_casebench.py
```

测试使用 `unittest` + 临时目录，覆盖模板扫描、字面符号保留、坏 JSON/非 UTF-8/超限/目录、缺失/多余变量、重复 id、退出码 0/1/2、`--json` 输出、`--case` 与 `--context` 边界、`--strict` 缺少 `expected` 失败、baseline 保留输入与渲染结果、拒绝覆盖、校验失败不产出文件，以及“旧版本生成基准 → 新版本比较”的完整流程。测试不读取任何真实 Prompt、密钥或外部文件。

## 明确边界

- 不调用任何模型、不发起网络请求。
- 不读取真实 Prompt 库、`model.properties`、`.env`、密钥或用户目录。
- 除 `baseline --output` 显式创建的新文件外只读；不写回用例文件，不修改模板。
- 无第三方依赖、无 Maven 集成、无前端构建。
- 不提交、不发布、不部署。
