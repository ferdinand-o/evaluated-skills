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


def test_five_contract_evals_load_with_anti_ceremony():
    evals = load_evals(EVALS)
    assert len(evals) == 5 and all(ev.eval_class == "contract" for ev in evals)
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
    prompt = _evals()[eval_id].prompt
    if prompt.startswith("/setup-user check"):
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


GAPS = REPO_ROOT / "skills" / "setup-user" / "references" / "superpowers-gaps.json"
GAP_STATUS = {"vorhanden", "Regel", "nativ", "bleibt bewusst", "entfällt", "Lücke"}


def _spec20_gap_names() -> set[str]:
    """Erste Spalte der Lückentabelle in Spec 20, Namen einzeln."""
    text = (REPO_ROOT / "specs" / "Spec 20 – plugin-split.md").read_text(encoding="utf-8")
    section = text.split("### Lückentabelle superpowers → Haus", 1)[1].split("\n### ", 1)[0]
    names = set()
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.startswith("| ") or cells[0] in ("superpowers", "---"):
            continue
        names.update(n.strip() for n in cells[0].split(","))
    return names


def test_gaps_json_names_match_spec_20():
    """Spec 21 (B): jede Zeile nennt nur Skills aus der Lückentabelle in Spec 20, jede
    Tabellenzeile kommt vor. Den Status prüft der Test nicht gegen die Spec — er ändert
    sich mit Spec 23 und 24 hier, nicht dort."""
    data = json.loads(GAPS.read_text(encoding="utf-8"))
    assert data["_meta"]["skill"] == "setup-user"
    rows = data["rows"]
    listed = [name for row in rows for name in row["superpowers"]]
    assert len(listed) == len(set(listed))
    assert set(listed) == _spec20_gap_names()
    for row in rows:
        assert row["status"] in GAP_STATUS, row
        assert row["replacement"], row
        if row["status"] == "Regel":
            assert row["rules"] and all(r.endswith(".md") and "/" not in r for r in row["rules"]), row


def test_plugin_fixture_reaches_plugins_only_through_the_cache():
    """su-plugins: installPath stammt von einem anderen Rechner; ohne Cache-Fallback fände
    route_check.py keinen Hook — der Eval prüfte dann nichts."""
    cfg = FIXTURES / "su-plugins" / "cfg"
    installed = json.loads((cfg / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
    for installs in installed["plugins"].values():
        assert not Path(installs[0]["installPath"]).exists()
    aligned = FIXTURES / "su-aligned" / "cfg"
    for path in aligned.rglob("*"):
        if path.is_file() and path.name != "settings.json":
            assert (cfg / path.relative_to(aligned)).read_bytes() == path.read_bytes(), path
