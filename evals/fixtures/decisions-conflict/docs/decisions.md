<!-- skill: feature-spec | schema: 1 | generated: feature-spec Ernte nach "fehler-antworten-vereinheitlichen" -->
# Entscheidungen

- 2026-05-01 — Alle API-Fehler folgen `{"error": {"code": "<SCREAMING_SNAKE>", "message": "<Text>"}}`; `error.code` ist Pflicht und wird von Clients zur Unterscheidung ausgewertet, nicht der Text. (Anlass: fehler-antworten-vereinheitlichen)
