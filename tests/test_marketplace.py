"""Repo-Test für .claude-plugin/marketplace.json: ein Plugin für die Sammlung, dessen
`skills`-Liste bei `source: "./"` die vollständige Menge ist (Claude-Code-Doku,
plugin-marketplaces, „Advanced plugin entries"). Jede Skill unter skills/ ist gelistet
oder steht ausdrücklich in EXCLUDED — eine neue Skill, die niemand einträgt, macht den
Test rot, statt still im Plugin zu fehlen. G2: der Test meldet, ein Hook fehlt."""

import json
from pathlib import Path

from conftest import REPO_ROOT

MANIFEST = REPO_ROOT / ".claude-plugin" / "marketplace.json"
SKILLS = REPO_ROOT / "skills"

# Skills, die bewusst nicht im Plugin sind, mit Grund.
EXCLUDED = {
    "cad-parts": "braucht einen stl-cad-server als MCP-Server; ohne ihn ist die Skill nutzlos",
}


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _entry() -> dict:
    plugins = _manifest()["plugins"]
    assert len(plugins) == 1, "ein Plugin für die ganze Sammlung"
    return plugins[0]


def test_manifest_has_required_fields():
    m = _manifest()
    assert m["name"] == "cc-skills" and m["owner"]["name"]
    entry = _entry()
    assert entry["name"] == "cc-skills" and entry["source"] == "./"
    assert entry["strict"] is False, "ohne plugin.json ist der Marketplace-Eintrag die ganze Definition"


def test_every_listed_skill_exists_and_is_inside_skills():
    for path in _entry()["skills"]:
        assert path.startswith("./skills/") and ".." not in path, path
        assert (REPO_ROOT / path / "SKILL.md").is_file(), path


def test_every_skill_directory_is_listed_or_excluded():
    listed = {Path(p).name for p in _entry()["skills"]}
    on_disk = {p.name for p in SKILLS.iterdir() if (p / "SKILL.md").is_file()}
    missing = on_disk - listed - set(EXCLUDED)
    assert not missing, f"nicht im Plugin und nicht in EXCLUDED: {sorted(missing)}"
    assert not (listed & set(EXCLUDED)), "eine ausgeschlossene Skill steht in der Liste"
    assert set(EXCLUDED) <= on_disk, "EXCLUDED nennt eine Skill, die es nicht gibt"


def test_list_is_sorted_without_duplicates():
    paths = _entry()["skills"]
    assert paths == sorted(set(paths))


def test_no_plugin_json_that_would_conflict_with_strict_false():
    """strict: false plus eine plugin.json mit Komponenten wäre ein Konflikt und das
    Plugin lüde nicht (Doku, „Strict mode")."""
    plugin_json = REPO_ROOT / ".claude-plugin" / "plugin.json"
    if plugin_json.is_file():
        data = json.loads(plugin_json.read_text(encoding="utf-8"))
        for key in ("skills", "commands", "agents", "hooks", "mcpServers", "lspServers", "outputStyles"):
            assert key not in data, f"plugin.json deklariert {key} — Konflikt mit strict: false"
