<!-- skill: setup-repo | schema: 1 | generated: python skills/setup-repo/scripts/plan_repo.py -->
# setup-repo — Plan

## Verifikation

Verifikation: `make check`

Quelle: Makefile: check. Vor jeder Erfolgsmeldung laufen lassen.

## Kandidaten

- `line-length = 100` · pyproject.toml [tool.ruff] · Werkzeug — geprüft von ruff

## Budget

Immer geladen nach apply: 44 von 150 Zeilen (CLAUDE.md samt Importen, Rules ohne `paths`).

## Plugins je Repo

ungeprüft — Plugin-ID nicht gefunden; `apply` schreibt keine `enabledPlugins`.

## Hooks (abwählbar)

- Bereichs-Hook (`UserPromptSubmit`, `Stop`): **an** — meldet Dateien außerhalb der Bereiche aktiver Ziele in `docs/goals.md`, hält nie etwas an. Abwählen: neu planen mit `--without-goal-hook`.
- Verifikations-Hook (`Stop`): aus — zuschalten mit `--with-verify-hook`.
- `permissions.deny` für `.env` und Schlüsseldateien: aus — zuschalten mit `--deny-secrets`.
  Ein Read-Deny gilt für die Datei-Werkzeuge und erkannte Bash-Dateikommandos, nicht für beliebige Unterprozesse.

## Änderungen

### `CLAUDE.md` (create)

```diff
+<!-- skill: setup-repo | schema: 1 | generated: python skills/setup-repo/scripts/plan_repo.py -->
+# Arbeitsweise in diesem Repo
+
+Verifikation: `make check`
+
+Quelle: Makefile: check. Vor jeder Erfolgsmeldung laufen lassen.
+
+## Fertig heißt geprüft
+
+- Vor jeder Erfolgsmeldung läuft die Verifikation; das Ergebnis steht in der Antwort.
+- Ist sie rot, wird der Fehler behoben oder offen benannt, nie übergangen.
+- Fehlt ein Befehl, heißt das Ergebnis „ungeprüft", nicht „fertig".
+
+## Konventionen
+
+Keine geernteten Regeln ohne Geltungsbereich.
+
+Regeln, die nur für einen Teil des Repos gelten, liegen unter `.claude/rules/`; Claude
+Code lädt sie nur bei passenden Dateien. Was ein konfigurierter Linter, Formatter oder
+Typprüfer schon prüft, steht hier nicht.
```

### `docs/goals.md` (create)

```diff
+<!-- skill: setup-repo | schema: 1 | generated: python skills/setup-repo/scripts/plan_repo.py -->
+# Ziele
+
+Zielstand über Sitzungen hinweg. Gepflegt von Menschen und von Claude nach
+`.claude/rules/goals.md`; Schema und Glob-Dialekt der Bereiche stehen in der Reference
+`goals.md` von setup-repo. IDs heißen `G<n>`, fortlaufend über alle drei Tabellen.
+
+## Aktiv
+
+| id | Ziel | Fertig wenn | Bereich | seit |
+| --- | --- | --- | --- | --- |
+
+## Kandidaten
+
+| id | Kandidat | entdeckt bei | Grund | am |
+| --- | --- | --- | --- | --- |
+
+## Erledigt
+
+| id | Ziel | Beleg | am |
+| --- | --- | --- | --- |
```

### `.claude/rules/goals.md` (create)

```diff
+<!-- skill: setup-repo | schema: 1 | generated: python skills/setup-repo/scripts/plan_repo.py -->
+# Ziele und entdeckte Arbeit
+
+Gilt nur, solange `docs/goals.md` unter *Aktiv* mindestens ein Ziel hat; sonst nichts tun.
+Kopfzeile von `docs/goals.md` zuerst prüfen; vor jedem Schreiben die Datei neu lesen.
+
+Jede während der Arbeit entdeckte Aufgabe gehört in genau eine Klasse:
+
+1. **Vom Nutzer verlangt** — steht im aktuellen Prompt: erledigen.
+2. **Teil des Ziels** — nötig, damit „Fertig wenn" eintritt: erledigen.
+3. **Trivial** — in einer Datei, die die Aufgabe ohnehin ändert, höchstens fünf Zeilen,
+   keine neue öffentliche Schnittstelle, kein neuer Test nötig: erledigen, im Turn-Ende nennen.
+4. **Neues Ziel** — alles andere: nicht umsetzen. Unter *Kandidaten* anhängen
+   (`G<n>`, eins über dem höchsten `n` aller Tabellen), im Turn-Ende nennen.
+   Eintragen ist kein Umsetzen: ohne Rückfrage, und `docs/goals.md` liegt nie außerhalb
+   eines Bereichs.
+
+Unter *Aktiv* trägt Claude nur ein, was der Nutzer ausdrücklich ein Ziel nennt, mit
+prüfbarem „Fertig wenn", und schlägt die passende `/goal`-Zeile vor. Nach *Erledigt*
+wandert ein Ziel nur mit Beleg (Befehl und Ergebnis).
+
+Eine Meldung `[setup-repo] Geändert außerhalb des Bereichs …` heißt: Diese Dateien liegen
+außerhalb der Bereiche aktiver Ziele. Ordne sie einer der vier Klassen zu und sag welcher.
+Einen Merge-Konflikt in `docs/goals.md` nicht selbst lösen — fragen.
```

### `.claude/hooks/goal_scope.py` (copy)

Kopie von `assets/runtime/goal_scope.py` (343 Zeilen).

### `.gitignore` (gitignore)

```diff
+.skills/cache/
+.claude/settings.local.json
```
(nur fehlende Zeilen werden angehängt)

### `.claude/settings.json` (merge-json)

Gemischt wird:

```json
{
  "permissions": {
    "allow": [
      "Bash(make check)",
      "Bash(make lint)",
      "Bash(make test)"
    ]
  },
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "command -v python3 >/dev/null 2>&1 && exec python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/goal_scope.py\" || exec python \"$CLAUDE_PROJECT_DIR/.claude/hooks/goal_scope.py\"",
            "timeout": 30
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "command -v python3 >/dev/null 2>&1 && exec python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/goal_scope.py\" || exec python \"$CLAUDE_PROJECT_DIR/.claude/hooks/goal_scope.py\"",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

## Hinweise

- `.skills/cache/` ist bis `apply` im Repo unversioniert sichtbar; `apply` ergänzt `.gitignore`.
- `apply` läuft erst nach Bestätigung, in einem eigenen Aufruf, und committet nie.

## Block für apply

```json setup-repo-plan
{
  "base": {
    ".claude/hooks/goal_scope.py": null,
    ".claude/rules/goals.md": null,
    ".claude/settings.json": null,
    ".gitignore": null,
    "CLAUDE.md": null,
    "docs/goals.md": null
  },
  "budget": {
    "limit": 150,
    "lines": 44
  },
  "candidates": [
    {
      "checked_by": "ruff",
      "class": "werkzeug",
      "id": "c1",
      "paths": [],
      "source": "pyproject.toml [tool.ruff]",
      "text": "`line-length = 100`"
    }
  ],
  "hash": "2a082b697115989aa3625664cda07354ebca7d266c780cbbb09c1dc96dbd65c7",
  "operations": [
    {
      "action": "create",
      "content": "<!-- skill: setup-repo | schema: 1 | generated: python skills/setup-repo/scripts/plan_repo.py -->\n# Arbeitsweise in diesem Repo\n\nVerifikation: `make check`\n\nQuelle: Makefile: check. Vor jeder Erfolgsmeldung laufen lassen.\n\n## Fertig heißt geprüft\n\n- Vor jeder Erfolgsmeldung läuft die Verifikation; das Ergebnis steht in der Antwort.\n- Ist sie rot, wird der Fehler behoben oder offen benannt, nie übergangen.\n- Fehlt ein Befehl, heißt das Ergebnis „ungeprüft\", nicht „fertig\".\n\n## Konventionen\n\nKeine geernteten Regeln ohne Geltungsbereich.\n\nRegeln, die nur für einen Teil des Repos gelten, liegen unter `.claude/rules/`; Claude\nCode lädt sie nur bei passenden Dateien. Was ein konfigurierter Linter, Formatter oder\nTypprüfer schon prüft, steht hier nicht.\n",
      "path": "CLAUDE.md"
    },
    {
      "action": "create",
      "content": "<!-- skill: setup-repo | schema: 1 | generated: python skills/setup-repo/scripts/plan_repo.py -->\n# Ziele\n\nZielstand über Sitzungen hinweg. Gepflegt von Menschen und von Claude nach\n`.claude/rules/goals.md`; Schema und Glob-Dialekt der Bereiche stehen in der Reference\n`goals.md` von setup-repo. IDs heißen `G<n>`, fortlaufend über alle drei Tabellen.\n\n## Aktiv\n\n| id | Ziel | Fertig wenn | Bereich | seit |\n| --- | --- | --- | --- | --- |\n\n## Kandidaten\n\n| id | Kandidat | entdeckt bei | Grund | am |\n| --- | --- | --- | --- | --- |\n\n## Erledigt\n\n| id | Ziel | Beleg | am |\n| --- | --- | --- | --- |\n",
      "path": "docs/goals.md"
    },
    {
      "action": "create",
      "content": "<!-- skill: setup-repo | schema: 1 | generated: python skills/setup-repo/scripts/plan_repo.py -->\n# Ziele und entdeckte Arbeit\n\nGilt nur, solange `docs/goals.md` unter *Aktiv* mindestens ein Ziel hat; sonst nichts tun.\nKopfzeile von `docs/goals.md` zuerst prüfen; vor jedem Schreiben die Datei neu lesen.\n\nJede während der Arbeit entdeckte Aufgabe gehört in genau eine Klasse:\n\n1. **Vom Nutzer verlangt** — steht im aktuellen Prompt: erledigen.\n2. **Teil des Ziels** — nötig, damit „Fertig wenn\" eintritt: erledigen.\n3. **Trivial** — in einer Datei, die die Aufgabe ohnehin ändert, höchstens fünf Zeilen,\n   keine neue öffentliche Schnittstelle, kein neuer Test nötig: erledigen, im Turn-Ende nennen.\n4. **Neues Ziel** — alles andere: nicht umsetzen. Unter *Kandidaten* anhängen\n   (`G<n>`, eins über dem höchsten `n` aller Tabellen), im Turn-Ende nennen.\n   Eintragen ist kein Umsetzen: ohne Rückfrage, und `docs/goals.md` liegt nie außerhalb\n   eines Bereichs.\n\nUnter *Aktiv* trägt Claude nur ein, was der Nutzer ausdrücklich ein Ziel nennt, mit\nprüfbarem „Fertig wenn\", und schlägt die passende `/goal`-Zeile vor. Nach *Erledigt*\nwandert ein Ziel nur mit Beleg (Befehl und Ergebnis).\n\nEine Meldung `[setup-repo] Geändert außerhalb des Bereichs …` heißt: Diese Dateien liegen\naußerhalb der Bereiche aktiver Ziele. Ordne sie einer der vier Klassen zu und sag welcher.\nEinen Merge-Konflikt in `docs/goals.md` nicht selbst lösen — fragen.\n",
      "path": ".claude/rules/goals.md"
    },
    {
      "action": "copy",
      "content": "#!/usr/bin/env python3\n\"\"\"Bereichs-Hook von setup-repo (Spec 22, Abschnitt C). Tier 1, nur Stdlib.\n\nLäuft an zwei Ereignissen, erkannt an `hook_event_name` der Payload auf stdin:\n\n- `UserPromptSubmit`: hält die Basis des Turns fest — HEAD und für jede geänderte oder\n  unversionierte Datei einen Inhalts-Hash — und gibt eine offene Meldung aus dem letzten\n  Turn als `hookSpecificOutput.additionalContext` aus.\n- `Stop`: bestimmt die Dateien, die sich im Turn geändert haben (Commits des Turns zählen\n  mit, vorher Uncommittetes nur, wenn es sich weiter ändert). Liegt eine außerhalb der\n  Bereiche aller aktiven Ziele in `docs/goals.md` und wurde sie in der Session noch nicht\n  gemeldet, gibt er `systemMessage` aus und merkt die Meldung für den nächsten Prompt.\n\nEr hält nie etwas an: kein `decision`, kein Exit 2, kein Folgeturn; Exit immer 0.\nSchweigt ohne Repo-Commit, ohne Ledger, ohne aktives Ziel mit Bereich. Eine fehlende oder\nunbekannte Ledger-Kopfzeile und ein gescheiterter git-Aufruf werden einmal je Session per\n`systemMessage` gemeldet. Pfade relativ zur Repo-Wurzel, git immer mit `-z`. Zustand:\n`$SETUP_REPO_GOAL_STATE`, sonst `.skills/cache/setup-repo/goal-scope.json`, mit `_meta`,\natomar geschrieben; unlesbar heißt Neustart; Einträge älter als sieben Tage fallen weg.\nLedger, Glob-Dialekt und Ausnahmen: references/goals.md.\n\"\"\"\nimport hashlib\nimport json\nimport os\nimport re\nimport subprocess\nimport sys\nimport time\nfrom pathlib import Path\n\nMETA = {\"skill\": \"setup-repo\", \"schema\": 1, \"generated\": \"assets/runtime/goal_scope.py\"}\nPREFIX = \"[setup-repo]\"\nMAX_AGE = 7 * 24 * 3600\nMAX_LISTED = 10\nHEADER_RE = re.compile(r\"^<!--\\s*skill:\\s*setup-repo\\s*\\|\\s*schema:\\s*1\\s*\\|\")\nGOAL_ID_RE = re.compile(r\"^G\\d+$\")\nEXCLUDED_FILES = {\"docs/goals.md\", \"handoff.md\", \"docs/decisions.md\", \"CLAUDE.md\", \".gitignore\"}\nEXCLUDED_DIRS = (\"docs/debugging/\", \"docs/specs/wip/\", \".claude/\", \".skills/\")\n\n\nclass GitError(Exception):\n    pass\n\n\n# --- Globs -------------------------------------------------------------------------\n\ndef _segment_regex(segment):\n    out = []\n    for ch in segment:\n        if ch == \"*\":\n            out.append(\"[^/]*\")\n        elif ch == \"?\":\n            out.append(\"[^/]\")\n        else:\n            out.append(re.escape(ch))\n    return \"\".join(out)\n\n\ndef glob_match(pattern, path):\n    \"\"\"`**` beliebig viele Ordner, `*` und `?` innerhalb eines Pfadteils, `/` als Trenner,\n    Groß- und Kleinschreibung zählen, keine Klammern; `src/` gilt als `src/**`.\"\"\"\n    pattern = pattern.strip()\n    if not pattern:\n        return False\n    if pattern.endswith(\"/\"):\n        pattern += \"**\"\n    parts = pattern.split(\"/\")\n    regex = \"\"\n    for i, part in enumerate(parts):\n        last = i == len(parts) - 1\n        if part == \"**\":\n            regex += \".*\" if last else \"(?:[^/]+/)*\"\n        else:\n            regex += _segment_regex(part) + (\"\" if last else \"/\")\n    return re.fullmatch(regex, path) is not None\n\n\n# --- git ---------------------------------------------------------------------------\n\ndef _git(cwd, *args):\n    try:\n        proc = subprocess.run([\"git\", *args], cwd=str(cwd), capture_output=True, timeout=30)\n    except FileNotFoundError as exc:\n        raise GitError(\"git nicht gefunden\") from exc\n    except (OSError, subprocess.SubprocessError) as exc:\n        raise GitError(f\"git {args[0]} gescheitert ({type(exc).__name__})\") from exc\n    if proc.returncode != 0:\n        raise GitError(f\"git {args[0]} gescheitert: {proc.stderr.decode('utf-8', 'replace').strip()[:120]}\")\n    return proc.stdout.decode(\"utf-8\", \"replace\")\n\n\ndef _toplevel(root):\n    return Path(_git(root, \"rev-parse\", \"--show-toplevel\").strip())\n\n\ndef _head(top):\n    try:\n        return _git(top, \"rev-parse\", \"--verify\", \"-q\", \"HEAD\").strip() or None\n    except GitError:\n        return None\n\n\ndef _hash(path):\n    try:\n        return hashlib.sha256(path.read_bytes()).hexdigest()\n    except OSError:\n        return None\n\n\ndef _z(text):\n    return [p for p in text.split(\"\\0\") if p]\n\n\ndef _dirty(top):\n    \"\"\"Pfade mit Änderungen gegenüber HEAD samt unversionierten, aus `git status -z`.\"\"\"\n    entries = _git(top, \"status\", \"--porcelain\", \"-z\", \"--untracked-files=all\").split(\"\\0\")\n    paths, i = [], 0\n    while i < len(entries):\n        entry = entries[i]\n        i += 1\n        if len(entry) < 4:\n            continue\n        paths.append(entry[3:])\n        if \"R\" in entry[:2] or \"C\" in entry[:2]:\n            if i < len(entries) and entries[i]:\n                paths.append(entries[i])\n            i += 1\n    return paths\n\n\n# --- Ledger ------------------------------------------------------------------------\n\ndef read_ledger(top):\n    \"\"\"(None, None) ohne Ledger; (Grund, None) bei unbekannter Kopfzeile; sonst\n    (None, [(id, [globs]), …]) der aktiven Ziele.\"\"\"\n    try:\n        text = (top / \"docs\" / \"goals.md\").read_text(encoding=\"utf-8\", errors=\"replace\")\n    except OSError:\n        return None, None\n    first = next((line.strip() for line in text.splitlines() if line.strip()), \"\")\n    if not HEADER_RE.match(first):\n        return \"Kopfzeile von docs/goals.md fehlt oder ist unbekannt — Bereichsprüfung aus\", None\n    goals, in_active = [], False\n    for line in text.splitlines():\n        if line.startswith(\"## \"):\n            in_active = line.strip() == \"## Aktiv\"\n            continue\n        if not in_active or not line.lstrip().startswith(\"|\"):\n            continue\n        cells = [c.strip() for c in line.strip().strip(\"|\").split(\"|\")]\n        if len(cells) < 4 or not GOAL_ID_RE.match(cells[0]):\n            continue\n        globs = [g.strip().strip(\"`\") for g in cells[3].split(\",\") if g.strip().strip(\"`\")]\n        goals.append((cells[0], globs))\n    return None, goals\n\n\ndef _excluded(path):\n    return path in EXCLUDED_FILES or path.startswith(EXCLUDED_DIRS)\n\n\n# --- Zustand -----------------------------------------------------------------------\n\ndef _state_path(top):\n    env = os.environ.get(\"SETUP_REPO_GOAL_STATE\")\n    return Path(env) if env else top / \".skills\" / \"cache\" / \"setup-repo\" / \"goal-scope.json\"\n\n\ndef load_state(path):\n    try:\n        data = json.loads(path.read_text(encoding=\"utf-8\"))\n    except (OSError, ValueError):\n        return {}\n    sessions = data.get(\"sessions\") if isinstance(data, dict) else None\n    return sessions if isinstance(sessions, dict) else {}\n\n\ndef save_state(path, sessions):\n    now = time.time()\n    sessions = {k: v for k, v in sessions.items()\n                if isinstance(v, dict) and now - float(v.get(\"at\", 0) or 0) <= MAX_AGE}\n    try:\n        path.parent.mkdir(parents=True, exist_ok=True)\n        tmp = path.with_name(f\"{path.name}.{os.getpid()}.tmp\")\n        tmp.write_text(json.dumps({\"_meta\": META, \"sessions\": sessions}, ensure_ascii=False, indent=2),\n                       encoding=\"utf-8\")\n        for attempt in range(3):\n            try:\n                os.replace(tmp, path)\n                return\n            except OSError:\n                time.sleep(0.05 * (attempt + 1))\n        tmp.unlink(missing_ok=True)\n    except OSError:\n        pass\n\n\ndef _session(sessions, sid):\n    entry = sessions.get(sid)\n    entry = entry if isinstance(entry, dict) else {}\n    entry.setdefault(\"reported\", [])\n    entry.setdefault(\"notified\", [])\n    entry.setdefault(\"pending\", None)\n    entry[\"at\"] = time.time()\n    sessions[sid] = entry\n    return entry\n\n\ndef _notice(text):\n    return json.dumps({\"systemMessage\": f\"{PREFIX} {text}\"}, ensure_ascii=False)\n\n\ndef _sid(payload):\n    sid = payload.get(\"session_id\") if isinstance(payload, dict) else None\n    return sid if isinstance(sid, str) and sid else \"ohne-session\"\n\n\n# --- Ereignisse --------------------------------------------------------------------\n\ndef on_prompt(payload, root):\n    \"\"\"Basis des Turns festhalten; offene Meldung als additionalContext ausgeben.\"\"\"\n    try:\n        top = _toplevel(root)\n    except GitError:\n        return \"\"\n    head = _head(top)\n    if head is None:\n        return \"\"\n    state_path = _state_path(top)\n    sessions = load_state(state_path)\n    entry = _session(sessions, _sid(payload))\n    try:\n        entry[\"base\"] = {\"head\": head, \"files\": {p: _hash(top / p) for p in _dirty(top)}}\n    except GitError:\n        entry[\"base\"] = None\n    pending, entry[\"pending\"] = entry.get(\"pending\"), None\n    save_state(state_path, sessions)\n    if not pending:\n        return \"\"\n    return json.dumps({\"hookSpecificOutput\": {\"hookEventName\": \"UserPromptSubmit\",\n                                              \"additionalContext\": pending}}, ensure_ascii=False)\n\n\ndef on_stop(payload, root):\n    \"\"\"Änderungen des Turns gegen die Bereiche aktiver Ziele; meldet, hält nie an.\"\"\"\n    sid = _sid(payload)\n    try:\n        top = _toplevel(root)\n    except GitError as exc:\n        return _once_without_repo(root, sid, str(exc))\n    if _head(top) is None:\n        return \"\"\n    problem, goals = read_ledger(top)\n    state_path = _state_path(top)\n    sessions = load_state(state_path)\n    entry = _session(sessions, sid)\n\n    def once(reason):\n        if reason in entry[\"notified\"]:\n            save_state(state_path, sessions)\n            return \"\"\n        entry[\"notified\"].append(reason)\n        save_state(state_path, sessions)\n        return _notice(reason)\n\n    if problem:\n        return once(problem)\n    scoped = [(gid, globs) for gid, globs in goals or [] if globs]\n    base = entry.get(\"base\")\n    if not scoped or not isinstance(base, dict) or not base.get(\"head\"):\n        save_state(state_path, sessions)\n        return \"\"\n    try:\n        candidates = set(_z(_git(top, \"diff\", base[\"head\"], \"--name-only\", \"-z\")))\n        candidates |= set(_z(_git(top, \"ls-files\", \"--others\", \"--exclude-standard\", \"-z\")))\n    except GitError as exc:\n        return once(str(exc))\n    before = base.get(\"files\") or {}\n    changed = set()\n    for path in candidates | set(before):\n        now = _hash(top / path)\n        if path in before:\n            if now != before[path]:\n                changed.add(path)\n        else:\n            changed.add(path)\n    outside = sorted(p for p in changed if not _excluded(p) and p not in entry[\"reported\"]\n                     and not any(glob_match(g, p) for _, globs in scoped for g in globs))\n    if not outside:\n        save_state(state_path, sessions)\n        return \"\"\n    entry[\"reported\"].extend(outside)\n    ids = \", \".join(gid for gid, _ in scoped)\n    where = f\"des Bereichs von {ids}\" if len(scoped) == 1 else f\"der Bereiche von {ids}\"\n    listed = \", \".join(outside[:MAX_LISTED]) + (f\" und {len(outside) - MAX_LISTED} weitere\"\n                                                if len(outside) > MAX_LISTED else \"\")\n    text = (f\"{PREFIX} Geändert außerhalb {where}: {listed}. Laut Zielregel: vom Nutzer verlangt, \"\n            \"Teil des Ziels, trivial oder ein Kandidat.\")\n    entry[\"pending\"] = f\"{entry['pending']}\\n{text}\" if entry.get(\"pending\") else text\n    save_state(state_path, sessions)\n    return json.dumps({\"systemMessage\": text}, ensure_ascii=False)\n\n\ndef _once_without_repo(root, sid, reason):\n    \"\"\"git fehlt oder scheitert schon an der Wurzel: einmal je Session melden. Der Zustand\n    liegt dann am Ort, den SETUP_REPO_GOAL_STATE nennt, sonst unter dem Projektordner.\"\"\"\n    path = _state_path(Path(root))\n    sessions = load_state(path)\n    entry = _session(sessions, sid)\n    if reason in entry[\"notified\"]:\n        save_state(path, sessions)\n        return \"\"\n    entry[\"notified\"].append(reason)\n    save_state(path, sessions)\n    return _notice(f\"Bereichsprüfung aus — {reason}\")\n\n\ndef main():\n    try:\n        raw = sys.stdin.buffer.read().decode(\"utf-8\", errors=\"replace\")\n        try:\n            payload = json.loads(raw) if raw.strip() else {}\n        except ValueError:\n            payload = {}\n        payload = payload if isinstance(payload, dict) else {}\n        cwd = payload.get(\"cwd\") if isinstance(payload.get(\"cwd\"), str) else None\n        root = os.environ.get(\"CLAUDE_PROJECT_DIR\") or cwd or os.getcwd()\n        event = payload.get(\"hook_event_name\")\n        out = on_prompt(payload, root) if event == \"UserPromptSubmit\" else \\\n            on_stop(payload, root) if event == \"Stop\" else \"\"\n        if out:\n            sys.stdout.buffer.write((out + \"\\n\").encode(\"utf-8\"))\n    except BaseException as exc:  # noqa: BLE001 — ein Hook endet nie mit Traceback und nie anders als 0\n        try:\n            sys.stdout.write(_notice(f\"goal_scope: interner Fehler ({type(exc).__name__})\") + \"\\n\")\n        except Exception:  # noqa: BLE001\n            pass\n    return 0\n\n\nif __name__ == \"__main__\":\n    main()\n    sys.exit(0)\n",
      "path": ".claude/hooks/goal_scope.py"
    },
    {
      "action": "gitignore",
      "lines": [
        ".skills/cache/",
        ".claude/settings.local.json"
      ],
      "path": ".gitignore"
    },
    {
      "action": "merge-json",
      "patch": {
        "hooks": {
          "Stop": [
            {
              "hooks": [
                {
                  "command": "command -v python3 >/dev/null 2>&1 && exec python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/goal_scope.py\" || exec python \"$CLAUDE_PROJECT_DIR/.claude/hooks/goal_scope.py\"",
                  "timeout": 30,
                  "type": "command"
                }
              ]
            }
          ],
          "UserPromptSubmit": [
            {
              "hooks": [
                {
                  "command": "command -v python3 >/dev/null 2>&1 && exec python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/goal_scope.py\" || exec python \"$CLAUDE_PROJECT_DIR/.claude/hooks/goal_scope.py\"",
                  "timeout": 30,
                  "type": "command"
                }
              ]
            }
          ]
        },
        "permissions": {
          "allow": [
            "Bash(make check)",
            "Bash(make lint)",
            "Bash(make test)"
          ]
        }
      },
      "path": ".claude/settings.json"
    }
  ],
  "options": {
    "deny_secrets": false,
    "goal_hook": true,
    "verify_hook": false
  },
  "plugins": {},
  "schema": 1,
  "verification": {
    "command": "make deploy",
    "derived": false,
    "source": "Makefile: check"
  }
}
```
