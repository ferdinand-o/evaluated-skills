"""Lädt Datensätze aus JSON-Dateien im Ordner data/."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def _load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def load_users():
    return _load("users")


def load_orders():
    return _load("orders")
