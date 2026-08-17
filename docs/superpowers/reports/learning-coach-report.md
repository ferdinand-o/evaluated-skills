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
├── SKILL.md                       (Frontmatter nur name/description)
├── references/
│   ├── learner-schema.md          (Feldformat, Beherrschungsgrad 0-4, Beispiel, E3-Schnittstelle)
│   ├── hint-ladder.md              (vier Stufen, Formulierungen je Aufgabentyp, Anti-Kollaps)
│   └── methods.md                  (Abrufübung, Spacing-Tabelle, Fehleranalyse, Interleaving)
├── assets/learner-template.md      (Bootstrap-Vorlage mit Kopfzeile)
└── scripts/due_topics.py           (Tier 1, 40 Unit-Tests)
evals/learning-coach/evals.json     (9 Evals: 5 contract, 4 behavior — nach Fix-Runden)
evals/fixtures/lc-*/                (6 Fixtures, alle mit .skills/learning-coach/learner.md)
tests/test_learning_coach_due_topics.py
docs/superpowers/plans/2026-08-17-learning-coach.md
```

40 neue Unit-Tests, alle grün. Gesamtsuite: **186 von 186 bestanden** (146 bestehende
+ 37 neue).

## Fix-Runde (unabhängiger Review)

Ein unabhängiger Reviewer prüfte den Stand vor der ersten `run_evals.py`-Ausführung
und fand zwei Defekte und zwei Lücken (Befund unter
`scratchpad/review-learning-coach.md`). Alle vier wurden behoben, dazu eine
fünfte, als Anmerkung eingestufte Beobachtung dokumentiert statt behoben:

1. **Defekt — Eval widersprach der eigenen Hinweis-Leiter-Doktrin.** Der Prompt von
   `frustration-moves-one-rung-not-to-solution` endete mit „sag's mir einfach" —
   `hint-ladder.md` nennt genau diese Formulierung als sanktionierten Auslöser für
   Stufe 4. Ein doktrintreuer Agent hätte den Eval strukturell nicht bestehen
   können. **Entscheidung des Koordinators, umgesetzt wie vorgegeben:** die Doktrin
   gewinnt, der Eval wurde umgebaut — der Prompt drückt jetzt Frustration ohne
   explizite Lösungs-Bitte aus, der Judge-Claim prüft „eine Stufe weiter statt bis
   zur Lösung", nicht mehr „keine Lösung trotz Bitte".
2. **Defekt — Pflicht-Anti-Zeremonie-Eval hing an einer zu engen Regex.** Das Muster
   `nichts.*fällig|keine.*fällig|derzeit keine` ließ eine korrekte Antwort wie „kein
   Thema fällig" (Singular) durchfallen — exakt die in `docs/known-limits.md`
   dokumentierte Sprödigkeits-Klasse. Behoben: `nothing-due-stays-honest` ist jetzt
   `class: behavior` mit einem Judge-Claim für die Formulierung; `file_unchanged`
   bleibt als mechanisches `must` bestehen.
3. **Lücke — keine Reaktion auf existierende, aber leere/kaputte Aufgaben-Datei.**
   `due_topics.py::exercises_status()` ist neu: prüft neben Existenz auch, ob die
   Datei gültiges JSON und ein nicht-leeres Array ist. Fehlend, leer und
   strukturell unerwartet ergeben alle dieselbe mandatierte Phrase „Keine
   verifizierten Aufgaben gefunden". Neue Fixture `lc-broken-exercises` (leeres
   `[]`) plus Eval `empty-exercises-file-is-named-not-hidden` decken den Fall ab.
   Sechs neue Unit-Tests.
4. **Lücke — kein Eval prüfte die Kopfzeile nach einem echten Update.** Die
   Kopfzeile war nur beim Bootstrap getestet. `artifact_header`-Assertion zu
   `short-session-still-updates` und `abrupt-end-still-updates` ergänzt.
5. **Anmerkung — doppelte Themen-Slugs, nicht behoben.** Bleibt als dokumentierte
   Grenze in `docs/known-limits.md` stehen (kein beobachtbares Fehlverhalten,
   nur ein unterspezifizierter Update-Fall bei manuellem Copy-Paste-Fehler in
   `learner.md`).

`docs/known-limits.md` wurde um einen Abschnitt „learning-coach" ergänzt, der die
Fixes 1/2 sowie die verbleibende Unschärfe aus Fund 3 (Top-Level-Form-Annahme) und
die unbehobene Anmerkung (Fund 5) festhält.

## Fix-Runde 2 — Schnittstelle gegen den echten Erzeuger geprüft

Die in Fix-Runde 1 dokumentierte Unschärfe (Top-Level-Form von `*.exercises.json`
eine Ableitung aus Spec 13, nicht bestätigt) war berechtigt: Der Koordinator prüfte
sie gegen `exercise-forge`s tatsächlichen Code (`export.py:254`,
`data.get("exercises", [])`) und fand einen echten Defekt. Die angenommene
Top-Level-Form war falsch — der reale Erzeuger schreibt ein JSON-**Objekt** mit
`"exercises"`-Liste, kein Top-Level-Array. Mit der ursprünglichen Annahme hätte
`due_topics.py` **jede** real erzeugte Aufgabendatei als `malformed` gemeldet und
den Nutzer fälschlich vor kaputten Daten gewarnt, die in Ordnung sind.

Weder ich noch der Autor von exercise-forge konnten das beim parallelen Bauen sehen
— beide Testsuiten liefen grün, weil jede gegen ihre eigene Annahme prüfte. Der Fix
gehört laut Koordinator zu `learning-coach` (die bessere Form mit Metadaten-Spielraum
bleibt bei exercise-forge): `exercises_status()` erwartet jetzt ein Objekt mit
`"exercises"`-Schlüssel, dessen Wert eine Liste ist; fehlt der Schlüssel oder ist er
keine Liste, bleibt es `malformed` (die konservative A4-Haltung selbst war richtig,
nur die angenommene Form falsch). Der Inhalt der einzelnen Aufgaben-Objekte bleibt
weiterhin ungeprüft — das war nie der strittige Punkt.

Sechs Tests zu `exercises_status()` ersetzt/ergänzt (u. a. ein Test mit einer
realistischen Exporter-Form inklusive Metadaten-Feldern neben `"exercises"`), die
Fixture `lc-broken-exercises` und der zugehörige Eval
`empty-exercises-file-is-named-not-hidden` auf die korrigierte Form umgestellt.
`due_topics.py` manuell gegen die korrigierte Fixture verifiziert (siehe
„Testergebnis").

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
überschreibbar nach demselben Muster) und prüft Existenz **und grobe Struktur**
(`exercises_status()`, nachgerüstet in Fix-Runde 1, Top-Level-Form in Fix-Runde 2
korrigiert — siehe oben): fehlend, leer (`"exercises"`-Liste ohne Einträge) und
strukturell unerwartet (kein gültiges JSON-Objekt, oder `"exercises"` fehlt/ist
keine Liste) ergeben alle dieselbe Reaktion. Der Inhalt der einzelnen Aufgaben wird
nicht geparst, weil die genauen Feldnamen des Aufgaben-Schemas von exercise-forge
nicht bekannt sind (A4: was nicht sicher bekannt ist, wird nicht angenommen) — die
Top-Level-Form (`{"exercises": [...]}`) ist dagegen gegen den echten Erzeuger
verifiziert (`export.py:254`, `data.get("exercises", [])`), keine Ableitung mehr
(siehe `docs/known-limits.md`, Abschnitt „learning-coach"). In jedem der drei
Nicht-Erfolgsfälle meldet die Skill wörtlich **„Keine verifizierten Aufgaben
gefunden"** und schlägt vor, exercise-forge aufzurufen — als SKILL.md-Contract
mandatiert, damit der zugehörige Eval mechanisch (`output_matches`, kein Judge)
bleibt.

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

Neun Evals nach der Fix-Runde, fünf `contract` (mechanisch) und vier `behavior`
(Judge). Schema lokal gegen `evalkit.schema.load_evals` validiert (lädt sauber,
keine `EvalSchemaError`). Alle sechs Fixtures gegen `evalkit.workspace.prepare()`
probegebaut — jede liefert ein lesbares `.skills/learning-coach/learner.md` im
Workspace, `due_topics.py` läuft gegen jede Fixture direkt durch (manuell mit
`--today 2026-08-17` verifiziert, inklusive der exakten Phrase „Keine verifizierten
Aufgaben gefunden" für sowohl die fehlende als auch die leere Aufgaben-Datei).

- **Anti-Zeremonie (Pflicht, Spec 00 §2):** `nothing-due-stays-honest` — nichts
  fällig, `learner.md` muss `file_unchanged` bleiben, kein erfundenes Quiz. Nach
  der Fix-Runde `class: behavior` mit Judge-Claim statt einer zu engen Regex
  (Details oben, „Fix-Runde").
- Vier weitere `contract`-Evals hängen an `must_not: file_unchanged`, `artifact_header`
  oder der mandatierten Phrase — beides Artefakte/Wortlaut, die nur diese Skill
  kennt (A6): 16 fremde Skills im Eval-Agenten wüssten weder von
  `.skills/learning-coach/` noch von der exakten Phrase.
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
186 passed in 3.18s
```

(146 ursprünglich bestehende Tests + 40 neue für `due_topics.py`, davon 9 aus den
beiden Fix-Runden für `exercises_status()` — 6 aus Runde 1, netto 3 weitere aus
Runde 2 nach der Korrektur der Top-Level-Form — keine Regression.)

## Offene Sorgen

- `brief-common.md` fehlte (siehe oben) — unklar, ob dort zusätzliche verbindliche
  Vorgaben standen, die hier nicht berücksichtigt sind.
- Die neun Evals sind ungelaufen; ob die SKILL.md-Doktrin (harte Hinweis-Leiter,
  Update-Pflicht, exakte Phrase) einen echten Agenten tatsächlich lenkt, ist nicht
  gezeigt, nur plausibilisiert — das gilt insbesondere für die beiden in der
  Fix-Runde umgebauten Evals, die noch nie gegen einen echten Agenten liefen.
- Die Top-Level-Form von `exercises_status()` ist jetzt gegen `exercise-forge`s
  echten Code verifiziert (`export.py:254`, siehe Fix-Runde 2), nicht mehr nur
  eine Ableitung aus Spec 13 — das war der eine echte Defekt in der vorherigen
  Fassung. Der Inhalt der einzelnen Aufgaben-Objekte innerhalb von `"exercises"`
  bleibt weiterhin ungeprüft (bewusst, A4); sollte sich diese innere Form später
  als für `learner.md`/die Session relevant erweisen (z. B. Bloom-Ebene fürs
  gezielte Anfordern „eine Stufe schwerer"), ist das ein separater, noch nicht
  abgesicherter Punkt.
- Doppelte Themen-Slugs bleiben unaufgelöst (Anmerkung, bewusst nicht behoben).
- Die Schnittstelle zu exercise-forge (Spec 13) ist nur über den dokumentierten Pfad
  und Existenzprüfung abgesichert — sobald Spec 13 fertig ist, lohnt ein Integrations-
  Check, ob das tatsächliche Aufgaben-JSON die in Spec 13 versprochenen Felder (Typ,
  Lernziel, Schwierigkeit, Verifikations-Protokoll) wirklich trägt.
- README-Routing-Tabelle wurde bewusst nicht angefasst (mehrere parallele Branches
  ändern potenziell dieselbe Datei; nicht Teil des Auftrags).
