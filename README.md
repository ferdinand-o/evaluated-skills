# cc-skills

Persönliche Claude-Skills und ihre Spezifikationen.

## Aufbau

| Ordner | Inhalt |
| --- | --- |
| `skills/` | die gebauten Skills (je ein Ordner mit `SKILL.md`) |
| `specs/` | Spezifikationen, Spec 00 ist die gemeinsame Grundlage |
| `evals/` | Eval-Definitionen und Fixtures |
| `evalkit/` | der geteilte Eval-Harness |
| `docs/` | Konventionen und Pläne |

## Evals laufen lassen

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                                  # Harness-Unit-Tests
.venv/bin/python run_evals.py --class contract    # billige Contract-Evals
.venv/bin/python run_evals.py --skill handoff     # alles für eine Skill
```

Exit-Codes: `0` alles grün, `1` mindestens ein Eval gefallen, `2` Harness-Fehler.

## Routing

Welche Skill für welchen Anlass — die zentrale Matrix aus Spec 00 §5. Jede
Description trägt zusätzlich eine Abgrenzungsklausel gegen ihre zwei stärksten
Konkurrenten. Mit `(geplant)` markierte Skills sind spezifiziert, aber noch
nicht gebaut — die Matrix beschreibt den Zielzustand.

| Anlass | zuständig | nicht |
| --- | --- | --- |
| neues Feature, Codebase existiert | feature-spec | brainstorming — die eigene Profil-Skill, nicht superpowers (kein Codebase-Bezug), writing-plans (das *Wie* danach) |
| Bug, Testfehler | debug-ledger *(geplant)* | feature-spec |
| Testplan, Repo-Typ-Frage | testing-strategy | test-driven-development (Zyklus *während* der Implementierung), feature-spec *(geplant)* (erzeugt die Test-Stubs, testing-strategy implementiert sie aus) |
| Diff prüfen | `/code-review` (mitgeliefert) | eigene Review-Skill — siehe Spec 04, Zuschnitt offen |
| Sicherheit | `/security-review`, trailofbits | alle eigenen Skills |
| UI: Stil und Tokens | ui-architect | enterprise-ui (Produktoberfläche), motion-landing (Bewegung) |
| UI: Produktoberfläche, Tabellen, Formulare | enterprise-ui | ui-architect (Marketing/Brand) |
| Landing-Page-Bewegung | motion-landing *(geplant)* | ui-architect (Stil/Tokens), enterprise-ui |
| ad-hoc „fass zusammen" | visual-summary | dev-report (periodisch), handoff (Sitzungsende) |
| Konzept/Thema erklären (kein Code) | explain | learning-coach (Session mit Abruf), visual-summary (verdichtet Vorliegendes), architecture-map (Codebase) |
| Implementierungsplan zu einer Spec | impl-plan | superpowers:writing-plans (fremde Repos), brainstorming — die eigene Profil-Skill, nicht superpowers (die Spec davor), subagent-dev (zerlegt und dispatcht den fertigen Plan) |
| Skill bauen oder ändern | skill-forge | skill-creator (außerhalb dieser Sammlung, eigenes Eval-Schema), superpowers:writing-skills (Disziplin-Skills mit Druckszenarien), impl-plan (nur der Plan) |
| Sitzungsende, Übergabe | handoff | visual-summary, dev-report |

## Konventionen

- [Artefakt-Kopfzeile und Konsumenten-Regel](docs/artifact-header.md)
- [Spec 00 — Artefakt-Vertrag, Evals, Tiers und Routing](specs/Spec%2000%20%E2%80%93%20skill-foundation.md)
- [Bekannte Grenzen des Eval-Harness](docs/known-limits.md)
