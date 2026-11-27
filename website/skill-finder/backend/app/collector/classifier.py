"""把仓库归类为 AGENT / SKILL / MCP / PLUGIN，并记录命中的规则。

两轮匹配：先看 GitHub topics（精确、可靠），再看名称与描述里的英文短语
（需要先做驼峰拆分与标点归一）。一个仓库可以同时命中多个分类，结果按固定顺序
（AGENT → SKILL → MCP → PLUGIN）排列，``matched_rules`` 保留命中的原始规则名，
便于排查“为什么这个仓库被归到这里”。

本模块是纯函数，无 I/O、无随机性，可在离线测试里直接断言。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 四个分类同时也是 API 的 category 参数取值与前端筛选标签，改名需同步前端与查询逻辑。
CATEGORY_AGENT = "AGENT"
CATEGORY_SKILL = "SKILL"
CATEGORY_MCP = "MCP"
CATEGORY_PLUGIN = "PLUGIN"

# GitHub topic 精确匹配规则：topic 通常由仓库维护者手工标注，命中即可直接定类。
TOPIC_RULES: tuple[tuple[str, str], ...] = (
    ("ai-agent", CATEGORY_AGENT),
    ("agent-framework", CATEGORY_AGENT),
    ("agentic-ai", CATEGORY_AGENT),
    ("autonomous-agent", CATEGORY_AGENT),
    ("agent-skills", CATEGORY_SKILL),
    ("ai-skills", CATEGORY_SKILL),
    ("claude-skills", CATEGORY_SKILL),
    ("codex-skills", CATEGORY_SKILL),
    ("mcp-server", CATEGORY_MCP),
    ("model-context-protocol", CATEGORY_MCP),
    ("claude-plugin", CATEGORY_PLUGIN),
    ("ai-plugin", CATEGORY_PLUGIN),
    ("opencode-plugin", CATEGORY_PLUGIN),
    ("copilot-extension", CATEGORY_PLUGIN),
)

# 名称/描述里的英文短语规则；用词边界匹配，避免 "ai" 命中 "said" 这类误判。
PHRASE_RULES: tuple[tuple[str, str], ...] = (
    ("agent framework", CATEGORY_AGENT),
    ("agent frameworks", CATEGORY_AGENT),
    ("agent skill", CATEGORY_SKILL),
    ("agent skills", CATEGORY_SKILL),
    ("ai skill", CATEGORY_SKILL),
    ("ai skills", CATEGORY_SKILL),
    ("claude skill", CATEGORY_SKILL),
    ("claude skills", CATEGORY_SKILL),
    ("codex skill", CATEGORY_SKILL),
    ("codex skills", CATEGORY_SKILL),
    ("mcp server", CATEGORY_MCP),
    ("mcp servers", CATEGORY_MCP),
    ("model context protocol", CATEGORY_MCP),
    ("claude plugin", CATEGORY_PLUGIN),
    ("claude plugins", CATEGORY_PLUGIN),
    ("codex plugin", CATEGORY_PLUGIN),
    ("codex plugins", CATEGORY_PLUGIN),
    ("opencode plugin", CATEGORY_PLUGIN),
    ("opencode plugins", CATEGORY_PLUGIN),
    ("ai plugin", CATEGORY_PLUGIN),
    ("ai plugins", CATEGORY_PLUGIN),
    ("copilot extension", CATEGORY_PLUGIN),
    ("copilot extensions", CATEGORY_PLUGIN),
    ("vscode extension for ai", CATEGORY_PLUGIN),
)

# 短语正则在导入期一次性编译，采集时每轮要匹配上千条文本，避免重复编译开销。
_PHRASE_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = tuple(
    (re.compile(rf"\b{re.escape(phrase)}\b"), phrase, category)
    for phrase, category in PHRASE_RULES
)

# 分类输出顺序：与前端榜单的标签顺序一致，保证同一仓库每次排列稳定。
_CATEGORY_ORDER: dict[str, int] = {
    CATEGORY_AGENT: 0,
    CATEGORY_SKILL: 1,
    CATEGORY_MCP: 2,
    CATEGORY_PLUGIN: 3,
}


@dataclass(frozen=True)
class Classification:
    """一次分类的结果。

    Attributes:
        categories: 命中的分类，按 ``_CATEGORY_ORDER`` 排序，可能为空元组。
        matched_rules: 形如 ``topic:ai-agent`` 或 ``description:agent skills`` 的命中记录，
            写入 ``repositories.matched_rules``，用于解释分类来源。
    """

    categories: tuple[str, ...]
    matched_rules: tuple[str, ...]


def normalize_text(text: str) -> str:
    """把仓库名称/描述归一成便于短语匹配的小写词序列。

    先在“小写字母或数字紧跟大写字母”处插入空格，从而把 ``OpenAIAgent`` 拆成
    ``Open AI Agent``；再把所有非字母数字字符折叠成单个空格并转小写。

    Args:
        text: 原始名称或描述。

    Returns:
        仅含小写字母、数字与单空格的字符串；空输入返回空串。
    """
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text.lower())


def classify_repository(name: str, description: str, topics: list[str]) -> Classification:
    """按 topic 与英文短语判定仓库分类。

    Args:
        name: 仓库名（不含 owner），参与短语匹配。
        description: 仓库描述，可为空串；同样参与短语匹配。
        topics: GitHub topics 列表，大小写不敏感。

    Returns:
        去重且按固定顺序排列的 :class:`Classification`；一个规则都没命中时
        ``categories`` 为空元组，调用方仍会照常落库。
    """
    matched_rules: list[str] = []
    categories: list[str] = []

    topic_set = {topic.lower() for topic in topics}
    for topic, category in TOPIC_RULES:
        if topic in topic_set:
            matched_rules.append(f"topic:{topic}")
            _add_category(categories, category)

    fields = (
        ("name", normalize_text(name)),
        ("description", normalize_text(description)),
    )
    for field, text in fields:
        for pattern, phrase, category in _PHRASE_PATTERNS:
            if pattern.search(text):
                matched_rules.append(f"{field}:{phrase}")
                _add_category(categories, category)

    categories.sort(key=_CATEGORY_ORDER.__getitem__)

    return Classification(categories=tuple(categories), matched_rules=tuple(matched_rules))


def _add_category(categories: list[str], category: str) -> None:
    """按首次出现顺序追加分类，重复命中不产生重复标签。

    Args:
        categories: 待写入的分类列表，原地修改。
        category: 要追加的分类名。
    """
    if category not in categories:
        categories.append(category)
