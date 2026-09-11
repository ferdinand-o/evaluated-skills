---
name: skill-forge
description: Use when a skill of this collection is to be built from a spec or changed afterwards — "bau mir eine Skill", "ändere die Skill X", "prüfe die Skill X", "neue Skill nach Spec NN". Not for skills outside this collection or without evalkit (use skill-creator, which brings its own evals.json schema), and not for discipline skills that need pressure scenarios (use superpowers:writing-skills).
---

# skill-forge — Skills, die ihr eigenes Gate passieren

**Eiserne Regel:** *Keine Skill gilt als fertig, solange `lint_skill.py` einen **neuen**
Befund meldet, und keine ohne die Sektion „Was nicht gemessen wurde" im Report.* Bei
einer neuen Skill ist jeder Befund neu. G1 — diese SKILL.md verlangt es; Zähne bekommt
sie von `tests/test_skills_lint.py`, der jeden Skill-Ordner gegen ein eingefrorenes
Register lintet, sobald jemand `pytest` fährt (G2).

## Ablauf

1. **Spec** — `brainstorming` für Neues, `feature-spec` (03) mit Codebase-Bezug. Die
   Spec trägt eine Eval-Tabelle mit `id`-Spalte; ohne sie prüft niemand Coverage.
2. **Plan** mit `impl-plan` (16). Bei Tier 0 stehen die Evals vor der SKILL.md.
3. **Bau** im Hauptkontext oder in Paketen mit `subagent-dev` (09). Vorher
   `references/checklist.md`, nur den Abschnitt der Phase — nicht die ganze
   Pitfalls-Datei. Für Doktrin-Text: `references/form-selection.md` (welche Form gegen
   welches Versagen). Gerüste: `assets/skill-template/`.
4. **Lint, vor dem Commit:**
   ```bash
   python skills/skill-forge/scripts/lint_skill.py skills/<name> --base HEAD --out .skills/cache/skill-forge/lint.json
   # installiert: python .claude/skills/skill-forge/scripts/lint_skill.py skills/<name> --base HEAD --out …
   ```
   `--base HEAD` vergleicht mit dem letzten Commit; nur neue Befunde zählen. Ohne
   `--base` zählt alles (neue Skill), und `evals_due` ist ungeprüft, nie „nein". Fehlt
   das Skript, lautet die Übergabe „ungeprüft — Lint nicht verfügbar", nie „fertig".
5. **Evals**, wenn `evals_due: true` oder neue Skill — nach `references/evals.md`:
   `evalkit`-Schema, ein Prompt je Eval, Diskriminator-Frage in `notes`, ein Eval mit
   ID-Präfix `anti-ceremony-`. Vor jeder Fix-Runde ein zweiter Lauf.
6. **Review** durch einen Subagenten mit frischem Kontext
   (`references/reviewer-prompt.md`); dessen tragende Befunde selbst nachmessen; jede
   Fix-Runde endet mit dem Lint.
7. **Report, known-limits, Nachbarn** — Report mit „Was nicht gemessen wurde", Abschnitt
   `## <name>` in `docs/known-limits.md`, Routing-Matrix in Spec 00 §5 und `README.md`,
   Rückverweise der Nachbarn. Der Lint prüft alle drei; danach ist er ganz sauber.

**Anti-Zeremonie-Regel:** Ein geänderter Satz in einer bestehenden SKILL.md löst Lint
und Commit aus, sonst nichts — kein Eval, kein Report, kein Review — es sei denn, der
Lint meldet `evals_due: true` oder einen neuen Befund. Altbefunde der Skill stehen im
Register des Repo-Tests und sind nicht Sache dieser Änderung.

## Contract

- **Dreizehn Regeln, vier Zustände.** Jede Regel meldet `pass`, `finding`, `hint` oder
  `unchecked` mit Grund. **`unchecked` und `hint` zählen nie als `pass`**: Was der
  Lint nicht sehen konnte (kein `docs/`, keine Nachbarn, keine `evals.json`), hat er
  nicht bestanden — er sagt es. Im Eval-Workspace sind die Regeln zu `docs/`,
  Routing und Nachbarn deshalb `unchecked`; die Evals dieser Skill binden nur an
  Regeln, die dort geprüft sind.
- **Diff-Modus meldet nur Neues.** Mit `--base` läuft der Lint zweimal (Arbeitsstand,
  Basis) und der Exit-Code folgt `new_findings`. Ohne Git oder unbekannte Revision:
  Exit 2 mit Grund — nie stillschweigend „alles neu".
- **`evals_due` ist mechanisch:** `true`, wenn der Diff Frontmatter, einen
  Contract-Abschnitt (`## … Contract`) oder eine Zeile berührt, auf die ein
  Assertion-Pattern der eigenen `evals.json` greift. Der Aufrufer entscheidet nichts
  im Kopf.
- **`lint.json` ist das Artefakt** (`docs/artifact-header.md`, `_meta`): eine Zeile je
  Regel als `{"id": …, "status": …, "reason": …}`, in dieser Reihenfolge — an sie
  binden Evals.
- **Register statt Aufräumen.** Bestehende Skills tragen ihre Altbefunde in
  `tests/test_skills_lint.py`; die Menge darf nur schrumpfen, ein neuer Skill kommt nie
  hinein. `skill-forge` selbst hat ein leeres Register.
- **Was der Lint nicht prüft, prüft der Reviewer:** ob Assertions an skill-eigenen
  Artefakten hängen, ob Erzeuger und Konsument einer Schnittstelle zusammenpassen, ob
  Beispiele ihre Regel treffen, wo etwas Erfolg meldet, ohne geprüft zu haben.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Der Altbefund ist nicht meiner" | Stimmt — deshalb zählt er im Diff-Modus nicht. Was neu ist, ist deiner. |
| „Der Lint ist rot, ich räume schnell alles auf" | Das ist die Zeremonie, gegen die die Skill gebaut ist. `--base HEAD`, nur Neues beheben; das Register bleibt, bis jemand es bewusst schrumpft. |
| „Ein Satz braucht keinen Lint" | Ein Satz im Contract macht Evals fällig, einer im Frontmatter ändert den Trigger. Ob es einer davon war, sagt `evals_due` in einer Sekunde. |
| „`unchecked` ist praktisch grün" | Es ist praktisch nichts. Sieben Regeln `unchecked` heißt: sieben Regeln ungeprüft, und der Report sagt das. |
| „Die Description soll erklären, was die Skill tut" | Dann folgt der Agent der Description statt dem Body. Trigger und Abgrenzung — das Tun steht im Ablauf. |
| „Die Diskriminator-Frage beantworte ich pauschal" | Sechzehn fremde Skills sind im Harness sichtbar. Eine Assertion, die eine von ihnen genauso erfüllt, misst nichts. Je Eval, wörtlich in `notes`. |
| „Evals fahren hier nicht, also schreibe ich sie später" | Sie sind die ausführbare Definition von „fertig", gefahren oder nicht. Ungefahren steht im Report — nicht geschrieben ist ein Befund. |

## Abgrenzung

- **skill-creator** (Anthropic, im Nutzerprofil) — Skills außerhalb dieser Sammlung
  oder ohne `evalkit`. Sein `evals.json`-Schema (`expected_output`, `assertions`) ist
  mit `evalkit` inkompatibel; hier würde es die Eval-Datei überschreiben.
- **superpowers:writing-skills** — Disziplin-Skills, die Druckszenarien und
  Rationalisierungstabellen brauchen; „Match the Form to the Failure" ist von dort
  übernommen (`references/form-selection.md`). Rechnet in Wörtern, diese Sammlung in
  Zeilen.
- **impl-plan** (16) — der Plan-Schritt. Kein Plan → dort zuerst; diese Skill
  konsumiert ihn.
