<!-- skill: reddit-research | schema: 1 | generated: von Hand nach skills/skill-forge/assets/skill-template/report.md -->
# reddit-research — Abschlussbericht

Eingebunden am 2026-11-26 aus einem Zip des Maintainers (`reddit-research-skill.zip`), ohne Spec und
ohne Plan; Tier 1 (Skript nur Stdlib). Sequenziell im Hauptkontext geprüft und angepasst.

## Was entstanden ist

```
skills/reddit-research/SKILL.md                    150 Zeilen (Grenze 150)
skills/reddit-research/references/                 connector.md, scout-prompt.md, worker-prompt.md
skills/reddit-research/scripts/rr.py               Tier 1: select, remap, tally
evals/reddit-research/evals.json                   3 Evals, alle contract
evals/fixtures/rr-finished, rr-tags, rr-remap      lokale Fixtures, kein Connector
tests/test_reddit_research_rr.py                   9 Tests
```

Nachgezogen: Plugin `evaluated-knowledge` (`marketplace.json`), Routing-Matrix in Spec 00 §5 und
`README.md`, Abschnitt `## reddit-research` in `docs/known-limits.md`.

## Was beim Prüfen gefunden und geändert wurde

- **`rr.py remap` stürzte bei einer abgeschnittenen JSONL-Zeile ab** (`JSONDecodeError`), die ein
  abgebrochener Worker hinterlässt. `tally` fängt dieselbe Zeile ab. Jetzt überspringt `remap` sie und
  meldet die Zahl. Test: `test_remap_moves_other_and_survives_truncated_line`.
- **`rr.py select` überschrieb alte Batches stillschweigend**; jetzt Warnung auf stderr.
- **Prompt-Injection:** Scout- und Worker-Prompt nannten Reddit-Text nicht als Daten. Ergänzt in beiden
  Prompts und im Contract.
- **Pfade:** `SKILL_DIR` (kein Mechanismus des Repos) durch `${CLAUDE_SKILL_DIR}` ersetzt (Spec 25).
- **Description:** keine Abgrenzung, Prozessverb „runs“ (Lint `description`). Neu mit Triggern und
  „Not for“ gegen verified-research und den direkten Connector-Aufruf.
- **Fehlend nach Hausregeln:** `Tier`-Angabe im Skript, Contract- und Abgrenzungs-Abschnitt, Hinweis
  gegen das Committen des Arbeitsordners (Benutzernamen in den Tags).

## Was gemessen wurde

- **Connector-Schemas:** die in SKILL.md und Prompts benutzten Parameter (`search_posts`:
  `link_flair_text`, `after`/`before`, `max_text_chars`, `fields`, `cursor`; `get_items_by_id`: Ids ohne
  Präfix; `get_comment_tree`: `limit`, `start_breadth`, `start_depth`; `search_subreddits`:
  `name_prefix`; `aggregate_posts`: `group_by`, `frequency`; `get_user_subreddit_activity`) gegen die
  Tool-Definitionen dieser Session abgeglichen: alle vorhanden.
- **Tests:** `tests/test_reddit_research_rr.py`, 9 neu, grün.
- **Evals mit Skill:** 3 Läufe nach der letzten Fix-Runde, je 3 von 3 grün; davor in den Fix-Runden
  Fehlschläge (siehe `notes` der Evals): Remap-Prompt ohne „Reddit“ (Skill nicht gewählt),
  Assertion an Agent-Wortwahl, Fixture-Schema, das den Diskriminator vorsagte.
- **Baseline `--without-skill`:** 3 von 3 rot, also misst jeder Eval etwas. Ein früherer Lauf hatte
  den Anti-Zeremonie-Eval grün ohne Skill; die Fixture wurde deshalb umgebaut.
- **Lint:** `lint_skill.py skills/reddit-research`: 15 Regeln `pass`, 0 Befunde; `evals_due` ist ohne
  `--base` ungeprüft (neue Skill). Für die zwei geänderten Nachbarn (`verified-research`, `visual-summary`)
  mit `--base HEAD`: kein neuer Befund.
- **Gesamtsuite:** 2130 grün, 3 übersprungen, 1 rot (`test_rest_api_architect_gate.py::
  test_main_exit_zero_when_degraded_but_checklist_clean`, Spectral/oasdiff-Verfügbarkeit); der
  Fehlschlag besteht identisch auf dem Stand ohne diese Änderung (per `git stash` gegengeprüft).

## Was nicht gemessen wurde

**Die Pipeline** — Scouts, Tagging-Worker, Subreddit-Suche, Qualitätscheck und Bericht liefen nicht;
dafür braucht es den Connector und rund 75 Minuten Haiku-Läufe. Was vorliegt, prüft Skripte und
Schemas, nicht die Ergebnisqualität einer Recherche.

**Der Trigger** — ob „was sagt Reddit zu X“ bei dieser Skill landet, ist nicht als Routing-Eval
gefahren. Gemessen ist nur, dass Teilaufgaben ohne das Wort „Reddit-Recherche“ den Trigger verfehlen
können (3 von 5 Läufen im Zwischenstand).

**Die Zahlen der Skill** — „≈ 75 min“, „≈ 200 000 Token je Batch“ und die 80-%-Übereinstimmung stehen
im Original und wurden nicht nachgemessen.

**Injection** — kein Test mit einem Reddit-Text, der Anweisungen enthält.

**Der Anti-Zeremonie-Eval** trennt Skill und Basismodell nur über `"unit": "author"` und `"ci95"`.

## Offen für die nächste Runde

- Spec nachziehen oder die Skill bewusst als Fremdskill führen; ein Lauf mit Connector (klein, etwa
  30 Threads) als Abnahme.
- Entscheiden, ob `evaluated-knowledge` die richtige Heimat ist: Die Skill ist ohne Connector nutzlos,
  `cad-parts` wurde aus demselben Grund ausgeschlossen. Hier steht sie drin, weil sie sauber stoppt.
