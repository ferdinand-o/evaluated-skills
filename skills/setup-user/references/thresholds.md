# Schwellen, Zustand und Hinweise

## Schwellen

| Art | Schwellen | Quelle im stdin der Statusline |
| --- | --- | --- |
| Kontext | 60 %, 80 % | `context_window.used_percentage` |
| 5-Stunden-Limit | 80 % | `rate_limits.five_hour.used_percentage` |
| 7-Tage-Limit | 85 % | `rate_limits.seven_day.used_percentage` |

`apply` schreibt sie nach `<config-dir>/setup-user/thresholds.json` (mit `_meta`); der
Hook liest sie dort und nimmt bei fehlender oder kaputter Datei diese Werte.

## Was die Statusline schreibt

- **Limit-Cache** `<config-dir>/usage-cache.json`: je Fenster (`five_hour`, `seven_day`)
  `used_percentage` und `resets_at_epoch`, dazu `_meta`. Fehlt ein Fenster, ist es
  `null`, oder ist `used_percentage` `null`, bleibt der alte Wert dieses Fensters.
  Bisherige Schlüssel des Caches bleiben, weil andere Werkzeuge sie lesen.
- **Kontextzustand** `<config-dir>/setup-user/state/context-<session_id>.json`:
  `{"_meta": …, "session_id": …, "used_percentage": <Zahl oder null>}`. Fehlt der Wert,
  steht `null`, nie der alte.

## Gültigkeit

- Kontext gilt, solange die `session_id` des Prompts der des Zustands gleicht.
- Ein Limitfenster gilt, solange `resets_at_epoch` in der Zukunft liegt. Es gibt keine
  Frist: Ein Limit steigt im Fenster nur, ein älterer Wert über der Schwelle ist eine
  wahre Untergrenze.
- Fehlt ein Wert oder ist er `null`, schweigt der Hook für diese Art.

## Merker

- Kontext: `state/hints-<session_id>.json` hält je Schwelle `true`, wenn gemeldet. Fällt
  der Wert unter eine Schwelle, wird sie wieder `false`, also scharf.
- Limits: `state/limit-hints.json` hält gemeldete Schlüssel `<fenster>:<schwelle>:<resets_at_epoch>`.
  Ein neues Fenster hat einen neuen Schlüssel und ist von selbst scharf, für alle
  Sessions des Accounts.
- Der Hook liest und schreibt seine Merker bei jedem Lauf, damit das Aufräumen eine
  laufende Session nicht trifft.

## Ein Hinweis je Prompt

Je Art zählt nur die höchste neu überschrittene Schwelle; niedrigere, im selben Schritt
überschrittene gelten als gemeldet. Treffen Kontext und ein Limit zugleich, stehen beide
in einem Text.

## Ausgabe

Genau ein JSON-Objekt auf stdout, sonst nichts:

    {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "[setup-user] …"}}

Beim Schweigen bleibt stdout leer. Der Text ist eine Feststellung, keine Anweisung, weil
imperative Texte Claudes Schutz gegen Prompt-Injection auslösen können (hooks, „Add
context for Claude"):

- „[setup-user] Kontext 63 % (Schwelle 60 %). Laut Nutzerregel context.md ist das der
  Punkt für Handoff und /clear."
- „[setup-user] 5-Stunden-Limit 82 % (Schwelle 80 %), Reset 14:20 UTC."

## Aufräumen

Die Statusline löscht beim Schreiben Dateien unter `state/`, deren Änderungszeit älter
als 24 Stunden ist, und liegengebliebene `*.tmp` älter als eine Stunde.
