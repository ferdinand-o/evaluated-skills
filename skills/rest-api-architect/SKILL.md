---
name: rest-api-architect
description: Use when designing a new REST API from scratch (Greenfield) or capturing an existing one before extending it (Brownfield) — produces a validated OpenAPI spec plus a project-wide conventions file (errors, pagination, versioning, idempotency, naming). Triggers include "REST-API entwerfen", "Endpoint hinzufügen", "API-Konventionen", "Breaking Change prüfen", "bestehende API erfassen". Routes to feature-spec (07 consumes its Soll as the target shape), testing-strategy (07's output feeds rest-api.md contract tests), and work-plan (breaks a Brownfield audit into work — this skill reports, it never plans). Not for server/client codegen, GraphQL/gRPC, auth implementation, or API-gateway/deployment config — those are explicitly out of scope.
---

# rest-api-architect — Spec-first mit Konventions-Preset

**Die OpenAPI ist das Artefakt, die Konventionsdatei ist das Gesetz, die Skripte sind die
Polizei.** Kein Server-Codegen — diese Skill endet bei validierter OpenAPI plus
Konventionsdatei. Implementierung läuft im normalen Entwicklungsfluss.

## Modus wählen

- **Greenfield** — API existiert noch nicht oder wird um klar neue Ressourcen erweitert.
- **Brownfield** — es gibt bereits Code. Immer zuerst erfassen, nie aus dem Gedächtnis
  entwerfen.

## Greenfield-Ablauf

1. Ressourcenmodell klären (`references/resource-modeling.md`): Ressourcen, Beziehungen,
   Aktionen vs. Zustandsänderung.
2. Entwurf aus `assets/openapi-skeleton.yaml` nach `api/openapi.yaml` (pro Service, R4 — im
   Monorepo eine Spec je Service-Verzeichnis, abgelegt beim Service).
3. Jede Design-Entscheidung gegen `assets/conventions.json` (Override:
   `.skills/rest-api-architect/conventions.json`, falls vorhanden). Abweichung → begründeter
   `x-deviation`-Eintrag in der Spec, nie stillschweigend im Code.
4. `python "${CLAUDE_SKILL_DIR}/scripts/gate.py" --openapi api/openapi.yaml --ruleset <ruleset> --conventions <conventions> [--previous <letzte committete Version>]`
5. Nur echte Preset-Abweichungen zurück an den Nutzer — keine Architekturberatung für einen
   bereits konformen, trivialen Endpoint.

## Brownfield-Ablauf

1. `python "${CLAUDE_SKILL_DIR}/scripts/extract_openapi.py" --framework {fastapi,express,hono,auto} --src <verzeichnis> --out api/openapi.yaml` — **statische Analyse, importiert die Anwendung nie** (R2: das ist eine Sicherheitsfrage, nicht nur eine Abhängigkeitsfrage — ein Import führt DB-Verbindungen, Netzwerkaufrufe und Migrationen aus).
2. Was nicht deterministisch extrahiert wurde, trägt `x-verified: false` — sichtbar, nicht
   stillschweigend geraten. Liest du (Claude) danach Code, um Lücken zu schließen, bleibt die
   Markierung bestehen, bis ein Mensch sie bestätigt.
3. **Audit, kein Umbau (R5):** Ist vs. Preset als Bericht nach `docs/api-audit-<service>.md`
   — gewichtet nach Schwere, ohne ungefragte Sanierung. Für die Zerlegung in Arbeit: an
   `work-plan` verweisen, nicht selbst planen.
4. Ab dem nächsten Endpoint gilt der Greenfield-Ablauf gegen die jetzt vorliegende Ist-Spec.

## Contract

- Kein Endpoint ohne Eintrag in `api/openapi.yaml` — ein im Code implementierter, in der Spec
  fehlender Endpoint ist ein Verstoß, den du beim Review benennst.
- Keine Antwort ohne Bezug aufs Error-Schema (`components.schemas.Error`, `problem+json`).
- Breaking Changes (Feld entfernt/umbenannt, Pflichtfeld ergänzt, Statuscode geändert) sind ein
  Verstoß mit Verweis auf `references/evolution.md` — der Fix ist dokumentierte Migration, nie
  stiller Bruch.

## Anti-Rationalisierungs-Tabelle

| Gedanke | Realität |
| --- | --- |
| „Das Feld heißt besser X, benenne ich um" | Umbenennung ist ein Breaking Change. Deprecation-Pfad (`references/evolution.md`) oder lassen. |
| „Kleiner interner Endpoint, braucht keine Spec" | Interne Endpoints brechen Consumer genauso. Keine Ausnahme. |
| „Fehler gebe ich als String zurück, ist schneller" | `problem+json` ist das Preset. Abweichung nur als begründetes `x-deviation`. |
| „Ich erfasse das Brownfield-Repo und räume gleich mit auf" | Das Audit berichtet, es baut nicht um (R5). Sanierung ist eine eigene, geplante Arbeit. |
| „Route sieht klar aus, ich vertraue der Extraktion" | `x-verified: false` heißt: nicht deterministisch geprüft. Nicht stillschweigend auf `true` heben. |
| „Ein Endpoint mehr, ich gliedere die Fehlercodes gleich neu" | Ab ~50 Codes warnt die Skill (R6). Sie gliedert nicht selbst — das ist eine Projektentscheidung. |

## Gate-Ehrlichkeit (Spec 00 §4)

`gate.py` ist **G2**: das Urteil ist maschinell, der Aufruf bleibt Teil des Workflows — wer
daran vorbei committet, umgeht es. Es heißt nirgends „Blocker". Fehlt Spectral/oasdiff/npx,
meldet das Ergebnis sichtbar `ungeprüft (Spectral/oasdiff nicht verfügbar)` — die
Konventions-Checkliste (Textprüfung, kein externes Werkzeug) läuft davon unabhängig immer und
wird nie übersprungen.

## Leerfälle

- **Kein Vorgänger für den Breaking-Change-Check** (erster Lauf, `--previous` fehlt): Bericht
  sagt „kein Vorgänger, Breaking-Change-Check übersprungen" — nicht stillschweigend „bestanden".
- **Brownfield-Audit ohne Abweichungen:** der Bericht sagt das explizit („keine Abweichungen
  vom Preset gefunden"), keine erfundenen Verbesserungsvorschläge.
- **Exotisches Framework, null statisch gefundene Routen:** `api/openapi.yaml` trägt einen
  erklärenden Hinweis (`x-extraction.note`) statt einer leeren Spec, die Vollständigkeit
  vortäuscht.
- **Fehlercode-Registry unter der Warnschwelle:** keine Gliederungsempfehlung. Erst ab
  `errors.registry.warn_threshold` (Default 50) wird gewarnt, nie selbst umgebaut.
- **Triviale, bereits konforme Änderung:** kein Audit-Bericht, keine `x-deviation`-Einträge,
  keine Architekturdiskussion. Zeremonie für einen konformen Endpoint ist ein Fehler dieser
  Skill, kein Zeichen von Gründlichkeit.

## Abgrenzung

- **feature-spec** liefert das Soll, gegen das diese Skill entwirft — nicht umgekehrt.
- **testing-strategy** übernimmt Contract-Tests gegen `api/openapi.yaml` (`rest-api.md`).
- **work-plan** zerlegt einen Brownfield-Befund in Arbeit — diese Skill
  berichtet, sie plant nicht (R5).
- Kein Server-/Client-Codegen, kein GraphQL/gRPC, keine Auth-Implementierung (nur die
  Preset-Schnittstelle: Bearer + Fehlerformate), kein API-Gateway/Deployment.
