from src.auth import SESSION_CACHE, start_reset


def test_two_users_with_same_prefix_collide():
    SESSION_CACHE.clear()
    a = start_reset("alexander.mueller")
    b = start_reset("alexander.schmidt")  # gleiches 8-Zeichen-Praefix
    assert a is b  # sollte fuer verschiedene Nutzer False sein
