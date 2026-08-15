"""Einen frischen Agenten im Workspace starten und sein Transcript einsammeln."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT = 600


@dataclass(frozen=True)
class Transcript:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


def run_agent(
    prompt: str,
    cwd: Path,
    *,
    cli: str = "claude",
    timeout: int = DEFAULT_TIMEOUT,
    permission_mode: str = "bypassPermissions",
) -> Transcript:
    """Starte `claude -p <prompt>` in `cwd`.

    `bypassPermissions` ist vertretbar, weil `cwd` immer ein Wegwerf-Workspace
    unter tempfile ist — nie ein echtes Repo. Der Runner erzwingt nur das:
    Arbeitsverzeichnis, Setting-Quellen (`--setting-sources project`) und
    MCP-Konfiguration (`--strict-mcp-config`). Nicht erzwungen — und damit kein
    Bestandteil der Isolationszusage — ist alles andere an der Prozessumgebung:
    Der Agent läuft mit der vollen `os.environ` des aufrufenden Prozesses,
    einschließlich `HOME`. Ein Werkzeug, das absolute Pfade außerhalb von `cwd`
    anspricht oder Zustand unter `$HOME` liest/schreibt, trifft auf echte Dateien.
    Ein Versuch, `HOME`/`XDG_*` auf ein Unterverzeichnis von `cwd` umzubiegen,
    scheiterte am Smoke-Test: Die CLI findet ihre Anmeldedaten dann nicht mehr
    (`~/.claude/.credentials.json`, `~/.claude.json`) und meldet „Not logged in".
    Siehe docs/known-limits.md.
    """
    cwd = Path(cwd)
    if not cwd.is_dir():
        # subprocess.run wirft FileNotFoundError sowohl wenn das CLI fehlt als auch
        # wenn `cwd` fehlt — ohne diese Vorabprüfung würde beides fälschlich als
        # "CLI nicht gefunden" gemeldet, obwohl das CLI da ist.
        return Transcript(stdout="", stderr=f"Arbeitsverzeichnis nicht gefunden: {cwd}", exit_code=127, timed_out=False)

    argv = [
        cli,
        "-p",
        "--permission-mode", permission_mode,
        # Isolation: ohne das misst der Eval die global installierte Fassung der
        # Skill (und lässt fremde Plugins mitreden) statt der Repo-Version im
        # Workspace. Ergebnisse wären maschinenabhängig.
        "--setting-sources", "project",
        "--strict-mcp-config",
        prompt,
    ]
    try:
        done = subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return Transcript(
            stdout=(exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=f"Timeout nach {timeout}s",
            exit_code=124,
            timed_out=True,
        )
    except FileNotFoundError:
        return Transcript(stdout="", stderr=f"CLI nicht gefunden: {cli}", exit_code=127, timed_out=False)
    except OSError as exc:
        return Transcript(stdout="", stderr=f"CLI nicht startbar: {exc}", exit_code=126, timed_out=False)

    return Transcript(stdout=done.stdout, stderr=done.stderr, exit_code=done.returncode, timed_out=False)
