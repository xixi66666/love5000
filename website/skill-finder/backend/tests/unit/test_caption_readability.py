"""字幕可读性与时间戳真实性的校验。

`align_script` 把口播稿和 ASR 实测词时间戳对齐成字幕条。这里锁死三条底线：
1. 长句只在真实词边界处拆分，拼回去仍是完整原文，且相邻字幕首尾不重叠；
2. 每条字幕的起止时间必须取自实测时间戳，不能为了让长度好看而均分时间；
3. 英文名 `React`、版本号 `v2.5` 这类被 ASR 当成单个 token 的片段不能被再次切开。

零时长的 ASR token 和 NaN/inf/负数/倒序等坏边界必须在进入渲染器前就抛错——
渲染器拿到坏时间轴只会产出一帧都放不出来的成片。
"""

from itertools import pairwise

import pytest

from app.daily.speech import align_script


def test_long_caption_splits_at_actual_word_boundaries_and_keeps_original_text():
    text = "输入这段文字就能生成清楚的演示视频并且保留每个实际操作步骤。"
    words = [{"text": char, "start": index * 0.2, "end": (index + 1) * 0.2}
             for index, char in enumerate(text[:-1])]
    cues = align_script(text, words)
    assert "".join(cue["text"] for cue in cues) == text
    assert len(cues) > 1
    assert all(len(cue["text"]) <= 18 for cue in cues)
    for previous, following in pairwise(cues):
        assert previous["end"] <= following["start"]
    measured = {word["start"] for word in words} | {word["end"] for word in words}
    assert all(cue["start"] in measured and cue["end"] in measured for cue in cues)


def test_english_name_and_decimal_version_are_not_split_into_artificial_words():
    text = "使用 React 和 v2.5 制作一个可以完整播放的演示视频。"
    tokens = ["使用", "React", "和", "v2.5", "制作", "一个", "可以", "完整", "播放", "的", "演示", "视频"]
    words = [{"text": token, "start": index * 0.5, "end": (index + 1) * 0.5}
             for index, token in enumerate(tokens)]
    cues = align_script(text, words)
    assert "".join(cue["text"] for cue in cues).replace(" ", "") == text.replace(" ", "")
    assert any("React" in cue["text"] for cue in cues)
    assert any("v2.5" in cue["text"] for cue in cues)


def test_single_measured_long_word_is_kept_without_fake_internal_timestamps():
    text = "这是一个没有词内测量边界的完整语音意群不能强行均分时间。"
    cues = align_script(text, [{"text": text, "start": 0.2, "end": 6.8}])
    assert cues == [{"text": text, "start": 0.2, "end": 6.8}]


def test_zero_duration_asr_tokens_are_not_used_as_timing_anchors():
    cues = align_script("先看这个工具。", [
        {"text": "先看", "start": 0.1, "end": 0.8},
        {"text": "这个", "start": 0.8, "end": 0.8},
        {"text": "工具", "start": 0.8, "end": 1.8},
        {"text": "。", "start": 1.8, "end": 1.8},
    ])
    assert cues == [{"text": "先看这个工具。", "start": 0.1, "end": 1.8}]


# 四类坏边界：NaN 起点、inf 终点、负起点、终点早于起点，都来自异常的 ASR 结果；
# 它们必须在字幕对齐阶段就抛出带 "timestamp" 的运行时错误，不能透传进渲染器。
@pytest.mark.parametrize("start,end", [(float("nan"), 2), (0, float("inf")), (-1, 2), (2, 1)])
def test_bad_measured_boundaries_fail_before_they_can_reach_renderer(start, end):
    with pytest.raises(RuntimeError, match="timestamp"):
        align_script("演示视频。", [{"text": "演示视频", "start": start, "end": end}])
