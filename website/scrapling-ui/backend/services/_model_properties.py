"""统一模型配置读取（Python 侧公共源码）。

所有服务只读项目根目录的 ``model.properties``：提供商地址、密钥、模型目录和服务原配置都在里面。
文件不入库，只按当前目录与代码目录向上查找，不读取模型相关环境变量。

解析语义对齐 ``java.util.Properties``：``#``/``!`` 注释、反斜杠续行、``=``/``:``/空白分隔、
``\\uXXXX`` 转义与“重复键后者覆盖前者”都按 OpenJDK 实现移植，保证 Java 与 Python 读同一份
文件得到一致结果。``website/model-routing`` 是唯一源码，部署副本 ``_model_properties.py``
由 ``scripts/sync-model-routing.py`` 逐字节复制，两侧不允许出现差异。

失败处理：文件缺失时返回 ``exists=False`` 的空配置而不抛异常（便于提示部署未挂载）；
非法 ``\\uXXXX`` 与 Java 一样抛 ``ValueError``；没有 ``base-url`` 的提供商整段忽略。
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

FILE_NAME = "model.properties"
GLOBAL_SCOPE = "global"


class Provider:
    """单个模型提供方的配置快照。

    标准键为 ``label``/``base-url``/``api-key``/``capability``/``models``，其余键全部收进
    ``options``，供各服务读取私有参数（例如 ``tts-model``、图片尺寸白名单）。
    """
    def __init__(self, provider_id: str, label: str, base_url: str, api_key: str,
                 capability: str, models: list[str], options: dict[str, str]) -> None:
        """保存一条提供方配置。

        Args:
            provider_id: 规范化后的提供方 ID（小写、去空白）。
            label: 展示名，缺省等于 ID。
            base_url: 已去掉末尾斜杠的基础地址。
            api_key: 密钥；空串表示未配置，真正调用前由调用方校验。
            capability: ``text`` 为文本能力，其它值（如 ``image``）不会被文本选择器列出。
            models: 可用模型 ID 列表，按文件顺序。
            options: 除标准键外的全部自定义键值。
        """
        self.id = provider_id
        self.label = label
        self.base_url = base_url
        self.api_key = api_key
        self.capability = capability
        self.models = models
        self.options = options

    @property
    def text(self) -> bool:
        """是否为文本能力提供商（``capability`` 缺省即 ``text``）。"""
        return self.capability == "text"

    def option(self, name: str, default: str = "") -> str:
        """读取一个自定义选项并去掉首尾空白，空值回退 ``default``。"""
        value = _trim(self.options.get(name, ""))
        return value or default

    def int_option(self, name: str, default: int) -> int:
        """读取整数选项；非数字时回退 ``default`` 而不抛异常。"""
        try:
            return int(self.option(name, str(default)))
        except ValueError:
            return default

    def option_list(self, name: str) -> list[str]:
        """读取逗号分隔的选项，去空白、去重并保持出现顺序。"""
        return _split_list(self.option(name))

    def __repr__(self) -> str:  # 不输出密钥
        """仅用于排查配置，刻意不输出 ``api_key``。"""
        return f"Provider(id={self.id!r}, base_url={self.base_url!r}, models={self.models!r})"


class Route:
    """一条服务路由：提供方对象 + 模型 ID。"""
    def __init__(self, provider: Provider, model_id: str) -> None:
        """绑定提供方与模型。

        Args:
            provider: 已解析的提供方。
            model_id: 该提供方下的模型 ID。
        """
        self.provider = provider
        self.model_id = model_id

    @property
    def id(self) -> str:
        """``provider:model`` 形式的稳定标识，与 ``model.properties`` 的写法一致。"""
        return f"{self.provider.id}:{self.model_id}"

    def __repr__(self) -> str:
        """仅用于日志与断言。"""
        return f"Route({self.id!r})"


class ModelProperties:
    """一份已解析的 ``model.properties``。

    构造后只读：``providers`` 按文件出现顺序保留，``route(scope)`` 在服务未配置时回退到
    ``service.global``。``exists=False`` 表示文件缺失（例如容器里没挂载），调用方应据此
    提示部署问题，而不是把它当成“用户故意留空”。
    """
    def __init__(self, path: Path, exists: bool, providers: dict[str, Provider],
                 routes: dict[str, str]) -> None:
        """保存解析结果。

        Args:
            path: 配置文件路径；即使文件不存在也记录下来，便于错误提示。
            exists: 文件是否真实存在。
            providers: ``{id: Provider}``，保持文件中的出现顺序。
            routes: ``{scope: "provider:model"}`` 原始字符串路由。
        """
        self.path = path
        self.exists = exists
        self._providers = providers
        self._routes = routes

    @property
    def providers(self) -> Iterable[Provider]:
        """按文件顺序迭代全部提供方。"""
        return self._providers.values()

    def provider(self, provider_id: str) -> Provider | None:
        """按 ID 取提供方，ID 的大小写与首尾空白不敏感；不存在返回 None。"""
        return self._providers.get(_trim(provider_id or "").lower())

    def text_providers(self) -> list[Provider]:
        """全部文本能力提供方，供模型选择器列出候选项。"""
        return [provider for provider in self._providers.values() if provider.text]

    def route(self, scope: str) -> Route | None:
        """取某个服务的路由；该服务未配置时回退 ``service.global``。"""
        return self._parse_route(self._routes.get(scope)) or (
            self._parse_route(self._routes.get(GLOBAL_SCOPE)) if scope != GLOBAL_SCOPE else None)

    def _parse_route(self, raw: str | None) -> Route | None:
        """把 ``provider:model`` 解析成 Route。

        未知提供方、缺少冒号或模型 ID 为空都返回 None，让调用方按“未配置”处理，
        而不是抛异常打断整个页面。
        """
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
        """按“当前目录 → 代码目录”的顺序向上查找 ``model.properties``。

        先看 ``start``（默认 ``Path.cwd()``）及其所有父目录，再看本文件所在目录及其父目录，
        命中即返回；全部未命中时返回预期路径（此时并不存在），由 ``load`` 标记为缺失。
        """
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
        """读取指定文件（缺省用 ``locate()`` 的结果）并解析成配置对象。"""
        file = Path(path).expanduser().resolve() if path else cls.locate()
        if not file.is_file():
            return cls(file, False, {}, {})
        raw = _read(file)
        return cls(file, True, *_parse(raw))


# Properties 视空格、制表符和换页符为键值分隔符与行首空白。
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
    """按逗号拆分选项列表，去空白、去重并保持出现顺序。"""
    names: list[str] = []
    for part in str(raw or "").split(","):
        name = _trim(part)
        if name and name not in names:
            names.append(name)
    return names


def _parse(values: dict[str, str]):
    """把扁平键值表拆成提供方表与路由表。

    ``service.<scope>`` 归入路由表；其余 ``<provider>.<field>`` 按键分组；缺少 ``base-url``
    的分组被丢弃，因为无法发起请求，列进选择器只会误导用户。

    Returns:
        ``(providers, routes)``：``{id: Provider}`` 与 ``{scope: "provider:model"}``。
    """
    providers: dict[str, Provider] = {}
    routes: dict[str, str] = {}
    groups: dict[str, dict[str, str]] = {}
    for name, value in values.items():
        key = _trim(name)
        if not key:
            continue
        if key.startswith("service."):
            # 值为空等同于未配置，避免 "service.python-a=" 被当成有效路由。
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
        # 去掉末尾斜杠，调用方直接拼 "/chat/completions" 不会出现双斜杠。
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
