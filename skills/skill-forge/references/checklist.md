# Prüfliste je Bauphase — die 20 Punkte, und wer sie prüft

Destilliert aus `docs/skill-building-pitfalls.md`, `docs/known-limits.md` und den
Reports von fünfzehn Skill-Bauten (Prüfung `docs/assessment-writing-skills-writing-plans.md`
§4.3). **Mechanisch** heißt: `scripts/lint_skill.py` prüft es, die Regel-ID steht dabei.
**Ermessen** heißt: Niemand prüft es außer dir und dem Reviewer — dort steht die Frage,
die man sich stellt, kein Appell.

Lies nur den Abschnitt der Phase, in der du gerade bist. Die ganze Pitfalls-Datei ist
Lesestoff für den Anfang; diese Liste ist Werkzeug für den Moment.

## Phase Spec

| # | Punkt | Prüft | Quelle |
| --- | --- | --- | --- |
| 10 | Die Routing-Matrix in `README.md` und Spec 00 §5 kennt die Skill — in der Spalte „zuständig", nicht nur als „nicht" | mechanisch: `routing` | Spec 00 §5 |
| 15 | Erzeuger und Konsument jeder Schnittstelle liegen nebeneinander, bevor beide „fertig" heißen: Pfad *und* Form. Frage: Welche Datei liest ein Nachbar, und steht ihr Format in *beiden* Specs gleich? | Ermessen | Pitfalls „Über Schnittstellen"; zweimal gescheitert (learning-coach ↔ exercise-forge) |
| 18 | Der Contract verspricht nicht mehr, als sein Gate hält. Frage: Welcher Satz im Contract hat keinen Mechanismus hinter sich — und sagt er das? | Ermessen | Pitfalls „In der Doktrin"; Spec 00 §4 |

## Phase Plan

Der Plan ist Sache von `impl-plan` (16). Hier nur, was der Skill-Bau zusätzlich verlangt:

| # | Punkt | Prüft | Quelle |
| --- | --- | --- | --- |
| 6 | Ein Eval-Task mit ID-Präfix `anti-ceremony-` steht im Plan; bei Tier 0 vor der SKILL.md | mechanisch (Plan): `plan_to_tasks.py lint --spec` prüft nur, dass jede Eval-ID der Spec einen Task hat — das Präfix prüft erst `anti-ceremony-eval` an der fertigen Skill | Spec 00 §2; `impl-plan/references/task-patterns.md` |
| 19 | Der Skriptaufruf ist repo-relativ und scheitert installiert. Frage: Nennt die SKILL.md beide Pfade — `skills/<name>/scripts/…` und `.claude/skills/<name>/scripts/…`? | Ermessen (repo-weit ungelöst) | known-limits, learning-coach Fix-Runde 4; Spec 17 Entscheidung 4 |

## Phase Bau

| # | Punkt | Prüft | Quelle |
| --- | --- | --- | --- |
| 1 | Frontmatter nur `name` und `description` (optional `license`, `version`, `metadata`, `allowed-tools`) | mechanisch: `frontmatter` | Spec 00 §5 |
| 2 | SKILL.md ≤ 150 Zeilen; alles Weitere in `references/` | mechanisch: `skill-md-lines` | Spec 00 §5 |
| 3 | Die Description nennt Trigger und mindestens eine Abgrenzung („Not for …") und kein Prozessverb — was die Skill *tut*, steht im Body | mechanisch: `description` | Spec 00 §5 (Spec 17) |
| 4 | Kein „blockiert", „erzwingt", „stellt sicher" ohne `assets/hooks/` — G1 sagt „verlangt", G2 „meldet" | mechanisch: `gate-language` (absatzweise, Negation entkräftet) | Spec 00 §4 |
| 5 | Jedes Skript deklariert seinen Tier im Docstring; Tier 1 importiert nur Stdlib und Sibling-Skripte | mechanisch: `script-tier` | Spec 00 §3; Pitfalls „Analysier statisch, importier nicht" |
| 9 | Jedes Markdown-Asset trägt die Kopfzeile, oder seine Ausnahme steht in `docs/artifact-header.md` | mechanisch: `asset-headers` | `docs/artifact-header.md` |
| 16 | Jedes Beispiel gegen die Regel prüfen, unter der es steht. Frage: Folgt ein Agent, der nur das Beispiel liest, noch der Regel? | Ermessen | Pitfalls „Beispiele schlagen Vorschriften" |
| 17 | An jeder Stelle, die ein Urteil ausgibt: **Wo meldet etwas Erfolg, ohne geprüft zu haben?** `all([])`, null Treffer aus nichtleerer Eingabe, übersprungene Gates, `pass` statt `unchecked` | Ermessen — und `lint_skill.py` selbst ist das Beispiel: `unchecked` und `hint` zählen nie als `pass` | Pitfalls „Die eine Frage" |

## Phase Evals

| # | Punkt | Prüft | Quelle |
| --- | --- | --- | --- |
| 6 | `evals/<skill>/evals.json` existiert, lädt, und ein Eval trägt das Präfix `anti-ceremony-` | mechanisch: `evals-exist`, `anti-ceremony-eval` | Spec 00 §2 |
| 7 | Kein Judge-Claim mit Konjunktion — „und", „statt", „sowie" verketten Bedingungen, und die Kette ist milder als ihre Teile | mechanisch als Hinweis: `judge-claims` (`hint`, nie `finding`: 24 von 47 Claims im Repo tragen eine, die meisten legitim) | known-limits „Judge"; `references/evals.md` |
| 8 | Die Fixture stellt die Vorbedingung her: `"git": true` für `git_head_unchanged`, nichts unter dem Glob, den die Skill schreibt, jede genannte Fixture existiert | mechanisch (teilweise): `fixture-git` | known-limits „Fixtures" |
| 14 | Jede Assertion hängt an einem Artefakt oder Token, das **nur** diese Skill erzeugt. Frage: Könnte das Basismodell ohne die Skill dieselbe Ausgabe erzeugen? Wenn ja, misst der Eval nichts | Ermessen; `notes` beantwortet die Frage je Eval | known-limits, Pitfalls „Fremde Skills sind sichtbar"; `references/evals.md` |

## Phase Report und Nachbarn

| # | Punkt | Prüft | Quelle |
| --- | --- | --- | --- |
| 11 | Jede in „Abgrenzung" genannte Skill dieser Sammlung nennt diese Skill zurück | mechanisch: `neighbors` | Spec 00 §5 |
| 12 | Der Report hat die Sektion `## Was nicht gemessen wurde` — unter genau diesem Namen | mechanisch: `report-section` | Spec 17 (vorher unter sechs Namen) |
| 13 | `docs/known-limits.md` hat einen Abschnitt `## <skill>` | mechanisch: `report-section` | Spec 00; known-limits |
| 20 | Die Skill steht in der `skills`-Liste genau eines Plugins oder mit Grund in `.claude-plugin/excluded.json`; gehört sie zur Repo-Arbeit, auch in `PROJECT_SKILLS` von `scripts/sync_skills.py` | mechanisch: `plugin-membership`; die Projekt-Kopie `sync_skills.py --check` | Spec 20 |

## Was die Liste nicht ersetzt

Den zweiten Lauf vor jeder Fix-Runde (ein Eval-Ergebnis ist eine Stichprobe), den
Reviewer mit frischem Kontext (`references/reviewer-prompt.md`), und den Blick auf
die eigene Eiserne Regel: `architecture-map` existierte, damit Diagramme generiert
statt gemalt werden — und kein Eval prüfte das. Frag bei jeder Skill: Welcher Eval
würde rot, wenn jemand die Eiserne Regel bricht und sonst alles richtig macht?
