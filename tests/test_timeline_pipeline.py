import pytest

from feibi_singer.timeline_pipeline import calculate_vocal_gain_db, select_vocal_window


def test_vocal_gain_matches_original_loudness():
    assert calculate_vocal_gain_db(-12.5, -20.7) == 8.2


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
