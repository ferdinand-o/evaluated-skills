<!-- skill: skill-forge | schema: 1 | generated: von Hand nach skills/skill-forge/assets/skill-template/report.md -->
# work-plan — Abschlussbericht

Gebaut nach `specs/Spec 23 – work-plan.md`, Tier 1 ohne eigenes Skript, am 2026-10-13
sequenziell im Hauptkontext nach `docs/superpowers/plans/2026-10-13-work-plan.md`
(9 Tasks; das Gate koppelte acht davon). Jeder Task wurde mit `plan_to_tasks.py verify`
in einem sauberen Worktree abgenommen.

## Was entstanden ist

- `skills/work-plan/SKILL.md` (98 Zeilen): Schwelle „Kein Plan nötig", Quelle `**Spec:**`
  (feature-spec) oder `**Auftrag:**` mit `- Annahme:`-Zeilen, Verifikationsbefehl aus dem
  Repo, Verifikations-Task als letzter Task, Lint über
  `${CLAUDE_SKILL_DIR}/../subagent-dev/scripts/plan_to_tasks.py`, Übergabe mit
  „ungeprüft", wenn der Lint fehlt.
- `references/task-patterns.md` (Code-, Doku- und Verifikations-Task, Zuschnittsregel,
  Vokabular) und `assets/plan-template.md`; beide Beispiele sind als Plan lint-sauber.
- `plan_to_tasks.py lint` kennt die Kopfzeile `skill: work-plan`: genau eine Quelle,
  `Verifikation` als letzter Task, Coverage gegen die `### `-Titel unter
  `## Akzeptanzkriterien` einer feature-spec-Spec; `generate` und `verify` unverändert.
- Der Bereichs-Hook von setup-repo nimmt `docs/plans/` aus; die `sr-*`-Fixtures sind neu
  erzeugt.
- Vier Evals mit den Fixtures `wp-small`, `wp-spec`, `wp-verify`, `wp-finding` und der
  Strukturtest `tests/test_work_plan_evals.py`.
- Nachbarn:
  - subagent-dev, impl-plan, feature-spec, architecture-map und rest-api-architect
    verweisen auf work-plan statt auf `superpowers:writing-plans` und
    `superpowers:subagent-driven-development`.
  - `sync_skills.py --report`: superpowers-Verweise in Descriptions aktiver Plugins
    **6 → 0**; `test_no_superpowers_routing_targets` hält das.
  - `evaluated-dev` listet work-plan; eigene Routing-Zeile in README und Spec 00.

## Die Entscheidungen, die den Bau geprägt haben

- **Der Lint bleibt bei subagent-dev.** work-plan hat kein Skript; jede Formatregel ist
  in `plan_to_tasks.py` gebaut und dort getestet. Der Preis: Ohne subagent-dev daneben
  gibt es nur „ungeprüft".
- **Der Verifikations-Task ist lint-fähig.** `Test:` nennt die Datei, die den Befehl
  definiert, `Consumes:` alle `Produces:` der Code-Tasks — so steht er für das Gate
  hinter allen anderen, ohne dass der Parser eine Sonderregel braucht.
- **Die Schwelle steht in der Skill, nicht im Lint.** Ob ein Plan nötig ist, entscheidet
  Claude vor dem Schreiben; ein Lint sieht nur Pläne, die schon existieren.

## Was gemessen wurde

Suite: 1 506 grün, 3 übersprungen, 1 rot (`test_rest_api_architect_gate`, Spectral fehlt
in der Umgebung). `lint_skill.py skills/work-plan` ohne Befund; die fünf Nachbarn ohne
neuen Befund, `evals_due` bei allen fünf wegen der geänderten Description.

**Echte kopflose Sessions** (`claude -p` mit `--allowedTools`, `--permission-mode
acceptEdits`, CLI 2.1.296), Workspaces über `evalkit.workspace.prepare()`, Bewertung mit
`evalkit.runner.grade()`. Im Workspace liegt nur work-plan, nicht subagent-dev:

| Eval | mit Skill | ohne Skill |
| --- | --- | --- |
| 1 Anti-Zeremonie, Tippfehler | 1/1 | 0/1 — Plan in drei Schritten im Gespräch, ohne den Wortlaut der Schwelle |
| 2 Plan aus feature-spec | 1/1 | 0/1 — `docs/plans/export.md` ohne Kopfzeile, Interfaces und Verifikations-Task |
| 3 Verifikationsbefehl aus CLAUDE.md | 2/2 mit `make ci`, dazu 1/1 mit der ersten Fassung | 0/1 — Plan im Gespräch, keine Datei, kein „ungeprüft" |
| 4 Plan aus Befund | 2/2 (zweite Fassung) | 0/1 — kein Plan unter `docs/plans/` |

Die Pläne der bestandenen Läufe habe ich nachträglich mit `plan_to_tasks.py lint`
geprüft: alle ohne Befund, der aus Eval 2 mit „Spec-Coverage geprüft: 3
Akzeptanzkriterien".

**Zwei Evals waren falsch kalibriert und wurden geschärft:**

- **Eval 4, erste Fassung:** „Schreib einen Plan für den Zyklus, den ARCHITECTURE.md
  meldet." Die Skill antwortete „Kein Plan nötig" — zu Recht: Den Zyklus löst eine Zeile
  in `session.py`, eine Datei, keine neue Schnittstelle. Der Prompt verlangt jetzt
  zusätzlich, dass `User` seine Session von außen bekommt; das ändert den Konstruktor und
  liegt über der Schwelle. Die Fixture blieb unverändert.
- **Eval 3:** Die Fixture nannte `make check` — genau den Befehl, der als Beispiel in
  `task-patterns.md` steht. Ein Plan hätte ihn von dort abschreiben
  können, ohne die CLAUDE.md zu lesen. Die Fixture nennt jetzt `make ci`. Der erste Lauf
  mit `make check` hatte bestanden.

**Ein Fehler in Task 1 kam erst beim Eval-Test ans Licht:** Die Coverage verglich die
Kriterien-Titel mit der repr des Match-Objekts statt mit dem Header-Text; die repr kürzt
nach rund 50 Zeichen, ein langer Kriterien-Titel im Task-Titel galt deshalb als fehlend.
Der Unit-Test nutzte nur kurze Titel. Behoben in einem eigenen Commit, der Unit-Test hat
jetzt einen Titel über 50 Zeichen.

## Was nicht gemessen wurde

- **Ein Lauf mit Lint.** Im Eval-Workspace fehlt subagent-dev; ob Claude Lint-Befunde
  behebt statt umformuliert, misst kein Eval. `${CLAUDE_SKILL_DIR}` im Plugin-Cache ist
  nur für die lokale Installation nachgemessen (Spec 23, Constraints).
- **Wiederholbarkeit.** Evals 1 und 2 liefen einmal mit Skill, Evals 3 und 4 in ihrer
  geltenden Fassung zweimal; ohne Skill lief jeder Eval einmal.
- **Die Grenze der Schwelle.** Gemessen sind ein Tippfehler (darunter) und drei Aufträge
  klar darüber; der erste Eval-4-Prompt traf zufällig den Grenzfall und zeigte, dass die
  Skill dort die Regel anwendet statt den Wunsch nach einem Plan.
- **Isolation der Workspaces.** Ein Lauf meldete, er habe Kopien von `plan_to_tasks.py`
  in anderen Scratchpad-Verzeichnissen gesehen und bewusst nicht benutzt. Die Workspaces
  liegen nebeneinander unter demselben Elternordner; ein weniger vorsichtiger Lauf hätte
  einen fremden Lint aufrufen können.
- **Routing-Kollision** mit impl-plan und dem eingebauten Plan-Modus in einer Session,
  in der alle drei verfügbar sind.

## Offen für die nächste Runde

- Folgespec für `${CLAUDE_SKILL_DIR}` in subagent-dev, damit `generate` und `verify` in
  fremden Repos laufen (known-limits).
- Eval-Workspaces außerhalb eines gemeinsamen Elternordners anlegen.
- Spec 24 (test-first): der Rot-Grün-Zyklus, den work-plan nur als Steps nennt.
