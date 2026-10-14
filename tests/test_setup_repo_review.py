"""Tests für den Ziel-Reviewer von setup-repo (Spec 22, Abschnitt D): Prüfpunkte mit
Quelle, das Agent-Asset und seine Operation im Plan."""

import re

from conftest import REPO_ROOT

REVIEW = REPO_ROOT / "skills" / "setup-repo" / "references" / "review"
CHECKPOINT_RE = re.compile(r"^- \*\*(?P<id>[a-z0-9-]+)\*\* — (?P<text>.+?) Quelle: (?P<source>\S.*)$")


def checkpoints(name):
    text = (REVIEW / f"{name}.md").read_text(encoding="utf-8")
    section = text.split("## Prüfpunkte", 1)[1].split("\n## ", 1)[0]
    lines = [line for line in section.splitlines() if line.startswith("- ")]
    return text, lines


def test_checkpoints_have_sources():
    seen = set()
    for name in ("python", "typescript", "generic"):
        _, lines = checkpoints(name)
        assert lines, name
        for line in lines:
            m = CHECKPOINT_RE.match(line)
            assert m, f"{name}: Prüfpunkt ohne ID, Text oder Quelle: {line!r}"
            assert m["id"] not in seen, m["id"]
            seen.add(m["id"])
    text, lines = checkpoints("delphi")
    assert lines == []
    assert "vom Nutzer" in text


AGENT = REPO_ROOT / "skills" / "setup-repo" / "assets" / "agents" / "reviewer.md"
HEADER_RE = re.compile(r"^<!-- skill: setup-repo \| schema: 1 \| generated: [^>]+ -->$")


def test_reviewer_asset_shape():
    """Frontmatter für Claude Code in Zeile 1, Kopfzeile in der ersten Zeile danach
    (Ausnahme in docs/artifact-header.md), ein Platzhalter für die Prüfpunkte."""
    text = AGENT.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    front = dict(line.split(": ", 1) for line in lines[1:end])
    assert front["name"] == "reviewer"
    assert front["description"] and "/code-review" in front["description"]
    assert {t.strip() for t in front["tools"].split(",")} == {"Read", "Grep", "Glob", "Bash"}
    assert HEADER_RE.match(lines[end + 1])
    assert text.count("{{checkpoints}}") == 1
    assert "Failure-Szenario" in text and "ungeprüft" in text
    assert "skills/setup-repo/assets/agents/reviewer.md" in (REPO_ROOT / "docs" / "artifact-header.md").read_text(encoding="utf-8")


def _plan(repo, cfg, **options):
    from conftest import load_script
    detect_mod = load_script("skills/setup-repo/scripts/detect_repo.py")
    harvest_mod = load_script("skills/setup-repo/scripts/harvest_rules.py")
    plan_mod = load_script("skills/setup-repo/scripts/plan_repo.py")
    detect = detect_mod.detect(repo, cfg)
    return plan_mod, plan_mod.build_plan(repo, detect, harvest_mod.harvest(repo, detect), options)


def _write(root, rel, text="x\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _reviewer_op(block):
    return next((op for op in block["operations"] if op["path"] == ".claude/agents/reviewer.md"), None)


def test_plan_installs_reviewer_with_stack_checkpoints(tmp_path):
    repo = tmp_path / "py"
    _write(repo, "src/app.py", "def run():\n    return 1\n")
    plan_mod, block = _plan(repo, tmp_path / "cfg")
    op = _reviewer_op(block)
    assert op and op["action"] == "create"
    text = op["content"]
    assert "{{checkpoints}}" not in text
    assert "py-test-for-public" in text and "gen-done-when" in text and "ts-test-for-export" not in text
    assert text.splitlines()[0] == "---"
    assert block["options"]["reviewer"] is True
    assert ".claude/agents/reviewer.md" in plan_mod.render_plan(block)


def test_reviewer_for_delphi_and_unknown_stacks(tmp_path):
    repo = tmp_path / "delphi"
    _write(repo, "App.dproj", "<Project/>\n")
    _write(repo, "Main.pas", "unit Main;\n")
    _, block = _plan(repo, tmp_path / "cfg")
    text = _reviewer_op(block)["content"]
    assert "ungeprüft — keine Prüfpunkte für delphi" in text and "gen-scope" in text

    repo = tmp_path / "leer"
    _write(repo, "README.md", "# leer\n")
    _, block = _plan(repo, tmp_path / "cfg")
    text = _reviewer_op(block)["content"]
    assert "Stack nicht erkannt" in text and "gen-verification" in text and "py-" not in text

    repo = tmp_path / "ts"
    _write(repo, "src/a.ts", "export const a = 1;\n")
    _write(repo, "src/b.js", "module.exports = 1;\n")
    _, block = _plan(repo, tmp_path / "cfg")
    assert _reviewer_op(block)["content"].count("ts-test-for-export") == 1


def test_existing_reviewer_and_opt_out_get_no_operation(tmp_path):
    repo = tmp_path / "py"
    _write(repo, "src/app.py", "def run():\n    return 1\n")
    _write(repo, ".claude/agents/reviewer.md", "---\nname: reviewer\n---\neigener\n")
    plan_mod, block = _plan(repo, tmp_path / "cfg")
    assert _reviewer_op(block) is None
    assert "vorhanden, bleibt" in plan_mod.render_plan(block)
    (repo / ".claude" / "agents" / "reviewer.md").unlink()
    _, block = _plan(repo, tmp_path / "cfg", reviewer=False)
    assert _reviewer_op(block) is None and block["options"]["reviewer"] is False


def test_goal_rule_names_the_reviewer():
    text = (REPO_ROOT / "skills" / "setup-repo" / "assets" / "rules" / "goals.md").read_text(encoding="utf-8")
    assert "reviewer" in text and len(text.splitlines()) <= 25
