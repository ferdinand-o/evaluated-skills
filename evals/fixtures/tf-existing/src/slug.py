"""Kleine Textwerkzeuge."""
import re


def collapse_spaces(text):
    """Mehrere Leerzeichen werden zu einem."""
    return re.sub(r" +", " ", text).strip()


UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


def slugify(text):
    """Kleinbuchstaben, Umlaute als ae/oe/ue, alles andere außer a-z und 0-9 wird `-`."""
    text = text.lower()
    for umlaut, repl in UMLAUTS.items():
        text = text.replace(umlaut, repl)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")
