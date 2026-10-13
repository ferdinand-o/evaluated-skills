# plan.md — Ansicht für den Nutzer, Block für apply

`plan_repo.py` schreibt `.skills/cache/setup-repo/plan.md`. `apply_repo.py` liest daraus
nur den Block; alles andere ist für den Menschen. Aufbau, Normalisierung und Hash folgen
setup-user (Spec 21), nur relativ zur Repo-Wurzel statt zum Config-Verzeichnis.

## Aufbau

1. **Kopfzeile** in Zeile 1, nach `docs/artifact-header.md`:
   `<!-- skill: setup-repo | schema: 1 | generated: python …/plan_repo.py … -->`.
   Sie steht außerhalb des Hashes, weil sie das Kommando wie getippt trägt.
2. **Ansicht:** erkannter Stack, die Zeile `Verifikation: …` mit Quelle, je Kandidat eine
   Zeile „Kandidat · Quelle · Klasse", Budget, Plugins je Repo, abwählbare Hooks,
   geplante Änderungen als Diff je Datei, Annahmen. Dazu der Hinweis, dass
   `.skills/cache/` bis `apply` im Zielrepo unversioniert sichtbar ist.
3. **Block:** ein Codeblock mit Info-String `json setup-repo-plan`, genau einmal in der
   Datei. Fehlt er oder steht er zweimal, bricht `apply` ab.

## Felder des Blocks

| Feld | Inhalt |
| --- | --- |
| `schema` | `1` |
| `verification` | `command` (Text oder `null`), `source` (etwa `Makefile: check`), `derived` (`true` nur bei abgeleitetem Befehl, etwa aus einer `.dproj`) |
| `candidates` | je Kandidat `id`, `text`, `source`, `checked_by`, `class` (`ableitbar`, `werkzeug`, `regel` oder `offen`), `paths` (Liste, leer für alle Dateien) |
| `options` | `verify_hook` (Standard `false`), `goal_hook` (Standard `true`, abwählbar mit `--without-goal-hook`), `deny_secrets` (Standard `false`) |
| `plugins` | Objekt ID → `true`/`false` für `.claude/settings.local.json`; leer, wenn keine ID gefunden wurde |
| `budget` | `lines` (immer geladene Zeilen nach apply) und `limit` (`150`) |
| `operations` | Liste, je Eintrag `path` relativ zur Repo-Wurzel, `action` und je nach Aktion `content`, `patch` oder `lines` |
| `base` | je berührtem Pfad der SHA-256 des Bestands oder `null`, wenn die Datei fehlt |
| `hash` | SHA-256 über den Block ohne `hash` |

Aktionen:

- `create` — Datei mit `content` anlegen; nur erlaubt, wenn `base` für den Pfad `null` ist.
- `append` — Ergänzung an eine vorhandene Datei, etwa die bestehende CLAUDE.md; `content`
  ist der angehängte Text.
- `merge-json` — für `.claude/settings.json` und `.claude/settings.local.json`; `patch` ist
  ein Objekt nach den Mischregeln unten.
- `copy` — Laufzeitskript aus `assets/runtime/` nach `.claude/hooks/`; `content` ist der
  Dateiinhalt, damit der Hash ihn deckt.

Ziele (`references/goals.md`): `docs/goals.md` als `create` aus `assets/goals.md`, nur wenn
die Datei fehlt — ein vorhandener Ledger wird nie angefasst; `.claude/rules/goals.md` als
`create` aus `assets/rules/goals.md` oder, wenn vorhanden, gar nicht; mit `goal_hook`
dazu `.claude/hooks/goal_scope.py` als `copy` und beide Ereignisse aus
`assets/hooks/goal-scope.json` im Patch für `.claude/settings.json`.
- `gitignore` — `lines` sind die Zeilen, die in `.gitignore` noch fehlen; `/x` und `x`
  gelten als dieselbe Zeile. `apply` hängt an, was dann noch fehlt.

## Mischregeln für die Settings

- `.claude/settings.json`: `permissions.allow` und `permissions.deny` werden als Listen
  vereinigt, Reihenfolge des Bestands zuerst. Unter `hooks.<Ereignis>` wird der eigene
  Eintrag am Suffix `.claude/hooks/verify_stop.py` oder `.claude/hooks/goal_scope.py` im
  Kommando erkannt und ersetzt, sonst angehängt; fremde Einträge bleiben. Alle anderen Schlüssel fasst `apply` nicht an,
  auch `enabledPlugins` nicht.
- `.claude/settings.local.json`: nur `enabledPlugins`, je ID gesetzt; alles andere bleibt.
- Schreibformat: Einrückung 2, ohne ASCII-Escapes, Schlüsselreihenfolge des Bestands, LF,
  Zeilenumbruch am Ende. `.claude/settings.json` wird als Letztes geschrieben.

## Normalisierung und Hash

- Jeder Text im Block steht mit LF; Pfade sind relativ zur Repo-Wurzel und nutzen `/`.
- `base` hasht den Bestand nach derselben Normalisierung (CRLF wird LF). Dateien unter
  `.claude/skills/` stehen nie im Block und nie in `base`.
- Hash = SHA-256 über
  `json.dumps(block_ohne_hash, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`
  als UTF-8. Kein Zeitstempel, kein absoluter Pfad, kein HEAD-SHA, keine Kopfzeile.
- `plan_repo.py` und `apply_repo.py` rechnen den Hash je selbst; ein Test hält beide
  gleich (keine Imports zwischen Skripten).

## Was apply prüft

1. Der Block parst, `schema` ist bekannt, `hash` stimmt.
2. Jeder `base`-Hash stimmt mit dem heutigen Bestand.
3. Keine versionierte Zieldatei hat uncommittete Änderungen.

Scheitert eine Prüfung, schreibt `apply` nur `apply.md` mit dem Grund. `apply_repo.py
--check` liest denselben Block und meldet, welche Operation gegen den heutigen Bestand
noch etwas ändern würde.
