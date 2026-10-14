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
