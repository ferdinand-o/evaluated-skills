"""Evals und Fixtures von test-first (Spec 24). Läuft keine Agenten: Die Tests spielen
das erwartete Verhalten mit dem echten tdd_log.py in einem Eval-Workspace nach und
bewerten es mit evalkit — so greifen die Muster an echten Logs, nicht an gedachten."""

import json
import re
import shlex
import sys

from conftest import REPO_ROOT, load_script
from evalkit.runner import grade
from evalkit.schema import load_evals
from evalkit.workspace import prepare

tdd = load_script("skills/test-first/scripts/tdd_log.py")

EVALS_PATH = REPO_ROOT / "evals" / "test-first" / "evals.json"
FIXTURES = REPO_ROOT / "evals" / "fixtures"
SKILL = REPO_ROOT / "skills" / "test-first"
LOG = ".skills/cache/test-first/log.md"
PYTEST = f"{shlex.quote(sys.executable)} -m pytest -q"

SLUGIFY = '''

def slugify(text):
    text = text.lower()
    for umlaut, repl in {"ä": "ae", "ö": "oe", "ü": "ue"}.items():
        text = text.replace(umlaut, repl)
    return text.replace(" ", "-")
'''
SLUG_TEST = '''

def test_slugify_writes_umlauts():
    from src.slug import slugify
    assert slugify("Äpfel über") == "aepfel-ueber"
'''


def _evals():
    return {ev.id: ev for ev in load_evals(EVALS_PATH)}


def _workspace(tmp_path, fixture):
    return prepare(tmp_path / "ws", SKILL, FIXTURES / fixture)


def _append(root, rel, text):
    path = root / rel
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def _tdd(root, action, test_id, command, capsys):
    code = tdd.main([action, "--root", str(root), "--test", test_id, "--", command])
    return code, capsys.readouterr().out


def _cycle_pattern():
    return next(a.pattern for a in _evals()["red-before-green-is-recorded"].must
                if a.type == "file_matches" and "red" in a.pattern)


def test_five_contract_evals_with_git_fixtures():
    evals = load_evals(EVALS_PATH)
    assert [ev.id for ev in evals] == [
        "anti-ceremony-doc-typo-runs-no-cycle", "red-before-green-is-recorded",
        "green-on-first-run-is-flagged", "pressure-still-red-first", "explicit-waiver-says-untested"]
    assert all(ev.eval_class == "contract" for ev in evals)
    assert len({ev.prompt for ev in evals[1:]}) == 3          # Evals 2 bis 5: drei Prompts
    for ev in evals:
        meta = json.loads((FIXTURES / ev.fixture / "fixture.json").read_text(encoding="utf-8"))
        assert meta["git"] is True
        assert not (FIXTURES / ev.fixture / ".skills").exists()


def test_fixtures_hold_what_the_evals_assume():
    assert "Hello" not in (FIXTURES / "tf-docs" / "README.md").read_text(encoding="utf-8")
    assert "def slugify" not in (FIXTURES / "tf-feature" / "src" / "slug.py").read_text(encoding="utf-8")
    existing = (FIXTURES / "tf-existing" / "src" / "slug.py").read_text(encoding="utf-8")
    assert "def slugify" in existing
    assert "slugify" not in (FIXTURES / "tf-existing" / "tests" / "test_slug.py").read_text(encoding="utf-8")
    # Kein Fixture-Wert steht als Beispiel in der Skill (Lesson aus Spec 23).
    skill_text = "".join(p.read_text(encoding="utf-8") for p in SKILL.rglob("*.md"))
    assert "slugify" not in skill_text and "collapse_spaces" not in skill_text


def test_eval_patterns_match_only_real_cycles(tmp_path, capsys):
    pattern = _cycle_pattern()
    root = tmp_path / "repo"
    root.mkdir()
    fail = f"{shlex.quote(sys.executable)} -c \"raise SystemExit(1)\""
    ok = f"{shlex.quote(sys.executable)} -c pass"

    _tdd(root, "red", "test_a", fail, capsys)
    _tdd(root, "green", "test_a", ok, capsys)
    real = (root / LOG).read_text(encoding="utf-8")
    assert re.search(pattern, real, re.MULTILINE)

    # sofort-grün, danach green: green schreibt keine Zeile — das Muster greift nicht.
    other = tmp_path / "other"
    other.mkdir()
    _tdd(other, "red", "test_b", ok, capsys)
    _tdd(other, "green", "test_b", ok, capsys)
    assert not re.search(pattern, (other / LOG).read_text(encoding="utf-8"), re.MULTILINE)

    row = "| {id} | {phase} | `cmd` | 0 | 2026-10-13T10:00:00 |  |"
    crafted = {
        "sofort-grün vor green": [("t", "sofort-grün"), ("t", "green")],
        "zwei IDs": [("a", "red"), ("b", "green")],
        "ungeprüft vor green": [("t", "ungeprüft"), ("t", "green")],
        "Präfix-ID": [("test_a", "red"), ("test_ab", "green")],
    }
    for name, rows in crafted.items():
        text = "\n".join(row.format(id=i, phase=p) for i, p in rows)
        assert not re.search(pattern, text, re.MULTILINE), name
    flagged = next(a.pattern for a in _evals()["green-on-first-run-is-flagged"].must if a.type == "file_matches")
    assert re.search(flagged, (other / LOG).read_text(encoding="utf-8"), re.MULTILINE)
    assert not re.search(flagged, real, re.MULTILINE)


def test_simulated_skill_runs_pass_and_baselines_fail(tmp_path, capsys):
    evals = _evals()

    # Eval 2: Test, Rot, Code, Grün.
    ws = _workspace(tmp_path / "e2", "tf-feature")
    _append(ws.root, "tests/test_slug.py", SLUG_TEST)
    command = f"{PYTEST} tests/test_slug.py::test_slugify_writes_umlauts"
    assert _tdd(ws.root, "red", "test_slugify_writes_umlauts", command, capsys)[0] == 0
    _append(ws.root, "src/slug.py", SLUGIFY)
    assert _tdd(ws.root, "green", "test_slugify_writes_umlauts", command, capsys)[0] == 0
    result = grade(evals["red-before-green-is-recorded"], ws.root, ws.baseline, {}, "")
    assert result.passed, result.failures
    assert grade(evals["pressure-still-red-first"], ws.root, ws.baseline, {}, "").passed

    # Baseline: Code und Test ohne Log — Eval 2 und 4 scheitern.
    base = _workspace(tmp_path / "e2b", "tf-feature")
    _append(base.root, "src/slug.py", SLUGIFY)
    _append(base.root, "tests/test_slug.py", SLUG_TEST)
    assert not grade(evals["red-before-green-is-recorded"], base.root, base.baseline, {}, "").passed
    assert not grade(evals["pressure-still-red-first"], base.root, base.baseline, {}, "").passed

    # Eval 3: das Verhalten gibt es schon — sofort grün, Code unverändert.
    ws3 = _workspace(tmp_path / "e3", "tf-existing")
    _append(ws3.root, "tests/test_slug.py", SLUG_TEST)
    code, out = _tdd(ws3.root, "red", "test_slugify_writes_umlauts", command, capsys)
    assert code == 1
    result = grade(evals["green-on-first-run-is-flagged"], ws3.root, ws3.baseline, {}, out)
    assert result.passed, result.failures

    # Eval 5: Verzicht — Code ohne Log, Wortlaut in der Antwort.
    ws5 = _workspace(tmp_path / "e5", "tf-feature")
    _append(ws5.root, "src/slug.py", SLUGIFY)
    assert grade(evals["explicit-waiver-says-untested"], ws5.root, ws5.baseline, {}, "ungetestet auf Wunsch").passed
    assert not grade(evals["explicit-waiver-says-untested"], ws5.root, ws5.baseline, {}, "fertig").passed

    # Eval 1: Doku-Korrektur ohne Log.
    ws1 = _workspace(tmp_path / "e1", "tf-docs")
    readme = ws1.root / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8").replace("Helo", "Hello"), encoding="utf-8")
    assert grade(evals["anti-ceremony-doc-typo-runs-no-cycle"], ws1.root, ws1.baseline, {},
                 "Kein Test-Zyklus nötig — reine Doku.").passed
