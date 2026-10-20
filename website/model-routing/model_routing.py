"""Python 微服务统一模型路由客户端。仅标准库，不读取或传递密钥。"""
import json
import os
from pathlib import Path
from urllib import error, parse, request


class ModelRoutingError(RuntimeError):
    pass


def _hub():
    url = os.environ.get("MODEL_HUB_URL", "http://127.0.0.1:8080").rstrip("/")
    parsed = parse.urlparse(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.path:
        raise ModelRoutingError("MODEL_HUB_URL 必须是本机回环 HTTP 地址")
    return url


def _call(path, payload=None, timeout=3):
    req = request.Request(
        _hub() + path,
        data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Love530-Model": "1"},
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except error.HTTPError as exc:
        raise ModelRoutingError("统一模型入口拒绝请求，请检查模型状态或私有凭据") from exc


def active(service):
    try:
        return bool(_call("/api/models/effective/" + service, timeout=2).get("active"))
    except (error.URLError, TimeoutError, OSError, ModelRoutingError, ValueError):
        configured = os.environ.get("MODEL_ROUTING_STATE")
        state = Path(configured) if configured else next(
            (p / ".runtime/model-routing.json" for p in Path(__file__).resolve().parents
             if (p / ".runtime/model-routing.json").exists()), None)
        if state and state.exists():
            try:
                selected = json.loads(state.read_text(encoding="utf-8"))
                model = selected.get(service) or selected.get("global", "")
                if model and model != "native":
                    raise ModelRoutingError("统一模型入口离线，请先启动 website；已选模型不会自动改变")
            except (OSError, ValueError) as exc:
                raise ModelRoutingError("无法读取统一模型选择") from exc
        return False


def chat(service, payload):
    try:
        return _call("/api/models/chat/" + service, payload, timeout=310)
    except (error.URLError, TimeoutError, OSError) as exc:
        raise ModelRoutingError("统一模型请求失败，请检查 website 和模型提供方") from exc
