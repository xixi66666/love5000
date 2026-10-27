"""验证口播清理、完整事实留存和长度预算，不调用模型或数据库。"""
import json

from app.daily.pipeline import (
    NARRATION_LIMIT,
    SOURCE_NOTICE,
    compose,
    project_narration,
    spoken_text,
    summarize,
)


def project(summary, *, name="org/Agent-3.5", rank=1, stars=1234):
    return {"full_name": name, "summary": summary, "rank": rank, "daily_stars": stars}


def test_display_markup_and_urls_are_not_read_but_labels_and_facts_remain():
    raw = (
        "# 工具说明\n"
        "使用 **Agent-3.5** 和 `Qwen3.5-122B-A10B`；支持 1.25 GB 文件。\n"
        "查看[使用指南](https://example.com/guide_(v2))。\n"
        "- 注意：仅供测试，不能用于生产。https://example.com/details"
    )
    result = spoken_text(raw)

    assert "Agent-3.5" in result
    assert "Qwen3.5-122B-A10B" in result
    assert "1.25 GB" in result
    assert "使用指南" in result
    assert "注意：仅供测试，不能用于生产。" in result
    assert "https://" not in result
    assert not any(marker in result for marker in ("#", "**", "`", "](http"))


def test_markdown_cleaning_does_not_change_identifier_underscores_or_versions():
    assert spoken_text("支持 model_name_v2，版本 v1.2.3，最低 24.5 GB。") == (
        "支持 model_name_v2，版本 v1.2.3，最低 24.5 GB。"
    )


def test_reference_links_and_html_keep_readable_labels():
    result = spoken_text(
        '[文档][docs]，<strong>需要 Python 3.11+</strong>。\n'
        '[docs]: https://example.com/docs\n'
        '<https://example.com/extra>'
    )
    assert result == "文档，需要 Python 3.11+。"


def test_comparison_conditions_and_parameter_placeholders_are_preserved():
    raw = "需要 RAM < 16 GB，且 GPU > 8 GB；使用 <max_tokens> 参数，分数 <= 0.5。"

    assert spoken_text(raw) == (
        "需要 RAM < 16 GB，且 GPU > 8 GB。使用 <max_tokens> 参数，分数 <= 0.5。"
    )


def test_withdrawn_text_is_not_turned_back_into_a_spoken_claim():
    raw = "~~免费且无需授权~~，目前需要商用授权。<del>支持离线。</del>不支持离线。"
    result = spoken_text(raw)

    assert result == "目前需要商用授权。不支持离线。"
    assert "免费" not in result
    assert "无需授权" not in result


def test_report_summary_retains_original_names_numbers_and_tail_cautions():
    raw = "项目介绍。" * 35 + "支持 VeryLongModel-v1.2.3，需 24.5 GB 显存。注意：不能商用。"
    encoded = json.dumps({"introduction": raw}, ensure_ascii=False)

    assert summarize(encoded, "English description") == raw
    assert summarize(None, raw) == raw


def test_project_narration_keeps_countdown_and_leaves_star_fact_in_scene():
    item = project("用于整理开发文档。注意：不支持离线运行。", rank=2)
    original = item.copy()
    _, scenes = compose([item], "2026-10-23")
    scene = scenes[1]

    assert scene["narration"].startswith("第 2 名，Agent-3.5。")
    assert "用于整理开发文档。注意：不支持离线运行。" in scene["narration"]
    assert "1234" not in scene["narration"]
    assert "org/" not in scene["narration"]
    assert scene["growth"] == 1234
    assert scene["heading"] == "org/Agent-3.5"
    assert scene["summary"] == original["summary"]
    assert item == original


def test_name_already_opening_the_summary_is_not_repeated():
    narration = project_narration(project("Agent-3.5 用于整理开发文档。"))
    assert narration == "第 1 名。Agent-3.5 用于整理开发文档。"


def test_partial_name_prefix_does_not_hide_the_actual_repository_name():
    narration = project_narration(project("Agent-3.5-pro 是相关模型名称。"))
    assert narration.startswith("第 1 名，Agent-3.5。Agent-3.5-pro")


def test_long_narration_selects_complete_sentences_and_keeps_tail_conditions():
    facts = [f"第{i}项功能用于整理项目中的开发记录。" for i in range(30)]
    caution = "注意：需要 24.5 GB 显存，不能用于商用。"
    item = project("".join(facts) + caution)
    narration = project_narration(item)

    assert len(narration) <= NARRATION_LIMIT
    assert caution in narration
    assert narration.endswith(SOURCE_NOTICE)
    body = narration.removeprefix("第 1 名，Agent-3.5。").removesuffix(SOURCE_NOTICE)
    for sentence in body.split("。"):
        if sentence:
            assert sentence + "。" in facts or sentence + "。" == caution


def test_oversized_condition_is_not_partially_read_or_silently_dropped():
    raw = "用于文档整理。注意：" + "限制条件必须按项目说明核对，" * 45 + "不能商用。"
    narration = project_narration(project(raw))

    assert narration == "第 1 名，Agent-3.5。" + SOURCE_NOTICE
    assert len(narration) <= NARRATION_LIMIT


def test_unbroken_long_english_text_is_not_cut_mid_name_or_number():
    raw = "VeryLongModel-v1.2.3 requires 24.5 GB and " * 30
    narration = project_narration(project(raw))

    assert narration == "第 1 名，Agent-3.5。" + SOURCE_NOTICE
    assert len(narration) <= NARRATION_LIMIT
