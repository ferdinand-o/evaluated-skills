"""Strukturprüfung der skill-forge-evals.json (Spec 17). Läuft keine Evals — kein
Agentenlauf. Was hier geprüft wird, ist die Verdrahtung: Jedes lint.json-Muster der
Evals greift an einer echten Ausgabe des Skripts, nicht an einer von Hand
geschriebenen; und die Fixtures stellen die Vorbedingungen her, die die Assertions
voraussetzen.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

from conftest import REPO_ROOT, load_script
from evalkit.schema import load_evals

ls = load_script("skills/skill-forge/scripts/lint_skill.py")

EVALS_PATH = REPO_ROOT / "evals" / "skill-forge" / "evals.json"
FIXTURES = REPO_ROOT / "evals" / "fixtures"
LINT_PATH = ".skills/cache/skill-forge/lint.json"


def _evals():
    return {ev.id: ev for ev in load_evals(EVALS_PATH)}


def _lint_patterns(ev) -> list[tuple[str, bool]]:
    """(pattern, erwartet_treffer) aller file_matches auf lint.json."""
    out = [(a.pattern, True) for a in ev.must if a.type == "file_matches" and a.path == LINT_PATH]
    out += [(a.pattern, False) for a in ev.must_not if a.type == "file_matches" and a.path == LINT_PATH]
    return out


def _lint_json(skill_dir: Path, out: Path, *extra: str) -> str:
    ls.main([str(skill_dir), "--out", str(out), *extra])
    return out.read_text(encoding="utf-8")


def test_five_contract_evals_load():
    evals = load_evals(EVALS_PATH)
    assert len(evals) == 5 and all(ev.eval_class == "contract" for ev in evals)


def test_anti_ceremony_eval_binds_to_lint_json_and_untouched_files():
    anti = _evals()["anti-ceremony-one-sentence-change-lints-only"]
    assert any(a.type == "file_exists" and a.path == LINT_PATH for a in anti.must)
    assert any(a.type == "file_unchanged" for a in anti.must)


def test_every_eval_answers_the_discriminator_question():
    for ev in load_evals(EVALS_PATH):
        assert re.search(r"(?i)diskriminator", ev.notes or ""), ev.id


def test_every_fixture_exists_and_none_ships_the_lint_artifact():
    for ev in load_evals(EVALS_PATH):
        fdir = FIXTURES / ev.fixture
        assert (fdir / "fixture.json").is_file(), ev.id
        assert not (fdir / ".skills").exists(), f"{ev.fixture} bringt .skills/ mit"
    assert not (FIXTURES / "sf-spec" / "evals").exists(), "sf-spec darf nichts unter evals/ mitbringen"


def test_sf_existing_is_clean_at_base():
    """Der Anti-Zeremonie-Eval misst, ob eine Änderung eskaliert — nicht, ob Altlasten
    aufgeräumt werden. Dafür muss die Fixture ohne Befund sein."""
    report = ls.lint_skill(FIXTURES / "sf-existing" / "skills" / "note-tag", FIXTURES / "sf-existing")
    assert report.findings == [], [f"{r.id}: {r.reason}" for r in report.findings]
    assert not any(r.status == "unchecked" for r in report.rules), [r.id for r in report.rules if r.status == "unchecked"]


def test_gate_and_noanti_patterns_grip_real_script_output(tmp_path):
    evals = _evals()
    gate = _lint_json(FIXTURES / "sf-gate" / "skills" / "gate-demo", tmp_path / "gate.json")
    noanti = _lint_json(FIXTURES / "sf-noanti" / "skills" / "quiet-log", tmp_path / "noanti.json")
    clean = _lint_json(FIXTURES / "sf-existing" / "skills" / "note-tag", tmp_path / "clean.json")
    for pattern, expected in _lint_patterns(evals["gate-word-without-hook-is-reported"]):
        assert bool(re.search(pattern, gate, re.MULTILINE)) is expected, pattern
        assert not (expected and re.search(pattern, clean, re.MULTILINE)), f"{pattern} greift auch an der sauberen Skill"
    for pattern, expected in _lint_patterns(evals["missing-anti-ceremony-eval-is-reported"]):
        assert bool(re.search(pattern, noanti, re.MULTILINE)) is expected, pattern
        assert not re.search(pattern, clean, re.MULTILINE)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)


def _existing_repo(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    shutil.copytree(FIXTURES / "sf-existing", root, ignore=shutil.ignore_patterns("fixture.json"))
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture baseline")
    return root


def test_diff_mode_patterns_grip_real_script_output_for_both_prompts(tmp_path):
    """Eval 1 und 2 nachgespielt: dieselbe Fixture, die Änderung aus dem jeweiligen
    Prompt, --base HEAD — und die Muster der Evals gegen die echte lint.json."""
    evals = _evals()
    root = _existing_repo(tmp_path)
    md = root / "skills" / "note-tag" / "SKILL.md"
    original = md.read_text(encoding="utf-8")

    sentence = original.replace("3. Fertig. Keine Zusammenfassung, keine Rückfrage.", "3. Fertig — keine Zusammenfassung, keine Rückfrage.")
    assert sentence != original
    md.write_text(sentence, encoding="utf-8")
    text = _lint_json(root / "skills" / "note-tag", root / LINT_PATH, "--base", "HEAD", "--repo-root", str(root))
    for pattern, expected in _lint_patterns(evals["anti-ceremony-one-sentence-change-lints-only"]):
        assert bool(re.search(pattern, text, re.MULTILINE)) is expected, pattern
    assert json.loads(text)["new_findings"] == []

    token = original.replace("`Untagged:`", "`Untagged →`")
    assert token != original
    md.write_text(token, encoding="utf-8")
    text = _lint_json(root / "skills" / "note-tag", root / LINT_PATH, "--base", "HEAD", "--repo-root", str(root))
    for pattern, expected in _lint_patterns(evals["token-change-makes-evals-due"]):
        assert bool(re.search(pattern, text, re.MULTILINE)) is expected, pattern


def test_routing_eval_binds_to_house_vocabulary_the_fixture_does_not_name():
    routing = _evals()["routing-new-skill-gets-house-evals"]
    spec00 = (FIXTURES / "sf-spec" / "specs" / "Spec 00 – skill-foundation.md").read_text(encoding="utf-8")
    for word in ("anti-ceremony", "Diskriminator", "expected_output", "contract", "must"):
        assert word.lower() not in spec00.lower(), f"Fixture sagt {word!r} vor"
    assert any("anti-ceremony-" in a.pattern for a in routing.must)
    assert any("expected_output" in a.pattern for a in routing.must_not)
