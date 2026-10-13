"""Form der Ziel-Assets von setup-repo (Spec 22, Abschnitt C): Ledger-Gerüst, immer
geladene Zielregel, Hook-Fragment für beide Ereignisse."""

import json

from conftest import REPO_ROOT
from evalkit.assertions import ARTIFACT_HEADER_RE

ASSETS = REPO_ROOT / "skills" / "setup-repo" / "assets"
SCRIPT = "$CLAUDE_PROJECT_DIR/.claude/hooks/goal_scope.py"


def test_goal_assets_shape():
    ledger = (ASSETS / "goals.md").read_text(encoding="utf-8").splitlines()
    m = ARTIFACT_HEADER_RE.match(ledger[0])
    assert m and m.group("skill") == "setup-repo" and m.group("schema") == "1"
    text = "\n".join(ledger)
    for heading, columns in (("## Aktiv", "| id | Ziel | Fertig wenn | Bereich | seit |"),
                             ("## Kandidaten", "| id | Kandidat | entdeckt bei | Grund | am |"),
                             ("## Erledigt", "| id | Ziel | Beleg | am |")):
        section = text[text.index(heading):].split("\n## ")[0]
        table = [l for l in section.splitlines()[1:] if l.startswith("|")]
        assert table[0] == columns and set(table[1]) <= set("|- ") and len(table) == 2, heading

    rule = (ASSETS / "rules" / "goals.md").read_text(encoding="utf-8").splitlines()
    assert len(rule) <= 25 and ARTIFACT_HEADER_RE.match(rule[0])
    assert not rule[0].startswith("---")
    body = "\n".join(rule)
    for cls in ("Vom Nutzer verlangt", "Teil des Ziels", "Trivial", "Neues Ziel"):
        assert cls in body, cls
    assert "[setup-repo]" in body and "docs/goals.md" in body

    hooks = json.loads((ASSETS / "hooks" / "goal-scope.json").read_text(encoding="utf-8"))["hooks"]
    assert set(hooks) == {"UserPromptSubmit", "Stop"}
    for event, entries in hooks.items():
        (entry,) = entries
        (hook,) = entry["hooks"]
        assert hook["type"] == "command" and SCRIPT in hook["command"], event
        assert hook["command"].startswith("command -v python3 >/dev/null 2>&1 && exec python3 ")
