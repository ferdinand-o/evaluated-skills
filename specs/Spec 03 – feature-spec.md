# Spec 03: feature\-spec — Draft\-first Featurebeschreibung

Skill\-Spezifikation · Zyklus 3/14 · Entscheidung: Option B \+ Entscheidungsgedächtnis \+ Test\-Stub\-Export · Abgeglichen mit Spec 00

## Problem

Existierende Spec\-Skills (grill\-me, to\-spec, writing\-plans) interviewen gut, sind aber ungeerdet: Sie fragen, bevor sie die Codebase kennen, erzwingen kein Schema (Non\-Goals — die teuerste Auslassung — fehlen fast immer), und ihre Akzeptanzkriterien sind unprüfbare Prosa. Für Solo\-Arbeit kommt hinzu: Abstrakte Fragerunden sind langsamer als die Reaktion auf einen konkreten Entwurf, und jede neue Spec verhandelt Grundsatzentscheidungen neu, die längst gefallen sind.

## Constraints

Leser sind der Entwickler selbst und Claude — kein Team\-Formalismus, keine Stakeholder\-Sektionen. Die Zerlegung in Arbeitspakete übernimmt `superpowers:writing-plans` — die ursprünglich angedachte Geschwister\-Skill to\-tickets wird nach Spec 00 nicht gebaut; feature\-spec endet bei der fertigen Spec samt Stubs. Die Spec selbst ist wegwerfbar — sie lebt während der Arbeit in `docs/specs/wip/` und wird nach der Implementierung gelöscht; dauerhaft sind nur zwei Ableitungen: die Entscheidungszeilen in `docs/decisions.md` und die exportierten Test\-Stubs. Stacks: pytest (primär), Vitest (sekundär). Portables Frontmatter.

## Approach

**Draft\-first statt Interview\-first.** Die Skill scannt zuerst die Codebase (betroffene Module, vorhandene Muster, Einträge in `docs/decisions.md`) und legt sofort einen vollständigen Spec\-Entwurf vor. Alles Ungesicherte ist explizit markiert: `Annahme:` \-Zeilen („läuft über den bestehenden AuthService — widersprich, falls nein") und ein Block offener Fragen. Der Nutzer reagiert auf Konkretes, statt Abstraktes zu beantworten. Fallback als Regel in der SKILL.md: Wären mehr als drei *zentrale* Annahmen nötig, stellt die Skill zuerst die zwei bis drei entscheidenden Fragen — Interview ist die Ausnahme, nicht der Weg.

**Skill\-Struktur:**

```
feature-spec/
├── SKILL.md               (Doktrin, Draft-first-Ablauf, Fallback-Regel, Contract)
├── references/
│   ├── spec-schema.md     (Felddefinitionen + ausgefülltes Beispiel)
│   └── decisions-guide.md (was eine erntbare Entscheidung ist, Format)
├── assets/
│   └── spec-template.md
├── scripts/
│   └── export_stubs.py    (Tier 1; Given/When/Then → pytest-/Vitest-Skelette; G2)
└── evals/evals.json
```

**Spec\-Schema (Pflichtfelder):** Problem (2–3 Sätze); **Non\-Goals** — mindestens ein explizites „bauen wir nicht"; Annahmen (markiert, einzeln widersprechbar); Ansatz mit Bezug auf existierende Module; Akzeptanzkriterien ausschließlich als Given/When/Then; offene Fragen mit Entscheider. Contract: Eine Spec ohne Non\-Goals oder mit Prosa\-Kriterien ist unvollständig — der Stub\-Export schlägt dann fehl, was den Verstoß mechanisch sichtbar macht.

**Test\-Stub\-Export:** `export_stubs.py` parst die Given/When/Then\-Blöcke und erzeugt pro Kriterium ein Test\-Skelett (`test_<feature>_<kriterium>.py` mit vorbereitetem Arrange/Act/Assert\-Gerüst und `@pytest.mark.skip("stub: noch nicht implementiert")` bzw. `it.todo(...)` in Vitest). Die Stubs sind der Drift\-Schutz: Die Spec darf danach sterben — was sie versprochen hat, lebt als rote/übersprungene Tests im Repo weiter und wird von der normalen Testdisziplin eingefordert.

**Entscheidungsgedächtnis:** Nach Abschluss erntet die Skill Grundsatzentscheidungen (Fehlerformat, State\-Management, Namenskonventionen — Kriterien in decisions\-guide.md) als je eine Zeile nach `docs/decisions.md` (Datum, Entscheidung, Spec\-Anlass). Künftige Drafts lesen diese Datei im Scan und setzen Entschiedenes voraus, statt es neu zu fragen. Feature\-Details werden nicht geerntet — nur Wiederverwendbares.

**Anti\-Rationalisierungs\-Tabelle (Auszug):** „Der Nutzer weiß, was er will — Fragen sparen" → Annahmen trotzdem markieren; unmarkierte Annahmen sind versteckte Fragen. „Non\-Goals ergeben sich schon" → ohne explizites Nicht\-Ziel wächst der Scope beim Implementieren. „Kriterien als Checkliste reicht" → was der Stub\-Export nicht parsen kann, ist kein Kriterium.

**Evals:** (1) Vage Anfrage („bau mir Notifications") — entsteht ein Entwurf mit markierten Annahmen statt einer Fragenlawine oder ungeerdetem Volltreffer\-Anspruch? (2) Anfrage, die einer Zeile in decisions.md widerspricht — merkt es der Scan? (3) Feature mit verstecktem Scope\-Risiko — landet das Risiko in den Non\-Goals? (4) Kriterien absichtlich als Prosa formuliert — verweigert der Export und fordert Given/When/Then ein?

## Alternatives considered

Interview\-first (grill\-me\-Muster) bleibt für völlig neues Terrain ohne Codebase\-Bezug überlegen — dafür existiert der Fallback; als Default ist es für Solo\-Arbeit zu langsam. Integrierte Zerlegung bis zu Tickets wurde als Scope\-Bruch getrennt (Geschwister\-Skill). Reines Status\-Protokoll statt Stub\-Export war der leichtere Drift\-Schutz, verliert aber die mechanische Verbindung zum Code — vom Nutzer zugunsten der Stubs revidiert. PRD\-Formalismus verworfen (kein Team\-Publikum).

## Out of scope

Ticket\-/Arbeitspaket\-Zerlegung (`superpowers:writing-plans`), Aufwandsschätzung, Stakeholder\-/Approval\-Workflows, automatische Implementierung im Anschluss.

## Open questions

Stub\-Namenskonvention, damit `export_stubs.py` bei Re\-Export bestehende, schon implementierte Tests nicht überschreibt (Hash im Dateinamen vs. Marker\-Kommentar)? Wächst `docs/decisions.md` unbegrenzt oder mit Themen\-Gliederung ab \~30 Einträgen?

## Next steps

Spec\-Template und Schema\-Referenz schreiben; `export_stubs.py` für pytest implementieren (Vitest danach); decisions\-guide.md mit Ernte\-Kriterien formulieren; die vier Evals bauen — zuerst die Prosa\-Kriterien\-Trap, weil sie den Contract trägt; Description schärfen (triggert bei „neues Feature/bau mir X", nicht bei Bugfixes — dort greift systematic\-debugging).
