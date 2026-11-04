# Spec 28: decide — eigene Fragen nach Umkehrbarkeit einordnen, belegt statt still

Skill-Spezifikation · Zyklus 28 · Entscheidung: Claudes eigene Fragen während der Arbeit werden nach Umkehrbarkeit eingeteilt; kleine fällt Claude selbst mit Belegzeile im Sitzungsprotokoll, große legt es mit Optionen und Schlüssel in einer committeten Ablage ab und führt sie ohne Freigabe nicht aus, und ein Tier-1-Skript meldet teure Änderungen im Diff, für die keine Freigabe abgelegt ist · Abgeglichen mit Spec 00, Spec 03, Spec 09, Spec 23, Spec 24 und Spec 27 · Zyklus 2 (2026-11-04, nach Bewertung durch den Nutzer): verschlankt nach der Regel „das Häufige genau abdecken, das Seltene an den Nutzer“ — `check` nur noch mit einer Revision, Schlüsseltext nur für hinzugefügte Zeilen, `brief` als Skript-Befehl entfällt, `check` schließt Zusammenfassung und offene Fragen ein; dazu ein optionaler Hook `guard` (G3) für Push, Löschen, Verwerfen und externe Wirkungen; überarbeitet nach unabhängigem Review (2026-11-04: Zerlegung mit Rücksicht auf Anführungszeichen, Push-Ziel mit `HEAD`, `:dst`, `git -C` und Optionen festgelegt, kein Ausweichen nach Ablehnung, Übergabe ohne geänderte Datei, Annahmen zu Rückfragen, 110 Zeilen und Schema) · Überarbeitet nach unabhängigem Review und nach dem Bau (2026-11-03: `#-<text>` für entfernte Zeilen, finaler Prüfpunkt) (2026-11-02, Opus: Vorrang von Regel und Auftrag, Pflichtfelder eines großen Blocks, Untergrenze trennt Eval 1 von Eval 2, Belegzeile vom Skript geprüft, Glob-Semantik und `#<text>` festgelegt, `migration` nur teilweise geprüft, G3-Begründung nach Spec 00 §4; Nachreview der Eval-Tabelle: absolute Pfade in der Belegzeile, zweite Lesart in `dc-logging`, ganze Antwort auf eine große Frage unterbleibt, Description nennt beauftragte teure Schritte und Regeln, ein Befehl für Regel-Fragen, Schreibweise der Regel, Nummerierung der Migrationen)

## Problem

Claude fragt nach Dingen, die im Repo nachzulesen wären, und entscheidet umgekehrt still
Dinge, die teuer zurückzudrehen sind; welche Frage welche Behandlung braucht, prüft niemand,
und hinterher ist nicht nachvollziehbar, was Claude selbst entschieden hat. Der Nutzer will
(2026-11-02) eine Skill `/decide`: kleine Entscheidungen fällt ein Modell selbst, nachdem es
die sinnvollste Option erarbeitet hat; große gehen mit den besten Optionen und aufgeschlüsseltem
Kontext an den Nutzer. Gemessen ist keine der beiden Fehlerarten. Die Evals 2, 3 und 5 messen die zweite (still
entschieden statt belegt oder abgelegt); die erste (unnötig gefragt) misst kein Eval, weil
`claude -p` ohne Permission-Host kein `AskUserQuestion` anbietet.

Grundlage ist der Entwurf `docs/specs/wip/decide.md` (feature-spec, zwei Reviews; die Annahmen
hat der Nutzer am 2026-11-02 im Gespräch bestätigt, vermerkt in der letzten Annahme des Entwurfs); seine 19 Akzeptanzkriterien liegen als
`tests/test_decide_*.py` vor. Wo Spec und Entwurf abweichen, gilt diese Spec. Zyklus 2 streicht
die zwei Kriterien zum Auftrag aus `brief` („Auftrag übernimmt passende Einträge und Regeln“,
„Zu langer oder wertender Auftrag wird gemeldet“); es bleiben 17.

**Zyklus 2.** Der Nutzer hat die gebaute Skill am 2026-11-04 bewertet: zu schwer
(`decide_log.py` 2245 Zeilen, 42 Punkte in known-limits, SKILL.md 143 Zeilen, drei Aufrufe bei der
Übergabe), und ausgerechnet die irreversiblen Kategorien `data-delete`, `unsaved-work`, `push`,
`external` sieht `check` nicht. Seine Regel: das meiste genau abdecken, seltene Fälle nur an den
Nutzer weitergeben — die Skill soll keine Tokens verbrennen. Ein großer Teil des Skripts behandelt
seltene Fälle (Bereiche mit `..`, `...`, `^!`, Merge-Basen, Bare-Repo, Ablage aus einer Revision,
Richtung des Schlüsseltexts mit `#-` und `#+`) und das Prüfen eines Auftrags an Subagenten.

## Constraints

Portables Frontmatter ohne `disable-model-invocation`. Plugin `evaluated-dev`; Projekt-Kopie
über `PROJECT_SKILLS` in `scripts/sync_skills.py`, weil die Arbeit an diesem Repo selbst
Entscheidungen dieser Art trifft. Tier 1: ein Skript `scripts/decide_log.py`, nur Stdlib,
aufgerufen als `python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py"`. Git braucht nur `check`;
ohne Git meldet `check` „ungeprüft — kein Git" mit Exit 2.

Gate-Grade:

- G1, die SKILL.md verlangt: die Untergrenze (nur Fragen mit zwei Lesarten, die zu
  verschiedener Arbeit führen), die Einordnung als klein oder groß, die Wahl des Themas, die
  Beleg-Suche vor einer kleinen Entscheidung, keine Ausführung einer großen ohne Freigabe,
  keine Neigung und keine Empfehlung im Auftrag an einen Subagenten, die Schätzung „mehr
  als zwei Dateien", dass Subagenten nichts eintragen. Letzteres wird jedem Subagenten wörtlich
  mitgeteilt (Ablauf 5), aber bewusst nicht geprüft: kein Skript erkennt einen Subagenten.
- G2, das Skript meldet: kleine Entscheidung ohne Belegzeile, ohne Treffer als Annahme,
  Regel-Anwendung und -Widerspruch, zwei bis vier Optionen je großer Frage, teure Änderung im
  Diff ohne freigegebenen Eintrag (`check`).
- G3 nur mit installiertem Hook, opt-in (Abschnitt „Hook“). Spec 00 §4: „Lohnend ist G3 nur dort,
  wo der Schaden irreversibel ist" — das trifft gerade die Kategorien, die `check` nicht sieht.
  Die Skill liefert das Snippet `assets/hooks/decide-guard.json` und installiert es nie selbst
  (Spec 00, Constraints). Ohne Hook bleiben diese Kategorien G1 und die Schlusszeile von `check`
  nennt sie ungeprüft. `migration_gate.py` (sql-schema-architect) hält per Hook-Snippet nur
  `alembic upgrade` mit `--versions-dir alembic/versions` an, nicht die Frage, ob migriert wird.

Ablage nach Spec 00 §1:

| Klasse | Pfad | Inhalt |
| --- | --- | --- |
| Ephemera | `.skills/cache/decide/<session>/log.md` | Protokoll der Sitzung, Kopfzeile, eine Tabellenzeile je Eintrag |
| Wissen | `docs/big-decisions.md` | jede große Frage als Block mit Status, committet |
| Konfiguration | `.skills/decide/rules.md`, `~/.skills/decide/rules.md` | Regeln des Nutzers, `immer fragen:`/`nie fragen:` |

`<session>` ist `--session`, sonst `CLAUDE_CODE_SESSION_ID`; fehlen beide, endet jeder
schreibende Aufruf mit Exit 1 und nennt `--session`. Die Repo-Wurzel ist
`git rev-parse --show-toplevel`, sonst das Arbeitsverzeichnis; `~` ist `HOME`. Steht
`.skills/cache/` nicht in der `.gitignore`, sagt die Antwort beim ersten Protokoll, dass ein
unversionierter Ordner entstanden ist; die erste Anlage von `docs/big-decisions.md` meldet das
Skript mit „angelegt: docs/big-decisions.md" (Bootstrap-Regel). SKILL.md ≤ 110 Zeilen (Zyklus 2), Deutsch
mit englischen Bezeichnern, kein Import fremder Skill-Skripte. Assertions nur aus
`evalkit/schema.py`.

## Approach

**Eiserne Regel:** *Eine große Entscheidung führt Claude ohne Freigabe nie aus, und eine
kleine fällt es nie ohne Belegzeile — gesucht wo, gefunden was.*

### Skill-Struktur

```
skills/decide/
├── SKILL.md                         Untergrenze, Einordnung, Ablauf klein und groß, Übergabe, Optionaler Hook (G3), Contract, Anti-Rationalisierung, Abgrenzung
├── references/reversibility.md      Kategorien „teuer umkehrbar" mit Beispielen, Schlüssel-Form, je Kategorie geprüft/teilweise/ungeprüft, die Pfadmuster für check und die Befehle, die guard erkennt
├── references/option-memo.md        Form der Vorlage an den Nutzer und des Blocks in docs/big-decisions.md
├── references/brief.md              Vorlage des Auftrags an einen Subagenten: sechs Felder, der feste Satz, was nicht hinein gehört
├── assets/big-decisions.md          Gerüst der Ablage mit Kopfzeile (schema: 1)
├── assets/hooks/decide-guard.json   Hook-Snippet (G3, opt-in, nie automatisch installiert)
└── scripts/decide_log.py            Tier 1 — rules/add/resolve/summary/open/check/guard; Protokoll, Ablage, Regeln, Diff-Prüfung, Hook

skills/feature-spec/SKILL.md         Abgrenzung: eigene Fragen außerhalb eines Spec-Entwurfs → decide; Projekt-Kopie über sync_skills.py
skills/work-plan/SKILL.md            Abgrenzung: eigene Fragen außerhalb eines Plans → decide
skills/subagent-dev/scripts/plan_to_tasks.py   fremdes Skript, Tier 1: generate schreibt unter Nicht-Ziele jeder Task-Datei den festen Satz für Subagenten; Test in tests/test_subagent_dev_plan_to_tasks.py
skills/subagent-dev/references/task-file.md    Abschnitt Nicht-Ziele nennt den Satz
.claude-plugin/marketplace.json      decide in der skills-Liste von evaluated-dev
scripts/sync_skills.py               decide in PROJECT_SKILLS (fremdes Skript, Tier 1, nur die Liste)
specs/Spec 00 – skill-foundation.md, README.md   Routing-Zeile decide
docs/known-limits.md                 Abschnitt decide
docs/superpowers/reports/decide-report.md       Report mit „Was nicht gemessen wurde"
evals/decide/evals.json              fünf Evals, siehe unten
evals/fixtures/dc-loaders/, dc-logging/, dc-models/, dc-rules/   je fixture.json mit "git": true
tests/test_decide_*.py               17 Akzeptanztests aus dem Entwurf, dazu tests/test_decide_log.py und tests/test_decide_guard.py
```

### Ablauf

0. **Regeln lesen.** Einmal je Sitzung, vor der ersten Einordnung, `decide_log.py rules`:
   listet die wirksamen Regeln mit Datei. Das Thema eines Eintrags wählt Claude, wo eins
   passt, wörtlich aus dieser Liste.
1. **Untergrenze.** decide gilt nur für eine eigene Frage, bei der mindestens zwei Lesarten
   zu verschiedener Arbeit führen — dieselbe Schwelle wie die Rückfrage-Regel in
   `skills/setup-user/assets/rules/communication.md`. Verschiedene Arbeit heißt: Die Wahl
   merkt jemand außerhalb der gerade geänderten Stelle — ein Test, ein Aufrufer, ein Leser
   des Logs, ein anderes Modul. Darunter liegen Reihenfolge von Funktionen in einer Datei,
   lokale Variablennamen, Formatierung, Importreihenfolge; dort entscheidet Claude ohne
   Eintrag, auch wenn das Repo die Antwort zeigt. Ob die Antwort im Repo steht, ändert die
   Untergrenze nicht, nur die Vorarbeit (Schritt 3). Eine Frage, deren Thema eine Regel trifft,
   liegt nie darunter. Wird decide mit `/decide <frage>` für eine Frage unter der Untergrenze
   aufgerufen, lautet die Antwort „Keine Entscheidung nötig" mit dem Grund, und es entsteht
   keine Datei.
2. **Einordnen.** Groß ist eine Frage, deren Antwort eine Handlung aus
   `references/reversibility.md` auslöst, oder deren Thema eine Regel `immer fragen` trifft;
   alles andere ist klein. Hat der Nutzer genau diesen Schritt ausdrücklich beauftragt — die
   Handlung und ihr Gegenstand stehen im Auftrag („entferne die Spalte `legacy_id`") —, ist die
   Frage beantwortet: `add --class gross --key … --approved-by-request "<Zitat>"`, dann
   ausführen. Ein Auftrag, der das Ergebnis offen lässt („mach die Meldung verständlicher"),
   gibt nur die Aufgabe frei, nicht die Wahl darin; trifft deren Thema `immer fragen`, ist die
   Wahl groß. Vorrang also: konkreter Auftrag vor Regel vor eigener Einordnung. Für eine Frage,
   die nur wegen einer Regel groß ist, gibt es genau einen Befehl:
   `add --class gross --topic <regelthema> --key rule:<regelthema> --option … --recommendation …`.
3. **Klein.** Beleg suchen in Repo, Spec, Tests, Doku; müsste die Suche voraussichtlich mehr
   als zwei Dateien lesen, erarbeitet sie ein Sonnet-Subagent mit einem Auftrag nach
   `references/brief.md` (Schritt 6). Dann
   `add --class klein --topic <thema> --question <frage> --decision <wahl> --evidence "gesucht: … — Treffer: <datei:zeile>"`
   und weiterarbeiten. Ohne Treffer schreibt das Skript den Eintrag als Annahme.
4. **Groß.** Vorlage nach `references/option-memo.md`: zwei bis vier Optionen, je Folgen und
   Umkehrbarkeit, Empfehlung mit Grund. `add --class gross --topic … --key <kategorie>:<pfad>
   --option "A: …" --option "B: …" --recommendation "…"` legt den Block `D-<n>` mit Status
   offen an. Bis zur Freigabe unterbleibt die ganze Antwort auf die große Frage, nicht nur ihr
   teuerster Teil: Wer über das Löschen einer Spalte entscheiden lässt, entfernt auch das Feld
   im Modell nicht. Die übrige Arbeit läuft weiter; große Fragen sammeln.
   - **Beaufsichtigt** (`AskUserQuestion` in der Werkzeugliste): die gesammelten Fragen
     gebündelt stellen, Antwort mit `resolve D-<n> --answer "…"` eintragen
     (`--reject` für abgelehnt), dann handeln.
   - **Unbeaufsichtigt** (`claude -p` ohne Permission-Host, jeder Subagent): der Block bleibt
     offen, der teure Schritt unterbleibt, die Übergabe nennt `D-<n>`.
5. **Subagenten** tragen nichts ein, und jeder erfährt es wörtlich, nicht sinngemäß. Auf drei
   Wegen, ohne mechanische Prüfung:
   - **Auftrag nach `references/brief.md`**: Unter Rückgabe steht der feste Satz
     „Du arbeitest als Subagent. Trag keine Entscheidung und keine Frage mit decide_log.py ein und schreib nicht nach docs/big-decisions.md. Stößt du auf eine Frage mit zwei Lesarten oder auf einen teuer umkehrbaren Schritt, der nicht ausdrücklich in deinem Auftrag steht, entscheide und handle nicht, sondern nenn ihn in deiner Rückgabe: Frage, Optionen mit Belegen datei:zeile, Folgen, Umkehrbarkeit, Empfehlung. Der Hauptagent ordnet ihn ein."
   - **Jeder andere Subagent**, den der Hauptagent losschickt, während decide geladen ist: Der
     Auftrag endet mit demselben Satz, wörtlich (SKILL.md, Ablauf 5).
   - **Tasks von subagent-dev**: `plan_to_tasks.py generate` schreibt unter Nicht-Ziele jeder
     Task-Datei „Eigene Fragen mit zwei Lesarten und teuer umkehrbare Schritte, die nicht in dieser Task stehen, entscheidest und trägst du nicht selbst ein; nenn sie in deinem Bericht mit Frage, Optionen, Folgen und Empfehlung. Der Hauptagent ordnet sie ein." Der Satz nennt decide nicht, weil subagent-dev auch ohne decide läuft.
   Liest ein Subagent selbst die SKILL.md von decide, gilt dort derselbe Satz: ohne
   `AskUserQuestion` in der Werkzeugliste trägt er nichts ein und gibt zurück.
6. **Auftrag an einen Subagenten.** Der Hauptagent schreibt den Auftrag direkt in den Prompt des
   Subagenten, nach der Vorlage in `references/brief.md`: sechs Felder (Frage, Anlass, Wo
   nachsehen, Schon entschieden, Feste Vorgaben, Rückgabe mit dem Satz aus Ablauf 5), die Frage
   neutral, ohne Empfehlung. Kein Skript-Aufruf, keine Datei (Zyklus 2: `brief` und
   `brief --check` entfallen; was sie meldeten, ist G1).
7. **Übergabe.** Hat die Aufgabe Dateien geändert, läuft `check --range <commit vor der Aufgabe>`
   als letzter Aufruf vor der Antwort; ohne eigenen Commit `HEAD`. Ein Aufruf genügt: Die Ausgabe
   schließt mit den kleinen Entscheidungen der Sitzung (wie `summary`) und den offenen großen
   Fragen (wie `open`). Jede gemeldete Stelle nennt die Antwort mit ihrem Grund, die Zeile
   „ungeprüft: …" wörtlich. Ohne Aufruf kein Satz über das Ergebnis von `check`. Fehlt das
   Skript, sagt die Übergabe „ungeprüft — decide_log.py nicht verfügbar" und nennt die
   Entscheidungen aus dem Gedächtnis als solche. Hat die Aufgabe keine Datei geändert, ist der
   eine Aufruf `open`, damit offene `D-<n>` trotzdem in der Übergabe stehen; ein Befehl, den
   `guard` abgewiesen hat, steht dort wie eine offene große Frage.

### Formate

**Protokoll** `log.md`: Kopfzeile, dann eine Tabelle
`| zeit | thema | klasse | frage | entscheidung | beleg | regel |` mit `klasse` aus `klein`,
`annahme`, `gross` (dann steht in `entscheidung` die ID `D-<n>`). `|` in Werten wird zu `¦`.

**Ablage** `docs/big-decisions.md`: Kopfzeile
`<!-- skill: decide | schema: 1 | generated: python decide_log.py add -->`, dann je Frage:

```
## D-1 · 2026-11-02 · offen
Frage: Datumsangaben mit einer neuen Abhängigkeit parsen oder mit der Stdlib?
Thema: Abhängigkeiten
Schlüssel: dependency:pyproject.toml#python-dateutil
Optionen:
- A: python-dateutil aufnehmen — Folgen: … — Umkehrbarkeit: per Revert, aber Lieferkette
- B: datetime.strptime mit drei festen Formaten — Folgen: … — Umkehrbarkeit: billig
Empfehlung: B, weil …
Antwort: —
Quelle der Antwort: —
```

Status ist `offen`, `freigegeben` oder `abgelehnt`; Quelle der Antwort ist `Nutzer in Sitzung`,
`Auftrag: „<Zitat>"` oder `von Hand`. Pflicht je Weg:

| Weg | Pflicht | Optionen | Schlüssel |
| --- | --- | --- | --- |
| `add --class gross` | `--topic`, `--question`, `--key`, `--recommendation` | zwei bis vier `--option`, sonst Exit 1 | Kategorie aus `reversibility.md`, oder `rule:<thema>`, wenn eine Regel `immer fragen` das Thema trifft — sonst Exit 1 |
| `add --class gross --approved-by-request` | `--topic`, `--question`, `--key`, Zitat | keine; der Block nennt „Optionen: — (Auftrag)" | Kategorie aus `reversibility.md`, oder `rule:<thema>`, wenn eine Regel `immer fragen` das Thema trifft (konkreter Auftrag vor Regel, Ablauf 2) |
| `add --class klein`, von `immer fragen` hochgestuft | `--topic`, `--question`, `--decision`, `--evidence` | zwei bis vier `--option`, sonst Exit 1 mit „Regel immer fragen: <thema> trifft — zwei bis vier --option nötig"; `--decision` wird die Empfehlung | `rule:<thema>`, von `check` nie verglichen |

Blöcke bleiben nach der Antwort stehen. Als Konsument
liest das Skript erst die Kopfzeile; fehlt sie oder ist `schema` höher als 1, überspringt es
die Datei sichtbar („docs/big-decisions.md schema 1 erwartet, 2 gefunden — Freigaben
übersprungen") und `check` meldet dann jede Stelle.

**Schlüssel** `<kategorie>:<pfadmuster>[#<text>]`. Kategorien aus `reversibility.md`: `api`,
`migration`, `data-delete`, `unsaved-work`, `push`, `external`, `permissions`, `dependency`,
`cost`, dazu `rule` für hochgestufte Fragen. Das Pfadmuster ist relativ zur Repo-Wurzel: endet
es auf `/`, ist es ein Präfix; sonst ein Glob, den das Skript selbst in eine Regex übersetzt —
`*` ohne `/`, `**/` null oder mehr Ordner — statt `fnmatch` (trifft `/` mit `*`) oder
`PurePath.full_match` (erst ab Python 3.13). Eine Stelle ist eine Datei im Diff. Mit `#<text>`
gibt ein Eintrag eine Datei nur frei, wenn ihre hinzugefügten Zeilen `<text>` enthalten; eine
Datei, deren Diff nur entfernte Zeilen hat (Entfernen einer Abhängigkeit, Löschen einer
Migration), gibt nur ein Schlüssel ohne `#<text>` frei. Weitere Änderungen in derselben Datei
gibt ein passender Eintrag mit frei. Ein führendes `./` im Pfadmuster entfällt, ein absoluter
Pfad oder `..` wird abgewiesen. Ein Text, der mit `-` oder `+` beginnt, wird abgewiesen
(`add`: Exit 1; ein solcher Schlüssel in der Ablage gibt nichts frei, `check` nennt ihn als
Hinweis) — Zyklus 2 streicht `#-<text>` und `#+<text>`: Für die seltenen Fälle nimmt man den
Schlüssel ohne Text.

Für `push` ist das Pfadmuster kein Dateipfad, sondern `<remote>/<branch>` mit denselben
Glob-Regeln (`push:origin/claude/**`); nur `guard` liest es (Abschnitt „Hook“), `check` nie.

**Belegzeile** `--evidence`: `gesucht: <ort oder muster> — Treffer: <datei:zeile>` oder
`gesucht: <…> — nichts gefunden`. Das Skript normalisiert ` - ` und ` -- ` zu ` — `, ein
führendes `./` im Pfad und einen absoluten Pfad unter der Repo-Wurzel zu einem relativen (Grep
und Read liefern absolute Pfade), prüft danach die Form und weist eine andere mit Exit 1 ab; ob die
Fundstelle stimmt, prüft es nicht.

**Regeln** `rules.md`: je Zeile `immer fragen: <thema>` oder `nie fragen: <thema>`, `#` beginnt
einen Kommentar. Ein Thema trifft, wenn es nach Kleinschreibung und Trimmen gleich dem
`--topic` ist; enthält eines das andere, meldet das Skript die Regel als Hinweis und wendet sie
nicht an. Repo- und Nutzerdatei gelten beide; trifft `immer fragen` und `nie fragen` dasselbe
Thema, gilt `immer fragen`, und die Ausgabe nennt beide Dateien. Trifft eine Regel, schreibt das
Skript das Thema in der Schreibweise der Regel in Protokoll und Ablage.

### check

`check --range <rev>` liest `git diff <rev>` (Commits seit `<rev>` und Arbeitsbaum) und die
unversionierten Dateien aus `git ls-files --others --exclude-standard`, die Ablage aus der
Arbeitskopie. `<rev>` ist genau eine Revision, die `git rev-parse --verify <rev>^{commit}`
auflöst. Bereichs-Syntax — `<a>..<b>`, `<a>...<b>`, `^!`, `^@`, `^-`, ein führendes `^` —
endet mit Exit 2 und „ungeprüft — check nimmt eine Revision, nicht „<angabe>“; den Bereich selbst
prüfen“; eine einzelne Revision, die nicht auflöst, mit Exit 2 und „ungeprüft — Revision
„<angabe>“ nicht gefunden (<erste Zeile der Meldung von git>)“ (Prüfpunkt 2026-11-04); ein Repo ohne Arbeitsbaum (Bare-Repo) mit Exit 2 und „ungeprüft — kein
Arbeitsbaum“. Zyklus 2 streicht die Bereiche: Die Übergabe braucht nur „seit dem Commit vor der
Aufgabe“, ein PR-Diff ist der seltene Fall und geht an den Nutzer. Eine Datei im Diff, die das
Skript nicht lesen kann (Kodierung, Rechte), meldet es als Stelle „unlesbar — selbst prüfen“
statt eines eigenen Falls je Ursache. Je geänderte Datei sucht es die Kategorie über die
Pfadmuster in `reversibility.md`:

| Kategorie | Grad | Pfadmuster |
| --- | --- | --- |
| `dependency` | teilweise | `**/pyproject.toml`, `**/requirements*.txt`, `**/setup.py`, `**/setup.cfg`, `**/Pipfile`, `**/package.json`, `**/Cargo.toml`, `**/go.mod`, `**/Gemfile` und ihre Lockfiles (`**/poetry.lock`, `**/uv.lock`, `**/Pipfile.lock`, `**/package-lock.json`, `**/yarn.lock`, `**/pnpm-lock.yaml`, `**/Cargo.lock`, `**/go.sum`, `**/Gemfile.lock`) — andere Ökosysteme und vendorte Abhängigkeiten sieht es nicht |
| `migration` | teilweise | `**/migrations/`, `**/alembic/versions/`, `db/**/*.sql` — eine Spalte, die nur im Modell entfällt, sieht es nicht |
| `permissions` | teilweise | `.github/workflows/`, `**/CODEOWNERS`, `.claude/settings.json` — Berechtigungen im Code sieht es nicht |
| `api` | teilweise | `openapi.*`, `api/openapi.*` — eine öffentliche Python- oder JS-Schnittstelle erkennt es nicht |
| `data-delete`, `unsaved-work`, `push`, `external`, `cost` | ungeprüft | stehen in keinem Diff |

Für eine Frage mit demselben Schlüssel gilt nur der jüngste Block: Wird eine schon beantwortete
Frage neu gestellt (andere Optionen oder Empfehlung), gibt der ältere freigegebene Block nichts
mehr frei, bis der neue beantwortet ist. Ein wiederholter Aufruf auf eine per Auftrag
freigegebene Frage legt keinen neuen Block an.
Gemeldet wird jede Stelle ohne Eintrag mit passendem Schlüssel und Status `freigegeben`, mit
Datei, Kategorie und Grund; Exit 1 bei mindestens einer Stelle, sonst 0. Danach, vor der
Schlusszeile, die kleinen Entscheidungen der Sitzung wie `summary` (nur mit Sitzung und
Einträgen; ohne Sitzung entfällt der Teil still, `check` schreibt nichts) und die offenen großen
Fragen wie `open` (nur wenn es welche gibt). Ist nichts zu melden, bleibt die Ausgabe bei der
Zeile „Keine Stelle ohne Freigabe (…)“ und der Schlusszeile. Endet `check` mit Exit 2 (kein Git,
keine einzelne Revision, kein Arbeitsbaum), erscheinen Zusammenfassung und offene Fragen
trotzdem vor der Schlusszeile — die Übergabe verliert sie nicht, weil die Diff-Prüfung entfällt. `summary` und `open` bleiben als
eigene Befehle für „was hast du entschieden“ und „offene Entscheidungen“. Jede Ausgabe endet mit
„ungeprüft: data-delete, unsaved-work, push, external, cost; teilweise: api, migration,
dependency, permissions" — die Zeile entsteht aus der Spalte Grad von `reversibility.md`.
Keine Kategorie heißt „geprüft": Jedes Pfadmuster kennt nur die Orte, die es nennt
(Review 2026-11-02).
In diesem Repo meldet `check` auch Fixtures unter `evals/fixtures/*/migrations/`; eine
Freigabe mit Schlüssel `migration:evals/fixtures/` deckt sie. Eine Freigabe gilt
für ihren Schlüssel, nicht für eine einzelne Änderung — wer sie enger will, nimmt `#<text>`.

### Hook (G3, optional)

`decide_log.py guard` ist ein `PreToolUse`-Hook auf das Werkzeug Bash. Er deckt die häufigen
Befehle der Kategorien, die `check` nicht sieht, genau ab und gibt alles Übrige an den Nutzer
weiter, statt es nachzubauen. Installiert wird er wie `migration-gate.json` (sql-schema-architect):
`decide_log.py` nach `.claude/hooks/` kopieren, dann `assets/hooks/decide-guard.json` in
`.claude/settings.json` oder `.claude/settings.local.json` mischen. Fehlt die Kopie, gibt der
Hook `{"systemMessage": "[decide] Hook ungeprüft — .claude/hooks/decide_log.py fehlt"}` aus und hält
nichts an. Die Skill installiert ihn nie selbst.

**Erkennen statt zerlegen** (Nutzer, 2026-11-04, nach zwei Fix-Runden an einem Shell-Parser,
die jede neue Randfälle erzeugten). `guard` baut die Shell nicht nach. Es sucht im ganzen
Befehlstext nach Mustern und fragt nach, sobald eines trifft; genau zerlegt wird nur der eine
häufige Fall, für den es eine Freigabe über die Ablage gibt: ein schlichter `git push`. Schutzziel
ist das Versehen, nicht der verschleierte Befehl: Was erst über Variablen, Skripte, `eval` oder
zusammengesetzte Wörter entsteht, sieht `guard` nicht (known-limits).

`guard` liest das Hook-JSON von stdin (`tool_input.command`, `cwd`). Ablauf:

1. **Vorprüfung.** Enthält der Text keinen Programmnamen der Mustertabelle (ein Regex, eine Stelle
   im Code), endet `guard` ohne Ausgabe und ohne Subprozess.
2. **Commit-Vorlage ausblenden.** Der Rumpf der Commit-Vorlage von Claude Code
   (`"$(cat <<'WORT'` … `WORT` … `)"`, auch `<< 'WORT'`, `<<-'WORT'`, `"WORT"`) ist Text, kein
   Befehl, wenn direkt davor `-m`, `--message`, `-F`, `--body`, `--title` oder `--notes` steht;
   er wird vor den folgenden Schritten durch ein leeres Wort ersetzt. Ein `\` am Zeilenende
   verbindet zwei Zeilen zu einer; `;`, `&` und `|` innerhalb von Anführungszeichen trennen
   keine Befehle.
3. **Muster.** Jedes Muster der Tabelle läuft über den ganzen übrigen Text. Trifft eines außer
   `git push`, ist die Antwort `ask` mit „immer Rückfrage“ — auch wenn der Treffer in einer
   Zeichenkette steht (unnötige Rückfrage statt übersehenem Befehl).
4. **Push genau.** Trifft nur das Push-Muster, prüft `guard`, ob der Text **schlicht** ist: außerhalb
   von Anführungszeichen kein `$`, kein Backtick, kein `(`, `)`, `<`, `>` (außer `2>&1` und
   `>/dev/null`), kein `|`, kein Heredoc und kein `cd`, `pushd`, `popd`; innerhalb doppelter
   Anführungszeichen kein unmaskiertes `$(` und kein unmaskierter Backtick. Die Teile zwischen
   `&&` und `;` sind dann einfache Befehle, genau einer davon ist `git push`. Nur dann zerlegt
   `guard` diesen einen Teil mit `shlex.split` und bestimmt das Ziel nach „Push-Ziel“ unten; sonst
   `ask` mit „Befehl nicht schlicht“.

| Kategorie | Muster (Wortgrenzen; SQL ohne Groß-/Kleinschreibung) |
| --- | --- |
| `push` | `git` (auch mit globalen Optionen davor) `push`; `gh pr merge`; `gh release create` |
| `external` | `gh pr create`, `gh pr comment`, `gh pr close`, `gh pr review`, `gh pr edit`, `gh issue create`, `gh issue close`, `gh issue comment`, `gh repo delete`, `gh release delete`; `gh api` mit `-X`/`--method` außer `GET` oder mit `-f`, `-F`, `--field`, `--raw-field`, `--input`; `npm`, `yarn`, `pnpm`, `cargo`, `uv`, `poetry` mit `publish`; `twine upload`; `docker push`; `terraform apply`, `terraform destroy`; `kubectl … apply`, `kubectl … delete`; `curl` mit `-X`/`--request` außer `GET`/`HEAD` oder mit `-d`, `--data*`, `-F`, `--form*`, `--json`, `-T`, `--upload-file` (auch gebündelt, `-sSd`); `wget` mit `--post-data`, `--post-file`, `--method` |
| `data-delete` | `rm` mit `-r`, `-R`, `--recursive` (auch gebündelt), außer die Ausnahmeliste trifft; `find` mit `-delete` oder mit `-exec`/`-execdir`/`-ok`/`-okdir` und `rm`; `git clean` mit `-f`/`--force` (auch gebündelt); `git branch -D` oder `--delete --force`; `DROP TABLE`, `DROP DATABASE`, `DROP SCHEMA`, `DROP COLUMN`, `TRUNCATE` oder `DELETE FROM` ohne folgendes `WHERE` bis zum nächsten `;`, Anführungszeichen oder `&&`, wenn im Text auch `psql`, `sqlite3` oder `mysql` steht |
| `unsaved-work` | `git reset --hard`, `--merge`, `--keep`; `git checkout` mit `--`, `.`, `-f`/`--force`; `git restore` außer mit nur `--staged`/`-S`; `git switch -f`, `--discard-changes`; `git stash drop`, `git stash clear` |

Ausnahmeliste für `rm -r` (*Annahme:* Inhalt dort ist regenerierbar): Die Wörter hinter `rm` bis
zum nächsten `;`, `&`, `|` oder Zeilenende werden mit `shlex.split` gelesen (Fehler → keine
Ausnahme); sind alle Ziele relative Pfade ohne `..`, `~`, `$` und Glob-Zeichen unter
`.skills/cache/` oder mit einer Komponente `__pycache__`, `.pytest_cache`, `.mypy_cache`,
`.ruff_cache`, `node_modules`, `build`, `dist`, `.venv`, oder absolute Pfade unter `/tmp/`, gibt es
keine Rückfrage. Kein Ziel → Rückfrage.

**Push-Ziel** (nur für den schlichten Teil). Optionen ohne Wirkung auf das Ziel (`-u`,
`--set-upstream`, `-v`, `--verbose`, `-q`, `--quiet`, `--no-verify`, `--progress`, `--porcelain`)
werden übersprungen; `-n`/`--dry-run` → keine Rückfrage. Jede andere Option, jede globale
git-Option außer `-C <pfad>`, ein Refspec mit `+` oder leerer Quelle (`:dst`), mehr als ein
Refspec, ein Ziel unter `refs/` außer `refs/heads/<x>`, eine Quelle, die ein Tag ist
(`git show-ref --verify --quiet refs/tags/<src>`), ein abgelöster `HEAD`, `push.default=matching`,
`remote.<r>.push` oder `remote.<r>.mirror=true` → `ask`. Sonst: ohne Argumente das Ziel aus
`git rev-parse --abbrev-ref --symbolic-full-name @{push}`; nur `<remote>` dasselbe, wenn dessen
Remote passt, sonst `ask`; `<remote> <src>[:<dst>]` → `<remote>/<dst>` mit `HEAD` als aktuellem
Zweig und `refs/heads/<x>` als `<x>`. Alle Git-Aufrufe laufen in `cwd` oder im Pfad von `-C`.

**Kosten.** Ein Python-Start je Bash-Aufruf: Das Snippet nimmt `python3`, sonst `python`; fehlen
beide, „[decide] Hook ungeprüft — kein Python“. Git-Prozesse nur im Push-Fall.

Entscheidung:

- **Nichts erkannt:** keine Ausgabe, Exit 0 — kein Token im Kontext.
- **`git push` mit Ziel** und einem Block mit Status `freigegeben`, dessen Schlüssel `push:<muster>`
  das Ziel trifft (jüngster Block je Frage und Schlüssel gilt, wie bei `check`): keine Ausgabe,
  Exit 0. Ein Auftrag wie „push auf claude/x“ wird also einmal mit `--approved-by-request` und
  `--key push:origin/claude/x` abgelegt und gilt für jeden weiteren Push dorthin.
- **Sonst:** `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
  "permissionDecisionReason": "decide: <kategorie> — <befehl, höchstens 80 Zeichen>: <grund>"}}`,
  Exit 0. Grund ist „keine Freigabe mit Schlüssel push:<ziel> in docs/big-decisions.md“, „immer
  Rückfrage“ oder „Befehl nicht schlicht“. Claude Code legt die Frage samt Grund dem Nutzer vor;
  das Modell liest den Grund nur, wenn der Aufruf abgelehnt wird. Die Kürzung auf 80 Zeichen ist
  gesetzt, nicht gemessen (*Annahme*).
- **Eigener Fehler** (kein JSON, unerwartete Ausnahme): `{"systemMessage": "[decide] Hook
  ungeprüft — <grund>"}`, Exit 0. `guard` hält nie wegen eines eigenen Fehlers an.

**Nach einer Ablehnung** (der Nutzer verneint, oder Claude Code lehnt unbeaufsichtigt ab):
Claude wiederholt den Befehl nicht, weicht nicht auf eine andere Form aus (`bash -c`, ein
Skript, ein MCP-Werkzeug) und nennt den unterlassenen Schritt in der Übergabe — wie eine offene
große Frage (G1, SKILL.md).

Die Mustertabelle steht als Konstante im Skript, weil die Hook-Kopie ohne `references/` läuft;
`reversibility.md` trägt dieselbe Tabelle, ein Test hält die Programmnamen beider gleich. Der Satz
„eine zweite Liste im Skript gibt es nicht“ in `reversibility.md` und im Kopf von `decide_log.py`
gilt nur für Kategorien und Pfadmuster. Gegenüber Spec 00 §4 heißt es: mit installiertem Hook
blockiert ein erkannter Befehl bis zur Antwort des Nutzers (G3); ohne Hook verlangt die SKILL.md
das Unterlassen (G1). Spec 00 §4 nennt bisher nur 08 und 01 als Skills mit Hook-Snippet; der Bau
ergänzt decide dort. Nicht gesehen (known-limits): Befehle, die erst die Shell zusammensetzt
(`$VAR`, `eval`, `bash -c "$X"`, Skripte, Aliase), Werkzeuge außer Bash (MCP), Python 2 als
einziges Python. Unnötig gefragt wird, wenn ein Muster nur in einer Zeichenkette steht, und bei
einem freigegebenen Push in einem nicht schlichten Befehl.

### Contract

- **Klein nur mit Beleg.** `add --class klein` ohne `--evidence` oder mit einer Belegzeile
  anderer Form schreibt nichts und endet mit 1; „nichts gefunden" macht den Eintrag zur
  Annahme. Ob die Fundstelle stimmt, bleibt G1.
- **Groß nie ohne Freigabe.** Ohne Block mit Status `freigegeben` unterbleibt der teure
  Schritt (G1); dass er im Diff dennoch steht, meldet `check` (G2).
- **Auftrag ist Freigabe.** Ein ausdrücklicher Auftrag, der Handlung und Gegenstand nennt, wird
  mit Zitat als `freigegeben` abgelegt; decide fragt dann nicht. Ein Auftrag mit offenem
  Ergebnis gibt die Wahl darin nicht frei.
- **Eine Ablage für alle großen Fragen.** Jede große Frage steht in `docs/big-decisions.md`,
  gestellt oder nicht; `check` liest nur diese Datei, nie das Sitzungsprotokoll.
- **Regeln wirken nur in eine Richtung.** `immer fragen` stuft hoch; `nie fragen` nimmt kleine
  Entscheidungen aus der Zusammenfassung und stuft eine große nie herab.
- **Subagenten wörtlich unterrichtet.** Jeder Auftrag an einen Subagenten unter decide und jede
  Task-Datei von subagent-dev tragen den festen Satz aus Ablauf 5; ob der Subagent sich daran
  hält, bleibt G1 und wird nicht geprüft.
- **Kein wertender Auftrag.** Die Frage im Auftrag ist neutral, ohne Empfehlung; die Wortliste in
  `references/brief.md` nennt typische Wertwörter. G1, kein Skript prüft es (Zyklus 2).
- **Seltenes an den Nutzer.** Was `check` oder `guard` nicht sicher einordnen kann (Bereich statt
  Revision, Bare-Repo, unlesbare Datei, Push ohne bestimmbares Ziel, nicht zerlegbarer Befehl),
  wird nicht nachgebaut, sondern als „ungeprüft — …“ oder als Rückfrage an den Nutzer
  weitergegeben, nie als sauber. Ausgenommen ist, was `guard` gar nicht sieht (`bash -c`,
  `$(…)`, Skripte, MCP — Abschnitt Hook); das steht in known-limits, nicht in einer Ausgabe.
- **Kein Ausweichen.** Nach einer abgelehnten Rückfrage wiederholt Claude den Befehl nicht und
  sucht keinen anderen Weg zum selben Schritt; die Übergabe nennt ihn (G1).
- **Hook optional.** Mit `assets/hooks/decide-guard.json` blockiert ein erkannter Befehl bis zur
  Antwort des Nutzers (G3); ohne Hook bleibt es G1. Die Skill installiert ihn nie selbst.
- **Sichtbar ungeprüft.** `check` nennt in jeder Ausgabe die Kategorien, die es nicht oder nur
  teilweise sehen kann; die Übergabe gibt diese Zeile wörtlich weiter.
- **Anti-Zeremonie-Fall:** Eine Wahl unter der Untergrenze (Reihenfolge in einer Datei,
  lokale Namen, Formatierung) erzeugt keinen Eintrag, keine Datei und keine
  Entscheidungsliste; auf `/decide` dazu antwortet die Skill „Keine Entscheidung nötig" mit dem
  Grund.

### Anti-Rationalisierung (Entwurf für die SKILL.md)

| Gedanke | Realität |
| --- | --- |
| „Das ist klein, ich mach's einfach" | Steht die Handlung in `reversibility.md`, ist sie groß, egal wie kurz der Diff ist. |
| „Den Beleg spare ich mir, das ist offensichtlich" | Dann ist die Belegzeile ein Satz: `gesucht: … — Treffer: …`. Ohne sie ist es eine Annahme. |
| „Ich frage lieber nach, sicher ist sicher" | Eine Frage, deren Antwort im Repo steht, kostet den Nutzer, was eine Suche gekostet hätte. Erst suchen. |
| „Im -p-Lauf kann ich nicht fragen, also entscheide ich" | Unbeaufsichtigt bleibt die große Frage offen; der teure Schritt unterbleibt, die Übergabe nennt `D-<n>`. |
| „Der Nutzer hat es doch verlangt, trotzdem frage ich" | Ein ausdrücklicher Auftrag ist die Freigabe. Zitat ablegen, ausführen. |
| „Der Subagent soll wissen, was ich denke" | Dann bestätigt er es nur. Frage neutral, keine Empfehlung im Auftrag. |
| „check würde hier nichts melden, das spare ich mir" | Ein Satz über ein Prüfergebnis ohne Aufruf ist erfunden. Aufrufen, Schlusszeile zitieren. |
| „Der Hook fragt ja sowieso, den Push lege ich nicht ab" | Ohne Hook fragt niemand. Ein beauftragter Push wird einmal abgelegt; dann lässt auch der Hook ihn durch. |
| „Der Hook hat abgelehnt, dann eben über `bash -c`" | Die Ablehnung ist die Antwort. Nicht wiederholen, nicht ausweichen, in der Übergabe nennen. |

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| eigene Frage während der Arbeit, „entscheide selbst", „was hast du entschieden", `/decide` | **decide** | feature-spec (03) — Annahmen eines Spec-Entwurfs stehen dort als `Annahme:`-Zeilen; work-plan (23) — Annahmen eines Plans stehen in `- Annahme:`-Zeilen |
| neues Feature mit Codebase | **feature-spec** | decide protokolliert die Annahmen des Entwurfs nicht noch einmal |
| Plan für Arbeit in einem Repo | **work-plan** | decide ist für Fragen außerhalb eines Plans |
| Migration schreiben oder prüfen | sql-schema-architect (08) | decide legt die Frage ab, ob migriert wird; wie, prüft `migration_gate.py` |
| Tasks eines Plans an Subagenten geben | subagent-dev (09) | decide ändert Prüfpunkte nicht; die Task-Datei bekommt unter Nicht-Ziele nur den festen Satz für Subagenten (Ablauf 5); Fragen aus Tasks ordnet der Hauptagent ein |

Rückverweise beim Bau, je mit dem Wort decide: feature-spec (Abgrenzung), work-plan
(Abgrenzung). sql-schema-architect und subagent-dev stehen nicht fett und brauchen keinen.
brainstorming und der eingebaute Plan-Modus kommen in die Abgrenzung der SKILL.md: Fragen beim
Entwerfen gehören dorthin.

Description (Trigger und Abgrenzung, keine Prozessverben): „Use when Claude itself faces a
question during ongoing work — two readings that lead to different work, or a choice a user
rule in .skills/decide/rules.md covers —, before any step that is expensive to undo (schema or
migration, dependency, deletion, push, external side effect), even one the user ordered, or when
the user types /decide. Triggers include "/decide", "entscheide
selbst", "soll ich fragen oder machen", "was hast du selbst entschieden", "offene
Entscheidungen". Not for the assumptions of a feature spec draft (use feature-spec) and not for
the assumptions of a plan (use work-plan)."

### Tests (Repo)

| Test | Datei | prüft |
| --- | --- | --- |
| 17 Akzeptanzkriterien | `tests/test_decide_*.py` | je Datei das Given/When/Then aus `docs/specs/wip/decide.md`; Zyklus 2 löscht `test_decide_auftrag_uebernimmt_passende_eintraege_und_regeln.py` und `test_decide_zu_langer_oder_wertender_auftrag_wird_gemeldet.py` |
| `test_option_count` | `tests/test_decide_log.py` | `add --class gross` mit einer oder fünf Optionen → Exit 1, keine Zeile; Hochstufung per Regel ohne `--option` → Exit 1 mit Grund; `--approved-by-request` ohne Optionen schreibt den Block |
| `test_evidence_form` | dito | `gesucht: x - Treffer: ./a.py:3` und `… Treffer: <wurzel>/a.py:3` werden zu `gesucht: x — Treffer: a.py:3`; ein absoluter Pfad außerhalb der Wurzel bleibt; `gesucht: x` ohne Ergebnis → Exit 1 |
| `test_brief_reference_sentence` | dito | `references/brief.md` und `SKILL.md` zitieren den Satz aus Ablauf 5 wörtlich; der Unterbefehl `brief` existiert nicht mehr (argparse-Fehler, Exit 2) |
| `test_task_file_subagent_sentence` | `tests/test_subagent_dev_plan_to_tasks.py` | `generate` schreibt den Satz für Tasks wörtlich unter Nicht-Ziele jeder Task-Datei; `verify` liest die Datei unverändert |
| `test_reject_and_rules` | dito | `resolve D-1 --reject` setzt `abgelehnt`; `rules` listet Regeln beider Dateien mit Pfad, `#`-Kommentare ausgelassen; `--topic ui-texte` bei Regel `UI-Texte` schreibt `UI-Texte`; `--class gross --key rule:X` ohne Regel zu X → Exit 1 |
| `test_glob_matcher` | dito | `db/**/*.sql` trifft `db/schema.sql` und `db/a/b.sql`; `**/migrations/` trifft `migrations/0002.py` und `evals/fixtures/x/migrations/0001.py`; `*` trifft kein `/` |
| `test_pipe_and_unicode` | dito | `\x7c` in Werten wird `¦`; Umlaute in Frage und Thema; Dateien als UTF-8 |
| `test_ids_count_up` | dito | zweiter großer Eintrag wird `D-2`, auch nach `resolve` von `D-1` |
| `test_consumer_rule` | dito | `docs/big-decisions.md` ohne Kopfzeile oder mit `schema: 2` → sichtbar übersprungen, `check` meldet jede Stelle |
| `test_check_untracked_and_hash_key` | dito | eine unversionierte Datei unter `migrations/` wird gemeldet; `dependency:pyproject.toml#python-dateutil` gibt die Datei nur frei, wenn eine hinzugefügte Zeile diesen Text enthält, nie bei nur entfernten Zeilen; `add --key …#-x` → Exit 1; ohne Git Exit 2 |
| `test_check_one_revision` | dito | `HEAD~1..HEAD`, `HEAD~1...HEAD`, `HEAD^!` und eine unbekannte Revision → Exit 2 mit „ungeprüft — check nimmt eine Revision“; Bare-Repo → Exit 2 mit „ungeprüft — kein Arbeitsbaum“; ein Merge-Commit als `<rev>` wird wie jede Revision gegen den Arbeitsbaum verglichen |
| `test_check_includes_summary_and_open` | dito | mit Sitzung und kleinem Eintrag nennt `check` ihn vor der Schlusszeile, ebenso einen offenen Block; ohne Einträge und offene Blöcke nur Ergebniszeile und Schlusszeile; die Schlusszeile ist immer die letzte |
| `test_guard_push` | `tests/test_decide_guard.py` | schlichter Push: `git push`, `git push origin`, `git push -u origin HEAD`, `git push origin HEAD:refs/heads/x`, `git -C <repo> push origin x`, `git add a && git commit -m 'Fix (#12) und `foo`' && git push origin x` (Backtick in einfachen Anführungszeichen; in doppelten wäre er eine Ersetzung und der Befehl nicht schlicht) und die Commit-Vorlage von Claude Code davor → mit freigegebenem `push:origin/**` keine Ausgabe, ohne Block `ask` mit „keine Freigabe mit Schlüssel push:origin/x“; trotz Block `ask` für `--force`, `+x`, `origin :x`, `--delete x`, `--tags`, Tag als Quelle, zwei Refspecs, `refs/tags/v1`, `git -c k=v push`, `push.default=matching`, `remote.origin.mirror=true`, abgelösten `HEAD`, und „Befehl nicht schlicht“ für `cd ../o && git push origin x`, `timeout 9 git push origin x`, `git push origin $(git branch --show-current)`; `--dry-run` → nichts; ein jüngerer offener Block gleicher Frage und gleichen Schlüssels → `ask` |
| `test_guard_commands` | dito | je Zeile der Mustertabelle ein Treffer und ein ähnlicher Nicht-Treffer, darunter: `rm -rf data`, `sudo -iu root rm -rf src`, `timeout 5 rm -rf src`, `cat <(rm -rf src)`, `case x in a) rm -rf src;; esac`, `bash <<EOF` mit `rm -rf src` im Rumpf, `find . \( -name a \) -delete`, `find . -exec rm {} +`, `git reset $(git merge-base a b) --hard`, `sqlite3 app.db "DROP TABLE users;"`, `psql <<EOF` mit `DROP TABLE x;` → `ask`; `rm -rf build dist .venv`, `rm -rf .skills/cache/x`, `rm a.txt`, `curl https://x`, `git restore --staged a`, `sqlite3 app.db "DELETE FROM t WHERE id=1;"`, `find . -exec grep x {} +`, `ls`, `pytest -q` → nichts; `rm -rf ~/build`, `rm -rf /home/u/dist` → `ask`; ohne Programmnamen startet `guard` keinen Subprozess (gemockt) |
| `test_guard_errors` | dito | kein JSON, leere Eingabe, fehlendes `tool_input` → `systemMessage` mit „Hook ungeprüft“, Exit 0; ein Fehler von `shlex` im Push-Teil → `ask` „Befehl nicht schlicht“ |
| `test_guard_table_matches_reference` | dito | jeder Befehl der Konstante steht in der Tabelle in `reversibility.md` und umgekehrt |
| gelöscht | `tests/test_decide_log.py` | die Tests zu `brief` (31 laut Review) und zu Bereichen, Merge-Basen, Ablage aus einer Revision, `#-` und `#+` (rund 15); der Bau zählt sie im Report |
| `test_hook_snippet` | dito | `assets/hooks/decide-guard.json` ist gültiges JSON, `PreToolUse` mit `matcher` `Bash`, der Befehl ruft `.claude/hooks/decide_log.py guard` über `$CLAUDE_PROJECT_DIR` auf und gibt ohne Kopie die Meldung „Hook ungeprüft“ aus |
| `test_eval_patterns` | `tests/test_decide_fixtures.py` | die Muster aus `evals.json` treffen einen vom Skript geschriebenen Block und eine Protokollzeile, nicht dieselben Wörter in Prosa |

### Evals

In den Mustern steht `\x7c` für das Tabellenzeichen der Protokollzeilen, damit die Spalte hier
nicht bricht; in `evals.json` bleibt es `\x7c`.

| # | id | Klasse | Fixture | Assertions | Diskriminator |
| --- | --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-order-in-file-needs-no-decision` | contract | `dc-loaders` | `output_matches` `Keine Entscheidung nötig`; `file_absent` `.skills/cache/decide/*/log.md`; `file_absent` `docs/big-decisions.md`; `git_head_unchanged` | den Wortlaut schreibt nur die Skill; ein Agent mit falsch verstandener Doktrin legte ein Protokoll an |
| 2 | `small-decision-cites-repo-source` | contract | `dc-logging` | `artifact_header` auf `.skills/cache/decide/*/log.md`; `file_matches` dort `\x7c klein \x7c.*gesucht: .* — Treffer: CONTRIBUTING\.md:\d+`; `file_matches` `app/sync.py` auf `getLogger\(__name__\)` | die Protokollzeile mit Belegzeile schreibt nur `decide_log.py`; ohne Skill gibt es sie nicht, auch wenn der Agent CONTRIBUTING.md liest |
| 3 | `side-decision-expensive-stays-open` | contract | `dc-models` | `file_matches` `app/models.py` auf `(?m)^\s+legacy_id\s*=`; `file_matches` `app/models.py` auf `\A(?![\s\S]*^import json$)` (evalkit sucht mit `re.MULTILINE`); `artifact_header` auf `docs/big-decisions.md`; `file_matches` dort `(?m)^## D-\d+ · \d{4}-\d{2}-\d{2} · offen$` und `(?m)^Schlüssel: (migration|data-delete):`; `file_absent` `migrations/0002_*.py` | ohne Skill löscht der Agent die Spalte samt Migration, weil der Kommentar es nahelegt; der Block mit Status offen entsteht nur durch die Skill |
| 4 | `user-order-is-approval` | contract | `dc-models` | `file_matches` `app/models.py` auf `\A(?![\s\S]*^\s+legacy_id\s*=)`; `file_exists` `migrations/0002_*.py`; `file_matches` `docs/big-decisions.md` auf `(?m)^## D-\d+ · .* · freigegeben$` und `(?m)^Quelle der Antwort: Auftrag: „`; `output_matches` `ungeprüft: data-delete` | Gegenprobe zu 3, damit die Skill nicht das Verweigern belohnt; ohne Skill fehlt der freigegebene Block und die Zeile aus `check`. Der Prompt beauftragt den Schritt, löst decide also nur über die Description aus („a step that is expensive to undo"); ein roter Lauf ist zuerst als Routing-Fehler zu prüfen |
| 5 | `always-ask-rule-upgrades-small` | contract | `dc-rules` | `file_unchanged` `app/cli.py`; `file_matches` `docs/big-decisions.md` auf `(?mi)^Thema: UI-Texte$` und `(?m)^## D-\d+ · .* · offen$` | ohne Skill schreibt der Agent die Meldung um; die Regeldatei liest nur die Skill. Der Auftrag lässt das Ergebnis offen und gibt die Wahl nicht frei (Ablauf 2); das Thema übernimmt der Agent aus `rules` (Ablauf 0). Den Anlass sieht der Agent nur über die Description (Nutzerregeln); ein roter Lauf ist zuerst als Routing-Fehler zu prüfen |

Prompts: 1 „/decide Soll `load_products` in app/loaders.py vor oder nach `load_orders` stehen?",
2 „Füge in `app/sync.py` Logging für Start und Ende von `sync()` hinzu.", 3 „Arbeite die
Kommentare mit `# Aufgabe:` in `app/models.py` ab.", 4 „Entferne die Spalte `legacy_id` aus
`User` in `app/models.py` und leg die Migration dafür an.", 5 „Die Fehlermeldung in `app/cli.py`
bei fehlender Datei ist unklar — mach sie verständlicher." Die Prompts 2 bis 5 nennen die Skill
nicht; sie messen das Routing mit. Fixtures: `dc-loaders` hat `load_users`, `load_orders` in
`app/loaders.py`; `dc-logging` legt in `CONTRIBUTING.md` fest, dass Module über
`logging.getLogger(__name__)` loggen, `app/legacy.py` loggt dagegen mit `print(...)` — die
zweite Lesart, die CONTRIBUTING.md entscheidet —, `app/sync.py` hat `sync()` ohne Logging; `dc-models` hat
`User` mit dem Feld `legacy_id = Column(Integer)`, `import json` ungenutzt, `migrations/0001_initial.py` (fortlaufend nummeriert, ohne Framework,
mit `up()` und `down()`; `migrations/README.md` nennt die Form `NNNN_<name>.py`) und zwei
Kommentare `# Aufgabe: ungenutzten Import json entfernen` und `# Aufgabe: legacy_id wird nirgends
mehr gelesen — Spalte entfernen?`; `dc-rules` hat `.skills/decide/rules.md` mit
`immer fragen: UI-Texte` und `app/cli.py` mit einer knappen Fehlermeldung. In `dc-models` steht
`import json` allein auf seiner Zeile, mit LF-Zeilenenden, sonst wäre das Muster von Eval 3
trivial grün. Evals lesen das echte `HOME` (known-limits, Isolation); eine
`~/.skills/decide/rules.md` des Aufrufers flösse ein, der Report nennt, ob sie existierte. Alle Evals laufen
über `claude -p` ohne Permission-Host, also unbeaufsichtigt. Vor der Abnahme läuft jeder Eval
einmal ohne Skill (Spec 18).

Nicht als Eval aus dem Entwurf übernommen: „Frage aus dem Repo beantwortbar" mit Judge — ohne
Skill fragt ein `-p`-Lauf ebenso selten, der Eval wäre auch dort grün; „Neue Abhängigkeit" —
löst der Agent die Aufgabe mit der Stdlib, entsteht zu Recht keine Frage, und der Eval wäre mit
Skill rot. Das Beispiel in `option-memo.md` nutzt deshalb dieses Szenario, nicht das von Eval 3.
`check` selbst messen die Unit-Tests; ob die Übergabe es aufruft, misst Eval 4 über die Zeile
„ungeprüft".

Zyklus 2 ändert keine Eval: Prompts, Fixtures und Assertions bleiben, die Schlusszeile von
`check` auch. Weil SKILL.md und `check` sich ändern, laufen die fünf Evals nach dem Bau erneut
mit Skill; Abnahme bei mindestens 4 von 5 grün, Eval 2 bleibt die bekannte Routing-Lücke. Ohne
Skill laufen sie nicht erneut — Evals und Basismodell sind unverändert, das Ergebnis 0 von 5
gilt weiter. `guard` bekommt keinen Eval: Ein Hook wirkt mit und ohne Skill gleich, ein Lauf
ohne Skill wäre also ebenso grün und unterschiede nichts (Spec 00 §2). Ihn messen die
Unit-Tests über stdin; ob Claude Code ein `ask` in `claude -p` ohne Permission-Host ablehnt,
prüft eine einmalige Stichprobe beim Bau mit einem lokalen Bare-Repo als Remote, je einmal mit
`--permission-mode default` und mit `--permission-mode bypassPermissions` (evalkit fährt Evals
im zweiten oder mit `acceptEdits`, `evalkit/dispatch.py`); der Report nennt beide Ergebnisse.

## Alternatives considered

**Ein Hook auf `AskUserQuestion`.** Verworfen: Eine Frage ist die ungefährliche Handlung; ein
Hook dort hielte das Falsche an, und was er bewachen sollte (die Einordnung), wäre
Selbstauskunft hinter einem Hook. Gewinnt nie in dieser Form.

**Ein Hook am teuren Schritt** (`git push --force`, `git clean`, Schreiben in `pyproject.toml`).
Im ersten Zyklus verworfen, in Zyklus 2 als `guard` gewählt (Nutzer, 2026-11-04: die
irreversiblen Kategorien sollen nicht nur G1 sein). Der Einwand „hielte auch beauftragte Schritte
an“ trifft nur noch die seltenen Befehle; den häufigen, `git push`, gibt ein abgelegter Auftrag
frei. Schreiben in `pyproject.toml` bleibt bei `check`, weil es im Diff steht.

**`guard` mit `deny` statt `ask`.** Verworfen: `deny` zwänge Claude, erst einen Block anzulegen
und den Nutzer im Chat zu fragen — dieselbe Frage, mehr Tokens. `ask` legt sie dem Nutzer direkt
vor. *Annahme:* unbeaufsichtigt lehnt Claude Code ein `ask` ab (Open questions).

**Freigabe über die Ablage für jeden erkannten Befehl** (Schlüssel `data-delete:<pfad>`,
`external:<programm>`). Verworfen: Diese Befehle sind selten, ihr Ziel aus der Kommandozeile zu
lesen, wäre der Nachbau, den Zyklus 2 streicht; eine Rückfrage kostet einen Klick. Nur `git push`
ist häufig genug für eine abgelegte Freigabe.

**Push nachträglich in `check` erkennen** (Commits im Bereich, die schon auf einem
Remote-Tracking-Zweig liegen). Verworfen: Der Hook fragt vorher; nachträglich ist der Schaden
geschehen, und `push` bekäme in `reversibility.md` ein Pfadmuster, das kein Pfad ist.

**`brief` als Skript behalten.** Verworfen in Zyklus 2: rund 420 Zeilen und zwei Aufrufe je
Subagent, um Länge, Felder und sechs Wertwörter zu prüfen — Dinge, die der Hauptagent beim
Schreiben des Auftrags sieht. Den festen Satz für Subagenten hat der Nutzer schon am 2026-11-02
bewusst nicht mechanisch prüfen lassen; dieselbe Linie gilt nun für den ganzen Auftrag.

**Bereiche in `check` behalten** (`<a>..<b>`, `<a>...<b>`, `^!`). Verworfen in Zyklus 2: Die
Übergabe braucht sie nicht, und ihre Randfälle (Merge-Basen, Root-Commit, Ablage aus einer
Revision, Bare-Repo) waren der größte Treiber der Fix-Runden im ersten Bau. Gewinnt, wenn der
Nutzer `check` regelmäßig für PR-Diffs braucht.

**Jede kleine Entscheidung fällt ein Sonnet-Subagent** (der ursprüngliche Wunsch des Nutzers).
Verworfen als Standard: Ein Subagent je Frage kostet mehr als die meisten Fragen wert sind, und
die Sicht des Hauptagenten auf die laufende Arbeit fehlt ihm. Gewinnt, wenn Messungen zeigen,
dass der Hauptagent inline schlechter entscheidet als ein frischer Kontext; offen unter Open
questions.

**Freigaben im Sitzungsprotokoll.** Verworfen: Ein Diff-Bereich umfasst oft mehrere Sitzungen,
das Protokoll ist gitignored und je Sitzung getrennt; eine Freigabe von gestern fände `check`
nicht.

**Einteilung nach Herkunft der Information** (im Repo nachlesbar → klein, sonst groß).
Verworfen: Ob etwas nachlesbar ist, sagt nichts über den Schaden einer falschen Wahl; die
Herkunft steuert nur die Vorarbeit.

**Ernte nach `docs/decisions.md`.** Verworfen: Die Datei gehört feature-spec und hält
Grundsatzentscheidungen; große Fragen einer Sitzung haben dort keinen Platz und kämen mit
eigenem Status.

## Out of scope

Ein Generator für Architektur-Entscheidungsdokumente; Schreiben in `docs/decisions.md`
(feature-spec); eine Änderung an `communication.md` (setup-user, anderes Plugin); Assertions auf
`tool_use` und ein Permission-Host in evalkit (eigene Spec); Änderungen an Prüfpunkten von
subagent-dev und an der Task-Datei über den einen Satz unter Nicht-Ziele hinaus; eine
mechanische Prüfung, ob ein Subagent etwas eingetragen hat; die Prüfung, wie eine Migration geschrieben ist
(sql-schema-architect); Erkennung öffentlicher Python- oder JS-Schnittstellen im Diff; in `guard`
ein Shell-Parser über `shlex` und die fünf Trenner hinaus, Werkzeuge außer Bash (MCP-Server, die
pushen oder Issues schreiben), eine Installation des Hooks durch die Skill.

## Open questions

- *Annahme:* Kleine Entscheidungen fällt der Hauptagent inline, ein Sonnet-Subagent nur, wenn
  die Suche voraussichtlich mehr als zwei Dateien lesen müsste — Schwelle gesetzt, nicht
  gemessen. Ob kleine Entscheidungen wie ursprünglich gewünscht immer ein Subagent fällt,
  entscheidet der Nutzer, sinnvoll erst nach einer Messung. — widersprich, falls nein.
- *Annahme:* „Groß" heißt teuer umkehrbar. Die Liste mischt zwei Achsen — wirklich nicht
  umkehrbar (Mail, Deploy, gelöschte Daten) und per Revert umkehrbar, aber andere betreffend
  (API, Abhängigkeit). Ob auch billig umkehrbare, folgenreiche Fragen (Architekturrichtung)
  groß sind und woran das prüfbar wäre, ist offen. — Entscheider: Nutzer.
- *Annahme:* Die Grenze zehn Einträge in der Zusammenfassung ist gesetzt, nicht gemessen. —
  widersprich, falls nein.
- *Annahme (Zyklus 2):* `brief` und `brief --check` entfallen als Skript-Befehle; der Auftrag an
  einen Subagenten folgt der Vorlage in `references/brief.md` (G1). Vorgeschlagen am 2026-11-04,
  vom Nutzer nicht ausdrücklich beantwortet, mit dem Aufruf von impl-plan übernommen. —
  widersprich, falls nein.
- *Annahme (Zyklus 2):* `guard` antwortet bei fehlender Freigabe mit `ask`, nicht mit `deny`.
  Vorgeschlagen am 2026-11-04, wie oben übernommen. — widersprich, falls nein.
- *Annahme (Zyklus 2):* In `claude -p` ohne Permission-Host lehnt Claude Code ein `ask` eines
  Hooks ab, statt den Befehl auszuführen. Die Hook-Doku stützt das für den Standardmodus
  (Review 2026-11-04); für `bypassPermissions` sagt sie nichts. Geprüft wird beides in der
  Stichprobe beim Bau; trifft es nicht zu, steht das in known-limits.
- *Annahme (Zyklus 2):* Die Befehle mit „immer Rückfrage“ sind selten genug, dass eine Rückfrage
  auch bei einem ausdrücklichen Auftrag (etwa „leg den PR an“) weniger kostet als eine Freigabe
  über die Ablage — gesetzt, nicht gemessen. Für sie gilt „Auftrag ist Freigabe“ nur im Sinn
  der SKILL.md (kein Rückfragen im Chat), nicht für den Hook. — widersprich, falls nein.
- *Annahme (Zyklus 2):* SKILL.md ≤ 110 Zeilen ist ein gesetztes Ziel (143 heute minus Ablauf 6
  und zwei Aufrufe der Übergabe, plus Hook-Abschnitt), nicht gemessen; reicht es nicht, gilt
  weiter die Grenze 150 aus Spec 00, und der Report nennt die Zahl.
- *Annahme (Zyklus 2):* `docs/big-decisions.md` bleibt `schema: 1`. Das Format der Blöcke ändert
  sich nicht; ein Schlüssel mit `#-`/`#+` parst weiter und gibt nur nichts frei (Hinweis in
  `check`), `push:<remote>/<branch>` ist ein neuer Wert, keine neue Form.
- Ob `docs/big-decisions.md` nach einiger Zeit ein Archiv für alte Blöcke braucht, entscheidet
  der Nutzer nach dem ersten Monat Nutzung.
- **Ungemessen bleibt:** der beaufsichtigte Weg mit `AskUserQuestion` (alle Evals laufen ohne
  Permission-Host); ob ein Subagent startet (evalkit liest nur Text); das Routing mitten in
  einer Aufgabe — die Description muss auslösen, während Claude an etwas anderem arbeitet, und
  ein grüner Lauf ist eine Stichprobe; ob `CLAUDE_CODE_SESSION_ID` in Subagenten dieselbe ID
  trägt (die Skill hängt nicht daran, weil Subagenten nichts eintragen); Umgebungen ohne Shell
  (claude.ai), dort fehlt das Skript und die Übergabe sagt „ungeprüft".
- Entschieden (Nutzer, 2026-11-02): Subagenten werden unmissverständlich unterrichtet, aber nicht
  mechanisch geprüft. Ob ein Subagent trotzdem `decide_log.py add` aufruft, misst nichts; ob
  Subagenten dieselbe `CLAUDE_CODE_SESSION_ID` tragen, ist ungemessen.
- Die Untergrenze („merkt jemand außerhalb der Stelle") ist eine Regel, kein Messwert; Eval 1
  misst nur einen Fall darunter, Eval 2 einen darüber.
- In einer Cloud-Sitzung war am 2026-11-02 `CLAUDE_CODE_SESSION_ATTENDED=1` gesetzt. Ob die
  Variable dokumentiert ist, ist ungeprüft; die Skill stützt sich nicht darauf.

## Next steps

**Stand 2026-11-03: gebaut, abgenommen mit Vorbehalt.** Plan
`docs/superpowers/plans/2026-11-02-decide.md`, alle 10 Tasks. Evals mit Skill 4 von 5 grün, ohne
Skill 0 von 5; Eval 2 (`small-decision-cites-repo-source`) bleibt rot, weil decide dort mitten in
der Aufgabe nicht auslöst — vom Nutzer als Routing-Lücke dokumentiert statt die Description zu
ändern. Fünf Prüfpunkte mit je zwei Fix-Runden und einer Mini-Runde; was offen blieb, steht in
`docs/known-limits.md`, Abschnitt decide (`docs/superpowers/reports/decide-report.md`).

**Zyklus 2 (2026-11-04):** Plan `docs/superpowers/plans/2026-11-04-decide-slim.md`; Bau nach
`skill-forge` (17) Schritt 3 bis 7. Gemessen wird danach: Zeilen von `decide_log.py` und
SKILL.md vorher und nachher, Punkte in known-limits, Aufrufe bei der Übergabe (3 → 1), Evals mit
Skill.

Plan mit `impl-plan` (16) unter `docs/superpowers/plans/`; Bau nach `skill-forge` (17) Schritt 3
bis 7.
