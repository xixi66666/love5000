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
