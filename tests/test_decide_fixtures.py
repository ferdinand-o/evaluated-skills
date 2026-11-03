"""Evals und Fixtures von decide (Spec 28). Läuft keine Agenten: Die Tests spielen das erwartete
Verhalten mit dem echten decide_log.py in Wegwerf-Repos nach und messen die Muster aus
evals/decide/evals.json an dessen Ausgaben — so greifen sie an echten Protokollen, Blöcken und
check-Zeilen, nicht an gedachten. Die Muster werden aus der Datei gelesen, nie kopiert."""

import ast
import re
import shutil
import subprocess
import sys

from conftest import REPO_ROOT, decide_add_small, decide_commit, decide_log_file, decide_script, git
from evalkit.assertions import ARTIFACT_HEADER_RE, check
from evalkit.schema import load_evals
from evalkit.workspace import prepare

dl = decide_script()

EVALS_PATH = REPO_ROOT / "evals" / "decide" / "evals.json"
FIXTURES = REPO_ROOT / "evals" / "fixtures"
SKILL = REPO_ROOT / "skills" / "decide"
LEDGER = "docs/big-decisions.md"
LOG_GLOB = ".skills/cache/decide/*/log.md"
DC = ("dc-loaders", "dc-logging", "dc-models", "dc-rules")


def _evals():
    return {ev.id: ev for ev in load_evals(EVALS_PATH)}


def _assertions(eval_id, kind, path=None):
    ev = _evals()[eval_id]
    found = [a for a in ev.must if a.type == kind and (path is None or a.path == path)]
    assert found, (eval_id, kind, path)
    return found


def _patterns(eval_id, kind, path=None):
    return [a.pattern for a in _assertions(eval_id, kind, path)]


def _hits(pattern, text):
    """Wie evalkit: `re.search` mit `re.MULTILINE`."""
    return bool(re.search(pattern, text, re.MULTILINE))


def _seed(tmp_path, monkeypatch, name, fixture):
    """Wegwerf-Repo mit dem Inhalt der Fixture, ein Commit, Arbeitsverzeichnis dorthin."""
    root = tmp_path / name
    shutil.copytree(FIXTURES / fixture, root, ignore=shutil.ignore_patterns("fixture.json"))
    git(root, "init", "-q")
    base = decide_commit(root, "fixture")
    monkeypatch.chdir(root)
    return root, base


def _line_of(path, needle):
    return next(n for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if needle in line)


def test_eval_patterns(decide_repo, tmp_path, monkeypatch, capsys):
    # Eval 2: Protokollzeile klein mit Treffer CONTRIBUTING.md:<n>.
    root, _ = _seed(tmp_path, monkeypatch, "e2", "dc-logging")
    n = _line_of(root / "CONTRIBUTING.md", "logging.getLogger(__name__)")
    assert decide_add_small("Logging", "print wie app/legacy.py oder logging?", "logging.getLogger(__name__)",
                            f"gesucht: CONTRIBUTING.md, app/legacy.py — Treffer: CONTRIBUTING.md:{n}") == 0
    log = decide_log_file(root).read_text(encoding="utf-8")
    assert ARTIFACT_HEADER_RE.match(log.splitlines()[0])
    (row,) = _patterns("small-decision-cites-repo-source", "file_matches", LOG_GLOB)
    assert _hits(row, log)
    assert not _hits(row, f"Klein entschieden: gesucht: CONTRIBUTING.md — Treffer: CONTRIBUTING.md:{n}")
    other = tmp_path / "annahme"
    other.mkdir()
    git(other, "init", "-q")
    monkeypatch.chdir(other)
    assert decide_add_small("Logging", "Wie loggt sync()?", "logging", "gesucht: CONTRIBUTING.md — nichts gefunden") == 0
    assert not _hits(row, decide_log_file(other).read_text(encoding="utf-8"))   # Annahme ist keine klein-Zeile

    # Eval 3: Block offen mit Schlüssel migration:.
    root, _ = _seed(tmp_path, monkeypatch, "e3", "dc-models")
    assert dl.main(["add", "--class", "gross", "--topic", "Migrationen", "--question", "Spalte legacy_id entfernen?",
                    "--key", "migration:migrations/", "--option", "A: Spalte samt Migration 0002 entfernen",
                    "--option", "B: Spalte behalten", "--recommendation", "A, weil nirgends gelesen"]) == 0
    open_ledger = (root / LEDGER).read_text(encoding="utf-8")
    side = "side-decision-expensive-stays-open"
    assert all(check(a, root, {}).ok for a in _assertions(side, "artifact_header"))
    for pattern in _patterns(side, "file_matches", LEDGER):
        assert _hits(pattern, open_ledger), pattern
        assert not _hits(pattern, "D-1 ist offen (2026-11-03), der Schlüssel: migration:migrations/ wartet."), pattern

    # Eval 4: Block freigegeben per Auftrag, dann Migration, dann check — Schlusszeile.
    root, base = _seed(tmp_path, monkeypatch, "e4", "dc-models")
    order = _evals()["user-order-is-approval"].prompt
    assert dl.main(["add", "--class", "gross", "--topic", "Migrationen", "--question", "Spalte legacy_id entfernen?",
                    "--key", "migration:migrations/", "--approved-by-request", order]) == 0
    models = root / "app" / "models.py"
    models.write_text("".join(line for line in models.read_text(encoding="utf-8").splitlines(keepends=True)
                              if "legacy_id" not in line), encoding="utf-8")
    (root / "migrations" / "0002_drop_legacy_id.py").write_text(
        'def up(db):\n    db.execute("ALTER TABLE users DROP COLUMN legacy_id")\n\n\n'
        'def down(db):\n    db.execute("ALTER TABLE users ADD COLUMN legacy_id INTEGER")\n', encoding="utf-8")
    capsys.readouterr()
    code = dl.main(["check", "--range", base])
    out = capsys.readouterr().out
    assert code == 0, out                                   # migrations/0002 ist freigegeben
    approved_ledger = (root / LEDGER).read_text(encoding="utf-8")
    approval = "user-order-is-approval"
    for pattern in _patterns(approval, "file_matches", LEDGER):
        assert _hits(pattern, approved_ledger), pattern
        assert not _hits(pattern, open_ledger), pattern       # der offene Block aus Eval 3 trifft nicht
        assert not _hits(pattern, "D-1 ist freigegeben, Quelle der Antwort war der Auftrag."), pattern
    (tail,) = _patterns(approval, "output_matches")
    assert _hits(tail, out.splitlines()[-1])
    assert not _hits(tail, "Die Kategorie data-delete bleibt ungeprüft.")
    (still_open,) = [p for p in _patterns(side, "file_matches", LEDGER) if "offen" in p]
    assert not _hits(still_open, approved_ledger)           # und der freigegebene nicht für offen

    # Eval 5: Regel immer fragen stuft hoch — Block offen mit rule:UI-Texte.
    root, _ = _seed(tmp_path, monkeypatch, "e5", "dc-rules")
    n = _line_of(root / "app" / "cli.py", "Fehler:")
    assert decide_add_small("UI-Texte", "Wie lautet die Meldung bei fehlender Datei?", "B: Datei nennen",
                            f"gesucht: app/cli.py — Treffer: app/cli.py:{n}",
                            "--option", "A: Fehler: Datei nicht gefunden", "--option", "B: Datei nennen") == 0
    rule_ledger = (root / LEDGER).read_text(encoding="utf-8")
    assert "\nSchlüssel: rule:UI-Texte\n" in rule_ledger
    for pattern in _patterns("always-ask-rule-upgrades-small", "file_matches", LEDGER):
        assert _hits(pattern, rule_ledger), pattern
        assert not _hits(pattern, "Das Thema UI-Texte bleibt als D-1 offen."), pattern
    assert not _hits(_patterns("always-ask-rule-upgrades-small", "file_matches", LEDGER)[0], open_ledger)

    # Eval 1: der Wortlaut der Untergrenze.
    (token,) = _patterns("anti-ceremony-order-in-file-needs-no-decision", "output_matches")
    assert _hits(token, "Keine Entscheidung nötig — die Reihenfolge in einer Datei merkt niemand außerhalb.")
    assert not _hits(token, "Eine Entscheidung ist hier nicht nötig.")


def test_models_fixture_is_red_for_the_import_and_green_for_the_field(tmp_path):
    """Ohne LF und `import json` allein auf seiner Zeile wäre das Muster von Eval 3 trivial grün."""
    side = _assertions("side-decision-expensive-stays-open", "file_matches", "app/models.py")
    field_kept, import_gone = side
    (field_gone,) = _assertions("user-order-is-approval", "file_matches", "app/models.py")
    assert "legacy_id" in field_kept.pattern and "import json" in import_gone.pattern

    ws = prepare(tmp_path / "ws", SKILL, FIXTURES / "dc-models")
    assert not check(import_gone, ws.root, ws.baseline).ok
    assert check(field_kept, ws.root, ws.baseline).ok
    assert not check(field_gone, ws.root, ws.baseline).ok

    models = ws.root / "app" / "models.py"
    text = models.read_text(encoding="utf-8")
    models.write_text(text.replace("import json\n", ""), encoding="utf-8")        # Ergebnis von Eval 3
    assert check(import_gone, ws.root, ws.baseline).ok
    assert check(field_kept, ws.root, ws.baseline).ok

    models.write_text("".join(line for line in text.splitlines(keepends=True)
                              if not line.lstrip().startswith("legacy_id")), encoding="utf-8")   # ohne Feld
    assert not check(field_kept, ws.root, ws.baseline).ok
    assert check(field_gone, ws.root, ws.baseline).ok
    assert not check(import_gone, ws.root, ws.baseline).ok


def test_fixtures_hold_what_the_evals_assume():
    for name in DC:
        fixture = FIXTURES / name
        files = [p for p in fixture.rglob("*") if p.is_file()]
        rels = [p.relative_to(fixture).as_posix() for p in files]
        assert not any(r.startswith(".skills/cache/") for r in rels), name
        assert LEDGER not in rels, name
        for path in files:
            assert ".skills/cache/" not in path.read_text(encoding="utf-8"), path
            assert LEDGER not in path.read_text(encoding="utf-8"), path

    loaders = (FIXTURES / "dc-loaders" / "app" / "loaders.py").read_text(encoding="utf-8")
    assert "def load_users(" in loaders and "def load_orders(" in loaders and "load_products" not in loaders

    logging_fx = FIXTURES / "dc-logging"
    assert "logging.getLogger(__name__)" in (logging_fx / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "print(" in (logging_fx / "app" / "legacy.py").read_text(encoding="utf-8")
    sync = (logging_fx / "app" / "sync.py").read_text(encoding="utf-8")
    assert "def sync(" in sync and "logging" not in sync and "getLogger" not in sync

    models_fx = FIXTURES / "dc-models"
    raw = (models_fx / "app" / "models.py").read_bytes()
    assert b"\r" not in raw
    lines = raw.decode("utf-8").splitlines()
    assert lines.count("import json") == 1
    assert "    legacy_id = Column(Integer)" in lines
    assert "# Aufgabe: ungenutzten Import json entfernen" in raw.decode("utf-8")
    assert "# Aufgabe: legacy_id wird nirgends mehr gelesen — Spalte entfernen?" in raw.decode("utf-8")
    migration = ast.parse((models_fx / "migrations" / "0001_initial.py").read_text(encoding="utf-8"))
    assert {"up", "down"} <= {node.name for node in migration.body if isinstance(node, ast.FunctionDef)}
    assert "`NNNN_<name>.py`" in (models_fx / "migrations" / "README.md").read_text(encoding="utf-8")
    assert not list((models_fx / "migrations").glob("0002_*.py"))

    rules = (FIXTURES / "dc-rules" / ".skills" / "decide" / "rules.md").read_text(encoding="utf-8")
    assert "immer fragen: UI-Texte" in rules.splitlines()
    assert "Fehler:" in (FIXTURES / "dc-rules" / "app" / "cli.py").read_text(encoding="utf-8")


def test_python_fixtures_are_importable(tmp_path):
    """Jedes Modul der Fixtures importiert ohne Fremdpaket; geprüft in einer Kopie, damit kein
    `__pycache__` in der Fixture landet."""
    for name in DC:
        root = tmp_path / name
        shutil.copytree(FIXTURES / name, root, ignore=shutil.ignore_patterns("fixture.json"))
        modules = [p.relative_to(root).with_suffix("").as_posix().replace("/", ".")
                   for p in sorted((root / "app").glob("*.py")) if p.name != "__init__.py"]
        code = "import importlib, sys\nfor m in sys.argv[1:]: importlib.import_module(m)\n"
        for path in sorted(root.glob("migrations/*.py")):
            code += f"import runpy; runpy.run_path({str(path)!r})\n"
        done = subprocess.run([sys.executable, "-B", "-c", code, *modules], cwd=root,
                              capture_output=True, text=True, check=False)
        assert done.returncode == 0, (name, done.stderr)
