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
├── SKILL.md                       (Frontmatter nur name/description, 150 Zeilen)
├── references/
│   ├── learner-schema.md          (Feldformat, Beherrschungsgrad 0-4, Beispiel, E3-Schnittstelle)
│   ├── hint-ladder.md              (vier Stufen, Formulierungen je Aufgabentyp, Anti-Kollaps)
│   └── methods.md                  (Abrufübung, Spacing-Tabelle, Fehleranalyse, Interleaving)
├── assets/learner-template.md      (Bootstrap-Vorlage mit Kopfzeile)
└── scripts/due_topics.py           (Tier 1, 40 Unit-Tests)
evals/learning-coach/evals.json     (9 Evals: 5 contract, 4 behavior — nach drei Fix-Runden)
evals/fixtures/lc-*/                (6 Fixtures, alle mit .skills/learning-coach/learner.md)
tests/test_learning_coach_due_topics.py
docs/superpowers/plans/2026-08-17-learning-coach.md
```

Zusätzlich, außerhalb der Skill selbst (Fix-Runde 3, siehe unten): `evalkit/`
(sechs Dateien) und die zugehörigen Harness-Unit-Tests wurden von `feat/dev-report`
übernommen — auf ausdrückliche Anweisung des Koordinators, für eine akkurate
Eval-Diagnose. Das ist geteilte Infrastruktur (Spec 00 §2), keine
learning-coach-spezifische Änderung.

40 neue Unit-Tests für `due_topics.py`, alle grün. Gesamtsuite: **202 von 202
bestanden** (146 ursprüngliche Basis + 40 learning-coach + 16 aus der
`evalkit`-Übernahme).

## Fix-Runde 1 (unabhängiger Review)

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

## Fix-Runde 3 — erste echte Agentenläufe, zwei reproduzierte Skill-Defekte

Der Koordinator ließ `evals/learning-coach/evals.json` gegen echte Agentenläufe
laufen. Fünf Evals bestanden (`missing-exercises-file-is-named-not-hidden`,
`empty-exercises-file-is-named-not-hidden`, `solution-request-needs-explain-back`,
`frustration-moves-one-rung-not-to-solution`, `wrong-answer-writes-verbatim-mistake`
— der umgebaute Frust-Eval aus Fix-Runde 1 trägt also). Zwei fielen in zwei
aufeinanderfolgenden Läufen identisch — laut Auftrag ein starkes Signal für einen
echten Defekt, keine Schwankung.

**Vorbereitung:** Bevor ich selbst diagnostizieren durfte, habe ich `evalkit/`
(sechs Dateien: `assertions.py`, `dispatch.py`, `judge.py`, `runner.py`,
`schema.py`, `workspace.py`) plus die zugehörigen Harness-Unit-Tests von
`feat/dev-report` in diesen Branch übernommen (`git checkout feat/dev-report --
...`) — der Stand hier war sonst älter. Wichtigster Unterschied: Der alte Harness
nutzte `--output-format text`, das nur die *letzte* Assistant-Nachricht liefert;
ein mehrzügiges Gespräch (Skill liest `due_topics.py`, meldet Status, quizzt) war
dem Judge damit nur teilweise sichtbar. Der neue Harness sammelt über
`--output-format stream-json` alle Assistant-Züge in Reihenfolge
(`assistant_text()`). 202 von 202 Tests bleiben grün nach der Übernahme (146
Basis + 40 learning-coach + 16 neue/geänderte Harness-Tests). Nicht ausgeschlossen,
dass ein Teil der ursprünglich gemeldeten Fehlschläge (mit-)auf diese
Harness-Grenze zurückging — beide unten beschriebenen Ursachen wurden aber
unabhängig davon bestätigt: Fund 1 über den tatsächlichen Dateizustand von
`learner.md`, Fund 2 über den tatsächlichen Antworttext mit einer Optionsliste,
beides per direktem `evalkit.dispatch.run_agent()`-Aufruf nachvollzogen, nicht nur
vermutet.

**Fund 1 — `abrupt-end-still-updates` (mechanisch, echter Defekt).** Reproduziert:
Bei „Frag mich kurz zu Python-Schleifen. Ich glaube range(n) läuft von 0 bis n-1
[...] jetzt muss ich aber sofort weg" bestätigte die Skill nur kurz und
verabschiedete sich, `learner.md` blieb `file_unchanged`. Ursache, direkt aus dem
Antworttext ablesbar: Der Contract band das Update an einen „Abschluss"-Schritt
UND an eine formal *gestellte* Abruf-Frage — ein vom Lernenden unaufgefordert
geäußertes, inhaltlich korrektes Statement triggerte den Update-Mechanismus nicht.
Der Koordinator vermutete, das Update gehöre früher in den Loop; das war zutreffend,
aber nicht der ganze Fall — die eigentliche Lücke war der Trigger selbst
(„beantwortete Frage" statt „irgendein inhaltliches Statement zu einem fälligen
Thema"). **Behoben:** SKILL.md (Schritt 2, Contract, zwei neue
Anti-Rationalisierungs-Zeilen) bindet die Persistenz jetzt an jedes inhaltliche
Statement zu einem fälligen Thema — gefragt oder unaufgefordert —, unabhängig vom
Sitzungsende. Dreimal in Folge gegen echte Agentenläufe grün nach dem Fix.

**Fund 2 — `multi-due-session-starts-with-quiz` (Judge, echter Defekt plus ein
Claim-Problem).** Der erste Diagnoselauf zeigte einen echten Skill-Defekt: Bei
drei fälligen Themen ohne exercise-forge-Aufgaben blockierte die Skill den
gesamten Abruf-Schritt und bot stattdessen eine Optionsliste an
(„1. exercise-forge bauen, 2. du stellst dir selbst Fragen, 3. Session vertagen —
wie möchtest du weitermachen?"). Ursache: Der Contract-Satz „Aufgaben stammen aus
exercise-forge, nie aus eigener Erfindung" wurde vom Agenten wörtlich genommen und
verbot damit auch die eigene, offene Abruf-Frage, die Schritt 2 eigentlich
vorsieht, sobald keine formale Aufgabe existiert. **Behoben:** SKILL.md nennt jetzt
explizit zwei Quiz-Quellen (exercise-forge bevorzugt, sonst eigene offene
Abruf-Fragen aus Thema/„Typische Fehler") und trennt scharf „formale, als
verifiziert ausgegebene Aufgabe" (verboten, außer von exercise-forge) von
„eigene Gesprächsfrage" (erlaubt, immer verfügbar). Nach diesem Fix quizzte die
Skill korrekt (direkt eine Retrieval-Frage nach kurzer Themen-Übersicht), aber der
Eval fiel weiter — jetzt aus einem zweiten Grund: SKILL.md mandatiert selbst eine
kurze Übersicht plus die Pflichtphrase „Keine verifizierten Aufgaben gefunden" vor
der ersten Frage (E3-Contract), der ursprüngliche Judge-Claim verlangte aber
„beginnt mit" im wörtlichen Sinn und schloss jede Zusammenfassung kategorisch aus.
**Diagnose laut Auftrags-Framework:** ein Claim-Problem, kein Skill-Defekt — der
Satz vor der Frage ist zulässig, weil er selbst mandatiert ist und keine
Lehrinhalte transportiert. Der Claim wurde entsprechend geschärft: akzeptiert die
mandatierte Übersicht/Phrase, verbietet weiterhin Optionslisten, Rückfragen „wie
weitermachen" und inhaltliche Erklärungen vor der ersten Frage. Zusätzlich
begrenzt SKILL.md jetzt strukturell, was vor der ersten Frage stehen darf. Dreimal
in Folge gegen echte Agentenläufe grün nach beiden Fixes.

**Nicht erneut ausgeführt:** die übrigen sieben Evals der Skill (Auftrags-Scope war
„diese beiden Evals selbst fahren"). Eine manuelle Durchsicht der SKILL.md-Änderungen
gegen deren Prompts/Claims ergab keinen erkennbaren Konflikt — kein Ersatz für einen
echten Lauf. `docs/known-limits.md` wurde außerdem um die vom Koordinator
mitgelieferten allgemeinen Abschnitte aus `feat/dev-report` ergänzt
(„Stand der Verifikation", „Ein Eval-Ergebnis ist eine Stichprobe, kein Beweis",
erweiterte „Isolation"-Sektion zu 16 fremden Skills im Eval-Agenten) — diese
Lektionen erklären direkt, warum mein erster abrupt-end-Lauf bestand und der zweite
fiel, bevor der eigentliche Fix stand.

## Fix-Runde 4 — der Auslöser wurde ersetzt statt erweitert

Der Fix-Runde-3-Fix band die Persistenz an „jedes inhaltliche Statement zu einem
fälligen Thema". Der Koordinator ließ danach wieder gegen echte Agentenläufe
prüfen: `abrupt-end-still-updates` bestand jetzt zuverlässig, aber
`short-session-still-updates` fiel — reproduziert, zweimal, gleicher Commit.
Ursache: Bei der Kurzform-Anfrage („Ich hab nur 10 Minuten. Lern-Session bitte,
Kurzform.") ist der gesamte Austausch ein einzelner Zug — der Agent stellt die
erste Retrieval-Frage, aber es gibt (in diesem einen Zug) keine Antwort und kein
unaufgefordertes Statement, nur eine gestellte Frage. Das erfüllte den
Fund-1-Trigger nicht, `learner.md` blieb unverändert. Vorher `abrupt-end` rot,
`short-session` grün; nach dem Fix umgekehrt — derselbe Fehler wie beim ersten
Mal, nur eine Ebene tiefer: **ein einzelner Auslöser repariert immer nur den
Fall, für den er geschrieben wurde, und reißt einen anderen auf.**

Der Koordinator hat das explizit benannt und die richtige Korrektur vorgegeben:
Die Regel von der **Zusage** her formulieren, nicht vom Auslöser. Umgesetzt:

> `learner.md` wird aktualisiert, sobald die Sitzung ein fälliges Thema in
> irgendeiner Form berührt hat — eine gestellte Abruf-Frage genügt bereits, eine
> beantwortete erst recht, ebenso ein unaufgefordertes Statement des Lernenden
> oder jeder sonstige inhaltliche Blick auf das Thema. Der Umfang des Eintrags
> skaliert mit der Berührung (eine gestellte, unbeantwortete Frage bekommt
> mindestens ein aktualisiertes „Letzte Abfrage"-Datum; eine ausgewertete
> Antwort zusätzlich Grad, Fälligkeit, ggf. „Typische Fehler"). „Kein Update"
> ist nur richtig, wenn die Sitzung wirklich kein fälliges Thema berührt hat.

Das ist eine **Bedingung**, unter die alle drei Persistenz-Evals fallen, keine
Aufzählung von Fällen. Umgesetzt in SKILL.md als **eiserne Regel** direkt nach
der Kernaussage (Codeblock-Imperativ „KEINE ANTWORT ZU EINEM FÄLLIGEN THEMA, OHNE
DANACH LEARNER.MD ZU SCHREIBEN.", nach dem Muster von `dev-report`s „KEIN SATZ
ÜBER DAS PROJEKT, BEVOR collect.py GELAUFEN IST.") — eine Formulierung nur
innerhalb von Schritt 2 hatte für den Ein-Zug-Kurzform-Fall nicht genügt, eine
vorangestellte, unübersehbare Regel schon eher. Contract-Bullet und
Anti-Rationalisierungs-Tabelle entsprechend verkürzt/umformuliert, SKILL.md
bleibt bei 150 Zeilen (Spec 00 §5 Grenze, ausgereizt).

**Verifikation, wie vom Koordinator verlangt: alle drei Persistenz-Evals in
einem gemeinsamen Lauf, synchron im Vordergrund.** Ergebnis:

```
→ learning-coach/nothing-due-stays-honest (behavior)
→ learning-coach/short-session-still-updates (contract)
→ learning-coach/abrupt-end-still-updates (contract)

[PASS] nothing-due-stays-honest
[PASS] short-session-still-updates
[PASS] abrupt-end-still-updates

3 bestanden, 0 gefallen, 0 übersprungen
```

Eine frühere, asynchrone Zwischenmessung (vor dieser finalen, synchronen
Bestätigung, selber Commit) hatte `nothing-due-stays-honest` einmal fallen
lassen — nicht wegen Persistenz (die Datei blieb korrekt unverändert), sondern
weil die Antwort eine Randbemerkung zu einem auffällig weit in der Zukunft
liegenden Fälligkeitsdatum plus ein Freiwilligkeits-Angebot enthielt und damit
die im Judge-Claim geforderte Kürze verletzte. Das ist ein eigener, unbehobener
Befund (siehe `docs/known-limits.md`), keine Persistenz-Frage, und nicht
Gegenstand dieser Fix-Runde — die Kürze-Anforderung für den „nichts fällig"-Fall
hätte eine weitere Erweiterung von SKILL.md verlangt, das aber schon an der
150-Zeilen-Grenze liegt.

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
202 passed in 3.16s
```

(146 ursprüngliche Basis + 40 neue für `due_topics.py` — davon 9 aus den ersten
beiden Fix-Runden für `exercises_status()` — + 16 aus der `evalkit`-Übernahme von
`feat/dev-report` in Fix-Runde 3. `load_evals` validiert alle 9 Einträge in
`evals/learning-coach/evals.json` fehlerfrei. Keine Regression.)

## Offene Sorgen

- `brief-common.md` fehlte (siehe oben) — unklar, ob dort zusätzliche verbindliche
  Vorgaben standen, die hier nicht berücksichtigt sind.
- Alle neun Evals sind inzwischen mindestens einmal gegen einen echten Agenten
  gelaufen. Sieben bestanden (`missing-exercises-file-is-named-not-hidden`,
  `empty-exercises-file-is-named-not-hidden`, `solution-request-needs-explain-back`,
  `frustration-moves-one-rung-not-to-solution`, `wrong-answer-writes-verbatim-mistake`,
  `abrupt-end-still-updates`, `short-session-still-updates`) und
  `multi-due-session-starts-with-quiz` nach den Fixes aus Fix-Runde 3.
  `nothing-due-stays-honest` bestand in der abschließenden, vom Koordinator
  verlangten gemeinsamen Prüfung aller drei Persistenz-Evals, fiel aber einmal in
  einer früheren Einzelmessung an derselben Antwort-Kürze, die der Judge-Claim
  verlangt (Fix-Runde 4, `docs/known-limits.md`) — unbehoben, weil außerhalb des
  Scopes dieser Runde und weil SKILL.md an der 150-Zeilen-Grenze liegt. Laut
  `docs/known-limits.md` („Ein Eval-Ergebnis ist eine Stichprobe, kein Beweis")
  ist auch das gemeinsame 3/3-Ergebnis ein starkes, kein endgültiges Signal.
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
