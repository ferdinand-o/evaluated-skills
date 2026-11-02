<!-- skill: feature-spec | schema: 1 | generated: feature-spec Draft für "decide" -->
# Feature: decide

## Problem
Claude fragt heute nach Dingen, die im Repo nachzulesen wären, und entscheidet umgekehrt
still Dinge, die teuer zurückzudrehen sind; welche Frage welche Behandlung braucht, prüft
niemand, und hinterher ist nicht nachvollziehbar, was Claude selbst entschieden hat. Der
Nutzer will (2026-11-02) eine Skill `/decide`, die Claudes eigene Fragen prüft: kleine
Entscheidungen fällt ein Modell selbst, nachdem es die sinnvollste Option erarbeitet hat;
große gehen mit den besten Optionen und aufgeschlüsseltem Kontext an den Nutzer. Auslöser:
manuell und „wenn Claude Fragen hat".

## Non-Goals
- Kein Hook auf `AskUserQuestion`: Eine Frage zu stellen ist die ungefährliche Handlung; ein Hook dort hielte das Falsche an (Spec 00 §4: G3 nur bei irreversiblem Schaden).
- Kein Hook am teuren Schritt selbst in diesem Zyklus; Migrationen bewacht schon `migration_gate.py` von sql-schema-architect.
- Kein Subagent für Entscheidungen, deren Beleg der Hauptagent mit einer Suche findet.
- Kein Ersatz für die `Annahme:`-Zeilen von feature-spec und work-plan; decide nutzt dasselbe Muster sitzungsweit.
- Kein Generator für Architektur-Entscheidungsdokumente (ADR), kein Schreiben in `docs/decisions.md` (das erntet feature-spec).
- Keine Änderung an der Regel `communication.md` von setup-user: Sie liegt in einem anderen Plugin, schon installierte Kopien bekämen den Verweis nicht.
- Keine Erweiterung von evalkit in diesem Zyklus (Assertions auf `tool_use`, Permission-Host); sie wird als offene Frage festgehalten.

## Annahmen
- Annahme: Die tragende Achse ist die Umkehrbarkeit. „Klein" heißt billig umkehrbar, „groß" heißt teuer umkehrbar — so bleibt die Einteilung des Nutzers, aber prüfbar. — widersprich, falls „groß" auch billig umkehrbare, aber folgenreiche Fragen umfassen soll.
- Annahme: Teuer umkehrbar sind genau diese Handlungen: öffentliche Schnittstelle oder API ändern; Datenschema ändern oder Migration anlegen; Daten in einer Datenbank löschen; Dateien löschen oder überschreiben, die nicht in Git gesichert sind (`git reset --hard`, `git clean`, nicht committete Arbeit); Force-Push oder Push auf einen geteilten Branch; Deploy, Mail, Zahlung oder ein anderer externer Seiteneffekt; Sicherheit oder Berechtigungen ändern; neue Abhängigkeit (Lieferkette, Lizenz); neue laufende Kosten.
- Annahme: Die Herkunft der Information steuert nur die Vorarbeit, nicht die Klasse: Vor einer kleinen Entscheidung sucht Claude einen Beleg im Repo, in Spec, Tests oder Doku.
- Annahme: Jede kleine Entscheidung trägt im Protokoll eine Belegzeile „gesucht: <Ort oder Muster> — Treffer: <datei:zeile>" oder „gesucht: … — nichts gefunden"; ohne Treffer ist sie eine Annahme statt einer Entscheidung.
- Annahme: Kleine Entscheidungen fällt der Hauptagent inline.
- Annahme: Ein Sonnet-Subagent mit frischem Kontext erarbeitet eine kleine Entscheidung nur, wenn die Suche mehr als zwei Dateien lesen müsste — Schwelle gesetzt, nicht gemessen. Das hält die Idee des Nutzers für Entscheidungen, die die Recherche wert sind, ohne Subagenten-Kosten für Kleinkram.
- Annahme: Jeder Subagent bekommt einen Entscheidungsauftrag statt einer freien Zusammenfassung, mit den Feldern Frage (ein Satz, neutral), Anlass (laufende Aufgabe und Ziel), Feste Vorgaben (Nutzer, Spec, Plan, Regeln, je mit Quelle), Schon entschieden (passende Einträge der Sitzung), Wo nachsehen (Pfade und Suchmuster, keine Inhalte) und Rückgabe (Optionen mit Belegen `datei:zeile`, Folgen, Umkehrbarkeit, Empfehlung).
- Annahme: Der Auftrag enthält keine Neigung des Hauptagenten — kein Feld „Empfehlung" und keine wertende Formulierung der Frage —, damit der frische Kontext des Subagenten nicht die Sicht des Hauptagenten bestätigt.
- Annahme: Ein Auftrag umfasst höchstens 25 Zeilen — Grenze geschätzt, nicht gemessen; ein längerer Auftrag nimmt dem Subagenten den Vorteil des frischen Kontexts.
- Annahme: `decide_log.py brief` füllt Schon entschieden, Feste Vorgaben und Rückgabe aus Protokoll und Regeldateien; der Hauptagent ergänzt Frage, Anlass und Wo nachsehen. Der Auftrag liegt neben dem Protokoll unter `.skills/cache/decide/<session>/brief-<n>.md` und dient bei großen Entscheidungen zugleich als erster Teil der Vorlage an den Nutzer.
- Annahme: Für eine große Entscheidung schreibt Claude eine Vorlage mit zwei bis vier Optionen (vier ist die Obergrenze von `AskUserQuestion`), je Option Folgen und Umkehrbarkeit, und einer Empfehlung mit Grund; braucht die Vorlage Belege aus mehr als zwei Dateien, erarbeitet sie ein Sonnet-Subagent.
- Annahme: Claude führt eine große Entscheidung nie selbst aus, sondern arbeitet bis vor den teuren Schritt weiter und stellt die Frage.
- Annahme: Mehrere große Fragen werden gesammelt und gebündelt gestellt, solange die Arbeit bis dahin weiterlaufen kann.
- Annahme: Unbeaufsichtigt ist ein Lauf, in dem `AskUserQuestion` nicht in der Werkzeugliste steht — `claude -p` ohne Permission-Host und jeder Subagent. Dort bleibt eine große Frage offen und wird abgelegt, statt beantwortet.
- Annahme: Das Protokoll liegt je Sitzung unter `.skills/cache/decide/<CLAUDE_CODE_SESSION_ID>.md` (Ephemera, Kopfzeile); die Variable setzt Claude Code in Bash- und Hook-Prozessen.
- Annahme: Offene große Fragen liegen als Wissen unter `docs/open-decisions.md` (committet, Kopfzeile, eine Zeile je Frage), damit sie einen frischen Clone, eine Cloud-Sitzung oder einen geplanten Lauf überleben.
- Annahme: Am Ende einer Aufgabe nennt die Antwort alle kleinen Entscheidungen und Annahmen der Sitzung aus `decide_log.py summary`, je einzeln widerrufbar; ab mehr als zehn Einträgen nennt sie die zehn jüngsten und den Pfad des Protokolls — Grenze gesetzt, nicht gemessen.
- Annahme: Regeln des Nutzers stehen als Zeilen `immer fragen: <Thema>` oder `nie fragen: <Thema>` in `.skills/decide/rules.md` (Repo) und `~/.skills/decide/rules.md` (Nutzer), nach Spec 00 §1 als Konfiguration.
- Annahme: `immer fragen` macht eine kleine Entscheidung zu einer großen; `nie fragen` wirkt nur auf kleine Entscheidungen und kann eine große nie herabstufen.
- Annahme: Trigger in zwei Schichten — manuell `/decide <frage>` und die Description, die auf Entscheidungen über die laufende Arbeit eingegrenzt ist und brainstorming, learning-coach, exercise-forge und den Plan-Modus ausgrenzt.
- Annahme: Ein Tier-1-Skript `decide_log.py` mit `add`, `summary`, `check`, `open` und `brief` trägt das Protokoll; `check --range <bereich>` meldet Änderungen im Diff, die zur Liste „teuer umkehrbar" gehören, aber keinen freigegebenen großen Eintrag haben (G2).
- Annahme: Plugin `evaluated-dev`, portables Frontmatter ohne `disable-model-invocation`.
- Annahme: Die zentralen Weichen (Umkehrbarkeit als Achse, Subagent nur bei Recherchebedarf, kein Hook auf der Frage) stammen aus dem Gespräch vom 2026-11-02 und dem Review dieses Entwurfs; bestätigt hat der Nutzer sie noch nicht.

## Ansatz
Die Skill entsteht nach dem Hausprozess (skill-forge, Spec 17): Aus diesem Entwurf wird eine
Spec unter `specs/` (nächste freie Nummer 28), dann Plan mit impl-plan und Bau. Der Entwurf
stützt sich auf Vorhandenes:

- **Annahme-Muster:** feature-spec (`skills/feature-spec/`, „Annahme:"-Zeilen, einzeln
  widersprechbar) und work-plan (`skills/work-plan/SKILL.md`, „Quelle oder Annahme").
  decide überträgt das Muster auf die ganze Sitzung und fügt die Belegzeile hinzu.
- **Rückfrage-Regel:** `skills/setup-user/assets/rules/communication.md` sagt schon
  „Rückfragen nur, wenn verschiedene Lesarten zu verschiedener Arbeit führen; sonst die
  naheliegende Annahme nennen und weitermachen". decide ist das Verfahren hinter dieser Regel
  und nennt sie in der Abgrenzung; die Regel selbst bleibt unverändert.
- **Wann jemand antworten kann:** `claude -p` bietet `AskUserQuestion` nur mit einem
  Permission-Host an (Hooks-Doku, Abschnitt zu `AskUserQuestion`: „offers them only when the
  run has a permission host"). Gemessen am 2026-11-02 mit CLI 2.1.316: ohne Host fehlt das
  Werkzeug in der Werkzeugliste von `system.init`; mit `--permission-prompt-tool` ist es da,
  und ein `PreToolUse`-Hook darauf feuert. Subagenten bekommen das Werkzeug nie
  (Subagenten-Doku). Daraus folgt die Annahme zum unbeaufsichtigten Lauf.
- **Messbarkeit:** Skripte prüfen Unit-Tests (siehe Akzeptanzkriterien). Das Verhalten des
  Modells prüfen Evals in `evals/decide/evals.json`, die die Spec nach skill-forge festlegt:
  `anti-ceremony-trivial-name-stays-inline` (Benennung nach vorhandenem Muster, Protokoll mit
  Beleg, Bericht kurz), Spalte löschen (`file_unchanged` auf die Migration, Eintrag in
  `docs/open-decisions.md`), neue Abhängigkeit (`file_unchanged` auf `pyproject.toml`),
  Regel `immer fragen` aus einer Fixture-Datei `.skills/decide/rules.md`, Routing ohne
  Skill-Namen. Alle laufen über `claude -p` ohne Permission-Host, also als unbeaufsichtigter
  Lauf. Ob ein Subagent startet, kann evalkit nicht beobachten, weil es nur Textblöcke liest.
- **Verhältnis zu den Plan-Skills:** subagent-dev (Spec 09) dispatcht Tasks an Subagenten,
  die nie `AskUserQuestion` haben; Spec 27 legt Prüfpunkte fest. Große Fragen aus Tasks landen
  über decide in `docs/open-decisions.md`, und der nächste Prüfpunkt nennt sie.

Bausteine: `skills/decide/SKILL.md` (Ablauf, Klassen, Contract, Abgrenzung),
`references/reversibility.md` (die Liste „teuer umkehrbar" mit Beispielen und den Mustern,
die `check` im Diff sucht), `references/option-memo.md` (Form der Vorlage für große Fragen),
`references/brief.md` (Felder des Entscheidungsauftrags an Subagenten, was nicht hinein gehört),
`scripts/decide_log.py` (Tier 1).

## Akzeptanzkriterien

### Kleine Entscheidung mit Beleg wird protokolliert
- Given eine Sitzung mit gesetzter `CLAUDE_CODE_SESSION_ID`
- When `decide_log.py add` eine kleine Entscheidung mit Belegzeile „gesucht: src/parsers — Treffer: src/parsers/csv.py:12" erhält
- Then steht in `.skills/cache/decide/<session>.md` eine Zeile mit Frage, Klasse klein, Entscheidung und Beleg
- And die Datei trägt in Zeile 1 die Kopfzeile

### Kleine Entscheidung ohne Treffer wird Annahme
- Given eine Belegzeile „gesucht: docs, README — nichts gefunden"
- When `decide_log.py add` die kleine Entscheidung erhält
- Then steht sie als Annahme im Protokoll, nicht als Entscheidung

### Kleine Entscheidung ohne Belegzeile wird abgewiesen
- Given ein Aufruf von `decide_log.py add` für eine kleine Entscheidung ohne Belegzeile
- When das Skript läuft
- Then schreibt es keine Zeile und endet mit Exit 1 und dem Grund

### Regel immer fragen macht klein zu groß
- Given `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
- When `decide_log.py add` eine kleine Entscheidung mit Thema `UI-Texte` erhält
- Then schreibt es sie als große offene Frage nach `docs/open-decisions.md`
- And das Protokoll nennt die Regel als Grund

### Regel nie fragen stuft groß nicht herab
- Given `~/.skills/decide/rules.md` enthält `nie fragen: Migrationen`
- When `decide_log.py add` eine große Entscheidung mit Thema `Migrationen` erhält
- Then bleibt sie groß und offen
- And die Ausgabe meldet, dass die Regel auf große Entscheidungen nicht wirkt

### Zusammenfassung zeigt nur die eigene Sitzung
- Given das Protokoll der laufenden Sitzung hat zwei Entscheidungen und eine Annahme
- And ein Protokoll einer früheren Sitzung hat fünf Einträge
- When `decide_log.py summary` läuft
- Then nennt es genau die drei Einträge der laufenden Sitzung

### Zusammenfassung kürzt ab zehn Einträgen
- Given das Protokoll der laufenden Sitzung hat zwölf Einträge
- When `decide_log.py summary` läuft
- Then nennt es die zehn jüngsten und den Pfad des Protokolls

### Teure Änderung ohne Freigabe wird gemeldet
- Given ein Diff, der eine neue Abhängigkeit in `pyproject.toml` und eine neue Datei unter `migrations/` enthält
- And im Protokoll gibt es dafür keinen freigegebenen großen Eintrag
- When `decide_log.py check --range <bereich>` läuft
- Then meldet es beide Stellen mit Datei und Grund aus der Liste „teuer umkehrbar"

### Freigegebene teure Änderung wird nicht gemeldet
- Given derselbe Diff
- And `docs/open-decisions.md` führt beide Fragen mit Antwort des Nutzers als freigegeben
- When `decide_log.py check --range <bereich>` läuft
- Then meldet es nichts

### Auftrag übernimmt passende Einträge und Regeln
- Given das Protokoll der Sitzung hat eine Entscheidung mit Thema `CLI` und eine mit Thema `Logging`
- And `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
- When `decide_log.py brief --topic CLI` läuft
- Then enthält der Auftrag unter Schon entschieden genau den Eintrag mit Thema `CLI`
- And unter Feste Vorgaben die Regel mit ihrer Datei als Quelle
- And die Felder Frage, Anlass und Wo nachsehen stehen leer zum Ausfüllen

### Zu langer oder wertender Auftrag wird gemeldet
- Given ein ausgefüllter Auftrag mit 30 Zeilen und einem Feld `Empfehlung des Hauptagenten`
- When `decide_log.py brief --check` den Auftrag prüft
- Then meldet es die Länge über 25 Zeilen und das unzulässige Feld
- And endet mit Exit 1

### Offene große Fragen überleben die Sitzung
- Given eine große Frage wurde in einer früheren Sitzung abgelegt und nicht beantwortet
- When `decide_log.py open` in einer neuen Sitzung läuft
- Then nennt es die Frage mit Datum, Optionen und Empfehlung aus `docs/open-decisions.md`

## Offene Fragen
- Bleibt es bei „Sonnet-Subagent nur ab Recherche über mehr als zwei Dateien", oder sollen kleine Entscheidungen wie ursprünglich gewünscht immer von Sonnet-Subagents gefällt werden? Das kostet je Frage einen Subagenten. — Entscheider: du.
- Soll „groß" neben teuer umkehrbaren Schritten auch billig umkehrbare, aber folgenreiche Fragen umfassen (etwa Architekturrichtung eines Features), und woran wäre das prüfbar? — Entscheider: du.
- Soll evalkit Assertions auf `tool_use` und einen Permission-Host bekommen, damit Subagenten-Nutzung und das Fragen selbst messbar werden? Das wäre eine eigene Spec. — Entscheider: du.
- Gehört ein Hook am teuren Schritt (Push auf geteilten Branch, `git clean`, neue Abhängigkeit) in einen späteren Zyklus, nachdem `check` gezeigt hat, wie oft so etwas ohne Freigabe passiert? — Entscheider: du, nach der Messung.
- Wer räumt `docs/open-decisions.md` auf, wenn eine Frage beantwortet ist: decide beim nächsten Aufruf oder der Nutzer? — Entscheider: du.

---
Quellen: `skills/feature-spec/SKILL.md` und `references/decisions-guide.md`, `skills/work-plan/SKILL.md`, `skills/setup-user/assets/rules/communication.md`, `skills/sql-schema-architect` (`migration_gate.py`), `skills/debug-ledger/assets/hooks/check-ledger.json`, `specs/Spec 00 – skill-foundation.md` (§1, §4, §5), `specs/Spec 25 – skill-dir.md`, `skills/skill-forge/scripts/lint_skill.py`, `evalkit/` (Assertion-Typen, Judge liest nur Text), Claude-Code-Doku (Hooks: `AskUserQuestion`, Permission-Host; Headless; Subagenten; Umgebungsvariablen: `CLAUDE_CODE_SESSION_ID`), Messungen mit `claude -p` am 2026-11-02, Opus-Review dieses Entwurfs am 2026-11-02 · Übersprungene Quellen: `docs/decisions.md` (existiert in diesem Repo nicht)
