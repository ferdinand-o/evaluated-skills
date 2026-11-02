"""Gemeinsame Test-Helfer. Skill-Skripte liegen außerhalb von evalkit/ und sind
keine Pakete — sie werden per importlib geladen, statt sys.path zu verbiegen."""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_script(relpath: str):
    """Lade ein Skill-Skript als Modul, z. B. 'skills/dev-report/scripts/collect.py'.

    Registriert das Modul in `sys.modules`, bevor es ausgeführt wird — ohne das
    scheitert jede Klasse, die `dataclasses` benutzt: deren Maschinerie liest
    `sys.modules[cls.__module__].__dict__` und trifft sonst auf `None`. Der Import
    stirbt dann mit "'NoneType' object has no attribute '__dict__'" — einem Fehler,
    der wie ein Defekt im Skill-Code aussieht und nicht wie einer in diesem Helfer.
    """
    path = REPO_ROOT / relpath
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(root: Path, *args: str) -> str:
    """Git im gegebenen Ordner, mit check=True — für Tests, die ein Repo aufbauen."""
    import subprocess
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout


# --- decide (Spec 28): Repo, Protokoll, add --class klein ---------------------------------
# Einmal hier statt wortgleich in jeder tests/test_decide_*.py; Pfad und Zeilen kommen aus
# decide_log.py selbst, eine Format-Änderung wird also nur dort nachgezogen.

DECIDE_SCRIPT = "skills/decide/scripts/decide_log.py"
DECIDE_SESSION = "sitzung-1"
_decide_module = None


def decide_script():
    """decide_log.py als Modul, einmal geladen und von allen decide-Tests geteilt."""
    global _decide_module
    if _decide_module is None:
        _decide_module = load_script(DECIDE_SCRIPT)
    return _decide_module


@pytest.fixture
def decide_repo(tmp_path, monkeypatch):
    """Git-Repo als Wurzel, eigenes HOME, Sitzung aus der Umgebung; (root, home)."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", DECIDE_SESSION)
    monkeypatch.chdir(root)
    return root, home


def decide_log_file(root: Path, session: str = DECIDE_SESSION) -> Path:
    """Pfad des Protokolls, wie decide_log.py ihn bildet (`log_path`)."""
    return decide_script().log_path(root, session)


def decide_rows(root: Path, session: str = DECIDE_SESSION):
    """Zellen der Tabellenzeilen ohne Kopf: [zeit, thema, klasse, frage, entscheidung, beleg, regel],
    gelesen mit `parse_rows` aus decide_log.py. Das Format selbst prüft
    tests/test_decide_log.py::test_log_format_against_raw_text gegen den Rohtext.

    `parse_rows` verwirft Zeilen mit falscher Zellzahl still; damit keine für die Tests
    verschwindet, muss die Zahl der Tabellenzeilen im Rohtext (beginnen mit `|`, ohne Kopf und
    Trenner) gleich der Zahl der geparsten sein, sonst AssertionError."""
    dl = decide_script()
    text = decide_log_file(root, session).read_text(encoding="utf-8")
    entries = dl.parse_rows(text)
    head = {line.strip() for line in dl.TABLE_HEAD.splitlines()}
    raw = [line for line in text.splitlines() if line.strip().startswith("|") and line.strip() not in head]
    if len(raw) != len(entries):
        raise AssertionError(f"{len(raw)} Tabellenzeilen im Rohtext, {len(entries)} geparst: {raw}")
    return [[entry[c] for c in dl.COLUMNS] for entry in entries]


def decide_add_small(topic, question, decision, evidence, *extra):
    """`decide_log.py add --class klein …` über `main`; gibt den Exit-Code zurück."""
    return decide_script().main(["add", "--class", "klein", "--topic", topic, "--question", question,
                                 "--decision", decision, "--evidence", evidence, *extra])


# --- decide check: Commit-Helfer und Schlusszeile ------------------------------------------
# Einmal hier statt in tests/test_decide_log.py und den beiden check-Stubs. DECIDE_TAIL ist
# bewusst ein Literal (die Erwartung aus Spec 28, Abschnitt check), nicht aus dem Skript gelesen.

DECIDE_TAIL = ("ungeprüft: data-delete, unsaved-work, push, external, cost; "
               "teilweise: api, migration, dependency, permissions")


def decide_commit(root: Path, message: str = "x") -> str:
    """Alles im Repo committen (`git add -A`, feste Identität); gibt den Hash von HEAD zurück."""
    git(root, "add", "-A")
    git(root, "-c", "user.email=t@example.org", "-c", "user.name=t", "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD").strip()
