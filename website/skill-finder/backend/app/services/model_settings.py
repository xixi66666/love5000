"""Skill Finder 的模型配置读取：统一走项目根目录 model.properties。

对上层屏蔽 `model.properties` 的解析细节，只暴露“简介该用哪个模型/地址/密钥”和
“MiMo 配音 provider”两类查询。文件缺失、服务未配置或密钥为空时返回空值而不是抛错，
调用方（``introduction_service``）据此判断是“认证失败停止”还是“未配置降级”。
密钥只在调用请求头时读取一次，不落日志、不进响应。
"""
from __future__ import annotations

from . import _model_properties as model_properties


def load() -> model_properties.ModelProperties:
    """从项目根目录读取并解析 ``model.properties``。

    不做缓存：文件被修改后下一次调用即生效，代价是一次小文件读取。

    Returns:
        解析后的配置对象；文件缺失时返回空配置（各 getter 返回空串/``None``）。
    """
    return model_properties.ModelProperties.load()


def intro_route() -> model_properties.Route | None:
    """取 ``service.skill-finder`` 指向的模型路由。

    Returns:
        包含 provider 与模型 ID 的路由；未配置该服务时为 ``None``。
    """
    return load().route("skill-finder")


def intro_models(override: str = "") -> list[str]:
    """简介模型回退链；override 保留原有显式指定能力。"""
    raw = override.strip()
    if raw:
        source = [part.strip() for part in raw.split(",")]
    else:
        route = intro_route()
        if route is None:
            return []
        source = [route.model_id] + [name for name in route.provider.models if name != route.model_id]
    chain: list[str] = []
    for name in source:
        model = name.split("/", 1)[1] if "/" in name else name
        if model and model not in chain:
            chain.append(model)
    return chain


def intro_base_url() -> str:
    """简介模型的基础地址（OpenAI 兼容，调用方自行拼 ``/chat/completions``）。

    Returns:
        未配置 service 路由时为空串，调用方会因密钥/模型为空而提前失败。
    """
    route = intro_route()
    return route.provider.base_url if route else ""


def intro_api_key() -> str:
    """简介模型的 API Key。

    只用于请求头；不要打印或写进异常消息（``introduction_service`` 抛出的文案
    只说明“密钥未配置/认证失败”，不带值）。

    Returns:
        Key 字符串；未配置时为空串。
    """
    route = intro_route()
    return route.provider.api_key if route else ""


def mimo():
    """取 MiMo provider 配置，供日报配音（TTS）使用。

    语音与视频不参与统一文本模型路由，因此这里直接读 provider 段。

    Returns:
        provider 配置对象；不存在时由底层返回空值，调用方按“未配置”处理。
    """
    return load().provider("mimo")
