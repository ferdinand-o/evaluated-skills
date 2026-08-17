# Abschlussbericht: Skill `learning-coach`

Spec: `specs/Spec 14 – learning-coach.md`, gebunden an
`specs/Spec 00 – skill-foundation.md`.
Branch: `feat/learning-coach`, Basis: `0831fb7`.
Plan: `docs/superpowers/plans/2026-08-17-learning-coach.md`.

## Fehlende `brief-common.md`

Der Auftrag verlangte, zuerst
`/tmp/.../scratchpad/brief-common.md` (Fundament-Contract, Arbeitsweise,
Fehlerklassen) zu lesen. Diese Datei existierte unter dem angegebenen Pfad nicht —
weder im Scratchpad (nur `rulings-final-four.md` lag dort) noch im Repository. Ich
habe das nicht als BLOCKED gewertet (die BLOCKED-Bedingung im Auftrag war explizit an
den Git-Checkout gebunden, der funktionierte), sondern als Ersatz herangezogen:
`specs/Spec 00 – skill-foundation.md` (das Konventions-Dokument, auf das
`rulings-final-four.md` mehrfach verweist — Artefakt-Vertrag, Eval-Vertrag,
Dependency-Tiers, Gate-Ehrlichkeit) sowie die Konventionen der bereits gebauten
Geschwister-Skills `dev-report` und `verified-research` (auf `feat/verified-research`
und im eigenen Basis-Commit vorhanden) als gelebte Praxis. Sollte `brief-common.md`
zusätzliche, hier nicht abgedeckte Vorgaben enthalten haben, ist das eine offene
Lücke dieser Implementierung.

## Was gebaut wurde

```
skills/learning-coach/
├── SKILL.md                       (90 Zeilen, Frontmatter nur name/description)
├── references/
│   ├── learner-schema.md          (Feldformat, Beherrschungsgrad 0-4, Beispiel, E3-Schnittstelle)
│   ├── hint-ladder.md              (vier Stufen, Formulierungen je Aufgabentyp, Anti-Kollaps)
│   └── methods.md                  (Abrufübung, Spacing-Tabelle, Fehleranalyse, Interleaving)
├── assets/learner-template.md      (Bootstrap-Vorlage mit Kopfzeile)
└── scripts/due_topics.py           (Tier 1, 31 Unit-Tests)
evals/learning-coach/evals.json     (8 Evals: 4 contract, 4 behavior)
evals/fixtures/lc-*/                (5 Fixtures, alle mit .skills/learning-coach/learner.md)
tests/test_learning_coach_due_topics.py
docs/superpowers/plans/2026-08-17-learning-coach.md
```

31 neue Unit-Tests, alle grün. Gesamtsuite: **177 von 177 bestanden** (146 bestehende
+ 31 neue).

## E1 — `due_topics.py` als Tier 1

Nur Stdlib (`argparse`, `re`, `shutil`, `dataclasses`, `datetime`, `pathlib`). Zwei
Subcommands:

- `due` — parst `learner.md`, meldet fällige Themen (überfällig zuerst), pro Thema
  die Existenz der zugehörigen Aufgaben-Datei, und ein Abruf-Quiz-Budget von 2-4
  Fragen.
- `interval --grade N --result success|failure` — reiner Rechner, kein Datei-Zugriff,
  liefert nächsten Grad und nächstes Fälligkeitsdatum deterministisch.

Das Skript **führt keine Session** und **schreibt `learner.md` nicht zurück** — das
Update am Sitzungsende ist bewusst Doktrin (SKILL.md), kein Skript-Aufruf: Ein
Sokratischer Dialog lässt sich nicht durch Code ersetzen, nur durch mechanisch
prüfbare Regeln stützen.

## E2 — `learner.md`-Ort und Bootstrap

`resolve_base_dir(repo, skill_name, home=None)` ist die generische Fassung von
`verified-research/scripts/registry.py::resolve_base_dir` — parametrisiert über den
Skill-Namen, weil learning-coach zwei Basisverzeichnisse braucht: die eigene
(`learning-coach`, für `learner.md`) und die von `verified-research` (für den
Aufgaben-Pfad, siehe E3). Override greift, sobald `.skills/<skill_name>/` als
Verzeichnis im Projekt existiert; sonst `~/.skills/<skill_name>/`. Erster Lauf legt
`learner.md` aus `assets/learner-template.md` an und kündigt den Pfad auf stdout an
(Bootstrap-Regel, Spec 00 §1) — getestet, inklusive „nicht überschreiben, wenn schon
da".

Eine Datei, kein Themenbaum (A5): `learner.md` führt beliebig viele Themen als
eigene `## <slug>: <Name>`-Sektionen in einer flachen Struktur.

## E3 — Schnittstelle zu exercise-forge (Spec 13, parallel gebaut)

`due_topics.py` verlässt sich **ausschließlich** auf den Pfad
`~/.skills/verified-research/research/<slug>.exercises.json` (projektlokal
überschreibbar nach demselben Muster) und prüft nur dessen **Existenz** — es parst
den Inhalt nicht, weil die genauen Feldnamen des Aufgaben-Schemas von exercise-forge
nicht bekannt sind (A4: was nicht sicher bekannt ist, wird nicht angenommen). Fehlt
die Datei zu einem fälligen Thema, meldet die Skill wörtlich **„Keine verifizierten
Aufgaben gefunden"** und schlägt vor, exercise-forge aufzurufen — das ist als
SKILL.md-Contract mandatiert, nicht nur als Konvention erwähnt, damit der zugehörige
Eval mechanisch (`output_matches`, kein Judge) bleibt.

**Eigene Entscheidung, keine Spec-14-Vorgabe:** Dass der Aufgaben-Pfad unter dem
Namensraum von `verified-research` statt `learning-coach` liegt, steht so in Spec 13
und in E3 der Rulings — ich habe das wörtlich übernommen, aber die *Existenzprüfung
ohne Feld-Parsing* als konservative Umsetzung von „Bau keine Annahmen über Details,
die du nicht kennst" selbst gewählt.

## E4 — Fälligkeit, nie geraten

`is_due()`: Ein Thema ist fällig, wenn `next_due is None` **oder** `next_due <=
today`. Ein unlesbares Datum (`date.fromisoformat` schlägt fehl) wird wie ein
fehlendes behandelt — mit einer Warnung, nicht mit einem Absturz (A4). Getestet für
alle drei Fälle: vergangenes Datum, zukünftiges Datum, fehlendes Datum.

## Offene Fragen aus Spec 14, hier entschieden (eigene Entscheidungen)

1. **Granularität der Themen:** eine Ebene, freier Slug — keine erzwungene
   Konzept-/Gebiets-Zweistufigkeit. Begründung im Plan: „echte Themen vor Inhalt
   erfinden" wäre A5-widrig.
2. **Herabstufung bei Fehlversuchen:** ein falscher Abruf senkt den Grad sofort um
   genau eine Stufe, kein Toleranz-Zähler — `learner.md` führt ohnehin keinen
   separaten Fehlversuchs-Zähler, und „im Zweifel erinnern statt vergessen" (E4)
   spricht für schnelles Sinken.
3. **Spacing-Intervall-Tabelle** (`{0: 0, 1: 1, 2: 3, 3: 7, 4: 14}` Tage): eigene,
   einfache Progression statt vollem SM-2 — dokumentiert und begründet in
   `references/methods.md`, mit `next_interval()` deterministisch berechnet und
   getestet (Erfolg wächst, Fehler schrumpft, an den Grenzen 0/4 geklemmt).

## Evals (geschrieben, nicht ausgeführt — Auftrag: nicht ausführen)

Acht Evals, vier `contract` (mechanisch) und vier `behavior` (Judge). Schema lokal
gegen `evalkit.schema.load_evals` validiert (lädt sauber, keine `EvalSchemaError`).
Alle fünf Fixtures gegen `evalkit.workspace.prepare()` probegebaut — jede liefert ein
lesbares `.skills/learning-coach/learner.md` im Workspace, `due_topics.py` läuft
gegen jede Fixture direkt durch (manuell mit `--today 2026-08-17` verifiziert,
inklusive der exakten Phrase „Keine verifizierten Aufgaben gefunden").

- **Anti-Zeremonie (Pflicht, Spec 00 §2):** `nothing-due-stays-honest` — nichts
  fällig, `learner.md` muss `file_unchanged` bleiben, kein erfundenes Quiz.
- Drei weitere `contract`-Evals hängen an `must_not: file_unchanged` bzw. der
  mandatierten Phrase — beides Artefakte/Wortlaut, die nur diese Skill kennt (A6):
  16 fremde Skills im Eval-Agenten wüssten weder von `.skills/learning-coach/`
  noch von der exakten Phrase.
- Vier `behavior`-Evals decken die fünf Fallen aus Spec 14 ab (Lösungs-Wunsch,
  Frust-Trap, Quiz-zuerst, Fehleranalyse — die Kurzform-Eval aus Spec 14 ist als
  `short-session-still-updates` mechanisch statt als Judge-Fall umgesetzt).

**Was ich nicht verifizieren konnte:** ob ein echter Claude-Agent, der SKILL.md liest,
sich tatsächlich an die harte Hinweis-Leiter und die Update-Pflicht hält — das zeigt
nur ein echter `run_evals.py`-Lauf, den ich laut Auftrag nicht ausführen durfte. Auch
der Script-Pfad-Kontrakt (`skills/learning-coach/scripts/...` in SKILL.md vs. die
tatsächliche Installation unter `.claude/skills/learning-coach/...` im
Eval-Workspace) ist ungeprüft — dieselbe offene Frage, die der `verified-research`-
und der `dev-report`-Bericht schon nennen, hier nicht neu gelöst.

## Zusätzliche Entscheidung: `tests/conftest.py`-Fix

`load_script()` registrierte das geladene Modul bisher nicht in `sys.modules`,
wodurch `@dataclass` in `due_topics.py` mit
`AttributeError: 'NoneType' object has no attribute '__dict__'` abstürzte
(`dataclasses._is_type()` sucht `sys.modules[cls.__module__]`). Ich habe denselben
Fix angewendet, den der `verified-research`-Bericht für denselben Bug beschreibt
(unabhängig auf einem anderen Branch gefunden) — `sys.modules[spec.name] = module`
vor `exec_module()`. Da beide Branches vom selben Basis-Commit abzweigen und dieselbe
Datei ändern, ist beim Zusammenführen der Branches ein trivialer Merge-Konflikt in
`tests/conftest.py` zu erwarten (identischer Fix, unterschiedliche Kommentartexte).

## Testergebnis

```
177 passed in 3.14s
```

(146 bestehende Tests + 31 neue für `due_topics.py`, keine Regression.)

## Offene Sorgen

- `brief-common.md` fehlte (siehe oben) — unklar, ob dort zusätzliche verbindliche
  Vorgaben standen, die hier nicht berücksichtigt sind.
- Die acht Evals sind ungelaufen; ob die SKILL.md-Doktrin (harte Hinweis-Leiter,
  Update-Pflicht, exakte Phrase) einen echten Agenten tatsächlich lenkt, ist nicht
  gezeigt, nur plausibilisiert.
- Die Schnittstelle zu exercise-forge (Spec 13) ist nur über den dokumentierten Pfad
  und Existenzprüfung abgesichert — sobald Spec 13 fertig ist, lohnt ein Integrations-
  Check, ob das tatsächliche Aufgaben-JSON die in Spec 13 versprochenen Felder (Typ,
  Lernziel, Schwierigkeit, Verifikations-Protokoll) wirklich trägt.
- README-Routing-Tabelle wurde bewusst nicht angefasst (mehrere parallele Branches
  ändern potenziell dieselbe Datei; nicht Teil des Auftrags).
