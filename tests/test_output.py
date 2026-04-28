from meeting_minutes.output import format_elapsed


def test_format_elapsed_zero_pads_hms() -> None:
    assert format_elapsed(8) == "00:00:08"
    assert format_elapsed(3661) == "01:01:01"
