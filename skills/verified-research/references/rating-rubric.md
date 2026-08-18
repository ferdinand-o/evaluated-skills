# Truth-Bewertung: Kriterien und Einstufungs-Leitfaden

Wird eine Quelle getroffen, die nicht im Register steht, entscheidet diese Rubrik über
ihr Tier — einmal, mit Begründung, dann via
`skills/verified-research/scripts/registry.py add` eingetragen. Die Begründung landet
in der `notiz`, nicht daneben: `add_entry()` verlangt, dass sie mindestens eines der
fünf Kriterien unten beim Namen nennt (siehe `RUBRIC_KEYWORDS` in `registry.py`).

## Die fünf Kriterien

1. **Primär-/Sekundärstatus.** Ist das der Ort, an dem der Fakt entsteht (Gesetzestext,
   Originaldaten, Original-Paper, offizielle Ankündigung), oder berichtet die Quelle nur
   darüber? Ein Aggregator, der eine Pressemitteilung umformuliert, bleibt Sekundärquelle,
   egal wie viele Leser er hat.
2. **Redaktionelle Standards.** Gibt es einen dokumentierten Review-/Faktencheck-Prozess,
   eine erkennbare Redaktion mit Namen, Korrekturen bei Fehlern? Offene
   Publishing-Plattformen ohne Vorab-Prüfung (Blogs, Contributor-Netzwerke,
   Foren-Antworten) erfüllen das nicht, unabhängig vom Ansehen der Plattform insgesamt.
3. **Anreizlage / Interessenkonflikte.** Verdient die Quelle am Ergebnis (Affiliate,
   Werbung, Investor Relations, Lobbyarbeit)? Das disqualifiziert eine Quelle nicht
   automatisch, senkt aber ihr Tier gegenüber einer neutralen Quelle mit denselben
   Fakten — und verlangt, die Darstellung kritischer zu lesen.
4. **Track Record.** Wie oft musste die Quelle in der Vergangenheit korrigieren? Eine
   neue, unbekannte Quelle bekommt nicht automatisch das Vertrauen einer etablierten.
   Ohne Anhaltspunkte: konservativ einstufen.
5. **Aktualität.** Ist erkennbar, wann der Inhalt zuletzt geprüft/aktualisiert wurde?
   Eine undatierte Quelle zu einem sich änderndem Sachverhalt (Rechtslage, Marktdaten,
   Software-Version) verdient Misstrauen, selbst wenn die anderen vier Kriterien passen.

## Einstufungs-Leitfaden

- **Tier 1 — Primärquelle.** Gesetzestext, Standard (RFC/W3C/…), Original-Paper,
  offizielle Dokumentation des Herstellers/Maintainers, Originaldaten (Amt, Börse,
  Zentralbank). Kriterium 1 ist immer erfüllt; 2–5 meist auch, aber nicht Bedingung —
  ein Preprint ohne Peer-Review bleibt Tier 1 für „das behaupten die Autoren", nicht
  für „das ist geprüft".
- **Tier 2 — etablierte Fachquelle.** Kein Primärort des Fakts, aber redaktioneller
  Standard, Track Record, meist klare Anreizlage (Verlag/Redaktion statt Einzelperson).
  Fachverlage, etablierte Nachrichtenagenturen, kuratierte Referenzwerke.
- **Tier 3 — alles Übrige aus freier Suche.** Blogs, Foren, offene Publishing-Plattformen,
  Vergleichsportale, Contributor-Netzwerke ohne redaktionelle Kernprüfung, unbekannte
  Quellen ohne Track Record. Der Standardfall, bis die Rubrik etwas anderes rechtfertigt
  — nie umgekehrt.

## Zwei häufige Fehleinstufungen

- **Ein Aggregator mit vielen Lesern ist trotzdem Tier 3**, wenn er nur zusammenfasst.
  Reichweite ist kein Kriterium oben.
- **Ein Preprint ist Tier 1 für die Autoren-Aussage, nicht für die Wahrheit der
  Aussage.** Ein kritischer Claim, der nur auf einem unreviewten Preprint beruht, ist
  ein Fall für „Nur Sekundärquellen gefunden" analog — die Skill markiert das im
  Bericht als vorläufig, wenn kein begutachteter Nachweis auffindbar ist.
