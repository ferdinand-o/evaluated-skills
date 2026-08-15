# Abschlussbericht: Skill `verified-research`

Spec: `specs/Spec 12 – verified-research.md`, gebunden an `specs/Spec 00 – skill-foundation.md`.
Branch: `feat/verified-research`, Basis: `0831fb7`.
Plan: `docs/superpowers/plans/2026-08-15-verified-research.md`.

## Was gebaut wurde

```
skills/verified-research/
├── SKILL.md                       (81 Zeilen, Frontmatter nur name/description)
├── references/
│   ├── rating-rubric.md           (fünf Kriterien, Einstufungs-Leitfaden Tier 1-3)
│   ├── research-types.md          (adaptiert aus samber/deep-research, mit Attribution)
│   └── delta-mode.md              (Wissensdatei-Schema, Differenz-Ablauf, 30-Themen-Warnung)
├── assets/registry.json           (31 kuratierte Einträge, vier Domänen + allgemein)
└── scripts/
    ├── registry.py                (Tier 1, Lookup/Add/Bootstrap, 29 Unit-Tests)
    └── spotcheck.py                (Tier 1, Stichprobenauswahl, 16 Unit-Tests)
evals/verified-research/evals.json  (7 Evals, alle Klasse contract)
evals/fixtures/vr-*/                (7 lokale Fixtures, keine Websuche nötig)
tests/test_verified_research_registry.py, tests/test_verified_research_spotcheck.py
```

45 neue Unit-Tests, alle grün. Gesamtsuite: 191 von 191 bestanden
(146 bestehende + 45 neue), inklusive der 146 bestehenden aus dem Auftrag.

## R7 — Register als registry.json (Tier 1)

`registry.py` kapselt jeden Zugriff (`load_registry`, `save_registry`, `lookup`,
`add_entry`, `ensure_registry`). Jeder Eintrag trägt `pattern`/`name`/`tier`/`notiz`.
`add_entry()` erzwingt mechanisch, dass `notiz` mindestens eines der fünf
Rubrik-Kriterien (`RUBRIC_KEYWORDS`, an `rating-rubric.md` angelehnt) beim Namen
nennt, mindestens 15 Zeichen lang ist, und dass `tier` in {1,2,3} liegt — eine
`notiz` wie „wirkt seriös" wird mit `RegistryError` abgelehnt (getestet). Doppelte
`pattern`s in derselben Domäne werden abgewiesen (case-insensitiv).

`assets/registry.json` enthält 31 Einträge über `software-tech` (8),
`recht-steuern-de-eu` (6), `wissenschaft` (7), `wirtschaft-statistik` (7) und
`allgemein` (8, moderat verschoben durch Rundung — genaue Zahl im Code, nicht
kritisch für den Contract).

## R9 — spotcheck.py-Quote

`SPOTCHECK_REST_QUOTA = 1/3`, `SPOTCHECK_MIN_SAMPLE = 1`, `SPOTCHECK_SEED` als benannte
Konstanten. Kritische Claims sind immer in der Stichprobe; vom Rest wird
`math.floor(len(rest) * SPOTCHECK_REST_QUOTA)` gezogen (seed-basiert, damit dieselbe
Eingabe reproduzierbar dieselbe Stichprobe liefert — wichtig für Eval-Determinismus).

**Eine Korrektur gegenüber dem Auftragstext:** R9 nennt „bei drei unkritischen Claims"
als Beispiel, bei dem ohne Minimum-Regel nichts geprüft würde. Das stimmt numerisch
nicht — `3 * (1/3)` rundet in IEEE-754-double exakt auf `1.0`, `math.floor` liefert
also `1`, nicht `0`. Der tatsächliche Grenzfall liegt bei **ein oder zwei** übrig
gebliebenen unkritischen Claims (`math.floor(1 * (1/3)) == math.floor(2 * (1/3)) == 0`).
Ich habe Code-Kommentar und Tests entsprechend korrigiert und zusätzlich einen
Gegenprobe-Test geschrieben, der zeigt, dass bei genau drei Claims die Quote schon ohne
Minimum-Regel greift. Die *funktionale* Anforderung (Minimum verhindert eine leere
Stichprobe bei vorhandenen Claims) ist unverändert erfüllt und getestet.

## R10 — Wissensdatei flach

`delta-mode.md` legt eine Datei pro Thema fest, `registry.py topics` zählt
`*.md`-Dateien unter `research/` und liefert ab `TOPIC_WARNING_THRESHOLD = 30` eine
Warnung ohne automatische Umgliederung (getestet: unter/über Schwelle).

## R8 — Evals ohne Websuche

Alle 7 Evals sind Klasse `contract`, keiner braucht `WebSearch`/`WebFetch`. Jede
Fixture bringt ihre eigenen lokalen „Quellen" unter `sources/` mit; die Prompts
instruieren explizit „nutze ausschließlich lokale Dateien, keine Websuche". Ich habe
`registry.py` und `spotcheck.py` gegen mehrere Fixtures manuell probegefahren (siehe
Terminal-Log dieser Session), um zu verifizieren, dass die Assertions tatsächlich zum
erwarteten Skill-Verhalten passen — z. B. dass `spotcheck.py` gegen
`vr-spotcheck-trap` exakt den kritischen Claim mit der falschen Zahl in die Stichprobe
zieht, und dass `registry.py add` gegen `vr-unknown-source` einen Eintrag erzeugt, der
die zweite, positionsabhängige Regex-Assertion tatsächlich erfüllt.

Was ich **nicht** verifizieren konnte: ob ein echter Claude-Agent, der SKILL.md liest
und den Prompt bekommt, sich tatsächlich an den mandatierten Claim-Tag-Contract hält
(`[Tier N, kritisch, Quelle: ...]`, „Nur Sekundärquellen gefunden",
„VERWORFEN nach Spotcheck", `## Bekannt`/`## Neu`). Das kann nur ein echter
`run_evals.py`-Lauf zeigen, den ich laut Auftrag nicht ausführen durfte.

## R11 — Nicht an deep-research-Ergebnisqualität hängen

Jeder der 7 Evals trägt im `notes`-Feld einen Satz, der begründet, warum
`deep-research` dieselbe Assertion nicht hätte erfüllen können — entweder weil das
geprüfte Artefakt (Registerdatei mit `notiz`, Wissensdatei-Kopfzeile,
`.skills/cache/verified-research-spotcheck.json`) nur bei `verified-research`
entsteht, oder weil der geprüfte Text (Registereintrags-Name, exakte Tag-Syntax, exakte
Pflichtphrasen) frei erfunden bzw. skill-eigenes Vokabular ist, das `deep-research`
nicht kennt. Am stärksten ist das bei `registry-consulted-before-free-search`
(der Registereintragsname `Fixture-Primärdokumentation Internes Tool` ist nicht
erratbar) und `spotcheck-catches-numeric-trap` (der Pfad
`.skills/cache/verified-research-spotcheck.json` existiert überhaupt nur, wenn
`spotcheck.py` gelaufen ist). Am schwächsten ist vermutlich
`fresh-topic-updates-knowledge-file` — ein sehr befähigter Agent unter `deep-research`
könnte theoretisch spontan eine ähnliche Markdown-Datei mit Tier-Tag anlegen, wenn der
Prompt es nahelegt; die Kopfzeilen-Konvention (`skill: verified-research | schema: 1`)
macht das aber unwahrscheinlich, weil sie `deep-research` nirgends bekannt ist.

## Zusätzliche Entscheidungen, die ich treffen musste

1. **Verzeichnis- statt Datei-Ebene für den Projekt-Override** (dokumentiert in
   `docs/known-limits.md`, Abschnitt „verified-research"). Spec 00 §1 sagt wörtlich
   „gleichnamige Datei" — das würde für `research/<thema>.md` beim allerersten Lauf zu
   jedem neuen Thema nie greifen und ins echte Home-Verzeichnis des Aufrufers schreiben.
   `resolve_base_dir()` prüft stattdessen, ob `.skills/verified-research/` als
   Verzeichnis existiert. Das ist eine Abweichung vom Wortlaut, die ich für notwendig
   halte, aber nicht selbst als „richtig" absegnen kann — ein Review sollte das bestätigen.
2. **Claim-Tag-Format als eigene Konvention erfunden.** Spec 12 beschreibt den
   Tier-Contract, aber kein konkretes Textformat für „jeder Claim trägt ein Tier". Ich
   habe `[Tier <1-3>{, kritisch}?, Quelle: <adresse>]` als Zeilenende-Tag festgelegt,
   weil es sowohl für Menschen lesbar als auch für `spotcheck.py` regex-parsbar ist.
   Das ist eine Erfindung dieser Implementierung, keine Vorgabe aus Spec 12.
3. **spotcheck.py schreibt eine Ephemera-Datei** (`.skills/cache/verified-research-spotcheck.json`),
   die Spec 12 nicht explizit nennt. Ohne sie hätte ich keine mechanische, deep-research-sichere
   Assertion für „hat spotcheck wirklich den kritischen Claim gezogen" gehabt — die Alternative
   wäre ein `judge`-Eval gewesen, was R8/R11 zusammen unattraktiv machen.
4. **Exakte Pflichtphrasen statt Judge-Bewertung.** „Nur Sekundärquellen gefunden" und
   „VERWORFEN nach Spotcheck" sind wörtliche Vorgaben in SKILL.md, damit die
   entsprechenden Evals mechanisch (`contract`, kein `judge`) bleiben können — das war
   nötig, um R8 und R11 gleichzeitig einzuhalten, engt aber die Skill stilistisch enger
   ein, als Spec 12 das vorschreibt.
5. **`tests/conftest.py` gefixt.** `load_script()` registrierte das geladene Modul
   bisher nicht in `sys.modules`, wodurch `@dataclass` in `spotcheck.py` mit
   `AttributeError: 'NoneType' object has no attribute '__dict__'` abstürzte
   (`dataclasses._is_type()` sucht `sys.modules[cls.__module__]`). Kleiner, generischer
   Fix im geteilten Test-Helfer, betrifft potenziell auch künftige Skills mit Dataclasses.

## Was ich nicht verifizieren konnte (gehört nach `docs/known-limits.md`, dort bereits eingetragen)

- Quellenauswahl im echten Web (R8-Grenze per Auftrag).
- Ob ein echter Agent den mandatierten Claim-Tag-/Pflichtphrasen-Contract tatsächlich
  einhält (nur durch `run_evals.py` zu zeigen, lief nicht).
- Ob die Description tatsächlich gegen `deep-research` gewinnt (siehe unten).
- Ob der Script-Pfad-Kontrakt (`skills/verified-research/scripts/...` vs. die
  tatsächliche Installation unter `.claude/skills/verified-research/...` im
  Eval-Workspace) im echten Lauf funktioniert — betrifft auch `dev-report`.
- Die Positionsabhängigkeit der zweiten `unknown-source-gets-registry-entry`-Assertion.

## Einschätzung zur Description gegen deep-research

Unsicher. Die Description nennt explizit Register, Tier-Nachvollziehbarkeit und
Gedächtnis über frühere Läufe als Unterscheidungsmerkmale und benutzt Trigger-Phrasen
wie „Tier-Bewertung der Quellen"/„Quellenregister" — das deckt sich mit den
Eval-Prompts, die dasselbe Vokabular bewusst benutzen, um die Auswahl in Richtung
`verified-research` zu lenken. Das ist aber eine Absicherung auf der Prompt-Seite, kein
Beleg, dass die Description bei einer *natürlicheren* Anfrage („recherchier mir doch
mal X") tatsächlich gewinnt — dort könnte `deep-research` mit seiner kürzeren,
allgemeineren Description leicht die Oberhand behalten, gerade weil `verified-research`
bewusst enger und anspruchsvoller beschrieben ist (Quellenqualität als Bedingung, nicht
als Bonus). Ich halte das für den größten ungetesteten Schwachpunkt dieser Skill und
schlage vor, genau das als ersten echten `run_evals.py`-Test zu behandeln, sobald
Kontingent dafür da ist — mit einem Eval, der bewusst *nicht* das Register-Vokabular in
den Prompt legt.

## Ehrlichkeit zu einem Commit

`36e44db` enthält neben der angekündigten Pfad-Konsistenz-Korrektur auch die
Evals/Fixtures aus Task 4/5, weil beide `git add`-Aufrufe vor dem Commit ausgeführt
wurden. Die Commit-Message beschreibt nur die Pfad-Korrektur — inhaltlich ist nichts
verloren gegangen (alle Dateien sind im Diff sichtbar), aber die Historie ist an dieser
Stelle ungenauer als beabsichtigt.
