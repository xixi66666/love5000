"""统一模型入口的公共 Python 客户端。

被 python-a、scrapling-ui、skill-finder 共用：源码只放在 ``website/model-routing``，
部署时由 ``scripts/sync-model-routing.py`` 逐字节复制为各服务的 ``_model_routing.py``，
因此本文件不得依赖同目录以外的模块。

两条通道：

- 统一路由（``active``/``chat``/``try_chat``）：只访问固定网关 ``http://127.0.0.1:8080``，
  用 ``X-Love530-Model`` 自定义头标识本机服务调用，绝不携带提供方密钥；
- 原配置直连（``native_chat``/``native_chat_async``）：用调用方给的密钥直连提供方，
  只在网关明确回 204（含义是“按服务原配置处理”）或状态确认没有统一选择时使用。

失败策略：网关超时/HTTP 错误一律抛 ``ModelRoutingError``，不自动改道，避免把一次可能
已经计费成功的请求重放；只有“连接被拒绝且状态文件确认无已选模型”才允许退回原配置。
提供方错误只暴露 HTTP 状态码，响应正文（可能回显凭据）不进入异常消息。
"""

import asyncio
import json
from pathlib import Path
from urllib import error, parse, request


class ModelRoutingError(RuntimeError):
    """统一模型入口不可用、返回格式无效或状态不可信时抛出。

    调用方应把消息原样展示给用户（文案已脱敏），并放弃本次生成，不要换模型重试。
    """
    pass  # noqa: PIE790


class ModelProviderError(RuntimeError):
    """提供方直连失败，只携带 HTTP 状态码。

    ``status`` 为 None 表示传输层失败（DNS、超时、地址不合法等）。响应正文、请求头与
    密钥不会进入异常消息，避免随日志外泄。
    """
    def __init__(self, status=None):
        """构造异常并保留状态码。

        Args:
            status: 提供方返回的 HTTP 状态码；传输层失败时为 None。
        """
        self.status = status
        super().__init__("模型请求失败" + (f"：HTTP {status}" if status else "，请检查提供方配置"))


# 单次响应上限 8 MiB：模型输出与模型列表都远小于它，超限直接判为异常。
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class _NoRedirect(request.HTTPRedirectHandler):
    """禁止跟随 HTTP 重定向。

    ``Authorization`` 头不能被 3xx 带到第三方主机，否则 ``model.properties`` 里写错一个
    地址就可能把密钥发给陌生域名。
    """
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """urllib 的钩子：返回 None 即拒绝跟随重定向。

        不抛异常而是返回 None，是为了让调用方拿到原始 3xx 响应（``HTTPError``），
        从而按“网关异常”处理而不是静默变换目标地址。
        """
        return None  # noqa: RET501


def _open(req, timeout):
    """用禁用重定向的 opener 发请求。

    Args:
        req: 已带请求头与正文的 ``Request``。
        timeout: 超时秒数，超时会抛 ``TimeoutError``/``URLError``。

    Returns:
        可 ``with`` 的响应对象（``http.client.HTTPResponse``）。
    """
    return request.build_opener(_NoRedirect()).open(req, timeout=timeout)


def _decode(raw):
    """把响应字节解析成 JSON 对象。

    Args:
        raw: 原始响应体。

    Returns:
        顶层为 dict 的解析结果。

    Raises:
        ValueError: 超过 ``MAX_RESPONSE_BYTES``，防止异常响应把内存打满。
        TypeError: 顶层不是对象（数组、``null`` 都视为无效）。
    """
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("模型响应过大")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TypeError("模型响应格式无效")
    return data


# 网关固定为本机 website（8080）；不再读取 MODEL_HUB_URL 之类的环境变量。
_HUB = "http://127.0.0.1:8080"


def _hub():
    """返回固定网关基址；独立成函数便于测试替换。"""
    return _HUB


def _call(path, payload=None, timeout=3, allow_native=False):
    """向统一模型入口发一次 JSON 请求。

    请求固定带 ``X-Love530-Model`` 自定义头，website 据此区分“浏览器直接调用”与
    “受信任的本机服务调用”，因此不要手工构造同样的请求。

    Args:
        path: 以 ``/`` 开头的接口路径，服务标识由调用方拼好。
        payload: JSON 可序列化对象；None 表示发 GET。
        timeout: 超时秒数；生成类接口给到 310 秒。
        allow_native: 是否允许把 204 解释为“改用服务原配置”。

    Returns:
        解析后的响应 dict；``allow_native`` 为真且上游返回 204 时返回 None。

    Raises:
        ModelRoutingError: HTTP 错误、响应过大或 JSON 结构不符；上游原文不进消息。
    """
    req = request.Request(
        _hub() + path,
        data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Love530-Model": "1"},
    )
    try:
        with _open(req, timeout) as response:
            if response.status == 204 and allow_native:
                return None
            return _decode(response.read(MAX_RESPONSE_BYTES + 1))
    except error.HTTPError as exc:
        raise ModelRoutingError("统一模型入口拒绝请求，请检查模型状态或私有凭据") from exc
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ModelRoutingError("统一模型入口返回格式无效") from exc


def _state_path():
    """定位根目录的 ``.runtime/model-routing.json``（只存模型 ID）。

    从本文件所在目录逐级向上查找；找不到返回 None——部署副本所在目录可能没有该状态文件，
    此时按“没有统一选择”处理。
    """
    return next(
        (p / ".runtime/model-routing.json" for p in Path(__file__).resolve().parents
         if (p / ".runtime/model-routing.json").exists()), None)


def _require_native(service):
    """网关不可达时，判断当前服务能否安全退回原配置。

    只有状态文件里该服务与 ``global`` 都没有具体模型（或显式写成 ``native``）才算允许；
    文件损坏或读不出来时按“已选模型”处理并抛错，宁可失败也不重复调用计费接口。

    Raises:
        ModelRoutingError: 状态文件不可读，或存在已选模型——网关离线时不能静默改道。
    """
    state = _state_path()
    if state and state.exists():
        try:
            selected = json.loads(state.read_text(encoding="utf-8"))
            if not isinstance(selected, dict):
                raise TypeError("invalid state")
            local = selected.get(service, "")
            global_model = selected.get("global", "")
            if not isinstance(local, str) or not isinstance(global_model, str):
                raise TypeError("invalid selection")
        except (OSError, ValueError, TypeError) as exc:
            raise ModelRoutingError("无法读取统一模型选择") from exc
        model = local or global_model
        if model and model != "native":
            raise ModelRoutingError("统一模型入口离线，请先启动 website；已选模型不会自动改变")


def _connection_refused(exc):
    """判断是否为“连接被拒绝”，这是唯一允许退回原配置的传输层错误。

    POST 超时可能已产生结果和费用，不能据此再调用原模型；因此只有连接被拒绝这一种
    确定性失败，才允许在状态文件确认无已选模型后退回原配置。
    """
    return isinstance(exc, error.URLError) and isinstance(exc.reason, ConnectionRefusedError)


def active(service):
    """查询统一入口当前是否接管该服务。

    Returns:
        True 表示由统一入口处理；False 表示调用方应使用服务原配置。

    Raises:
        ModelRoutingError: 网关超时/HTTP 错误，或网关离线但状态文件显示已选模型。
    """
    try:
        return bool(_call("/api/models/effective/" + service, timeout=2).get("active"))
    except (error.URLError, TimeoutError, OSError) as exc:
        if _connection_refused(exc):
            _require_native(service)
            return False
        raise ModelRoutingError("统一模型状态查询失败") from exc


def try_chat(service, payload):
    """用一次 POST 完成生成，路由与原配置的取舍由网关内部决定。

    Args:
        service: 服务标识，例如 ``python-a``。
        payload: 对话请求体（model/messages/采样参数等）。

    Returns:
        模型结果 dict；网关返回 204 时返回 None，表示调用方应改用服务原配置。

    Raises:
        ModelRoutingError: 超时、HTTP 错误或响应结构无效——可能已产生费用的请求
            不会在这里被重放。
    """
    try:
        return _call("/api/models/complete/" + service, payload, timeout=310, allow_native=True)
    except (error.URLError, TimeoutError, OSError) as exc:
        if _connection_refused(exc):
            _require_native(service)
            return None
        raise ModelRoutingError("统一模型请求失败；不会自动换模型") from exc


def chat(service, payload):
    """旧版生成接口（``/api/models/chat``），保留兼容。

    与 ``try_chat`` 的区别是没有 204 语义：任何非 2xx 都按失败处理。

    Returns:
        模型结果 dict，结构由 website 网关决定（通常含 ``model`` 与 ``choices``）。

    Raises:
        ModelRoutingError: 网关不可达或返回非 2xx。
    """
    try:
        return _call("/api/models/chat/" + service, payload, timeout=310)
    except (error.URLError, TimeoutError, OSError) as exc:
        raise ModelRoutingError("统一模型请求失败，请检查 website 和模型提供方") from exc


def _native_headers(url, key, headers):
    """构造原配置直连所需的请求头，并校验目标地址。

    拒绝带用户名/密码、查询串、片段或非 HTTP(S) 的地址；``http`` 只允许回环主机，
    这样 ``model.properties`` 被改成明文外发地址时密钥不会真的发出去。

    Args:
        url: 提供方的 ``/chat/completions`` 地址。
        key: 提供方 API Key。
        headers: 附加请求头（例如 OpenCode Go 的会话头），可为 None。

    Returns:
        合并了 ``Content-Type`` 与 ``Authorization`` 的新字典。

    Raises:
        ModelProviderError: 地址不满足上述约束。
    """
    parsed = parse.urlparse(url)
    if (parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname
            or (parsed.scheme != "https" and not (
                parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}))):
        raise ModelProviderError()
    result = dict(headers or {})
    result.update({"Content-Type": "application/json", "Authorization": "Bearer " + key})
    return result


def native_chat(url, key, payload, timeout=90, headers=None):
    """用服务原配置同步直连提供方。

    Args:
        url: 完整 ``/chat/completions`` 地址。
        key: 提供方密钥。
        payload: 请求体。
        timeout: 超时秒数，默认 90。
        headers: 附加请求头。

    Returns:
        解析后的响应 dict。

    Raises:
        ModelProviderError: 非 2xx、传输失败或响应不是 JSON 对象；只带状态码。
    """
    req = request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                          headers=_native_headers(url, key, headers))
    try:
        with _open(req, timeout) as response:
            return _decode(response.read(MAX_RESPONSE_BYTES + 1))
    except error.HTTPError as exc:
        raise ModelProviderError(exc.code) from None
    except (error.URLError, OSError, ValueError, TypeError, UnicodeError):
        raise ModelProviderError() from None


async def native_chat_async(client, url, key, payload, timeout=90, headers=None):
    # 使用调用方已有异步连接池；不引入额外依赖或重复实现鉴权/响应解析。
    """异步版直连，复用调用方已有的 httpx 客户端与连接池。

    Args:
        client: 具备 ``post(...)`` 的异步客户端（``httpx.AsyncClient``）。
        url: 提供方接口地址。
        key: 提供方密钥。
        payload: 请求体。
        timeout: 超时秒数，默认 90。
        headers: 附加请求头。

    Returns:
        解析后的响应 dict。

    Raises:
        ModelProviderError: 非 2xx 或响应无效，只暴露状态码。
    """
    response = await client.post(url, headers=_native_headers(url, key, headers),
                                 json=payload, timeout=timeout, follow_redirects=False)
    if not 200 <= response.status_code < 300:
        raise ModelProviderError(response.status_code)
    try:
        return _decode(response.content)
    except (ValueError, TypeError, UnicodeError):
        raise ModelProviderError() from None


class ServiceModelClient:
    """把固定服务标识与同步/异步适配封装在一起。

    python-a 用同步方法，FastAPI 服务用 ``*_async`` 方法；异步路径统一走
    ``asyncio.to_thread``，因此不需要为异步再写一套请求与鉴权实现。
    """
    def __init__(self, service):
        """绑定服务标识。

        Args:
            service: 服务标识，用于拼 ``/api/models/*/<service>`` 路径。
        """
        self.service = service

    def active(self):
        """是否由统一入口接管；失败语义同模块级 ``active``。"""
        return active(self.service)

    def try_chat(self, payload):
        """单次生成；返回 None 表示调用方应改用服务原配置。"""
        return try_chat(self.service, payload)

    async def try_chat_async(self, payload):
        """``try_chat`` 的线程池包装，供异步调用方使用。"""
        return await asyncio.to_thread(self.try_chat, payload)

    async def active_async(self):
        """``active`` 的线程池包装。"""
        return await asyncio.to_thread(self.active)
