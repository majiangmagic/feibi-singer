import pytest

from feibi_singer.timeline_pipeline import (
    ACE_CAPTION,
    RVC_F0_CHANGE,
    assign_segment_lyrics,
    build_segment_plan,
    calculate_vocal_gain_db,
    has_preferred_vocal_coverage,
    parse_mean_volume_db,
    select_dynamic_split_points,
    select_vocal_window,
)


def test_dynamic_segments_use_locally_approved_rvc_pitch_shift():
    assert RVC_F0_CHANGE == 2


def test_ace_prioritizes_clear_studio_diction_over_live_delivery():
    assert "diction and lyric intelligibility are the highest priority" in ACE_CAPTION
    assert "No live-concert delivery" in ACE_CAPTION


def test_vocal_gain_matches_original_loudness():
    assert calculate_vocal_gain_db(-12.5, -20.7) == 8.2


def test_parse_mean_volume_db():
    assert parse_mean_volume_db("[Parsed_volumedetect] mean_volume: -25.3 dB") == -25.3
    assert parse_mean_volume_db("mean_volume: -inf dB") == float("-inf")


def test_candidate_search_continues_until_full_vocal_coverage():
    assert not has_preferred_vocal_coverage(0.85)
    assert not has_preferred_vocal_coverage(0.999)
    assert has_preferred_vocal_coverage(1.0)


def test_select_vocal_window_uses_long_intro_and_outro_silence():
    output = """
silence_start: 4.05
silence_end: 4.73 | silence_duration: 0.68
silence_start: 5.75
silence_end: 16.56 | silence_duration: 10.81
silence_start: 82.12
silence_end: 98.20 | silence_duration: 16.08
"""

    assert select_vocal_window(output, 98.20) == (16.56, 82.12)


def test_select_vocal_window_defaults_to_full_duration_without_long_silence():
    output = """
silence_start: 10.0
silence_end: 10.4 | silence_duration: 0.4
"""

    assert select_vocal_window(output, 30.0) == (0.0, 30.0)


def test_select_vocal_window_rejects_inverted_window():
    output = """
silence_start: 0.0
silence_end: 10.0 | silence_duration: 10.0
silence_start: 5.0
silence_end: 30.0 | silence_duration: 20.0
"""

    with pytest.raises(RuntimeError, match="invalid detected vocal window"):
        select_vocal_window(output, 30.0)


def test_dynamic_split_points_choose_low_energy_near_each_target():
    rms = [0.5] * 700
    rms[120] = 0.01
    rms[270] = 0.02
    rms[380] = 0.01
    rms[530] = 0.02

    assert select_dynamic_split_points(rms, 10, 65.0) == [12.0, 27.0, 38.0, 53.0]


def test_segment_lyrics_are_contiguous_and_complete():
    lines = ["one two", "three", "four five six", "seven", "eight nine"]

    assigned = assign_segment_lyrics(lines, [4.0, 8.0], 12.0)

    assert [line for segment in assigned for line in segment] == lines
    assert all(segment for segment in assigned)


def test_segment_plan_adds_context_without_exceeding_window():
    plan = build_segment_plan(["cat", "dog", "pig"], [10.0, 20.0], 30.0)

    assert [(item.input_start, item.input_end) for item in plan] == [
        (0.0, 17.5),
        (2.5, 27.5),
        (12.5, 30.0),
    ]
    assert plan[0].lyrics == ("cat", "dog")
    assert plan[1].lyrics == ("cat", "dog", "pig")
    assert plan[2].lyrics == ("dog", "pig")


def test_segment_plan_can_include_intro_and_outro_context():
    plan = build_segment_plan(
        ["cat", "dog"],
        [10.0],
        20.0,
        leading_context=5.0,
        trailing_context=6.0,
    )

    assert plan[0].input_start == -5.0
    assert plan[-1].input_end == 26.0
