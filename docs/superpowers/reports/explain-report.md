# explain — Abschlussbericht

Gebaut nach `specs/Spec 15 – explain.md` und `docs/superpowers/plans/2026-09-01-explain.md`.
Zyklus 15, Tier 0, zustandslos, web-only.

## Was entstanden ist

```
skills/explain/SKILL.md               101 Zeilen (Grenze 150)
skills/explain/references/honesty.md  Marker-Geltungsbereich, Hedging, Quellen, Routing
skills/explain/references/effort-ladder.md  fünf Stufen, Stufenerkennung, Recherche-Kopplung
evals/explain/evals.json              8 Evals
evals/fixtures/ex-sources/            Quellen-Fixture mit erfundenen Konstanten
tests/test_explain_evals_schema.py    8 Tests
```

Dazu nachgezogen: `learning-coach`s Abgrenzungssatz, die Routing-Matrix in Spec 00 §5
und in `README.md`.

## Die drei Entscheidungen, die den Bau geprägt haben

**Der Marker-Geltungsbereich war die blockierende Lücke.** Die Spec sagte, was
`Unverified:` und `Source:` bedeuten, aber nie, wann ein Satz *keinen* Marker trägt.
Entschieden in `honesty.md`: Eine unmarkierte Aussage behauptet Gewissheit — das ist
der Normalfall und wird nicht ausgewiesen. Wer nicht markiert, steht für die Aussage
gerade. Damit trägt Teil 1 nie einen Marker; ist nichts Gesichertes verfügbar, sagt
Teil 1 in einem Satz genau das.

**`Next:` ist ein Kompromiss, kein Layout-Detail.** Eine Skill ohne Dateien kann Kürze
nicht mechanisch messen: `output_max_lines` existiert nicht, `file_max_lines` greift
nur auf Dateien. Ohne einen wörtlichen Token hätte der Pflicht-Anti-Zeremonie-Eval
allein auf einem Judge-Urteil über „kurz" beruht — und im Repo ist gemessen, dass ein
Judge Kürze nur bei grober Verletzung zuverlässig beurteilt. `Next:` macht die
Abwesenheit des Anschlussblocks bei `low` prüfbar und ist zugleich das einzige
Merkmal, an dem sich die Ausgabe der Skill von einer guten Antwort ohne Skill
unterscheiden lässt. Der Preis: ein sichtbarer Fremdkörper in einer fließenden
Antwort.

**`xhigh` ist geblieben und musste sich rechtfertigen.** Der Spec-Review wollte die
Stufe streichen, weil sie sonst nirgends im Repo vorkommt. Sie ist eine reale
Claude-Effort-Stufe und war ausdrücklich angefragt; die Auflage war, dass die Trennung
zu `max` trägt. Sie lautet jetzt: `xhigh` blickt in die Breite (konkurrierende
Erklärungen desselben Gegenstands), `max` in die Tiefe der Zeit (Herkunft, offene
Streitfragen, Primärquellen). Für Gegenstände ohne konkurrierende Modelle fällt
`xhigh` ausdrücklich mit `max` zusammen, statt eine Modelldiskussion zu erfinden.

## Was gemessen wurde

- **987 Tests grün.** Der eine rote (`test_rest_api_architect_gate.py::test_main_exit_zero_when_degraded_but_checklist_clean`)
  ist vorbestehend und fremd — per `git stash` auf unverändertem Stand gegengeprüft;
  er erwartet ein fehlendes Spectral, das in dieser Umgebung installiert ist.
- **8 neue Tests** in `test_explain_evals_schema.py`. Einer davon fand beim ersten Lauf
  einen echten Mangel: Der Routing-Eval beschrieb seine eigene Schwäche, beantwortete
  aber die Diskriminator-Frage nicht. Behoben in den `notes`, nicht durch Aufweichen
  des Tests.
- **Schema-Validierung** der 8 Evals über `evalkit.schema.load_evals`.

## Was NICHT gemessen wurde

**Kein einziger der acht Evals ist gefahren.** Der Eval-Harness läuft in dieser
Umgebung nicht: `evalkit/dispatch.py` verdrahtet `permission_mode="bypassPermissions"`,
und die Claude-CLI verweigert das unter uid 0 (`docs/known-limits.md`, Abschnitt
„Betrieb"). Ein Lauf endet mit „0 bestanden, 0 gefallen, N übersprungen" und
Exit-Code 0 — er sieht aus, als sei nichts kaputt, obwohl nichts gemessen wurde. Was
hier vorliegt, ist damit eine geschriebene, schema-valide Eval-Sammlung, kein Nachweis
über das Verhalten der Skill.

**Das Zielsystem bleibt strukturell ungemessen.** Die Skill ist für claude.ai/Cowork
gebaut; der Harness fährt sie in Claude Code — mit Shell, Dateizugriff und fremden
Skills im Kontext. Selbst ein grüner Lauf belegte Verhalten *mit* verfügbaren
Werkzeugen, nicht ohne.

**Der eigentliche Fehlerfall der Skill ist unprüfbar.** `output_matches` prüft die
*Anwesenheit* eines Markers. Dass eine unsichere Aussage *ohne* Marker durchgegangen
ist, kann kein Mechanismus feststellen — und genau das ist der Fall, gegen den die
Skill existiert. Die Selbsteinschätzung der Unsicherheit bleibt G1-Selbstauskunft;
bei Tier 0 gibt es kein Gate, das die Lücke schließen könnte.

## Offen für die nächste Runde

- Die acht Evals einmal gegen echte Agentenläufe fahren, außerhalb eines
  Root-Containers. Am aussagekräftigsten sind `anti-ceremony-trivial-low-stays-bare`
  (trägt auf dem `must_not`) und `codebase-question-is-routed-away` (die Kollision mit
  `architecture-map`, die auf Description-Ebene nicht auflösbar ist).
- Ob `Next:` im Gebrauch stört. Wenn ja, entfällt mit ihm die mechanische Prüfbarkeit
  von zwei Evals — das ist ein echter Verlust, kein kosmetischer.
- Ob die englischen Tokens in einer durchgehend deutschen Antwort als Fremdkörper
  auffallen.
