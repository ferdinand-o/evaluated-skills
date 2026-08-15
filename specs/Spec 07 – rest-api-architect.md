# Spec 07: rest\-api\-architect — Spec\-first mit Konventions\-Preset

Skill\-Spezifikation · Zyklus 7/14 · Entscheidung: Greenfield \+ Brownfield, kein Codegen, meinungsstarke Defaults · Abgeglichen mit Spec 00

## Problem

API\-Design\-Skills sind heute Checklisten\-Prosa: Sie reden über gutes Design, hinterlassen aber kein Artefakt. Ohne OpenAPI als Source of Truth ist der Code die Doku; Fehlerformat, Paginierung, Versionierung und Idempotenz werden pro Endpoint neu erfunden; Breaking Changes bemerkt niemand, bis ein Consumer bricht; und im häufigsten Realfall — es gibt schon eine gewachsene API — helfen Greenfield\-Ratschläge gar nicht.

## Constraints

Zwei Modi: Greenfield (spec\-first entwerfen) und Brownfield (Bestand erfassen, dann normal weiterarbeiten). Kein Server\-Codegen — die Skill endet bei validierter OpenAPI plus Konventionsdatei; Implementierung läuft im normalen Entwicklungsfluss (Schnittstelle zu feature\-spec/Spec 03 und code\-review/Spec 04, deren Soll dann die OpenAPI ist). Konventionen als meinungsstarkes, projektweise überschreibbares Preset. Stacks für Brownfield\-Introspektion: FastAPI (primär), Express/Hono (sekundär). Portables Frontmatter.

## Approach

**Die OpenAPI ist das Artefakt, die Konventionsdatei ist das Gesetz, zwei Skripte sind die Polizei.**

**Skill\-Struktur:**

```
rest-api-architect/
├── SKILL.md                (Doktrin, Modi, Workflow, Contract)
├── references/
│   ├── conventions.md      (das Preset erklärt: warum RFC 9457, warum Cursor …)
│   ├── resource-modeling.md (Ressourcen schneiden, Beziehungen, Aktionen vs. Ressourcen)
│   └── evolution.md        (Deprecation statt Bruch, Versionierungs-Playbook)
├── assets/
│   ├── conventions.yaml    (maschinenlesbares Preset — Quelle für Lint-Regeln)
│   ├── spectral-ruleset.yaml (Spectral-Regeln, generiert aus conventions.yaml)
│   └── openapi-skeleton.yaml (Grundgerüst mit Error-Schema, Paginierungs-Parametern)
├── scripts/
│   ├── gen_ruleset.py      (Tier 1; conventions.yaml → spectral-ruleset.yaml)
│   ├── extract_openapi.py  (Tier 2; Brownfield: Framework-Introspektion → Ist-Spec)
│   └── gate.py             (Tier 3: Spectral + oasdiff; G2 — Lint + Breaking-Change-Check)
└── evals/evals.json
```

**Konventions\-Preset (Defaults, projektweise überschreibbar):** Fehler als RFC 9457 problem\+json mit Fehlercode\-Registry; Cursor\-Paginierung (`cursor`/`limit`, `next_cursor` in der Antwort); Pfad\-Versionierung `/v1` mit Deprecation\-Headern statt Brüchen; Idempotency\-Key\-Pflicht für unsichere POSTs; snake\_case\-Felder, Plural\-Ressourcen, keine Verben in Pfaden (definierte Ausnahmen für echte Aktionen); Zeitstempel als RFC 3339 UTC. Das mitgelieferte Preset lebt maschinenlesbar in `assets/conventions.yaml`, der Projekt\-Override nach Spec 00 in `.skills/rest-api-architect/conventions.yaml`; `gen_ruleset.py` erzeugt daraus das Spectral\-Ruleset — eine Quelle, kein Drift zwischen Doku und Lint.

**Workflow Greenfield:** Ressourcenmodell (Entitäten, Beziehungen, Lebenszyklen — References\-gestützt) → OpenAPI\-Entwurf aus dem Skeleton, jede Design\-Entscheidung gegen conventions.yaml → `gate.py` (Spectral) → Review\-Fragen nur für echte Abweichungen vom Preset. Contract: Kein Endpoint ohne Spec\-Eintrag; keine Antwort ohne Error\-Schema\-Bezug; Abweichungen vom Preset stehen als begründete `x-deviation`\-Einträge in der Spec, nicht stillschweigend im Code.

**Workflow Brownfield:** `extract_openapi.py` introspiziert deterministisch (FastAPI: Routen/Models direkt; Express/Hono: Router\-Scan) → Ist\-OpenAPI; wo Introspektion nicht reicht, liest das LLM den Code und markiert die Einträge `x-verified: false` — extrahiert ist nicht gesichert, und der Unterschied bleibt sichtbar. Danach: Konventions\-Audit (Ist vs. Preset als Bericht, ohne Zwang zur Sofort\-Sanierung) und ab dem nächsten Endpoint gilt der Greenfield\-Workflow gegen die Ist\-Spec.

**Breaking\-Change\-Gate:** `gate.py` führt oasdiff gegen die letzte committete Spec\-Version: Brüche (Feld entfernt/umbenannt, Pflichtfeld ergänzt, Statuscode geändert) werden als Verstoß gemeldet, mit Verweis aufs Evolution\-Playbook (Deprecation\-Pfad) — der Fix ist dokumentierte Migration, nie stiller Bruch. Durchsetzungsgrad **G2** (Spec 00 §4): Das Urteil ist maschinell, der Aufruf bleibt Teil des Workflows — wer an der Skill vorbei committet, umgeht es.

**Anti\-Rationalisierungs\-Tabelle (Auszug):** „Das Feld heißt besser X, benenne ich um" → Umbenennung ist ein Breaking Change; Deprecation\-Pfad oder lassen. „Kleiner interner Endpoint, braucht keine Spec" → interne Endpoints brechen Consumer genauso; keine Ausnahme. „Fehler gebe ich als String zurück, ist schneller" → problem\+json ist das Preset; Abweichung nur als begründetes x\-deviation.

**Evals:** (1) Feature\-Wunsch, der zur Feld\-Umbenennung verführt — schlägt das Gate an und kommt der Deprecation\-Pfad? (2) Brownfield\-Repo mit Mischmasch\-Konventionen — entsteht ein ehrlicher Audit\-Bericht statt ungefragter Massen\-Refactorings? (3) Endpoint\-Implementierung ohne Spec\-Update provoziert — greift der Contract? (4) Exotisches Framework ohne Introspektions\-Support — werden die LLM\-extrahierten Einträge als unverifiziert markiert?

## Alternatives considered

Codegen mit Framework\-Adaptern (Router\-Gerüste aus der Spec) verworfen: Framework\-Pflege in der Skill, Lock\-in, und der normale Entwicklungsfluss implementiert ohnehin gegen die Spec. Konventions\-Interview pro Projekt verworfen zugunsten sofort nutzbarer Defaults mit Override — das Interview bleibt als Weg, `conventions.yaml` initial anzupassen. Runtime\-Capture für Brownfield (Traffic mitschneiden → Schema) verworfen: mächtig, aber schwergewichtig und umgebungsabhängig; Introspektion \+ markierter LLM\-Fallback deckt den Bedarf. GraphQL bewusst nicht mitbehandelt — eigene Spur, falls je nötig.

## Out of scope

Server\-/Client\-Codegen, GraphQL/gRPC, API\-Gateway\-/Deployment\-Konfiguration, Auth\-Implementierung (das Preset definiert nur die Konventions\-Schnittstelle: Bearer \+ Fehlerformate), Load\-/Contract\-Testing (testing\-strategy/Spec 05 übernimmt mit rest\-api.md).

## Open questions

Gilt eine Spec pro Service oder pro Repo (Monorepo\-Fall)? — Spec 10 stellt dieselbe Frage für `ARCHITECTURE.md`; beide sollten gemeinsam beantwortet werden. Soll das Konventions\-Audit im Brownfield\-Modus eine priorisierte Sanierungs\-Liste erzeugen (Brücke zu `superpowers:writing-plans`)? Fehlercode\-Registry: zentral in conventions.yaml oder pro Domäne gesplittet?

## Next steps

conventions.yaml \+ Spectral\-Ruleset als erstes bauen (sie tragen alles); openapi\-skeleton.yaml mit Error\-/Paginierungs\-Grundgerüst; extract\_openapi.py für FastAPI implementieren; gate.py mit oasdiff\-Integration; Eval 1 (Umbenennungs\-Trap) zuerst fahren; Description mit Routing zu feature\-spec (Soll\-Lieferant) und testing\-strategy (Contract\-Tests) schärfen.
