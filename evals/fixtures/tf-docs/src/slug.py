"""Kleine Textwerkzeuge."""
import re


def collapse_spaces(text):
    """Mehrere Leerzeichen werden zu einem."""
    return re.sub(r" +", " ", text).strip()
