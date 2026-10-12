from src.greet import greet


def test_greet():
    assert greet("Ada") == "Hallo, Ada!"
