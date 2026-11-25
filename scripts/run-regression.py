#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""love5000 离线回归。

一键运行：
  1. website/src/test/js 下四份 Node 测试（首页三份 + 提示词一份）
  2. python -m unittest discover -s website/model-routing
  3. scripts/sync-model-picker.py --check（只检查，不写入）
  4. scripts/sync-model-routing.py --check（只检查，不写入）
  5. Maven 离线白名单测试（-o，不访问远程仓库）

不访问远程服务，不读取 model.properties、.env、用户笔记或密钥。
可从任意目录执行；脚本以自身位置定位仓库根目录。
兼容 Python 3.7+ 与 Windows mvn.cmd。

退出码 0 表示全部通过，1 表示检查失败，2 表示只有运行工具缺失。
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]

PASS = "PASS"
FAIL = "FAIL"
MISSING = "MISSING"

NODE_TESTS = [
    ("Node 首页动效", "website/src/test/js/homepage-motion.test.js"),
    ("Node 首页视频循环", "website/src/test/js/homepage-video-loop.test.js"),
    ("Node 首页服务健康", "website/src/test/js/service-health.test.js"),
    ("Node 提示词分类", "website/src/test/js/prompt-console/prompt-category-groups.test.js"),
]

JAVA_TESTS = (
    ("website", "com.example.website.integration.health.ServiceHealthCheckerTest"),
    ("website", "com.example.website.integration.health.ServiceHealthAggregatorTest"),
    ("website", "com.example.website.integration.health.ServiceHealthControllerTest"),
    ("website", "com.example.website.integration.models.ModelRoutingServiceTest"),
    ("personal-agent", "com.example.personalagent.KnowledgeIntegrationTest"),
)

NODE_TIMEOUT_SECONDS = 120
PYTHON_TIMEOUT_SECONDS = 300
MAVEN_TIMEOUT_SECONDS = 1800
OUTPUT_TAIL_LINES = 120


def find_maven():
    """优先使用 Windows 的 mvn.cmd，兼容已设置 Maven 主目录的环境。"""
    names = ["mvn.cmd", "mvn.bat", "mvn"] if os.name == "nt" else ["mvn"]
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    for variable in ("MAVEN_HOME", "M2_HOME"):
        home = os.environ.get(variable)
        if not home:
            continue
        candidate = Path(home) / "bin" / ("mvn.cmd" if os.name == "nt" else "mvn")
        if candidate.is_file():
            return str(candidate)
    return None


def find_java():
    found = shutil.which("java")
    if found:
        return found
    home = os.environ.get("JAVA_HOME")
    if home:
        candidate = Path(home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        if candidate.is_file():
            return str(candidate)
    return None


def decode_stream(stream):
    """把子进程输出解码为文本；编码不一致时用替换字符，避免回归脚本自身崩溃。"""
    if stream is None:
        return ""
    if isinstance(stream, str):
        return stream
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return stream.decode(encoding, "replace")


def tail_text(text, lines=OUTPUT_TAIL_LINES):
    rows = text.replace("\r\n", "\n").replace("\r", "\n").rstrip().split("\n")
    return "\n".join(rows[-lines:])


def run_command(command, timeout):
    """执行命令并返回 (状态, 输出, 耗时秒数)。不抛异常给调用方。"""
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            errors="replace",
            timeout=timeout,
        )
        return (
            PASS if completed.returncode == 0 else FAIL,
            completed.stdout or "",
            time.monotonic() - started,
        )
    except subprocess.TimeoutExpired as exc:
        return (
            FAIL,
            decode_stream(getattr(exc, "output", None)) + "\n命令超时（%s 秒）" % timeout,
            time.monotonic() - started,
        )
    except OSError as exc:
        return FAIL, "无法执行命令：%s\n%s" % (" ".join(command), exc), time.monotonic() - started


def record(results, name, status, seconds=0.0, detail=""):
    results.append({
        "name": name,
        "status": status,
        "seconds": seconds,
        "detail": detail,
    })


def run_test_step(results, name, command, timeout):
    print("正在运行 %s…" % name, flush=True)
    status, output, seconds = run_command(command, timeout)
    record(results, name, status, seconds, output if status != PASS else "")


def report_timestamp(report):
    try:
        return report.stat().st_mtime_ns
    except FileNotFoundError:
        return None


def check_java_reports(previous):
    problems = []
    for report, timestamp in previous.items():
        updated = report_timestamp(report)
        if updated is None or updated == timestamp:
            problems.append("未生成本轮报告：%s" % report.name)
            continue
        try:
            suite = ElementTree.parse(str(report)).getroot()
            if int(suite.attrib["tests"]) <= int(suite.attrib.get("skipped", "0")):
                problems.append("未实际执行测试：%s" % report.name)
        except (OSError, ElementTree.ParseError, KeyError, ValueError):
            problems.append("无法读取测试报告：%s" % report.name)
    return "\n".join(problems)


def main():
    results = []

    python = sys.executable or "python"
    node = shutil.which("node")

    # 1. 四份 Node 测试。逐份执行，任何一份失败都会记录并继续后面的步骤。
    for name, relative_path in NODE_TESTS:
        if not node:
            record(results, name, MISSING, 0.0, "未找到 node；请安装 Node.js 并加入 PATH。")
            continue
        test_path = ROOT / relative_path
        if not test_path.is_file():
            record(results, name, FAIL, 0.0, "测试文件不存在：%s" % test_path)
            continue
        run_test_step(results, name, [node, str(test_path)], NODE_TIMEOUT_SECONDS)

    # 2. 模型路由公共 unittest。
    model_routing_dir = ROOT / "website" / "model-routing"
    if not model_routing_dir.is_dir():
        record(results, "Python 模型路由 unittest", FAIL, 0.0,
               "目录不存在：%s" % model_routing_dir)
    else:
        run_test_step(
            results,
            "Python 模型路由 unittest",
            [python, "-m", "unittest", "discover", "-s", "website/model-routing"],
            PYTHON_TIMEOUT_SECONDS,
        )

    # 3. 两个同步脚本的只读检查。
    for name, relative_path in (
        ("模型选择器同步 --check", "scripts/sync-model-picker.py"),
        ("模型路由同步 --check", "scripts/sync-model-routing.py"),
    ):
        script = ROOT / relative_path
        if not script.is_file():
            record(results, name, FAIL, 0.0, "脚本不存在：%s" % script)
            continue
        run_test_step(
            results,
            name,
            [python, str(script), "--check"],
            PYTHON_TIMEOUT_SECONDS,
        )

    # 4. Maven 离线白名单测试。
    maven_name = "Maven 离线白名单测试"
    maven = find_maven()
    java = find_java()
    if not maven:
        record(results, maven_name, MISSING, 0.0,
               "未找到 Maven；请安装 Maven 并将 mvn.cmd 加入 PATH。")
    elif not java:
        record(results, maven_name, MISSING, 0.0,
               "未找到 java；请安装 JDK 并设置 PATH 或 JAVA_HOME。")
    else:
        command = [
            maven,
            "-o",
            "-pl",
            "website,personal-agent",
            "-am",
            "-Dtest=" + ",".join(name.rsplit(".", 1)[-1] for _, name in JAVA_TESTS),
            "-Dsurefire.failIfNoSpecifiedTests=false",
            "test",
        ]
        # common 参与 reactor 构建。通过每个指定类的新报告确认测试真正执行。
        report_paths = [
            ROOT / module / "target" / "surefire-reports" / ("TEST-" + name + ".xml")
            for module, name in JAVA_TESTS
        ]
        previous = {report: report_timestamp(report) for report in report_paths}
        print("正在运行 %s…" % maven_name, flush=True)
        status, output, seconds = run_command(command, MAVEN_TIMEOUT_SECONDS)
        if status == PASS:
            output = check_java_reports(previous)
            if output:
                status = FAIL
        record(results, maven_name, status, seconds, output if status != PASS else "")

    # 5. 汇总。
    total = len(results)
    passed = [item for item in results if item["status"] == PASS]
    failed = [item for item in results if item["status"] == FAIL]
    missing = [item for item in results if item["status"] == MISSING]

    print("")
    print("=" * 64)
    print("love5000 离线回归结果")
    print("=" * 64)
    for index, item in enumerate(results, 1):
        line = "[%d/%d] %s ... %s" % (index, total, item["name"], item["status"])
        if item["seconds"]:
            line += " (%.2fs)" % item["seconds"]
        print(line)
        if item["detail"]:
            for row in tail_text(item["detail"]).split("\n"):
                print("    " + row)
    print("-" * 64)
    print("通过 %d / %d，失败 %d，依赖缺失 %d" % (
        len(passed), total, len(failed), len(missing)))
    if failed:
        print("失败步骤：%s" % "、".join(item["name"] for item in failed))
    if missing:
        print("依赖缺失步骤：%s" % "、".join(item["name"] for item in missing))

    if failed:
        return 1
    if missing:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
