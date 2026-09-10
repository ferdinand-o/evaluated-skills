# Evals schreiben — die Regeln, die der Harness nicht prüft

`evalkit/schema.py` prüft Form: gültige Assertion-Typen, ein Prompt je Eval, Judge nur
in `behavior`. Alles hier ist das, was das Schema durchlässt und das Repo trotzdem
teuer gelernt hat (`docs/known-limits.md`, Abschnitte „Stichprobe", „Judge", „Fixtures";
`docs/skill-building-pitfalls.md`, „In den Evals").

## Die Diskriminator-Frage

Jeder Eval beantwortet in `notes` eine Frage: **Könnte das Basismodell ohne diese Skill
dieselbe Ausgabe erzeugen?** Sechzehn fremde Skills sind im Harness sichtbar; eine
Assertion, die eine von ihnen genauso erfüllt, belegt nichts über deine. Die Antwort
steht wörtlich in `notes` mit dem Wort „Diskriminator", und sie nennt das Artefakt oder
den Token, an dem der Eval hängt:

- **Ein Artefakt, das nur diese Skill schreibt.** `gate.json` bei `subagent-dev`,
  `lint.json` bei `impl-plan` und `skill-forge`, die Kopfzeile
  `<!-- skill: impl-plan | … -->` in einem Plan. Ein Basismodell schreibt keine Datei
  mit diesem Namen an diesem Ort.
- **Ein wörtlicher Token aus der Doktrin.** `Next:`, `Unverified:`, `Source:` bei
  `explain`; die kanonischen Task-Titel `Evals`, `Nachbarn`, `known-limits`, `Report`
  bei `impl-plan`; das ID-Präfix `anti-ceremony-`. Ein Basismodell drückt dasselbe in
  anderen Worten aus.
- **Die Abwesenheit von etwas, das ohne Regel da wäre.** `must_not: output_matches
  "Next:"` bei `low` — ohne die Skill gibt es keine Regel, die den Anschlussblock
  verbietet, und keinen Grund, ihn so zu nennen.

Was **kein** Diskriminator ist: Kürze, Höflichkeit, Struktur, „guter Stil", ein
Vokabular, das die Fixture selbst vorgibt (eine Spec 00 in der Fixture, die `class`
und `must` nennt, macht `"class": "contract"` zum Abschreiben).

Lautet die Antwort „ja, könnte es", wird der Eval umgebaut oder gestrichen — nicht
weichgespült.

## Ein Claim, eine Bedingung

Zusammengesetzte Judge-Claims verdecken Defekte: „erkennt X und tut Y statt Z" wird
bejaht, sobald der Judge *eine* Bedingung erfüllt sieht, auch wenn die wichtigste
verletzt ist. Deshalb:

- **Ein Judge-Claim je Eval**, mit einer Zahl statt eines Adjektivs („höchstens sechs
  Sätze", nicht „kurz") — gemessen beurteilt ein Judge Kürze nur bei grober Verletzung
  zuverlässig.
- **Alles mechanisch Prüfbare ganz aus dem Judge heraus**: Existenz per `file_exists`,
  Wortlaut per `file_matches`/`output_matches`, Länge per `file_max_lines`. Der Judge
  bekommt nur, was kein Regex sieht.
- `lint_skill.py` meldet „ und ", „ UND ", „ statt ", „ sowie " im Claim als **`hint`**,
  nie als Befund: 24 von 47 Claims im Repo tragen eine Konjunktion, die meisten
  legitim („X statt Y" ist eine Bedingung). Der Hinweis heißt: einmal hinsehen, ob
  hier zwei Bedingungen verkettet sind.

## Fixture-Vorbedingungen

Die Fixture muss herstellen, was die Assertion voraussetzt — sonst ist der Eval rot
aus einem Grund, der nichts mit der Skill zu tun hat (sechs Evals auf einmal, einmal):

- **`"git": true`** in `fixture.json`, wenn die Skill committet oder eine Assertion
  `git_head_unchanged` nutzt. Ohne Repo landen Artefakte außerhalb des Workspace.
- **Nichts unter dem Glob, den die Skill schreibt.** `resolve_target` nimmt den
  alphabetisch ersten Treffer; bringt die Fixture eine Datei unter
  `docs/superpowers/plans/` mit, prüft der Eval die Fixture statt die Skill.
- **Nichts, was den Diskriminator vorsagt.** Eine gekürzte Spec 00 in der Fixture
  darf das Vokabular nicht enthalten, an dem der Eval hängt.
- **Minimal-synthetisch** (Spec 00 §2): die Falle enthalten, nicht Realismus beweisen.
  Zehn bis fünfzig Dateien, oft weniger.
- **Was im Eval-Workspace fehlt:** `evalkit/workspace.py::prepare()` kopiert nur das
  Skill-Verzeichnis nach `.claude/skills/<name>/` und die Fixture an die Wurzel. Kein
  `docs/`, kein `README.md`, keine fremde Skill. Ein Skript der eigenen Skill ist da;
  ein Skript einer anderen Skill nicht. Was der Lint dort nicht sieht, meldet er als
  `unchecked` — ein Eval darf nur an Regeln binden, die in seiner Fixture geprüft sind.

## Der Pflicht-Anti-Zeremonie-Eval

Spec 00 §2 verlangt ihn; `lint_skill.py` erkennt ihn am ID-Präfix `anti-ceremony-`. Er
prüft den trivialen Fall, in dem die Skill klein bleiben muss: der Tippfehler-Bug, der
Einzeltest, der Mini-Diff, der geänderte Satz. Seine Assertion hängt an einem Artefakt
(„lint.json sagt `evals_due: false`, und `evals.json` ist unverändert"), nie an einem
Stimmungsurteil über Kürze.

## Ein Ergebnis ist eine Stichprobe

Derselbe Eval, derselbe Commit: einmal rot, einmal grün — mehrfach belegt. Es schwankt,
ob eine Skill geladen wird, wie weit sie ihren Ablauf durchläuft, ob ein Judge zustimmt.
**Vor jeder Fix-Runde ein zweiter Lauf**, sonst repariert man eine funktionierende
Skill. Routing-Evals (Prompt ohne Skill-Namen) sind die stochastischsten: Ein roter
Lauf zeigt eine Kollision, ein grüner beweist nichts.

## Trigger-Eval-Set — wenn der Harness läuft

Aus Anthropics `skill-creator` übernommen, hier als Vorgehen für den Tag, an dem der
Harness außerhalb eines Root-Containers läuft (`docs/known-limits.md`, „Betrieb"):

1. **Zwanzig realistische Anfragen** in der Sprache des Nutzers, ohne Skill-Namen. Acht
   bis zehn davon sind **Beinahe-Treffer**, die *nicht* auslösen dürfen — für
   `skill-forge` etwa „schreib mir eine Skill-Beschreibung für die Stellenanzeige",
   „welche Skills hat das Repo", „bau mir ein Skript".
2. Je Anfrage ein Lauf; gezählt wird, ob die Skill geladen wurde (Transcript), nicht ob
   die Ausgabe gut war.
3. Description ändern, wiederholen. Zwei Descriptions gegeneinander mit je fünf
   Wiederholungen — die Varianz ist die Metrik, nicht der Mittelwert.

Bis dahin bleibt jede Aussage über Trigger Lektüre und Annahme, und der Report sagt
das unter „Was nicht gemessen wurde".

## Baseline ohne Skill — die Forderung

Die Diskriminator-Frage wird heute *beantwortet*, nicht *gemessen*. Ein
`--without-skill`-Flag in `evals/run_evals.py` (derselbe Prompt, dieselbe Fixture,
ohne installierte Skill) wäre die billigste Harness-Erweiterung mit dem größten
Erkenntnisgewinn: Ein Eval, der ohne Skill genauso grün ist, misst nichts. Das ist eine
eigene, kleine Spec; diese Skill fordert sie in `known-limits` ein und wartet nicht
darauf.
