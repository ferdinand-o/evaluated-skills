from src.greet import greet


def test_greeting():
    assert greet("Welt") == "Hello, Welt!"
