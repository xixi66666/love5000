"""Skill Finder 的模型配置读取：统一走项目根目录 model.properties。"""
from __future__ import annotations

from . import _model_properties as model_properties


def load() -> model_properties.ModelProperties:
    return model_properties.ModelProperties.load()


def intro_route() -> model_properties.Route | None:
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
    route = intro_route()
    return route.provider.base_url if route else ""


def intro_api_key() -> str:
    route = intro_route()
    return route.provider.api_key if route else ""


def mimo():
    return load().provider("mimo")
