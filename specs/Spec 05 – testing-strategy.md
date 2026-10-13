# Spec 05: testing\-strategy — Universelles Testing mit Repo\-Typ\-Adaptern

Skill\-Spezifikation · Zyklus 5/14 · Entscheidung: Eine Skill \+ deterministisches Routing \+ Extension\-Referenz als tiefster Adapter · Abgeglichen mit Spec 00

## Problem

Testing\-Skills existieren als generische Best\-Practices\-Listen (TestMu\-Pack, Framework\-Snippets) oder als enge Spezialisten (webapp\-testing) — nichts deckt die Realität ab, dass ein Legacy\-Monolith, eine moderne REST\-API und eine Chrome\-Extension *fundamental verschieden* getestet werden, obwohl das Ziel identisch ist (Regressionen billig fangen). Ohne Repo\-Typ\-Bewusstsein schreibt Claude naive Unit\-Tests in Legacy\-Code (wo Characterization\-Tests hingehören) und Standard\-Playwright gegen Extensions (wo Persistent Context und SW\-Termination nötig sind). Die Chrome\-Extension\-Lücke ist dabei die größte: Keine bekannte Skill behandelt `--load-extension`, chrome.\*\-Mocks oder erzwungene Service\-Worker\-Termination.

## Constraints

Eine Skill, nicht sechs — Varianz liegt in References, nicht in konkurrierenden Descriptions. Die Referenz\-Auswahl erfolgt deterministisch per Skript, nie per Bauchgefühl. Mehrsprachig (mindestens Python/pytest, TS/Vitest\+Playwright, Java/JUnit als Legacy\-Vertreter). Nur lokale Ausführung, kein CI\-Workflow\-Asset. Extension\-Fokus: Content Scripts. Portables Frontmatter. Promotion\-Regel als Wachstums\-Ventil ist Teil der Skill\-Doku.

## Approach

**Kern \+ Adapter.** Die SKILL.md trägt die universelle Doktrin, `detect_stack.py` klassifiziert das Repo, eine harte Routing\-Tabelle bestimmt die zu ladende Adapter\-Referenz. Progressive Disclosure macht die Breite bezahlbar: Geladen wird nur der eine passende Adapter.

**Skill\-Struktur:**

```
testing-strategy/
├── SKILL.md                 (Doktrin, Routing-Tabelle, Test-Plan-Contract, Promotion-Regel)
├── references/
│   ├── test-design.md       (querliegend: gute Tests, Anti-Patterns, Flakiness-Vermeidung)
│   ├── legacy-monolith.md   (Characterization/Golden-Master, Seams, Approval-Tests)
│   ├── rest-api.md          (Contract-Tests, Schema-Validierung, Testcontainers)
│   ├── chrome-extension.md  (tiefster Adapter — siehe unten)
│   ├── frontend-spa.md      (Component-/E2E-Schnitt, Testing-Library-Disziplin)
│   └── cli-library.md       (Snapshot von CLI-Output, Public-API-Tests)
├── scripts/
│   └── detect_stack.py      (Tier 2; Repo-Klassifikation → .skills/cache/detect_stack.json:
│                             Typ, Sprache, Runner, Signale)
└── evals/evals.json
```

**Doktrin (Kern):** Testen optimiert Regressions\-Fang pro Wartungskosten — nicht Coverage\-Prozente (explizit verworfen: lädt zum Gaming ein; Verhaltensabdeckung schlägt Zeilenabdeckung). Der Repo\-Typ bestimmt die Pyramide: Legacy bekommt erst ein Sicherheitsnetz aus Characterization\-Tests, *dann* Refactoring, nie umgekehrt; APIs testen Contracts vor Implementierungsdetails; Extensions testen Kontextgrenzen und Neustarts. Was nicht getestet wird, ist eine dokumentierte Entscheidung, kein Versehen.

**Output\-Contract — der Test\-Plan\-Block:** Vor dem ersten geschriebenen Test gibt die Skill immer aus: erkannter Repo\-Typ (aus detect\_stack.py), Runner, Test\-Schichten mit Begründung, bewusste Auslassungen. Ein Test\-PR ohne Plan\-Block ist ein sichtbarer Regelverstoß; ein Plan, der der Klassifikation widerspricht, ebenso.

**`detect_stack.py`\:** liest deterministische Signale — manifest.json → Extension; openapi.yaml/Router\-Muster → REST\-API; package.json/pyproject/pom → Sprache und Runner; fehlende Tests plus alte, große Historie → Legacy\-Verdacht (Score, kein Orakel). Ausgabe als JSON nach `.skills/cache/detect_stack.json` (Ephemera, gitignored, jederzeit neu erzeugbar); bei Mehrdeutigkeit listet es die Kandidaten und die Skill fragt nach, statt zu raten.

**Adapter chrome\-extension.md (der tiefste):** Vier Schichten: (1) Unit mit gemocktem `chrome.*` (Messaging, storage) ohne Browser; (2) Integration via Playwright Persistent Context mit `--load-extension` — die fertige, erprobte Fixture ist das wertvollste Einzelstück des Adapters; (3) **SW\-Termination\-Chaostest**\: Service Worker gezielt beenden (Debugger\-API/Idle erzwingen) und prüfen, dass Message\-Routing und State\-Rehydrierung nach Neustart korrekt sind — Kernrisiko jeder MV3\-Extension; (4) Content\-Script\-Tests gegen eingefrorene **Fixture\-Seiten** statt Live\-Websites (Live\-DOM ändert sich, Tests müssen es nicht). Konvention: Jede neue Message\-Route erhält ihren Termination\-Test.

**Promotion\-Regel:** Braucht ein Adapter eigene Skripte/Assets oder überschreitet er \~300 Zeilen, wird er zur Geschwister\-Skill befördert (Description\-Routing beidseitig nachziehen). chrome\-extension.md ist der erste Kandidat.

**Evals:** (1) Legacy\-Trap: 10 Jahre alter Code ohne Tests — kommen Characterization\-Tests statt naiver Units mit erfundenem Soll\-Verhalten? (2) Extension\-Trap: Message\-Handler\-Änderung — enthält der Plan den SW\-Neustart\-Fall? (3) Routing\-Trap: Repo mit manifest.json *und* REST\-Backend — fragt die Skill statt zu raten? (4) Anti\-Zeremonie: einzelner neuer Test in gut getestetem Repo — kommt ein Drei\-Zeilen\-Plan statt einer Strategie\-Abhandlung?

## Alternatives considered

Skill\-Familie von Beginn an (ein Skill pro Repo\-Typ) ist bei sehr tiefen Themen sauberer, lässt aber sechs Descriptions ums Triggering konkurrieren — die Promotion\-Regel holt die Aufspaltung nach, wenn Tiefe sie rechtfertigt. Coverage\-Ziele als Contract verworfen (Gaming). Ein CI\-Workflow\-Asset war ursprünglich angedacht, wurde per Constraint gestrichen — nachrüstbar als eigenes Asset ohne Strukturänderung.

## Out of scope

CI/GitHub\-Actions\-Integration, Last\-/Performance\-Tests (eigene Spur), Visual\-Regression (eigener Skill\-Kandidat aus der Analyse), Mutation Testing (später als test\-design\-Erweiterung), Test\-Generierung aus Specs (gehört zu feature\-spec/Spec 03 via Stub\-Export — Schnittstelle: testing\-strategy implementiert die Stubs aus).

## Open questions

Wie viele Sprachen trägt test\-design.md konkret, bevor es splittet (Python/TS sicher, Java nur für Legacy)? Wann gilt ein Cache\-Eintrag von detect\_stack.py als veraltet — Änderung an Manifest\- oder Lockfiles, Alter, oder Neuklassifikation bei jedem expliziten Aufruf?

## Next steps

detect\_stack.py mit Signal\-Tabelle implementieren; SKILL.md mit Routing\-Tabelle und Test\-Plan\-Contract schreiben; chrome\-extension.md zuerst ausarbeiten (Playwright\-Fixture bauen und *real testen* — sie ist das Herzstück), dann legacy\-monolith.md; die vier Evals aufsetzen, Legacy\-Trap zuerst.
