#!/usr/bin/env python3
"""本地服务诊断台：探测显式清单中的本机服务健康接口，并可按需导出 HTML 报告。

只使用 Python 3.7+ 标准库，从仓库根目录以
``python tools/service-doctor/service_doctor.py`` 运行。工具按 JSON 清单逐个
探测标准服务的 ``/api/health`` 与聚合接口 ``/api/services/health``，在终端打印
每项状态，并可额外写出一份自包含的中文 HTML 报告。

命令行参数与默认值：

- ``-m/--manifest PATH``：JSON 清单，默认同目录的 ``services.example.json``。
- ``-o/--html PATH``：额外写出 HTML 报告；缺省时不创建任何文件。
- ``-t/--timeout SECONDS``：单个目标的连接与读取超时，默认 ``3.0``，允许
  ``0.05`` 到 ``60``。
- ``-j/--jobs N``：并发上限，默认 ``8``，允许 ``1`` 到 ``32``；实际并发数还会
  被目标数量压小，结果始终按清单顺序输出。
- ``--version``：打印版本后退出。

退出码：``0`` 全部目标正常；``1`` 至少一个目标检查失败；``2`` 配置错误，包括
清单不可读、URL 不合法、``--timeout``/``--jobs`` 越界，以及 HTML 报告写入失败。
配置错误在探测之前返回，不会访问任何目标。

副作用：只读取清单文件；只有显式给出 ``--html`` 时才以 UTF-8 编码、LF 换行写出
一个报告文件（不创建目录，报告路径与清单相同会被拒绝）。工具不读取环境变量里
的代理设置、不读取用户配置或凭据、不启动或停止任何服务、不跟随 3xx 重定向、不把
响应正文写进终端或报告。

降级策略：单个目标的连接拒绝、超时、HTTP 错误和响应格式错误都只折叠成一条
``CheckResult`` 状态，不会中断整轮巡检，因此一次运行总能给出清单中全部目标的
结论；只有清单与参数本身的配置错误才会在探测前中止并返回 ``2``。
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
# 按脚本自身位置定位，保证从任意工作目录调用都能找到随工具提交的默认清单。
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "services.example.json"

# 输入/输出上限：清单 1 MiB、单个响应 256 KiB。前者防止异常清单拖垮解析，
# 后者保证一个畸形的巨大响应也不会被整段读进内存。
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
# 清单条数与并发上限，把一次运行的时间和线程数固定在可预期范围内。
MAX_SERVICES = 256
MAX_JOBS = 32
# 超时下限避免 0 或负数产生永远无法完成的探测；上限避免整轮巡检被单个目标拖住。
MIN_TIMEOUT_SECONDS = 0.05
MAX_TIMEOUT_SECONDS = 60.0
DEFAULT_TIMEOUT_SECONDS = 3.0
DEFAULT_JOBS = 8

# 退出码与 README 的约定一致：0 正常、1 服务失败、2 配置/输出错误。
EXIT_OK = 0
EXIT_SERVICE_FAILURE = 1
EXIT_CONFIG_ERROR = 2

# 清单中的 kind：标准服务要求 service 标识匹配，聚合接口校验 healthy 与 services。
KIND_SERVICE = "service"
KIND_AGGREGATE = "aggregate"

# 状态码保持 ASCII，便于写进 HTML 的 class 属性和测试断言；中文标签只用于展示。
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
# 固定顺序：汇总计数与状态标签遍历都依赖它，不要改成按出现顺序动态生成。
STATUS_ORDER = tuple(STATUS_LABELS)

KIND_LABELS = {
    KIND_SERVICE: "标准服务",
    KIND_AGGREGATE: "聚合接口",
}

USER_AGENT = "service-doctor/{}".format(VERSION)


class ConfigError(Exception):
    """清单、URL 或 CLI 参数不合法。

    ``main`` 把它统一映射为 ``EXIT_CONFIG_ERROR`` 并只输出一行中文提示，因此消息
    必须面向最终用户，且不得包含响应正文或凭据。
    """


class ReportError(Exception):
    """HTML 报告无法写入。

    只用于包装底层 ``OSError``，让调用方能把“报告写不出来”与“服务不健康”区分
    成不同退出码；原始异常链不向外暴露。
    """


@dataclass(frozen=True)
class ServiceSpec:
    """清单中一条探测目标，以及规范化后的连接参数。

    ``url`` 保留清单里的原始字符串用于展示；``scheme``/``host``/``port``/
    ``target`` 是 ``_parse_service_url`` 校验后的结果，其中 ``target`` 已包含查询
    串。``expected_service`` 只在 ``kind=service`` 时有值，``kind=aggregate`` 时
    为 ``None``。
    """

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
    """单个目标的探测结论。

    ``status`` 是状态机码值（见 ``STATUS_*``）；``http_status`` 在连接未建立或未
    收到响应时为 ``None``；``elapsed_ms`` 由 ``time.monotonic`` 差值换算并向下取整
    到毫秒；``detail`` 是固定措辞的中文说明，永远不包含响应正文。
    """

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
        """是否健康；只有 ``healthy`` 视为通过，其余状态都计入失败。"""
        return self.status == STATUS_HEALTHY


def _contains_control(value: str) -> bool:
    """是否含 C0 控制字符或 DEL（``0x7F``）。

    清单里的名称与 URL 最终会进入终端和 HTML，控制字符会破坏输出、伪造日志行，
    所以在解析阶段直接拒绝，而不是等到渲染时再处理。
    """
    for char in value:
        code = ord(char)
        if code < 0x20 or code == 0x7F:
            return True
    return False


def _validate_loopback_host(host: str) -> None:
    """只接受数值回环地址，避免 localhost 的二次解析和重绑定风险。

    显式拒绝 ``localhost``：它依赖 hosts 解析，既可能落到 IPv6 也可能被改写到
    非回环地址，探测结果会随机器配置漂移；数值地址则不会在运行期被重新解析。

    Raises:
        ConfigError: 主机名不是 IP 字面量，或不是回环地址。
    """
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
    """校验清单里的 url 并拆成 ``http.client`` 需要的连接参数。

    只接受 ASCII 的绝对 ``http``/``https`` 地址：不允许用户名、密码、片段，不允许
    空白或控制字符，总长不超过 2048；主机必须是数值回环地址。缺少端口时按 scheme
    取 80/443，路径为空时用 ``/``，查询串原样保留。

    Args:
        raw_url: 清单中的原始值，可能是任何 JSON 类型。

    Returns:
        ``(scheme, host, port, target)``，其中 ``target`` 为发往目标的请求路径
        （含 ``?`` 查询串）。

    Raises:
        ConfigError: 任一限制不满足；消息只描述规则，不回显敏感内容。
    """
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
    """校验清单里的名称字段，返回去掉首尾空白后的值。

    Args:
        value: 原始值，必须是字符串。
        field_name: 出错时展示的字段路径，例如 ``services[0].name``。

    Raises:
        ConfigError: 非字符串、去空白后为空、超过 120 字符或含控制字符。
    """
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
    """把清单中的一条记录校验并转换成 ``ServiceSpec``。

    字段集合是封闭的：出现 ``name``/``url``/``kind``/``expected_service`` 以外的键
    直接报错，避免拼写错误被静默忽略。``kind=service`` 必须给出非空的
    ``expected_service``，``kind=aggregate`` 则不允许携带该字段。

    Args:
        entry: ``services`` 数组里的元素，可能是任何 JSON 类型。
        index: 数组下标，仅用于拼出 ``services[i]`` 形式的定位。

    Raises:
        ConfigError: 结构、类型、取值或 URL 任一项不合法。
    """
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
    """读取并完整校验清单；任何配置问题都抛 ConfigError。

    读取上限 1 MiB，按 UTF-8（允许 BOM）解码；顶层只允许 ``services``，且必须是
    1 到 256 项的非空数组，服务名称不得重复。全部校验通过后才返回，因此调用方拿到
    的列表可以直接拿去探测。

    Args:
        path: 清单文件路径。

    Returns:
        ``ServiceSpec`` 列表，顺序与清单一致。

    Raises:
        ConfigError: 文件不可读、编码或 JSON 非法、结构不合法、URL 不安全。
    """
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
    """按指定状态打包一条探测结论。

    ``detail`` 只接受固定措辞的说明，调用方不得把响应正文传进来；耗时由
    ``time.monotonic`` 的差值换算成毫秒，负值（理论上不会出现）夹到 0。

    Args:
        spec: 被探测的目标，提供名称、URL、kind 与预期 service。
        status: ``STATUS_*`` 之一。
        started_at: 探测开始时的 ``time.monotonic()`` 读数。
        detail: 面向用户的中文说明。
        http_status: 实际收到的 HTTP 状态码；连接未建立时为 ``None``。

    Returns:
        冻结后的 ``CheckResult``。
    """
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
    """按健康检查契约解析响应体，返回 ``(状态, 中文说明)``。

    契约要点：响应体不能为空且必须是 JSON 对象；``success`` 必须是字面布尔 ``True``
    （字符串 ``"true"``、数字 ``1`` 都不算）。``kind=aggregate`` 还要求布尔
    ``healthy`` 与数组 ``services``，结构合法但 ``healthy=false`` 时单独报告“下游
    不健康”；``kind=service`` 的 ``service`` 必须是字符串，且与清单里的
    ``expected_service`` 完全一致。

    Args:
        spec: 当前目标，决定校验哪一套字段。
        raw_body: 已限制大小的响应字节。

    Returns:
        状态码与固定措辞的说明；任何输入都只映射为状态，不抛异常。
    """
    if not raw_body:
        return STATUS_FORMAT_ERROR, "响应体为空"

    try:
        payload = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError, RecursionError):
        # 嵌套过深的 JSON 会抛 RecursionError，与语法错误一样按“格式错误”处理。
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
    """判断异常是否表示“端口明确拒绝连接”。

    Windows 上拒绝连接可能表现为 ``WSAECONNREFUSED`` 或 ``winerror=10061``，与
    ``ECONNREFUSED`` 不总是等价，所以这里同时检查 ``errno`` 与 ``winerror``，以便把
    “连接被拒绝”与其它网络/TLS 错误分开报告。
    """
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
    """探测单个服务；所有返回值都不包含响应正文。

    只发一次 ``GET``，带 ``Connection: close`` 并显式不跟随 3xx：非 200 一律记为
    ``http_error``。响应体最多读取 ``MAX_RESPONSE_BYTES + 1`` 字节，超出即判
    ``format_error``，避免畸形响应把内存打满。

    网络层异常全部折叠成状态而不是向外抛出，所以单个目标失败不会中断整轮巡检；
    这就是本工具的降级策略。

    Args:
        spec: 已通过清单校验的目标。
        timeout: 连接与读取共用的超时秒数。

    Returns:
        ``CheckResult``；``detail`` 是固定中文说明，不含响应正文，可以安全地写进
        终端和 HTML 报告。
    """
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

        # 多读 1 字节即可判断是否越界，不必把整个超大响应读进内存。
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
        # 关闭失败不影响已经得到的结论，静默忽略即可。
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
    """有界并行执行，并按输入顺序返回结果。

    并发数取 ``min(jobs, len(specs))`` 且至少为 1；只有一个目标时直接串行探测，避免
    为单项创建线程池。使用 ``executor.map`` 而不是 ``as_completed``，返回顺序因此与
    清单一致，汇总和报告都不需要再排序。

    Args:
        specs: 已通过清单校验的目标，顺序即输出顺序。
        timeout: 传给 ``check_service`` 的单目标超时秒数。
        jobs: 并发上限；调用方已在 CLI 层校验过取值范围。

    Returns:
        与 ``specs`` 等长且同序的 ``CheckResult`` 列表；``specs`` 为空时返回空列表。
    """
    if not specs:
        return []
    worker_count = max(1, min(int(jobs), len(specs)))

    # 把 timeout 绑定进闭包，executor.map 只接收 spec，避免每项重复写参数。
    def probe(spec: ServiceSpec) -> CheckResult:
        return check_service(spec, timeout)

    if worker_count == 1:
        return [probe(spec) for spec in specs]

    with ThreadPoolExecutor(
        max_workers=worker_count, thread_name_prefix="service-doctor"
    ) as executor:
        return list(executor.map(probe, specs))


def summarize(results: Sequence[CheckResult]) -> Dict[str, Any]:
    """统计各状态数量，返回 ``total``/``healthy``/``failed``/``counts``。

    ``counts`` 始终包含 ``STATUS_ORDER`` 里的全部状态（未出现记 0），
    ``failed = total - healthy``，因此未知状态也计入失败但不会新增 ``counts`` 键。

    Args:
        results: 一次巡检验证过的结果序列。

    Returns:
        供终端摘要、HTML 概览卡和 CLI 退出码共用的统计字典。
    """
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
    """状态码转中文标签；未知码回退为“未知状态”，保证展示层不会抛 KeyError。"""
    return STATUS_LABELS.get(status, "未知状态")


def _expected_text(result: CheckResult) -> str:
    """报告里“校验目标”一列：聚合接口不校验 service，标准服务列出预期标识。"""
    if result.kind == KIND_AGGREGATE:
        return "聚合接口（不校验 service）"
    return "预期 service={}".format(result.expected_service)


def _http_text(result: CheckResult, missing: str = "—") -> str:
    """报告里“HTTP 状态”一列；未收到响应时使用调用方给的占位符。"""
    if result.http_status is None:
        return missing
    return "HTTP {}".format(result.http_status)


def format_terminal(
    results: Sequence[CheckResult],
    timeout: float,
    jobs: int,
) -> str:
    """把探测结果渲染成终端文本。

    输出顺序固定为：带总数/超时/并发的标题行、逐项一行（状态、名称、URL、耗时、
    HTTP 码、校验目标、说明）、汇总行，以及一行“只探测回环地址”的说明。字段全部
    来自 ``CheckResult`` 的固定枚举值或已校验的清单内容，不含响应正文。

    Args:
        results: 探测结果，按输入顺序输出。
        timeout: 本次使用的超时秒数，写进标题行。
        jobs: 本次使用的并发上限，写进标题行。

    Returns:
        以换行符连接的整段文本，调用方一次 ``print`` 即可。
    """
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


# 报告样式整段内联在模块里，生成的文件因此不依赖外部字体、图片或脚本；这里只描述
# 展示，不拼接任何动态值，所以字符串本身不需要转义。桌面三列概览、移动端单列，
# 打印时去掉滚动容器。
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

# 报告骨架用 string.Template：$css、$generated_at、$rows 等占位符由
# render_html_report 填充。静态 HTML 与文案全部写在这个字面量里，动态值必须先做
# HTML 逃逸再 substitute；不要在这段字符串内部插入注释或改动排版。
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
    """把任意值转成字符串并做 HTML 逃逸（连引号一起转义），用于所有插值点。"""
    return html.escape(str(value), quote=True)


def render_html_report(
    results: Sequence[CheckResult],
    generated_at: Optional[str] = None,
    timeout: Optional[float] = None,
    jobs: Optional[int] = None,
) -> str:
    """生成自包含中文 HTML；所有插值均做 HTML 逃逸，不含响应正文。

    报告含概览卡（检查项/正常/失败）、逐项表格（名称与 URL、类型、状态徽标、HTTP
    状态、耗时、校验目标、说明）和状态分类脚注；CSS 内联，不引用外部资源或脚本。

    Args:
        results: 探测结果，表格行按该顺序输出。
        generated_at: 报告时间文本；``None`` 时取本机当前时间与时区偏移。
        timeout: 本次使用的超时秒数；``None`` 时显示“未记录”。
        jobs: 本次使用的并发上限；``None`` 时显示“未记录”。

    Returns:
        完整 HTML 文档字符串，可直接落盘，也可在测试里断言逃逸结果。
    """
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
    """渲染并写出 HTML 报告。

    固定使用 UTF-8 编码与 LF 换行，保证同一份结果在不同平台上产出相同字节；会覆盖
    同名文件，但父目录必须已存在（本函数不创建目录，主流程另行拒绝覆盖清单文件）。

    Args:
        path: 输出路径。
        results: 探测结果，按输入顺序写进表格。
        generated_at: 报告时间文本；``None`` 时用当前本机时间。
        timeout: 本次使用的超时秒数；``None`` 时显示“未记录”。
        jobs: 本次使用的并发上限；``None`` 时显示“未记录”。

    Raises:
        ReportError: 目标不可写；底层 ``OSError`` 被包装后不再外露，便于 CLI 统一
            映射到配置错误退出码。
    """
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
    """校验超时必须是有限数，且落在允许区间内。

    Raises:
        ConfigError: ``nan``/``inf`` 或越界；提示里给出完整允许范围。
    """
    if not math.isfinite(value):
        raise ConfigError("--timeout 必须是有限数字")
    if not MIN_TIMEOUT_SECONDS <= value <= MAX_TIMEOUT_SECONDS:
        raise ConfigError(
            "--timeout 必须在 {:.2f} 到 {:.0f} 秒之间".format(
                MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS
            )
        )


def _validate_jobs(value: int) -> None:
    """校验并发上限在 1 到 ``MAX_JOBS`` 之间。

    Raises:
        ConfigError: 越界；提示里给出允许范围。
    """
    if not 1 <= value <= MAX_JOBS:
        raise ConfigError("--jobs 必须在 1 到 {} 之间".format(MAX_JOBS))


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 解析器。

    帮助文案与 README 的参数表保持一致；``--timeout``/``--jobs`` 的合法范围写在
    help 里，真正的数值校验留给 ``main``，以便越界时返回文档化的退出码 ``2`` 而不是
    由 argparse 直接退出。

    Returns:
        已注册全部参数的 ``ArgumentParser``。
    """
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
    """CLI 主流程：校验配置 → 探测 → 打印 → 可选写报告 → 返回退出码。

    校验刻意放在探测之前：参数越界、清单不可读、报告路径与清单相同都会在发出任何
    请求前返回 ``2``。结果总是先打印到 stdout，之后才尝试写报告，因此报告写入失败
    时终端结论仍然完整（此时退出码为 ``2``，不表示服务状态）。

    Args:
        argv: 参数列表；``None`` 时由 argparse 读取 ``sys.argv[1:]``。

    Returns:
        ``EXIT_OK``（全部正常）、``EXIT_SERVICE_FAILURE``（至少一项失败）或
        ``EXIT_CONFIG_ERROR``（配置或报告写入错误）；错误信息写到 stderr。
    """
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
                # 报告与清单指向同一文件时拒绝，避免把清单覆盖成 HTML；路径解析失败
                # 时按“不同文件”处理，真正的写入错误会由 write_html_report 报告。
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
