"""Spaltenbeschreibung ohne Datenbanktreiber."""


class Integer:
    pass


class String:
    pass


class Column:
    def __init__(self, kind, primary_key=False):
        self.kind = kind
        self.primary_key = primary_key
