#!/usr/bin/env python3
"""本地服务诊断台。

只使用 Python 3.7+ 标准库，通过显式清单探测本机 HTTP/HTTPS 服务。
不读取用户配置或凭据，不启动服务，不跟随重定向，不使用系统代理。
URL 主机只接受数值回环地址，不做域名解析。
"""

import argparse
import errno
import html
import http.client
import ipaddress
import json
import math
import socket
import ssl
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from string import Template
from textwrap import dedent
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

VERSION = "1.0.0"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "services.example.json"

MAX_MANIFEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
MAX_SERVICES = 256
MAX_JOBS = 32
MIN_TIMEOUT_SECONDS = 0.05
MAX_TIMEOUT_SECONDS = 60.0
DEFAULT_TIMEOUT_SECONDS = 3.0
DEFAULT_JOBS = 8

EXIT_OK = 0
EXIT_SERVICE_FAILURE = 1
EXIT_CONFIG_ERROR = 2

KIND_SERVICE = "service"
KIND_AGGREGATE = "aggregate"

STATUS_HEALTHY = "healthy"
STATUS_DOWNSTREAM_UNHEALTHY = "downstream_unhealthy"
STATUS_CONNECTION_REFUSED = "connection_refused"
STATUS_TIMEOUT = "timeout"
STATUS_HTTP_ERROR = "http_error"
STATUS_FORMAT_ERROR = "format_error"
STATUS_CONNECTION_ERROR = "connection_error"

STATUS_LABELS = {
    STATUS_HEALTHY: "正常",
    STATUS_DOWNSTREAM_UNHEALTHY: "下游不健康",
    STATUS_CONNECTION_REFUSED: "连接被拒绝",
    STATUS_TIMEOUT: "超时",
    STATUS_HTTP_ERROR: "HTTP 错误",
    STATUS_FORMAT_ERROR: "格式错误",
    STATUS_CONNECTION_ERROR: "其他连接错误",
}
STATUS_ORDER = tuple(STATUS_LABELS)

KIND_LABELS = {
    KIND_SERVICE: "标准服务",
    KIND_AGGREGATE: "聚合接口",
}

USER_AGENT = "service-doctor/{}".format(VERSION)


class ConfigError(Exception):
    """清单、URL 或 CLI 参数不合法。"""


class ReportError(Exception):
    """HTML 报告无法写入。"""


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    url: str
    kind: str
    expected_service: Optional[str]
    scheme: str
    host: str
    port: int
    target: str


@dataclass(frozen=True)
class CheckResult:
    name: str
    url: str
    kind: str
    expected_service: Optional[str]
    status: str
    http_status: Optional[int]
    elapsed_ms: int
    detail: str

    @property
    def ok(self) -> bool:
        return self.status == STATUS_HEALTHY


def _contains_control(value: str) -> bool:
    for char in value:
        code = ord(char)
        if code < 0x20 or code == 0x7F:
            return True
    return False


def _validate_loopback_host(host: str) -> None:
    """只接受数值回环地址，避免 localhost 的二次解析和重绑定风险。"""
    if host == "localhost":
        raise ConfigError("不接受 localhost，请使用 127.0.0.1 或 ::1")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ConfigError(
            "URL 主机必须是数值回环地址（127.0.0.0/8 或 ::1）"
        ) from None
    if not address.is_loopback:
        raise ConfigError("URL 主机必须是本机回环地址")


def _parse_service_url(raw_url: Any) -> Tuple[str, str, int, str]:
    if not isinstance(raw_url, str) or not raw_url:
        raise ConfigError("url 必须是非空字符串")
    if not raw_url.isascii():
        raise ConfigError("url 必须使用 ASCII，非 ASCII 字符请先做 URL 编码")
    if _contains_control(raw_url) or " " in raw_url:
        raise ConfigError("url 不能包含空白或控制字符")
    if len(raw_url) > 2048:
        raise ConfigError("url 过长")

    try:
        parts = urlsplit(raw_url)
    except ValueError:
        raise ConfigError("url 无法解析") from None

    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise ConfigError("url 只支持明确的 http:// 或 https:// 地址")
    if not parts.netloc:
        raise ConfigError("url 缺少主机")
    if parts.username is not None or parts.password is not None:
        raise ConfigError("url 不允许包含用户名或密码")
    if parts.fragment:
        raise ConfigError("url 不允许包含片段（#）")

    try:
        port = parts.port
    except ValueError:
        raise ConfigError("url 端口不合法") from None
    if port is None:
        port = 443 if scheme == "https" else 80
    if not 1 <= port <= 65535:
        raise ConfigError("url 端口必须在 1 到 65535 之间")

    host = parts.hostname
    if not host:
        raise ConfigError("url 缺少主机")
    _validate_loopback_host(host)

    target = parts.path or "/"
    if parts.query:
        target += "?" + parts.query

    return scheme, host, port, target


def _validate_name(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ConfigError("{} 必须是字符串".format(field_name))
    name = value.strip()
    if not name:
        raise ConfigError("{} 不能为空".format(field_name))
    if len(name) > 120:
        raise ConfigError("{} 不能超过 120 个字符".format(field_name))
    if _contains_control(name):
        raise ConfigError("{} 不能包含控制字符".format(field_name))
    return name


def _build_service_spec(entry: Any, index: int) -> ServiceSpec:
    where = "services[{}]".format(index)
    if not isinstance(entry, dict):
        raise ConfigError("{} 必须是对象".format(where))

    allowed_keys = {"name", "url", "kind", "expected_service"}
    unknown_keys = sorted(set(entry.keys()) - allowed_keys)
    if unknown_keys:
        raise ConfigError(
            "{} 包含未知字段：{}".format(where, ", ".join(unknown_keys))
        )

    name = _validate_name(entry.get("name"), "{}.name".format(where))
    kind = entry.get("kind")
    if kind not in (KIND_SERVICE, KIND_AGGREGATE):
        raise ConfigError(
            "{}.kind 必须是 \"service\" 或 \"aggregate\"".format(where)
        )

    expected_service = entry.get("expected_service")
    if kind == KIND_SERVICE:
        expected_service = _validate_name(
            expected_service, "{}.expected_service".format(where)
        )
    elif expected_service is not None:
        raise ConfigError(
            "{}.expected_service 仅用于 kind=service".format(where)
        )

    scheme, host, port, target = _parse_service_url(entry.get("url"))
    return ServiceSpec(
        name=name,
        url=entry["url"],
        kind=kind,
        expected_service=expected_service,
        scheme=scheme,
        host=host,
        port=port,
        target=target,
    )


def load_manifest(path: Path) -> List[ServiceSpec]:
    """读取并完整校验清单；任何配置问题都抛 ConfigError。"""
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError:
        raise ConfigError("无法读取清单文件：{}".format(path)) from None
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ConfigError("清单文件超过 1 MiB 上限")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ConfigError("清单文件必须是 UTF-8 编码") from None

    try:
        document = json.loads(text)
    except ValueError:
        raise ConfigError("清单文件不是有效 JSON") from None

    if not isinstance(document, dict):
        raise ConfigError("清单顶层必须是 JSON 对象")
    unknown_root_keys = sorted(set(document.keys()) - {"services"})
    if unknown_root_keys:
        raise ConfigError(
            "清单包含未知顶层字段：{}".format(", ".join(unknown_root_keys))
        )
    entries = document.get("services")
    if not isinstance(entries, list) or not entries:
        raise ConfigError("services 必须是非空数组")
    if len(entries) > MAX_SERVICES:
        raise ConfigError("services 最多允许 {} 项".format(MAX_SERVICES))

    specs = [
        _build_service_spec(entry, index)
        for index, entry in enumerate(entries)
    ]

    seen_names = set()
    for spec in specs:
        if spec.name in seen_names:
            raise ConfigError("服务名称重复：{}".format(spec.name))
        seen_names.add(spec.name)

    return specs


def _result(
    spec: ServiceSpec,
    status: str,
    started_at: float,
    detail: str,
    http_status: Optional[int] = None,
) -> CheckResult:
    return CheckResult(
        name=spec.name,
        url=spec.url,
        kind=spec.kind,
        expected_service=spec.expected_service,
        status=status,
        http_status=http_status,
        elapsed_ms=max(0, int(round((time.monotonic() - started_at) * 1000))),
        detail=detail,
    )


def _parse_health_payload(spec: ServiceSpec, raw_body: bytes) -> Tuple[str, str]:
    if not raw_body:
        return STATUS_FORMAT_ERROR, "响应体为空"

    try:
        payload = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return STATUS_FORMAT_ERROR, "响应不是有效 JSON"

    if not isinstance(payload, dict):
        return STATUS_FORMAT_ERROR, "JSON 顶层不是对象"
    if payload.get("success") is not True:
        return STATUS_FORMAT_ERROR, "success 不是字面布尔 true"

    if spec.kind == KIND_AGGREGATE:
        healthy = payload.get("healthy")
        services = payload.get("services")
        if not isinstance(healthy, bool):
            return STATUS_FORMAT_ERROR, "聚合响应 healthy 缺失或不是布尔值"
        if not isinstance(services, list):
            return STATUS_FORMAT_ERROR, "聚合响应 services 缺失或不是数组"
        if not healthy:
            return (
                STATUS_DOWNSTREAM_UNHEALTHY,
                "聚合响应 healthy=false，下游服务不健康",
            )
        return STATUS_HEALTHY, "HTTP 200，success=true，healthy=true（聚合接口）"

    service = payload.get("service")
    if not isinstance(service, str):
        return STATUS_FORMAT_ERROR, "service 缺失或不是字符串"
    if service != spec.expected_service:
        return STATUS_FORMAT_ERROR, "service 与预期不匹配"
    return STATUS_HEALTHY, "HTTP 200，success=true，service 匹配"


def _is_connection_refused(exc: OSError) -> bool:
    refused_errno = getattr(errno, "WSAECONNREFUSED", None)
    return (
        isinstance(exc, ConnectionRefusedError)
        or exc.errno == errno.ECONNREFUSED
        or (refused_errno is not None and exc.errno == refused_errno)
        or getattr(exc, "winerror", None) == 10061
    )


def check_service(
    spec: ServiceSpec, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> CheckResult:
    """探测单个服务；所有返回值都不包含响应正文。"""
    started_at = time.monotonic()
    connection = None
    try:
        if spec.scheme == "https":
            connection = http.client.HTTPSConnection(
                spec.host,
                spec.port,
                timeout=timeout,
                context=ssl.create_default_context(),
            )
        else:
            connection = http.client.HTTPConnection(
                spec.host, spec.port, timeout=timeout
            )

        connection.request(
            "GET",
            spec.target,
            headers={
                "Accept": "application/json",
                "Connection": "close",
                "User-Agent": USER_AGENT,
            },
        )
        response = connection.getresponse()
        status_code = response.status

        if status_code != 200:
            return _result(
                spec,
                STATUS_HTTP_ERROR,
                started_at,
                "HTTP 状态码 {}，预期 200".format(status_code),
                http_status=status_code,
            )

        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            return _result(
                spec,
                STATUS_FORMAT_ERROR,
                started_at,
                "响应体超过 {} 字节上限".format(MAX_RESPONSE_BYTES),
                http_status=status_code,
            )

        status, detail = _parse_health_payload(spec, body)
        return _result(
            spec,
            status,
            started_at,
            detail,
            http_status=status_code,
        )

    except (socket.timeout, TimeoutError):
        return _result(
            spec,
            STATUS_TIMEOUT,
            started_at,
            "超过 {:.2f} 秒仍未完成".format(timeout),
        )
    except OSError as exc:
        if _is_connection_refused(exc):
            return _result(
                spec,
                STATUS_CONNECTION_REFUSED,
                started_at,
                "无法连接：连接被拒绝",
            )
        return _result(
            spec,
            STATUS_CONNECTION_ERROR,
            started_at,
            "连接失败（网络或 TLS 错误）",
        )
    except http.client.HTTPException:
        return _result(
            spec,
            STATUS_CONNECTION_ERROR,
            started_at,
            "HTTP 响应无法解析",
        )
    except (UnicodeError, ValueError):
        return _result(
            spec,
            STATUS_CONNECTION_ERROR,
            started_at,
            "请求无法发送",
        )
    except Exception:
        return _result(
            spec,
            STATUS_CONNECTION_ERROR,
            started_at,
            "其他连接错误",
        )
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def run_checks(
    specs: Sequence[ServiceSpec],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    jobs: int = DEFAULT_JOBS,
) -> List[CheckResult]:
    """有界并行执行，并按输入顺序返回结果。"""
    if not specs:
        return []
    worker_count = max(1, min(int(jobs), len(specs)))

    def probe(spec: ServiceSpec) -> CheckResult:
        return check_service(spec, timeout)

    if worker_count == 1:
        return [probe(spec) for spec in specs]

    with ThreadPoolExecutor(
        max_workers=worker_count, thread_name_prefix="service-doctor"
    ) as executor:
        return list(executor.map(probe, specs))


def summarize(results: Sequence[CheckResult]) -> Dict[str, Any]:
    counts = {status: 0 for status in STATUS_ORDER}
    for result in results:
        if result.status in counts:
            counts[result.status] += 1
    healthy = counts[STATUS_HEALTHY]
    return {
        "total": len(results),
        "healthy": healthy,
        "failed": len(results) - healthy,
        "counts": counts,
    }


def _status_label(status: str) -> str:
    return STATUS_LABELS.get(status, "未知状态")


def _expected_text(result: CheckResult) -> str:
    if result.kind == KIND_AGGREGATE:
        return "聚合接口（不校验 service）"
    return "预期 service={}".format(result.expected_service)


def _http_text(result: CheckResult, missing: str = "—") -> str:
    if result.http_status is None:
        return missing
    return "HTTP {}".format(result.http_status)


def format_terminal(
    results: Sequence[CheckResult],
    timeout: float,
    jobs: int,
) -> str:
    summary = summarize(results)
    lines = [
        "本地服务诊断：共 {} 项，超时 {:.2f}s，并发 {}".format(
            summary["total"], timeout, jobs
        ),
    ]
    for result in results:
        lines.append(
            "[{}] {} | {} | {}ms | {} | {} | {}".format(
                _status_label(result.status),
                result.name,
                result.url,
                result.elapsed_ms,
                _http_text(result, "无 HTTP 状态"),
                _expected_text(result),
                result.detail,
            )
        )
    lines.append(
        "汇总：正常 {}/{}，失败 {}".format(
            summary["healthy"], summary["total"], summary["failed"]
        )
    )
    lines.append("说明：只探测清单中的数值回环地址；不读取凭据，不启动服务。")
    return "\n".join(lines)


_REPORT_CSS = """
:root {
  color-scheme: light;
  --ink: #17211f;
  --muted: #5f716c;
  --line: #d8e2de;
  --paper: #fbfdfc;
  --panel: #ffffff;
  --accent: #0b7a66;
  --ok: #126b46;
  --ok-soft: #e4f6ec;
  --bad: #a1362b;
  --bad-soft: #fbeae7;
  --warn: #8a5a12;
  --warn-soft: #fff4da;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    radial-gradient(circle at 12% 0%, #dff3ed 0, transparent 34rem),
    var(--paper);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei",
    "PingFang SC", "Noto Sans CJK SC", sans-serif;
  line-height: 1.55;
}
main { width: min(1180px, calc(100% - 40px)); margin: 0 auto; padding: 42px 0 56px; }
header { margin-bottom: 26px; }
.eyebrow { color: var(--accent); font-size: 12px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; }
h1 { margin: 8px 0 8px; font-size: clamp(28px, 4vw, 46px); line-height: 1.1; letter-spacing: -.03em; }
.lede { margin: 0; color: var(--muted); max-width: 760px; }
.meta { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 16px; color: var(--muted); font-size: 13px; }
.cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 24px 0; }
.card { border: 1px solid var(--line); border-radius: 16px; background: var(--panel); padding: 16px 18px; }
.card-label { color: var(--muted); font-size: 12px; }
.card-value { margin-top: 4px; font-size: 28px; font-weight: 750; letter-spacing: -.03em; }
.card-value.ok { color: var(--ok); }
.card-value.bad { color: var(--bad); }
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 16px; background: var(--panel); }
table { width: 100%; min-width: 1020px; border-collapse: collapse; }
th, td { padding: 12px 14px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--line); font-size: 13px; }
th { background: #f1f7f4; color: var(--muted); font-size: 12px; letter-spacing: .03em; }
tbody tr:last-child td { border-bottom: 0; }
.name { font-weight: 700; }
.url { color: var(--muted); word-break: break-all; }
.badge { display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.status-healthy { background: var(--ok-soft); color: var(--ok); }
.status-downstream_unhealthy, .status-timeout { background: var(--warn-soft); color: var(--warn); }
.status-connection_refused, .status-http_error, .status-format_error,
.status-connection_error { background: var(--bad-soft); color: var(--bad); }
.status-unknown { background: #eef1f0; color: var(--muted); }
.detail { min-width: 210px; }
.footnote { margin-top: 18px; color: var(--muted); font-size: 12px; }
@media (max-width: 720px) {
  main { width: min(calc(100% - 24px), 1180px); padding-top: 26px; }
  .cards { grid-template-columns: 1fr; }
}
@media print {
  body { background: #fff; }
  main { width: 100%; padding: 0; }
  .table-wrap { overflow: visible; }
}
"""

_REPORT_TEMPLATE = Template(
    dedent(
        """\
        <!doctype html>
        <html lang="zh-CN">
        <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="color-scheme" content="light">
        <title>本地服务诊断报告</title>
        <style>
        $css
        </style>
        </head>
        <body>
        <main>
        <header>
        <div class="eyebrow">LOOPBACK SERVICE DOCTOR</div>
        <h1>本地服务诊断报告</h1>
        <p class="lede">仅探测清单内的 HTTP/HTTPS 数值回环地址。本报告不包含任何响应正文，也不跟随重定向或使用系统代理。</p>
        <div class="meta">
        <span>生成时间：$generated_at</span>
        <span>超时：$timeout</span>
        <span>并发：$jobs</span>
        </div>
        </header>
        <section class="cards" aria-label="概览">
        <div class="card"><div class="card-label">检查项</div><div class="card-value">$total</div></div>
        <div class="card"><div class="card-label">正常</div><div class="card-value ok">$healthy</div></div>
        <div class="card"><div class="card-label">失败</div><div class="card-value $failed_class">$failed</div></div>
        </section>
        <div class="table-wrap">
        <table>
        <thead><tr><th>服务 / 地址</th><th>类型</th><th>状态</th><th>HTTP 状态</th><th>耗时</th><th>校验目标</th><th>说明</th></tr></thead>
        <tbody>
        $rows
        </tbody>
        </table>
        </div>
        <p class="footnote">状态分类：正常、下游不健康、连接被拒绝、超时、HTTP 错误、格式错误、其他连接错误。配置错误不会生成诊断结果，并以独立退出码返回。</p>
        </main>
        </body>
        </html>
        """
    )
)


def _safe(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_html_report(
    results: Sequence[CheckResult],
    generated_at: Optional[str] = None,
    timeout: Optional[float] = None,
    jobs: Optional[int] = None,
) -> str:
    """生成自包含中文 HTML；所有插值均做 HTML 逃逸，不含响应正文。"""
    if generated_at is None:
        generated_at = datetime.now().astimezone().strftime(
            "%Y-%m-%d %H:%M:%S %z"
        )
    summary = summarize(results)

    timeout_text = "未记录" if timeout is None else "{:.2f}s".format(timeout)
    jobs_text = "未记录" if jobs is None else str(jobs)

    rows = []
    for result in results:
        status_class = (
            "status-" + result.status
            if result.status in STATUS_LABELS
            else "status-unknown"
        )
        rows.append(
            "<tr>"
            "<td><div class=\"name\">{}</div><div class=\"url\">{}</div></td>"
            "<td>{}</td>"
            "<td><span class=\"badge {}\">{}</span></td>"
            "<td>{}</td>"
            "<td>{} ms</td>"
            "<td>{}</td>"
            "<td class=\"detail\">{}</td>"
            "</tr>".format(
                _safe(result.name),
                _safe(result.url),
                _safe(KIND_LABELS.get(result.kind, result.kind)),
                _safe(status_class),
                _safe(_status_label(result.status)),
                _safe(_http_text(result)),
                _safe(result.elapsed_ms),
                _safe(_expected_text(result)),
                _safe(result.detail),
            )
        )

    return _REPORT_TEMPLATE.substitute(
        css=_REPORT_CSS,
        generated_at=_safe(generated_at),
        timeout=_safe(timeout_text),
        jobs=_safe(jobs_text),
        total=_safe(summary["total"]),
        healthy=_safe(summary["healthy"]),
        failed=_safe(summary["failed"]),
        failed_class=_safe("bad" if summary["failed"] else "ok"),
        rows="\n".join(rows),
    )


def write_html_report(
    path: Path,
    results: Sequence[CheckResult],
    generated_at: Optional[str] = None,
    timeout: Optional[float] = None,
    jobs: Optional[int] = None,
) -> None:
    document = render_html_report(
        results, generated_at=generated_at, timeout=timeout, jobs=jobs
    )
    path = Path(path)
    try:
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(document)
    except OSError:
        raise ReportError("无法写入 HTML 报告：{}".format(path)) from None


def _validate_timeout(value: float) -> None:
    if not math.isfinite(value):
        raise ConfigError("--timeout 必须是有限数字")
    if not MIN_TIMEOUT_SECONDS <= value <= MAX_TIMEOUT_SECONDS:
        raise ConfigError(
            "--timeout 必须在 {:.2f} 到 {:.0f} 秒之间".format(
                MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS
            )
        )


def _validate_jobs(value: int) -> None:
    if not 1 <= value <= MAX_JOBS:
        raise ConfigError("--jobs 必须在 1 到 {} 之间".format(MAX_JOBS))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="service-doctor",
        description=(
            "本地服务诊断台：只探测清单中的数值回环地址，验证 HTTP 200、"
            "success=true；聚合接口还验证 healthy 与 services。"
        ),
    )
    parser.add_argument(
        "-m",
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="自定义 JSON 清单（默认：内置 services.example.json）",
    )
    parser.add_argument(
        "-o",
        "--html",
        type=Path,
        default=None,
        help="写入一份自包含中文 HTML 报告",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="单项超时秒数，默认 %.1f，范围 %.2f-%.0f"
        % (DEFAULT_TIMEOUT_SECONDS, MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS),
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=DEFAULT_JOBS,
        help="并发上限，默认 %d，范围 1-%d" % (DEFAULT_JOBS, MAX_JOBS),
    )
    parser.add_argument(
        "--version",
        action="version",
        version="service-doctor {}".format(VERSION),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        _validate_timeout(args.timeout)
        _validate_jobs(args.jobs)
        manifest_path = Path(args.manifest)
        specs = load_manifest(manifest_path)
        if args.html is not None:
            html_path = Path(args.html)
            try:
                same_path = html_path.resolve() == manifest_path.resolve()
            except OSError:
                same_path = False
            if same_path:
                raise ConfigError("HTML 报告不能覆盖清单文件")
    except ConfigError as exc:
        print("配置错误：{}".format(exc), file=sys.stderr)
        return EXIT_CONFIG_ERROR

    results = run_checks(specs, timeout=args.timeout, jobs=args.jobs)
    print(format_terminal(results, timeout=args.timeout, jobs=args.jobs))

    if args.html is not None:
        try:
            write_html_report(
                args.html,
                results,
                timeout=args.timeout,
                jobs=args.jobs,
            )
        except ReportError as exc:
            print("配置错误：{}".format(exc), file=sys.stderr)
            return EXIT_CONFIG_ERROR
        print("HTML 报告已写入：{}".format(args.html))

    summary = summarize(results)
    if summary["failed"]:
        return EXIT_SERVICE_FAILURE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
