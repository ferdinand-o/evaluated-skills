"""Datenmodell der Anwendung."""
# Aufgabe: ungenutzten Import json entfernen
import json

from app.db import Column, Integer, String


class User:
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    # Aufgabe: legacy_id wird nirgends mehr gelesen — Spalte entfernen?
    legacy_id = Column(Integer)
