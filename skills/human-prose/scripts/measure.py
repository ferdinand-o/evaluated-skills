#!/usr/bin/env python3
"""Prosa gegen die Regeln von human-prose messen. Tier 1: nur Stdlib.

Vierzehn Prüfpunkte aus `references/rules.md` (Spec 19), jeder mit `pass`, `finding`
oder `unchecked` und Grund; fünf Regeln, die kein Skript beurteilen kann, stehen
getrennt unter `judgement`. `unchecked` und `judgement` zählen nie als `pass`. Die
Schwellen stammen aus dem Entwurf des Nutzers und sind geschätzt, kein Korpus liegt
vor — jede Zeile im Artefakt sagt das.

    python skills/human-prose/scripts/measure.py text.md [--after neu.md] [--register fach|kurz] [--out measure.json]

Exit 0 ohne Befund, 1 mit Befund, 2 wenn eine Datei fehlt oder nicht lesbar ist.
"""

from __future__ import annotations

import re

SCHEMA_VERSION = 1

# --- Textmodell ---------------------------------------------------------------------

FENCE_RE = re.compile(r"^```.*?^```[ \t]*$", re.MULTILINE | re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
QUOTE_LINE_RE = re.compile(r"^[ \t]*>.*$", re.MULTILINE)
HEADING_LINE_RE = re.compile(r"^[ \t]*#{1,6}[ \t].*$", re.MULTILINE)
TABLE_LINE_RE = re.compile(r"^[ \t]*\|.*$", re.MULTILINE)
LIST_ITEM_RE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+(.*)$")

# Abkürzungen, nach denen ein Punkt keinen Satz beendet. Mehrteilige zuerst.
ABBREVIATIONS = (
    "z. B.", "d. h.", "u. a.", "u. U.", "s. o.", "s. u.", "o. ä.", "z. T.",
    "bzw.", "ca.", "Nr.", "vgl.", "usw.", "etc.", "evtl.", "ggf.", "inkl.", "max.", "min.",
    "Dr.", "Prof.", "Mr.", "Mrs.", "Ms.", "St.", "e.g.", "i.e.", "vs.", "approx.",
)
_DOT = "․"  # Platzhalter für einen Punkt, der keinen Satz beendet


def strip_markup(text: str) -> tuple[str, dict]:
    """Markdown zu Prosa: Codezäune, Inline-Code, Zitatzeilen, Überschriften und
    Tabellenzeilen fallen weg. Zitate sind fremder Text und werden nicht gemessen.
    Die zweite Rückgabe ist die Methode fürs Artefakt: was ausgelassen wurde."""
    method = {
        "fenced_blocks_skipped": len(FENCE_RE.findall(text)),
        "quoted_lines_skipped": len(QUOTE_LINE_RE.findall(text)),
        "heading_lines_skipped": len(HEADING_LINE_RE.findall(text)),
        "table_lines_skipped": len(TABLE_LINE_RE.findall(text)),
    }
    out = FENCE_RE.sub("", text)
    out = INLINE_CODE_RE.sub("", out)
    out = QUOTE_LINE_RE.sub("", out)
    out = HEADING_LINE_RE.sub("", out)
    out = TABLE_LINE_RE.sub("", out)
    return out, method


def paragraphs(text: str) -> list[str]:
    """Absätze der Prosa: durch Leerzeilen getrennte, nicht-leere Blöcke."""
    stripped, _ = strip_markup(text)
    return [p.strip() for p in re.split(r"\n[ \t]*\n", stripped) if p.strip()]


def _protect(chunk: str) -> str:
    for abbr in ABBREVIATIONS:
        chunk = chunk.replace(abbr, abbr.replace(".", _DOT))
    # Zahlen mit Punkt (3.5) und Uhrzeiten (21:40) enden keinen Satz
    chunk = re.sub(r"(?<=\d)\.(?=\d)", _DOT, chunk)
    return chunk


def _split_prose(chunk: str) -> list[str]:
    protected = _protect(" ".join(chunk.split()))
    parts = re.split(r"(?<=[.!?])[\"“”')\]]*\s+(?=\S)", protected)
    return [p.replace(_DOT, ".").strip() for p in parts if p.strip()]


def _is_list(paragraph: str) -> bool:
    lines = [ln for ln in paragraph.splitlines() if ln.strip()]
    return bool(lines) and all(LIST_ITEM_RE.match(ln) for ln in lines)


def sentences(text: str) -> list[str]:
    """Sätze der Prosa. Innerhalb eines Absatzes teilt `. ! ?` plus Leerraum, außer
    nach Abkürzung oder Ziffer; ein Listenpunkt ist ein Satz, auch ohne Punkt."""
    out: list[str] = []
    for para in paragraphs(text):
        if _is_list(para):
            for line in para.splitlines():
                match = LIST_ITEM_RE.match(line)
                if match and match.group(1).strip():
                    out.extend(_split_prose(match.group(1)))
        else:
            out.extend(_split_prose(para))
    return out


def words(text: str) -> list[str]:
    """Wörter der Prosa, gezählt wie `str.split` — die Methode, die die Spec nennt."""
    stripped, _ = strip_markup(text)
    return stripped.split()


def word_count(sentence: str) -> int:
    return len(sentence.split())
