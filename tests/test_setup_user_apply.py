"""Tests für inspect_config.py und apply_config.py von setup-user (Spec 21, Abschnitt A).

Alles läuft in tmp_path; die Assets kommen aus einem Temp-Ordner, den die Tests über
die Modulkonstante ASSETS einsetzen, damit kein Test vom echten Statusline-Asset abhängt.
Kein Test berührt ~/.claude."""

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest
from conftest import load_script

inspect = load_script("skills/setup-user/scripts/inspect_config.py")

STUB_STATUSLINE = "#!/usr/bin/env python3\n# setup-user: statusline\nprint('stub')\n"
STUB_HINT = "#!/usr/bin/env python3\n# setup-user: context_hint\nprint('')\n"


def make_assets(root: Path, known: list[str] | None = None) -> Path:
    a = root / "assets"
    (a / "runtime").mkdir(parents=True)
    (a / "rules").mkdir()
    (a / "settings").mkdir()
    (a / "runtime" / "statusline.py").write_text(STUB_STATUSLINE, encoding="utf-8")
    (a / "runtime" / "context_hint.py").write_text(STUB_HINT, encoding="utf-8")
    (a / "runtime" / "known-statusline-hashes.json").write_text(
        json.dumps({"_meta": {}, "sha256": known or []}), encoding="utf-8")
    (a / "CLAUDE.md.tmpl").write_text(
        "<!-- skill: setup-user | schema: 1 | generated: assets/CLAUDE.md.tmpl -->\n# Profil\n\nSprache: {{language}}\n",
        encoding="utf-8")
    for name in ("communication", "verification", "context", "git"):
        (a / "rules" / f"{name}.md").write_text(
            f"<!-- skill: setup-user | schema: 1 | generated: assets/rules/{name}.md -->\n# {name}\n\nTon: {{{{tone}}}}\n",
            encoding="utf-8")
    (a / "settings" / "context-hint.json").write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [
        {"type": "command", "command": "<python> \"<config-dir>/setup-user/runtime/context_hint.py\" || true"}]}]}}),
        encoding="utf-8")
    return a


@pytest.fixture
def assets(tmp_path, monkeypatch):
    a = make_assets(tmp_path / "skill")
    monkeypatch.setattr(inspect, "ASSETS", a)
    return a


def cfg_with(tmp_path: Path, name: str, settings: dict | None = None, files: dict | None = None) -> Path:
    cfg = tmp_path / name
    cfg.mkdir(parents=True)
    if settings is not None:
        (cfg / "settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    for rel, text in (files or {}).items():
        (cfg / rel).parent.mkdir(parents=True, exist_ok=True)
        (cfg / rel).write_text(text, encoding="utf-8")
    return cfg


def snapshot(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


# --- inspect_config.py --------------------------------------------------------------

def test_plan_is_path_and_eol_neutral(tmp_path, assets):
    hashes = []
    for name, eol in (("eins", "\n"), ("zwei/tiefer", "\r\n")):
        cfg = tmp_path / name
        cfg.mkdir(parents=True)
        own = cfg / "status.py"
        own.write_text(STUB_STATUSLINE, encoding="utf-8")
        settings = {"statusLine": {"type": "command", "command": f'python3 "{cfg}/status.py"'}, "spinnerTipsEnabled": False}
        (cfg / "settings.json").write_bytes(json.dumps(settings, indent=2).replace("\n", eol).encode("utf-8"))
        block = inspect.build_plan(cfg, {}, None)
        assert block["hash"] == inspect.plan_hash(block)
        hashes.append(block["hash"])
    assert hashes[0] == hashes[1]
    text_a = inspect.render_plan(block, tmp_path / "eins")
    text_b = inspect.render_plan(block, tmp_path / "zwei" / "tiefer")
    assert text_a.splitlines()[0] != text_b.splitlines()[0], "Kopfzeile nennt das Ziel, liegt aber außerhalb des Hashes"


@pytest.mark.parametrize("case, expected", [
    ("own-marker", "own"), ("own-hash", "own"), ("none", "none"), ("foreign", "foreign")])
def test_plan_classifies_statusline(tmp_path, monkeypatch, case, expected):
    old = "print('meine alte statusline')\n"
    a = make_assets(tmp_path / "skill", known=[hashlib.sha256(old.encode()).hexdigest()])
    monkeypatch.setattr(inspect, "ASSETS", a)
    files, settings = {}, {}
    if case == "own-marker":
        files["s.py"] = STUB_STATUSLINE
    elif case == "own-hash":
        files["s.py"] = old.replace("\n", "\r\n")
    elif case == "foreign":
        files["s.py"] = "print('fremd')\n"
    cfg = cfg_with(tmp_path, "cfg", None, files)
    if files:
        settings = {"statusLine": {"type": "command", "command": f"python3 {cfg}/s.py"}}
    (cfg / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    block = inspect.build_plan(cfg, {}, None)
    assert block["statusline"]["kind"] == expected
    paths = {op["path"] for op in block["operations"]}
    assert "setup-user/runtime/context_hint.py" in paths
    assert ("setup-user/runtime/statusline.py" in paths) is (expected != "foreign")
    text = inspect.render_plan(block, cfg)
    assert ("Kontext-Hinweise nicht verfügbar" in text) is (expected == "foreign")


def test_plan_writes_only_plan_md(tmp_path, assets, capsys):
    cfg = cfg_with(tmp_path, "cfg", {"spinnerTipsEnabled": False})
    before = snapshot(cfg)
    assert inspect.main(["--config-dir", str(cfg)]) == 0
    after = snapshot(cfg)
    assert set(after) - set(before) == {"setup-user/plan.md"}
    assert all(after[k] == v for k, v in before.items())
    out = capsys.readouterr().out
    assert out.splitlines()[0] == f"Ziel: {cfg.resolve()}"
    text = (cfg / "setup-user" / "plan.md").read_text(encoding="utf-8")
    assert text.startswith("<!-- skill: setup-user | schema: 1 | generated: ")
    assert text.count("```json setup-user-plan") == 1


def test_plan_resolves_python(tmp_path, assets):
    cfg = cfg_with(tmp_path, "a", {})
    assert inspect.build_plan(cfg, {}, None)["python"] == "python3"
    assert inspect.build_plan(cfg, {}, "py -3")["python"] == "py -3"
    own = cfg_with(tmp_path, "b", None, {"s.py": STUB_STATUSLINE})
    (own / "settings.json").write_text(json.dumps({"statusLine": {"command": f'python "{own}/s.py"'}}), encoding="utf-8")
    block = inspect.build_plan(own, {}, "py -3")
    assert block["python"] == "python", "das vorhandene Kommando gewinnt"
    hook = json.dumps(block["operations"])
    assert "python \\\"<config-dir>/setup-user/runtime/context_hint.py\\\" || true" in hook


def test_plan_answers_and_existing_files(tmp_path, assets):
    cfg = cfg_with(tmp_path, "cfg", {}, {"CLAUDE.md": "# meins\n", "rules/git.md": "# meins\n"})
    block = inspect.build_plan(cfg, {"language": "Englisch", "unbekannt": 1}, None)
    ops = {op["path"]: op for op in block["operations"]}
    assert "CLAUDE.md" not in ops, "vorhandene CLAUDE.md bekommt nur bestätigte Ergänzungen"
    assert "rules/git.md" not in ops
    assert ops["rules/context.md"]["action"] == "create"
    assert block["answers"]["language"] == "Englisch" and "unbekannt" not in block["answers"]
    assert "CLAUDE.md" not in block["base"], "nicht geplant, also nicht gehasht"
    fresh = cfg_with(tmp_path, "fresh", {})
    claude = {op["path"]: op for op in inspect.build_plan(fresh, {"language": "Englisch"}, None)["operations"]}["CLAUDE.md"]
    assert "Sprache: Englisch" in claude["content"]


def test_plan_refuses_missing_dir_and_broken_settings(tmp_path, assets, capsys):
    assert inspect.main(["--config-dir", str(tmp_path / "fehlt")]) == 2
    cfg = cfg_with(tmp_path, "cfg")
    (cfg / "settings.json").write_text("{kaputt", encoding="utf-8")
    assert inspect.main(["--config-dir", str(cfg)]) == 2
    assert not (cfg / "setup-user" / "plan.md").exists()


# --- apply_config.py ----------------------------------------------------------------

apply = load_script("skills/setup-user/scripts/apply_config.py")


def plan_for(cfg: Path, answers: dict | None = None, python: str | None = None) -> Path:
    block = inspect.build_plan(cfg, answers or {}, python)
    out = cfg / "setup-user" / "plan.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(inspect.render_plan(block, cfg), encoding="utf-8")
    return out


def without_bookkeeping(snap: dict) -> dict:
    return {k: v for k, v in snap.items() if not k.startswith("setup-user/backups/") and k != "setup-user/plan.md"}


def test_hash_functions_agree(tmp_path, assets):
    for name, settings in (("a", {}), ("b", {"spinnerTipsEnabled": False}), ("c", {"statusLine": {"command": "x.sh"}})):
        block = inspect.build_plan(cfg_with(tmp_path, name, settings), {"tone": "ä ö ü"}, None)
        assert apply.canonical_hash(block) == inspect.plan_hash(block) == block["hash"]


def test_apply_merges_and_substitutes_config_dir(tmp_path, assets):
    cfg = cfg_with(tmp_path, "cfg", {"spinnerTipsEnabled": False})
    result = apply.apply_plan(plan_for(cfg), cfg)
    settings = json.loads((cfg / "settings.json").read_text(encoding="utf-8"))
    posix = cfg.resolve().as_posix()
    assert settings["spinnerTipsEnabled"] is False
    assert settings["statusLine"] == {"type": "command", "command": f'python3 "{posix}/setup-user/runtime/statusline.py"'}
    hook = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    assert hook == f'python3 "{posix}/setup-user/runtime/context_hint.py" || true'
    assert (cfg / "setup-user" / "runtime" / "context_hint.py").read_text(encoding="utf-8") == STUB_HINT
    assert (cfg / "CLAUDE.md").read_text(encoding="utf-8").startswith("<!-- skill: setup-user")
    assert json.loads((cfg / "setup-user" / "thresholds.json").read_text(encoding="utf-8"))["_meta"]["skill"] == "setup-user"
    assert result["backup"] is not None
    assert (Path(result["backup"]) / "settings.json").read_text(encoding="utf-8").count("spinnerTipsEnabled") == 1


def test_apply_is_idempotent(tmp_path, assets):
    cfg = cfg_with(tmp_path, "cfg", {"spinnerTipsEnabled": False})
    apply.apply_plan(plan_for(cfg), cfg)
    first = without_bookkeeping(snapshot(cfg))
    apply.apply_plan(plan_for(cfg), cfg)
    assert without_bookkeeping(snapshot(cfg)) == first
    settings = json.loads((cfg / "settings.json").read_text(encoding="utf-8"))
    assert len(settings["hooks"]["UserPromptSubmit"]) == 1, "kein zweiter Hook-Eintrag"


@pytest.mark.parametrize("change", ["plan", "state"])
def test_apply_refuses_changed_plan_or_state(tmp_path, assets, change):
    cfg = cfg_with(tmp_path, "cfg", {"spinnerTipsEnabled": False})
    plan = plan_for(cfg)
    if change == "plan":
        plan.write_text(plan.read_text(encoding="utf-8").replace('"knapp und sachlich"', '"anders"'), encoding="utf-8")
    else:
        (cfg / "settings.json").write_text(json.dumps({"spinnerTipsEnabled": True}), encoding="utf-8")
    before = snapshot(cfg)
    with pytest.raises(apply.ApplyError):
        apply.apply_plan(plan, cfg)
    assert snapshot(cfg) == before


def test_apply_requires_explicit_existing_config_dir(tmp_path, assets, monkeypatch, capsys):
    cfg = cfg_with(tmp_path, "cfg", {})
    plan = plan_for(cfg)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    assert apply.main(["--plan", str(plan)]) == 2, "$CLAUDE_CONFIG_DIR zählt nicht als ausdrücklich"
    assert apply.main(["--plan", str(plan), "--config-dir", str(tmp_path / "fehlt")]) == 2
    assert not (tmp_path / "fehlt").exists()
    assert not (cfg / "CLAUDE.md").exists()
    assert apply.main(["--plan", str(plan), "--config-dir", str(cfg)]) == 0


def test_apply_writes_settings_last(tmp_path, assets):
    cfg = cfg_with(tmp_path, "cfg", {"spinnerTipsEnabled": False})
    plan = plan_for(cfg)
    (cfg / "setup-user" / "runtime").write_text("ich bin eine Datei, kein Ordner", encoding="utf-8")
    before = (cfg / "settings.json").read_bytes()
    with pytest.raises(apply.ApplyError):
        apply.apply_plan(plan, cfg)
    assert (cfg / "settings.json").read_bytes() == before


def test_apply_keeps_foreign_keys_and_statusline_options(tmp_path, assets):
    foreign_hook = {"hooks": [{"type": "command", "command": "echo fremd"}]}
    settings = {
        "model": "opus",
        "statusLine": {"type": "command", "command": "python3 old.py", "padding": 2, "refreshInterval": 5},
        "hooks": {"UserPromptSubmit": [foreign_hook], "Stop": [{"hooks": [{"type": "command", "command": "x"}]}]},
    }
    cfg = cfg_with(tmp_path, "cfg", settings, {"old.py": STUB_STATUSLINE})
    settings["statusLine"]["command"] = f"python3 {cfg}/old.py"
    (cfg / "settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    result = apply.apply_plan(plan_for(cfg), cfg)
    apply.apply_plan(plan_for(cfg), cfg)
    after = json.loads((cfg / "settings.json").read_text(encoding="utf-8"))
    assert after["model"] == "opus" and after["hooks"]["Stop"] == settings["hooks"]["Stop"]
    assert after["statusLine"]["padding"] == 2 and after["statusLine"]["refreshInterval"] == 5
    assert after["statusLine"]["command"].endswith('setup-user/runtime/statusline.py"')
    groups = after["hooks"]["UserPromptSubmit"]
    assert groups[0] == foreign_hook and len(groups) == 2
    assert json.loads((Path(result["backup"]) / "settings.json").read_text(encoding="utf-8")) == settings
    text = (cfg / "settings.json").read_text(encoding="utf-8")
    assert text.endswith("\n") and "\r" not in text and text.startswith('{\n  "model"')


# --- Plugin-Profil (Abschnitt B) -------------------------------------------------------

def _profile(block):
    return {p["id"]: p for p in block["plugins"]["profile"]}


def _settings_patch(block):
    return next(op["patch"] for op in block["operations"] if op["path"] == "settings.json")


def test_profile_keeps_explicit_user_values(tmp_path, assets):
    """Spec 21 B: Ein gesetzter Wert in enabledPlugins bleibt und steht als Konflikt im
    Plan; erst plugins_off macht daraus einen Patch. Ungesetzt → false, sobald die
    Abschaltbedingung erfüllt ist; engineering → false als Annahme."""
    from test_setup_user_route import make_config, skill
    sp, eng = "superpowers@claude-plugins-official", "engineering@knowledge-work"

    # Bedingung nicht erfüllt (evaluated-dev verweist auf superpowers:) → superpowers bleibt, mit Grund
    cfg = make_config(tmp_path / "a")
    block = inspect.build_plan(cfg, {}, "python3")
    profile = _profile(block)
    assert profile[sp]["action"] == "keep" and "(b)" in profile[sp]["reason"]
    assert profile[eng]["action"] == "set" and _settings_patch(block)["enabledPlugins"] == {eng: False}
    assert "evaluated-dev@evaluated-skills" not in profile
    assert str(tmp_path) not in json.dumps(block["plugins"])

    # Bedingung erfüllt, superpowers gesetzt (wie nach `claude plugin install`) → Konflikt
    cfg = make_config(tmp_path / "b")
    skill(tmp_path / "b" / "mkt", "feature-spec", "Use for specs. Not for plans (use work-plan).")
    block = inspect.build_plan(cfg, {}, "python3")
    assert block["plugins"]["condition"]["met"] is True
    assert _profile(block)[sp]["action"] == "conflict"
    assert sp not in _settings_patch(block).get("enabledPlugins", {})
    text = inspect.render_plan(block, cfg)
    assert "## Plugins" in text and "plugins_off" in text and "Konflikt" in text

    # ausdrücklich freigegeben → Patch, und apply mischt enabledPlugins
    out = plan_for(cfg, {"plugins_off": [sp]})
    block = apply.read_block(out)
    assert _settings_patch(block)["enabledPlugins"] == {sp: False, eng: False}
    apply.apply_plan(out, cfg)
    settings = json.loads((cfg / "settings.json").read_text(encoding="utf-8"))
    assert settings["enabledPlugins"] == {sp: False, "evaluated-dev@evaluated-skills": True, eng: False}

    # ungesetzt und Bedingung erfüllt → false ohne Rückfrage; schon false → nichts
    cfg = make_config(tmp_path / "c", enabled={"evaluated-dev@evaluated-skills": True, eng: False})
    skill(tmp_path / "c" / "mkt", "feature-spec", "Use for specs.")
    block = inspect.build_plan(cfg, {}, "python3")
    assert _profile(block)[sp]["action"] == "set" and _profile(block)[eng]["action"] == "none"
    assert _settings_patch(block)["enabledPlugins"] == {sp: False}


def test_profile_counts_rules_planned_in_the_same_plan(tmp_path, assets):
    from test_setup_user_route import make_config, skill
    cfg = make_config(tmp_path, rules=(), enabled={"evaluated-dev@evaluated-skills": True})
    skill(tmp_path / "mkt", "feature-spec", "Use for specs.")
    block = inspect.build_plan(cfg, {}, "python3")
    assert any(op["path"] == "rules/verification.md" for op in block["operations"])
    assert block["plugins"]["condition"]["c"]["ok"] is True
    assert _profile(block)["superpowers@claude-plugins-official"]["action"] == "set"


def test_profile_without_plugins_is_unchecked(tmp_path, assets):
    cfg = cfg_with(tmp_path, "cfg", {})
    block = inspect.build_plan(cfg, {}, "python3")
    assert block["plugins"]["checked"] is False and block["plugins"]["profile"] == []
    assert "enabledPlugins" not in _settings_patch(block)
    assert "ungeprüft" in inspect.render_plan(block, cfg)
