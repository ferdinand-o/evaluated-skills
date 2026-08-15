# Abschlussbericht: Skill `feature-spec`

Branch `feat/feature-spec`, Basis `0831fb7` (specs/skill-foundation). Acht
Commits, siehe unten. Plan: `docs/superpowers/plans/2026-08-15-feature-spec.md`.

## Was gebaut wurde

```
skills/feature-spec/
├── SKILL.md                        (99 Zeilen, Grenze 150)
├── references/
│   ├── spec-schema.md              (Feldregeln + vollständig ausgefülltes Beispiel)
│   └── decisions-guide.md          (Ernte-Kriterien, Zeilenformat, 30-Einträge-Warnregel)
├── assets/
│   └── spec-template.md
└── scripts/
    └── export_stubs.py             (Tier 1, nur Stdlib, 389 Zeilen)

tests/test_feature_spec_export.py   (36 Tests)
evals/feature-spec/evals.json       (4 Evals: 2 contract, 2 behavior)
evals/fixtures/
├── prose-criteria/                 (Contract-Falle: Prosa-Kriterium)
├── vague-feature/                  (Task-Manager mit EmailService/EventBus)
├── decisions-conflict/             (docs/decisions.md mit Fehlerformat-Entscheidung)
└── scope-risk-tenant/              (Multi-Tenant-Codebase, tenant_id-Scoping)

docs/artifact-header.md             (Ausnahme für # spec-stub:-Marker ergänzt)
README.md                           (Routing-Zeile feature-spec: geplant -> gebaut)
```

`export_stubs.py` ist der einzige mechanische Teil. Es parst `## Non-Goals`
und `## Akzeptanzkriterien` (mit `### <Titel>`-Blöcken, `- Given/When/Then/
And …`-Zeilen) aus einer Spec-Markdown-Datei, sammelt **alle** Contract-
Verstöße (fehlende/leere Non-Goals, Prosa-Kriterien mit Zeilennummer,
fehlende Kategorien, Slug-Kollisionen) und wirft erst am Ende einen
gesammelten Fehler — kein früher Abbruch, der spätere Verstöße verdeckt.
Bei Erfolg entstehen pytest-Stubs (`@pytest.mark.skip("stub: noch nicht
implementiert")`) und optional (`--vitest`) Vitest-Stubs (`it.todo(...)`).
Re-Export überschreibt eine Stub-Datei nur, wenn sie noch beide Marker
trägt — Entscheidung 1 aus dem Auftrag, wörtlich umgesetzt.

Manuell smoke-getestet vor dem ersten Commit (Erfolgsfall, Prosa-
Verweigerung, fehlende Non-Goals, Vitest-Flag) und durch 36 Unit-Tests
sowie einen Lauf gegen `evalkit.workspace.prepare()` für alle vier Fixtures
abgesichert.

## Zusätzlich getroffene Entscheidungen

Die Spec und der Auftrag legen den Contract fest, aber nicht das exakte
Markdown-Parsformat — das musste ich selbst entwerfen, dokumentiert in
`references/spec-schema.md`:

- **Sektionsüberschriften sind wörtlich**: `## Non-Goals` und
  `## Akzeptanzkriterien`, case-insensitiv verglichen, aber sonst exakt.
  Keine deutschen Alternativnamen (`## Nicht-Ziele` würde nicht erkannt).
  Das ist bewusst eng, weil ein mechanischer Parser sonst raten müsste,
  welche Überschrift gemeint ist — Raten ist genau das, was der Contract
  verhindern soll.
- **Given/When/Then-Präfixe**: `Given`, `When`, `Then`, `And` als erstes
  Wort einer `- `-Zeile, groß-/kleinschreibungsunabhängig, gefolgt von `:`
  oder Leerzeichen. Keine Bold-Markdown-Variante (`**Given**`) akzeptiert —
  bewusst, damit die Prosa-Falle (Eval 4) nicht durch geschickte
  Formatierung umgangen werden kann.
- **Dateinamen nur mit Unterstrichen, nie mit Bindestrichen**: `slugify()`
  erzeugt lesbare Bindestrich-Slugs für Titel, aber pytest-Dateinamen und
  Funktionsnamen wandeln sie über `ident()` in Unterstriche — ein
  Bindestrich in einem Python-Modulnamen ist beim Import riskant. Das stand
  in keiner der beiden Spezifikationen, ist aber notwendig, damit die
  erzeugten Stubs tatsächlich mit `pytest` sammelbar sind.
- **`from __future__ import annotations` aus `export_stubs.py` entfernt.**
  In Kombination mit `@dataclass(frozen=True)` und dem Lademechanismus
  `tests/conftest.py:load_script` (der das Skript per
  `importlib.util.module_from_spec` lädt, ohne es in `sys.modules`
  einzutragen) wirft Python 3.13 einen `AttributeError`, weil `dataclasses`
  bei String-Annotationen `sys.modules[cls.__module__]` nachschlägt. Ich
  habe **nicht** `tests/conftest.py` geändert (das wäre ein Eingriff in
  gemeinsame Infrastruktur außerhalb meiner Skill, siehe „Was du NICHT
  tust"), sondern den Future-Import entfernt — alle verwendeten Type-Hints
  (`tuple[str, ...]`, `X | None`, `dict[str, int]`) sind in Python 3.10+
  auch ohne ihn laufzeitfähig. **Sorge:** Sollte `conftest.load_script`
  später generell auf `from __future__ import annotations` + `@dataclass`
  angewiesen sein (andere Skills könnten das brauchen), ist der eigentliche
  Fix dort fällig — ich habe ihn nur lokal umgangen, nicht behoben.
- **Vitest wurde vollständig gebaut, nicht nur angekündigt.** Der Auftrag
  ließ offen, ob Vitest „im selben Lauf" entsteht oder als Lücke in
  `docs/known-limits.md` landet. Ich habe es gebaut (`--vitest`-Flag,
  gespiegelte Überschreiblogik über `// spec-stub: <slug>` + `it.todo(`),
  weil der Aufwand gering war und die Auftrags-Formulierung das als
  bevorzugte Option nennt.
- **`docs/artifact-header.md` um eine zweite dokumentierte Ausnahme
  erweitert** (nach dem `handoff.md`-Muster): Die Stub-Dateien tragen
  `# spec-stub: <slug>` statt der generischen Kopfzeile, weil der Marker
  hier Überschreibschutz ist, kein Konsumenten-Signal. Spec-Entwurf und
  `docs/decisions.md` tragen weiterhin die reguläre Kopfzeile.
- **README-Routing-Zeile aktualisiert** (nur die `feature-spec`-Zelle, nicht
  die daneben liegende `debug-ledger`/`systematic-debugging`-Namens-
  inkonsistenz zwischen README und Spec 00 — das ist eine andere Skill und
  außerhalb meines Auftrags).

## Was nicht verifiziert werden konnte

- **Keine echten Agent-Läufe.** `run_evals.py` wurde laut Auftrag nicht
  ausgeführt. Alle vier Evals sind nur mechanisch gegen
  `evalkit.schema.load_evals()` validiert (Schema korrekt, 4 Evals, richtige
  Klassen) und die beiden `contract`-Fixtures manuell gegen
  `export_stubs.py` durchgespielt (prose-criteria: verifiziert, verweigert
  wie erwartet). Die beiden `behavior`-Evals (vage Anfrage,
  Mandanten-Scope-Risiko) hängen an Judge-Urteilen über eine tatsächliche
  Draft-first-Antwort von Claude — das habe ich nicht simuliert, weil das
  genau der teure Agentenlauf ist, den ich nicht auslösen soll. Ob die
  Judge-Claims tatsächlich das messen, was sie behaupten zu messen, ist
  ungeprüft.
- **`decisions-conflict`-Fixture wurde nicht gegen einen echten Scan
  getestet**, nur ihr `fixture.json` und die Dateiinhalte mechanisch
  geprüft (JSON-Syntax, `workspace.prepare()`-Ladbarkeit). Ob ein echter
  Claude-Lauf den Konflikt tatsächlich mit den Begriffen `decisions.md` und
  `error.code` benennt, wie das `output_matches`-Pattern es verlangt, ist
  ungeprüft.
- **Kein Pflicht-Anti-Zeremonie-Eval.** Spec 00 §2 verlangt „mindestens ein
  Anti-Zeremonie-Eval" pro Skill; Spec 03 nennt aber vier feste, andere
  Evals und keinen trivialen Fall. Ich habe keinen fünften Eval ergänzt, um
  nicht über den Auftrag hinauszugehen, aber die Lücke besteht real — genau
  wie bei `handoff`s vergleichbarer Lücke, die `docs/known-limits.md` schon
  für den Harness selbst vermerkt (dort als Schema-Lücke, nicht
  Skill-Lücke). Diese Skill hat schlicht keinen eigenen trivialen Fall
  getestet: Was wäre eine „triviale" feature-spec-Anfrage? Eine, die schon
  vollständig als Given/When/Then vorformuliert ankommt? Das ist nicht
  offensichtlich genug, um es ungefragt zu entscheiden.
- **Die Given/When/Then-Parsing-Grenzfälle sind nicht erschöpfend.** Zum
  Beispiel: verschachtelte Bullet-Listen unter einem Kriterium (Einrückung),
  Kriterien mit Markdown-Inline-Code im Titel, das die Slug-Erzeugung
  durchkreuzt, oder ein `### `-Titel, der zufällig identisch mit einer
  anderen `##`-Sektion kollidiert. Die 36 Unit-Tests decken die im Auftrag
  genannten Leerfälle vollständig ab, aber nicht jede denkbare Markdown-
  Verformung.
- **Kein Nachweis, dass der Fallback aus SKILL.md Schritt 2 („mehr als drei
  zentrale Annahmen → Interview zuerst") in der Praxis greift.** Das ist
  reine Doktrin (G1), keiner der vier Evals prüft diesen Zweig gezielt —
  alle vier Fixtures sind so gebaut, dass Draft-first sinnvoll ist, keine
  Fixture erzwingt den Interview-Fallback.

## Was davon nach `docs/known-limits.md` gehört

Ich habe `docs/known-limits.md` bewusst **nicht** verändert — die
bestehenden Einträge dort sind Harness- und Betriebs-Grenzen aus dem
Merge-Review des Eval-Harness selbst, nicht Skill-spezifische Lücken. Nach
Rücksprache mit dir sollten aus meiner Sicht folgende Punkte dort (oder in
einem neuen `## feature-spec`-Abschnitt nach dem Muster von
`## dev-report`) ergänzt werden, sobald echte Agent-Läufe stattfinden:

1. Die beiden `behavior`-Evals sind bis zum ersten echten Lauf ungeprüft
   (siehe oben) — sollte der erste Lauf zeigen, dass die Judge-Claims zu
   vage oder zu eng formuliert sind, gehört das hier rein, so wie
   `docs/known-limits.md` das für `unsupported-claim-is-marked` bei
   dev-report bereits vormacht.
2. Der fehlende Anti-Zeremonie-Eval für `feature-spec` — als Spec-Lücke,
   analog zum bestehenden Eintrag „Der Pflicht-Anti-Zeremonie-Eval aus §2
   ist nirgends erzwungen".
3. Der `conftest.load_script` + `frozen dataclass` + `from __future__
   import annotations`-Konflikt (siehe oben) — eine latente Falle für jede
   künftige Skill, die dieselbe Kombination verwendet, ohne dass etwas im
   Harness sie verhindert.

## Verifikation

```
182 passed in 3.15s   (146 bestehende + 36 neue, keine Regression)
evalkit.schema.load_evals('evals/feature-spec/evals.json') -> 4 Evals, korrekte Klassen
wc -l skills/feature-spec/SKILL.md -> 99 (Grenze 150)
```

## Commits (feat/feature-spec, ab Basis 0831fb7)

```
07dcc25 docs(feature-spec): Implementierungsplan
108d3e5 docs(feature-spec): Spec-Schema, Template und Entscheidungsgedächtnis-Guide
1739714 feat(feature-spec): export_stubs.py parst Given/When/Then und exportiert pytest-/Vitest-Stubs
371ce70 test(feature-spec): export_stubs.py — Contract-Verweigerung, Overwrite-Schutz, Re-Export
ac08efa feat(feature-spec): SKILL.md — Draft-first-Doktrin, Contract, Abgrenzung
02d07c9 feat(feature-spec): vier Eval-Fixtures — Prosa-Falle, vage Anfrage, Entscheidungs-Konflikt, Mandanten-Scope
152542c feat(feature-spec): vier Evals — Prosa-Falle als Contract zuerst
7021327 docs: feature-spec-Ausnahme in artifact-header.md, README-Routing aktualisiert
f6f6cb6 docs: Abschlussbericht feature-spec
```

## Fix-Runde (nach unabhängigem Review)

Ein unabhängiger Reviewer fand zwei Defekte, beide vom Koordinator selbst
nachvollzogen bzw. bewertet.

**Defekt 1 (schwer, Datenverlust):** `should_write_pytest`/
`should_write_vitest` prüften den Skip-/Todo-Marker per `marker in text` —
wahr, sobald der Markertext irgendwo im Dateiinhalt stand, auch
auskommentiert (`# @pytest.mark.skip(...)`) oder nur als Zitat in einem
Docstring. Der naheliegendste Weg, einen Stub zu aktivieren — die Skip-Zeile
auskommentieren statt löschen —, führte dazu, dass der nächste Re-Export
eine fertige Testimplementierung mit einem leeren Stub überschrieb, Exit 0,
ohne Warnung. Behoben: Der Marker zählt nur noch als aktiv, wenn eine
Code-Zeile (außerhalb eines Docstrings/Triple-Quote-Strings, per
Vorkommen-Parität von `'''`/`"""` naiv erkannt) exakt dem generierten
`@pytest.mark.skip("stub: noch nicht implementiert")` entspricht bzw. bei
Vitest mit `it.todo(` beginnt und nicht `//`-auskommentiert ist. Fünf neue
Tests decken die drei vom Reviewer genannten Fälle ab (auskommentiert,
Docstring-Erwähnung, echter aktiver Marker trotz harmloser
Docstring-Koinzidenz) plus eine direkte Reproduktion des ursprünglichen
Datenverlust-Szenarios über `write_pytest_stubs()`. Die
„übersprungen"-Meldung pro Datei war bereits vorher in `main()` vorhanden
(`print(f"übersprungen (bereits implementiert): {path}")`) — jetzt zusätzlich
durch einen Test abgesichert, der die Ausgabe prüft, nicht nur den
Rückgabewert.

**Defekt 2 (Fehlklassifizierung):** `decisions-conflict-is-surfaced` war
`class: "contract"` mit drei unabhängigen Regex-Treffern
(`decisions\.md`, `error\.code`, `widerspr\w*|konflikt`), die auch dann
bestehen, wenn der Entwurf die Begriffe nur beiläufig erwähnt und die
bestehende Entscheidung trotzdem stillschweigend übergeht — es gab keine
`must_not`-Absicherung, und die drei Treffer durften unabhängig voneinander
an beliebigen Stellen im Output liegen. Ob ein Konflikt *substantiell*
aufgegriffen wurde, ist ein Urteil. Behoben: `class: "behavior"`, ein
Judge-Claim, der explizit verlangt, dass der Entwurf die bestehende
Entscheidung benennt, den Widerspruch zur Anfrage feststellt, und eine
bewusste Wahl trifft (folgen oder bewusst revidieren) — bloßes Erwähnen der
Begriffe reicht dem Claim-Text nach ausdrücklich nicht. Ein `must_not`-Judge-
Claim fängt zusätzlich den Fall der stillschweigenden Übernahme ohne jede
Erwähnung der Entscheidung.

`docs/known-limits.md` bekam einen neuen `## feature-spec`-Abschnitt: die
naive Docstring-Erkennung in `_code_lines()` und ihre Grenzfälle, dass nach
der Reklassifizierung nur noch ein `contract`-Eval übrig ist (die übrigen
drei brauchen jetzt einen Judge-Lauf), dass alle drei `behavior`-Evals bis
zum ersten echten Agentenlauf ungeprüft bleiben, und der weiterhin fehlende
Anti-Zeremonie-Eval.

**Verifikation nach der Fix-Runde:**
```
187 passed (146 Basis + 41 feature-spec, davon 5 neu für die Fix-Runde)
evalkit.schema.load_evals('evals/feature-spec/evals.json') -> 4 Evals,
  Klassen: contract, behavior, behavior, behavior
```

**Was weiterhin nicht verifiziert werden konnte:** Ob der neu formulierte
Judge-Claim für `decisions-conflict-is-surfaced` tatsächlich trennscharf
ist — er verlangt drei Teilaussagen in einem Claim (benennt die Entscheidung
UND erkennt den Widerspruch UND trifft eine Wahl), was für einen Judge
schwerer zu beurteilen sein könnte als ein einzelner, engerer Claim. Das ist
eine Abwägung, keine Gewissheit, und bleibt bis zum ersten echten Lauf offen
— siehe `docs/known-limits.md`.

Repo-Hinweis vom Koordinator übernommen, keine Änderung nötig: Der
`conftest.load_script`/`@dataclass`-Konflikt (siehe oben, „zusätzlich
getroffene Entscheidungen") ist inzwischen auf `feat/dev-report` in
`tests/conftest.py` behoben. Diese Skill behält ihre lokale Umgehung (kein
`from __future__ import annotations` in `export_stubs.py`), weil ein
Zurücknehmen keinen Mehrwert hätte und ein Revert-Risiko ohne Nutzen wäre.
