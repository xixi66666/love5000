#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""love5000 离线回归入口。

用途：一条命令验证当前工作区没有破坏首页动效、首页视频循环、首页服务健康、提示词分类、
模型路由公共客户端与部署副本一致性，以及五个白名单 Maven 测试类。

参数：不接受命令行参数，也没有开关；仓库根目录由脚本自身位置推导（``parents[1]``），
因此可以从任意工作目录执行。兼容 Python 3.7+ 与 Windows 的 ``mvn.cmd``。

执行阶段（与 ``main`` 里的编号注释一一对应）：
  1. 逐份运行 website/src/test/js 下四份 Node 测试（首页三份 + 提示词一份）；
  2. 运行 python -m unittest discover -s website/model-routing；
  3. 以 --check 只读校验 scripts/sync-model-picker.py 与 scripts/sync-model-routing.py
     生成的部署副本是否与唯一源码一致；
  4. 以 -o 离线模式运行 Maven 白名单测试，不访问远程仓库。

副作用：以子进程方式调用 node、当前解释器、两个同步脚本和 Maven；Maven 会写入各模块的
target/ 目录（surefire 报告用于确认测试真的执行过），其余阶段不写文件。不访问远程服务，
不读取 model.properties、.env、用户笔记或密钥。

退出码：0 表示全部通过；1 表示至少一步失败（含超时、同步检查不一致、测试未真正执行）；
2 表示只有运行工具（node / Maven / java）缺失，没有任何断言失败。
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

# 各阶段子进程超时，单位秒；Maven 首次运行要编译多个模块，因此放宽到 30 分钟。
NODE_TIMEOUT_SECONDS = 120
PYTHON_TIMEOUT_SECONDS = 300
MAVEN_TIMEOUT_SECONDS = 1800
# 失败步骤只回显输出末尾这么多行：够看到断言与异常栈顶，又不会把整段编译日志刷进终端。
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
    """定位 java 可执行文件。

    Maven 需要 JDK，但用户常只设置 ``JAVA_HOME`` 而不把 java 放进 PATH，
    所以 PATH 找不到时再回退到 ``JAVA_HOME/bin``。
    """
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
    """截取输出末尾若干行用于回显。

    子进程输出常混用 CRLF 与 LF（Windows 的 mvn.cmd 尤其明显），先统一换行再切行，
    避免回显时出现多余空行或缩进错乱。
    """
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
    """把一步结果追加进汇总列表；detail 仅在非通过时填充，供最后统一回显。"""
    results.append({
        "name": name,
        "status": status,
        "seconds": seconds,
        "detail": detail,
    })


def run_test_step(results, name, command, timeout):
    """打印当前步骤、执行命令并记录结果；失败时保留输出尾部以便定位。"""
    print("正在运行 %s…" % name, flush=True)
    status, output, seconds = run_command(command, timeout)
    record(results, name, status, seconds, output if status != PASS else "")


def report_timestamp(report):
    """返回 surefire 报告的修改时间（纳秒）；报告不存在时返回 None，首轮运行属正常情况。"""
    try:
        return report.stat().st_mtime_ns
    except FileNotFoundError:
        return None


def check_java_reports(previous):
    """确认本轮 Maven 真的执行了指定测试。

    ``-Dtest=...`` 的类名写错或 Surefire 判定跳过时，Maven 依然返回 0，因此改为比较运行前后
    报告的修改时间，并要求报告里的 tests 数大于 skipped 数；无法判断时按失败处理，宁可误报
    也不让白名单测试静默空跑。

    Args:
        previous: 运行前采集的 ``{报告路径: 修改时间}`` 快照。

    Returns:
        逐条问题描述、以换行连接；空字符串表示全部通过。
    """
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
    """按顺序执行四个阶段并打印汇总，返回值直接作为进程退出码（0 通过 / 1 失败 / 2 缺工具）。"""
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

    # 2. 模型路由公共 unittest。目录缺失时记为失败，不静默跳过，避免回归覆盖率悄悄变少。
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

    # 3. 两个同步脚本的只读检查。只比较部署副本，不写入仓库。
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
        # common 也参与 reactor 构建；逐个比对指定类的新报告，避免 -Dtest 类名失效后静默空跑。
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
