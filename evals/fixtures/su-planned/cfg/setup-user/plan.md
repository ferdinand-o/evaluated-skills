<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py --config-dir /home/user/cc-skills/evals/fixtures/su-planned/cfg -->

# setup-user — Plan

Ziel: `/home/user/cc-skills/evals/fixtures/su-planned/cfg` · Hash `5944f63b0ed43783` · Interpreter `python3`

## Statusline

Keine Statusline eingetragen; `apply` setzt das Asset ein.

## Annahmen

- git: kein Commit und kein Push ohne Auftrag (Asset-Wert, nicht gefragt oder nicht beantwortet)
- language: Deutsch (Asset-Wert, nicht gefragt oder nicht beantwortet)
- shell: bash (Asset-Wert, nicht gefragt oder nicht beantwortet)
- tone: knapp und sachlich (Asset-Wert, nicht gefragt oder nicht beantwortet)

## Plugins

- ungeprüft — keine Plugins unter <config-dir>/plugins; `enabledPlugins` bleibt unberührt.

## Änderungen

### `setup-user/runtime/context_hint.py` — copy (neu)

```diff
--- vorher
+++ nachher
@@ -0,0 +1,179 @@
+#!/usr/bin/env python3
+# setup-user: context_hint
+"""UserPromptSubmit-Hook: meldet Claude das Überschreiten einer Kontext- oder Limitschwelle.
+
+Tier 1: nur Stdlib. Liest den Kontextzustand, den die Statusline je Session schreibt,
+und den Limit-Cache des Accounts; Format und Regeln stehen in
+skills/setup-user/references/thresholds.md. Der Hook hält nie etwas an: Jede Ausnahme
+wird gefangen, es gibt kein argparse, und er endet immer mit Exit 0. Beim Schweigen
+bleibt stdout leer; sonst steht dort genau ein JSON-Objekt mit
+hookSpecificOutput.hookEventName und additionalContext.
+"""
+
+import json
+import os
+import re
+import sys
+import time
+from pathlib import Path
+
+DEFAULT_THRESHOLDS = {"context": [60, 80], "five_hour": [80], "seven_day": [85]}
+LIMIT_LABELS = {"five_hour": "5-Stunden-Limit", "seven_day": "7-Tage-Limit"}
+SESSION_RE = re.compile(r"[A-Za-z0-9_-]+")
+META = {"skill": "setup-user", "schema": 1, "generated": "assets/runtime/context_hint.py"}
+
+
+def _config_dir() -> Path:
+    env = os.environ.get("CLAUDE_CONFIG_DIR")
+    if env:
+        return Path(env)
+    here = Path(__file__).resolve()
+    if here.parent.name == "runtime" and here.parent.parent.name == "setup-user":
+        return here.parent.parent.parent
+    return Path.home() / ".claude"
+
+
+def _read_json(path: Path):
+    try:
… 142 Zeilen mehr
```

### `setup-user/runtime/statusline.py` — copy (neu)

```diff
--- vorher
+++ nachher
@@ -0,0 +1,292 @@
+#!/usr/bin/env python3
+# setup-user: statusline
+"""Claude Code Statusline.
+
+Zeile 1: [Modell] Verzeichnis | Git-Branch
+Zeile 2: Contextfenster-Balken | Session-Kosten | Session-Dauer
+Zeile 3/4: Claude.ai Nutzungslimits (5h / 7 Tage) als Balken mit Reset-Zeit
+           in Europe/Berlin
+
+Mehrzeilen-Ausgabe: siehe https://code.claude.com/docs/en/statusline#display-multiple-lines
+Jede per print() ausgegebene Zeile wird als eigene Statuszeile dargestellt.
+
+Berechnet den Europe/Berlin-Offset selbst (EU-DST-Regel), weil das
+zoneinfo-Modul unter Windows ohne das zusaetzliche Paket "tzdata" keine
+IANA-Zeitzonendatenbank findet.
+
+Asset von setup-user (Spec 21), Vorlage ist die Statusline des Nutzers vom 2026-10-11
+(tests/fixtures/setup-user/statusline-original.py); die Anzeige ist gleich. Korrigiert:
+stdin als UTF-8-Bytes, leeres oder kaputtes stdin und null-Felder brechen nichts; die
+Zeilen kommen zuerst, geschrieben wird danach; der Limit-Cache liegt im
+Config-Verzeichnis ($CLAUDE_CONFIG_DIR, sonst drei Ebenen über dieser Datei, sonst
+~/.claude) und behält ein Fenster, für das kein neuer Wert kommt; je Session entsteht
+setup-user/state/context-<session_id>.json für den Kontext-Hinweis; geschrieben wird
+atomar; das Skript endet immer mit Exit 0. Format: references/thresholds.md.
+"""
+import calendar
+import json
+import os
+import re
+import subprocess
+import sys
+import time as _time
+from datetime import date, datetime, time, timedelta, timezone
+from pathlib import Path
+
+CYAN = "\033[36m"
+GREEN = "\033[32m"
… 255 Zeilen mehr
```

### `setup-user/thresholds.json` — copy (neu)

```diff
--- vorher
+++ nachher
@@ -0,0 +1,17 @@
+{
+  "_meta": {
+    "skill": "setup-user",
+    "schema": 1,
+    "generated": "scripts/apply_config.py"
+  },
+  "context": [
+    60,
+    80
+  ],
+  "five_hour": [
+    80
+  ],
+  "seven_day": [
+    85
+  ]
+}
```

### `CLAUDE.md` — create (neu)

```diff
--- vorher
+++ nachher
@@ -0,0 +1,27 @@
+<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py, Vorlage assets/CLAUDE.md.tmpl -->
+# Persönliche Vorgaben für alle Projekte
+
+Gilt in jedem Repo, solange dessen eigene CLAUDE.md nichts anderes sagt. Die Details
+stehen in `rules/`; diese Datei bleibt kurz, weil sie in jeder Session geladen wird.
+
+## Arbeitsweise
+
+- Sprache in Antworten und Commit-Texten: Deutsch. Ton: knapp und sachlich.
+- Shell auf diesem Rechner: bash. Befehle so schreiben, dass sie dort laufen.
+- Git: kein Commit und kein Push ohne Auftrag.
+- Erst die Lage prüfen (Dateien, Tests, Stand), dann handeln; nichts behaupten, was
+  nicht gelesen oder gemessen ist.
+- Fertig heißt geprüft. Was nicht geprüft werden konnte, heißt so und nennt den Grund.
+
+## Regeln
+
+- `rules/communication.md` — Sprache, Ton, Antwortlänge
+- `rules/verification.md` — Belege vor Erfolgsmeldungen, Review-Befunde nachmessen
+- `rules/context.md` — was `[setup-user]`-Hinweise bedeuten
+- `rules/git.md` — Commits und Pushes
+
+## Repo-Regeln gehen vor
+
+Was ein Repo in seiner CLAUDE.md, in `.claude/rules/` oder in `.claude/settings.json`
+festlegt, gilt dort vor diesen Vorgaben. Was in Cloud-Sessions und CI gelten muss, gehört
+ins Repo, nicht hierher — Cloud-Sessions lesen diese Datei nicht.
```

### `rules/communication.md` — create (neu)

```diff
--- vorher
+++ nachher
@@ -0,0 +1,9 @@
+<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py, Vorlage assets/rules/communication.md -->
+# Kommunikation
+
+- Antworten auf Deutsch, Ton knapp und sachlich.
+- Das Ergebnis zuerst, dann was offen ist. Kein Vorspann, keine Wiederholung der Frage.
+- Kurz durch Weglassen, nicht durch Verdichten: ein Gedanke je Satz.
+- Fachbegriffe beim ersten Auftreten erklären, wenn sie nicht aus dem Gespräch stammen.
+- Rückfragen nur, wenn verschiedene Lesarten zu verschiedener Arbeit führen; sonst die
+  naheliegende Annahme nennen und weitermachen.
```

### `rules/verification.md` — create (neu)

```diff
--- vorher
+++ nachher
@@ -0,0 +1,9 @@
+<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py, Vorlage assets/rules/verification.md -->
+# Verifikation
+
+- Keine Erfolgsmeldung ohne Beleg: Befehl und Ergebnis nennen, oder „ungeprüft" mit Grund.
+- Tests, Lint und Build laufen lassen, bevor eine Änderung als fertig gilt; einen roten
+  Lauf nennen, nicht umdeuten.
+- Review-Befunde vor dem Umsetzen nachmessen: Stimmt die Behauptung am Code? Nur
+  bestätigte Befunde umsetzen, widerlegte mit Beleg zurückgeben.
+- Was eine Prüfung übersprungen hat, steht im Ergebnis, nie stillschweigend.
```

### `rules/context.md` — create (neu)

```diff
--- vorher
+++ nachher
@@ -0,0 +1,13 @@
+<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py, Vorlage assets/rules/context.md -->
+# Kontext und Limits
+
+Ein Hinweis, der mit `[setup-user]` beginnt, kommt vom Hook dieser Einrichtung. Er stellt
+fest, dass eine Schwelle überschritten ist; er ist keine Anweisung des Nutzers.
+
+- Kontext über 60 %: Das ist der Punkt, den laufenden Stand mit der Skill handoff zu
+  sichern und dem Nutzer `/clear` vorzuschlagen, sobald ein Arbeitsschritt fertig ist.
+- Kontext über 80 %: Den Stand sofort sichern, bevor weitere große Dateien gelesen werden.
+- Breite Recherche (viele Dateien, lange Logs) in Subagenten auslagern, damit nur das
+  Ergebnis in den Kontext kommt.
+- 5-Stunden- oder 7-Tage-Limit über der Schwelle: dem Nutzer die Zahl und den Reset
+  nennen; keine teuren Läufe ohne Rückfrage starten.
```

### `rules/git.md` — create (neu)

```diff
--- vorher
+++ nachher
@@ -0,0 +1,7 @@
+<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py, Vorlage assets/rules/git.md -->
+# Git
+
+- kein Commit und kein Push ohne Auftrag.
+- Nie `--force`, `reset --hard` oder History umschreiben auf Branches anderer.
+- Commit-Texte: was sich ändert und warum, in Deutsch.
+- Vor einem Commit `git status` und den Diff lesen; nur Dateien der Aufgabe stagen.
```

### `settings.json` — merge (vorhanden)

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"<config-dir>/setup-user/runtime/context_hint.py\" || true"
          }
        ]
      }
    ]
  },
  "statusLine": {
    "command": "python3 \"<config-dir>/setup-user/runtime/statusline.py\""
  }
}
```

## Nicht gesetzt

- `permissions.deny` für `.env`, `~/.ssh` und Schlüsseldateien wird nur auf Bestätigung gesetzt (Antwort `deny_secrets: true`). Ein Read-Deny gilt für die Datei-Werkzeuge und erkannte Bash-Dateikommandos, nicht für beliebige Unterprozesse.

## Block für apply

```json setup-user-plan
{
  "answers": {
    "git": "kein Commit und kein Push ohne Auftrag",
    "language": "Deutsch",
    "shell": "bash",
    "tone": "knapp und sachlich"
  },
  "assumed": [
    "git",
    "language",
    "shell",
    "tone"
  ],
  "base": {
    "CLAUDE.md": null,
    "rules/communication.md": null,
    "rules/context.md": null,
    "rules/git.md": null,
    "rules/verification.md": null,
    "settings.json": "3405309aa1f05fc075592fc18930866ce5072a64d5b5b2f550d9f62500061c9e",
    "setup-user/runtime/context_hint.py": null,
    "setup-user/runtime/statusline.py": null,
    "setup-user/thresholds.json": null
  },
  "hash": "5944f63b0ed43783380295177582b59c44ff27af02cf2031e49bccde876e4156",
  "operations": [
    {
      "action": "copy",
      "content": "#!/usr/bin/env python3\n# setup-user: context_hint\n\"\"\"UserPromptSubmit-Hook: meldet Claude das Überschreiten einer Kontext- oder Limitschwelle.\n\nTier 1: nur Stdlib. Liest den Kontextzustand, den die Statusline je Session schreibt,\nund den Limit-Cache des Accounts; Format und Regeln stehen in\nskills/setup-user/references/thresholds.md. Der Hook hält nie etwas an: Jede Ausnahme\nwird gefangen, es gibt kein argparse, und er endet immer mit Exit 0. Beim Schweigen\nbleibt stdout leer; sonst steht dort genau ein JSON-Objekt mit\nhookSpecificOutput.hookEventName und additionalContext.\n\"\"\"\n\nimport json\nimport os\nimport re\nimport sys\nimport time\nfrom pathlib import Path\n\nDEFAULT_THRESHOLDS = {\"context\": [60, 80], \"five_hour\": [80], \"seven_day\": [85]}\nLIMIT_LABELS = {\"five_hour\": \"5-Stunden-Limit\", \"seven_day\": \"7-Tage-Limit\"}\nSESSION_RE = re.compile(r\"[A-Za-z0-9_-]+\")\nMETA = {\"skill\": \"setup-user\", \"schema\": 1, \"generated\": \"assets/runtime/context_hint.py\"}\n\n\ndef _config_dir() -> Path:\n    env = os.environ.get(\"CLAUDE_CONFIG_DIR\")\n    if env:\n        return Path(env)\n    here = Path(__file__).resolve()\n    if here.parent.name == \"runtime\" and here.parent.parent.name == \"setup-user\":\n        return here.parent.parent.parent\n    return Path.home() / \".claude\"\n\n\ndef _read_json(path: Path):\n    try:\n        return json.loads(path.read_text(encoding=\"utf-8\"))\n    except (OSError, ValueError):\n        return None\n\n\ndef _write_json(path: Path, obj) -> None:\n    \"\"\"Atomar über eine Temp-Datei; scheitert os.replace (Windows, offener Leser), drei\n    Versuche, danach bleibt die alte Datei.\"\"\"\n    try:\n        path.parent.mkdir(parents=True, exist_ok=True)\n        tmp = path.with_name(f\"{path.name}.{os.getpid()}.tmp\")\n        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + \"\\n\", encoding=\"utf-8\")\n        for attempt in range(3):\n            try:\n                os.replace(tmp, path)\n                return\n            except OSError:\n                time.sleep(0.05 * (attempt + 1))\n        tmp.unlink(missing_ok=True)\n    except OSError:\n        pass\n\n\ndef _touch(path: Path) -> None:\n    try:\n        if path.exists():\n            os.utime(path)\n    except OSError:\n        pass\n\n\ndef _thresholds(config_dir: Path) -> dict:\n    data = _read_json(config_dir / \"setup-user\" / \"thresholds.json\")\n    result = {}\n    for kind, default in DEFAULT_THRESHOLDS.items():\n        values = data.get(kind) if isinstance(data, dict) else None\n        ok = isinstance(values, list) and values and all(isinstance(v, (int, float)) for v in values)\n        result[kind] = sorted(values) if ok else default\n    return result\n\n\ndef _number(value) -> bool:\n    return isinstance(value, (int, float)) and not isinstance(value, bool)\n\n\ndef _context_part(payload: dict, state_dir: Path, thresholds: list) -> str | None:\n    sid = payload.get(\"session_id\")\n    if not isinstance(sid, str) or not SESSION_RE.fullmatch(sid):\n        return None\n    state = _read_json(state_dir / f\"context-{sid}.json\")\n    hints_path = state_dir / f\"hints-{sid}.json\"\n    if not isinstance(state, dict) or state.get(\"session_id\") != sid or not _number(state.get(\"used_percentage\")):\n        _touch(hints_path)\n        return None\n    pct = state[\"used_percentage\"]\n    stored = _read_json(hints_path)\n    reported = stored.get(\"reported\", {}) if isinstance(stored, dict) else {}\n    if not isinstance(reported, dict):\n        reported = {}\n    updated, crossed = {}, []\n    for threshold in thresholds:\n        key = str(threshold)\n        if pct >= threshold:\n            if not reported.get(key):\n                crossed.append(threshold)\n            updated[key] = True\n        else:\n            updated[key] = False\n    if updated != reported or not isinstance(stored, dict):\n        _write_json(hints_path, {\"_meta\": META, \"session_id\": sid, \"reported\": updated})\n    else:\n        _touch(hints_path)\n    if not crossed:\n        return None\n    return (f\"Kontext {round(pct)} % (Schwelle {max(crossed)} %). \"\n            \"Laut Nutzerregel context.md ist das der Punkt für Handoff und /clear.\")\n\n\ndef _limit_parts(config_dir: Path, state_dir: Path, thresholds: dict, now: float) -> list[str]:\n    cache = _read_json(config_dir / \"usage-cache.json\")\n    path = state_dir / \"limit-hints.json\"\n    stored = _read_json(path)\n    reported = set(stored.get(\"reported\", [])) if isinstance(stored, dict) and isinstance(stored.get(\"reported\"), list) else set()\n    parts, changed = [], False\n    for window, label in LIMIT_LABELS.items():\n        entry = cache.get(window) if isinstance(cache, dict) else None\n        if not isinstance(entry, dict):\n            continue\n        pct, reset = entry.get(\"used_percentage\"), entry.get(\"resets_at_epoch\")\n        if not _number(pct) or not _number(reset) or reset <= now:\n            continue\n        crossed = []\n        for threshold in thresholds[window]:\n            key = f\"{window}:{threshold}:{int(reset)}\"\n            if pct >= threshold and key not in reported:\n                crossed.append(threshold)\n                reported.add(key)\n                changed = True\n        if crossed:\n            when = time.strftime(\"%H:%M\", time.gmtime(reset))\n            parts.append(f\"{label} {round(pct)} % (Schwelle {max(crossed)} %), Reset {when} UTC.\")\n    alive = {k for k in reported if k.rsplit(\":\", 1)[-1].isdigit() and int(k.rsplit(\":\", 1)[-1]) > now}\n    if changed or alive != reported:\n        _write_json(path, {\"_meta\": META, \"reported\": sorted(alive)})\n    else:\n        _touch(path)\n    return parts\n\n\ndef hint_for(payload, config_dir, now):\n    \"\"\"Hinweistext ohne Ausgabeform, oder None. Liest und schreibt nur die Merker unter\n    <config_dir>/setup-user/state/.\"\"\"\n    if not isinstance(payload, dict):\n        return None\n    config_dir = Path(config_dir)\n    state_dir = config_dir / \"setup-user\" / \"state\"\n    thresholds = _thresholds(config_dir)\n    parts = []\n    context = _context_part(payload, state_dir, thresholds[\"context\"])\n    if context:\n        parts.append(context)\n    parts.extend(_limit_parts(config_dir, state_dir, thresholds, now))\n    return \"[setup-user] \" + \" \".join(parts) if parts else None\n\n\ndef main():\n    try:\n        raw = sys.stdin.buffer.read().decode(\"utf-8\", errors=\"replace\")\n        payload = json.loads(raw) if raw.strip() else {}\n        text = hint_for(payload, _config_dir(), time.time())\n        if text:\n            out = {\"hookSpecificOutput\": {\"hookEventName\": \"UserPromptSubmit\", \"additionalContext\": text}}\n            sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode(\"utf-8\"))\n            sys.stdout.buffer.flush()\n    except BaseException:  # noqa: BLE001 — ein Hook-Fehler darf nie einen Prompt anhalten\n        pass\n    return 0\n\n\nif __name__ == \"__main__\":\n    main()\n    sys.exit(0)\n",
      "path": "setup-user/runtime/context_hint.py"
    },
    {
      "action": "copy",
      "content": "#!/usr/bin/env python3\n# setup-user: statusline\n\"\"\"Claude Code Statusline.\n\nZeile 1: [Modell] Verzeichnis | Git-Branch\nZeile 2: Contextfenster-Balken | Session-Kosten | Session-Dauer\nZeile 3/4: Claude.ai Nutzungslimits (5h / 7 Tage) als Balken mit Reset-Zeit\n           in Europe/Berlin\n\nMehrzeilen-Ausgabe: siehe https://code.claude.com/docs/en/statusline#display-multiple-lines\nJede per print() ausgegebene Zeile wird als eigene Statuszeile dargestellt.\n\nBerechnet den Europe/Berlin-Offset selbst (EU-DST-Regel), weil das\nzoneinfo-Modul unter Windows ohne das zusaetzliche Paket \"tzdata\" keine\nIANA-Zeitzonendatenbank findet.\n\nAsset von setup-user (Spec 21), Vorlage ist die Statusline des Nutzers vom 2026-10-11\n(tests/fixtures/setup-user/statusline-original.py); die Anzeige ist gleich. Korrigiert:\nstdin als UTF-8-Bytes, leeres oder kaputtes stdin und null-Felder brechen nichts; die\nZeilen kommen zuerst, geschrieben wird danach; der Limit-Cache liegt im\nConfig-Verzeichnis ($CLAUDE_CONFIG_DIR, sonst drei Ebenen über dieser Datei, sonst\n~/.claude) und behält ein Fenster, für das kein neuer Wert kommt; je Session entsteht\nsetup-user/state/context-<session_id>.json für den Kontext-Hinweis; geschrieben wird\natomar; das Skript endet immer mit Exit 0. Format: references/thresholds.md.\n\"\"\"\nimport calendar\nimport json\nimport os\nimport re\nimport subprocess\nimport sys\nimport time as _time\nfrom datetime import date, datetime, time, timedelta, timezone\nfrom pathlib import Path\n\nCYAN = \"\\033[36m\"\nGREEN = \"\\033[32m\"\nYELLOW = \"\\033[33m\"\nRED = \"\\033[31m\"\nRESET = \"\\033[0m\"\n\nBAR_WIDTH = 10\nFOLDER = \"\\U0001F4C1\"   # 📁\nBRANCH = \"\\U0001F33F\"   # 🌿\nCLOCK = \"⏱️\"  # ⏱️\n\nMETA = {\"skill\": \"setup-user\", \"schema\": 1, \"generated\": \"assets/runtime/statusline.py\"}\nSESSION_RE = re.compile(r\"[A-Za-z0-9_-]+\")\nSTATE_MAX_AGE = 24 * 3600\nTMP_MAX_AGE = 3600\n\n\ndef last_sunday(year, month):\n    last_day = calendar.monthrange(year, month)[1]\n    d = date(year, month, last_day)\n    offset = (d.weekday() - 6) % 7  # Monday=0 ... Sunday=6\n    return d - timedelta(days=offset)\n\n\ndef berlin_offset(dt_utc):\n    year = dt_utc.year\n    dst_start = datetime.combine(last_sunday(year, 3), time(1, 0), tzinfo=timezone.utc)\n    dst_end = datetime.combine(last_sunday(year, 10), time(1, 0), tzinfo=timezone.utc)\n    if dst_start <= dt_utc < dst_end:\n        return timedelta(hours=2), \"CEST\"\n    return timedelta(hours=1), \"CET\"\n\n\ndef to_berlin_str(epoch):\n    if epoch is None:\n        return None\n    dt_utc = datetime.fromtimestamp(epoch, tz=timezone.utc)\n    offset, abbr = berlin_offset(dt_utc)\n    dt_berlin = dt_utc + offset\n    return f\"{dt_berlin:%d.%m. %H:%M} {abbr}\"\n\n\ndef fmt_duration(ms):\n    if not ms:\n        return None\n    total_sec = int(ms // 1000)\n    mins, secs = divmod(total_sec, 60)\n    hours, mins = divmod(mins, 60)\n    if hours:\n        return f\"{hours}h {mins}m\"\n    return f\"{mins}m {secs}s\"\n\n\ndef bar(pct):\n    pct = max(0, min(100, pct))\n    filled = round(pct * BAR_WIDTH / 100)\n    color = RED if pct >= 90 else YELLOW if pct >= 70 else GREEN\n    return f\"{color}{'█' * filled}{'░' * (BAR_WIDTH - filled)}{RESET}\"\n\n\ndef git_branch(cwd):\n    try:\n        out = subprocess.run(\n            [\"git\", \"branch\", \"--show-current\"],\n            cwd=cwd, capture_output=True, text=True, timeout=2,\n        )\n        return out.stdout.strip() or None\n    except (OSError, subprocess.SubprocessError):\n        return None\n\n\n# --- Eingabe, robust gegen null, falsche Typen und kaputtes stdin -----------------\n\ndef _obj(value):\n    return value if isinstance(value, dict) else {}\n\n\ndef _num(value):\n    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None\n\n\ndef read_input():\n    try:\n        raw = sys.stdin.buffer.read().decode(\"utf-8\", errors=\"replace\")\n        data = json.loads(raw) if raw.strip() else {}\n    except (OSError, ValueError):\n        data = {}\n    return data if isinstance(data, dict) else {}\n\n\n# --- Anzeige (gleich der Vorlage) --------------------------------------------------\n\ndef render(data):\n    model = _obj(data.get(\"model\")).get(\"display_name\", \"?\")\n    workspace = _obj(data.get(\"workspace\"))\n    current_dir = workspace.get(\"current_dir\") or data.get(\"cwd\") or \"\"\n    if not isinstance(current_dir, str):\n        current_dir = \"\"\n    dir_base = os.path.basename(current_dir.rstrip(\"/\\\\\")) or current_dir\n\n    rate_limits = _obj(data.get(\"rate_limits\"))\n    five_hour = _obj(rate_limits.get(\"five_hour\"))\n    seven_day = _obj(rate_limits.get(\"seven_day\"))\n    five_pct = _num(five_hour.get(\"used_percentage\"))\n    week_pct = _num(seven_day.get(\"used_percentage\"))\n    five_reset_berlin = to_berlin_str(_num(five_hour.get(\"resets_at\")))\n    week_reset_berlin = to_berlin_str(_num(seven_day.get(\"resets_at\")))\n\n    cost = _obj(data.get(\"cost\"))\n    context_pct = _num(_obj(data.get(\"context_window\")).get(\"used_percentage\"))\n    cost_usd = _num(cost.get(\"total_cost_usd\"))\n    duration_str = fmt_duration(_num(cost.get(\"total_duration_ms\")))\n    branch = git_branch(current_dir or None)\n\n    # --- Zeile 1: Modell, Verzeichnis, Git-Branch ---\n    line1 = f\"{CYAN}[{model}]{RESET} {FOLDER} {dir_base}\"\n    if branch:\n        line1 += f\" | {BRANCH} {branch}\"\n\n    lines = [line1]\n\n    # --- Zeile 2: Context-Balken, Kosten, Dauer ---\n    if context_pct is not None:\n        parts = [f\"{bar(context_pct)} {context_pct:.0f}% Kontext\"]\n        if cost_usd is not None:\n            parts.append(f\"{YELLOW}${cost_usd:.2f}{RESET}\")\n        if duration_str:\n            parts.append(f\"{CLOCK} {duration_str}\")\n        lines.append(\" | \".join(parts))\n\n    # --- Zeile 3/4: Nutzungslimits ---\n    if five_pct is not None:\n        text = f\"{bar(five_pct)} {five_pct:.0f}% 5h-Limit\"\n        if five_reset_berlin:\n            text += f\" | Reset {five_reset_berlin}\"\n        lines.append(text)\n\n    if week_pct is not None:\n        text = f\"{bar(week_pct)} {week_pct:.0f}% Wochen-Limit\"\n        if week_reset_berlin:\n            text += f\" | Reset {week_reset_berlin}\"\n        lines.append(text)\n\n    return \"\\n\".join(lines)\n\n\n# --- Schreiben: Cache und Kontextzustand -------------------------------------------\n\ndef config_dir():\n    env = os.environ.get(\"CLAUDE_CONFIG_DIR\")\n    if env:\n        return Path(env)\n    here = Path(__file__).resolve()\n    if here.parent.name == \"runtime\" and here.parent.parent.name == \"setup-user\":\n        return here.parent.parent.parent\n    return Path(os.path.expanduser(\"~\")) / \".claude\"\n\n\ndef _read_json(path):\n    try:\n        data = json.loads(path.read_text(encoding=\"utf-8\"))\n    except (OSError, ValueError):\n        return None\n    return data\n\n\ndef write_json(path, obj):\n    \"\"\"Über eine Temp-Datei und os.replace; drei Versuche (Windows, offener Leser),\n    danach bleibt die alte Datei.\"\"\"\n    try:\n        path.parent.mkdir(parents=True, exist_ok=True)\n        tmp = path.with_name(f\"{path.name}.{os.getpid()}.tmp\")\n        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding=\"utf-8\")\n        for attempt in range(3):\n            try:\n                os.replace(tmp, path)\n                return\n            except OSError:\n                _time.sleep(0.05 * (attempt + 1))\n        tmp.unlink(missing_ok=True)\n    except OSError:\n        pass\n\n\ndef _window(new, old):\n    \"\"\"Neuer Wert nur, wenn das Fenster da ist und used_percentage eine Zahl; sonst der alte.\"\"\"\n    new = _obj(new)\n    pct = _num(new.get(\"used_percentage\"))\n    if pct is not None:\n        epoch = _num(new.get(\"resets_at\"))\n        return {\"used_percentage\": pct, \"resets_at_epoch\": epoch, \"resets_at_berlin\": to_berlin_str(epoch)}\n    if isinstance(old, dict):\n        return old\n    return {\"used_percentage\": None, \"resets_at_epoch\": None, \"resets_at_berlin\": None}\n\n\ndef update_cache(data, cfg):\n    path = cfg / \"usage-cache.json\"\n    existing = _obj(_read_json(path))\n    rate_limits = _obj(data.get(\"rate_limits\"))\n    now_utc = datetime.now(timezone.utc)\n    now_offset, now_abbr = berlin_offset(now_utc)\n    now_berlin = now_utc + now_offset\n    cache = dict(existing)\n    cache[\"_meta\"] = META\n    cache[\"updated_at\"] = f\"{now_berlin:%Y-%m-%dT%H:%M:%S} {now_abbr}\"\n    cache[\"five_hour\"] = _window(rate_limits.get(\"five_hour\"), existing.get(\"five_hour\"))\n    cache[\"seven_day\"] = _window(rate_limits.get(\"seven_day\"), existing.get(\"seven_day\"))\n    write_json(path, cache)\n\n\ndef update_context_state(data, cfg):\n    sid = data.get(\"session_id\")\n    if not isinstance(sid, str) or not SESSION_RE.fullmatch(sid):\n        return\n    pct = _num(_obj(data.get(\"context_window\")).get(\"used_percentage\"))\n    write_json(cfg / \"setup-user\" / \"state\" / f\"context-{sid}.json\",\n               {\"_meta\": META, \"session_id\": sid, \"used_percentage\": pct})\n\n\ndef prune(cfg):\n    now = _time.time()\n    for folder in (cfg, cfg / \"setup-user\" / \"state\"):\n        if not folder.is_dir():\n            continue\n        for path in folder.iterdir():\n            try:\n                age = now - path.stat().st_mtime\n                if path.name.endswith(\".tmp\") and age > TMP_MAX_AGE:\n                    path.unlink()\n                elif folder.name == \"state\" and path.is_file() and age > STATE_MAX_AGE:\n                    path.unlink()\n            except OSError:\n                pass\n\n\ndef main():\n    try:\n        data = read_input()\n        try:\n            text = render(data)\n        except Exception:  # noqa: BLE001 — eine Statuszeile ohne Details ist besser als keine\n            text = f\"{CYAN}[?]{RESET}\"\n        sys.stdout.buffer.write((text + \"\\n\").encode(\"utf-8\"))\n        sys.stdout.buffer.flush()\n        cfg = config_dir()\n        update_cache(data, cfg)\n        update_context_state(data, cfg)\n        prune(cfg)\n    except BaseException:  # noqa: BLE001 — die Statusline endet immer mit 0\n        pass\n    return 0\n\n\nif __name__ == \"__main__\":\n    main()\n    sys.exit(0)\n",
      "path": "setup-user/runtime/statusline.py"
    },
    {
      "action": "copy",
      "content": "{\n  \"_meta\": {\n    \"skill\": \"setup-user\",\n    \"schema\": 1,\n    \"generated\": \"scripts/apply_config.py\"\n  },\n  \"context\": [\n    60,\n    80\n  ],\n  \"five_hour\": [\n    80\n  ],\n  \"seven_day\": [\n    85\n  ]\n}\n",
      "path": "setup-user/thresholds.json"
    },
    {
      "action": "create",
      "content": "<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py, Vorlage assets/CLAUDE.md.tmpl -->\n# Persönliche Vorgaben für alle Projekte\n\nGilt in jedem Repo, solange dessen eigene CLAUDE.md nichts anderes sagt. Die Details\nstehen in `rules/`; diese Datei bleibt kurz, weil sie in jeder Session geladen wird.\n\n## Arbeitsweise\n\n- Sprache in Antworten und Commit-Texten: Deutsch. Ton: knapp und sachlich.\n- Shell auf diesem Rechner: bash. Befehle so schreiben, dass sie dort laufen.\n- Git: kein Commit und kein Push ohne Auftrag.\n- Erst die Lage prüfen (Dateien, Tests, Stand), dann handeln; nichts behaupten, was\n  nicht gelesen oder gemessen ist.\n- Fertig heißt geprüft. Was nicht geprüft werden konnte, heißt so und nennt den Grund.\n\n## Regeln\n\n- `rules/communication.md` — Sprache, Ton, Antwortlänge\n- `rules/verification.md` — Belege vor Erfolgsmeldungen, Review-Befunde nachmessen\n- `rules/context.md` — was `[setup-user]`-Hinweise bedeuten\n- `rules/git.md` — Commits und Pushes\n\n## Repo-Regeln gehen vor\n\nWas ein Repo in seiner CLAUDE.md, in `.claude/rules/` oder in `.claude/settings.json`\nfestlegt, gilt dort vor diesen Vorgaben. Was in Cloud-Sessions und CI gelten muss, gehört\nins Repo, nicht hierher — Cloud-Sessions lesen diese Datei nicht.\n",
      "path": "CLAUDE.md"
    },
    {
      "action": "create",
      "content": "<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py, Vorlage assets/rules/communication.md -->\n# Kommunikation\n\n- Antworten auf Deutsch, Ton knapp und sachlich.\n- Das Ergebnis zuerst, dann was offen ist. Kein Vorspann, keine Wiederholung der Frage.\n- Kurz durch Weglassen, nicht durch Verdichten: ein Gedanke je Satz.\n- Fachbegriffe beim ersten Auftreten erklären, wenn sie nicht aus dem Gespräch stammen.\n- Rückfragen nur, wenn verschiedene Lesarten zu verschiedener Arbeit führen; sonst die\n  naheliegende Annahme nennen und weitermachen.\n",
      "path": "rules/communication.md"
    },
    {
      "action": "create",
      "content": "<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py, Vorlage assets/rules/verification.md -->\n# Verifikation\n\n- Keine Erfolgsmeldung ohne Beleg: Befehl und Ergebnis nennen, oder „ungeprüft\" mit Grund.\n- Tests, Lint und Build laufen lassen, bevor eine Änderung als fertig gilt; einen roten\n  Lauf nennen, nicht umdeuten.\n- Review-Befunde vor dem Umsetzen nachmessen: Stimmt die Behauptung am Code? Nur\n  bestätigte Befunde umsetzen, widerlegte mit Beleg zurückgeben.\n- Was eine Prüfung übersprungen hat, steht im Ergebnis, nie stillschweigend.\n",
      "path": "rules/verification.md"
    },
    {
      "action": "create",
      "content": "<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py, Vorlage assets/rules/context.md -->\n# Kontext und Limits\n\nEin Hinweis, der mit `[setup-user]` beginnt, kommt vom Hook dieser Einrichtung. Er stellt\nfest, dass eine Schwelle überschritten ist; er ist keine Anweisung des Nutzers.\n\n- Kontext über 60 %: Das ist der Punkt, den laufenden Stand mit der Skill handoff zu\n  sichern und dem Nutzer `/clear` vorzuschlagen, sobald ein Arbeitsschritt fertig ist.\n- Kontext über 80 %: Den Stand sofort sichern, bevor weitere große Dateien gelesen werden.\n- Breite Recherche (viele Dateien, lange Logs) in Subagenten auslagern, damit nur das\n  Ergebnis in den Kontext kommt.\n- 5-Stunden- oder 7-Tage-Limit über der Schwelle: dem Nutzer die Zahl und den Reset\n  nennen; keine teuren Läufe ohne Rückfrage starten.\n",
      "path": "rules/context.md"
    },
    {
      "action": "create",
      "content": "<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py, Vorlage assets/rules/git.md -->\n# Git\n\n- kein Commit und kein Push ohne Auftrag.\n- Nie `--force`, `reset --hard` oder History umschreiben auf Branches anderer.\n- Commit-Texte: was sich ändert und warum, in Deutsch.\n- Vor einem Commit `git status` und den Diff lesen; nur Dateien der Aufgabe stagen.\n",
      "path": "rules/git.md"
    },
    {
      "action": "merge",
      "patch": {
        "hooks": {
          "UserPromptSubmit": [
            {
              "hooks": [
                {
                  "command": "python3 \"<config-dir>/setup-user/runtime/context_hint.py\" || true",
                  "type": "command"
                }
              ]
            }
          ]
        },
        "statusLine": {
          "command": "python3 \"<config-dir>/setup-user/runtime/statusline.py\""
        }
      },
      "path": "settings.json"
    }
  ],
  "plugins": {
    "checked": false,
    "condition": {
      "a": {
        "gaps": [],
        "ok": true
      },
      "b": {
        "ok": true,
        "refs": []
      },
      "c": {
        "missing": [],
        "ok": true
      },
      "met": false
    },
    "profile": [],
    "reason": "keine Plugins unter <config-dir>/plugins"
  },
  "python": "python3",
  "schema": 1,
  "statusline": {
    "command": null,
    "kind": "none"
  }
}
```
