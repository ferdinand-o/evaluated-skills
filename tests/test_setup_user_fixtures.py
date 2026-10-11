"""Verdrahtung der setup-user-Evals (Spec 21, Abschnitt A). Läuft keinen Agenten.

Geprüft wird: die vier Evals laden; die versionierten Pläne in su-planned und
su-own-statusline gleichen einem neu erzeugten; su-aligned gleicht den Assets; und jeder
Eval, mit den Skripten nachgespielt wie ein Agent sie aufrufen würde, besteht seine
eigenen Assertionen — gemessen mit evalkit, nicht mit nachgebauten Regeln."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT, load_script
from evalkit.assertions import check
from evalkit.schema import load_evals
from evalkit.workspace import snapshot

inspect = load_script("skills/setup-user/scripts/inspect_config.py")
apply = load_script("skills/setup-user/scripts/apply_config.py")

EVALS = REPO_ROOT / "evals" / "setup-user" / "evals.json"
FIXTURES = REPO_ROOT / "evals" / "fixtures"
SCRIPTS = REPO_ROOT / "skills" / "setup-user" / "scripts"
ASSETS = REPO_ROOT / "skills" / "setup-user" / "assets"


def _evals() -> dict:
    return {ev.id: ev for ev in load_evals(EVALS)}


def test_four_contract_evals_load_with_anti_ceremony():
    evals = load_evals(EVALS)
    assert len(evals) == 4 and all(ev.eval_class == "contract" for ev in evals)
    assert any(ev.id.startswith("anti-ceremony-") for ev in evals)
    assert all("Diskriminator" in (ev.notes or "") for ev in evals)


@pytest.mark.parametrize("fixture", ["su-planned", "su-own-statusline"])
def test_fixture_plans_are_current(fixture, monkeypatch):
    root = FIXTURES / fixture
    monkeypatch.chdir(root)
    stored = apply.read_block(root / "cfg" / "setup-user" / "plan.md")
    fresh = inspect.build_plan(Path("cfg"), {}, "python3")
    assert fresh == stored, "Plan der Fixture veraltet: inspect_config.py --config-dir cfg --python python3 im Fixture-Ordner"


def test_aligned_fixture_matches_assets():
    cfg = FIXTURES / "su-aligned" / "cfg"
    for name in ("statusline.py", "context_hint.py"):
        assert (cfg / "setup-user" / "runtime" / name).read_bytes() == (ASSETS / "runtime" / name).read_bytes(), name
    block = inspect.build_plan(FIXTURES / "su-fresh" / "cfg", {}, "python3")
    ops = {op["path"]: op for op in block["operations"]}
    for rel in ("CLAUDE.md", "rules/communication.md", "rules/verification.md", "rules/context.md", "rules/git.md",
                "setup-user/thresholds.json"):
        assert (cfg / rel).read_text(encoding="utf-8") == ops[rel]["content"], rel


def _run(script: str, *args: str, cwd: Path) -> str:
    env = {**os.environ, "HOME": str(cwd / ".home"), "USERPROFILE": str(cwd / ".home")}
    env.pop("CLAUDE_CONFIG_DIR", None)
    proc = subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=cwd, capture_output=True,
                          text=True, env=env, timeout=60)
    return proc.stdout + proc.stderr


def _replay(eval_id: str, ws: Path) -> str:
    if eval_id.startswith("anti-ceremony-"):
        return _run("verify_install.py", "--config-dir", "cfg", "--write-check", cwd=ws)
    if eval_id == "plan-is-default-and-writes-only-plan":
        return _run("inspect_config.py", "--config-dir", "cfg", cwd=ws)
    out = _run("apply_config.py", "--plan", "cfg/setup-user/plan.md", "--config-dir", "cfg", cwd=ws)
    return out + _run("verify_install.py", "--config-dir", "cfg", cwd=ws)


@pytest.mark.skipif(shutil.which("bash") is None, reason="verify_install.py braucht bash")
@pytest.mark.parametrize("eval_id", sorted(_evals()))
def test_replayed_eval_passes_its_own_assertions(eval_id, tmp_path):
    ev = _evals()[eval_id]
    ws = tmp_path / "ws"
    shutil.copytree(FIXTURES / ev.fixture, ws, ignore=shutil.ignore_patterns("fixture.json"))
    (ws / ".home").mkdir()
    baseline = snapshot(ws)
    output = _replay(eval_id, ws)
    failures = [r.detail for a in ev.must if not (r := check(a, ws, baseline, output)).ok]
    failures += [f"must_not: {a.type}" for a in ev.must_not if check(a, ws, baseline, output).ok]
    assert not failures, (failures, output)
    assert not any((ws / ".home").iterdir()), "nichts im Home"
