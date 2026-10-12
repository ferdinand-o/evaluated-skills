"""Tests für skills/setup-repo/scripts/harvest_rules.py (Spec 22, Abschnitt B).

Kandidaten tragen Quelle und den Beleg, welches Werkzeug sie prüft; die Klasse trägt erst
Claude über plan_repo.py --classes ein."""

import json
import subprocess
import sys

from conftest import REPO_ROOT, load_script

detect_mod = load_script("skills/setup-repo/scripts/detect_repo.py")
harvest_mod = load_script("skills/setup-repo/scripts/harvest_rules.py")
SCRIPT = REPO_ROOT / "skills" / "setup-repo" / "scripts" / "harvest_rules.py"


def write(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def git(root, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, check=True,
                   capture_output=True)


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    write(repo, "pyproject.toml", '[tool.ruff]\nline-length = 100\n\n[tool.ruff.lint]\nselect = ["E", "F"]\n\n'
                                  '[tool.mypy]\nstrict = true\n')
    write(repo, "CONTRIBUTING.md", "# Beitragen\n\n- Neue Funktionen bekommen einen Test unter tests/.\n"
                                   "- Keine Abhängigkeit ohne Eintrag im Changelog.\n\nText ohne Punkt.\n")
    write(repo, ".editorconfig", "root = true\n\n[*.py]\nindent_size = 4\n")
    git(repo, "init", "-q")
    for i, subject in enumerate(["feat: a", "fix(core): b", "docs: c", "feat!: d", "chore: e", "Merge x"]):
        write(repo, f"f{i}.txt", subject)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", subject)
    return repo


def test_harvest_marks_tool_rules(tmp_path):
    repo = make_repo(tmp_path)
    cands = harvest_mod.harvest(repo, detect_mod.detect(repo, tmp_path / "cfg"))
    by_text = {c["text"]: c for c in cands}
    line = by_text["`line-length = 100`"]
    assert line["source"] == "pyproject.toml [tool.ruff]" and line["checked_by"] == "ruff"
    assert by_text["`select = [\"E\", \"F\"]`"]["checked_by"] == "ruff"
    assert by_text["`strict = true`"]["source"] == "pyproject.toml [tool.mypy]"
    assert by_text["`[*.py] indent_size = 4`"]["checked_by"] == "editorconfig"
    contributing = [c for c in cands if c["source"] == "CONTRIBUTING.md"]
    assert [c["text"] for c in contributing] == ["Neue Funktionen bekommen einen Test unter tests/.",
                                                 "Keine Abhängigkeit ohne Eintrag im Changelog."]
    assert all(c["checked_by"] is None for c in contributing)
    commits = [c for c in cands if c["source"].startswith("git log")]
    assert len(commits) == 1 and "typ(bereich): beschreibung" in commits[0]["text"]
    assert commits[0]["source"] == "git log (5 von 6 Betreffs)"
    assert [c["id"] for c in cands] == [f"c{i}" for i in range(1, len(cands) + 1)]
    assert all("class" not in c for c in cands)


def test_harvest_without_sources_or_git_is_empty(tmp_path):
    repo = tmp_path / "leer"
    repo.mkdir()
    assert harvest_mod.harvest(repo, detect_mod.detect(repo, tmp_path / "cfg")) == []


def test_harvest_main_writes_candidates_json(tmp_path):
    repo = make_repo(tmp_path)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    detect_script = REPO_ROOT / "skills" / "setup-repo" / "scripts" / "detect_repo.py"
    subprocess.run([sys.executable, str(detect_script), "--repo", str(repo), "--config-dir", str(cfg)],
                   check=True, capture_output=True, timeout=30)
    proc = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo)], capture_output=True, text=True,
                          timeout=30)
    assert proc.returncode == 0, proc.stderr
    data = json.loads((repo / ".skills/cache/setup-repo/candidates.json").read_text(encoding="utf-8"))
    assert data["_meta"]["skill"] == "setup-repo" and data["candidates"][0]["id"] == "c1"


def test_harvest_main_without_detect_json_says_so(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    proc = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo)], capture_output=True, text=True,
                          timeout=30)
    assert proc.returncode == 2 and "detect_repo.py" in proc.stderr
    assert not (repo / ".skills").exists()
