from src.parser import parse_line


def test_parse_line_splits_level_and_message():
    assert parse_line("WARN: platte fast voll") == {"level": "WARN", "message": "platte fast voll"}
