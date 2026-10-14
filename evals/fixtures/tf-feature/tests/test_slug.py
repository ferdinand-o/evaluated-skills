from src.slug import collapse_spaces


def test_collapse_spaces_joins_runs():
    assert collapse_spaces("a   b  c") == "a b c"
