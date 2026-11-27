#!/usr/bin/env python3
"""提示词用例回归台：离线校验模板变量、渲染固定用例，并比较模板升级的差异。

只使用 Python 3.9+ 标准库，从仓库根目录以
``python tools/prompt-casebench/prompt_casebench.py <子命令> <文件...>`` 运行；
不调用任何模型、不发起网络请求、不读取真实 Prompt 私料、密钥或用户目录。

子命令与默认值：

- ``lint files...``：校验结构、模板语法与缺失/多余变量，只报告不渲染。
- ``render files... [--case ID] [--json]``：渲染用例，默认输出纯文本，
  ``--json`` 改为输出结构化 JSON。
- ``baseline files... --output PATH``：把全部渲染结果写成新的基准 JSON；
  ``--output`` 必填且目标必须尚不存在。
- ``compare files... [--context N] [--strict] [--baseline PATH]``：逐用例与
  ``expected`` 或基准文件比较；``--context`` 是 unified diff 的上下文行数，
  默认 ``3``，允许 ``0`` 到 ``20``。

退出码：``0`` 全部正常；``1`` 校验发现错误、渲染失败，或 ``compare`` 出现
不一致/严格模式下缺少基准；``2`` 配置错误（文件不存在、坏 JSON、非法参数、
输出文件已存在或父目录不存在、baseline 格式非法）。

副作用：除 ``baseline --output`` 显式创建的一个新文件外全程只读——不写回用例
文件、不改模板。``baseline`` 先完成全部读取、校验、渲染和序列化，最后以独占
模式（``xb``）一次性落盘，失败路径不留下输出文件或半成品。

降级策略：单个文件或单个用例的问题都被收敛成 ``Finding`` 或渲染错误后继续处理
下一项，因此一次运行能报出全部问题；只有文件本身不可读、参数非法或基准文件损坏
才作为配置错误立即返回，不吞掉错误。

用例文件为显式 JSON；模板只允许单一占位符语法：``${variable}``（dollar）或
``{{variable}}``（brace），不支持转义、默认值、过滤器或任何控制逻辑。渲染按
“先切片段、后拼接”实现，变量值里的 ``$``、``{``、``}`` 不会被二次解释。
"""

import argparse
import difflib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

VERSION = "1.1.0"

# 输入/输出上限：用例文件 1 MiB、基准文件 8 MiB、单个文件 512 个用例。上限用于
# 把单次运行的耗时与输出体积固定在可预期范围内，不是安全边界。
MAX_FILE_BYTES = 1024 * 1024
MAX_BASELINE_BYTES = 8 * 1024 * 1024
MAX_CASES = 512

# 基准文件指纹：load_baseline 依赖这两个字段拒绝把普通用例文件当基准读取。
BASELINE_FORMAT = "prompt-casebench-baseline"
BASELINE_FORMAT_VERSION = 1

# 退出码与 README 的约定一致：0 正常、1 校验/渲染失败或不一致、2 配置错误。
EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_CONFIG_ERROR = 2

# 支持的占位符语法；一个用例文件只能声明其中一种，混用按模板错误处理。
SYNTAX_DOLLAR = "dollar"
SYNTAX_BRACE = "brace"
SYNTAXES = (SYNTAX_DOLLAR, SYNTAX_BRACE)

# 问题级别：error 影响退出码，warning（例如多余变量）只提示。
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

# 用例文件允许的字段集合：多一个少一个都按结构错误处理，避免拼写错误被静默忽略。
TOP_LEVEL_KEYS = frozenset({"name", "syntax", "template", "cases"})
CASE_KEYS = frozenset({"id", "variables", "expected"})

# 变量名规则，以及会破坏终端输出的控制字符集合；两者也用于校验用例 id 与名称。
VARIABLE_NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ConfigError(Exception):
    """用例文件无法读取或 CLI 参数不合法。

    只表示“读不出来/参数不对”这类无法继续的情况；结构问题走 ``Finding``，以便
    lint 一次报出全部错误。CLI 把它映射为退出码 ``2``。
    """


@dataclass(frozen=True)
class Finding:
    """一条校验结论。

    ``severity`` 取 ``SEVERITY_ERROR`` 或 ``SEVERITY_WARNING``；``location`` 是
    JSONPath 风格的定位（例如 ``$.cases[0].variables.'x'``）；``message`` 是面向
    维护者的中文说明。
    """

    severity: str
    location: str
    message: str

    def line(self) -> str:
        """渲染成 ``[错误] 位置: 说明`` 或 ``[警告] 位置: 说明`` 的单行文本。"""
        label = "错误" if self.severity == SEVERITY_ERROR else "警告"
        return "[{}] {}: {}".format(label, self.location, self.message)


@dataclass(frozen=True)
class CaseSpec:
    """一个通过结构校验的用例。

    ``variables`` 已剔除非法项，保证值都是字符串；``expected`` 是可选的基准文本，
    缺省时 ``compare`` 会跳过或按严格模式判失败；``index`` 是它在 ``cases`` 数组里
    的下标，仅用于定位信息。
    """

    case_id: str
    variables: Dict[str, str]
    expected: Optional[str]
    index: int


@dataclass(frozen=True)
class CaseFile:
    """一个通过校验的用例文件。

    ``segments`` 是 ``scan_template`` 切出的 ``text``/``var`` 片段，渲染时直接拼接
    即可，无需重复扫描模板；``variables`` 保留首次出现顺序；``warnings`` 汇总构建
    过程中的警告，便于 ``render`` 与 ``compare`` 顺带回显。
    """

    path: Path
    name: str
    syntax: str
    template: str
    segments: Tuple[Tuple[str, str], ...]
    variables: Tuple[str, ...]
    cases: Tuple[CaseSpec, ...]
    warnings: Tuple[Finding, ...] = field(default=())


@dataclass(frozen=True)
class CaseRenderResult:
    """单个用例的渲染结果；``error`` 非空时 ``rendered`` 一定为 ``None``。"""

    case: CaseSpec
    rendered: Optional[str]
    error: Optional[str]

    @property
    def ok(self) -> bool:
        """是否渲染成功；失败原因放在 ``error`` 里由调用方打印。"""
        return self.error is None


@dataclass(frozen=True)
class BaselineCase:
    """基准文件中的一条用例快照：``rendered`` 即当时的实际渲染文本。"""

    case_id: str
    rendered: str


@dataclass(frozen=True)
class BaselineFile:
    """基准文件中的一个用例文件快照，按命令行顺序与本次输入一一对应。

    ``path`` 与 ``name`` 只用于报告来源，比较时按用例 ``id`` 匹配而不是按文本顺序，
    因此旧基准里的字段顺序变化不会误报。
    """

    path: str
    name: str
    cases: Tuple[BaselineCase, ...]


# ---------------------------------------------------------------------------
# 模板扫描与渲染
# ---------------------------------------------------------------------------


def scan_template(
    template: str, syntax: str
) -> Tuple[List[Tuple[str, str]], List[str], List[str]]:
    """把模板切成片段，返回 (segments, variables, errors)。

    单趟扫描：遇到另一套语法的标记立即记错并跳过它；遇到本语法的开标记就向后查找
    闭标记，变量名再用 ``VARIABLE_NAME_PATTERN`` 校验。之所以切片而不是反复
    ``str.replace``，是为了让替换值里的 ``$``/``{``/``}`` 保持字面含义。

    segments 元素为 ("text", 原文) 或 ("var", 变量名)。
    variables 为按首次出现顺序排列的去重变量名。
    errors 为人类可读的模板语法错误列表（含 1 起始字符位置）；遇到未闭合占位符时
    停止扫描，因为其后的内容已无法可靠切分。
    """
    if syntax == SYNTAX_DOLLAR:
        open_marker, close_marker, foreign = "${", "}", "{{"
    else:
        open_marker, close_marker, foreign = "{{", "}}", "${"

    segments: List[Tuple[str, str]] = []
    variables: List[str] = []
    errors: List[str] = []
    buffer: List[str] = []
    i = 0
    n = len(template)
    while i < n:
        if template.startswith(foreign, i):
            errors.append(
                "第 {} 个字符处出现另一套语法的占位符标记 {!r}，"
                "用例文件只允许单一语法".format(i + 1, foreign)
            )
            i += len(foreign)
            continue
        if template.startswith(open_marker, i):
            close_index = template.find(close_marker, i + len(open_marker))
            if close_index == -1:
                errors.append(
                    "第 {} 个字符处的占位符 {!r} 未闭合".format(i + 1, open_marker)
                )
                break
            name = template[i + len(open_marker):close_index]
            if not name:
                errors.append("第 {} 个字符处的占位符变量名为空".format(i + 1))
            elif not VARIABLE_NAME_PATTERN.fullmatch(name):
                errors.append(
                    "第 {} 个字符处的占位符变量名 {!r} 不合法："
                    "只允许字母、数字、下划线且不以数字开头，不允许空白".format(
                        i + 1, name
                    )
                )
            else:
                if buffer:
                    segments.append(("text", "".join(buffer)))
                    buffer = []
                segments.append(("var", name))
                if name not in variables:
                    variables.append(name)
            i = close_index + len(close_marker)
            continue
        buffer.append(template[i])
        i += 1
    if buffer:
        segments.append(("text", "".join(buffer)))
    return segments, variables, errors


def render_segments(
    segments: Sequence[Tuple[str, str]], values: Dict[str, str]
) -> Tuple[Optional[str], List[str], List[str]]:
    """渲染片段。返回 (rendered, missing, bad_type)。

    ``missing`` 为模板需要但用例未提供的变量名；``bad_type`` 为值不是字符串的变量
    名，两者都按首次出现顺序去重。只做文本拼接，不对替换值做任何二次扫描，因此
    值里出现 ``${...}``、``{{...}}`` 或 ``$500`` 都原样保留。

    任一列表非空时 ``rendered`` 为 ``None``，调用方据此判定该用例渲染失败，而不是
    抛异常中断整轮比较。
    """
    parts: List[str] = []
    missing: List[str] = []
    bad_type: List[str] = []
    for kind, payload in segments:
        if kind == "text":
            parts.append(payload)
            continue
        if payload not in values:
            if payload not in missing:
                missing.append(payload)
            continue
        value = values[payload]
        if not isinstance(value, str):
            if payload not in bad_type:
                bad_type.append(payload)
            continue
        parts.append(value)
    if missing or bad_type:
        return None, missing, bad_type
    return "".join(parts), [], []


# ---------------------------------------------------------------------------
# 用例文件加载与校验
# ---------------------------------------------------------------------------


def load_raw_case_file(path: Path) -> object:
    """读取并解析 JSON 用例文件，失败抛 ConfigError。

    只接受明确的 JSON 文件（目录直接拒绝），字节数上限 ``MAX_FILE_BYTES``；先按
    UTF-8 解码再交给 ``json.loads``，因此编码错误与语法错误会得到不同提示。返回值
    仍是未校验的 JSON 值，结构校验在 ``validate_case_file`` 里完成。

    Args:
        path: 用例文件路径，必须是显式文件。

    Returns:
        ``json.loads`` 的原始结果，可能是任何 JSON 类型。

    Raises:
        ConfigError: 文件不存在、是目录、超限、非 UTF-8 或 JSON 非法。
    """
    if not path.exists():
        raise ConfigError("用例文件不存在：{}".format(path))
    if path.is_dir():
        raise ConfigError(
            "用例文件必须是明确的 JSON 文件，不接受目录：{}".format(path)
        )
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ConfigError(
            "用例文件超过 1 MiB 上限（{} 字节）：{}".format(size, path)
        )
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigError("用例文件不是合法 UTF-8：{}（{}）".format(path, exc))
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            "用例文件不是合法 JSON：{}（第 {} 行第 {} 列：{}）".format(
                path, exc.lineno, exc.colno, exc.msg
            )
        )


def _is_clean_string(value: object) -> bool:
    """是否为可安全展示的非空字符串：非空且不含控制字符。

    用例 ``name``、用例 ``id`` 与基准里的 ``id`` 都用它把关，避免控制字符破坏终端
    输出或伪造日志行。
    """
    return (
        isinstance(value, str)
        and bool(value)
        and CONTROL_PATTERN.search(value) is None
    )


def validate_case_file(
    path: Path, raw: object
) -> Tuple[Optional[CaseFile], List[Finding]]:
    """校验结构并构建 CaseFile。

    返回 (case_file, findings)。schema 或模板语法存在错误时 case_file 为 None；
    用例级问题（缺失/多余变量、值类型错误）只记入 findings，不阻止构建，这样 lint
    能一次报出全部问题。

    校验顺序刻意从顶层开始：先字段集合与必填项，再 ``name``/``syntax``/
    ``template``，最后逐个用例；模板扫描失败会立刻返回，因为后续的变量比对依赖
    扫描结果。缺失变量是错误、多余变量只是警告——前者会让渲染失败，后者不影响
    产出。

    Args:
        path: 用例文件路径，只用于定位与默认 ``name``（文件名主干）。
        raw: ``load_raw_case_file`` 返回的未校验 JSON 值。

    Returns:
        ``(CaseFile 或 None, findings)``；存在 error 级问题时第一项为 ``None``。
    """
    findings: List[Finding] = []

    # 两个小闭包统一 findings 的追加写法，省掉每处调用重复构造 Finding。
    def error(location: str, message: str) -> None:
        findings.append(Finding(SEVERITY_ERROR, location, message))

    def warning(location: str, message: str) -> None:
        findings.append(Finding(SEVERITY_WARNING, location, message))

    if not isinstance(raw, dict):
        error("$", "顶层必须是 JSON 对象")
        return None, findings

    unknown_top = sorted(set(raw) - TOP_LEVEL_KEYS)
    for key in unknown_top:
        error("$", "不允许的顶层字段 {!r}".format(key))
    for required in ("syntax", "template", "cases"):
        if required not in raw:
            error("$", "缺少必填顶层字段 {!r}".format(required))
    if any(f.severity == SEVERITY_ERROR for f in findings):
        return None, findings

    name = raw.get("name", path.stem)
    if not _is_clean_string(name):
        error("$.name", "name 必须是不含控制字符的非空字符串")

    syntax = raw["syntax"]
    if syntax not in SYNTAXES:
        error(
            "$.syntax",
            "syntax 必须是 {!r} 或 {!r}，实际为 {!r}".format(
                SYNTAX_DOLLAR, SYNTAX_BRACE, syntax
            ),
        )
        return None, findings

    template = raw["template"]
    if not isinstance(template, str) or not template:
        error("$.template", "template 必须是非空字符串")
        return None, findings

    segments, template_vars, scan_errors = scan_template(template, syntax)
    for message in scan_errors:
        error("$.template", message)
    if scan_errors:
        return None, findings

    cases_raw = raw["cases"]
    if not isinstance(cases_raw, list) or not cases_raw:
        error("$.cases", "cases 必须是非空数组")
        return None, findings
    if len(cases_raw) > MAX_CASES:
        error("$.cases", "cases 数量 {} 超过上限 {}".format(len(cases_raw), MAX_CASES))
        return None, findings

    cases: List[CaseSpec] = []
    seen_ids = set()
    template_var_set = set(template_vars)
    for index, entry in enumerate(cases_raw):
        location = "$.cases[{}]".format(index)
        if not isinstance(entry, dict):
            error(location, "用例必须是 JSON 对象")
            continue
        for key in sorted(set(entry) - CASE_KEYS):
            error(location, "不允许的用例字段 {!r}".format(key))
        case_id = entry.get("id")
        if not _is_clean_string(case_id):
            error(location, "id 必须是不含控制字符的非空字符串")
            case_id = None
        elif case_id in seen_ids:
            error(location, "用例 id {!r} 重复".format(case_id))
        else:
            seen_ids.add(case_id)
        variables = entry.get("variables")
        if not isinstance(variables, dict):
            error(location + ".variables", "variables 必须是 JSON 对象")
            variables = None
        expected = entry.get("expected")
        if expected is not None and not isinstance(expected, str):
            error(location + ".expected", "expected 必须是字符串")
            expected = None
        if case_id is None or variables is None:
            continue
        clean_variables: Dict[str, str] = {}
        for key, value in variables.items():
            var_location = location + ".variables.{!r}".format(key)
            if not VARIABLE_NAME_PATTERN.fullmatch(key):
                error(var_location, "变量名 {!r} 不合法".format(key))
                continue
            if not isinstance(value, str):
                error(var_location, "变量 {!r} 的值必须是字符串".format(key))
                continue
            clean_variables[key] = value
        missing = [v for v in template_vars if v not in clean_variables]
        extra = [v for v in clean_variables if v not in template_var_set]
        if missing:
            error(
                location,
                "缺失模板变量：{}".format("、".join("${" + v + "}" for v in missing)),
            )
        if extra:
            warning(
                location,
                "多余变量（模板未使用）：{}".format(
                    "、".join("${" + v + "}" for v in extra)
                ),
            )
        cases.append(
            CaseSpec(
                case_id=case_id,
                variables=clean_variables,
                expected=expected,
                index=index,
            )
        )

    if not cases:
        error("$.cases", "没有任何结构合法的用例")
        return None, findings

    case_file = CaseFile(
        path=path,
        name=name,
        syntax=syntax,
        template=template,
        segments=tuple(segments),
        variables=tuple(template_vars),
        cases=tuple(cases),
        warnings=tuple(f for f in findings if f.severity == SEVERITY_WARNING),
    )
    return case_file, findings


def load_case_file(path_text: str) -> Tuple[Optional[CaseFile], List[Finding]]:
    """load + validate 的便捷封装。

    Args:
        path_text: 命令行给出的用例文件路径。

    Returns:
        ``(CaseFile 或 None, findings)``，与 ``validate_case_file`` 一致。

    Raises:
        ConfigError: 文件本身读不出来（不存在、目录、超限、坏 JSON）；结构问题
            不抛异常，而是通过 findings 返回。
    """
    path = Path(path_text)
    raw = load_raw_case_file(path)
    return validate_case_file(path, raw)


def render_case(case_file: CaseFile, case: CaseSpec) -> CaseRenderResult:
    """渲染单个用例，把缺失变量与类型错误转成中文失败原因。

    失败时返回 ``rendered=None`` 与 ``error`` 文案，供 lint/render/compare 直接打印
    或写进 JSON；渲染层不抛异常，避免一个坏用例中断整轮子命令。类型错误优先于缺失
    变量报告，因为前者需要用户改数据、后者只需要补变量。

    Args:
        case_file: 已校验的用例文件，提供模板片段。
        case: 待渲染的用例，提供变量值。

    Returns:
        ``CaseRenderResult``；``ok`` 为真时 ``rendered`` 是完整文本。
    """
    rendered, missing, bad_type = render_segments(case_file.segments, case.variables)
    if bad_type:
        return CaseRenderResult(
            case=case,
            rendered=None,
            error="变量值不是字符串：{}".format("、".join(bad_type)),
        )
    if missing:
        return CaseRenderResult(
            case=case,
            rendered=None,
            error="缺失模板变量：{}".format("、".join(missing)),
        )
    assert rendered is not None
    return CaseRenderResult(case=case, rendered=rendered, error=None)


# ---------------------------------------------------------------------------
# 基准文件加载
# ---------------------------------------------------------------------------


def load_raw_baseline_file(path: Path) -> object:
    """读取并解析 baseline JSON，失败抛 ConfigError。

    与用例文件相同的检查（必须是显式文件、UTF-8、JSON 可解析），但上限放宽到
    ``MAX_BASELINE_BYTES``，因为基准额外保存了模板原文与每个用例的渲染结果。

    Args:
        path: 基准文件路径。

    Returns:
        ``json.loads`` 的原始结果，结构校验由 ``load_baseline`` 完成。

    Raises:
        ConfigError: 文件不存在、是目录、超限、非 UTF-8 或 JSON 非法。
    """
    if not path.exists():
        raise ConfigError("基准文件不存在：{}".format(path))
    if path.is_dir():
        raise ConfigError(
            "基准文件必须是明确的 JSON 文件，不接受目录：{}".format(path)
        )
    size = path.stat().st_size
    if size > MAX_BASELINE_BYTES:
        raise ConfigError(
            "基准文件超过 8 MiB 上限（{} 字节）：{}".format(size, path)
        )
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigError("基准文件不是合法 UTF-8：{}（{}）".format(path, exc))
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            "基准文件不是合法 JSON：{}（第 {} 行第 {} 列：{}）".format(
                path, exc.lineno, exc.colno, exc.msg
            )
        )


def load_baseline(path_text: str) -> Tuple[BaselineFile, ...]:
    """加载并严格校验 baseline 子命令生成的基准 JSON。

    与用例文件不同，这里任何不合法都直接抛错而不是累积 findings：基准是可信输入，
    结构不对就没有比较意义。校验包括格式标记、整数版本号（用 ``type()`` 判断以排除
    布尔值）、非空 ``files``、每项的 ``path``/``name``/``cases``、用例 ``id`` 非空且
    唯一，以及 ``rendered`` 为字符串。

    Args:
        path_text: ``--baseline`` 给出的基准文件路径。

    Returns:
        按基准记录顺序排列的 ``BaselineFile`` 元组，下标与命令行输入文件对应。

    Raises:
        ConfigError: 任一结构检查失败；消息中带 ``files[i]`` 定位与文件路径。
    """
    path = Path(path_text)
    raw = load_raw_baseline_file(path)
    if not isinstance(raw, dict):
        raise ConfigError("基准文件顶层必须是 JSON 对象：{}".format(path))
    if raw.get("format") != BASELINE_FORMAT:
        raise ConfigError(
            "基准文件缺少格式标记 {!r}：{}".format(BASELINE_FORMAT, path)
        )
    version = raw.get("format_version")
    # 用 type() 而不是 isinstance()：布尔是 int 的子类，true 不能当作版本号 1。
    if type(version) is not int or version != BASELINE_FORMAT_VERSION:
        raise ConfigError(
            "不支持的基准格式版本 {!r}（期望 {}）：{}".format(
                version, BASELINE_FORMAT_VERSION, path
            )
        )
    files_raw = raw.get("files")
    if not isinstance(files_raw, list) or not files_raw:
        raise ConfigError("基准文件的 files 必须是非空数组：{}".format(path))

    baseline_files: List[BaselineFile] = []
    for file_index, entry in enumerate(files_raw):
        location = "files[{}]".format(file_index)
        if not isinstance(entry, dict):
            raise ConfigError(
                "基准文件 {} 必须是 JSON 对象：{}".format(location, path)
            )
        entry_path = entry.get("path")
        entry_name = entry.get("name")
        if not isinstance(entry_path, str):
            raise ConfigError(
                "基准文件 {}.path 必须是字符串：{}".format(location, path)
            )
        if not isinstance(entry_name, str):
            raise ConfigError(
                "基准文件 {}.name 必须是字符串：{}".format(location, path)
            )
        cases_raw = entry.get("cases")
        if not isinstance(cases_raw, list) or not cases_raw:
            raise ConfigError(
                "基准文件 {}.cases 必须是非空数组：{}".format(location, path)
            )
        cases: List[BaselineCase] = []
        seen_ids = set()
        for case_index, case_entry in enumerate(cases_raw):
            case_location = "{}.cases[{}]".format(location, case_index)
            if not isinstance(case_entry, dict):
                raise ConfigError(
                    "基准文件 {} 必须是 JSON 对象：{}".format(case_location, path)
                )
            case_id = case_entry.get("id")
            if not _is_clean_string(case_id):
                raise ConfigError(
                    "基准文件 {}.id 必须是不含控制字符的非空字符串：{}".format(
                        case_location, path
                    )
                )
            if case_id in seen_ids:
                raise ConfigError(
                    "基准文件 {} 的用例 id {!r} 重复：{}".format(
                        location, case_id, path
                    )
                )
            seen_ids.add(case_id)
            rendered = case_entry.get("rendered")
            if not isinstance(rendered, str):
                raise ConfigError(
                    "基准文件 {}.rendered 必须是字符串：{}".format(
                        case_location, path
                    )
                )
            cases.append(BaselineCase(case_id=case_id, rendered=rendered))
        baseline_files.append(
            BaselineFile(
                path=entry_path,
                name=entry_name,
                cases=tuple(cases),
            )
        )
    return tuple(baseline_files)


# ---------------------------------------------------------------------------
# 子命令实现
# ---------------------------------------------------------------------------


def _load_all(file_args: Sequence[str]) -> Tuple[List[Tuple[str, Optional[CaseFile], List[Finding]]], bool]:
    """加载全部用例文件。

    返回 (条目列表, 是否存在配置错误)。条目为 (路径文本, case_file, findings)。
    任何文件读取失败（ConfigError）都记为配置错误并在 findings 中给出原因，但不会
    中断后续文件；各子命令据此决定是继续汇总还是直接返回退出码 2。
    """
    entries: List[Tuple[str, Optional[CaseFile], List[Finding]]] = []
    has_config_error = False
    for file_text in file_args:
        try:
            case_file, findings = load_case_file(file_text)
        except ConfigError as exc:
            entries.append((file_text, None, [Finding(SEVERITY_ERROR, "$", str(exc))]))
            has_config_error = True
            continue
        entries.append((file_text, case_file, findings))
    return entries, has_config_error


def cmd_lint(args: argparse.Namespace) -> int:
    """执行 lint：逐个文件打印问题，最后汇总错误与警告数量。

    即使某个文件读不出来也会继续处理其余文件（配置错误记在该文件的 findings 里）。
    退出码优先级：存在配置错误返回 ``EXIT_CONFIG_ERROR``，否则有 error 返回
    ``EXIT_CHECK_FAILED``，只有 warning 时返回 ``EXIT_OK``。

    Args:
        args: 已解析的参数，使用 ``args.files``。

    Returns:
        上述三个退出码之一。
    """
    entries, has_config_error = _load_all(args.files)
    total_errors = 0
    total_warnings = 0
    for file_text, _case_file, findings in entries:
        print("===== lint {} =====".format(file_text))
        if not findings:
            print("通过：结构与变量检查无问题")
            continue
        for finding in findings:
            print(finding.line())
            if finding.severity == SEVERITY_ERROR:
                total_errors += 1
            else:
                total_warnings += 1
    print(
        "汇总：{} 个文件，{} 个错误，{} 个警告".format(
            len(entries), total_errors, total_warnings
        )
    )
    if has_config_error:
        return EXIT_CONFIG_ERROR
    return EXIT_CHECK_FAILED if total_errors else EXIT_OK


def cmd_render(args: argparse.Namespace) -> int:
    """执行 render：按 ``--case`` 选择用例并输出渲染文本或 JSON。

    ``--json`` 时输出每个文件的 ``path``/``name``/``syntax``/``template_variables``/
    ``warnings``/``cases``，每个用例再含 ``id``/``ok``/``rendered``/``error``，便于
    其它工具消费；否则按文件分段打印纯文本。配置错误与“指定 id 不存在”都返回
    ``EXIT_CONFIG_ERROR``，只要有用例渲染失败就返回 ``EXIT_CHECK_FAILED``。

    Args:
        args: 已解析的参数，使用 ``files``、``case`` 与 ``json``。

    Returns:
        ``EXIT_OK``、``EXIT_CHECK_FAILED`` 或 ``EXIT_CONFIG_ERROR``。
    """
    entries, has_config_error = _load_all(args.files)
    if has_config_error:
        for file_text, _case_file, findings in entries:
            for finding in findings:
                # 只回显文件级错误（location 为 "$"）：这是本次无法继续的原因，
                # 逐用例的细节留给 lint 报告，避免 render 输出被重复刷屏。
                if finding.severity == SEVERITY_ERROR and finding.location == "$":
                    print(finding.line(), file=sys.stderr)
        return EXIT_CONFIG_ERROR

    failed = False
    if args.json:
        files_payload = []
        for file_text, case_file, _findings in entries:
            payload_cases = []
            assert case_file is not None
            selected = _select_cases(case_file, args.case)
            if selected is None:
                print(
                    "用例 {!r} 不存在于 {}".format(args.case, file_text),
                    file=sys.stderr,
                )
                return EXIT_CONFIG_ERROR
            for case in selected:
                result = render_case(case_file, case)
                if not result.ok:
                    failed = True
                payload_cases.append(
                    {
                        "id": case.case_id,
                        "ok": result.ok,
                        "rendered": result.rendered,
                        "error": result.error,
                    }
                )
            files_payload.append(
                {
                    "path": file_text,
                    "name": case_file.name,
                    "syntax": case_file.syntax,
                    "template_variables": list(case_file.variables),
                    "warnings": [w.line() for w in case_file.warnings],
                    "cases": payload_cases,
                }
            )
        print(json.dumps({"files": files_payload}, ensure_ascii=False, indent=2))
    else:
        for file_text, case_file, _findings in entries:
            assert case_file is not None
            print("===== {}（{}，{} 语法）=====".format(file_text, case_file.name, case_file.syntax))
            for finding in case_file.warnings:
                print(finding.line())
            selected = _select_cases(case_file, args.case)
            if selected is None:
                print(
                    "用例 {!r} 不存在于 {}".format(args.case, file_text),
                    file=sys.stderr,
                )
                return EXIT_CONFIG_ERROR
            for case in selected:
                result = render_case(case_file, case)
                print("--- 用例 {} ---".format(case.case_id))
                if result.ok:
                    print(result.rendered)
                else:
                    failed = True
                    print("渲染失败：{}".format(result.error))
    return EXIT_CHECK_FAILED if failed else EXIT_OK


def _select_cases(case_file: CaseFile, case_id: Optional[str]) -> Optional[Tuple[CaseSpec, ...]]:
    """按 id 过滤用例；``case_id`` 为 ``None`` 时返回全部。

    Returns:
        匹配到的用例元组；指定了 id 却一个也没匹配到时返回 ``None``，调用方据此
        区分“没有指定筛选”和“id 不存在”两种情形。
    """
    if case_id is None:
        return case_file.cases
    matched = tuple(c for c in case_file.cases if c.case_id == case_id)
    return matched if matched else None


def _ensure_new_output_path(path: Path) -> None:
    """在创建任何文件之前检查输出路径；不修改磁盘。

    用 ``os.path.lexists`` 判断存在性，连悬空符号链接也算“已存在”，避免后续独占
    创建时意外跟随链接写到别处；父目录缺失同样拒绝，工具不代替用户创建目录。

    Raises:
        ConfigError: 目标已存在，或父目录不是已存在的目录。
    """
    if os.path.lexists(str(path)):
        raise ConfigError("输出文件已存在，baseline 不会覆盖：{}".format(path))
    parent = path.parent
    if not parent.is_dir():
        raise ConfigError(
            "输出文件的父目录不存在或不是目录：{}".format(parent)
        )


def _remove_partial_output(path: Path, created: bool) -> None:
    """尽力删除本次新建的半成品文件。

    只在 ``created`` 为真（文件确实是本次创建的）时动手；删除失败（例如句柄仍被占用）
    直接忽略，让原始错误继续向上抛，避免清理异常覆盖真正的失败原因。
    """
    if not created:
        return
    try:
        path.unlink()
    except OSError:
        pass


def write_new_text_file(path: Path, text: str) -> None:
    """以独占方式创建 UTF-8 文件；写入失败时移除半成品。

    先编码再落盘，因此编码错误不会留下空文件；打开模式为 ``xb``，目标已存在时得到
    ``FileExistsError`` 且绝不覆盖。写入过程中的任何异常（含 Ctrl-C 等
    ``BaseException``）都会尝试删除本次创建的文件，保证失败路径没有残留。

    Raises:
        ConfigError: 编码失败、目标已存在或写入时发生 ``OSError``。
    """
    try:
        payload = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ConfigError("输出内容不是合法 UTF-8：{}".format(exc))
    created = False
    try:
        with path.open("xb") as handle:
            created = True
            handle.write(payload)
            # 显式 flush，让写入错误在离开 with 之前就暴露出来，避免误报写入成功。
            handle.flush()
    except FileExistsError:
        raise ConfigError("输出文件已存在，baseline 不会覆盖：{}".format(path))
    except OSError as exc:
        _remove_partial_output(path, created)
        raise ConfigError("无法写入输出文件：{}（{}）".format(path, exc))
    except BaseException:
        _remove_partial_output(path, created)
        raise


def cmd_baseline(args: argparse.Namespace) -> int:
    """执行 baseline：把全部用例的渲染结果写入一个新的基准 JSON。

    顺序是硬约束：先检查输出路径（已存在直接返回 2，绝不覆盖），再加载并校验全部
    输入，然后逐个用例渲染，最后一次性写出。任何一步失败都在落盘之前返回，因此失败
    路径不会产生输出文件或半成品；输入文件全程只读。

    Args:
        args: 已解析的参数，使用 ``files`` 与 ``output``。

    Returns:
        ``EXIT_OK`` 写入成功；``EXIT_CONFIG_ERROR`` 输出路径/写入错误；
        ``EXIT_CHECK_FAILED`` 输入校验或渲染失败。
    """
    output_path = Path(args.output)
    try:
        _ensure_new_output_path(output_path)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_CONFIG_ERROR

    entries, has_config_error = _load_all(args.files)
    if has_config_error:
        for file_text, _case_file, findings in entries:
            for finding in findings:
                if finding.severity == SEVERITY_ERROR:
                    print(
                        "{}: {}".format(file_text, finding.line()),
                        file=sys.stderr,
                    )
        return EXIT_CONFIG_ERROR

    invalid = False
    for file_text, case_file, findings in entries:
        for finding in findings:
            print("{}: {}".format(file_text, finding.line()), file=sys.stderr)
            if finding.severity == SEVERITY_ERROR:
                invalid = True
        if case_file is None:
            invalid = True
    if invalid:
        print("baseline 未写入：输入校验失败", file=sys.stderr)
        return EXIT_CHECK_FAILED

    files_payload = []
    total_cases = 0
    render_failed = False
    for file_text, case_file, _findings in entries:
        assert case_file is not None
        payload_cases = []
        for case in case_file.cases:
            result = render_case(case_file, case)
            if not result.ok:
                render_failed = True
                print(
                    "{}: [失败] 用例 {}：{}".format(
                        file_text, case.case_id, result.error
                    ),
                    file=sys.stderr,
                )
                continue
            assert result.rendered is not None
            payload_cases.append(
                {
                    "id": case.case_id,
                    "variables": dict(case.variables),
                    "expected": case.expected,
                    "rendered": result.rendered,
                }
            )
            total_cases += 1
        files_payload.append(
            {
                "path": file_text,
                "name": case_file.name,
                "syntax": case_file.syntax,
                "template": case_file.template,
                "template_variables": list(case_file.variables),
                "cases": payload_cases,
            }
        )
    if render_failed:
        print("baseline 未写入：至少一个用例渲染失败", file=sys.stderr)
        return EXIT_CHECK_FAILED

    payload = {
        "format": BASELINE_FORMAT,
        "format_version": BASELINE_FORMAT_VERSION,
        "tool_version": VERSION,
        "files": files_payload,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        write_new_text_file(output_path, text)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_CONFIG_ERROR
    print(
        "baseline 已写入：{}（{} 个文件，{} 个用例）".format(
            output_path, len(entries), total_cases
        )
    )
    return EXIT_OK


def cmd_compare(args: argparse.Namespace) -> int:
    """执行 compare：逐用例与 expected 或 baseline 基准比较。

    基准来源二选一：给了 ``--baseline`` 就按命令行顺序把第 i 个基准文件对应到第 i 个
    输入文件、再按用例 ``id`` 匹配，基准值取其中的 ``rendered``；否则取用例自身的
    ``expected``。缺少基准时默认记“跳过”，``--strict`` 下改记“失败”。不一致时输出
    ``difflib.unified_diff``（行首统一缩进四格），最后给出“一致/不一致/失败/跳过”
    四项计数。

    Args:
        args: 已解析的参数，使用 ``files``、``baseline``、``strict`` 与 ``context``。

    Returns:
        存在不一致或失败时返回 ``EXIT_CHECK_FAILED``，否则 ``EXIT_OK``；输入或基准
        配置错误返回 ``EXIT_CONFIG_ERROR``。
    """
    entries, has_config_error = _load_all(args.files)
    if has_config_error:
        for file_text, _case_file, findings in entries:
            for finding in findings:
                # 与 render 一致：只回显文件级错误（location 为 "$"）。
                if finding.severity == SEVERITY_ERROR and finding.location == "$":
                    print(finding.line(), file=sys.stderr)
        return EXIT_CONFIG_ERROR

    baseline_files: Optional[Tuple[BaselineFile, ...]] = None
    if args.baseline is not None:
        try:
            baseline_files = load_baseline(args.baseline)
        except ConfigError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_CONFIG_ERROR
        if len(baseline_files) != len(entries):
            print(
                "基准文件包含 {} 个用例文件，但本次要比较 {} 个；"
                "请按输入顺序提供相同数量的文件".format(
                    len(baseline_files), len(entries)
                ),
                file=sys.stderr,
            )
            return EXIT_CONFIG_ERROR

    if args.strict:
        if baseline_files is None:
            print("严格模式：缺少 expected 的用例按失败处理")
        else:
            print("严格模式：基准中缺少的用例按失败处理")

    total_matched = 0
    total_mismatched = 0
    total_failed = 0
    total_skipped = 0
    for index, (file_text, case_file, _findings) in enumerate(entries):
        assert case_file is not None
        print("===== compare {}（{}）=====".format(file_text, case_file.name))
        if args.baseline is not None:
            print("基准：{}".format(args.baseline))
        for finding in case_file.warnings:
            print(finding.line())
        baseline_map: Optional[Dict[str, BaselineCase]] = None
        if baseline_files is not None:
            baseline_map = {
                baseline_case.case_id: baseline_case
                for baseline_case in baseline_files[index].cases
            }
        for case in case_file.cases:
            result = render_case(case_file, case)
            if not result.ok:
                total_failed += 1
                print("[失败] 用例 {}：{}".format(case.case_id, result.error))
                continue
            assert result.rendered is not None

            if baseline_map is not None:
                baseline_case = baseline_map.get(case.case_id)
                if baseline_case is None:
                    if args.strict:
                        total_failed += 1
                        print(
                            "[失败] 用例 {}：严格模式下基准缺少该用例".format(
                                case.case_id
                            )
                        )
                    else:
                        total_skipped += 1
                        print("[跳过] 用例 {}：基准缺少该用例".format(case.case_id))
                    continue
                reference_text = baseline_case.rendered
                reference_label = "baseline（基准渲染）"
            else:
                if case.expected is None:
                    if args.strict:
                        total_failed += 1
                        print(
                            "[失败] 用例 {}：严格模式要求 expected 基准文本，"
                            "但该用例没有".format(case.case_id)
                        )
                    else:
                        total_skipped += 1
                        print(
                            "[跳过] 用例 {}：没有 expected 基准文本".format(
                                case.case_id
                            )
                        )
                    continue
                reference_text = case.expected
                reference_label = "expected（已保存基准）"

            if result.rendered == reference_text:
                total_matched += 1
                print("[一致] 用例 {}".format(case.case_id))
                continue
            total_mismatched += 1
            print("[不一致] 用例 {}：模板升级影响了该用例的实际输出".format(case.case_id))
            diff = difflib.unified_diff(
                reference_text.splitlines(),
                result.rendered.splitlines(),
                fromfile=reference_label,
                tofile="rendered（当前渲染）",
                lineterm="",
                n=args.context,
            )
            for line in diff:
                print("    " + line)
    print(
        "汇总：{} 一致，{} 不一致，{} 失败，{} 跳过".format(
            total_matched, total_mismatched, total_failed, total_skipped
        )
    )
    return EXIT_CHECK_FAILED if (total_mismatched or total_failed) else EXIT_OK


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """构造带四个子命令的 CLI 解析器。

    子命令通过 ``set_defaults(handler=...)`` 绑定处理函数，``main`` 只负责取
    ``args.handler``；``-V/--version`` 由 argparse 打印版本后直接退出。``--context``
    的合法范围不在这里限制，而是在 ``main`` 里校验，以便越界时返回文档化的
    ``EXIT_CONFIG_ERROR``。

    Returns:
        已注册全部子命令与参数的 ``ArgumentParser``。
    """
    parser = argparse.ArgumentParser(
        prog="prompt-casebench",
        description=(
            "提示词用例回归台：不调用模型，校验模板变量、渲染已保存用例、"
            "比较模板升级对每个用例实际输出的影响。"
        ),
    )
    parser.add_argument("-V", "--version", action="version", version=VERSION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    lint_parser = subparsers.add_parser(
        "lint", help="校验用例文件结构、模板语法和缺失/多余变量"
    )
    lint_parser.add_argument("files", nargs="+", help="明确的 JSON 用例文件路径")
    lint_parser.set_defaults(handler=cmd_lint)

    render_parser = subparsers.add_parser(
        "render", help="渲染用例并输出实际文本"
    )
    render_parser.add_argument("files", nargs="+", help="明确的 JSON 用例文件路径")
    render_parser.add_argument("--case", dest="case", help="只渲染指定 id 的用例")
    render_parser.add_argument(
        "--json", action="store_true", help="以 JSON 结构输出渲染结果"
    )
    render_parser.set_defaults(handler=cmd_render)

    baseline_parser = subparsers.add_parser(
        "baseline",
        help="渲染全部用例并写入一个新的基准 JSON（不改动输入文件）",
    )
    baseline_parser.add_argument("files", nargs="+", help="明确的 JSON 用例文件路径")
    baseline_parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="要创建的基准 JSON 路径；文件必须尚不存在，创建后绝不覆盖",
    )
    baseline_parser.set_defaults(handler=cmd_baseline)

    compare_parser = subparsers.add_parser(
        "compare", help="渲染用例并与 expected 或 baseline 基准逐用例 diff"
    )
    compare_parser.add_argument("files", nargs="+", help="明确的 JSON 用例文件路径")
    compare_parser.add_argument(
        "--context",
        type=int,
        default=3,
        help="unified diff 的上下文行数，默认 3",
    )
    compare_parser.add_argument(
        "--strict",
        action="store_true",
        help="缺少基准的用例记为失败（默认记为跳过且不失败）",
    )
    compare_parser.add_argument(
        "--baseline",
        metavar="PATH",
        help="使用 baseline 子命令生成的基准 JSON 作为 expected 来源",
    )
    compare_parser.set_defaults(handler=cmd_compare)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI 入口：解析参数、校验 ``--context`` 范围，再把控制权交给子命令。

    只有 ``compare`` 的 ``--context`` 需要额外校验（0 到 20），越界时直接返回
    ``EXIT_CONFIG_ERROR`` 而不是继续比较；其余校验都在子命令内部完成。

    Args:
        argv: 参数列表；``None`` 时由 argparse 读取 ``sys.argv[1:]``。

    Returns:
        子命令返回的退出码（0/1/2），``__main__`` 直接交给 ``sys.exit``。
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "compare" and not 0 <= args.context <= 20:
        print("--context 必须在 0 到 20 之间", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
