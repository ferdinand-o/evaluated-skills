# Bericht: Skill `sql-schema-architect` (Spec 08)

Branch `feat/sql-schema-architect`, Basis `0831fb7`. Zehn Commits, `6d0e8d9`
(Plan) bis `f9795f1` (letzter Fix). Volle Testsuite: 260/260 grün
(146 bestehende + 114 neue). `run_evals.py` nicht ausgeführt (Auftrag).

## Was gebaut wurde

```
skills/sql-schema-architect/
├── SKILL.md                       (110 Zeilen)
├── references/
│   ├── conventions.md
│   ├── migration-safety.md        (spiegelt migration_gate.py's Klassifikationstabelle wörtlich)
│   └── modeling.md                (inkl. Array-vs-Relation-Antipattern für Eval 2)
├── assets/
│   ├── conventions.json           (R1: JSON, kein YAML)
│   ├── table-template.md
│   └── hooks/migration-gate.json  (G3-Vorlage, nie automatisch installiert)
└── scripts/
    ├── gen_erd.py       (Tier 1, ast, keine Imports — R3)
    ├── lint_schema.py   (Tier 1 im Kern, sqlfluff optional — R4)
    └── migration_gate.py (Tier 1, ast, keine Imports — R2)

evals/sql-schema-architect/evals.json  (5 Evals)
evals/fixtures/{production-trap,array-vs-relation,missing-downgrade,
                convention-violations,green-additive}/

tests/test_sql_schema_architect_{migration_gate,gen_erd,lint_schema}.py
(61 + 23 + 29 = 113 Tests, plus 1 Regressionstest für relationship()-Rendering)
```

### `migration_gate.py`

Liest eine Alembic-Revision ausschließlich mit `ast.parse` — `upgrade()`/
`downgrade()` per Funktionsname, `op.<method>(...)`-Aufrufe per
`ast.walk`+Attribute-Match auf `op`, Argumentwerte über `ast.unparse()` in
Text verwandelt (kein `literal_eval`, das würde an `sa.Column(...)`
scheitern). Klassifiziert jede Operation grün/gelb/rot nach einer
Tabelle, die identisch in `migration-safety.md` steht. `execute()` und
unbekannte `op.*`-Methoden sind eine eigene vierte Kategorie (`unknown`),
die **nie** als grün in das Gesamturteil einfließt — ein sonst grünes Bild
mit einem `op.execute()` landet mechanisch getestet bei `review_required`
(Exit 2), nie bei `pass` (Exit 0). Kontraktprüfungen: `upgrade()` fehlt,
`downgrade()` leer ohne begründete Einbahn-Migration
(`raise NotImplementedError("<Grund>")`), rote Klassifikation ohne
`Mehrschritt-Plan:`-Marker im Dateitext — alle drei führen zu
`violation` (Exit 1). Härte-Erkennung (R6) liest `.claude/settings.json`
und `.claude/settings.local.json` nach dem Hook-Pfad-Fragment und schreibt
die geltende Härte (G2/G3) in jede Text- und JSON-Ausgabe. `--hook-check`
liest ein PreToolUse-JSON von stdin, matcht `alembic\s+upgrade` in
`tool_input.command`, klassifiziert alle Revisionen im Versions-Verzeichnis
und blockiert (Exit 2) bei jedem Status außer `pass`.

Ich musste die Tabellen-Argument-Position pro `op.*`-Signatur explizit
kodieren (`create_index`/`drop_index` haben den Tabellennamen an Position 1,
nicht 0; `create_foreign_key` ebenso) — ein naiver „erstes Text-Argument"-
Ansatz hätte den Index- bzw. Constraint-Namen fälschlich als Tabellenname
gelesen. Das ist in Tests abgedeckt (`test_create_index_*`,
`test_create_foreign_key_*`).

### `gen_erd.py`

Scannt Klassen mit `ast`, erkennt `__tannename__`-Literale, `Column(...)`/
`mapped_column(...)`-Zuweisungen, verschachtelte `ForeignKey(...)` (inkl.
`ondelete`), `relationship(...)`-Aufrufe und Indizes über `index=True` oder
`__table_args__`. Statisch nicht Auflösbares — dynamisches `__tablename__`
(f-String, Funktionsaufruf) oder eine Klasse mit Columns aber ohne eigenes
`__tablename__` (Mixin-/Vererbungskette) — wird **nicht** übersprungen,
sondern mit Klassenname und sichtbarer Warnung sowohl in `ScanResult.warnings`
als auch als `%%`-Kommentar im gerenderten Mermaid-Diagramm aufgenommen (R3).
FK-Kanten tragen Kardinalität `||--o{` per Default, `||--||` wenn die Spalte
`unique=True` trägt. `relationship()`-Aufrufe wurden zunächst geparst, aber
nicht gerendert — beim Review dieses Berichts gefunden und nachgezogen
(Commit `f9795f1`): sie erscheinen jetzt als informative `%%`-Kommentare
unter dem Diagramm, mit dem Hinweis, dass nur die FK-Kanten verlässliche
Kardinalität tragen.

### `lint_schema.py`

Tier 1 im Kern: Naming (snake_case, mechanisch über Regex — grammatische
Singular/Plural-Erkennung bewusst **nicht** automatisiert, siehe unten),
Typen (`String(n)`/`VARCHAR` gegen `text`, `DateTime` ohne `timezone=True`),
Pflichtspalten, FK-`ondelete`, und der Steckbrief-Vertrag (Existenz,
Artefakt-Kopfzeile, alle vier Pflichtsektionen nicht-leer, „Index ohne
Zugriffsmuster" wenn ein Index existiert und die Hauptzugriffsmuster-Sektion
leer/fehlend ist). Lädt `gen_erd.py` per `importlib.util` aus demselben
`scripts/`-Verzeichnis (kein Paket, kein `sys.path`-Eingriff — dasselbe
Muster wie `tests/conftest.py::load_script`), damit beide Skripte
eigenständig per `python scripts/lint_schema.py` laufen. sqlfluff ist
optional: `shutil.which("sqlfluff")` entscheidet, und die Ausgabe trägt
**immer** eine der beiden Zeilen — „sqlfluff nicht installiert …
Kernprüfungen liefen trotzdem" oder „sqlfluff ausgeführt" (R4, Spec 00 §3/§4,
kein stilles Überspringen). Projekt-Override via
`.skills/sql-schema-architect/conventions.json` überschreibt Top-Level-Keys
des Default-Presets, ohne es vollständig duplizieren zu müssen.

## Entscheidungen, die ich zusätzlich treffen musste

1. **Kein Kommentar-Bypass für `varchar`.** Die Spec deutete einen
   „dokumentierten Grund" für `varchar` an; ich habe bewusst **keinen**
   Kommentar-Marker implementiert, der die Lint-Prüfung stillschweigend
   abschaltet — genau das wäre die Falle aus `brief-common.md`
   („Assertions, die nichts bewachen"): ein Agent könnte lernen, immer einen
   Fake-Grund-Kommentar zu setzen. `reject_varchar` flaggt jetzt
   ausnahmslos; ein begründeter Einsatz gehört ins PR-Review.
2. **Grammatische Tabellen-Plurality bewusst nicht mechanisch geprüft.**
   `table_plurality_preference` bleibt dokumentierte Präferenz in
   `conventions.json`/`conventions.md`, kein Lint-Befund — ohne Wörterbuch
   ist „ist das ein Plural?" nicht zuverlässig genug für eine Assertion, die
   etwas beweisen soll.
3. **Exit-Code-Dreiteilung bei `migration_gate.py`** (0 pass / 1 violation /
   2 review_required) ist meine Ergänzung, nicht explizit in der Spec
   gefordert — nötig, um R2s zentrale Anforderung („nicht bewertbar" darf nie
   mit „bestanden" verwechselt werden) auch im Exit-Code sichtbar zu machen,
   nicht nur im Text.
4. **`from __future__ import annotations` in `migration_gate.py` weggelassen.**
   Zusammenspiel aus `dataclasses` + String-Annotationen +
   `tests/conftest.py::load_script` (registriert das dynamisch geladene
   Modul nicht in `sys.modules`) bricht `dataclass`-Feldauflösung
   (`AttributeError: 'NoneType' object has no attribute '__dict__'`). Statt
   `conftest.py` anzufassen (gemeinsame Infrastruktur, die auch andere
   Skills nutzen) habe ich nur mein eigenes Skript angepasst — Python 3.13
   wertet `X | None`/`list[X]` zur Laufzeit ohne Future-Import aus.
5. **Anti-Zeremonie-Eval als `behavior`, nicht `contract`.** Anders als
   `dev-report` gibt es hier kein einzelnes, pfad-vorhersagbares
   Report-Artefakt, dessen Kürze sich per `file_max_lines` prüfen ließe —
   die Kürze zeigt sich in der Konversation, nicht in einer Datei.
   `docs/known-limits.md` dokumentiert bereits denselben Kompromiss für
   `handoff`s `anti-ceremony-invents-nothing`; ich folge dem Präzedenzfall.
6. **README.md-Routing-Matrix nicht angefasst.** Schon `dev-report` (voll
   gebaut, im Basis-Commit) taucht dort nicht als eigene Zeile auf, nur als
   „nicht"-Verweis anderer Zeilen — ich habe das bestehende Muster
   respektiert, statt einseitig eine neue Konvention einzuführen.

## Was ich nicht verifizieren konnte

- **Kein echter Eval-Lauf.** `run_evals.py` startet echte Claude-Läufe;
  laut Auftrag zentral koordiniert, nicht von mir ausgeführt. Ich habe
  stattdessen `evalkit.workspace.prepare()` für alle fünf Fixtures manuell
  aufgerufen und `migration_gate.py`/`lint_schema.py` gegen die gebauten
  Workspaces laufen lassen — die mechanischen `must`-Muster
  (`"status":\s*"violation"`, `userEmail`, `String\(50\)`, …) sind damit
  gegen echten Skript-Output verifiziert, nicht nur gegen mein Verständnis
  des Codes. Die drei `judge`-Assertions (Produktions-Trap-Muster,
  Array-vs-Relation-Empfehlung, Kürze des trivialen Falls) sind **nicht**
  gegen einen echten Claude-Agenten getestet — ob das Modell den
  SKILL.md-Anweisungen in der Praxis tatsächlich so folgt, wie ich es beim
  Schreiben des Prompts angenommen habe, bleibt offen bis zum zentralen
  Eval-Lauf.
- **Kein Hook praktisch installiert/getestet.** `detect_hook_installed()`
  und `--hook-check` sind durch Unit-Tests mit synthetischen
  `settings.json`/stdin-Payloads abgedeckt, aber nie gegen eine echte
  Claude-Code-`PreToolUse`-Hook-Ausführung. Das genaue JSON-Kontrakt
  (`tool_name`, `tool_input.command`) stammt aus meinem Verständnis der
  Hook-Konvention, nicht aus einem verifizierten Live-Aufruf.
- **sqlfluff-Pfad ungetestet gegen ein echtes sqlfluff.** Es ist in dieser
  Umgebung nicht installiert (R4 bestätigt das); `sqlfluff_status()` ist nur
  mit gemocktem `shutil.which` getestet, der `subprocess.run`-Zweig mit
  echtem sqlfluff-JSON-Output lief nie.
- **Cardinality-Heuristik in `gen_erd.py` ist ungeprüft gegen reale
  Codebasen.** `unique=True` → `1:1`, sonst `1:1--o{` ist eine plausible,
  aber nicht validierte Faustregel; SQLAlchemy-2.0-Style
  (`Mapped[int]`-Annotationen ohne expliziten Typ-Positionalarg in
  `mapped_column(...)`) wird nur teilweise erfasst — der Typ-Ausdruck fällt
  dann auf `"?"` zurück, was `render_mermaid` sichtbar macht, aber nicht
  automatisch aus der Annotation nachträgt.

## Für `docs/known-limits.md`

Folgende Punkte gehören dort hinein (ich habe die Datei nicht verändert,
weil der Auftrag „keine andere Skill anfassen" auch für die gemeinsame
Dokumentation defensiv auslegen lässt — melde das explizit zur Prüfung):

1. **`migration_gate.py`s `Mehrschritt-Plan:`-Marker ist ein Freitext-
   Contract, keine inhaltliche Prüfung.** Der Marker verlangt nur mehr als
   zehn Zeichen nach dem Doppelpunkt — ein Agent könnte technisch mit einer
   inhaltsleeren, aber langen Phrase eine rote Migration „begründen", ohne
   dass tatsächlich mehrere Revisionen oder ein reales Backfill existieren.
   Das ist dieselbe Klasse Schwäche wie dev-reports `must_not`-Regex-Fallen:
   die Form ist geprüft, der Inhalt nicht.
2. **`--hook-check`s Bash-Muster (`alembic\s+upgrade`) ist eng.** Projekte,
   die Migrationen über `python -m alembic`, `poetry run alembic`, ein
   `Makefile`-Target oder ein CI-Skript anstoßen, umgehen den Hook
   vollständig, ohne dass irgendetwas das meldet — ein stiller blinder
   Fleck, kein Fehler im engeren Sinn, aber erwähnenswert für Nutzer, die
   sich auf G3 verlassen.
3. **`gen_erd.py` löst SQLAlchemy-2.0-`Mapped[T]`-Typannotationen ohne
   expliziten `mapped_column(...)`-Typ-Positionalarg nicht auf** (Typ
   erscheint als `"?"`). Betrifft Codebasen im neueren SQLAlchemy-2.0-Stil.
4. **Der Steckbrief-Vertrag prüft nur Nicht-Leerheit der Sektionen, nicht
   deren Aussagekraft.** Eine „Hauptzugriffsmuster"-Sektion mit dem Inhalt
   „x" (wie in einigen Test-Fixtures, absichtlich minimal) erfüllt den
   Contract genauso wie ein echter Satz — dieselbe Grenze wie bei jedem rein
   strukturellen Contract-Check.

## Testergebnis

`.venv/bin/pytest -q` → **260 passed** (146 vorher + 114 neu:
61 `migration_gate` + 24 `gen_erd` + 29 `lint_schema`, davon einer
nachträglich für das relationship()-Rendering ergänzt). `load_evals()`
bestätigt 5 syntaktisch valide Evals in
`evals/sql-schema-architect/evals.json`. Alle fünf Fixtures wurden über
`evalkit.workspace.prepare()` gebaut und die mechanischen `must`-Muster der
drei nicht-`judge`-lastigen Evals (production-trap: nur `file_exists`;
missing-downgrade; convention-violations) gegen echten Skript-Output
verifiziert.
