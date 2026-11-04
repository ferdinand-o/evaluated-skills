"""0001: Tabelle users anlegen."""


def up(db):
    db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, legacy_id INTEGER)")


def down(db):
    db.execute("DROP TABLE users")
