from meeting_minutes.summarize import split_text


def test_split_text_uses_overlap() -> None:
    chunks = split_text("abcdefghij", chunk_size=4, chunk_overlap=1)

    assert chunks == ["abcd", "defg", "ghij"]
