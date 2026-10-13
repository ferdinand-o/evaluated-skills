"""Verdrahtung der setup-repo-Evals (Spec 22, Abschnitt B). Läuft keinen Agenten.

Geprüft wird: die fünf Evals laden; die versionierten Pläne in sr-planned, sr-aligned
und sr-tampered gleichen einem neu erzeugten (sr-tampered bis auf die eine absichtliche
Änderung); der Bestand in sr-aligned gleicht dem Ergebnis von apply; und jeder Eval,
mit den installierten Skripten nachgespielt wie ein Agent sie aufrufen würde, besteht
seine eigenen Assertionen — gemessen mit evalkit, nicht mit nachgebauten Regeln.
Pläne entstehen wie im Eval-Workspace in einer frischen Git-Kopie mit einem Commit
„fixture baseline" und einem leeren Config-Verzeichnis."""

import json
import os
import shutil
import subprocess
import sys

import pytest
from conftest import REPO_ROOT, load_script
from evalkit.assertions import check
from evalkit.schema import load_evals
from evalkit.workspace import prepare

detect_mod = load_script("skills/setup-repo/scripts/detect_repo.py")
harvest_mod = load_script("skills/setup-repo/scripts/harvest_rules.py")
plan_mod = load_script("skills/setup-repo/scripts/plan_repo.py")
apply_mod = load_script("skills/setup-repo/scripts/apply_repo.py")

EVALS = REPO_ROOT / "evals" / "setup-repo" / "evals.json"
FIXTURES = REPO_ROOT / "evals" / "fixtures"
SKILL = REPO_ROOT / "skills" / "setup-repo"
PLAN = ".skills/cache/setup-repo/plan.md"
CLASSES = {"c1": "werkzeug"}
REGENERATE = "Fixture veraltet: neu erzeugen, wie die description in ihrer fixture.json es beschreibt"


def _evals() -> dict:
    return {ev.id: ev for ev in load_evals(EVALS)}


def _git_copy(src, dest, *, skip_cache=True):
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("fixture.json", *([".skills"] if skip_cache else [])))
    g = ["git", "-c", "user.name=evalkit", "-c", "user.email=evalkit@localhost"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fixture baseline"]):
        subprocess.run(g + args, cwd=dest, check=True, capture_output=True)
    return dest


def _fresh_block(fixture, tmp_path):
    ws = _git_copy(FIXTURES / fixture, tmp_path / f"fresh-{fixture}")
    detect = detect_mod.detect(ws, tmp_path / "leer")
    return plan_mod.build_plan(ws, detect, harvest_mod.harvest(ws, detect), {"classes": CLASSES})


def test_five_contract_evals_load_with_anti_ceremony():
    evals = load_evals(EVALS)
    assert len(evals) == 5 and all(ev.eval_class == "contract" for ev in evals)
    assert any(ev.id.startswith("anti-ceremony-") for ev in evals)
    assert all("Diskriminator" in (ev.notes or "") for ev in evals)
    for name in ("sr-aligned", "sr-fresh", "sr-notests", "sr-planned", "sr-tampered"):
        assert json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))["git"] is True


def test_fixture_plans_are_current(tmp_path):
    fresh = _fresh_block("sr-planned", tmp_path)
    for fixture in ("sr-planned", "sr-aligned"):
        stored = apply_mod.read_block(FIXTURES / fixture / PLAN)
        assert stored == fresh, f"{fixture}: {REGENERATE}"

    raw = (FIXTURES / "sr-tampered" / PLAN).read_text(encoding="utf-8")
    block = json.loads(raw[raw.index("```json setup-repo-plan") + len("```json setup-repo-plan"):].split("```")[0])
    assert block["verification"]["command"] == "make deploy"
    assert plan_mod.plan_hash(block) != block["hash"]
    block["verification"]["command"] = "make check"
    assert block == fresh, "sr-tampered weicht an mehr als der einen absichtlichen Stelle ab"


def test_aligned_fixture_matches_apply(tmp_path):
    ws = _git_copy(FIXTURES / "sr-planned", tmp_path / "ws", skip_cache=False)
    assert apply_mod.apply_plan(ws, ws / PLAN)["ok"] is True
    aligned = FIXTURES / "sr-aligned"
    for path in sorted(p for p in aligned.rglob("*") if p.is_file() and p.name != "fixture.json"):
        rel = path.relative_to(aligned).as_posix()
        assert (ws / rel).read_bytes() == path.read_bytes(), f"{rel}: {REGENERATE}"
    produced = {p.relative_to(ws).as_posix() for p in ws.rglob("*") if p.is_file()
                and not p.relative_to(ws).as_posix().startswith((".git/", ".skills/cache/setup-repo/apply.md"))}
    expected = {p.relative_to(aligned).as_posix() for p in aligned.rglob("*") if p.is_file()} - {"fixture.json"}
    assert produced == expected


def _run(ws, script, *args):
    env = {**os.environ, "HOME": str(ws.parent / "home"), "USERPROFILE": str(ws.parent / "home"),
           "CLAUDE_CONFIG_DIR": str(ws.parent / "cfg")}
    proc = subprocess.run([sys.executable, str(ws / ".claude/skills/setup-repo/scripts" / script), *args],
                          cwd=ws, capture_output=True, text=True, env=env, timeout=120)
    return proc.stdout + proc.stderr


def _replay(eval_id, ws):
    if eval_id.startswith("anti-ceremony-"):
        return _run(ws, "apply_repo.py", "--check")
    if eval_id.startswith("plan-"):
        out = _run(ws, "detect_repo.py") + _run(ws, "harvest_rules.py")
        classes = json.dumps(CLASSES) if eval_id == "plan-from-repo-writes-only-report" else "{}"
        return out + _run(ws, "plan_repo.py", "--classes", classes)
    return _run(ws, "apply_repo.py")


@pytest.mark.parametrize("eval_id", sorted(_evals()))
def test_replayed_eval_passes_its_own_assertions(eval_id, tmp_path):
    ev = _evals()[eval_id]
    for d in ("home", "cfg"):
        (tmp_path / d).mkdir()
    ws = prepare(tmp_path / "ws", SKILL, FIXTURES / ev.fixture)
    output = _replay(eval_id, ws.root)
    failures = [r.detail for a in ev.must if not (r := check(a, ws.root, ws.baseline, output)).ok]
    failures += [f"must_not: {a.type} {a.pattern}" for a in ev.must_not if check(a, ws.root, ws.baseline, output).ok]
    assert not failures, (failures, output)
    assert not any((tmp_path / "home").iterdir()), "nichts im Home"
