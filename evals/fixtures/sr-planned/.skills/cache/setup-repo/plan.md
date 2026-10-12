<!-- skill: setup-repo | schema: 1 | generated: python skills/setup-repo/scripts/plan_repo.py -->
# setup-repo — Plan

## Verifikation

Verifikation: `make check`

Quelle: Makefile: check. Vor jeder Erfolgsmeldung laufen lassen.

## Kandidaten

- `line-length = 100` · pyproject.toml [tool.ruff] · Werkzeug — geprüft von ruff

## Budget

Immer geladen nach apply: 20 von 150 Zeilen (CLAUDE.md samt Importen, Rules ohne `paths`).

## Plugins je Repo

ungeprüft — Plugin-ID nicht gefunden; `apply` schreibt keine `enabledPlugins`.

## Hooks (abwählbar)

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
    ".claude/settings.json": null,
    ".gitignore": null,
    "CLAUDE.md": null
  },
  "budget": {
    "limit": 150,
    "lines": 20
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
  "hash": "2a98038d69f4ad2af058e6d3afa235c0a22fc0e4c64cb9662daa4f455c4411a8",
  "operations": [
    {
      "action": "create",
      "content": "<!-- skill: setup-repo | schema: 1 | generated: python skills/setup-repo/scripts/plan_repo.py -->\n# Arbeitsweise in diesem Repo\n\nVerifikation: `make check`\n\nQuelle: Makefile: check. Vor jeder Erfolgsmeldung laufen lassen.\n\n## Fertig heißt geprüft\n\n- Vor jeder Erfolgsmeldung läuft die Verifikation; das Ergebnis steht in der Antwort.\n- Ist sie rot, wird der Fehler behoben oder offen benannt, nie übergangen.\n- Fehlt ein Befehl, heißt das Ergebnis „ungeprüft\", nicht „fertig\".\n\n## Konventionen\n\nKeine geernteten Regeln ohne Geltungsbereich.\n\nRegeln, die nur für einen Teil des Repos gelten, liegen unter `.claude/rules/`; Claude\nCode lädt sie nur bei passenden Dateien. Was ein konfigurierter Linter, Formatter oder\nTypprüfer schon prüft, steht hier nicht.\n",
      "path": "CLAUDE.md"
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
    "verify_hook": false
  },
  "plugins": {},
  "schema": 1,
  "verification": {
    "command": "make check",
    "derived": false,
    "source": "Makefile: check"
  }
}
```
