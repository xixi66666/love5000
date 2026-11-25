#!/usr/bin/env python3
"""提示词用例回归台（prompt-casebench）。

只使用 Python 3.9+ 标准库。面向提示词库维护者：
在不调用任何模型的前提下，校验模板变量、渲染已保存用例，
并比较模板升级前后各用例的实际输出差异。

用例文件为显式 JSON；模板只允许单一占位符语法：
``${variable}``（dollar）或 ``{{variable}}``（brace），
不支持转义、默认值、过滤器或任何控制逻辑。
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

MAX_FILE_BYTES = 1024 * 1024
MAX_BASELINE_BYTES = 8 * 1024 * 1024
MAX_CASES = 512

BASELINE_FORMAT = "prompt-casebench-baseline"
BASELINE_FORMAT_VERSION = 1

EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_CONFIG_ERROR = 2

SYNTAX_DOLLAR = "dollar"
SYNTAX_BRACE = "brace"
SYNTAXES = (SYNTAX_DOLLAR, SYNTAX_BRACE)

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

TOP_LEVEL_KEYS = frozenset({"name", "syntax", "template", "cases"})
CASE_KEYS = frozenset({"id", "variables", "expected"})

VARIABLE_NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ConfigError(Exception):
    """用例文件无法读取或 CLI 参数不合法。"""


@dataclass(frozen=True)
class Finding:
    severity: str
    location: str
    message: str

    def line(self) -> str:
        label = "错误" if self.severity == SEVERITY_ERROR else "警告"
        return "[{}] {}: {}".format(label, self.location, self.message)


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    variables: Dict[str, str]
    expected: Optional[str]
    index: int


@dataclass(frozen=True)
class CaseFile:
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
    case: CaseSpec
    rendered: Optional[str]
    error: Optional[str]

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class BaselineCase:
    case_id: str
    rendered: str


@dataclass(frozen=True)
class BaselineFile:
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

    segments 元素为 ("text", 原文) 或 ("var", 变量名)。
    variables 为按首次出现顺序排列的去重变量名。
    errors 为人类可读的模板语法错误列表（含 1 起始字符位置）。
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

    missing 为模板需要但用例未提供的变量名；bad_type 为值不是字符串的变量名。
    任一非空时 rendered 为 None。
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
    """读取并解析 JSON 用例文件，失败抛 ConfigError。"""
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
    用例级问题（缺失/多余变量、值类型错误）只记入 findings，不阻止构建。
    """
    findings: List[Finding] = []

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
    """load + validate 的便捷封装。"""
    path = Path(path_text)
    raw = load_raw_case_file(path)
    return validate_case_file(path, raw)


def render_case(case_file: CaseFile, case: CaseSpec) -> CaseRenderResult:
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
    """读取并解析 baseline JSON，失败抛 ConfigError。"""
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
    """加载并严格校验 baseline 子命令生成的基准 JSON。"""
    path = Path(path_text)
    raw = load_raw_baseline_file(path)
    if not isinstance(raw, dict):
        raise ConfigError("基准文件顶层必须是 JSON 对象：{}".format(path))
    if raw.get("format") != BASELINE_FORMAT:
        raise ConfigError(
            "基准文件缺少格式标记 {!r}：{}".format(BASELINE_FORMAT, path)
        )
    version = raw.get("format_version")
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
    任何文件读取失败（ConfigError）记为配置错误，findings 中给出原因。
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
    entries, has_config_error = _load_all(args.files)
    if has_config_error:
        for file_text, _case_file, findings in entries:
            for finding in findings:
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
    if case_id is None:
        return case_file.cases
    matched = tuple(c for c in case_file.cases if c.case_id == case_id)
    return matched if matched else None


def _ensure_new_output_path(path: Path) -> None:
    """在创建任何文件之前检查输出路径；不修改磁盘。"""
    if os.path.lexists(str(path)):
        raise ConfigError("输出文件已存在，baseline 不会覆盖：{}".format(path))
    parent = path.parent
    if not parent.is_dir():
        raise ConfigError(
            "输出文件的父目录不存在或不是目录：{}".format(parent)
        )


def _remove_partial_output(path: Path, created: bool) -> None:
    if not created:
        return
    try:
        path.unlink()
    except OSError:
        pass


def write_new_text_file(path: Path, text: str) -> None:
    """以独占方式创建 UTF-8 文件；写入失败时移除半成品。"""
    try:
        payload = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ConfigError("输出内容不是合法 UTF-8：{}".format(exc))
    created = False
    try:
        with path.open("xb") as handle:
            created = True
            handle.write(payload)
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
    entries, has_config_error = _load_all(args.files)
    if has_config_error:
        for file_text, _case_file, findings in entries:
            for finding in findings:
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
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "compare" and not 0 <= args.context <= 20:
        print("--context 必须在 0 到 20 之间", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
