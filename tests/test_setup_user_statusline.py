"""Tests für skills/setup-user/assets/runtime/statusline.py (Spec 21, Abschnitt A).

Vorlage ist die Statusline des Nutzers (tests/fixtures/setup-user/statusline-original.py).
Das Asset zeigt dasselbe an, schreibt den Limit-Cache aber nach $CLAUDE_CONFIG_DIR, behält
Fenster ohne neuen Wert, schreibt je Session den Kontextzustand und endet immer mit 0.
Alle Läufe als Unterprozess mit HOME und CLAUDE_CONFIG_DIR auf tmp_path."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import REPO_ROOT

ASSET = REPO_ROOT / "skills" / "setup-user" / "assets" / "runtime" / "statusline.py"
ORIGINAL = REPO_ROOT / "tests" / "fixtures" / "setup-user" / "statusline-original.py"
KNOWN = REPO_ROOT / "skills" / "setup-user" / "assets" / "runtime" / "known-statusline-hashes.json"


def full_input(cwd: Path, sid: str = "s1", five=81, seven=23) -> dict:
    return {"session_id": sid, "model": {"display_name": "Opus"}, "workspace": {"current_dir": str(cwd)},
            "context_window": {"used_percentage": 42.4},
            "cost": {"total_cost_usd": 1.234, "total_duration_ms": 754000},
            "rate_limits": {"five_hour": {"used_percentage": five, "resets_at": 1791720000},
                            "seven_day": {"used_percentage": seven, "resets_at": 1792300000}}}


def run(script: Path, data, home: Path, cfg: Path | None = None, *, raw: bytes | None = None):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
    env.update({"HOME": str(home), "USERPROFILE": str(home)})
    if cfg is not None:
        env["CLAUDE_CONFIG_DIR"] = str(cfg)
    payload = raw if raw is not None else json.dumps(data).encode("utf-8")
    return subprocess.run([sys.executable, "-I", str(script)], input=payload, capture_output=True, env=env, timeout=20)


def cache(cfg: Path) -> dict:
    return json.loads((cfg / "usage-cache.json").read_text(encoding="utf-8"))


@pytest.fixture
def dirs(tmp_path):
    home, cfg, cwd = tmp_path / "home", tmp_path / "cfg", tmp_path / "work"
    for d in (home, cfg, cwd):
        d.mkdir()
    return home, cfg, cwd


def test_statusline_display_unchanged(dirs):
    home, cfg, cwd = dirs
    ours = run(ASSET, full_input(cwd), home, cfg)
    theirs = run(ORIGINAL, full_input(cwd), home)
    assert ours.returncode == theirs.returncode == 0, ours.stderr
    assert ours.stdout == theirs.stdout
    assert len(ours.stdout.decode("utf-8").splitlines()) == 4


def test_statusline_keeps_cache_on_session_start(dirs):
    home, cfg, cwd = dirs
    run(ASSET, full_input(cwd), home, cfg)
    start = full_input(cwd)
    del start["rate_limits"]
    assert run(ASSET, start, home, cfg).returncode == 0
    c = cache(cfg)
    assert c["five_hour"]["used_percentage"] == 81 and c["seven_day"]["used_percentage"] == 23
    assert c["five_hour"]["resets_at_epoch"] == 1791720000 and c["five_hour"]["resets_at_berlin"]
    assert c["_meta"]["skill"] == "setup-user" and "updated_at" in c


def test_statusline_keeps_window_on_explicit_null(dirs):
    home, cfg, cwd = dirs
    run(ASSET, full_input(cwd), home, cfg)
    data = full_input(cwd)
    data["rate_limits"] = {"five_hour": None, "seven_day": {"used_percentage": None, "resets_at": 1}}
    assert run(ASSET, data, home, cfg).returncode == 0
    c = cache(cfg)
    assert c["five_hour"]["used_percentage"] == 81 and c["seven_day"]["used_percentage"] == 23


def test_statusline_partial_window_keeps_other_window(dirs):
    home, cfg, cwd = dirs
    run(ASSET, full_input(cwd), home, cfg)
    data = full_input(cwd, five=90)
    del data["rate_limits"]["seven_day"]
    run(ASSET, data, home, cfg)
    c = cache(cfg)
    assert c["five_hour"]["used_percentage"] == 90
    assert c["seven_day"] == {"used_percentage": 23, "resets_at_epoch": 1792300000,
                              "resets_at_berlin": c["seven_day"]["resets_at_berlin"]}


def test_statusline_respects_config_dir(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    a, b = tmp_path / "acct-a", tmp_path / "acct-b"
    a.mkdir()
    b.mkdir()
    run(ASSET, full_input(tmp_path, five=10), home, a)
    run(ASSET, full_input(tmp_path, five=20), home, b)
    assert cache(a)["five_hour"]["used_percentage"] == 10 and cache(b)["five_hour"]["used_percentage"] == 20
    assert not (home / ".claude" / "usage-cache.json").exists()
    installed = tmp_path / "acct-c"
    (installed / "setup-user" / "runtime").mkdir(parents=True)
    shutil.copy(ASSET, installed / "setup-user" / "runtime" / "statusline.py")
    run(installed / "setup-user" / "runtime" / "statusline.py", full_input(tmp_path, five=30), home)
    assert cache(installed)["five_hour"]["used_percentage"] == 30, "ohne Variable: drei Ebenen über der Datei"


@pytest.mark.parametrize("raw", [b"", b"{kaputt", b"[1]", '{"context_window": null, "session_id": "s1"}'.encode(),
                                 '{"model": {"display_name": "Opus 😀 ä"}, "workspace": {"current_dir": "/tmp/ü"}}'.encode(),
                                 b'{"model": {"display_name": "\xff\xfe"}}'])
def test_statusline_survives_null_empty_and_non_ascii_input(dirs, raw):
    home, cfg, _ = dirs
    proc = run(ASSET, None, home, cfg, raw=raw)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.decode("utf-8").strip(), "mindestens eine Zeile"
    if b"context_window" in raw:
        state = json.loads((cfg / "setup-user" / "state" / "context-s1.json").read_text(encoding="utf-8"))
        assert state["used_percentage"] is None and state["session_id"] == "s1"


def test_statusline_writes_context_state(dirs):
    home, cfg, cwd = dirs
    run(ASSET, full_input(cwd, sid="abc-1"), home, cfg)
    state = json.loads((cfg / "setup-user" / "state" / "context-abc-1.json").read_text(encoding="utf-8"))
    assert state["used_percentage"] == 42.4 and state["_meta"]["skill"] == "setup-user"


def test_statusline_state_prunes_and_sanitizes(dirs):
    home, cfg, cwd = dirs
    state = cfg / "setup-user" / "state"
    state.mkdir(parents=True)
    old, fresh, tmp_old = state / "context-alt.json", state / "hints-neu.json", state / "x.json.1.tmp"
    for p in (old, fresh, tmp_old):
        p.write_text("{}", encoding="utf-8")
    two_days = time.time() - 2 * 86400
    os.utime(old, (two_days, two_days))
    os.utime(tmp_old, (two_days, two_days))
    run(ASSET, full_input(cwd), home, cfg)
    assert not old.exists() and not tmp_old.exists() and fresh.exists()
    run(ASSET, full_input(cwd, sid="../ausbruch"), home, cfg)
    assert not (cfg / "setup-user" / "ausbruch.json").exists()
    assert not any("ausbruch" in p.name for p in cfg.rglob("*"))


def test_known_hashes_name_the_original():
    digest = hashlib.sha256(ORIGINAL.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert digest in json.loads(KNOWN.read_text(encoding="utf-8"))["sha256"]
    lines = ASSET.read_text(encoding="utf-8").splitlines()
    assert lines[1] == "# setup-user: statusline"
