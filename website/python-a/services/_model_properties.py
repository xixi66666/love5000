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
        value = _trim(self.options.get(name, ""))
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
        return self._providers.get(_trim(provider_id or "").lower())

    def text_providers(self) -> list[Provider]:
        return [provider for provider in self._providers.values() if provider.text]

    def route(self, scope: str) -> Route | None:
        return self._parse_route(self._routes.get(scope)) or (
            self._parse_route(self._routes.get(GLOBAL_SCOPE)) if scope != GLOBAL_SCOPE else None)

    def _parse_route(self, raw: str | None) -> Route | None:
        if not raw:
            return None
        value = _trim(raw)
        if ":" not in value:
            return None
        provider_id, model_id = value.split(":", 1)
        provider = self.provider(provider_id)
        if provider is None or not _trim(model_id):
            return None
        return Route(provider, _trim(model_id))

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


_WHITESPACE = " \t\f"


def _read(path: Path) -> dict[str, str]:
    """按 ``java.util.Properties.load(Reader)`` 的语法读取 UTF-8 属性文件。

    允许一个 UTF-8 BOM；自然换行、注释、续行、分隔符、转义和重复键
    均与 Java 保持一致。值保持原样（含尾部空格），由 ``_parse`` 统一裁剪。
    """
    values: dict[str, str] = {}
    for line in _logical_lines(path.read_bytes().decode("utf-8-sig")):
        key, value = _split_property(line)
        values[key] = value
    return values


def _logical_lines(text: str) -> Iterable[str]:
    """生成 Properties 的逻辑行，移植自 OpenJDK LineReader.readLine。"""
    line: list[str] = []
    offset = 0
    length = len(text)
    skip_white_space = True
    is_comment_line = False
    is_new_line = True
    appended_line_begin = False
    preceding_backslash = False
    skip_lf = False

    while True:
        if offset >= length:
            if not line or is_comment_line:
                return
            if preceding_backslash:
                line.pop()
            yield "".join(line)
            return

        char = text[offset]
        offset += 1

        if skip_lf:
            skip_lf = False
            if char == "\n":
                continue

        if skip_white_space:
            if char in _WHITESPACE:
                continue
            if not appended_line_begin and char in "\r\n":
                continue
            skip_white_space = False
            appended_line_begin = False

        if is_new_line:
            is_new_line = False
            if char in "#!":
                is_comment_line = True
                continue

        if char not in "\r\n":
            line.append(char)
            if char == "\\":
                preceding_backslash = not preceding_backslash
            else:
                preceding_backslash = False
            continue

        if is_comment_line or not line:
            is_comment_line = False
            is_new_line = True
            skip_white_space = True
            line.clear()
            continue

        if preceding_backslash:
            line.pop()
            skip_white_space = True
            appended_line_begin = True
            preceding_backslash = False
            if char == "\r":
                skip_lf = True
            continue

        yield "".join(line)
        line.clear()
        skip_white_space = True
        is_comment_line = False
        is_new_line = True
        appended_line_begin = False
        preceding_backslash = False
        skip_lf = False


def _split_property(line: str) -> tuple[str, str]:
    """拆分逻辑行为 key/value，移植自 OpenJDK Properties.load0。"""
    limit = len(line)
    key_length = 0
    value_start = limit
    has_separator = False
    preceding_backslash = False

    while key_length < limit:
        char = line[key_length]
        if char in "=:" and not preceding_backslash:
            value_start = key_length + 1
            has_separator = True
            break
        if char in _WHITESPACE and not preceding_backslash:
            value_start = key_length + 1
            break
        if char == "\\":
            preceding_backslash = not preceding_backslash
        else:
            preceding_backslash = False
        key_length += 1

    while value_start < limit:
        char = line[value_start]
        if char not in _WHITESPACE:
            if not has_separator and char in "=:":
                has_separator = True
            else:
                break
        value_start += 1

    return _unescape(line[:key_length]), _unescape(line[value_start:])


def _unescape(raw: str) -> str:
    """处理 Properties 的 ``\\t``/``\\n``/``\\r``/``\\f``/``\\uXXXX``。"""
    value: list[str] = []
    offset = 0
    length = len(raw)
    while offset < length:
        char = raw[offset]
        offset += 1
        if char != "\\":
            value.append(char)
            continue
        if offset >= length:
            raise ValueError("Malformed \\uxxxx encoding.")
        char = raw[offset]
        offset += 1
        if char == "u":
            digits = raw[offset:offset + 4]
            if len(digits) != 4 or any(digit not in "0123456789abcdefABCDEF" for digit in digits):
                raise ValueError("Malformed \\uxxxx encoding.")
            value.append(chr(int(digits, 16)))
            offset += 4
        elif char == "t":
            value.append("\t")
        elif char == "r":
            value.append("\r")
        elif char == "n":
            value.append("\n")
        elif char == "f":
            value.append("\f")
        else:
            value.append(char)
    return "".join(value)


def _trim(value: str) -> str:
    """等价于 Java String.trim：只裁剪 U+0020 及以下字符。"""
    start = 0
    end = len(value)
    while start < end and ord(value[start]) <= 0x20:
        start += 1
    while end > start and ord(value[end - 1]) <= 0x20:
        end -= 1
    return value[start:end]


def _split_list(raw: str) -> list[str]:
    names: list[str] = []
    for part in str(raw or "").split(","):
        name = _trim(part)
        if name and name not in names:
            names.append(name)
    return names


def _parse(values: dict[str, str]):
    providers: dict[str, Provider] = {}
    routes: dict[str, str] = {}
    groups: dict[str, dict[str, str]] = {}
    for name, value in values.items():
        key = _trim(name)
        if not key:
            continue
        if key.startswith("service."):
            scope = _trim(key[len("service."):]).lower()
            if scope and _trim(value):
                routes[scope] = _trim(value)
            continue
        if "." not in key:
            continue
        provider_id, field = key.split(".", 1)
        provider_id, field = _trim(provider_id).lower(), _trim(field).lower()
        if not provider_id or not field:
            continue
        groups.setdefault(provider_id, {})[field] = _trim(value)
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
