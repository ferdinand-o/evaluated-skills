<!-- skill: setup-user | schema: 1 | generated: von Hand beim Bau von Spec 21, Task 1 -->
# Statusline-Vorlage des Nutzers

`statusline-original.py` ist die Statusline, die der Nutzer am 2026-10-11 als seine
heute eingetragene Fassung übergeben hat, unverändert. Eine korrigierte Fassung aus dem
Review vom 2026-10-07 lag nicht vor; die Korrektur entsteht in Task 5 als
`skills/setup-user/assets/runtime/statusline.py`.

| Datei | SHA-256, LF-normalisiert |
| --- | --- |
| `statusline-original.py` | `6e411ffd30aff8d257801026da79a7de61c1bc9fd5dca8f7ce7214df60a20eaa` |

Beobachtet am 2026-10-11 mit `HOME` auf einem Temp-Verzeichnis:

- Volle Beispiel-Eingabe: vier Zeilen (Modell und Verzeichnis, Kontext mit Kosten und
  Dauer, 5-Stunden-Limit, Wochen-Limit), Exit 0, Cache unter `~/.claude/usage-cache.json`.
- Leeres stdin: `JSONDecodeError`, Exit 1.
- `"context_window": null`: `AttributeError`, Exit 1.
- Der Cache-Pfad folgt `HOME`, nicht `CLAUDE_CONFIG_DIR`; ein Lauf ohne `rate_limits`
  schreibt beide Fenster mit `null`.

Tests führen die Datei nur mit `HOME` und `CLAUDE_CONFIG_DIR` auf `tmp_path` aus.
