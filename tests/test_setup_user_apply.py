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
