<!-- skill: setup-user | schema: 1 | generated: python inspect_config.py --config-dir /home/user/cc-skills/evals/fixtures/su-own-statusline/cfg -->

# setup-user — Plan

Ziel: `/home/user/cc-skills/evals/fixtures/su-own-statusline/cfg` · Hash `31cb07feb9a5fb0c` · Interpreter `python3`

## Statusline

Fremde Statusline (`python3 cfg/my-status.py`) bleibt eingetragen. Kontext-Hinweise nicht verfügbar — fremde Statusline schreibt keinen Kontextzustand. Der Hook wird trotzdem eingetragen und schweigt, bis die Asset-Statusline läuft.

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
    "settings.json": "abbd81d89cf615968048a0a385fdca5d44ee413e4ff2e0ba35011122baf0a11e",
    "setup-user/runtime/context_hint.py": null,
    "setup-user/thresholds.json": null
  },
  "hash": "31cb07feb9a5fb0ce3067f63cd8b20252ad1f1ccb8ec60720a33acac8706c987",
  "operations": [
    {
      "action": "copy",
      "content": "#!/usr/bin/env python3\n# setup-user: context_hint\n\"\"\"UserPromptSubmit-Hook: meldet Claude das Überschreiten einer Kontext- oder Limitschwelle.\n\nTier 1: nur Stdlib. Liest den Kontextzustand, den die Statusline je Session schreibt,\nund den Limit-Cache des Accounts; Format und Regeln stehen in\nskills/setup-user/references/thresholds.md. Der Hook hält nie etwas an: Jede Ausnahme\nwird gefangen, es gibt kein argparse, und er endet immer mit Exit 0. Beim Schweigen\nbleibt stdout leer; sonst steht dort genau ein JSON-Objekt mit\nhookSpecificOutput.hookEventName und additionalContext.\n\"\"\"\n\nimport json\nimport os\nimport re\nimport sys\nimport time\nfrom pathlib import Path\n\nDEFAULT_THRESHOLDS = {\"context\": [60, 80], \"five_hour\": [80], \"seven_day\": [85]}\nLIMIT_LABELS = {\"five_hour\": \"5-Stunden-Limit\", \"seven_day\": \"7-Tage-Limit\"}\nSESSION_RE = re.compile(r\"[A-Za-z0-9_-]+\")\nMETA = {\"skill\": \"setup-user\", \"schema\": 1, \"generated\": \"assets/runtime/context_hint.py\"}\n\n\ndef _config_dir() -> Path:\n    env = os.environ.get(\"CLAUDE_CONFIG_DIR\")\n    if env:\n        return Path(env)\n    here = Path(__file__).resolve()\n    if here.parent.name == \"runtime\" and here.parent.parent.name == \"setup-user\":\n        return here.parent.parent.parent\n    return Path.home() / \".claude\"\n\n\ndef _read_json(path: Path):\n    try:\n        return json.loads(path.read_text(encoding=\"utf-8\"))\n    except (OSError, ValueError):\n        return None\n\n\ndef _write_json(path: Path, obj) -> None:\n    \"\"\"Atomar über eine Temp-Datei; scheitert os.replace (Windows, offener Leser), drei\n    Versuche, danach bleibt die alte Datei.\"\"\"\n    try:\n        path.parent.mkdir(parents=True, exist_ok=True)\n        tmp = path.with_name(f\"{path.name}.{os.getpid()}.tmp\")\n        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + \"\\n\", encoding=\"utf-8\")\n        for attempt in range(3):\n            try:\n                os.replace(tmp, path)\n                return\n            except OSError:\n                time.sleep(0.05 * (attempt + 1))\n        tmp.unlink(missing_ok=True)\n    except OSError:\n        pass\n\n\ndef _touch(path: Path) -> None:\n    try:\n        if path.exists():\n            os.utime(path)\n    except OSError:\n        pass\n\n\ndef _thresholds(config_dir: Path) -> dict:\n    data = _read_json(config_dir / \"setup-user\" / \"thresholds.json\")\n    result = {}\n    for kind, default in DEFAULT_THRESHOLDS.items():\n        values = data.get(kind) if isinstance(data, dict) else None\n        ok = isinstance(values, list) and values and all(isinstance(v, (int, float)) for v in values)\n        result[kind] = sorted(values) if ok else default\n    return result\n\n\ndef _number(value) -> bool:\n    return isinstance(value, (int, float)) and not isinstance(value, bool)\n\n\ndef _context_part(payload: dict, state_dir: Path, thresholds: list) -> str | None:\n    sid = payload.get(\"session_id\")\n    if not isinstance(sid, str) or not SESSION_RE.fullmatch(sid):\n        return None\n    state = _read_json(state_dir / f\"context-{sid}.json\")\n    hints_path = state_dir / f\"hints-{sid}.json\"\n    if not isinstance(state, dict) or state.get(\"session_id\") != sid or not _number(state.get(\"used_percentage\")):\n        _touch(hints_path)\n        return None\n    pct = state[\"used_percentage\"]\n    stored = _read_json(hints_path)\n    reported = stored.get(\"reported\", {}) if isinstance(stored, dict) else {}\n    if not isinstance(reported, dict):\n        reported = {}\n    updated, crossed = {}, []\n    for threshold in thresholds:\n        key = str(threshold)\n        if pct >= threshold:\n            if not reported.get(key):\n                crossed.append(threshold)\n            updated[key] = True\n        else:\n            updated[key] = False\n    if updated != reported or not isinstance(stored, dict):\n        _write_json(hints_path, {\"_meta\": META, \"session_id\": sid, \"reported\": updated})\n    else:\n        _touch(hints_path)\n    if not crossed:\n        return None\n    return (f\"Kontext {round(pct)} % (Schwelle {max(crossed)} %). \"\n            \"Laut Nutzerregel context.md ist das der Punkt für Handoff und /clear.\")\n\n\ndef _limit_parts(config_dir: Path, state_dir: Path, thresholds: dict, now: float) -> list[str]:\n    cache = _read_json(config_dir / \"usage-cache.json\")\n    path = state_dir / \"limit-hints.json\"\n    stored = _read_json(path)\n    reported = set(stored.get(\"reported\", [])) if isinstance(stored, dict) and isinstance(stored.get(\"reported\"), list) else set()\n    parts, changed = [], False\n    for window, label in LIMIT_LABELS.items():\n        entry = cache.get(window) if isinstance(cache, dict) else None\n        if not isinstance(entry, dict):\n            continue\n        pct, reset = entry.get(\"used_percentage\"), entry.get(\"resets_at_epoch\")\n        if not _number(pct) or not _number(reset) or reset <= now:\n            continue\n        crossed = []\n        for threshold in thresholds[window]:\n            key = f\"{window}:{threshold}:{int(reset)}\"\n            if pct >= threshold and key not in reported:\n                crossed.append(threshold)\n                reported.add(key)\n                changed = True\n        if crossed:\n            when = time.strftime(\"%H:%M\", time.gmtime(reset))\n            parts.append(f\"{label} {round(pct)} % (Schwelle {max(crossed)} %), Reset {when} UTC.\")\n    alive = {k for k in reported if k.rsplit(\":\", 1)[-1].isdigit() and int(k.rsplit(\":\", 1)[-1]) > now}\n    if changed or alive != reported:\n        _write_json(path, {\"_meta\": META, \"reported\": sorted(alive)})\n    else:\n        _touch(path)\n    return parts\n\n\ndef hint_for(payload, config_dir, now):\n    \"\"\"Hinweistext ohne Ausgabeform, oder None. Liest und schreibt nur die Merker unter\n    <config_dir>/setup-user/state/.\"\"\"\n    if not isinstance(payload, dict):\n        return None\n    config_dir = Path(config_dir)\n    state_dir = config_dir / \"setup-user\" / \"state\"\n    thresholds = _thresholds(config_dir)\n    parts = []\n    context = _context_part(payload, state_dir, thresholds[\"context\"])\n    if context:\n        parts.append(context)\n    parts.extend(_limit_parts(config_dir, state_dir, thresholds, now))\n    return \"[setup-user] \" + \" \".join(parts) if parts else None\n\n\ndef main():\n    try:\n        raw = sys.stdin.buffer.read().decode(\"utf-8\", errors=\"replace\")\n        payload = json.loads(raw) if raw.strip() else {}\n        text = hint_for(payload, _config_dir(), time.time())\n        if text:\n            out = {\"hookSpecificOutput\": {\"hookEventName\": \"UserPromptSubmit\", \"additionalContext\": text}}\n            sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode(\"utf-8\"))\n            sys.stdout.buffer.flush()\n    except BaseException:  # noqa: BLE001 — ein Hook-Fehler darf nie einen Prompt anhalten\n        pass\n    return 0\n\n\nif __name__ == \"__main__\":\n    main()\n    sys.exit(0)\n",
      "path": "setup-user/runtime/context_hint.py"
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
    "command": "python3 cfg/my-status.py",
    "kind": "foreign"
  }
}
```
