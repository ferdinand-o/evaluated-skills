"""Einen frischen Agenten im Workspace starten und sein Transcript einsammeln."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT = 600


def assistant_text(raw: str) -> str:
    """Alle Assistant-Textblöcke aus einem stream-json-Transcript, in Reihenfolge.

    Mit dem Default `--output-format text` liefert `claude -p` auf stdout nur die
    **letzte** Assistant-Nachricht. Jede `output_matches`-Assertion und jeder
    Judge-Claim über den Ablauf ("X, bevor Y geschieht") prüfte damit einen
    Ausschnitt, den er für das Ganze hielt: Was in einem früheren Zug stand, war
    unbeobachtbar. Ein motion-landing-Eval fiel deshalb durch, obwohl der geforderte
    Storyboard-Block korrekt erzeugt worden war — nur eben eine Runde zu früh.

    Kaputte Zeilen werden übersprungen: Ein Timeout schneidet die letzte Zeile
    mitten im JSON ab, und daran soll die Auswertung des Rests nicht scheitern.
    """
    parts: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "assistant":
            continue
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                parts.append(block["text"])
    return "\n".join(parts)


@dataclass(frozen=True)
class Transcript:
    """`stdout` ist das rohe stream-json-Transcript (Diagnose), `text` die daraus
    zusammengesetzte Assistant-Ausgabe aller Züge (Bewertungsgrundlage)."""

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    text: str = ""


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
        # Sorgt dafür, dass die Repo-Version der Skill aus dem Workspace gilt und
        # nicht eine global installierte gleichen Namens. Es hält fremde Skills
        # aber NICHT heraus: gemessen sind 16 global installierte Skills im
        # Agenten trotz dieser Flagge (docs/known-limits.md, Abschnitt Isolation).
        "--setting-sources", "project",
        "--strict-mcp-config",
        # stream-json statt des Defaults `text`: Letzterer gibt nur die letzte
        # Assistant-Nachricht aus, siehe assistant_text().
        "--output-format", "stream-json",
        "--verbose",
        prompt,
    ]
    try:
        done = subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        return Transcript(
            stdout=partial or "",
            stderr=f"Timeout nach {timeout}s",
            exit_code=124,
            timed_out=True,
            text=assistant_text(partial or ""),
        )
    except FileNotFoundError:
        return Transcript(stdout="", stderr=f"CLI nicht gefunden: {cli}", exit_code=127, timed_out=False)
    except OSError as exc:
        return Transcript(stdout="", stderr=f"CLI nicht startbar: {exc}", exit_code=126, timed_out=False)

    return Transcript(
        stdout=done.stdout,
        stderr=done.stderr,
        exit_code=done.returncode,
        timed_out=False,
        text=assistant_text(done.stdout),
    )
