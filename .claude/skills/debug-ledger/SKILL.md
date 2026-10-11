---
name: debug-ledger
description: "Use when encountering any bug, test failure, or \"das funktioniert nicht\" — including a one-line typo fix, not only hard cases. Every case gets a ledger file under docs/debugging/ with mandatory fields (Symptom, Repro-Kommando, Erwartung vs. Beobachtung); the archive is checked for a matching solved case first; and a full-mode fix proposal is mechanically refused without at least one tested row in the Hypothesen-Tabelle. Triggers include \"Bug\", \"Testfehler\", \"das geht nicht\", \"warum stürzt das ab\", \"es ist immer noch kaputt\". Not for new feature work (use feature-spec). What sets this apart from any other debugging doctrine, including one installed by another plugin, is the artifact: a persisted, archived, mechanically-checked ledger file under docs/debugging/ that a prose-only doctrine never produces — not stricter rhetoric, the same trigger scope plus a file."
---

# debug-ledger — das Artefakt ist der Prozess

Die Skill organisiert sich um das Schema von `debug-ledger.md`, nicht um
Prosa-Phasen. Leere Pflichtfelder sind der Durchsetzungsmechanismus: Ein
vorgeschlagener Fix bei leerer Hypothesen-Tabelle ist ein mechanisch sichtbarer
Regelverstoß, den `check_ledger.py` benennt.

## Die eiserne Regel

```
KEIN FIX-VORSCHLAG IM VOLLEN MODUS OHNE MINDESTENS EINE GETESTETE HYPOTHESE
```

Adaptiert aus [obra/superpowers](https://github.com/obra/superpowers) (MIT
License, Copyright (c) 2025 Jesse Vincent) — dort als „Iron Law" formuliert.
Der Unterschied hier: Statt einer Selbstverpflichtung ist es eine Datei-Prüfung.
Volle Attribution und die adaptierte 3-Fehlversuche-Regel: `references/escalation.md`.

## Ablauf

**Phase 0 — Archiv-Check.** Lies `docs/debugging/INDEX.md` und suche nach
Symptom-Stichworten, bevor du irgendetwas anlegst. Ein Treffer wird zuerst als
Hypothese getestet. Fehlt `INDEX.md` (kein Archiv, oder noch kein Fall gelöst),
ist das kein Fehler — es gibt schlicht keinen Treffer, weiter zu Schritt 1.

1. **Mini-Ledger anlegen, ausnahmslos:**
   ```bash
   python skills/debug-ledger/scripts/new_ledger.py \
     --symptom "…" --repro "…" --expected "…" --observed "…"
   ```
   Auch bei einem Tippfehler-Bug. Das Mini-Ledger ist drei Zeilen Aufwand, kein
   Prozess.
2. **Eskalieren, wenn eines der vier Signale zutrifft** (Details:
   `references/escalation.md`): zweiter fehlgeschlagener Fixversuch,
   Multi-Komponenten-Verdacht, kein zuverlässiges Repro, oder der Nutzer meldet
   „immer noch kaputt".
   ```bash
   python skills/debug-ledger/scripts/new_ledger.py --escalate PFAD
   ```
   Sonst bleibt es beim Mini-Ledger — das ist der Normalfall, nicht die Ausnahme.
3. **Im vollen Modus:** Evidenz sammeln (`references/tooling-python.md`,
   `references/tooling-node.md`, `scripts/bisect_run.py`), jede Zeile der
   Hypothesen-Tabelle mit echtem Test füllen, bevor `## Fix` einen Vorschlag
   bekommt.
4. **Vor jedem Fix-Vorschlag im vollen Modus prüfen:**
   ```bash
   python skills/debug-ledger/scripts/check_ledger.py PFAD
   ```
   Exit 1 heißt: Verstoß, nicht vorschlagen. Der Fix-Commit referenziert die
   Ledger-Datei in der Commit-Message.
5. **Nach Auflösung:**
   ```bash
   python skills/debug-ledger/scripts/new_ledger.py --resolve PFAD --cause "…"
   ```
   Das Ledger bleibt im Archiv, `INDEX.md` bekommt seine Symptom→Ursache-Zeile.
   So verzinst sich jeder gelöste Bug in Phase 0 aller zukünftigen.

## Contract

- Mini-Ledger ist für jeden Fall Pflicht, unabhängig von gefühlter Trivialität.
- Volles Schema nur durch die vier definierten Signale, nie durch
  Selbsteinschätzung „ist eh einfach".
- Kein Fix-Vorschlag im vollen Modus ohne getestete Hypothesen-Zeile —
  `check_ledger.py` ist **G2** (meldet Verstoß, Aufruf bleibt freiwillig).
- `docs/debugging/INDEX.md` bleibt flach. Ab 50 Einträgen warnt
  `--resolve` sichtbar; die Datei wird nie automatisch umgegliedert oder
  geprunt — das Archiv ist der Zinseszins dieser Skill, ein geprunter Fall ist
  genau der, den Phase 0 als Nächstes gebraucht hätte.
- Jedes Ledger trägt als erste Zeile die Kopfzeile
  `<!-- skill: debug-ledger | schema: 1 | generated: <Kommando> -->`;
  `INDEX.md` ebenso. Vollregel (Ausnahmen, Konsumenten-Regel): `docs/artifact-header.md`
  — Repo-Kontext, nicht Teil dieser Skill.

## Anti-Rationalisierung

Adaptiert aus obra/superpowers (MIT License, Copyright (c) 2025 Jesse Vincent).

| Gedanke | Realität |
| --- | --- |
| „Ist doch trivial, kein Ledger nötig" | Mini-Ledger ist drei Zeilen. Aufwand ist keine Ausrede. |
| „Ich seh das Problem schon, lass mich fixen" | Symptom sehen ≠ Ursache verstehen. Ohne getestete Hypothese ist es eine Vermutung. |
| „Noch ein Fix, dann passt's" (nach 2 Fehlschlägen) | Genau das Signal für Eskalation, nicht für einen dritten Versuch ohne Evidenz. |
| „Das Archiv durchsuchen kostet Zeit, ich kenn den Fall eh nicht" | Phase 0 ist eine Grep-Suche, keine Recherche. Überspringen kostet mehr, wenn der Fall doch drinsteht. |
| „Mehrere Fixes gleichzeitig probieren spart Zeit" | Dann weißt du nicht, welcher wirkte. Eine Hypothese, ein Test. |

## Leerfälle

- Kein `docs/debugging/`-Verzeichnis → beim ersten `new_ledger.py`-Aufruf wird
  es angekündigt und angelegt (Bootstrap-Regel, Spec 00 §1), nicht stillschweigend.
- `bisect_run.py` ohne Git-Repo → meldet das explizit, Exit 2, kein stiller
  Fehlschlag.
- `--escalate` auf ein bereits volles Ledger → idempotent, ändert nichts.
- `--resolve` auf ein Ledger mit vorhandener `INDEX.md`-Zeile → idempotent.

## Optionaler Hook (G3)

`assets/hooks/check-ledger.json` ist eine Vorlage für einen `PreToolUse`-Hook,
der `git commit` abfängt und `check_ledger.py --staged` laufen lässt. **Wird von
dieser Skill nie automatisch installiert** (Spec 00 §4) — der Nutzer kopiert das
Fragment bewusst in seine `settings.json`. Ohne Hook bleibt es bei G2.

## Abgrenzung

- **`superpowers:systematic-debugging`** — dieselbe Grunddoktrin (Root Cause
  vor Fix), aber rein im Chatverlauf. `debug-ledger` schreibt stattdessen ein
  Artefakt, das die Session überlebt, mechanisch geprüft wird und ein Archiv
  füttert. Bei echtem Doppel-Trigger gewinnt die spezifischere, artefaktbasierte
  Beschreibung dieser Skill für Anfragen, die einen Bug/Testfehler benennen.
- **`feature-spec`** — neues Feature, keine Fehlersuche. Nicht diese Skill.
- Ohne Git-Repo funktioniert das Ledger trotzdem (reine Dateien unter
  `docs/debugging/`); nur `bisect_run.py` braucht Git.
