"""Tests für skills/setup-user/scripts/verify_install.py (Spec 21, Abschnitt A).

Die Prüfung führt nur Befehle aus, deren Skript einem Asset gleicht, und das in einer
Sandbox. Die Assets kommen aus tmp_path (Modulkonstante ASSETS): eine Stub-Statusline mit
Kennzeile, die Cache und Kontextzustand schreibt, und der echte Hook."""

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest
from conftest import REPO_ROOT, load_script

verify_mod = load_script("skills/setup-user/scripts/verify_install.py")
REAL_HINT = REPO_ROOT / "skills" / "setup-user" / "assets" / "runtime" / "context_hint.py"

STUB_STATUSLINE = '''#!/usr/bin/env python3
# setup-user: statusline
import json, os, pathlib, sys
d = json.loads(sys.stdin.buffer.read().decode("utf-8"))
cfg = pathlib.Path(os.environ["CLAUDE_CONFIG_DIR"])
rl = d["rate_limits"]
cache = {w: {"used_percentage": rl[w]["used_percentage"], "resets_at_epoch": rl[w]["resets_at"]} for w in rl}
(cfg / "usage-cache.json").write_text(json.dumps(cache))
st = cfg / "setup-user" / "state"
st.mkdir(parents=True, exist_ok=True)
(st / ("context-" + d["session_id"] + ".json")).write_text(
    json.dumps({"session_id": d["session_id"], "used_percentage": d["context_window"]["used_percentage"]}))
print("Opus | Kontext " + str(d["context_window"]["used_percentage"]) + " %")
'''
SILENT = "#!/usr/bin/env python3\n# setup-user: context_hint\n"
EXIT3 = "#!/usr/bin/env python3\nimport sys\nsys.exit(3)\n"
EMPTY_STATUSLINE = "#!/usr/bin/env python3\n# setup-user: statusline\n"


def make_install(tmp_path: Path, monkeypatch, *, statusline=STUB_STATUSLINE, hint=None, hook_suffix=" || true",
                 statusline_cmd=None) -> Path:
    assets = tmp_path / "skill" / "assets" / "runtime"
    assets.mkdir(parents=True)
    (assets / "statusline.py").write_text(statusline, encoding="utf-8")
    hint_text = hint if hint is not None else REAL_HINT.read_text(encoding="utf-8")
    (assets / "context_hint.py").write_text(hint_text, encoding="utf-8")
    monkeypatch.setattr(verify_mod, "ASSETS", tmp_path / "skill" / "assets")

    cfg = tmp_path / "cfg"
    runtime = cfg / "setup-user" / "runtime"
    runtime.mkdir(parents=True)
    shutil.copy(assets / "statusline.py", runtime / "statusline.py")
    shutil.copy(assets / "context_hint.py", runtime / "context_hint.py")
    posix = cfg.resolve().as_posix()
    settings = {
        "statusLine": {"type": "command", "command": statusline_cmd or f'python3 "{posix}/setup-user/runtime/statusline.py"'},
        "hooks": {"UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": f'python3 "{posix}/setup-user/runtime/context_hint.py"{hook_suffix}'}]}]},
    }
    (cfg / "settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return cfg


def snapshot(*roots: Path) -> dict:
    out = {}
    for root in roots:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def test_verify_passes_and_runs_in_sandbox_only(tmp_path, monkeypatch):
    cfg = make_install(tmp_path, monkeypatch)
    before = snapshot(tmp_path)
    result = verify_mod.verify(cfg)
    assert result["findings"] == [], result
    assert result["unchecked"] == []
    assert {r["kind"] for r in result["ran"]} == {"statusline", "hook"}
    assert snapshot(tmp_path) == before, "keine neue oder geänderte Datei außerhalb der Sandbox, auch nicht unter HOME"


def test_verify_skips_foreign_commands(tmp_path, monkeypatch):
    marker = tmp_path / "fremd-lief"
    foreign = tmp_path / "fremd.py"
    foreign.write_text(f"open({str(marker)!r}, 'w').write('x')\nprint('fremd')\n", encoding="utf-8")
    cfg = make_install(tmp_path, monkeypatch, statusline_cmd=f'python3 "{foreign}"')
    result = verify_mod.verify(cfg)
    assert not marker.exists(), "die fremde Statusline darf nie laufen"
    assert any("ungeprüft (fremd, nicht ausgeführt)" in u for u in result["unchecked"])
    assert result["findings"] == [], "der Hook meldet mit dem eingespielten Beispielzustand"


@pytest.mark.parametrize("case", ["silent-hook", "nonzero-exit", "empty-statusline", "missing-script"])
def test_verify_flags_silent_hook_nonzero_exit_and_empty_statusline(tmp_path, monkeypatch, case):
    if case == "silent-hook":
        cfg = make_install(tmp_path, monkeypatch, hint=SILENT)
        expected = "schweigt"
    elif case == "nonzero-exit":
        cfg = make_install(tmp_path, monkeypatch, hint=EXIT3, hook_suffix="")
        expected = "Exit 3"
    elif case == "empty-statusline":
        cfg = make_install(tmp_path, monkeypatch, statusline=EMPTY_STATUSLINE)
        expected = "leer"
    else:
        cfg = make_install(tmp_path, monkeypatch)
        (cfg / "setup-user" / "runtime" / "context_hint.py").unlink()
        expected = "fehlt"
    result = verify_mod.verify(cfg)
    assert any(expected in f for f in result["findings"]), result


def test_verify_without_bash_is_unchecked(tmp_path, monkeypatch):
    cfg = make_install(tmp_path, monkeypatch)
    monkeypatch.setattr(verify_mod, "_find_bash", lambda: None)
    result = verify_mod.verify(cfg)
    assert result["ran"] == [] and result["findings"] == []
    assert any("ungeprüft — keine bash" in u for u in result["unchecked"])


def test_verify_main_exit_codes(tmp_path, monkeypatch, capsys):
    cfg = make_install(tmp_path, monkeypatch)
    assert verify_mod.main(["--config-dir", str(cfg)]) == 0
    assert "geprüft" in capsys.readouterr().out
    (cfg / "setup-user" / "runtime" / "context_hint.py").unlink()
    assert verify_mod.main(["--config-dir", str(cfg)]) == 1
