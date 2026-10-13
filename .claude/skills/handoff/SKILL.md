---
name: handoff
description: Use when a work session is ending, before a planned /clear, or after completing a major milestone — creates or updates handoff.md in the project root so a fresh Claude Code session can continue seamlessly. Triggers include "handoff", "Übergabe", "sichere den Stand", "machen wir morgen weiter", "wir hören hier auf", "lass uns aufhören", "wrap up".
---

# Handoff — Sitzungszustand für die nächste Session sichern

Schreibe oder aktualisiere `./handoff.md` im Projekt-Root (= aktuelles
Arbeitsverzeichnis), damit eine frische Claude-Code-Session ohne Erklärung
des Nutzers weiterarbeiten kann.

## Abgrenzung

- `CLAUDE.md` = dauerhafte Konventionen. **Nie** von diesem Skill anfassen.
- Memory-Verzeichnis (`~/.claude/projects/.../memory/`): **nie** von diesem
  Skill anfassen.
- `handoff.md` = rollierender Sitzungszustand. Nur diese Datei schreiben.
- Kein `git commit` — der Nutzer committet selbst.
- **setup-user** installiert einen Hook, der bei hohem Kontext mit `[setup-user]` zum
  Sichern rät; den Stand sichert handoff, nicht der Hook.
- **human-prose** überarbeitet auf Zuruf den Fließtext einer `handoff.md`; die
  Kopfzeile `# Handoff — <Projektname>` und die sechs Sektionen bleiben.

## Vorgehen

1. Existierende `./handoff.md` lesen (falls vorhanden). Ihr „Stand:"-Datum
   bestimmt, seit wann Fortschritt zu erfassen ist.
2. Grounding sammeln: `git log --oneline --since=<Stand-Datum>` und
   `git status`. Ohne Git-Repo stattdessen: Sessionverlauf und
   Datei-Zeitstempel (`ls -lt`).
3. Sessionverlauf auswerten: Was wurde implementiert (mit Dateipfaden)?
   Welche Probleme sind offen (Symptom, was wurde probiert, Stand)? Welche
   Entscheidungen fielen und warum? Welche Ansätze wurden verworfen?
4. `./handoff.md` **komplett neu schreiben** (Write, ersetzen — nie
   anhängen), exakt im Format unten.
5. Dem Nutzer in 1–2 Sätzen bestätigen, was aktualisiert wurde.

## Format (exakt diese sechs Sektionen)

    # Handoff — <Projektname> (Stand: YYYY-MM-DD)

    ## Status
    2–3 Sätze: Big Picture + aktuelle Phase.

    ## Implementiert
    Kürzlich Fertiges, je mit Dateipfad(en).

    ## Offene Probleme
    Je Problem: Symptom, was probiert wurde, aktueller Stand.

    ## Erkenntnisse & Entscheidungen
    Warum-Entscheidungen, verworfene Ansätze, Stolperfallen.

    ## Nächste Schritte
    Konkret und geordnet.

    ## Einstiegspunkte
    Schlüsseldateien, Start-/Testkommandos.

## Inhaltsregeln

- **Max. 150 Zeilen.** Vorgefundene längere Datei beim Update aggressiv
  auf das Limit prunen.
- **Ziele stehen nicht hier.** Existiert `docs/goals.md` mit lesbarer Kopfzeile von
  setup-repo, nennt die Übergabe es unter „Einstiegspunkte" — der Zielstand über
  Sitzungen gehört dorthin, `handoff.md` trägt nur den Stand dieser Sitzung.
- Erledigtes fliegt raus, sobald es nicht mehr handlungsrelevant ist —
  die Git-Historie ist das Archiv.
- Keine Diff-Nacherzählung: nur, was nicht aus Code/Git ableitbar ist
  (Warum-Entscheidungen, verworfene Ansätze, offene Probleme mit Stand).
- Dateipfade statt Prosa — die nächste Session liest Dateien selbst.
- Absolute Daten („2026-07-03"), nie relative („gestern").
- Sprache: Deutsch.

## Randfälle

- Verzeichnis sieht nicht nach Projekt aus (kein Git, kein Code): erst
  beim Nutzer nachfragen, bevor du eine handoff.md anlegst.
- Leere Sektion (z. B. keine offenen Probleme): Sektion behalten, Inhalt
  „Keine." — nie Sektionen weglassen.
