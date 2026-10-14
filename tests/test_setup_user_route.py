"""Tests für skills/setup-user/scripts/route_check.py (Spec 21, Abschnitt B).

Die Fake-Plugins folgen dem Layout, das `claude plugin install` am 2026-10-14 (CLI
2.1.296) in einem Wegwerf-Config-Verzeichnis angelegt hat: `installed_plugins.json` in
Version 2, `installPath` unter `plugins/cache/<marketplace>/<plugin>/<version>`, bei einem
lokalen Marketplace die ganze Repo-Kopie mit `.claude-plugin/marketplace.json`."""

import json

from conftest import load_script

route = load_script("skills/setup-user/scripts/route_check.py")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def skill(root, name, description):
    write(root / "skills" / name / "SKILL.md", f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n")


def plugin_dir(root, name, skills, hooks=None):
    write(root / ".claude-plugin" / "plugin.json", json.dumps({"name": name}))
    for skill_name, description in skills.items():
        skill(root, skill_name, description)
    if hooks is not None:
        write(root / "hooks" / "hooks.json", json.dumps({"hooks": hooks}))
    return root


def make_config(tmp_path, *, enabled=None, rules=("verification.md",), cache_env=None):
    cfg = tmp_path / "cfg"
    cache = (cache_env or cfg / "plugins" / "cache")
    # superpowers aus einem offiziellen Marketplace; installPath veraltet → Cache-Fallback
    plugin_dir(cache / "claude-plugins-official" / "superpowers" / "5.0.0", "superpowers",
               {"brainstorming": "Use when ideas need shaping.", "writing-plans": "Use for plans."},
               hooks={"SessionStart": [{"matcher": "startup|clear|compact",
                                        "hooks": [{"type": "command", "command": "x"}]}]})
    # lokaler Marketplace: ganze Repo-Kopie, Skills über die skills-Liste
    mkt = tmp_path / "mkt"
    write(mkt / ".claude-plugin" / "marketplace.json", json.dumps({"name": "cc-skills", "plugins": [
        {"name": "cc-dev", "source": "./", "defaultEnabled": True,
         "skills": ["./skills/feature-spec", "./skills/subagent-dev"]},
        {"name": "cc-ui", "source": "./", "defaultEnabled": False, "skills": ["./skills/ui-architect"]},
    ]}))
    skill(mkt, "feature-spec", "Use for specs. Not for plans (use superpowers:writing-plans).")
    skill(mkt, "subagent-dev", "Use to dispatch a plan.")
    skill(mkt, "ui-architect", "Use for UI tokens.")
    # engineering aus einem anderen Marketplace, mit einer Skill gleichen Namens wie cc-dev
    plugin_dir(cache / "knowledge-work" / "engineering" / "1.2.0", "engineering",
               {"feature-spec": "Use for engineering specs.", "standup": "Use for standups."})
    write(cfg / "plugins" / "installed_plugins.json", json.dumps({"version": 2, "plugins": {
        "superpowers@claude-plugins-official": [{"scope": "user", "installPath": "/nirgends/superpowers/5.0.0"}],
        "cc-dev@cc-skills": [{"scope": "user", "installPath": str(mkt)}],
        "cc-ui@cc-skills": [{"scope": "user", "installPath": str(mkt)}],
        "engineering@knowledge-work": [{"scope": "user", "installPath": "/nirgends/engineering"}],
    }}))
    # ein synchronisiertes Plugin mit einer Skill, die superpowers auch hat
    plugin_dir(cfg / "plugins" / "synced" / "abc", "notes", {"brainstorming": "Use for notes."})
    settings = {"enabledPlugins": enabled if enabled is not None else {
        "superpowers@claude-plugins-official": True, "cc-dev@cc-skills": True}}
    write(cfg / "settings.json", json.dumps(settings))
    for rule in rules:
        write(cfg / "rules" / rule, "<!-- skill: setup-user | schema: 1 | generated: x -->\n")
    return cfg


def by_id(report):
    return {p["id"]: p for p in report["plugins"]}


def test_route_check_layouts_and_condition(tmp_path):
    cfg = make_config(tmp_path)
    report = route.route_report(cfg)
    plugins = by_id(report)
    assert report["checked"] is True
    assert set(plugins) == {"superpowers@claude-plugins-official", "cc-dev@cc-skills", "cc-ui@cc-skills",
                            "engineering@knowledge-work", "notes@synced"}
    # aktiv: enabledPlugins, sonst defaultEnabled, sonst an
    assert plugins["cc-dev@cc-skills"]["active"] and plugins["cc-dev@cc-skills"]["explicit"] is True
    assert not plugins["cc-ui@cc-skills"]["active"] and plugins["cc-ui@cc-skills"]["explicit"] is None
    assert plugins["engineering@knowledge-work"]["active"]
    # Layouts: Cache-Fallback, lokaler Marketplace mit skills-Liste, synced
    assert plugins["superpowers@claude-plugins-official"]["skills"] == ["brainstorming", "writing-plans"]
    assert plugins["cc-dev@cc-skills"]["skills"] == ["feature-spec", "subagent-dev"]
    assert plugins["notes@synced"]["skills"] == ["brainstorming"]
    # Rollen: engineering nur am Namen, nie ein cc-*
    assert plugins["engineering@knowledge-work"]["role"] == "engineering"
    assert plugins["cc-dev@cc-skills"]["role"] == "cc"
    assert plugins["superpowers@claude-plugins-official"]["role"] == "superpowers"
    # Befunde
    assert plugins["superpowers@claude-plugins-official"]["session_start"] == ["startup|clear|compact"]
    assert plugins["cc-dev@cc-skills"]["superpowers_refs"] == ["feature-spec"]
    collisions = {c["skill"]: c["plugins"] for c in report["collisions"]}
    assert collisions["brainstorming"] == ["notes@synced", "superpowers@claude-plugins-official"]
    assert collisions["feature-spec"] == ["cc-dev@cc-skills", "engineering@knowledge-work"]
    assert "ui-architect" not in collisions          # cc-ui ist aus
    # Abschaltbedingung: (a) ok aus der Lückentabelle, (b) ein Verweis, (c) Regel liegt
    cond = report["condition"]
    assert cond["a"]["ok"] and cond["a"]["gaps"] == []
    assert not cond["b"]["ok"] and cond["b"]["refs"] == ["cc-dev@cc-skills/feature-spec"]
    assert cond["c"]["ok"]
    assert cond["met"] is False

    text = route.render_markdown(report)
    assert text.startswith("## Plugins")
    assert "superpowers · SessionStart-Hook · startup|clear|compact" in text
    assert "Abschaltbedingung: nicht erfüllt" in text
    assert str(tmp_path) not in json.dumps(report) and str(tmp_path) not in text   # keine absoluten Pfade


def test_condition_parts_a_and_c(tmp_path, monkeypatch):
    cfg = make_config(tmp_path, rules=())
    gaps = json.loads(route.GAPS_PATH.read_text(encoding="utf-8"))
    gaps["rows"].append({"superpowers": ["new-thing"], "replacement": "—", "status": "Lücke", "source": "x"})
    fake = write(tmp_path / "gaps.json", json.dumps(gaps))
    monkeypatch.setattr(route, "GAPS_PATH", fake)
    cond = route.route_report(cfg)["condition"]
    assert not cond["a"]["ok"] and cond["a"]["gaps"] == ["new-thing"]
    assert not cond["c"]["ok"] and cond["c"]["missing"] == ["verification.md"]


def test_condition_met_when_superpowers_refs_are_gone(tmp_path):
    cfg = make_config(tmp_path, enabled={"superpowers@claude-plugins-official": True,
                                         "cc-dev@cc-skills": True, "engineering@knowledge-work": False})
    mkt = tmp_path / "mkt"
    skill(mkt, "feature-spec", "Use for specs. Not for plans (use work-plan).")
    report = route.route_report(cfg)
    assert report["condition"]["met"] is True
    assert not by_id(report)["engineering@knowledge-work"]["active"]
    assert "feature-spec" not in {c["skill"] for c in report["collisions"]}   # engineering ist aus
    assert "Abschaltbedingung: erfüllt" in route.render_markdown(report)


def test_cache_dir_from_environment(tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    cfg = make_config(tmp_path, cache_env=elsewhere)
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(elsewhere))
    plugins = by_id(route.route_report(cfg))
    assert plugins["superpowers@claude-plugins-official"]["skills"] == ["brainstorming", "writing-plans"]
    monkeypatch.delenv("CLAUDE_CODE_PLUGIN_CACHE_DIR")
    assert by_id(route.route_report(cfg))["superpowers@claude-plugins-official"]["skills"] == []


def test_unchecked_without_plugins_dir(tmp_path, capsys):
    cfg = tmp_path / "cfg"
    write(cfg / "settings.json", "{}")
    report = route.route_report(cfg)
    assert report["checked"] is False and "plugins" in report["reason"]
    assert "ungeprüft" in route.render_markdown(report)
    assert route.main(["--config-dir", str(cfg), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["checked"] is False
    assert route.main(["--config-dir", str(cfg), "--markdown"]) == 0
    assert capsys.readouterr().out.startswith("## Plugins")
