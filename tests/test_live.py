from meeting_minutes.live import _segment_elapsed_seconds


def test_segment_elapsed_seconds_rounds_fractional_segment_end_to_nearest_second() -> None:
    assert _segment_elapsed_seconds(10, 0.4) == 10
    assert _segment_elapsed_seconds(10, 0.5) == 11
    assert _segment_elapsed_seconds(10, 0.9) == 11
