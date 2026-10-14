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
