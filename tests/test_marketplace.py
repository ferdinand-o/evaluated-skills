"""Repo-Test für .claude-plugin/marketplace.json (Spec 20, plugin-split): vier Plugins mit
Root-Quelle und `skills`-Liste, die je Eintrag die vollständige Menge ist (Claude-Code-Doku,
plugins/manifest-reference: „only those subdirectories load"). Jede Skill unter skills/
steht in genau einer Liste oder mit Grund in .claude-plugin/excluded.json — eine neue
Skill, die niemand einträgt, macht den Test rot, statt still im Plugin zu fehlen. Dazu die
Projekt-Kopien unter .claude/skills/, die scripts/sync_skills.py spiegelt. G2: der Test
meldet, ein Hook fehlt."""

import json
import re
from pathlib import Path

import pytest
from conftest import REPO_ROOT, load_script

MANIFEST = REPO_ROOT / ".claude-plugin" / "marketplace.json"
EXCLUDED_JSON = REPO_ROOT / ".claude-plugin" / "excluded.json"
SKILLS = REPO_ROOT / "skills"

# Zuschnitt aus Spec 20: Name -> defaultEnabled.
PLUGINS = {"evaluated-dev": True, "evaluated-setup": True, "evaluated-ui": False, "evaluated-knowledge": True}

# Plugins nur für Claude Code: ihre Skills dürfen Frontmatter tragen, das claude.ai (Web)
# nicht kennt. Alle anderen müssen sich dort hinzufügen lassen.
CLAUDE_CODE_ONLY_PLUGINS = {"evaluated-setup"}


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _excluded() -> dict:
    data = json.loads(EXCLUDED_JSON.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "excluded.json ist ein JSON-Objekt"
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _entries() -> dict[str, dict]:
    return {e["name"]: e for e in _manifest()["plugins"]}


def _listed() -> dict[str, list[str]]:
    """Skill-Name -> Plugins, in deren Liste er steht."""
    out: dict[str, list[str]] = {}
    for name, entry in _entries().items():
        for path in entry.get("skills", []):
            out.setdefault(Path(path).name, []).append(name)
    return out


def test_manifest_has_required_fields():
    m = _manifest()
    assert m["name"] == "evaluated-skills" and m["owner"]["name"]


def test_plugin_entries_are_fixed():
    entries = _entries()
    assert sorted(entries) == sorted(PLUGINS)
    for name, entry in entries.items():
        assert entry["source"] == "./", name
        assert entry["strict"] is False, f"{name}: ohne plugin.json ist der Eintrag die ganze Definition"
        assert entry.get("defaultEnabled", True) is PLUGINS[name], name
        assert "version" not in entry, f"{name}: mit version blieben Nutzer auf der Cache-Kopie"
        assert "dependencies" not in entry, name
        paths = entry["skills"]
        assert paths and paths == sorted(set(paths)), f"{name}: Liste sortiert, ohne Doppel"
        for path in paths:
            assert path.startswith("./skills/") and ".." not in path, path
            assert (REPO_ROOT / path / "SKILL.md").is_file(), path


def test_every_skill_in_exactly_one_plugin():
    listed, excluded = _listed(), _excluded()
    on_disk = {p.name for p in SKILLS.iterdir() if (p / "SKILL.md").is_file()}
    problems = []
    for name in sorted(on_disk):
        plugins = listed.get(name, [])
        if name in excluded and plugins:
            problems.append(f"{name}: ausgeschlossen und trotzdem in {plugins}")
        elif name not in excluded and len(plugins) != 1:
            problems.append(f"{name}: in {len(plugins)} Plugins {plugins}")
    assert not problems, problems


def test_excluded_json_names_existing_skills_with_reason():
    for name, reason in _excluded().items():
        assert (SKILLS / name / "SKILL.md").is_file(), f"excluded.json nennt {name}, das es nicht gibt"
        assert isinstance(reason, str) and reason.strip(), f"{name}: Grund fehlt"


# Seit Spec 25 auch `${CLAUDE_SKILL_DIR}/../<andere>/`: der Nachbar liegt nur im selben Plugin daneben.
_SKILL_REF = re.compile(r"(?:skills/|/\.\./)([a-z0-9][a-z0-9-]*)/")


def test_no_file_refs_across_plugins():
    """Ein Plugin bringt nur die Ordner seiner eigenen Skills mit; ein Pfad
    `skills/<andere>/…` zeigt ins Leere, wenn die andere in einem anderen Plugin liegt
    oder ausgeschlossen ist (Spec 20, „Kein Dateiverweis über eine Plugin-Grenze")."""
    listed, excluded = _listed(), _excluded()
    findings = []
    for name, plugins in sorted(listed.items()):
        for path in sorted((SKILLS / name).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for other in _SKILL_REF.findall(line):
                    if other == name:
                        continue
                    if other in excluded or (other in listed and listed[other] != plugins):
                        findings.append(f"{path.relative_to(REPO_ROOT)}:{lineno} -> {other}/")
    assert not findings, findings


def test_project_copies_match_originals():
    sync = load_script("scripts/sync_skills.py")
    assert sync.PROJECT_SKILLS == sorted(set(sync.PROJECT_SKILLS))
    for name in sync.PROJECT_SKILLS:
        assert (SKILLS / name / "SKILL.md").is_file(), name
    drift = sync.sync(REPO_ROOT, check=True)
    assert drift == [], "Projekt-Kopie weicht ab, python scripts/sync_skills.py: " + ", ".join(
        f"{s} {p}" for s, p in drift[:10])


def test_repo_disables_cc_dev_for_project_copies():
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["enabledPlugins"]["evaluated-dev@evaluated-skills"] is False


def test_no_plugin_json_that_would_conflict_with_strict_false():
    """strict: false plus eine plugin.json mit Komponenten wäre ein Konflikt und das
    Plugin lüde nicht (Doku, „Strict mode")."""
    plugin_json = REPO_ROOT / ".claude-plugin" / "plugin.json"
    if plugin_json.is_file():
        data = json.loads(plugin_json.read_text(encoding="utf-8"))
        for key in ("skills", "commands", "agents", "hooks", "mcpServers", "lspServers", "outputStyles"):
            assert key not in data, f"plugin.json deklariert {key} — Konflikt mit strict: false"


def test_descriptions_carry_no_angle_bracket_tags():
    """Der Plugin-Import von claude.ai (Web) lehnt `<…>` in der Description ab und lässt die
    Skill still weg; gemessen am 2026-09-23 an learning-coach und verified-research, die als
    einzige `<Thema>` in der Description trugen. Im Body stören die Platzhalter nicht."""
    offenders = []
    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        head = skill_md.read_text(encoding="utf-8").split("\n---", 2)[0]
        desc = head.split("description:", 1)[1] if "description:" in head else ""
        if re.search(r"<[A-Za-z][^>]*>", desc):
            offenders.append(skill_md.parent.name)
    assert not offenders, f"<…> in der Description, claude.ai lädt die Skill nicht: {offenders}"


# Regeln des Skill-Uploads von claude.ai, wie sie quick_validate.py von skill-creator prüft.
CLAUDE_AI_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}


def _claude_ai_findings(skill_dir: Path) -> list[str]:
    import yaml
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return ["kein Frontmatter"]
    data = yaml.safe_load(match.group(1))
    findings = []
    if set(data) - CLAUDE_AI_KEYS:
        findings.append(f"Schlüssel {sorted(set(data) - CLAUDE_AI_KEYS)}")
    name, desc = str(data.get("name", "")), str(data.get("description", ""))
    if not re.fullmatch(r"[a-z0-9-]{1,64}", name) or "anthropic" in name or "claude" in name:
        findings.append(f"name {name!r}")
    if "<" in desc or ">" in desc:
        findings.append("< oder > in der Description")
    if not desc or len(desc) > 1024:
        findings.append(f"Description {len(desc)} Zeichen")
    nested = [p for p in skill_dir.rglob("SKILL.md") if p != skill_dir / "SKILL.md"
              and "__pycache__" not in p.parts and p.relative_to(skill_dir).parts[0] != "evals"]
    if nested:
        findings.append(f"weitere SKILL.md {[str(p.relative_to(skill_dir)) for p in nested]}")
    return findings


def test_web_plugins_pass_claude_ai_upload_rules():
    """claude.ai (Web) lehnt ein Plugin ab, wenn eine seiner Skills die Upload-Regeln
    verletzt. Am 2026-10-14 war evaluated-dev deshalb nicht hinzufügbar: setup-repo und setup-user
    tragen `disable-model-invocation`, das nur Claude Code kennt. Seitdem liegen sie in
    evaluated-setup, und dieser Test hält die übrigen Plugins importierbar."""
    findings = []
    for name, entry in _entries().items():
        if name in CLAUDE_CODE_ONLY_PLUGINS:
            continue
        for path in entry["skills"]:
            for f in _claude_ai_findings(REPO_ROOT / path):
                findings.append(f"{name}/{Path(path).name}: {f}")
    assert not findings, findings


def test_no_nested_plugin_json_anywhere_in_the_repo():
    """claude.ai (Web) durchsucht bei `source: "./"` das ganze Repo und lehnt jedes Plugin
    ab, sobald irgendwo eine `.claude-plugin/plugin.json` liegt, die nicht an der Wurzel
    steht (gemeldet am 2026-10-15: „found nested: evals/fixtures/su-plugins/…/plugin.json").
    Fixtures, die einen Plugin-Cache nachbilden, kommen ohne diese Datei aus."""
    import subprocess
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, text=True,
                             check=True).stdout.split("\0")
    nested = [p for p in tracked if p.endswith(".claude-plugin/plugin.json") and p != ".claude-plugin/plugin.json"]
    assert not nested, f"verschachtelte plugin.json, claude.ai lehnt alle Plugins ab: {nested}"


def test_no_skill_folder_carries_a_second_skill_md():
    """Gilt für jeden Ordner unter skills/, nicht nur für gelistete: Der Web-Loader las am
    2026-09-23 alle Ordner, unabhängig von der `skills`-Liste (known-limits, Marketplace)."""
    nested = [str(p.relative_to(REPO_ROOT)) for p in sorted(SKILLS.glob("*/**/SKILL.md"))
              if p.parent.parent != SKILLS and "__pycache__" not in p.parts]
    assert not nested, f"claude.ai nimmt je Skill genau eine SKILL.md an: {nested}"


def test_claude_code_only_skills_live_in_claude_code_only_plugins():
    lint = load_script("skills/skill-forge/scripts/lint_skill.py")
    listed = _listed()
    for skill in lint.CLAUDE_CODE_ONLY:
        assert set(listed.get(skill, [])) <= CLAUDE_CODE_ONLY_PLUGINS, (skill, listed.get(skill))
    for plugin in CLAUDE_CODE_ONLY_PLUGINS:
        assert "claude.ai" in _entries()[plugin]["description"], "Description sagt, dass es nicht ins Web geht"


# --- scripts/sync_skills.py (Spec 20) ---------------------------------------------


@pytest.fixture
def sync_mod():
    return load_script("scripts/sync_skills.py")


def _skill(root: Path, name: str, description: str = "Use when testing.", extra: dict | None = None) -> Path:
    d = root / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n", encoding="utf-8")
    for rel, text in (extra or {}).items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text, encoding="utf-8")
    return d


def _write_manifest(root: Path, plugins: list[dict], excluded: dict | None = None) -> None:
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"name": "t", "owner": {"name": "t"}, "plugins": plugins}), encoding="utf-8")
    if excluded is not None:
        (root / ".claude-plugin" / "excluded.json").write_text(json.dumps(excluded), encoding="utf-8")


def test_sync_mirrors_and_ignores_pycache(tmp_path, sync_mod, monkeypatch):
    monkeypatch.setattr(sync_mod, "PROJECT_SKILLS", ["alpha"])
    src = _skill(tmp_path, "alpha", extra={"references/a.md": "eins\n", "scripts/x.py": "print(1)\n"})
    (src / "scripts" / "__pycache__").mkdir()
    (src / "scripts" / "__pycache__" / "x.cpython-313.pyc").write_bytes(b"\x00")
    (src / "scripts" / "y.pyc").write_bytes(b"\x00")

    sync_mod.sync(tmp_path, check=False)
    dst = tmp_path / ".claude" / "skills" / "alpha"
    assert (dst / "references" / "a.md").read_text(encoding="utf-8") == "eins\n"
    assert not (dst / "scripts" / "__pycache__").exists()
    assert not (dst / "scripts" / "y.pyc").exists()
    assert sync_mod.sync(tmp_path, check=True) == []

    (src / "references" / "a.md").write_text("zwei\n", encoding="utf-8")
    (src / "references" / "b.md").write_text("neu\n", encoding="utf-8")
    (src / "scripts" / "x.py").unlink()
    (dst / "stray.md").write_text("weg\n", encoding="utf-8")
    findings = dict((path, status) for status, path in sync_mod.sync(tmp_path, check=True))
    assert findings == {
        "alpha/references/a.md": "abweichend",
        "alpha/references/b.md": "fehlend",
        "alpha/scripts/x.py": "überzählig",
        "alpha/stray.md": "überzählig",
    }
    assert (dst / "scripts" / "x.py").exists(), "check schreibt nichts"

    sync_mod.sync(tmp_path, check=False)
    assert sync_mod.sync(tmp_path, check=True) == []
    assert not (dst / "scripts" / "x.py").exists() and not (dst / "stray.md").exists()


def test_sync_reports_installed_skill_outside_table(tmp_path, sync_mod, monkeypatch):
    monkeypatch.setattr(sync_mod, "PROJECT_SKILLS", ["alpha"])
    _skill(tmp_path, "alpha")
    sync_mod.sync(tmp_path, check=False)
    (tmp_path / ".claude" / "skills" / "beta").mkdir()
    (tmp_path / ".claude" / "skills" / "beta" / "SKILL.md").write_text("x", encoding="utf-8")
    assert ("überzählig", "beta/SKILL.md") in sync_mod.sync(tmp_path, check=True)
    sync_mod.sync(tmp_path, check=False)
    assert not (tmp_path / ".claude" / "skills" / "beta").exists()


def test_superpowers_report_counts_descriptions(tmp_path, sync_mod):
    _skill(tmp_path, "on-skill", "Use when x. Not for y (use superpowers:writing-plans) or z (superpowers:tdd).")
    _skill(tmp_path, "off-skill", "Use when x (use superpowers:writing-plans).")
    _skill(tmp_path, "gone-skill", "Use when x (use superpowers:writing-skills).")
    _skill(tmp_path, "clean-skill", "Use when x.", extra={"references/r.md": "superpowers:writing-plans\n"})
    _write_manifest(tmp_path, [
        {"name": "p-on", "source": "./", "skills": ["./skills/clean-skill", "./skills/on-skill"]},
        {"name": "p-off", "source": "./", "defaultEnabled": False, "skills": ["./skills/off-skill"]},
    ], excluded={"gone-skill": "Grund"})
    report = sync_mod.superpowers_report(tmp_path)
    assert report == {"p-on": {"on-skill": 2}}


@pytest.mark.parametrize("manifest_text, excluded_text", [
    ("{kaputt", None),
    (json.dumps({"plugins": []}), "[1, 2]"),
])
def test_report_exits_2_on_broken_config(tmp_path, sync_mod, capsys, manifest_text, excluded_text):
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin" / "marketplace.json").write_text(manifest_text, encoding="utf-8")
    if excluded_text is not None:
        (tmp_path / ".claude-plugin" / "excluded.json").write_text(excluded_text, encoding="utf-8")
    assert sync_mod.main(["--report", "--repo", str(tmp_path)]) == 2
    assert capsys.readouterr().err.strip()


def test_check_exit_codes(tmp_path, sync_mod, monkeypatch):
    monkeypatch.setattr(sync_mod, "PROJECT_SKILLS", ["alpha"])
    _skill(tmp_path, "alpha")
    assert sync_mod.main(["--check", "--repo", str(tmp_path)]) == 1
    assert sync_mod.main(["--repo", str(tmp_path)]) == 0
    assert sync_mod.main(["--check", "--repo", str(tmp_path)]) == 0


ROUTING_TARGETS = ("superpowers:writing-plans", "superpowers:subagent-driven-development",
                   "test-driven-development")
# Herkunft, kein Routing-Ziel (Spec 23, „Bewusst bleiben").
ROUTING_TARGET_ALLOWED = {
    "skills/impl-plan/references/reviewer-prompt.md",
    # test-first grenzt sich gegen die TDD-Skill von superpowers ab, die es ersetzt (Spec 24).
    "skills/test-first/SKILL.md",
    # Die Lückentabelle nennt die superpowers-Skills als Daten (Spec 21 B).
    "skills/setup-user/references/superpowers-gaps.json",
}


def test_no_superpowers_routing_targets():
    """Spec 23 und 24: Keine Description eines aktiven Plugins verweist auf superpowers,
    und unter skills/ zeigt nichts mehr auf writing-plans, subagent-driven-development
    oder test-driven-development — work-plan, das eingebaute Agent-Werkzeug und
    test-first sind die Ziele."""
    sync = load_script("scripts/sync_skills.py")
    report = sync.superpowers_report(REPO_ROOT)
    assert sum(n for skills in report.values() for n in skills.values()) == 0, report
    hits = []
    for path in sorted((REPO_ROOT / "skills").rglob("*")):
        if path.suffix not in (".md", ".py", ".json") or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        if rel not in ROUTING_TARGET_ALLOWED and any(t in text for t in ROUTING_TARGETS):
            hits.append(rel)
    assert hits == [], hits


def test_cross_plugin_check_sees_skill_dir_neighbors():
    """Die Erweiterung greift: ein `../<x>/` in einem fremden Plugin wäre ein Befund."""
    assert _SKILL_REF.findall('python "${CLAUDE_SKILL_DIR}/../subagent-dev/scripts/plan_to_tasks.py"') == ["subagent-dev"]
    assert _SKILL_REF.findall("skills/explain/references/x.md") == ["explain"]
