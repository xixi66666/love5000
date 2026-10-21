"""模型路由与原配置的公共传输；统一路由不读取或传递提供方密钥。"""
import asyncio
import json
import os
from pathlib import Path
from urllib import error, parse, request


class ModelRoutingError(RuntimeError):
    pass


class ModelProviderError(RuntimeError):
    """只携带 HTTP 状态，不保留可能包含凭据的响应正文。"""
    def __init__(self, status=None):
        self.status = status
        super().__init__("模型请求失败" + (f"：HTTP {status}" if status else "，请检查提供方配置"))


MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open(req, timeout):
    return request.build_opener(_NoRedirect()).open(req, timeout=timeout)


def _decode(raw):
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("模型响应过大")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TypeError("模型响应格式无效")
    return data


def _hub():
    url = os.environ.get("MODEL_HUB_URL", "http://127.0.0.1:8080").rstrip("/")
    parsed = parse.urlparse(url)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username
            or parsed.path or parsed.query or parsed.fragment):
        raise ModelRoutingError("MODEL_HUB_URL 必须是本机回环 HTTP 地址")
    return url


def _call(path, payload=None, timeout=3, allow_native=False):
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


def _require_native(service):
    configured = os.environ.get("MODEL_ROUTING_STATE")
    state = Path(configured) if configured else next(
        (p / ".runtime/model-routing.json" for p in Path(__file__).resolve().parents
         if (p / ".runtime/model-routing.json").exists()), None)
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
    # POST 超时可能已产生结果和费用，不能据此再调用原模型。
    return isinstance(exc, error.URLError) and isinstance(exc.reason, ConnectionRefusedError)


def active(service):
    try:
        return bool(_call("/api/models/effective/" + service, timeout=2).get("active"))
    except (error.URLError, TimeoutError, OSError) as exc:
        if _connection_refused(exc):
            _require_native(service)
            return False
        raise ModelRoutingError("统一模型状态查询失败") from exc


def try_chat(service, payload):
    """一次请求完成路由；仅 204 或安全的离线原配置返回 None。"""
    try:
        return _call("/api/models/complete/" + service, payload, timeout=310, allow_native=True)
    except (error.URLError, TimeoutError, OSError) as exc:
        if _connection_refused(exc):
            _require_native(service)
            return None
        raise ModelRoutingError("统一模型请求失败；不会自动换模型") from exc


def chat(service, payload):
    try:
        return _call("/api/models/chat/" + service, payload, timeout=310)
    except (error.URLError, TimeoutError, OSError) as exc:
        raise ModelRoutingError("统一模型请求失败，请检查 website 和模型提供方") from exc


def _native_headers(url, key, headers):
    parsed = parse.urlparse(url)
    if (parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname
            or (parsed.scheme != "https" and not (
                parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}))):
        raise ModelProviderError()
    result = dict(headers or {})
    result.update({"Content-Type": "application/json", "Authorization": "Bearer " + key})
    return result


def native_chat(url, key, payload, timeout=90, headers=None):
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
    response = await client.post(url, headers=_native_headers(url, key, headers),
                                 json=payload, timeout=timeout, follow_redirects=False)
    if not 200 <= response.status_code < 300:
        raise ModelProviderError(response.status_code)
    try:
        return _decode(response.content)
    except (ValueError, TypeError, UnicodeError):
        raise ModelProviderError() from None


class ServiceModelClient:
    """把固定服务标识和同步/异步适配收在公共客户端。"""
    def __init__(self, service):
        self.service = service

    def active(self):
        return active(self.service)

    def try_chat(self, payload):
        return try_chat(self.service, payload)

    async def try_chat_async(self, payload):
        return await asyncio.to_thread(self.try_chat, payload)

    async def active_async(self):
        return await asyncio.to_thread(self.active)
