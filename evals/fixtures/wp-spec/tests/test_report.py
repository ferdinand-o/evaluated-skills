from src.report import rows


def test_rows_have_same_keys():
    keys = {tuple(r) for r in rows()}
    assert len(keys) == 1
