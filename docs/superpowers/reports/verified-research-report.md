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

53 neue Unit-Tests, alle grün (45 aus der Erstimplementierung, 8 aus der Fix-Runde für
die Register-Grenzprüfung). Gesamtsuite: 199 von 199 bestanden (146 bestehende + 53 neue).

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
   `docs/known-limits.md`, Abschnitt „verified-research"). **Korrektur nach Review:**
   Ich hatte das ursprünglich als wörtliches Zitat aus Spec 00 §1 dargestellt
   („falls eine gleichnamige Datei im Repo liegt"). Das steht dort nicht — Spec 00 §1
   sagt nur „mit optionalem Projekt-Override — dasselbe Muster wie persönliche vs.
   Projekt-Skills" und nennt keine Bedingung dafür, wann der Override greift. Die
   Formulierung stammt aus dem Auftrag/aus Spec 12s Paraphrase, nicht aus Spec 00
   selbst; ich habe die Paraphrase für den Wortlaut gehalten, statt es an der Quelle
   zu prüfen. `resolve_base_dir()` prüft, ob `.skills/verified-research/` als
   Verzeichnis existiert — das ist **meine eigene Entscheidung**, keine Spec-00-Regel:
   Ein Override auf Datei-Ebene würde für `research/<thema>.md` beim allerersten Lauf
   zu jedem neuen Thema nie greifen und ins echte Home-Verzeichnis des Aufrufers
   schreiben. Die Verzeichnis-Prüfung selbst halte ich weiterhin für richtig, nur trug
   die ursprüngliche Begründung sie fälschlich als Zitat statt als eigene Ableitung.
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

## Fix-Runde (nach unabhängigem Review)

Ein unabhängiger Reviewer hat drei Defekte gefunden, zwei davon mechanisch nachprüfbar,
einer war eine Zitat-Verfälschung; alle drei sind behoben.

**1. `lookup()` matchte reinen Teilstring statt Host-/Pfad-Grenzen.** Das Muster `"ir."`
(gedacht als Präfix für Investor-Relations-Subdomains) klassifizierte `elixir.example.com`
und `kefir.example.blog` als Tier-1-Primärquellen — die Buchstabenfolge kam zufällig vor,
ohne dass jemand die Domain bewertet hätte. `registry.py` hat jetzt `_boundary_pattern()`:
ein alphanumerisches Randzeichen des Musters darf nicht mitten in einem längeren
alphanumerischen Lauf der Zielzeichenkette stecken; ein Muster, dessen Rand schon ein
Trennzeichen ist (`-vergleich.de`), bekommt an der Seite keine zusätzliche Grenze, weil
die Absicht (Suffix-Wildcard innerhalb eines Labels) sonst kaputtginge.

Ich habe das **ganze Register** (36 Muster in `assets/registry.json`) programmatisch
gegen adversariale Nachbarschaft geprüft (jedes Muster mit einem alphanumerischen Zeichen
direkt davor bzw. danach verklebt) — 68 der so erzeugten Fälle waren unter dem alten
Teilstring-Vergleich falsch-positiv und sind jetzt korrekt abgelehnt, ohne einen der
beabsichtigten Treffer zu verlieren (`arxiv.org` exakt, `-vergleich.de` als
Label-Suffix, `github.com`/`docs.python.org` mit Pfad, `ir.` am String-Anfang und nach
Schema-Präfix bleiben alle erhalten). Zwei zusätzliche reale Fälle über den gemeldeten
hinaus: `dev.to` matchte als Teilstring in `avdev.today`, und — der bemerkenswertere
Fund — `arxiv.org` matchte als Teilstring in `chemarxiv.org`, einem eigenständigen,
anderen Preprint-Server (ChemRxiv), der dadurch fälschlich arXivs Tier-1-Bewertung geerbt
hätte. Acht neue Tests in `tests/test_verified_research_registry.py` decken die
Grenzfälle ab, darunter `elixir.example.com` als expliziter Negativfall wie vom Reviewer
verlangt, sowie `chemarxiv.org` als zweiter dokumentierter Fund.

**2. Eval-Regex strenger als der Parser, den sie prüft.** `critical-claim-tier3-only-flagged`
verlangte exakt ein Leerzeichen nach dem Komma vor „kritisch", während `spotcheck.py`
mit `,\s*kritisch` parst (`evals/verified-research/evals.json`, `must`/`must_not`). Beide
Assertions sind jetzt auf `\s*` statt festem Leerzeichen umgestellt, ebenso die drei
übrigen Stellen, die `[Tier N`/`[Tier [1-3]` ohne diese Toleranz prüften — dieselbe
Bugklasse hätte dort baugleich zuschlagen können, auch wenn nur eine Stelle konkret
gemeldet wurde.

**3. Falsches Spec-00-Zitat an vier Stellen.** `registry.py`, `docs/known-limits.md`,
der Plan und dieser Bericht behaupteten, Spec 00 §1 sage wörtlich „falls eine
gleichnamige Datei im Repo liegt". Das steht dort nicht — Spec 00 §1 sagt nur „mit
optionalem Projekt-Override — dasselbe Muster wie persönliche vs. Projekt-Skills" und
trifft keine Aussage darüber, wann der Override greift. Alle vier Stellen sind
umformuliert: Sie sagen jetzt, was Spec 00 tatsächlich vorgibt, und dass die
Verzeichnis-Ebene meine eigene, begründete Entscheidung ist — nicht aus Spec 00
zitiert. Die Verzeichnis-Prüfung selbst bleibt unverändert; nur ihre Begründung war
falsch attribuiert.

Alle Tests grün (199, siehe unten), `evalkit.schema.load_evals` validiert die 7 Evals
weiterhin fehlerfrei. `run_evals.py` wurde weiterhin nicht ausgeführt.
