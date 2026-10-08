from infrastructure.db import Database


class Broken:
    """Bewusste Schichtverletzung fuer den Eval: domain importiert infrastructure."""

    def __init__(self):
        self.db = Database()
