"""统一模型配置读取。

所有服务只读项目根目录的 ``model.properties``：提供商地址、密钥、模型目录和服务原配置都在里面。
文件不入库，只按当前目录与代码目录向上查找，不读取模型相关环境变量。
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

FILE_NAME = "model.properties"
GLOBAL_SCOPE = "global"


class Provider:
    def __init__(self, provider_id: str, label: str, base_url: str, api_key: str,
                 capability: str, models: list[str], options: dict[str, str]) -> None:
        self.id = provider_id
        self.label = label
        self.base_url = base_url
        self.api_key = api_key
        self.capability = capability
        self.models = models
        self.options = options

    @property
    def text(self) -> bool:
        return self.capability == "text"

    def option(self, name: str, default: str = "") -> str:
        value = self.options.get(name, "").strip()
        return value or default

    def int_option(self, name: str, default: int) -> int:
        try:
            return int(self.option(name, str(default)))
        except ValueError:
            return default

    def option_list(self, name: str) -> list[str]:
        return _split_list(self.option(name))

    def __repr__(self) -> str:  # 不输出密钥
        return f"Provider(id={self.id!r}, base_url={self.base_url!r}, models={self.models!r})"


class Route:
    def __init__(self, provider: Provider, model_id: str) -> None:
        self.provider = provider
        self.model_id = model_id

    @property
    def id(self) -> str:
        return f"{self.provider.id}:{self.model_id}"

    def __repr__(self) -> str:
        return f"Route({self.id!r})"


class ModelProperties:
    def __init__(self, path: Path, exists: bool, providers: dict[str, Provider],
                 routes: dict[str, str]) -> None:
        self.path = path
        self.exists = exists
        self._providers = providers
        self._routes = routes

    @property
    def providers(self) -> Iterable[Provider]:
        return self._providers.values()

    def provider(self, provider_id: str) -> Provider | None:
        return self._providers.get((provider_id or "").strip().lower())

    def text_providers(self) -> list[Provider]:
        return [provider for provider in self._providers.values() if provider.text]

    def route(self, scope: str) -> Route | None:
        return self._parse_route(self._routes.get(scope)) or (
            self._parse_route(self._routes.get(GLOBAL_SCOPE)) if scope != GLOBAL_SCOPE else None)

    def _parse_route(self, raw: str | None) -> Route | None:
        if not raw:
            return None
        value = raw.strip()
        if ":" not in value:
            return None
        provider_id, model_id = value.split(":", 1)
        provider = self.provider(provider_id)
        if provider is None or not model_id.strip():
            return None
        return Route(provider, model_id.strip())

    @classmethod
    def locate(cls, start: Path | None = None) -> Path:
        bases: list[Path] = [Path(start) if start else Path.cwd()]
        try:
            bases.extend(Path(__file__).resolve().parents)
        except OSError:
            pass
        for base in bases:
            for candidate in [base, *base.parents]:
                file = candidate / FILE_NAME
                if file.is_file():
                    return file
        return (Path(start) if start else Path.cwd()).resolve() / FILE_NAME

    @classmethod
    def load(cls, path: Path | None = None) -> ModelProperties:
        file = Path(path).expanduser().resolve() if path else cls.locate()
        if not file.is_file():
            return cls(file, False, {}, {})
        raw = _read(file)
        return cls(file, True, *_parse(raw))


def _read(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    pending = ""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        text = pending + line.strip()
        if text.endswith("\\"):
            pending = text[:-1]
            continue
        pending = ""
        if not text or text.startswith(("#", "!")):
            continue
        if "=" not in text:
            continue
        key, value = text.split("=", 1)
        values[key.strip()] = value.strip()
    if pending:
        values.setdefault(pending, "")
    return values


def _split_list(raw: str) -> list[str]:
    names: list[str] = []
    for part in str(raw or "").split(","):
        name = part.strip()
        if name and name not in names:
            names.append(name)
    return names


def _parse(values: dict[str, str]):
    providers: dict[str, Provider] = {}
    routes: dict[str, str] = {}
    groups: dict[str, dict[str, str]] = {}
    for name, value in values.items():
        key = name.strip()
        if not key:
            continue
        if key.startswith("service."):
            scope = key[len("service."):].strip().lower()
            if scope and value.strip():
                routes[scope] = value.strip()
            continue
        if "." not in key:
            continue
        provider_id, field = key.split(".", 1)
        provider_id, field = provider_id.strip().lower(), field.strip().lower()
        if not provider_id or not field:
            continue
        groups.setdefault(provider_id, {})[field] = value.strip()
    for provider_id, fields in groups.items():
        base_url = fields.get("base-url", "").rstrip("/")
        if not base_url:
            continue
        options = {key: value for key, value in fields.items()
                   if key not in {"label", "base-url", "api-key", "capability", "models"}}
        providers[provider_id] = Provider(
            provider_id,
            fields.get("label", provider_id),
            base_url,
            fields.get("api-key", ""),
            fields.get("capability", "text") or "text",
            _split_list(fields.get("models", "")),
            options,
        )
    return providers, routes
