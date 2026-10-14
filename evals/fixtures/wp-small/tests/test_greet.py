from src.greet import greet


def test_greet_names_the_person():
    assert "Ada" in greet("Ada")
