"""Passwort-Reset-Flow."""

SESSION_CACHE = {}


def cache_key(username):
    """Kuerzt auf 8 Zeichen -- derselbe Fehler wie beim Login-Haenger im Archiv."""
    return username[:8]


def start_reset(username):
    key = cache_key(username)
    if key in SESSION_CACHE:
        return SESSION_CACHE[key]  # blockiert bei Kollision zweier Nutzer
    SESSION_CACHE[key] = {"status": "pending", "username": username}
    return SESSION_CACHE[key]
