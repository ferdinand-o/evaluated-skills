"""Tests für skills/setup-user/assets/runtime/context_hint.py (Spec 21, Abschnitt A).

Der Hook läuft als Unterprozess mit CLAUDE_CONFIG_DIR und HOME auf tmp_path; kein Test
berührt ~/.claude. Zustand und Limit-Cache schreibt der Test von Hand im Format aus
skills/setup-user/references/thresholds.md."""

import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import REPO_ROOT, load_script

HOOK = REPO_ROOT / "skills" / "setup-user" / "assets" / "runtime" / "context_hint.py"
SID = "sess-1"


def run_hook(cfg: Path, payload, *, raw: bytes | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfg), "HOME": str(cfg / "home"), "USERPROFILE": str(cfg / "home")}
    data = raw if raw is not None else json.dumps(payload).encode("utf-8")
    return subprocess.run([sys.executable, str(HOOK)], input=data, capture_output=True, env=env, timeout=20)


def set_context(cfg: Path, pct, sid: str = SID) -> None:
    state = cfg / "setup-user" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / f"context-{sid}.json").write_text(json.dumps({"session_id": sid, "used_percentage": pct}), encoding="utf-8")


def set_limits(cfg: Path, five=None, seven=None, five_reset=None, seven_reset=None) -> None:
    now = int(time.time())
    cache = {}
    if five is not None:
        cache["five_hour"] = {"used_percentage": five, "resets_at_epoch": five_reset or now + 3600}
    if seven is not None:
        cache["seven_day"] = {"used_percentage": seven, "resets_at_epoch": seven_reset or now + 86400}
    (cfg / "usage-cache.json").write_text(json.dumps(cache), encoding="utf-8")


def text_of(proc: subprocess.CompletedProcess) -> str | None:
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.decode("utf-8")
    if not out.strip():
        return None
    return json.loads(out)["hookSpecificOutput"]["additionalContext"]


def test_hint_once_and_rearms(tmp_path):
    set_context(tmp_path, 63)
    first = text_of(run_hook(tmp_path, {"session_id": SID}))
    assert first and "Kontext 63 %" in first and "Schwelle 60 %" in first
    assert text_of(run_hook(tmp_path, {"session_id": SID})) is None, "zweiter Prompt über derselben Schwelle"
    set_context(tmp_path, 20)  # nach /compact
    assert text_of(run_hook(tmp_path, {"session_id": SID})) is None
    set_context(tmp_path, 61)
    assert "Schwelle 60 %" in text_of(run_hook(tmp_path, {"session_id": SID})), "wieder scharf"

    now = int(time.time())
    set_limits(tmp_path, five=81, five_reset=now + 600)
    assert "5-Stunden-Limit 81 %" in text_of(run_hook(tmp_path, {"session_id": SID}))
    assert text_of(run_hook(tmp_path, {"session_id": "andere"})) is None, "Limits gelten je Account, einmal gemeldet"
    set_limits(tmp_path, five=82, five_reset=now + 18600)  # neues Fenster
    assert "5-Stunden-Limit 82 %" in text_of(run_hook(tmp_path, {"session_id": SID}))


def test_hint_one_text_per_prompt_highest_threshold(tmp_path):
    set_context(tmp_path, 50)
    assert text_of(run_hook(tmp_path, {"session_id": SID})) is None
    set_context(tmp_path, 85)
    text = text_of(run_hook(tmp_path, {"session_id": SID}))
    assert "Schwelle 80 %" in text and "Schwelle 60 %" not in text
    set_context(tmp_path, 70)
    assert text_of(run_hook(tmp_path, {"session_id": SID})) is None, "60 gilt als gemeldet"
    set_context(tmp_path, 90)
    set_limits(tmp_path, seven=86)
    text = text_of(run_hook(tmp_path, {"session_id": SID}))
    assert text.count("[setup-user]") == 1 and "Kontext 90 %" in text and "7-Tage-Limit 86 %" in text


@pytest.mark.parametrize("case", ["foreign-session", "null-context", "expired-limit", "null-limit", "nothing"])
def test_hint_silent_on_foreign_session_null_or_expired_limits(tmp_path, case):
    now = int(time.time())
    if case == "foreign-session":
        set_context(tmp_path, 90, sid="fremd")
    elif case == "null-context":
        set_context(tmp_path, None)
    elif case == "expired-limit":
        set_limits(tmp_path, five=99, five_reset=now - 1)
    elif case == "null-limit":
        set_limits(tmp_path, five=None)
        (tmp_path / "usage-cache.json").write_text(
            json.dumps({"five_hour": {"used_percentage": None, "resets_at_epoch": now + 600}}), encoding="utf-8")
    assert text_of(run_hook(tmp_path, {"session_id": SID})) is None


def test_hint_limits_without_statusline_state(tmp_path):
    set_limits(tmp_path, five=95)
    text = text_of(run_hook(tmp_path, {"session_id": SID}))
    assert "5-Stunden-Limit" in text and "Kontext" not in text


@pytest.mark.parametrize("raw", [b"{kaputt", b"", b"\xff\xfe\x00", "[1, 2]".encode(), "{\"session_id\": \"../x\"}".encode()])
def test_hint_exit_zero_on_any_error(tmp_path, raw):
    set_context(tmp_path, 90)
    (tmp_path / "setup-user" / "state" / f"hints-{SID}.json").write_text("{kaputt", encoding="utf-8")
    proc = run_hook(tmp_path, None, raw=raw)
    assert proc.returncode == 0 and proc.stdout == b""


def test_hint_exit_zero_on_unreadable_state_and_forced_exception(tmp_path, monkeypatch, capsys):
    set_context(tmp_path, 90)
    (tmp_path / "setup-user" / "state" / f"hints-{SID}.json").write_text("{kaputt", encoding="utf-8")
    assert text_of(run_hook(tmp_path, {"session_id": SID})), "kaputter Merker zählt als leer"

    mod = load_script("skills/setup-user/assets/runtime/context_hint.py")

    def boom(*_args):
        raise RuntimeError("erzwungen")

    monkeypatch.setattr(mod, "hint_for", boom)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b'{"session_id": "sess-1"}')))
    assert mod.main() == 0
    assert capsys.readouterr().out == ""


def test_hint_output_shape(tmp_path):
    set_context(tmp_path, 81)
    proc = run_hook(tmp_path, {"session_id": SID, "prompt": "Grüße 😀"})
    out = proc.stdout.decode("utf-8")
    data = json.loads(out)  # genau ein Objekt, sonst nichts
    assert set(data) == {"hookSpecificOutput"}
    assert data["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert data["hookSpecificOutput"]["additionalContext"].startswith("[setup-user]")


def test_hint_reads_thresholds_json(tmp_path):
    (tmp_path / "setup-user").mkdir()
    (tmp_path / "setup-user" / "thresholds.json").write_text(
        json.dumps({"_meta": {}, "context": [30], "five_hour": [80], "seven_day": [85]}), encoding="utf-8")
    set_context(tmp_path, 35)
    assert "Schwelle 30 %" in text_of(run_hook(tmp_path, {"session_id": SID}))
