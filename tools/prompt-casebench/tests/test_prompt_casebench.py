"""prompt-casebench 的 unittest 测试。

被测对象是同目录上一级的 ``prompt_casebench.py``（临时插入 ``sys.path`` 后导入为
``p``）。覆盖模板扫描（两种语法、混用另一套语法、未闭合、非法变量名）、片段的字面
符号保留与缺失变量、用例文件与基准文件的读取校验、lint/render/compare 的退出码
0/1/2、``--json`` 输出、``--case``/``--context`` 边界、``--strict`` 语义、baseline
的独占写入与失败不落盘，以及“旧版本生成基准 → 新版本比较”的完整流程。

隔离手段：用例文件只写入 ``tempfile.TemporaryDirectory()``，``main`` 的 stdout/stderr
用 ``redirect_stdout``/``redirect_stderr`` 捕获；示例用例只读取 ``examples/`` 下的合成
文件，不读取真实 Prompt、密钥，也不访问网络。
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parents[1]
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import prompt_casebench as p  # noqa: E402


def _write_case_file(dir_path, payload):
    """把 payload 写入临时目录下的 case.json，返回路径。"""
    path = Path(dir_path) / "case.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _valid_case():
    """返回一份字段完整的最小合法用例（dollar 语法，单个用例 c1）。"""
    return {
        "name": "demo",
        "syntax": "dollar",
        "template": "你好 ${name}，今天是 ${date}。",
        "cases": [
            {
                "id": "c1",
                "variables": {"name": "小明", "date": "周一"},
                "expected": "你好 小明，今天是 周一。",
            }
        ],
    }


def _run_cli(argv):
    """在捕获 stdout/stderr 下运行 main，返回 (exit_code, stdout, stderr)。"""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = p.main(argv)
    return code, out.getvalue(), err.getvalue()


class ScanTemplateTest(unittest.TestCase):
    """覆盖 ``scan_template`` 的切片与报错分支。

    包括 dollar/brace 两种语法的基本切片、变量去重顺序、混用另一套语法、未闭合
    占位符、空变量名，以及含空格或数字开头的非法变量名。
    """

    def test_dollar_basic(self):
        segments, variables, errors = p.scan_template("a${x}b", "dollar")
        self.assertEqual(errors, [])
        self.assertEqual(variables, ["x"])
        self.assertEqual(segments, [("text", "a"), ("var", "x"), ("text", "b")])

    def test_brace_basic(self):
        segments, variables, errors = p.scan_template("a{{x}}b", "brace")
        self.assertEqual(errors, [])
        self.assertEqual(variables, ["x"])
        self.assertEqual(segments, [("text", "a"), ("var", "x"), ("text", "b")])

    def test_variable_dedup_order(self):
        _, variables, _ = p.scan_template("${a}${b}${a}", "dollar")
        self.assertEqual(variables, ["a", "b"])

    def test_foreign_syntax_rejected(self):
        _, _, errors = p.scan_template("${a} and {{b}}", "dollar")
        self.assertTrue(any("另一套语法" in e for e in errors))

    def test_unclosed_placeholder(self):
        _, _, errors = p.scan_template("${a", "dollar")
        self.assertTrue(any("未闭合" in e for e in errors))

    def test_empty_variable_name(self):
        _, _, errors = p.scan_template("${}", "dollar")
        self.assertTrue(any("变量名为空" in e for e in errors))

    def test_illegal_variable_name(self):
        _, _, errors = p.scan_template("${1bad}", "dollar")
        self.assertTrue(any("不合法" in e for e in errors))
        _, _, errors = p.scan_template("${a b}", "dollar")
        self.assertTrue(any("不合法" in e for e in errors))


class RenderSegmentsTest(unittest.TestCase):
    """覆盖 ``render_segments`` 的拼接与失败分支。

    包括替换值中的字面符号不被二次解释、缺失变量、非字符串值；失败时断言
    ``rendered`` 为 ``None`` 且对应列表只含真实缺项。
    """

    def test_literal_symbols_preserved(self):
        # 替换值中的 ${...} / {{...}} / $500 不得被二次解释
        segments, _, _ = p.scan_template("Hello ${name}", "dollar")
        rendered, missing, bad = p.render_segments(
            segments, {"name": "${not_a_var} $500 {{x}}"}
        )
        self.assertEqual(rendered, "Hello ${not_a_var} $500 {{x}}")
        self.assertEqual(missing, [])
        self.assertEqual(bad, [])

    def test_missing_variable(self):
        segments, _, _ = p.scan_template("${a}${b}", "dollar")
        rendered, missing, bad = p.render_segments(segments, {"a": "1"})
        self.assertIsNone(rendered)
        self.assertEqual(missing, ["b"])

    def test_non_string_value(self):
        segments, _, _ = p.scan_template("${a}", "dollar")
        rendered, missing, bad = p.render_segments(segments, {"a": 5})
        self.assertIsNone(rendered)
        self.assertEqual(bad, ["a"])


class LoadRawTest(unittest.TestCase):
    """覆盖 ``load_raw_case_file`` 的失败分支。

    包括文件不存在、坏 JSON、非 UTF-8、路径是目录，以及超过 ``MAX_FILE_BYTES`` 上限；
    每条都断言抛出 ``ConfigError``，不会返回半解析结果。
    """

    def test_missing_file(self):
        with self.assertRaises(p.ConfigError):
            p.load_raw_case_file(Path("__no_such_file__.json"))

    def test_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text("{ not json !", encoding="utf-8")
            with self.assertRaises(p.ConfigError) as ctx:
                p.load_raw_case_file(path)
            self.assertIn("合法 JSON", str(ctx.exception))

    def test_non_utf8(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bin.json"
            path.write_bytes(b"\xff\xfe\x00\x01")
            with self.assertRaises(p.ConfigError):
                p.load_raw_case_file(path)

    def test_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(p.ConfigError):
                p.load_raw_case_file(Path(d))

    def test_oversize_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "big.json"
            path.write_text(" " * (p.MAX_FILE_BYTES + 1), encoding="utf-8")
            with self.assertRaises(p.ConfigError):
                p.load_raw_case_file(path)


class ValidateTest(unittest.TestCase):
    """覆盖 ``validate_case_file`` 的结构与变量校验。

    包括合法文件、缺失变量是 error、多余变量只是 warning、未知顶层字段、非法
    ``syntax``、空 ``cases``、重复 ``id``，以及模板语法错误阻止构建（返回 ``None``）。
    """

    def test_valid(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, _valid_case())
            case_file, findings = p.load_case_file(path)
            self.assertIsNotNone(case_file)
            self.assertEqual(case_file.variables, ("name", "date"))
            self.assertEqual(findings, [])

    def test_missing_variable_is_error(self):
        payload = _valid_case()
        payload["cases"][0]["variables"] = {"name": "小明"}  # 缺 date
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            case_file, findings = p.load_case_file(path)
            self.assertIsNotNone(case_file)
            errors = [f for f in findings if f.severity == p.SEVERITY_ERROR]
            self.assertTrue(any("缺失模板变量" in f.message for f in errors))

    def test_extra_variable_is_warning(self):
        payload = _valid_case()
        payload["cases"][0]["variables"]["unused"] = "x"  # 多余变量
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            case_file, findings = p.load_case_file(path)
            self.assertIsNotNone(case_file)
            warnings = [f for f in findings if f.severity == p.SEVERITY_WARNING]
            self.assertTrue(any("多余变量" in f.message for f in warnings))
            # 多余变量不应作为错误导致 lint 失败
            self.assertFalse(any(f.severity == p.SEVERITY_ERROR for f in findings))

    def test_unknown_top_level_key(self):
        payload = _valid_case()
        payload["bogus"] = 1
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            case_file, findings = p.load_case_file(path)
            self.assertIsNone(case_file)
            self.assertTrue(any("不允许的顶层字段" in f.message for f in findings))

    def test_invalid_syntax_value(self):
        payload = _valid_case()
        payload["syntax"] = "mustache"
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            case_file, findings = p.load_case_file(path)
            self.assertIsNone(case_file)
            self.assertTrue(any("syntax" in f.message for f in findings))

    def test_empty_cases(self):
        payload = _valid_case()
        payload["cases"] = []
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            case_file, findings = p.load_case_file(path)
            self.assertIsNone(case_file)
            self.assertTrue(any("非空数组" in f.message for f in findings))

    def test_duplicate_case_id(self):
        payload = _valid_case()
        payload["cases"].append(dict(payload["cases"][0]))
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            case_file, findings = p.load_case_file(path)
            self.assertIsNotNone(case_file)
            self.assertTrue(any("重复" in f.message for f in findings))

    def test_template_syntax_error_blocks(self):
        payload = _valid_case()
        payload["template"] = "a ${b"
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            case_file, findings = p.load_case_file(path)
            self.assertIsNone(case_file)


class ExitCodeTest(unittest.TestCase):
    """覆盖各子命令的退出码与关键输出。

    lint 的 0/1/2、render 的纯文本与 ``--json``、compare 的一致/不一致/跳过、
    ``--case`` 不存在与 ``--context`` 越界返回 2；stdout 用 ``redirect_stdout`` 捕获，
    用例文件只落在临时目录。
    """

    def test_lint_ok_exit_0(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, _valid_case())
            code, _, _ = _run_cli(["lint", path])
            self.assertEqual(code, p.EXIT_OK)

    def test_lint_extra_variable_exit_0(self):
        # 多余变量是警告，不是错误
        payload = _valid_case()
        payload["cases"][0]["variables"]["unused"] = "x"
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            code, _, _ = _run_cli(["lint", path])
            self.assertEqual(code, p.EXIT_OK)

    def test_lint_missing_variable_exit_1(self):
        payload = _valid_case()
        payload["cases"][0]["variables"] = {"name": "小明"}
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            code, _, _ = _run_cli(["lint", path])
            self.assertEqual(code, p.EXIT_CHECK_FAILED)

    def test_bad_json_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text("{ bad", encoding="utf-8")
            code, _, _ = _run_cli(["lint", str(path)])
            self.assertEqual(code, p.EXIT_CONFIG_ERROR)

    def test_missing_file_exit_2(self):
        code, _, _ = _run_cli(["lint", "__no_such_file__.json"])
        self.assertEqual(code, p.EXIT_CONFIG_ERROR)

    def test_render_ok_exit_0(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, _valid_case())
            code, out, _ = _run_cli(["render", path])
            self.assertEqual(code, p.EXIT_OK)
            self.assertIn("你好 小明，今天是 周一。", out)

    def test_render_json_output(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, _valid_case())
            code, out, _ = _run_cli(["render", "--json", path])
            self.assertEqual(code, p.EXIT_OK)
            data = json.loads(out)
            self.assertEqual(data["files"][0]["cases"][0]["rendered"], "你好 小明，今天是 周一。")

    def test_compare_match_exit_0(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, _valid_case())
            code, _, _ = _run_cli(["compare", path])
            self.assertEqual(code, p.EXIT_OK)

    def test_compare_mismatch_exit_1(self):
        payload = _valid_case()
        payload["cases"][0]["expected"] = "和渲染结果不一样"
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            code, out, _ = _run_cli(["compare", path])
            self.assertEqual(code, p.EXIT_CHECK_FAILED)
            self.assertIn("不一致", out)

    def test_compare_without_expected_skipped_exit_0(self):
        payload = _valid_case()
        del payload["cases"][0]["expected"]
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            code, out, _ = _run_cli(["compare", path])
            self.assertEqual(code, p.EXIT_OK)
            self.assertIn("跳过", out)

    def test_render_nonexistent_case_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, _valid_case())
            code, _, _ = _run_cli(["render", "--case", "nope", path])
            self.assertEqual(code, p.EXIT_CONFIG_ERROR)

    def test_compare_context_out_of_range_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, _valid_case())
            code, _, _ = _run_cli(["compare", "--context", "99", path])
            self.assertEqual(code, p.EXIT_CONFIG_ERROR)


class StrictCompareTest(unittest.TestCase):
    """覆盖 ``compare --strict`` 的语义差异。

    缺少 ``expected`` 的用例从“跳过”改为“失败”并返回 1，且输出里不出现 ``[跳过]``；
    带 ``expected`` 且一致的用例在严格模式下仍然通过。
    """

    def test_strict_missing_expected_fails_instead_of_skipping(self):
        payload = _valid_case()
        del payload["cases"][0]["expected"]
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            code, out, _ = _run_cli(["compare", "--strict", path])
            self.assertEqual(code, p.EXIT_CHECK_FAILED)
            self.assertIn("严格模式", out)
            self.assertIn("[失败]", out)
            self.assertNotIn("[跳过]", out)
            self.assertIn("1 失败", out)

    def test_strict_with_expected_still_passes(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, _valid_case())
            code, out, _ = _run_cli(["compare", "--strict", path])
            self.assertEqual(code, p.EXIT_OK)
            self.assertIn("[一致]", out)


class BaselineTest(unittest.TestCase):
    """覆盖 ``baseline`` 的写入与失败路径。

    断言输出保留模板、语法、变量、``expected`` 与新增的 ``rendered``，输入文件字节
    不变；已存在的输出被拒绝且内容原样保留；输入校验失败与坏输入都不留下输出文件。
    """

    def test_baseline_writes_rendered_data_and_keeps_input_unchanged(self):
        payload = _valid_case()
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            before = Path(path).read_bytes()
            output = Path(d) / "baseline.json"
            code, _, _ = _run_cli(["baseline", path, "--output", str(output)])
            self.assertEqual(code, p.EXIT_OK)
            self.assertEqual(Path(path).read_bytes(), before)

            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["format"], p.BASELINE_FORMAT)
            self.assertEqual(data["format_version"], p.BASELINE_FORMAT_VERSION)
            item = data["files"][0]
            self.assertEqual(item["template"], payload["template"])
            self.assertEqual(item["syntax"], payload["syntax"])
            case = item["cases"][0]
            self.assertEqual(case["id"], "c1")
            self.assertEqual(case["variables"], payload["cases"][0]["variables"])
            self.assertEqual(case["expected"], payload["cases"][0]["expected"])
            self.assertEqual(case["rendered"], "你好 小明，今天是 周一。")

    def test_baseline_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, _valid_case())
            output = Path(d) / "baseline.json"
            output.write_text("sentinel", encoding="utf-8")
            code, _, err = _run_cli(["baseline", path, "--output", str(output)])
            self.assertEqual(code, p.EXIT_CONFIG_ERROR)
            self.assertIn("已存在", err)
            self.assertEqual(output.read_text(encoding="utf-8"), "sentinel")

    def test_baseline_validation_failure_leaves_no_output(self):
        payload = _valid_case()
        payload["cases"][0]["variables"] = {"name": "小明"}  # 缺 date
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            output = Path(d) / "baseline.json"
            code, _, err = _run_cli(["baseline", path, "--output", str(output)])
            self.assertEqual(code, p.EXIT_CHECK_FAILED)
            self.assertFalse(output.exists())
            self.assertIn("未写入", err)

    def test_baseline_bad_input_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text("{ bad", encoding="utf-8")
            output = Path(d) / "baseline.json"
            code, _, _ = _run_cli(["baseline", str(path), "--output", str(output)])
            self.assertEqual(code, p.EXIT_CONFIG_ERROR)
            self.assertFalse(output.exists())


class BaselineCompareFlowTest(unittest.TestCase):
    """覆盖 baseline 与 compare 的联动。

    先用旧模板生成基准再比较新旧模板：旧版全部一致、新版输出不一致并带
    ``baseline（基准渲染）`` 标签；另验证基准能为自身缺少 ``expected`` 的目标用例
    补齐基准值。示例文件只读，基准只写临时目录。
    """

    def test_generate_baseline_from_old_then_compare_new(self):
        examples_dir = TOOL_DIR / "examples"
        old = examples_dir / "upgrade-old.example.json"
        new = examples_dir / "upgrade-new.example.json"
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "old-baseline.json"
            code, _, _ = _run_cli(["baseline", str(old), "--output", str(output)])
            self.assertEqual(code, p.EXIT_OK)

            code, _, _ = _run_cli(
                ["compare", str(old), "--baseline", str(output), "--strict"]
            )
            self.assertEqual(code, p.EXIT_OK)

            code, text, _ = _run_cli(
                ["compare", str(new), "--baseline", str(output), "--strict"]
            )
            self.assertEqual(code, p.EXIT_CHECK_FAILED)
            self.assertIn("不一致", text)
            self.assertIn("baseline（基准渲染）", text)

    def test_baseline_supplies_missing_expected_in_target(self):
        payload = _valid_case()
        del payload["cases"][0]["expected"]
        with tempfile.TemporaryDirectory() as d:
            path = _write_case_file(d, payload)
            output = Path(d) / "baseline.json"
            code, _, _ = _run_cli(["baseline", path, "--output", str(output)])
            self.assertEqual(code, p.EXIT_OK)

            code, text, _ = _run_cli(
                ["compare", "--strict", "--baseline", str(output), path]
            )
            self.assertEqual(code, p.EXIT_OK)
            self.assertIn("[一致]", text)


class ExampleFilesTest(unittest.TestCase):
    """``examples/`` 下的合成示例文件必须能通过 lint 与 compare。

    覆盖四条示例：两种语法的基本渲染、字面符号、以及升级前后各版本内部的自我一致；
    只读取 ``examples/`` 里的合成数据，不涉及真实 Prompt。
    """

    def test_examples_lint_and_compare(self):
        examples_dir = TOOL_DIR / "examples"
        files = sorted(str(f) for f in examples_dir.glob("*.example.json"))
        self.assertTrue(files, "examples 目录应包含至少一个示例文件")
        code, _, _ = _run_cli(["lint"] + files)
        self.assertEqual(code, p.EXIT_OK)

    def test_example_compare_ok(self):
        # 只有带 expected 且自身一致的示例能通过 compare；
        # upgrade-old 与 upgrade-new 各自内部一致，也应通过。
        examples_dir = TOOL_DIR / "examples"
        files = sorted(str(f) for f in examples_dir.glob("*.example.json"))
        code, _, _ = _run_cli(["compare"] + files)
        self.assertEqual(code, p.EXIT_OK)


if __name__ == "__main__":
    unittest.main()
