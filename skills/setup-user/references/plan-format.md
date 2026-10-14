# plan.md — Ansicht für den Nutzer, Block für apply

`inspect_config.py` schreibt `<config-dir>/setup-user/plan.md`. `apply_config.py` liest
daraus nur den Block; alles andere ist für den Menschen.

## Aufbau

1. **Kopfzeile** in Zeile 1, nach `docs/artifact-header.md`:
   `<!-- skill: setup-user | schema: 1 | generated: python …/inspect_config.py --config-dir … -->`.
   Sie steht außerhalb des Hashes, weil sie das Kommando wie getippt trägt.
2. **Ansicht:** Ziel (aufgelöster Pfad), Bestand, geplante Änderungen als Diff je Datei,
   Konflikte, Annahmen (Interview-Werte aus den Assets, wenn niemand geantwortet hat),
   Statusline-Befund, das Angebot `permissions.deny` mit seiner Grenze.
3. **Block:** ein Codeblock mit Info-String `json setup-user-plan`, genau einmal in der
   Datei. Fehlt er oder steht er zweimal, bricht `apply` ab.

## Felder des Blocks

| Feld | Inhalt |
| --- | --- |
| `schema` | `1` |
| `python` | aufgelöster Interpreter für die Kommandos, etwa `python3` |
| `answers` | Interview-Antworten: `language`, `tone`, `shell`, `git`; fehlende als Asset-Wert |
| `statusline` | `own` (Kennzeile oder bekannter Hash), `none`, `foreign`; bei `foreign` der Pfad |
| `plugins` | Plugin-Profil aus `route_check.py`: `checked`, `reason`, `profile` (je Eintrag `id`, `action` `set`/`conflict`/`keep`/`none`, `reason`) und `condition` (Teile a bis c, `met`); ohne absolute Pfade |
| `operations` | Liste, je Eintrag `path` relativ zu `<config-dir>`, `action`, und je nach Aktion `content` oder `patch` |
| `base` | je berührtem Pfad der SHA-256 des Bestands oder `null`, wenn die Datei fehlt |
| `hash` | SHA-256 über den Block ohne `hash` |

Aktionen:

- `create` — Datei mit `content` anlegen; nur erlaubt, wenn `base` für den Pfad `null` ist.
- `copy` — Laufzeitskript aus `assets/runtime/` kopieren; `content` ist der Dateiinhalt,
  damit der Hash ihn deckt.
- `merge` — nur für `settings.json`; `patch` ist ein Objekt mit den Schlüsseln, die
  `references/settings-merge.md` erlaubt.
- `append` — bestätigte Ergänzung an eine vorhandene CLAUDE.md oder Regeldatei; `content`
  ist der angehängte Text.

## Normalisierung und Hash

- Jeder Text im Block (Inhalte, Patches) steht mit LF und mit dem Platzhalter
  `<config-dir>` statt dem absoluten Pfad des Config-Verzeichnisses.
- `base` hasht den Bestand nach derselben Normalisierung: CRLF wird LF, der absolute Pfad
  (auch mit Backslashes) wird `<config-dir>`.
- Hash = SHA-256 über
  `json.dumps(block_ohne_hash, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`
  als UTF-8. Kein Zeitstempel, kein absoluter Pfad, keine Kopfzeile.
- `inspect_config.py` und `apply_config.py` rechnen den Hash je selbst; ein Test hält
  beide gleich (keine Imports zwischen Skripten).

## Was apply prüft

1. `--config-dir` steht auf der Kommandozeile und das Verzeichnis existiert.
2. Der Block parst, `schema` ist bekannt, `hash` stimmt.
3. Jeder `base`-Hash stimmt mit dem heutigen Bestand.

Scheitert eine Prüfung, schreibt `apply` nichts und nennt den Grund.
