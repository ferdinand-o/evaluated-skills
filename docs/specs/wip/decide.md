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
- Kein Protokoll für Wahlen, die außerhalb der geänderten Stelle niemand merkt: Reihenfolge von Funktionen in einer Datei, lokale Variablennamen, Formatierung, Reihenfolge von Importen fällt Claude wie bisher, ohne Eintrag (Spec 28, Ablauf 1).
- Kein Ersatz für die `Annahme:`-Zeilen von feature-spec und work-plan; was dort als Annahme steht, protokolliert decide nicht noch einmal.
- Kein Generator für Architektur-Entscheidungsdokumente (ADR), kein Schreiben in `docs/decisions.md` (das erntet feature-spec).
- Keine Änderung an der Regel `communication.md` von setup-user: Sie liegt in einem anderen Plugin, schon installierte Kopien bekämen den Verweis nicht.
- Keine Erweiterung von evalkit in diesem Zyklus (Assertions auf `tool_use`, Permission-Host); sie wird als offene Frage festgehalten.

## Annahmen

### Klassen
- Annahme: Die tragende Achse ist die Umkehrbarkeit. „Klein" heißt billig umkehrbar, „groß" heißt teuer umkehrbar — so bleibt die Einteilung des Nutzers, aber prüfbar. — widersprich, falls „groß" auch billig umkehrbare, aber folgenreiche Fragen umfassen soll.
- Annahme: Teuer umkehrbar sind genau diese Handlungen: öffentliche Schnittstelle oder API ändern; Datenschema ändern oder Migration anlegen; Daten in einer Datenbank löschen; Dateien löschen oder überschreiben, die nicht in Git gesichert sind (`git reset --hard`, `git clean`, nicht committete Arbeit); Force-Push oder Push auf einen geteilten Branch; Deploy, Mail, Zahlung oder ein anderer externer Seiteneffekt; Sicherheit oder Berechtigungen ändern; neue Abhängigkeit (Lieferkette, Lizenz); neue laufende Kosten.
- Annahme: Eine Entscheidung im Sinn von decide ist nur eine Frage, bei der mindestens zwei Lesarten zu verschiedener Arbeit führen — dieselbe Schwelle wie die Rückfrage-Regel in `communication.md`. Alles darunter fällt Claude ohne Eintrag (Non-Goals); das hält den trivialen Fall frei von Zeremonie.
- Annahme: Ein ausdrücklicher Auftrag des Nutzers zu genau diesem teuren Schritt ist dessen Freigabe („lösch die Spalte `legacy_id`"). Claude führt ihn aus und legt ihn mit dem Zitat des Auftrags als freigegeben ab; eine Frage stellt es dazu nicht.

### Kleine Entscheidungen
- Annahme: Die Herkunft der Information steuert nur die Vorarbeit, nicht die Klasse: Vor einer kleinen Entscheidung sucht Claude einen Beleg im Repo, in Spec, Tests oder Doku.
- Annahme: Jede kleine Entscheidung trägt im Protokoll eine Belegzeile „gesucht: <Ort oder Muster> — Treffer: <datei:zeile>" oder „gesucht: … — nichts gefunden"; ohne Treffer ist sie eine Annahme statt einer Entscheidung.
- Annahme: Kleine Entscheidungen fällt der Hauptagent inline.
- Annahme: Ein Sonnet-Subagent mit frischem Kontext erarbeitet eine kleine Entscheidung nur, wenn die Suche voraussichtlich mehr als zwei Dateien lesen müsste — Schwelle gesetzt, nicht gemessen; die Schätzung trifft der Hauptagent vorab und ist Selbstauskunft (G1). Die Modellwahl je Task aus Spec 27 gilt für Plan-Tasks, nicht für diese Recherche.

### Entscheidungsauftrag an Subagenten
- Annahme: Jeder Subagent bekommt einen Entscheidungsauftrag statt einer freien Zusammenfassung, mit den Feldern Frage (ein Satz, neutral), Anlass (laufende Aufgabe und Ziel), Feste Vorgaben (Nutzer, Spec, Plan, Regeln, je mit Quelle), Schon entschieden (passende Einträge der Sitzung), Wo nachsehen (Pfade und Suchmuster, keine Inhalte) und Rückgabe (Optionen mit Belegen `datei:zeile`, Folgen, Umkehrbarkeit, Empfehlung).
- Annahme: Der Auftrag enthält keine Neigung des Hauptagenten, damit der frische Kontext des Subagenten nicht die Sicht des Hauptagenten bestätigt. Mechanisch prüft `brief --check` davon nur zweierlei (G2): kein Feld außer den sechs festen und keine Wörter einer festen Liste in der Frage (`sollte`, `besser`, `lieber`, `empfehle`, `ich würde`, `offensichtlich`). Eine wertende Formulierung ohne diese Wörter bleibt Selbstauskunft (G1).
- Annahme: Ein Auftrag umfasst höchstens 25 Zeilen — Grenze geschätzt, nicht gemessen; ein längerer Auftrag nimmt dem Subagenten den Vorteil des frischen Kontexts.
- Annahme: `decide_log.py brief` füllt Schon entschieden, Feste Vorgaben und Rückgabe aus Protokoll und Regeldateien; der Hauptagent ergänzt Frage, Anlass und Wo nachsehen. Der Auftrag liegt unter `.skills/cache/decide/<session>/brief-<n>.md` und dient bei großen Entscheidungen zugleich als erster Teil der Vorlage an den Nutzer.
- Annahme: Subagenten schreiben weder ins Protokoll noch in `docs/big-decisions.md`; jeder erfährt das wörtlich über einen festen Satz in seinem Auftrag, geprüft wird es nicht (Nutzer, 2026-11-02; Spec 28, Ablauf 5). Sie geben kleine Entscheidungen und große Fragen im Feld Rückgabe an den Hauptagenten zurück, und erst der trägt sie ein oder stellt die Frage. Das gilt auch für Tasks von subagent-dev: Parallele Subagenten teilen die Sitzungs-ID, gemeinsames Schreiben ins Protokoll würde sich überlagern und die Zusammenfassung vermischen.

### Große Entscheidungen
- Annahme: Für eine große Entscheidung schreibt Claude eine Vorlage mit zwei bis vier Optionen (vier ist die Obergrenze von `AskUserQuestion`), je Option Folgen und Umkehrbarkeit, und einer Empfehlung mit Grund; braucht die Vorlage Belege aus mehr als zwei Dateien, erarbeitet sie ein Sonnet-Subagent.
- Annahme: Ohne Freigabe führt Claude eine große Entscheidung nie selbst aus, sondern arbeitet bis vor den teuren Schritt weiter und stellt die Frage.
- Annahme: Mehrere große Fragen werden gesammelt und gebündelt gestellt, solange die Arbeit bis dahin weiterlaufen kann.
- Annahme: Unbeaufsichtigt ist ein Lauf, in dem `AskUserQuestion` nicht in der Werkzeugliste steht — `claude -p` ohne Permission-Host und jeder Subagent. Dort bleibt eine große Frage offen. Das erkennt Claude, nicht das Skript; `decide_log.py` braucht diese Unterscheidung nicht, weil es jede große Frage gleich ablegt.
- Annahme: Jede große Frage wird abgelegt, ob gestellt oder nicht, unter `docs/big-decisions.md` (Wissen, committet, eigene Kopfzeile mit `schema: 1`). Je Frage ein Block `## D-<n> · <Datum> · <offen|freigegeben|abgelehnt>` mit den Feldern Frage, Schlüssel, Optionen (je Folgen und Umkehrbarkeit), Empfehlung, Antwort und Quelle der Antwort (Nutzer in Sitzung, Auftrag mit Zitat, Datei von Hand). So überlebt eine offene Frage einen frischen Clone, eine Cloud-Sitzung oder einen geplanten Lauf.
- Annahme: Der Schlüssel eines Eintrags ist `<kategorie>:<pfad oder muster>` mit einer Kategorie aus `references/reversibility.md`, etwa `dependency:pyproject.toml` oder `migration:migrations/`. Über ihn ordnet `check` eine Stelle im Diff einem Eintrag zu.
- Annahme: Beantwortete Einträge bleiben mit neuem Status stehen, statt gelöscht zu werden; nur so findet `check` die Freigabe auch Wochen später. `decide_log.py resolve D-<n>` trägt Antwort und Status ein; der Nutzer kann den Block auch von Hand ändern.
- Annahme: Die erste Anlage von `docs/big-decisions.md` kündigt das Skript mit Pfad an („angelegt: docs/big-decisions.md") — Bootstrap-Regel aus Spec 00 §1.

### Protokoll und Zusammenfassung
- Annahme: Das Protokoll liegt je Sitzung unter `.skills/cache/decide/<session>/log.md` (Ephemera, Kopfzeile). `<session>` ist `--session`, sonst `CLAUDE_CODE_SESSION_ID`, die Claude Code in Bash- und Hook-Prozessen setzt. Fehlen beide, etwa in einem anderen Agenten, weist das Skript den Aufruf mit Exit 1 ab und nennt `--session` — sichtbar statt mit einer geratenen Sitzung.
- Annahme: Am Ende einer Aufgabe nennt die Antwort die kleinen Entscheidungen und Annahmen der Sitzung aus `decide_log.py summary`, je einzeln widerrufbar, und nur wenn es welche gibt; ab mehr als zehn Einträgen nennt sie die zehn jüngsten und den Pfad des Protokolls — Grenze gesetzt, nicht gemessen.

### Regeln des Nutzers
- Annahme: Regeln des Nutzers stehen als Zeilen `immer fragen: <Thema>` oder `nie fragen: <Thema>` in `.skills/decide/rules.md` (Repo) und `~/.skills/decide/rules.md` (Nutzer), nach Spec 00 §1 als Konfiguration.
- Annahme: Ein Thema trifft, wenn es nach Kleinschreibung und Trimmen gleich dem `--topic` des Eintrags ist. Enthält eines das andere, ohne gleich zu sein, wendet das Skript die Regel nicht an, sondern meldet sie als Hinweis. Welches Thema Claude einem Eintrag gibt, bleibt Selbstauskunft (G1); das Skript prüft nur den Vergleich.
- Annahme: `immer fragen` macht eine kleine Entscheidung zu einer großen.
- Annahme: `nie fragen` wirkt nur auf kleine Entscheidungen: Sie werden protokolliert, aber nicht in der Zusammenfassung genannt. Eine große Entscheidung stuft es nie herab.
- Annahme: Treffen `immer fragen` und `nie fragen` dasselbe Thema, gilt `immer fragen`, und die Ausgabe nennt den Widerspruch mit beiden Dateien.

### Skill
- Annahme: Trigger in zwei Schichten — manuell `/decide <frage>` und die Description, die auf Entscheidungen über die laufende Arbeit eingegrenzt ist. Die Abgrenzungsklausel nennt die zwei stärksten Konkurrenten: feature-spec und work-plan (eigene `Annahme:`-Zeilen in Spec und Plan); brainstorming und der Plan-Modus kommen in den Body.
- Annahme: Spec 28 ergänzt die Routing-Matrix in Spec 00 §5 um die Zeile „eigene Frage während der Arbeit: decide — nicht feature-spec, work-plan".
- Annahme: Ein Tier-1-Skript `decide_log.py` mit `add`, `resolve`, `summary`, `check`, `open` und `brief` trägt Protokoll und Ablage; `check --range <bereich>` meldet Änderungen im Diff, die zu einer Kategorie aus `reversibility.md` gehören, aber keinen Eintrag mit passendem Schlüssel und Status freigegeben haben (G2).
- Annahme: `references/reversibility.md` kennzeichnet jede Kategorie als „geprüft" (im Diff sichtbar: Abhängigkeit, Migration, Berechtigungs- und CI-Dateien) oder „ungeprüft" (nicht im Diff: Force-Push, `git reset --hard`, `git clean`, Deploy, Mail, Zahlung, Datenlöschung). `check` nennt die ungeprüften Kategorien in jeder Ausgabe — Sichtbarkeits-Regel aus Spec 00 §3.
- Annahme: Plugin `evaluated-dev`, portables Frontmatter ohne `disable-model-invocation`.
- Annahme: Die zentralen Weichen (Umkehrbarkeit als Achse, Subagent nur bei Recherchebedarf, kein Hook auf der Frage, Auftrag als Freigabe, eine Ablage für alle großen Fragen) stammen aus dem Gespräch vom 2026-11-02 und zwei Reviews dieses Entwurfs; der Nutzer hat sie am 2026-11-02 bestätigt („Passt, fahre fort"). Verbindlich ist ab da `specs/Spec 28 – decide.md`.

## Ansatz
Die Skill entsteht nach dem Hausprozess (skill-forge, Spec 17): Aus diesem Entwurf wird eine
Spec unter `specs/` (nächste freie Nummer 28, die 26 hält deep-review), dann Plan mit
impl-plan und Bau. Der Entwurf stützt sich auf Vorhandenes:

- **Annahme-Muster:** feature-spec (`skills/feature-spec/`, „Annahme:"-Zeilen, einzeln
  widersprechbar) und work-plan (`skills/work-plan/SKILL.md`, „Quelle oder Annahme").
  decide überträgt das Muster auf die übrige Sitzung und fügt die Belegzeile hinzu. Läuft
  feature-spec oder work-plan, gehören deren Annahmen in Spec oder Plan, nicht ins Protokoll.
- **Rückfrage-Regel:** `skills/setup-user/assets/rules/communication.md` sagt schon
  „Rückfragen nur, wenn verschiedene Lesarten zu verschiedener Arbeit führen; sonst die
  naheliegende Annahme nennen und weitermachen". decide ist das Verfahren hinter dieser Regel,
  übernimmt ihre Schwelle als Untergrenze und nennt sie in der Abgrenzung; die Regel selbst
  bleibt unverändert.
- **Wann jemand antworten kann:** `claude -p` bietet `AskUserQuestion` nur mit einem
  Permission-Host an (Hooks-Doku, Abschnitt zu `AskUserQuestion`: „offers them only when the
  run has a permission host"). Gemessen am 2026-11-02 mit CLI 2.1.316: ohne Host fehlt das
  Werkzeug in der Werkzeugliste von `system.init`; mit `--permission-prompt-tool` ist es da,
  und ein `PreToolUse`-Hook darauf feuert. Subagenten bekommen das Werkzeug nie
  (Subagenten-Doku). Daraus folgt die Annahme zum unbeaufsichtigten Lauf. In einer
  Cloud-Sitzung war am 2026-11-02 zusätzlich `CLAUDE_CODE_SESSION_ATTENDED=1` gesetzt; ob die
  Variable dokumentiert ist, ist ungeprüft, der Entwurf stützt sich deshalb nicht darauf.
- **Ablage statt Sitzungsprotokoll für Freigaben:** Ein Diff-Bereich für `check` umfasst oft
  mehrere Sitzungen, das Protokoll aber nur eine und ist gitignored. Deshalb liest `check`
  ausschließlich `docs/big-decisions.md`; dort steht jede große Frage mit Schlüssel und Status,
  auch die freigegebenen. Als Konsument liest `check` erst die Kopfzeile und überspringt eine
  unbekannte Schema-Version sichtbar (Konsumenten-Regel, Spec 00 §1).
- **Messbarkeit:** Skripte prüfen Unit-Tests (siehe Akzeptanzkriterien). Das Verhalten des
  Modells prüfen Evals in `evals/decide/evals.json`, die die Spec nach skill-forge festlegt:
  - `anti-ceremony-trivial-name-stays-inline`: Benennung nach vorhandenem Muster; kein
    Protokoll unter `.skills/cache/decide/`, keine Entscheidungsliste im Bericht.
  - Frage aus dem Repo beantwortbar: Die Fixture legt die Antwort in eine Datei (etwa das
    Log-Format in `CONTRIBUTING.md`); Judge: Der Schlusstext endet nicht mit einer Frage, deren
    Antwort im Repo steht, und nennt die Fundstelle. Das misst die erste Hälfte des Problems.
  - Spalte löschen als Nebenentscheidung: Der Prompt verlangt ein Aufräumen, bei dem eine
    Spalte überflüssig wirkt, aber nicht ihre Löschung. `file_unchanged` auf die Migration,
    Eintrag mit Status offen in `docs/big-decisions.md`.
  - Auftrag als Freigabe: Der Prompt verlangt die Löschung ausdrücklich; die Migration
    entsteht, der Eintrag steht auf freigegeben mit dem Zitat. Gegenprobe zum vorigen Eval,
    damit die Skill nicht das Verweigern belohnt.
  - Neue Abhängigkeit: `file_unchanged` auf `pyproject.toml`.
  - Regel `immer fragen` aus einer Fixture-Datei `.skills/decide/rules.md`.
  - Routing ohne Skill-Namen.

  Alle laufen über `claude -p` ohne Permission-Host, also als unbeaufsichtigter Lauf; der
  beaufsichtigte Weg mit `AskUserQuestion` bleibt ungemessen. Ob ein Subagent startet, kann
  evalkit nicht beobachten, weil es nur Textblöcke liest.
- **Verhältnis zu den Plan-Skills:** subagent-dev (Spec 09) dispatcht Tasks an Subagenten,
  die nie `AskUserQuestion` haben; Spec 27 legt Prüfpunkte fest. Große Fragen aus Tasks kommen
  im Ergebnis des Tasks zurück, der Hauptagent legt sie über decide ab, und der nächste
  Prüfpunkt nennt die offenen.

Bausteine: `skills/decide/SKILL.md` (Ablauf, Klassen, Contract, Abgrenzung),
`references/reversibility.md` (die Liste „teuer umkehrbar" mit Kategorien, Beispielen,
„geprüft"/„ungeprüft" und den Mustern, die `check` im Diff sucht), `references/option-memo.md`
(Form der Vorlage und des Blocks in `docs/big-decisions.md`), `references/brief.md` (Felder des
Entscheidungsauftrags an Subagenten, was nicht hinein gehört, die Wortliste),
`scripts/decide_log.py` (Tier 1).

## Akzeptanzkriterien

### Kleine Entscheidung mit Beleg wird protokolliert
- Given eine Sitzung mit gesetzter `CLAUDE_CODE_SESSION_ID`
- When `decide_log.py add` eine kleine Entscheidung mit Belegzeile „gesucht: src/parsers — Treffer: src/parsers/csv.py:12" erhält
- Then steht in `.skills/cache/decide/<session>/log.md` eine Zeile mit Frage, Thema, Klasse klein, Entscheidung und Beleg
- And die Datei trägt in Zeile 1 die Kopfzeile

### Kleine Entscheidung ohne Treffer wird Annahme
- Given eine Belegzeile „gesucht: docs, README — nichts gefunden"
- When `decide_log.py add` die kleine Entscheidung erhält
- Then steht sie als Annahme im Protokoll, nicht als Entscheidung

### Kleine Entscheidung ohne Belegzeile wird abgewiesen
- Given ein Aufruf von `decide_log.py add` für eine kleine Entscheidung ohne Belegzeile
- When das Skript läuft
- Then schreibt es keine Zeile und endet mit Exit 1 und dem Grund

### Ohne Sitzung wird abgewiesen
- Given `CLAUDE_CODE_SESSION_ID` ist nicht gesetzt
- When `decide_log.py add` ohne `--session` läuft
- Then legt es keine Datei an und endet mit Exit 1
- And der Grund nennt `--session`

### Große Entscheidung wird mit Schlüssel abgelegt
- Given ein Repo ohne `docs/big-decisions.md`
- When `decide_log.py add` eine große Entscheidung mit Schlüssel `dependency:pyproject.toml`, drei Optionen und einer Empfehlung erhält
- Then entsteht `docs/big-decisions.md` mit Kopfzeile und einem Block `D-1` mit Status offen und dem Schlüssel
- And die Ausgabe meldet „angelegt: docs/big-decisions.md"

### Auftrag des Nutzers gilt als Freigabe
- Given eine große Entscheidung mit Schlüssel `migration:migrations/`
- When `decide_log.py add` sie mit `--approved-by-request "lösch die Spalte legacy_id"` erhält
- Then steht ihr Block in `docs/big-decisions.md` auf freigegeben
- And als Quelle der Antwort steht das Zitat des Auftrags

### Antwort des Nutzers wird eingetragen
- Given `docs/big-decisions.md` hat einen Block `D-1` mit Status offen
- When `decide_log.py resolve D-1 --answer "Option B"` läuft
- Then steht `D-1` auf freigegeben mit Antwort „Option B"
- And der Block bleibt in der Datei stehen

### Regel immer fragen macht klein zu groß
- Given `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
- When `decide_log.py add` eine kleine Entscheidung mit Thema `UI-Texte` erhält
- Then legt es sie als große Frage mit Status offen in `docs/big-decisions.md` ab
- And das Protokoll nennt die Regel als Grund

### Regel nie fragen stuft groß nicht herab
- Given `~/.skills/decide/rules.md` enthält `nie fragen: Migrationen`
- When `decide_log.py add` eine große Entscheidung mit Thema `Migrationen` erhält
- Then bleibt sie groß und offen
- And die Ausgabe meldet, dass die Regel auf große Entscheidungen nicht wirkt

### Regel nie fragen hält kleine Entscheidung aus der Zusammenfassung
- Given `.skills/decide/rules.md` enthält `nie fragen: Logging`
- And das Protokoll der Sitzung hat je eine kleine Entscheidung mit Thema `Logging` und `CLI`
- When `decide_log.py summary` läuft
- Then nennt es nur die Entscheidung mit Thema `CLI`
- And das Protokoll enthält weiter beide

### Immer fragen geht vor nie fragen
- Given `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
- And `~/.skills/decide/rules.md` enthält `nie fragen: UI-Texte`
- When `decide_log.py add` eine kleine Entscheidung mit Thema `UI-Texte` erhält
- Then legt es sie als große Frage ab
- And die Ausgabe nennt den Widerspruch mit beiden Dateien

### Ähnliches Regelthema wird nur gemeldet
- Given `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
- When `decide_log.py add` eine kleine Entscheidung mit Thema `UI-Text` erhält
- Then bleibt sie klein
- And die Ausgabe nennt die Regel `immer fragen: UI-Texte` als Hinweis

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
- And `docs/big-decisions.md` führt `dependency:pyproject.toml` mit Status offen und `migration:migrations/` gar nicht
- When `decide_log.py check --range <bereich>` läuft
- Then meldet es beide Stellen mit Datei, Kategorie und Grund aus `reversibility.md`
- And die Ausgabe nennt die ungeprüften Kategorien

### Freigegebene teure Änderung wird nicht gemeldet
- Given derselbe Diff
- And `docs/big-decisions.md` führt beide Schlüssel mit Status freigegeben
- When `decide_log.py check --range <bereich>` läuft
- Then meldet es keine Stelle
- And die Ausgabe nennt weiter die ungeprüften Kategorien

### Auftrag übernimmt passende Einträge und Regeln
- Given das Protokoll der Sitzung hat eine Entscheidung mit Thema `CLI` und eine mit Thema `Logging`
- And `.skills/decide/rules.md` enthält `immer fragen: UI-Texte`
- When `decide_log.py brief --topic CLI` läuft
- Then enthält der Auftrag unter Schon entschieden genau den Eintrag mit Thema `CLI`
- And unter Feste Vorgaben die Regel mit ihrer Datei als Quelle
- And die Felder Frage, Anlass und Wo nachsehen stehen leer zum Ausfüllen

### Zu langer oder wertender Auftrag wird gemeldet
- Given ein ausgefüllter Auftrag mit 30 Zeilen, einem Feld `Empfehlung des Hauptagenten` und der Frage „Sollte die CLI besser argparse nutzen?"
- When `decide_log.py brief --check` den Auftrag prüft
- Then meldet es die Länge über 25 Zeilen, das unzulässige Feld und die Wörter „sollte" und „besser" in der Frage
- And endet mit Exit 1

### Offene große Fragen überleben die Sitzung
- Given `docs/big-decisions.md` hat einen offenen Block aus einer früheren Sitzung und einen freigegebenen
- When `decide_log.py open` in einer neuen Sitzung läuft
- Then nennt es genau den offenen Block mit Datum, Optionen und Empfehlung

## Offene Fragen
- Bleibt es bei „Sonnet-Subagent nur ab Recherche über mehr als zwei Dateien", oder sollen kleine Entscheidungen wie ursprünglich gewünscht immer von Sonnet-Subagents gefällt werden? Das kostet je Frage einen Subagenten. — Entscheider: du.
- Soll „groß" neben teuer umkehrbaren Schritten auch billig umkehrbare, aber folgenreiche Fragen umfassen (etwa Architekturrichtung eines Features), und woran wäre das prüfbar? Die Liste mischt schon heute zwei Achsen: wirklich nicht umkehrbar (Mail, Deploy, gelöschte Daten) und per Revert umkehrbar, aber andere betreffend (API, Abhängigkeit). — Entscheider: du.
- Soll evalkit Assertions auf `tool_use` und einen Permission-Host bekommen, damit Subagenten-Nutzung und das Fragen selbst messbar werden? Das wäre eine eigene Spec. — Entscheider: du.
- Gehört ein Hook am teuren Schritt (Push auf geteilten Branch, `git clean`, neue Abhängigkeit) in einen späteren Zyklus, nachdem `check` gezeigt hat, wie oft so etwas ohne Freigabe passiert? Er deckte auch die Kategorien ab, die `check` als ungeprüft meldet. — Entscheider: du, nach der Messung.
- Braucht `docs/big-decisions.md` nach einiger Zeit ein Archiv für alte freigegebene Blöcke, oder reicht eine Datei, solange große Fragen selten bleiben? — Entscheider: du, nach dem ersten Monat Nutzung.

---
Quellen: `skills/feature-spec/SKILL.md`, `references/spec-schema.md` und `references/decisions-guide.md`, `skills/work-plan/SKILL.md`, `skills/setup-user/assets/rules/communication.md`, `skills/sql-schema-architect` (`migration_gate.py`), `skills/debug-ledger/assets/hooks/check-ledger.json`, `specs/Spec 00 – skill-foundation.md` (§1, §2, §3, §4, §5), `specs/Spec 25 – skill-dir.md`, `specs/Spec 27 – subagent-dev-checkpoints.md`, `docs/artifact-header.md`, `skills/skill-forge/scripts/lint_skill.py`, `evalkit/` (Assertion-Typen in `schema.py`, Judge liest nur Text), Claude-Code-Doku (Hooks: `AskUserQuestion`, Permission-Host; Headless; Subagenten; Umgebungsvariablen: `CLAUDE_CODE_SESSION_ID`), Messungen mit `claude -p` am 2026-11-02, zwei Opus-Reviews dieses Entwurfs am 2026-11-02 · Übersprungene Quellen: `docs/decisions.md` (existiert in diesem Repo nicht)
