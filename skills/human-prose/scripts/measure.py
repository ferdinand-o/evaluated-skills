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


# --- Regeln und Schwellen -------------------------------------------------------------

# Schwellen aus dem Entwurf (Abschnitt 1, 2, 4, 6). Geschätzt, kein Korpus — jede
# Zeile im Artefakt trägt den Vermerk. Raten gelten je Wortzahl; unter der Bezugsgröße
# ist ein einzelner Treffer erlaubt (`max(1, …)`), sonst wäre jede Mail mit einem
# Doppelpunkt rot.
LIMITS = {
    "fach": {"passive_share": 0.20, "exclamations": 0, "fragments_per": 200, "mean_range": (13, 18)},
    "kurz": {"passive_share": 0.10, "exclamations": 1, "fragments_per": None, "mean_range": (9, 14)},
}
PARTICIPLE_PER = 300      # R4.3: höchstens eines je 300 Wörter
UNG_PER_1000 = 15         # R4.4
PAREN_PER = 200           # R1.4
COLON_PER = 150           # R1.4
HEDGES_PER_300 = 3        # R4.6
SPREAD_SHORT_MAX = 6      # R2.1: ein Satz mit höchstens sechs Wörtern
SPREAD_LONG_MIN = 20      # R2.1: ein Satz mit mindestens zwanzig Wörtern
SPREAD_STDDEV_RATIO = 0.4 # R2.1: Standardabweichung mindestens 40 Prozent des Mittels
SPREAD_WINDOW = 10        # R2.1: je zehn aufeinanderfolgende Sätze
SPREAD_MIN_SENTENCES = 4  # unter vier Sätzen ungeprüft (Spec 19, Constraints)
TRIAD_SHARE = 0.5         # R3.3
CLAIM_PARAGRAPH_MIN = 3   # R5.1: ein Absatz ab drei Sätzen ist eine Behauptung, kürzere sind Zäsur

# R4.1 — tote Phrasen Deutsch, als Muster: Groß-/Kleinschreibung egal, Lücken dort,
# wo ein Subjekt oder ein Objekt dazwischen stehen kann. Wortlaut identisch mit
# references/rules.md („als Muster").
PHRASES_DE = [
    r"in der heutigen welt", r"im digitalen zeitalter", r"in der heutigen schnelllebigen zeit",
    r"spielt (\w+ ){0,2}eine entscheidende rolle", r"ist von entscheidender bedeutung",
    r"es ist wichtig zu beachten", r"es sei darauf hingewiesen", r"nicht nur .{1,80}, sondern auch",
    r"ein echter gamechanger", r"auf das nächste level", r"umfassender leitfaden",
    r"maßgeschneiderte lösung", r"nahtlos\w*", r"ganzheitlich\w*", r"revolutionier\w*",
    r"vielfältig\w*", r"sorgfältig ausgewählt", r"tauchen wir ein",
    r"hängt von ihren individuellen anforderungen ab", r"es gibt keine einheitslösung",
]
# R4.2 — tote Phrasen Englisch. `robust` und `leverage` zählen immer; der Fachkontext,
# den der Entwurf ausnimmt, ist ein Urteil und steht im Grund.
PHRASES_EN = [
    r"delve\w*", r"tapestry", r"meticulous\w*", r"pivotal", r"testament to", r"a plethora of",
    r"a multitude of", r"it is important to note", r"it'?s worth noting",
    r"in today'?s fast-paced world", r"navigate the (\w+ ){0,2}landscape", r"unlock the potential",
    r"seamless\w*", r"robust", r"leverag\w+", r"supercharge\w*", r"elevate\w*",
    r"game-?changer", r"at its core", r"when it comes to",
]
PARTICIPLE_RE = re.compile(r"[,—–]\s*(wodurch|was es|ensuring|allowing|making it|resulting in)\b", re.IGNORECASE)
CONNECTOR_RE = re.compile(r"^(darüber hinaus|zudem|außerdem|furthermore|moreover|additionally)\b", re.IGNORECASE)
OPENERS = [r"in diesem artikel", r"im folgenden", r"lass uns", r"let'?s dive in", r"in this guide"]
CLOSERS = [r"zusammenfassend lässt sich sagen", r"fazit:", r"in conclusion", r"at the end of the day", r"\bultimately\b"]
HEDGES = [r"könnte\w*", r"möglicherweise", r"unter umständen", r"tendenziell", r"in der regel",
          r"eventuell", r"vielleicht", r"\bmight\b", r"\bperhaps\b", r"\bpossibly\b", r"tends? to"]
UNG_RE = re.compile(r"\b\w{2,}ung(?:en|s)?\b")
PASSIVE_DE_RE = re.compile(r"\b(wird|werden|wurde|wurden|worden)\b.*\b(ge\w+(t|en)|\w+iert)\b|\b(ge\w+(t|en)|\w+iert)\b.*\b(wird|werden|wurde|wurden|worden)\b", re.IGNORECASE)
PASSIVE_EN_RE = re.compile(r"\b(is|are|was|were|been|being|be)\b\s+(\w+ly\s+)?\w+(ed|en)\b", re.IGNORECASE)
FINITE_VERBS = {
    "ist", "sind", "war", "waren", "hat", "haben", "hatte", "wird", "werden", "wurde", "kann",
    "muss", "soll", "darf", "gibt", "geht", "kommt", "bleibt", "steht", "reicht", "läuft",
    "is", "are", "was", "were", "has", "have", "had", "do", "does", "did", "can", "will",
    "should", "must", "goes", "comes", "stays", "works", "runs",
}
FRAGMENT_MAX_WORDS = 5
CONCRETE_RE = re.compile(
    r"\d"                                   # Ziffer, Datum, Uhrzeit
    r"|`[^`]+`"                             # Backtick
    r"|(?<![\w/])/[\w.-]+(?:/[\w.-]+)+"     # Pfad
    r"|\b[A-ZÄÖÜ]{2,}\b"                    # Abkürzung in Großbuchstaben (TTL, SQL)
    r"|\b[a-z]+[A-Z]\w*\b|\b[A-Z][a-z]+[A-Z]\w*\b"  # gemischte Schreibung (PostgreSQL, iPhone)
)
CONJ_RE = re.compile(r"\b(und|oder|and|or)\b", re.IGNORECASE)

JUDGEMENT = [
    {"id": "R3.1", "question": "Ist jede Liste eine Liste, oder wären es zwei Sätze?"},
    {"id": "R5.3", "question": "Steht eine Empfehlung da, wo eine gefragt war?"},
    {"id": "R5.4", "question": "Beginnt jeder Satz mit Bekanntem und endet mit dem Neuen?"},
    {"id": "R2.3-2", "question": "Wiederholt ein Absatzende nur das Gesagte?"},
    {"id": "R5.2", "question": "Ist jede Zahl, jedes Zitat, jede Anekdote belegt (Original, Auftrag, Rückfrage)?"},
]


def judgement() -> list[dict]:
    """Die fünf Regeln, die kein Skript beurteilt — Urteil des Schreibenden, nie pass."""
    return [dict(j) for j in JUDGEMENT]


# --- Prüfpunkte -----------------------------------------------------------------------

class Check:
    """Ein Prüfpunkt: `status` ist pass, finding oder unchecked; `limit` die Schwelle,
    `estimated` sagt, dass sie aus dem Entwurf stammt und nicht gemessen ist."""

    def __init__(self, id: str, status: str, value, limit, reason: str, estimated: bool = True):
        self.id, self.status, self.value, self.limit, self.reason, self.estimated = id, status, value, limit, reason, estimated

    def as_dict(self) -> dict:
        return {"id": self.id, "status": self.status, "value": self.value, "limit": self.limit,
                "reason": self.reason, "estimated": self.estimated}


def _allowed(words_total: int, per: int, base: int = 1) -> int:
    return max(base, int(words_total * base / per))


def _raw_paragraphs(text: str) -> list[str]:
    """Absätze mit Inline-Code — für R5.1, das Backticks als konkret zählt."""
    out = FENCE_RE.sub("", text)
    out = QUOTE_LINE_RE.sub("", out)
    out = HEADING_LINE_RE.sub("", out)
    out = TABLE_LINE_RE.sub("", out)
    return [p.strip() for p in re.split(r"\n[ \t]*\n", out) if p.strip()]


def check_r11(text, sents, paras, n_words, register):
    prose, _ = strip_markup(text)
    em = prose.count("—")
    en = len(re.findall(r"\s–\s", prose))
    semi = prose.count(";")
    total = em + en + semi
    reason = f"Geviertstrich {em}, Gedankenstrich mit Leerzeichen {en}, Semikolon {semi} (außerhalb von Code und Zitaten)"
    return Check("R1.1", "finding" if total else "pass", total, 0, reason, estimated=False)


def check_phrases(text, sents, paras, n_words, register):
    prose, _ = strip_markup(text)
    hits = []
    for pat in PHRASES_DE + PHRASES_EN:
        for match in re.finditer(pat, prose, re.IGNORECASE):
            hits.append(match.group(0))
    reason = ("tote Phrasen (R4.1/R4.2, Muster mit Lücke): " + ", ".join(f"„{h}\"" for h in hits[:6])) if hits else "keine tote Phrase aus R4.1/R4.2"
    if any(h.lower().startswith(("robust", "leverag")) for h in hits):
        reason += '; „robust"/„leverage" sind im Fachkontext erlaubt, das ist ein Urteil'
    return Check("R4.1/R4.2", "finding" if hits else "pass", len(hits), 0, reason, estimated=False)


def check_r43(text, sents, paras, n_words, register):
    prose, _ = strip_markup(text)
    count = len(PARTICIPLE_RE.findall(prose))
    allowed = _allowed(n_words, PARTICIPLE_PER)
    reason = f"{count} Partizip-Anhängsel auf {n_words} Wörter, erlaubt {allowed} (eines je {PARTICIPLE_PER} Wörter, geschätzt)"
    return Check("R4.3", "finding" if count > allowed else "pass", count, allowed, reason)


def check_r21(text, sents, paras, n_words, register):
    import statistics
    lengths = [word_count(s) for s in sents]
    n = len(lengths)
    mean = round(statistics.mean(lengths), 1) if lengths else 0
    if n < SPREAD_MIN_SENTENCES:
        return Check("R2.1", "unchecked", {"sentences": n, "mean": mean}, None,
                     f"nur {n} Sätze — Streuung ist unter {SPREAD_MIN_SENTENCES} Sätzen nicht prüfbar")
    windows = [lengths] if n < SPREAD_WINDOW else [lengths[i:i + SPREAD_WINDOW] for i in range(n - SPREAD_WINDOW + 1)]
    problems = []
    for i, win in enumerate(windows):
        m_ = statistics.mean(win)
        sd = statistics.pstdev(win)
        if min(win) > SPREAD_SHORT_MAX:
            problems.append(f"Fenster {i + 1}: kein Satz mit höchstens sechs Wörtern (kürzester {min(win)})")
        if max(win) < SPREAD_LONG_MIN:
            problems.append(f"Fenster {i + 1}: kein Satz mit mindestens zwanzig Wörtern (längster {max(win)})")
        if m_ and sd / m_ < SPREAD_STDDEV_RATIO:
            problems.append(f"Fenster {i + 1}: Streuung {sd / m_:.0%} unter 40 Prozent")
    lo, hi = LIMITS[register]["mean_range"]
    corridor = f"Mittel {mean} Wörter, Zielkorridor {lo} bis {hi} ({register}, geschätzt)"
    value = {"sentences": n, "mean": mean, "lengths": lengths if n <= 30 else lengths[:30]}
    if problems:
        return Check("R2.1", "finding", value, {"short": SPREAD_SHORT_MAX, "long": SPREAD_LONG_MIN, "stddev_ratio": SPREAD_STDDEV_RATIO},
                     "; ".join(problems[:3]) + f"; {corridor}")
    return Check("R2.1", "pass", value, {"short": SPREAD_SHORT_MAX, "long": SPREAD_LONG_MIN, "stddev_ratio": SPREAD_STDDEV_RATIO},
                 f"je Fenster ein kurzer, ein langer Satz, Streuung über 40 Prozent; {corridor}")


def check_r22(text, sents, paras, n_words, register):
    hits = [p.split("\n")[0][:40] for p in paras if CONNECTOR_RE.match(p.strip())]
    reason = ("Absatz beginnt mit Konnektor: " + "; ".join(f"„{h}\"" for h in hits)) if hits else "kein Absatzanfang mit Konnektor (R2.2)"
    return Check("R2.2", "finding" if hits else "pass", len(hits), 0, reason, estimated=False)


def check_r35(text, sents, paras, n_words, register):
    if not paras:
        return Check("R3.5", "unchecked", 0, 0, "kein Absatz", estimated=False)
    hits = []
    first, last = paras[0].lower(), paras[-1].lower()
    for pat in OPENERS:
        if re.match(r"\s*" + pat, first):
            hits.append(f"Eröffnung „{pat}\"")
    for pat in CLOSERS:
        if re.search(pat, last):
            hits.append(f"Abschluss „{pat}\"")
    reason = "; ".join(hits) if hits else "kein Rahmen aus Ankündigung und Zusammenfassung (R3.5)"
    return Check("R3.5", "finding" if hits else "pass", len(hits), 0, reason, estimated=False)


def check_r51(text, sents, paras, n_words, register):
    raw = _raw_paragraphs(text)
    vague = []
    checked = 0
    for para in raw:
        if _is_list(para) or len(_split_prose(para)) < CLAIM_PARAGRAPH_MIN:
            continue
        checked += 1
        if not CONCRETE_RE.search(para):
            vague.append(para[:50])
    if not checked:
        return Check("R5.1", "unchecked", 0, None, f"kein Absatz mit mindestens {CLAIM_PARAGRAPH_MIN} Sätzen — nichts zu prüfen")
    reason = (f"{len(vague)} von {checked} Behauptungsabsätzen ohne Ziffer, Pfad, Backtick oder Großwort — Heuristik: " + "; ".join(f"„{v}…\"" for v in vague)) if vague else f"jeder der {checked} Behauptungsabsätze trägt ein konkretes Element (Heuristik: Ziffer, Pfad, Backtick, Großwort; deutsche Substantive zählen nicht)"
    return Check("R5.1", "finding" if vague else "pass", len(vague), 0, reason + f"; Behauptungsabsatz ab {CLAIM_PARAGRAPH_MIN} Sätzen, geschätzt")


def check_r52(text, sents, paras, n_words, register):
    return Check("R5.2", "unchecked", None, None, "ob eine Zahl, ein Zitat oder eine Anekdote erfunden ist, misst kein Skript — Urteil des Schreibenden", estimated=False)


def _enumerations(text, sents, paras) -> list[int]:
    sizes = []
    for para in paras:
        if _is_list(para):
            sizes.append(len([ln for ln in para.splitlines() if LIST_ITEM_RE.match(ln)]))
    for s in sents:
        for match in re.finditer(r"((?:[^,.;:]+,\s+){1,6}[^,.;:]+?)\s+(?:und|oder|and|or)\s+[^,.;:]+", s):
            items = [x for x in match.group(1).split(",") if x.strip()]
            sizes.append(len(items) + 1)
    return sizes


def check_r33(text, sents, paras, n_words, register):
    sizes = _enumerations(text, sents, paras)
    triads = sum(1 for n in sizes if n == 3)
    if len(sizes) < 2:
        return Check("R3.3", "pass", triads, TRIAD_SHARE, f"{len(sizes)} Aufzählung(en), unter zwei ist es kein Muster (Grenze 50 Prozent, geschätzt)")
    share = triads / len(sizes)
    reason = f"{triads} von {len(sizes)} Aufzählungen haben genau drei Elemente ({share:.0%}), Grenze 50 Prozent (geschätzt)"
    return Check("R3.3", "finding" if share > TRIAD_SHARE else "pass", triads, TRIAD_SHARE, reason)


def check_r44(text, sents, paras, n_words, register):
    prose, _ = strip_markup(text)
    count = len(UNG_RE.findall(prose))
    allowed = max(1, int(n_words * UNG_PER_1000 / 1000))
    rate = round(count * 1000 / n_words, 1) if n_words else 0
    reason = f"{count} Wörter auf -ung auf {n_words} Wörter ({rate} je 1000), erlaubt {allowed} ({UNG_PER_1000} je 1000, geschätzt)"
    return Check("R4.4", "finding" if count > allowed else "pass", count, allowed, reason)


def check_r14(text, sents, paras, n_words, register):
    prose, _ = strip_markup(text)
    parens = prose.count("(")
    # Doppelpunkt am Zeilenende (vor einer Liste) zählt nicht
    colons = len(re.findall(r":(?!\s*$)", prose, re.MULTILINE))
    bangs = prose.count("!")
    lim = {"parens": _allowed(n_words, PAREN_PER), "colons": _allowed(n_words, COLON_PER), "exclamations": LIMITS[register]["exclamations"]}
    problems = []
    if parens > lim["parens"]:
        problems.append(f"Klammern {parens} > {lim['parens']}")
    if colons > lim["colons"]:
        problems.append(f"Doppelpunkte {colons} > {lim['colons']}")
    if bangs > lim["exclamations"]:
        problems.append(f"Ausrufezeichen {bangs} > {lim['exclamations']}")
    value = {"parens": parens, "colons": colons, "exclamations": bangs}
    reason = ("; ".join(problems) if problems else f"Klammern {parens}, Doppelpunkte {colons}, Ausrufezeichen {bangs} im Rahmen") + f" (je {PAREN_PER}/{COLON_PER} Wörter, {register}, geschätzt)"
    return Check("R1.4", "finding" if problems else "pass", value, lim, reason)


def check_r45(text, sents, paras, n_words, register):
    if not sents:
        return Check("R4.5", "unchecked", 0, None, "keine Sätze")
    passive = [s for s in sents if PASSIVE_DE_RE.search(s) or PASSIVE_EN_RE.search(s)]
    share = len(passive) / len(sents)
    limit = LIMITS[register]["passive_share"]
    reason = f"{len(passive)} von {len(sents)} Sätzen im Passiv ({share:.0%}), Grenze {limit:.0%} ({register}, geschätzt; Heuristik: werden-Form plus Partizip)"
    return Check("R4.5", "finding" if share > limit else "pass", round(share, 2), limit, reason)


def check_r46(text, sents, paras, n_words, register):
    prose, _ = strip_markup(text)
    count = sum(len(re.findall(pat, prose, re.IGNORECASE)) for pat in HEDGES)
    allowed = _allowed(n_words, 300, HEDGES_PER_300)
    reason = f"{count} Hedges auf {n_words} Wörter, erlaubt {allowed} (drei je 300 Wörter, geschätzt)"
    return Check("R4.6", "finding" if count > allowed else "pass", count, allowed, reason)


def _is_fragment(sentence: str) -> bool:
    toks = [t.strip(".,!?:;\"“”'()").lower() for t in sentence.split()]
    if len(toks) <= 3:
        return True
    return len(toks) <= FRAGMENT_MAX_WORDS and not any(t in FINITE_VERBS for t in toks)


def check_r24(text, sents, paras, n_words, register):
    frags = [s for s in sents if _is_fragment(s)]
    per = LIMITS[register]["fragments_per"]
    if per is None:
        return Check("R2.4", "pass", len(frags), None, f"{len(frags)} Fragment(e) — in der Kurzform frei (Heuristik: bis fünf Wörter ohne finites Verb)")
    allowed = _allowed(n_words, per)
    reason = f"{len(frags)} Fragment(e) auf {n_words} Wörter, erlaubt {allowed} (eines je {per} Wörter, geschätzt; Heuristik: bis fünf Wörter ohne finites Verb)"
    return Check("R2.4", "finding" if len(frags) > allowed else "pass", len(frags), allowed, reason)


CHECKS = [
    check_r11, check_phrases, check_r43, check_r21, check_r22, check_r35, check_r51,
    check_r52, check_r33, check_r44, check_r14, check_r45, check_r46, check_r24,
]


def check_all(text: str, register: str = "fach") -> list[Check]:
    """Alle vierzehn Prüfpunkte in der Reihenfolge der Spec-Tabelle."""
    if register not in LIMITS:
        raise ValueError(f"unbekanntes Register {register!r}, erlaubt: {', '.join(LIMITS)}")
    sents = sentences(text)
    paras = paragraphs(text)
    n_words = len(words(text))
    return [fn(text, sents, paras, n_words, register) for fn in CHECKS]


# --- Artefakt und CLI -----------------------------------------------------------------

import argparse
import json
import shlex
import sys
from pathlib import Path

DEFAULT_OUT = Path(".skills") / "cache" / "human-prose" / "measure.json"


def measure_meta(argv: list[str]) -> dict:
    cmd = "python skills/human-prose/scripts/measure.py " + " ".join(shlex.quote(a) for a in argv)
    return {"skill": "human-prose", "schema": SCHEMA_VERSION, "generated": cmd}


def measure_text(text: str, register: str) -> dict:
    """Ein Textblock des Artefakts: die vierzehn Zeilen, die fünf Urteile, die Summe."""
    checks = check_all(text, register)
    rows = [c.as_dict() for c in checks]
    summary = {status: sum(1 for c in checks if c.status == status) for status in ("pass", "finding", "unchecked")}
    _, method = strip_markup(text)
    return {
        "words": len(words(text)),
        "sentences": len(sentences(text)),
        "paragraphs": len(paragraphs(text)),
        "skipped": method,
        "checks": rows,
        "judgement": judgement(),
        "summary": summary,
    }


def render_measure_json(results: dict, meta: dict, register: str) -> str:
    """`_meta` zuerst (docs/artifact-header.md, JSON-Konvention), dann Methode, Register,
    dann `text` oder `before`/`after`."""
    payload = {
        "_meta": meta,
        "method": {
            "words": "str.split",
            "sentence_splitter": "Punkt, Ausrufe- oder Fragezeichen plus Leerraum; Abkürzungen und Zahlen ausgenommen; Listenpunkt = Satz",
            "excluded": "Codezäune, Inline-Code, Zitatzeilen, Überschriften, Tabellenzeilen",
            "limits": "aus dem Entwurf v0.1, geschätzt, kein Korpus",
        },
        "register": register,
    }
    payload.update(results)
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Datei nicht gefunden: {path}", file=sys.stderr)
    except UnicodeDecodeError:
        print(f"Datei nicht als UTF-8 lesbar: {path}", file=sys.stderr)
    except OSError as exc:
        print(f"Datei nicht lesbar: {path}: {exc}", file=sys.stderr)
    return None


def _summary_line(label: str, block: dict) -> str:
    s = block["summary"]
    return f"{label}: {s['pass']} pass, {s['finding']} Befunde, {s['unchecked']} ungeprüft ({block['words']} Wörter, {block['sentences']} Sätze)"


def _print_table(results: dict) -> None:
    if "text" in results:
        for row in results["text"]["checks"]:
            print(f"  [{row['status']:9}] {row['id']:10} {row['reason']}")
        print(_summary_line("Nachgemessen", results["text"]))
        return
    before, after = results["before"], results["after"]
    print(f"  {'Regel':10} {'vorher':10} {'nachher':10}")
    for b, a in zip(before["checks"], after["checks"]):
        print(f"  {b['id']:10} {b['status']:10} {a['status']:10} {a['reason'][:70]}")
    print(_summary_line("Vorher", before))
    print(_summary_line("Nachher", after))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="human-prose: Prosa gegen die vierzehn Prüfpunkte messen (Tier 1)")
    parser.add_argument("text", help="Datei mit dem Text (Modus A: der Entwurf; Modus B: das Original)")
    parser.add_argument("--after", help="Modus B: die überarbeitete Fassung — Artefakt trägt before und after")
    parser.add_argument("--register", choices=sorted(LIMITS), default="fach", help="fach (Doku, Artikel) oder kurz (Mail, Chat); Default fach")
    parser.add_argument("--out", help=f"Artefakt-Pfad, Default {DEFAULT_OUT}")
    args = parser.parse_args(argv)

    text = _read(Path(args.text))
    if text is None:
        return 2
    results: dict
    if args.after:
        after = _read(Path(args.after))
        if after is None:
            return 2
        results = {"before": measure_text(text, args.register), "after": measure_text(after, args.register)}
        decisive = results["after"]
    else:
        results = {"text": measure_text(text, args.register)}
        decisive = results["text"]

    out = Path(args.out) if args.out else DEFAULT_OUT
    if not out.parent.exists():
        # Bootstrap-Regel (docs/artifact-header.md): die Anlage wird angekündigt.
        print(f"human-prose legt an: {out.parent}/ (Artefakt {out.name})")
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_measure_json(results, measure_meta(argv), args.register), encoding="utf-8")

    _print_table(results)
    print(f"Artefakt: {out}")
    return 1 if decisive["summary"]["finding"] else 0


if __name__ == "__main__":
    sys.exit(main())
