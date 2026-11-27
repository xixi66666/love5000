"""GitHub 仓库分类规则的离线用例。

`classify_repository` 是纯函数：先按 topics 精确匹配，再把名称与描述做驼峰拆分、
标点归一后按英文短语匹配，最后按 AGENT → SKILL → MCP → PLUGIN 的固定顺序去重输出，
`matched_rules` 记录命中来源（如 `topic:ai-agent`）以便解释分类结果。
这里覆盖 topic 与短语两条通路、大小写不敏感、多分类排序，以及只写 `skill`
（单词形式）不得被误判为 SKILL 的边界。无网络、无数据库。
"""

from app.collector.classifier import classify_repository


def test_classifies_agent_and_mcp_from_topics() -> None:
    result = classify_repository(
        name="agent-hub",
        description="Composable tools",
        topics=["ai-agent", "model-context-protocol"],
    )
    assert result.categories == ("AGENT", "MCP")
    assert "topic:ai-agent" in result.matched_rules


def test_matches_multi_word_phrase_in_name() -> None:
    result = classify_repository(
        name="awesome-agent-framework",
        description="A curated list",
        topics=["python"],
    )
    assert "AGENT" in result.categories
    assert "name:agent framework" in result.matched_rules


def test_matches_phrase_in_description() -> None:
    result = classify_repository(
        name="helper",
        description="Build mcp server in minutes",
        topics=[],
    )
    assert result.categories == ("MCP",)
    assert "description:mcp server" in result.matched_rules


def test_is_case_insensitive() -> None:
    result = classify_repository(
        name="MyAgentSkills",
        description="Collection of tools",
        topics=[],
    )
    assert "SKILL" in result.categories


def test_single_word_skill_is_not_misclassified() -> None:
    result = classify_repository(
        name="skill",
        description="Improve your skills in Python",
        topics=[],
    )
    assert result.categories == ()
    assert result.matched_rules == ()


def test_multiple_categories_sorted_and_deduplicated() -> None:
    """分类顺序按固定优先级而非命中顺序，同一仓库重复命中只保留一个标签。"""
    result = classify_repository(
        name="agent framework and agent skills hub",
        description="mcp server collection",
        topics=["mcp-server"],
    )
    assert result.categories == ("AGENT", "SKILL", "MCP")


def test_classifies_plugin_from_topic() -> None:
    result = classify_repository(
        name="toolbox",
        description="Extend your editor",
        topics=["claude-plugin"],
    )
    assert result.categories == ("PLUGIN",)
    assert "topic:claude-plugin" in result.matched_rules


def test_classifies_plugin_from_phrase() -> None:
    result = classify_repository(
        name="MyClaudePlugin",
        description="A plugin for Claude",
        topics=[],
    )
    assert "PLUGIN" in result.categories
    assert "name:claude plugin" in result.matched_rules


def test_all_categories_sorted_with_plugin_last() -> None:
    result = classify_repository(
        name="agent framework and agent skills hub",
        description="mcp server with claude plugin",
        topics=[],
    )
    assert result.categories == ("AGENT", "SKILL", "MCP", "PLUGIN")
