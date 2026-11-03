"""Tests für skills/decide/scripts/decide_log.py (Spec 28, Task 1): Wurzel und Sitzung,
Form der Belegzeile, Tabellenzeichen und Umlaute, Regeln aus Repo- und Nutzerdatei."""

import errno
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import DECIDE_SESSION as SESSION
from conftest import DECIDE_TAIL as TAIL
from conftest import decide_add_small as add_small
from conftest import decide_commit as commit
from conftest import decide_log_file as log_file
from conftest import decide_rows as rows
from conftest import decide_script, git

dl = decide_script()


def write_rules(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_root_and_session(tmp_path, monkeypatch, capsys):
    root = tmp_path / "repo"
    (root / "a" / "b").mkdir(parents=True)
    git(root, "init", "-q")
    assert dl.repo_root(root / "a" / "b").resolve() == root.resolve()
    plain = tmp_path / "ohne-git"
    plain.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    assert dl.repo_root(plain) == plain

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "aus-env")
    assert dl.session_id("von-hand") == "von-hand"
    assert dl.session_id(None) == "aus-env"
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    assert dl.session_id(None) is None

    # Eine Sitzungs-ID wird Ordnername: kein Pfadtrenner, kein `..`.
    monkeypatch.chdir(root)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert add_small("CLI", "?", "ja", "gesucht: a — nichts gefunden", "--session", "../weg") == 1
    assert "--session" in capsys.readouterr().err
    assert not (root / ".skills").exists()


def test_evidence_form(decide_repo, tmp_path, capsys):
    root, _ = decide_repo
    want = "gesucht: x — Treffer: a.py:3"
    assert dl.normalize_evidence("gesucht: x - Treffer: ./a.py:3", root) == want
    assert dl.normalize_evidence("gesucht: x -- Treffer: a.py:3", root) == want
    assert dl.normalize_evidence(f"gesucht: x — Treffer: {root}/a.py:3", root) == want
    assert dl.normalize_evidence(f"gesucht: x — Treffer: {root.resolve()}/a.py:3", root) == want
    assert (dl.normalize_evidence(f"gesucht: {root}/src, ./docs — nichts gefunden", root)
            == "gesucht: src, docs — nichts gefunden")
    outside = tmp_path / "anderswo" / "a.py"
    assert (dl.normalize_evidence(f"gesucht: x — Treffer: {outside}:3", root)
            == f"gesucht: x — Treffer: {outside}:3")

    # über die Kommandozeile: normalisiert ins Protokoll
    assert add_small("CLI", "Kurzoption?", "Kurzform -v", f"gesucht: x -- Treffer: {root}/a.py:3") == 0
    assert rows(root)[0][5] == want

    # andere Form: Exit 1, keine Zeile, der Grund nennt die erwartete Form
    capsys.readouterr()
    for bad in ("gesucht: x", "Treffer: a.py:3", "gesucht: x — Treffer: a.py", "gesucht: — nichts gefunden"):
        assert add_small("CLI", "Noch eine?", "nein", bad) == 1, bad
        err = capsys.readouterr().err
        assert "nichts gefunden" in err and "Treffer: <datei:zeile>" in err, err
    assert len(rows(root)) == 1


def test_pipe_and_unicode(decide_repo):
    root, _ = decide_repo
    assert add_small("Übersetzungen", "Trenner | oder ; für Größen?", "„|“ bleibt",
                     "gesucht: a|b — nichts gefunden") == 0
    [row] = rows(root)
    assert len(row) == 7
    assert row[1:6] == ["Übersetzungen", "annahme", "Trenner ¦ oder ; für Größen?", "„¦“ bleibt",
                        "gesucht: a¦b — nichts gefunden"]
    raw = log_file(root).read_bytes()
    assert "Größen".encode("utf-8") in raw
    raw.decode("utf-8")


def test_rules_listing(decide_repo, capsys):
    root, home = decide_repo
    repo_rules = root / ".skills" / "decide" / "rules.md"
    user_rules = home / ".skills" / "decide" / "rules.md"
    write_rules(repo_rules, "# Kommentarzeile\nnie fragen: UI-Texte   # Wortlaut ist egal\n\n")
    write_rules(user_rules, "immer fragen: Migrationen\n#immer fragen: Versteckt\nunsinn ohne Doppelpunkt\n")

    rules = dl.load_rules(root, home)
    assert [(r.kind, r.topic) for r in rules] == [("nie fragen", "UI-Texte"), ("immer fragen", "Migrationen")]
    assert rules[0].path == repo_rules and rules[1].path == user_rules

    assert dl.main(["rules"]) == 0
    out = capsys.readouterr().out
    assert "nie fragen: UI-Texte" in out and ".skills/decide/rules.md" in out
    assert "immer fragen: Migrationen" in out and "~/.skills/decide/rules.md" in out
    assert "Versteckt" not in out and "Kommentarzeile" not in out and "Wortlaut" not in out
    assert "unsinn ohne Doppelpunkt" in out          # sichtbar ignoriert, nicht still

    # Treffer nach Kleinschreibung und Trimmen: Thema in der Schreibweise der Regel
    assert add_small("  ui-texte ", "Text der Fehlermeldung?", "Datei fehlt",
                     "gesucht: msgs.py — Treffer: msgs.py:2") == 0
    [row] = rows(root)
    assert row[1:3] == ["UI-Texte", "klein"]
    assert "nie fragen: UI-Texte" in row[6]
    out = capsys.readouterr().out
    assert "nie fragen: UI-Texte" in out


def test_rules_without_files(decide_repo, capsys):
    _, home = decide_repo
    assert dl.load_rules(Path.cwd(), home) == []
    assert dl.main(["rules"]) == 0
    assert "Keine Regeln" in capsys.readouterr().out


def test_upgrade_without_options_writes_nothing(decide_repo, capsys):
    root, home = decide_repo
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: UI-Texte\n")
    assert add_small("ui-texte", "Text der Fehlermeldung?", "Datei fehlt",
                     "gesucht: msgs.py — Treffer: msgs.py:2") == 1
    err = capsys.readouterr().err
    assert "Regel immer fragen: UI-Texte trifft — zwei bis vier --option nötig" in err
    assert add_small("UI-Texte", "Text?", "A", "gesucht: msgs.py — Treffer: msgs.py:2",
                     "--option", "A: kurz") == 1
    assert "zwei bis vier --option" in capsys.readouterr().err
    assert not log_file(root).exists()
    assert not (root / "docs").exists()


def test_summary_without_entries(decide_repo, capsys):
    assert dl.main(["summary"]) == 0
    out = capsys.readouterr().out
    assert "Keine Einträge" in out
    assert not [line for line in out.splitlines() if line.startswith("- ")]


# --- Funde des Prüfpunkts 1 (F1–F13) ---------------------------------------------------

def small_args(home, topic="CLI", question="Kurzoption?", decision="kurz",
               evidence="gesucht: cli.py — Treffer: cli.py:3"):
    return SimpleNamespace(topic=topic, question=question, decision=decision, evidence=evidence,
                           options=None, home=home)


def test_evidence_through_symlink(decide_repo, tmp_path, monkeypatch):
    """F1: Ein absoluter Belegpfad über einen symlinkten Ordner wird relativ zur Wurzel."""
    root, _ = decide_repo
    link = tmp_path / "link"
    link.symlink_to(root, target_is_directory=True)
    want = "gesucht: x — Treffer: CONTRIBUTING.md:12"
    assert dl.normalize_evidence(f"gesucht: x — Treffer: {link}/CONTRIBUTING.md:12", root) == want
    monkeypatch.chdir(link)                         # git liefert den echten Pfad als Wurzel
    assert add_small("Doku", "Wo steht es?", "CONTRIBUTING", f"gesucht: x — Treffer: {link}/CONTRIBUTING.md:12") == 0
    assert rows(root)[0][5] == want


def test_summary_hides_never_topic_with_pipe_and_spaces(decide_repo, capsys):
    """F2: `nie fragen` trifft in summary wie in add, auch bei `|` und doppeltem Leerraum."""
    root, _ = decide_repo
    write_rules(root / ".skills" / "decide" / "rules.md", "nie fragen: a|b\nnie fragen: Log  Level\n")
    assert add_small("a|b", "Trenner?", "Pipe", "gesucht: a — nichts gefunden") == 0
    assert "erscheint nicht in summary" in capsys.readouterr().out
    assert add_small("Log  Level", "Retries?", "debug", "gesucht: net.py — Treffer: net.py:3") == 0
    assert "erscheint nicht in summary" in capsys.readouterr().out
    assert add_small("CLI", "Kurzoption?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    capsys.readouterr()
    assert dl.main(["summary"]) == 0
    out = capsys.readouterr().out
    assert [line for line in out.splitlines() if line.startswith("- ")] == [
        "- [klein] CLI: Kurzoption? → kurz (gesucht: cli.py — Treffer: cli.py:3)"]
    assert "ausgelassen per nie fragen: 2" in out


def test_hint_only_from_word_start(decide_repo, capsys):
    """F4: Ein ähnliches Thema ist nur ab Wortanfang ein Hinweis — `UI` steckt nicht in `Build`."""
    root, home = decide_repo
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: UI\n")
    rules = dl.load_rules(root, home)
    assert dl.match_rules(rules, "Build") == ([], [])
    assert dl.match_rules(rules, "UI-Texte")[1] == rules
    assert add_small("Build", "Ordner?", "dist", "gesucht: Makefile — Treffer: Makefile:4") == 0
    out = capsys.readouterr().out
    assert "ähnelt" not in out and "immer fragen: UI" not in out, out


def test_empty_log_is_like_missing(decide_repo, capsys):
    """F5: Ein leeres oder nur aus Leerraum bestehendes log.md gilt als fehlend."""
    root, _ = decide_repo
    path = log_file(root)
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    assert dl.main(["summary"]) == 0
    assert "Keine Einträge" in capsys.readouterr().out
    path.write_text("\n  \n", encoding="utf-8")
    assert add_small("CLI", "Kurzoption?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    assert path.read_text(encoding="utf-8").splitlines()[0] == dl.LOG_HEADER
    assert len(rows(root)) == 1


def test_dash_only_before_result(decide_repo):
    """F6: Nur der Trenner vor `Treffer:`/`nichts gefunden` wird ` — `, das Suchmuster bleibt."""
    root, _ = decide_repo
    assert (dl.normalize_evidence("gesucht: rg 'foo - bar' - Treffer: a.py:3", root)
            == "gesucht: rg 'foo - bar' — Treffer: a.py:3")
    assert (dl.normalize_evidence("gesucht: rg 'a -- b' – c -- nichts gefunden", root)
            == "gesucht: rg 'a -- b' – c — nichts gefunden")


def test_relative_path_from_subdir(decide_repo, monkeypatch):
    """F7: `./` und `../` gelten relativ zum Arbeitsverzeichnis, das Protokoll relativ zur Wurzel."""
    root, _ = decide_repo
    (root / "src").mkdir()
    monkeypatch.chdir(root / "src")
    assert (dl.normalize_evidence("gesucht: ./, ../docs — Treffer: ./parser.py:12", root)
            == "gesucht: src, docs — Treffer: src/parser.py:12")
    assert add_small("Parser", "Trenner?", ";", "gesucht: ./ — Treffer: ./parser.py:12") == 0
    assert rows(root)[0][5] == "gesucht: src — Treffer: src/parser.py:12"


def test_trailing_punctuation(decide_repo):
    """F8: `.`, `,`, `;` oder `)` am Ende der Belegzeile fallen weg."""
    root, _ = decide_repo
    for tail in (".", ")", ";", ",", ")."):
        assert (dl.normalize_evidence(f"gesucht: src — Treffer: src/a.py:3{tail}", root)
                == "gesucht: src — Treffer: src/a.py:3"), tail
    assert dl.normalize_evidence("gesucht: docs — nichts gefunden.", root) == "gesucht: docs — nichts gefunden"
    assert add_small("CLI", "Kurzoption?", "kurz", "gesucht: src — Treffer: src/a.py:3.") == 0


def test_unwritable_log_is_one_line(decide_repo, capsys):
    """F9: Scheitert das Schreiben, endet add mit 1 und einem Grund statt Traceback."""
    root, _ = decide_repo
    (root / ".skills").write_text("keine Ordner\n", encoding="utf-8")
    assert add_small("CLI", "Kurzoption?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 1
    err = capsys.readouterr().err
    assert f".skills/cache/decide/{SESSION}/log.md" in err and "nichts geschrieben" in err, err
    assert len(err.strip().splitlines()) == 1


def test_big_flags_on_small_warn(decide_repo, capsys):
    """F10: Angaben großer Fragen bei add --class klein werden sichtbar ignoriert."""
    root, _ = decide_repo
    assert add_small("CLI", "Kurzoption?", "kurz", "gesucht: cli.py — Treffer: cli.py:3",
                     "--option", "A: -v", "--option", "B: -V", "--recommendation", "A",
                     "--key", "rule:CLI", "--approved-by-request", "mach -v") == 0
    captured = capsys.readouterr()
    for flag in ("--option", "--recommendation", "--key", "--approved-by-request"):
        assert flag in captured.err, captured.err
    assert "--class gross" in captured.err
    assert "Eingetragen" in captured.out
    assert len(rows(root)) == 1
    assert add_small("CLI", "Noch eine?", "nein", "gesucht: cli.py — Treffer: cli.py:4") == 0
    assert capsys.readouterr().err == ""


def test_write_atomic_sleeps_only_between_attempts(tmp_path, monkeypatch):
    """F12: Nach dem letzten Fehlversuch wird nicht mehr gewartet."""
    sleeps = []

    def fail(*_):
        raise OSError("belegt")

    monkeypatch.setattr(dl.os, "replace", fail)
    monkeypatch.setattr(dl.time, "sleep", sleeps.append)
    target = tmp_path / "log.md"
    with pytest.raises(OSError):
        dl.write_atomic(target, "x\n")
    assert len(sleeps) == 2
    assert list(tmp_path.iterdir()) == []


def test_contradiction_once_per_topic(decide_repo, capsys):
    """F13: Ein Widerspruch je Thema, auch wenn eine Regel doppelt steht."""
    root, home = decide_repo
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: X\n")
    write_rules(home / ".skills" / "decide" / "rules.md", "immer fragen: X\nnie fragen: x\n")
    assert dl.main(["rules"]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("Widerspruch")]
    assert len(lines) == 1, lines
    assert ".skills/decide/rules.md" in lines[0] and "~/.skills/decide/rules.md" in lines[0]


# --- Funde des Prüfpunkts 1, Runde 2 (F1–F10) -------------------------------------------

def unreadable(monkeypatch, name="log.md"):
    """Lesefehler auf `name` simulieren — als root greift Modus 0200 nicht. `read_file` liest Bytes
    (`read_bytes`) und dekodiert sie mit `decode_text`."""
    real = Path.read_bytes

    def read_bytes(self, *args, **kwargs):
        if self.name == name:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)


def test_unreadable_log_is_not_replaced(decide_repo, monkeypatch, capsys):
    """R2-F1: Ein vorhandenes, aber unlesbares log.md gilt nicht als fehlend — add und summary
    enden mit 1, das Protokoll bleibt, wie es war."""
    root, _ = decide_repo
    for n in range(3):
        assert add_small("CLI", f"Frage {n}?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    before = log_file(root).read_bytes()
    capsys.readouterr()
    unreadable(monkeypatch)
    assert add_small("CLI", "Danach?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 1
    captured = capsys.readouterr()
    assert "nicht lesbar" in captured.err and "nichts geschrieben" in captured.err, captured.err
    assert "Permission denied" in captured.err
    assert "Protokoll angelegt" not in captured.out + captured.err
    with open(log_file(root), "rb") as handle:                  # Path.read_bytes ist ersetzt
        assert handle.read() == before

    assert dl.main(["summary"]) == 1
    err = capsys.readouterr().err
    assert "nicht lesbar" in err and f".skills/cache/decide/{SESSION}/log.md" in err, err


def test_relative_path_outside_root_stays_as_written(decide_repo, monkeypatch):
    """R2-F2: `./`, `../` und `..` außerhalb der Wurzel bleiben, wie sie stehen."""
    root, _ = decide_repo
    for text in ("gesucht: ../other — nichts gefunden", "gesucht: .. — nichts gefunden",
                 "gesucht: x — Treffer: ../other/a.py:3"):
        assert dl.normalize_evidence(text, root) == text
    (root / "src").mkdir()
    monkeypatch.chdir(root / "src")
    assert (dl.normalize_evidence("gesucht: ../../x, ../docs — nichts gefunden", root)
            == "gesucht: ../../x, docs — nichts gefunden")


def test_write_failure_keeps_cause(decide_repo, monkeypatch, capsys):
    """R2-F6: Scheitern alle Ersetzungen, nennt die Meldung die Ursache und den Pfad einmal,
    relativ zur Wurzel."""
    root, _ = decide_repo

    def deny(src, dst):
        raise PermissionError(13, "Permission denied", str(src), None, str(dst))

    monkeypatch.setattr(dl.os, "replace", deny)
    monkeypatch.setattr(dl.time, "sleep", lambda _: None)
    with pytest.raises(PermissionError):
        dl.write_atomic(root / "x.md", "x\n")
    assert add_small("CLI", "Kurzoption?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 1
    err = capsys.readouterr().err
    assert "Permission denied" in err, err
    assert err.count("log.md") == 1 and str(root) not in err, err


def test_hint_for_topic_starting_with_non_word_char(decide_repo):
    """R2-F7: Beginnt das kürzere Thema mit einem Nicht-Wortzeichen, reicht der Teilstring."""
    root, home = decide_repo
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: .NET\n")
    rules = dl.load_rules(root, home)
    assert dl.match_rules(rules, "ASP.NET") == ([], rules)
    assert dl.match_rules(rules, "Build") == ([], [])


def test_log_format_against_raw_text(decide_repo):
    """R2-F9: Pfad und Zeilenformat des Protokolls, unabhängig von log_path/parse_rows geprüft."""
    root, _ = decide_repo
    assert add_small("CLI", "Kurz|option?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    raw = (root / ".skills" / "cache" / "decide" / "sitzung-1" / "log.md").read_text(encoding="utf-8")
    lines = raw.split("\n")
    assert lines[:4] == [
        "<!-- skill: decide | schema: 1 | generated: python decide_log.py add -->",
        "",
        "| zeit | thema | klasse | frage | entscheidung | beleg | regel |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    assert re.fullmatch(r"\| \d{4}-\d\d-\d\dT\d\d:\d\d:\d\d \| CLI \| klein \| Kurz¦option\? \| kurz "
                        r"\| gesucht: cli\.py — Treffer: cli\.py:3 \| — \|", lines[4]), lines[4]
    assert lines[5:] == [""]


def test_summary_many_entries_and_rules(decide_repo, monkeypatch):
    """R2-F10: summary schlägt Themen in Mengen nach statt match_rules je Eintrag — mit vielen
    Einträgen und Regeln dasselbe Ergebnis wie der Abgleich über match_rules."""
    root, home = decide_repo
    rule_lines = [f"nie fragen: Thema {n}" for n in range(0, 30, 2)]
    rule_lines += [f"immer fragen: thema  {n}" for n in range(0, 30, 6)]      # Widersprüche
    rule_lines += ["nie fragen: a|b", "immer fragen: Thema", "nie fragen: Thema 1x"]
    write_rules(root / ".skills" / "decide" / "rules.md", "\n".join(rule_lines) + "\n")
    rules = dl.load_rules(root, home)
    topics = [f"THEMA {n % 31}" for n in range(60)] + ["a|b", "A ¦ B", "Thema"]
    for n, topic in enumerate(topics):
        klasse = ("klein", "annahme", "gross")[n % 3]
        dl.append_row(root, SESSION, {"zeit": "2026-11-02T10:00:00", "thema": topic, "klasse": klasse,
                                      "frage": f"F{n}?", "entscheidung": "e", "beleg": "b", "regel": "—"})

    def old_silent(entry):
        hits, _ = dl.match_rules(rules, entry["thema"])
        return (any(r.kind == "nie fragen" for r in hits) and not any(r.kind == "immer fragen" for r in hits)
                and entry["klasse"] in ("klein", "annahme"))

    entries, _ = dl.log_entries(root, SESSION)
    visible = [e["frage"] for e in entries if not old_silent(e)]
    hidden = len(entries) - len(visible)
    assert 0 < hidden < len(entries) and len(visible) > dl.SUMMARY_LIMIT

    def no_match_rules(*_):
        raise AssertionError("summary ruft match_rules je Eintrag auf")

    monkeypatch.setattr(dl, "match_rules", no_match_rules)
    code, text = dl.summary(root, SESSION, home)
    assert code == 0
    lines = text.splitlines()
    assert lines[0] == f"Einträge der Sitzung {SESSION}: {len(visible)}"
    assert f"ausgelassen per nie fragen: {hidden}" in lines
    shown_questions = [re.search(r": (F\d+\?) →", line).group(1) for line in lines if line.startswith("- ")]
    assert shown_questions == visible[-dl.SUMMARY_LIMIT:]


# --- Funde des Prüfpunkts 1, Runde 3 (F1–F5) --------------------------------------------
# Die Sperre gilt je offener Datei; geprüft wird sie darum mit echten Unterprozessen.

_LOAD = """
import importlib.util, sys, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("decide_log", sys.argv[1])
dl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dl)
"""
HOLDER = _LOAD + """
with dl.log_lock(Path(sys.argv[2])):
    print("gesperrt", flush=True)
    time.sleep(60)
"""
WRITER = _LOAD + """
dl.LOCK_WAIT = 20                       # die Prozesse warten hier aufeinander, nicht auf die Uhr
read_log = dl.read_log

def slow_read(*args):                   # Lesen und Ersetzen weit auseinander: ohne Sperre geht eine Zeile verloren
    text = read_log(*args)
    time.sleep(0.2)
    return text

dl.read_log = slow_read
sys.exit(dl.main(["add", "--class", "klein", "--topic", "CLI", "--question", sys.argv[2],
                  "--decision", "kurz", "--evidence", "gesucht: cli.py — Treffer: cli.py:3"]))
"""


def script_path():
    return str(Path(dl.__file__).resolve())


HOLD_TIMEOUT = 10                       # Sekunden, die hold_lock auf „gesperrt“ wartet


@contextmanager
def hold_lock(root):
    """Kindprozess, der die Sperre des Protokolls hält, solange der Block läuft. Meldet er nicht
    binnen `HOLD_TIMEOUT` Sekunden „gesperrt“, scheitert die Prüfung; beendet wird er in jedem Fall."""
    child = subprocess.Popen([sys.executable, "-c", HOLDER, script_path(), str(log_file(root))],
                             stdout=subprocess.PIPE, text=True)
    lines = []
    reader = threading.Thread(target=lambda: lines.append(child.stdout.readline()), daemon=True)
    try:
        reader.start()
        reader.join(HOLD_TIMEOUT)
        assert lines and lines[0].strip() == "gesperrt", f"Kind meldet nicht „gesperrt“ binnen {HOLD_TIMEOUT} s"
        yield child
    finally:
        child.kill()
        child.wait()
        reader.join(5)
        child.stdout.close()


def test_concurrent_add_in_processes_keeps_every_row(decide_repo):
    """R3-F1: Vier add in eigenen Prozessen gleichzeitig verlieren keine Zeile; die Sperrdatei bleibt liegen."""
    root, _ = decide_repo
    assert add_small("CLI", "Vorher?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    children = [subprocess.Popen([sys.executable, "-c", WRITER, script_path(), f"Frage {n}?"], cwd=root,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for n in range(4)]
    results = [child.communicate(timeout=60) + (child.returncode,) for child in children]
    assert [code for _, _, code in results] == [0, 0, 0, 0], results
    assert sorted(r[3] for r in rows(root)) == ["Frage 0?", "Frage 1?", "Frage 2?", "Frage 3?", "Vorher?"]
    assert log_file(root).with_name("log.md.lock").exists()


def test_held_lock_ends_with_exit_1_after_wait(decide_repo, monkeypatch, capsys):
    """R3-F1: Hält ein zweiter Prozess die Sperre, endet add nach LOCK_WAIT mit 1 und nennt den Pfad."""
    root, _ = decide_repo
    assert add_small("CLI", "Vorher?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    monkeypatch.setattr(dl, "LOCK_WAIT", 0.3)
    with hold_lock(root):
        capsys.readouterr()
        started = time.monotonic()
        assert add_small("CLI", "Danach?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 1
        waited = time.monotonic() - started
    err = capsys.readouterr().err
    assert waited >= 0.3, waited
    assert "Protokoll gesperrt" in err and f".skills/cache/decide/{SESSION}/log.md.lock" in err, err
    assert "nichts geschrieben" in err and len(err.strip().splitlines()) == 1, err
    assert [r[3] for r in rows(root)] == ["Vorher?"]


def test_process_end_releases_lock(decide_repo, monkeypatch, capsys):
    """R3-F1: Endet der Prozess, der die Sperre hält (hier per kill), ist sie frei; die Datei bleibt."""
    root, _ = decide_repo
    monkeypatch.setattr(dl, "LOCK_WAIT", 0.3)
    with hold_lock(root) as child:
        child.kill()
        child.wait()
    lock = log_file(root).with_name("log.md.lock")
    assert lock.exists()
    assert add_small("CLI", "Danach?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0, capsys.readouterr().err
    assert [r[3] for r in rows(root)] == ["Danach?"]
    assert lock.exists()


def test_without_lock_module_writes_visibly(decide_repo, monkeypatch, capsys):
    """R3-F1: Gibt es weder fcntl noch msvcrt, schreibt add ohne Sperre und sagt das."""
    root, _ = decide_repo
    monkeypatch.setattr(dl, "fcntl", None)
    monkeypatch.setattr(dl, "msvcrt", None)
    assert add_small("CLI", "Kurzoption?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    assert "ohne Sperre" in capsys.readouterr().out
    assert len(rows(root)) == 1


def test_bare_dot_is_like_dot_slash(decide_repo, monkeypatch, tmp_path):
    """R3-F2: Ein nacktes `.` gilt wie `./` relativ zum Arbeitsverzeichnis."""
    root, _ = decide_repo
    assert dl.normalize_evidence("gesucht: . — nichts gefunden", root) == "gesucht: . — nichts gefunden"
    (root / "src").mkdir()
    monkeypatch.chdir(root / "src")
    assert dl.normalize_evidence("gesucht: . — nichts gefunden", root) == "gesucht: src — nichts gefunden"
    assert dl.normalize_evidence("gesucht: ., ./ — nichts gefunden", root) == "gesucht: src, src — nichts gefunden"
    monkeypatch.chdir(tmp_path)                     # außerhalb der Wurzel bleibt es, wie es steht
    assert dl.normalize_evidence("gesucht: . — nichts gefunden", root) == "gesucht: . — nichts gefunden"


def test_non_word_topic_needs_end_boundary(decide_repo):
    """R3-F3: `.net` ist ein Hinweis zu `ASP.NET`, aber nicht zu `config.network`."""
    root, home = decide_repo
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: .net\n")
    rules = dl.load_rules(root, home)
    assert dl.match_rules(rules, "config.network") == ([], [])
    assert dl.match_rules(rules, "ASP.NET") == ([], rules)
    assert dl.match_rules(rules, "ASP.NET Core") == ([], rules)


def test_decide_rows_fails_on_row_with_wrong_cell_count(decide_repo):
    """R3-F4: decide_rows scheitert, wenn eine Tabellenzeile beim Parsen wegfiele."""
    root, _ = decide_repo
    assert add_small("CLI", "Kurzoption?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    path = log_file(root)
    path.write_text(path.read_text(encoding="utf-8") + "| a | b | c | d | e | f | g | h |\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="Tabellenzeilen"):
        rows(root)


def test_write_atomic_keeps_original_error(tmp_path, monkeypatch):
    """R3-F5: Wirft das Aufräumen der Nachbardatei, bleibt der Fehler von os.replace sichtbar."""
    real_unlink = Path.unlink

    def replace_fails(src, dst):
        raise PermissionError(13, "replace verweigert", str(src))

    def unlink_fails(self, *args, **kwargs):
        if self.name.endswith(".tmp"):
            raise PermissionError(13, "unlink verweigert", str(self))
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(dl.os, "replace", replace_fails)
    monkeypatch.setattr(dl.time, "sleep", lambda _: None)
    monkeypatch.setattr(Path, "unlink", unlink_fails)
    with pytest.raises(PermissionError, match="replace verweigert"):
        dl.write_atomic(tmp_path / "log.md", "x\n")


# --- Funde des Prüfpunkts 1, Mini-Runde 4 (F1–F4) ---------------------------------------

@pytest.mark.parametrize("name", ["ENOLCK", "EOPNOTSUPP", "ENOSYS"])
def test_filesystem_without_flock_writes_visibly(decide_repo, monkeypatch, capsys, name):
    """R4-F1/F4: Kann das Dateisystem nicht sperren (z. B. CIFS: flock → ENOLCK), schreibt add
    ohne Sperre und nennt die Ursache — statt mit „nicht schreibbar“ zu scheitern."""
    root, _ = decide_repo
    code = getattr(errno, name)

    def no_flock(fd):
        raise OSError(code, os.strerror(code))

    monkeypatch.setattr(dl, "_try_lock", no_flock)
    assert add_small("CLI", "Kurzoption?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    out = capsys.readouterr().out
    assert f"ohne Sperre geschrieben ({os.strerror(code)})" in out, out
    assert [r[3] for r in rows(root)] == ["Kurzoption?"]


def test_msvcrt_lock_is_released_before_close(decide_repo, monkeypatch):
    """R4-F2: Unter Windows wird der gesperrte Bereich vor os.close mit LK_UNLCK an Offset 0 freigegeben."""
    root, _ = decide_repo
    calls = []
    real_close = os.close

    def locking(fd, mode, nbytes):
        calls.append(("locking", mode, nbytes, os.lseek(fd, 0, os.SEEK_CUR)))

    def close(fd):
        calls.append(("close", fd))
        real_close(fd)

    monkeypatch.setattr(dl, "fcntl", None)
    monkeypatch.setattr(dl, "msvcrt", SimpleNamespace(LK_NBLCK="NB", LK_UNLCK="UN", locking=locking))
    monkeypatch.setattr(dl.os, "close", close)
    with dl.log_lock(log_file(root)):
        assert calls == [("locking", "NB", 1, 0)]
    assert [c[0] for c in calls] == ["locking", "locking", "close"], calls
    assert calls[1] == ("locking", "UN", 1, 0), calls


SILENT = "import time\ntime.sleep(4)\n"


def test_hold_lock_gives_up_and_ends_child(decide_repo, monkeypatch):
    """R4-F3: Schreibt das Kind nie „gesperrt“, scheitert hold_lock nach der Zeitgrenze, und das Kind ist beendet."""
    root, _ = decide_repo
    started = []

    class Recording(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            started.append(self)

    monkeypatch.setattr(subprocess, "Popen", Recording)
    monkeypatch.setitem(globals(), "HOLDER", SILENT)
    monkeypatch.setitem(globals(), "HOLD_TIMEOUT", 0.5)
    begin = time.monotonic()
    with pytest.raises(AssertionError):
        with hold_lock(root):
            pass
    assert time.monotonic() - begin < 3
    assert len(started) == 1 and started[0].poll() is not None


# --- Task 2: Ablage großer Fragen, Freigabe, Antwort, offene Fragen ---------------------

def ledger_text(root):
    return (root / "docs" / "big-decisions.md").read_text(encoding="utf-8")


def big(*extra, topic="Abhängigkeiten", question="Datumsangaben parsen?", key="dependency:pyproject.toml"):
    """`decide_log.py add --class gross …` über `main`; gibt den Exit-Code zurück."""
    args = ["add", "--class", "gross"]
    for flag, value in (("--topic", topic), ("--question", question), ("--key", key)):
        if value is not None:
            args += [flag, value]
    return dl.main(args + list(extra))


TWO = ("--option", "A: python-dateutil", "--option", "B: strptime", "--recommendation", "B, weil Stdlib")


def test_upgrade_writes_rule_key_block(decide_repo):
    """Abnehmer-Test Task 2: add_small mit Regeltreffer immer fragen und zwei --option legt einen
    Block mit `Schlüssel: rule:UI-Texte` an."""
    root, home = decide_repo
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: UI-Texte\n")
    args = SimpleNamespace(topic="ui-texte", question="Text der Fehlermeldung?", decision="B: „Datei fehlt“",
                           evidence="gesucht: app/cli.py — Treffer: app/cli.py:12",
                           options=["A: „Fehler“", "B: „Datei fehlt“"], home=home)
    code, message = dl.add_small(root, SESSION, args)
    assert code == 0, message
    text = ledger_text(root)
    assert "\nSchlüssel: rule:UI-Texte\n" in text
    assert "\nThema: UI-Texte\n" in text
    assert "\nEmpfehlung: B: „Datei fehlt“\n" in text
    assert re.search(r"(?m)^## D-1 · \d{4}-\d{2}-\d{2} · offen$", text)


def test_option_count(decide_repo, capsys):
    root, home = decide_repo
    # eine oder fünf Optionen: Exit 1, keine Datei, keine Zeile
    assert big("--option", "A: x", "--recommendation", "A") == 1
    assert "zwei bis vier --option" in capsys.readouterr().err
    five = [a for n in range(5) for a in ("--option", f"{n}: x")]
    assert big(*five, "--recommendation", "A") == 1
    assert "zwei bis vier --option" in capsys.readouterr().err
    assert not (root / "docs").exists()
    assert not log_file(root).exists()

    # Pflichtfelder: ohne --recommendation, ohne --question → Exit 1
    assert big("--option", "A: x", "--option", "B: y") == 1
    assert "--recommendation" in capsys.readouterr().err
    assert big(*TWO, question=None) == 1
    assert "--question" in capsys.readouterr().err
    # unbekannte Kategorie, leeres Pfadmuster
    assert big(*TWO, key="frontend:app/") == 1
    assert "frontend" in capsys.readouterr().err
    assert big(*TWO, key="dependency:") == 1
    capsys.readouterr()
    # rule:X ohne Regel zu X
    assert big(*TWO, topic="X", key="rule:X") == 1
    assert "immer fragen" in capsys.readouterr().err
    assert not (root / "docs").exists()

    # Hochstufung ohne --option
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: UI-Texte\n")
    assert add_small("UI-Texte", "Text?", "kurz", "gesucht: a.py — Treffer: a.py:1") == 1
    assert "Regel immer fragen: UI-Texte trifft — zwei bis vier --option nötig" in capsys.readouterr().err
    assert not (root / "docs").exists()

    # rule:<thema> mit Regel: zulässig
    assert big(*TWO, topic="ui-texte", key="rule:ui-texte") == 0
    text = ledger_text(root)
    assert "\nSchlüssel: rule:UI-Texte\n" in text and "\nThema: UI-Texte\n" in text

    # --approved-by-request ohne Optionen schreibt den Block
    capsys.readouterr()
    assert big("--approved-by-request", "nimm python-dateutil auf") == 0
    text = ledger_text(root)
    block = text[text.index("## D-2"):]
    assert "\nOptionen: — (Auftrag)\n" in block
    assert re.search(r"(?m)^## D-2 · .* · freigegeben$", text)
    # mit Auftrag rule:<thema> nur, wenn eine Regel immer fragen das Thema trifft (CP2-F15)
    assert big("--approved-by-request", "ändere den Text", topic="X", key="rule:X") == 1
    assert "immer fragen" in capsys.readouterr().err


def test_big_entry_is_log_row(decide_repo, capsys):
    """Ein großer Eintrag steht zusätzlich als Protokollzeile `gross` mit `D-<n>`."""
    root, _ = decide_repo
    assert big(*TWO) == 0
    [row] = rows(root)
    assert row[1:5] == ["Abhängigkeiten", "gross", "Datumsangaben parsen?", "D-1"]
    out = capsys.readouterr().out
    assert "angelegt: docs/big-decisions.md" in out and "D-1" in out


def test_ids_count_up(decide_repo, capsys):
    root, _ = decide_repo
    assert big(*TWO) == 0
    assert "angelegt: docs/big-decisions.md" in capsys.readouterr().out
    assert dl.main(["resolve", "D-1", "--answer", "B"]) == 0
    assert big(*TWO, question="Zweite Frage?") == 0
    assert "angelegt" not in capsys.readouterr().out
    text = ledger_text(root)
    assert re.findall(r"(?m)^## (D-\d+) ", text) == ["D-1", "D-2"]
    assert [r[4] for r in rows(root)] == ["D-1", "D-2"]


def test_reject(decide_repo, capsys):
    root, _ = decide_repo
    assert big(*TWO) == 0
    assert dl.main(["resolve", "D-1", "--reject"]) == 0
    text = ledger_text(root)
    assert re.search(r"(?m)^## D-1 · .* · abgelehnt$", text)
    assert "\nQuelle der Antwort: Nutzer in Sitzung\n" in text
    capsys.readouterr()
    # unbekannte ID, keine Antwort: Exit 1, Datei unverändert
    assert dl.main(["resolve", "D-7", "--answer", "B"]) == 1
    assert "D-7" in capsys.readouterr().err
    assert dl.main(["resolve", "D-1"]) == 1
    assert "--answer" in capsys.readouterr().err
    assert ledger_text(root) == text


def test_read_ledger_shape(decide_repo):
    """Rückgabe von read_ledger für Task 3: Liste von dicts je Block, Problem None."""
    root, _ = decide_repo
    assert big(*TWO) == 0
    assert big("--approved-by-request", "lösch die Spalte", topic="Migrationen", question="Spalte weg?",
               key="migration:migrations/") == 0
    blocks, problem = dl.read_ledger(root)
    assert problem is None
    assert [(b["id"], b["number"], b["status"], b["key"]) for b in blocks] == [
        ("D-1", 1, "offen", "dependency:pyproject.toml"),
        ("D-2", 2, "freigegeben", "migration:migrations/")]
    assert blocks[0]["options"] == ["A: python-dateutil", "B: strptime"]
    assert blocks[0]["recommendation"] == "B, weil Stdlib"
    assert blocks[1]["options"] == []
    assert blocks[1]["source"] == "Auftrag: „lösch die Spalte“"
    assert dl.read_ledger(root / "nirgends") == ([], None)


def test_ledger_lock_lives_in_cache(decide_repo):
    """Die Sperre der Ablage liegt unter .skills/cache/decide/, nicht neben docs/big-decisions.md."""
    root, _ = decide_repo
    assert big(*TWO) == 0
    assert sorted(p.name for p in (root / "docs").iterdir()) == ["big-decisions.md"]
    assert (root / ".skills" / "cache" / "decide" / "big-decisions.md.lock").exists()


@pytest.mark.parametrize("head, reason", [
    ("# Große Entscheidungen\n", "ohne Kopfzeile von decide"),
    ("<!-- skill: decide | schema: 2 | generated: python decide_log.py add -->\n",
     "docs/big-decisions.md schema 1 erwartet, 2 gefunden — Freigaben übersprungen"),
])
def test_consumer_rule_ledger(decide_repo, capsys, head, reason):
    root, _ = decide_repo
    path = root / "docs" / "big-decisions.md"
    path.parent.mkdir()
    original = head + "\n## D-1 · 2026-11-01 · offen\nFrage: x?\nSchlüssel: api:openapi.yaml\n"
    path.write_text(original, encoding="utf-8")
    blocks, problem = dl.read_ledger(root)
    assert blocks == [] and reason in problem and "übersprungen" in problem
    assert dl.main(["open"]) == 1
    assert reason in capsys.readouterr().err
    assert big(*TWO) == 1
    assert "nichts geschrieben" in capsys.readouterr().err
    assert dl.main(["resolve", "D-1", "--answer", "B"]) == 1
    capsys.readouterr()
    assert path.read_text(encoding="utf-8") == original
    assert not log_file(root).exists()


def test_open_without_ledger(decide_repo, capsys):
    assert dl.main(["open"]) == 0
    assert "Keine offenen großen Fragen" in capsys.readouterr().out


# --- Funde des Prüfpunkts 2 (F1–F15) ----------------------------------------------------

def blocks_in(root):
    return re.findall(r"(?m)^## (D-\d+) ", ledger_text(root))


def test_big_retry_after_log_failure_keeps_one_block(decide_repo, monkeypatch, capsys):
    """CP2-F1: Scheitert die Protokollzeile, legt ein Wiederholungsaufruf keinen zweiten Block an,
    sondern nennt „D-1 steht schon“ und holt nur die Protokollzeile nach."""
    root, _ = decide_repo
    monkeypatch.setattr(dl, "LOCK_WAIT", 0.3)
    with hold_lock(root):
        assert big(*TWO) == 1
    assert "Protokollzeile für D-1 fehlt" in capsys.readouterr().err
    assert blocks_in(root) == ["D-1"]
    for _ in range(2):
        assert big(*TWO) == 0
        out = capsys.readouterr().out
        assert "D-1 steht schon" in out, out
        assert blocks_in(root) == ["D-1"]
        assert [r[4] for r in rows(root)] == ["D-1"]
    # eine andere Frage ist ein neuer Block; dieselbe Frage nach der Antwort nicht (Final-F3)
    assert big(*TWO, question="Andere Frage?") == 0
    assert dl.main(["resolve", "D-1", "--answer", "B"]) == 0
    capsys.readouterr()
    assert big(*TWO) == 0
    assert "D-1 ist schon freigegeben (Antwort: B)" in capsys.readouterr().out
    assert blocks_in(root) == ["D-1", "D-2"]
    # per Auftrag: derselbe Auftrag ein zweites Mal legt ebenfalls keinen Block an
    assert big("--approved-by-request", "nimm python-dateutil auf", question="Auftrag?") == 0
    assert big("--approved-by-request", "nimm python-dateutil auf", question="Auftrag?") == 0
    assert "D-3 steht schon" in capsys.readouterr().out
    assert blocks_in(root) == ["D-1", "D-2", "D-3"]
    assert [r[4] for r in rows(root)] == ["D-1", "D-2", "D-3"]


def test_resolve_finds_empty_and_spaced_fields(decide_repo):
    """CP2-F2: Ein von Hand geleertes „Antwort:“ oder „Quelle der Antwort :“ wird gefunden und
    ersetzt, statt eine zweite Zeile anzulegen."""
    root, _ = decide_repo
    assert big(*TWO) == 0
    path = root / "docs" / "big-decisions.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("\nQuelle der Antwort: —\n", "\nQuelle der Antwort :  \n")
    text = text.replace("\nAntwort: —\n", "\nAntwort:\n")
    path.write_text(text, encoding="utf-8")
    assert dl.read_ledger(root)[0][0]["answer"] == ""
    assert dl.main(["resolve", "D-1", "--answer", "B"]) == 0
    text = ledger_text(root)
    assert re.findall(r"(?m)^\s*Antwort\s*:.*$", text) == ["Antwort: B"], text
    assert re.findall(r"(?m)^\s*Quelle der Antwort\s*:.*$", text) == ["Quelle der Antwort: Nutzer in Sitzung"], text


def test_resolve_only_open_blocks(decide_repo, capsys):
    """CP2-F3: resolve ändert nur offene Blöcke; sonst Exit 1 mit Status und Quelle, nichts geschrieben."""
    root, _ = decide_repo
    assert big("--approved-by-request", "nimm python-dateutil auf") == 0
    before = ledger_text(root)
    capsys.readouterr()
    assert dl.main(["resolve", "D-1", "--reject"]) == 1
    err = capsys.readouterr().err
    assert "freigegeben" in err and "Auftrag: „nimm python-dateutil auf“" in err, err
    assert "nichts geschrieben" in err, err
    assert ledger_text(root) == before
    assert big(*TWO, question="Zweite?") == 0
    assert dl.main(["resolve", "D-2", "--answer", "B"]) == 0
    before = ledger_text(root)
    capsys.readouterr()
    assert dl.main(["resolve", "D-2", "--reject"]) == 1
    err = capsys.readouterr().err
    assert "freigegeben" in err and "Nutzer in Sitzung" in err, err
    assert ledger_text(root) == before


def test_key_category_and_pattern_trimmed(decide_repo, capsys):
    """CP2-F4: Leerraum um Kategorie und Pfadmuster fällt weg; Leerraum im Muster wird abgewiesen."""
    root, _ = decide_repo
    assert big(*TWO, key="dependency: pyproject.toml") == 0
    assert big(*TWO, question="Zweite?", key="dependency :pyproject.toml #python-dateutil") == 0
    assert [b["key"] for b in dl.read_ledger(root)[0]] == [
        "dependency:pyproject.toml", "dependency:pyproject.toml#python-dateutil"]
    capsys.readouterr()
    assert big(*TWO, question="Dritte?", key="dependency:pyproject\t.toml") == 1   # Leerzeichen: CP2-R2-F7
    assert "Tab oder Zeilenumbruch" in capsys.readouterr().err
    assert blocks_in(root) == ["D-1", "D-2"]


def test_resolve_notes_unversioned_cache(decide_repo, capsys):
    """CP2-F5: Legt resolve .skills/cache/ an (frischer Clone), kommt derselbe Hinweis wie bei add."""
    root, _ = decide_repo
    assert big(*TWO) == 0
    assert big(*TWO, question="Zweite?") == 0
    shutil.rmtree(root / ".skills")
    capsys.readouterr()
    assert dl.main(["resolve", "D-1", "--answer", "B"]) == 0
    assert ".skills/cache/ steht nicht in der .gitignore" in capsys.readouterr().out
    (root / ".gitignore").write_text(".skills/cache/\n", encoding="utf-8")
    shutil.rmtree(root / ".skills")
    assert dl.main(["resolve", "D-2", "--answer", "B"]) == 0
    assert ".gitignore" not in capsys.readouterr().out


def test_resolve_without_lock_says_so(decide_repo, monkeypatch, capsys):
    """CP2-F6: Schreibt resolve ohne Sperre, nennt die Meldung die Ursache wie add."""
    root, _ = decide_repo
    assert big(*TWO) == 0

    def no_flock(fd):
        raise OSError(errno.ENOLCK, os.strerror(errno.ENOLCK))

    monkeypatch.setattr(dl, "_try_lock", no_flock)
    capsys.readouterr()
    assert dl.main(["resolve", "D-1", "--answer", "B"]) == 0
    out = capsys.readouterr().out
    assert f"ohne Sperre geschrieben ({os.strerror(errno.ENOLCK)})" in out, out


def test_ledger_with_bom(decide_repo, capsys):
    """CP2-F7: Eine mit BOM gespeicherte Ablage wird gelesen; geschrieben wird ohne BOM."""
    root, _ = decide_repo
    assert big(*TWO) == 0
    path = root / "docs" / "big-decisions.md"
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert dl.read_ledger(root)[1] is None
    capsys.readouterr()
    assert dl.main(["open"]) == 0
    assert "D-1" in capsys.readouterr().out
    assert big(*TWO, question="Zweite?") == 0
    assert dl.main(["resolve", "D-1", "--answer", "B"]) == 0
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert blocks_in(root) == ["D-1", "D-2"]


def test_header_problem_keeps_path(decide_repo, capsys):
    """CP2-F8: Das Satzende kommt aus header_problem; ein Pfad mit „übersprungen“ bleibt, wie er ist."""
    root, _ = decide_repo
    session = "x-übersprungen"
    path = log_file(root, session)
    path.parent.mkdir(parents=True)
    path.write_text("# kein Kopf\n", encoding="utf-8")
    want = f".skills/cache/decide/{session}/log.md ohne Kopfzeile von decide — nichts geschrieben"
    assert add_small("CLI", "Kurzoption?", "kurz", "gesucht: cli.py — Treffer: cli.py:3", "--session", session) == 1
    assert want in capsys.readouterr().err
    assert big(*TWO, "--session", session) == 1
    assert want in capsys.readouterr().err
    assert dl.main(["summary", "--session", session]) == 1
    assert f".skills/cache/decide/{session}/log.md ohne Kopfzeile von decide — übersprungen" in capsys.readouterr().err


def test_big_reports_contradiction(decide_repo, capsys):
    """CP2-F9: add_big meldet den Widerspruch immer/nie fragen, die Spalte regel nennt die geltende Regel."""
    root, home = decide_repo
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: Migrationen\n")
    write_rules(home / ".skills" / "decide" / "rules.md", "nie fragen: Migrationen\n")
    assert big(*TWO, topic="migrationen", question="Spalte weg?", key="migration:migrations/") == 0
    out = capsys.readouterr().out
    assert ("Widerspruch: immer fragen: Migrationen (.skills/decide/rules.md) und nie fragen: Migrationen "
            "(~/.skills/decide/rules.md) — immer fragen gilt.") in out, out
    [row] = rows(root)
    assert row[6] == "immer fragen: Migrationen"


def test_ignored_flags_warning_follows_upgrade(decide_repo, monkeypatch, capsys):
    """CP2-F13: Die Warnung zu ignorierten Angaben nennt die Hochstufung genau dann, wenn add_small
    hochgestuft hat — auch wenn sich die Regeln zwischen zwei Lesevorgängen ändern würden."""
    root, home = decide_repo
    flags = ("--option", "A: kurz", "--option", "B: lang", "--recommendation", "A")
    assert add_small("UI-Texte", "Text?", "A", "gesucht: a.py — Treffer: a.py:1", *flags) == 0
    err = capsys.readouterr().err
    assert "bei einer kleinen Entscheidung ignoriert" in err and "--option" in err, err

    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: UI-Texte\n")
    assert add_small("UI-Texte", "Text 2?", "A", "gesucht: a.py — Treffer: a.py:1", *flags) == 0
    err = capsys.readouterr().err
    assert "per Regel hochgestuften Frage" in err and "--option" not in err, err

    answers = [dl.read_rules(root, home)]    # zweiter Lesevorgang sähe die Regel nicht mehr
    calls = []

    def read_rules(*args):
        calls.append(args)
        return answers.pop(0) if answers else ([], [], [])

    monkeypatch.setattr(dl, "read_rules", read_rules)
    assert add_small("UI-Texte", "Text 3?", "A", "gesucht: a.py — Treffer: a.py:1", *flags) == 0
    err = capsys.readouterr().err
    assert "per Regel hochgestuften Frage" in err and "--option" not in err, err
    assert len(calls) == 1, calls             # R2-F7: Regeln und Hinweise aus einem Lesevorgang


def test_approved_request_with_rule_key(decide_repo, capsys):
    """CP2-F15: Ein konkreter Auftrag zu einem Thema einer Regel immer fragen wird mit rule:<thema>
    als freigegeben abgelegt (konkreter Auftrag vor Regel)."""
    root, _ = decide_repo
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: UI-Texte\n")
    assert big("--approved-by-request", "ändere die Meldung auf „Datei fehlt“", topic="ui-texte",
               question="Text der Fehlermeldung?", key="rule:ui-texte") == 0, capsys.readouterr().err
    [block] = dl.read_ledger(root)[0]
    assert (block["status"], block["key"], block["topic"]) == ("freigegeben", "rule:UI-Texte", "UI-Texte")
    assert block["source"] == "Auftrag: „ändere die Meldung auf „Datei fehlt““"


# --- Funde des Prüfpunkts 2, Runde 2 (F1–F9) --------------------------------------------

def concurrent_row(monkeypatch, root):
    """Zwischen dem Schreiben des Blocks und der Protokollzeile trägt ein zweites, gleiches add
    seine Zeile `gross | D-<n>` ein — so, wie es zwei gleichzeitige Prozesse tun können. Einmalig."""
    real = dl.append_block

    def append_block(*args):
        result = real(*args)
        monkeypatch.setattr(dl, "append_block", real)
        if result[0] is not None:
            dl.append_row(root, SESSION, {"zeit": "2026-11-02T10:00:00", "thema": "Abhängigkeiten",
                                          "klasse": "gross", "frage": args[2]["question"],
                                          "entscheidung": f"D-{result[0]}", "beleg": "—", "regel": "—"})
        return result

    monkeypatch.setattr(dl, "append_block", append_block)


def test_concurrent_same_big_writes_one_row(decide_repo, monkeypatch, capsys):
    """CP2-R2-F1: Ob die Zeile für D-<n> steht, prüft append_row unter der Sperre des Protokolls;
    zwei gleiche add --class gross gleichzeitig ergeben eine Zeile gross | D-1."""
    root, _ = decide_repo
    concurrent_row(monkeypatch, root)
    assert big(*TWO) == 0, capsys.readouterr().err          # neuer Block, die Zeile kam dazwischen
    assert [(r[2], r[4]) for r in rows(root)] == [("gross", "D-1")]
    assert "Protokollzeile für D-1 steht schon" in capsys.readouterr().out
    # Block steht schon ohne Zeile; beide Aufrufe sehen das, einer schreibt die Zeile zuerst
    monkeypatch.setattr(dl, "LOCK_WAIT", 0.3)
    with hold_lock(root):
        assert big(*TWO, question="Zweite?") == 1
    concurrent_row(monkeypatch, root)
    assert big(*TWO, question="Zweite?") == 0, capsys.readouterr().err
    assert [(r[2], r[4]) for r in rows(root)] == [("gross", "D-1"), ("gross", "D-2")]
    assert blocks_in(root) == ["D-1", "D-2"]


def test_same_question_other_options_is_refused(decide_repo, capsys):
    """CP2-R2-F2: Gleiche Frage und gleicher Schlüssel, aber andere Optionen oder Empfehlung:
    Exit 1, nichts geschrieben, statt still „steht schon“."""
    root, _ = decide_repo
    assert big(*TWO) == 0
    before, log_before = ledger_text(root), log_file(root).read_text(encoding="utf-8")
    capsys.readouterr()
    fixed = ("--option", "A: python-dateutil", "--option", "B: datetime.strptime", "--recommendation", "B, weil Stdlib")
    assert big(*fixed) == 1
    err = capsys.readouterr().err
    assert "D-1 steht offen mit anderen Optionen — von Hand ändern oder mit resolve beantworten" in err, err
    assert big("--option", "A: python-dateutil", "--option", "B: strptime", "--recommendation", "A") == 1
    assert "D-1 steht offen mit anderer Empfehlung" in capsys.readouterr().err    # CP2-R3-F4: Feld genannt
    assert ledger_text(root) == before
    assert log_file(root).read_text(encoding="utf-8") == log_before
    assert big(*TWO) == 0                                   # wirklich gleich: weiter „steht schon“
    assert "D-1 steht schon" in capsys.readouterr().out


def test_existing_open_block_repeats_instruction(decide_repo, monkeypatch, capsys):
    """CP2-R2-F3: Steht der offene Block schon, sagt die Ausgabe trotzdem, dass der Schritt bis zur
    Freigabe unterbleibt; „Protokollzeile … ergänzt“ nur, wenn sie wirklich fehlte."""
    root, _ = decide_repo
    instruction = "Bis zur Freigabe unterbleibt der Schritt; Antwort mit `resolve D-1 --answer \"…\"` oder `--reject`."
    monkeypatch.setattr(dl, "LOCK_WAIT", 0.3)
    with hold_lock(root):
        assert big(*TWO) == 1
    capsys.readouterr()
    assert big(*TWO) == 0                                   # andere Sitzung, gleiche offene Frage
    out = capsys.readouterr().out
    assert instruction in out and "Protokollzeile für D-1 ergänzt." in out, out
    assert "nachgetragen" not in out, out
    assert big(*TWO) == 0
    out = capsys.readouterr().out
    assert instruction in out and "Protokollzeile für D-1 steht schon." in out, out
    assert "ergänzt" not in out, out


def test_first_field_wins_for_read_and_resolve(decide_repo):
    """CP2-R2-F4: Steht ein Feld doppelt, gilt das erste — für parse_blocks wie für resolve."""
    root, _ = decide_repo
    assert big(*TWO) == 0
    path = root / "docs" / "big-decisions.md"
    path.write_text(ledger_text(root).rstrip("\n") + "\n  Antwort : siehe Chat\nOptionen:\n- C: später\n",
                    encoding="utf-8")
    [block] = dl.read_ledger(root)[0]
    assert block["answer"] == "—" and block["options"] == ["A: python-dateutil", "B: strptime"], block
    assert dl.main(["resolve", "D-1", "--answer", "B"]) == 0
    [block] = dl.read_ledger(root)[0]
    assert (block["status"], block["answer"]) == ("freigegeben", "B"), block


def test_resolve_notice_follows_cache_folder(decide_repo, monkeypatch, capsys):
    """CP2-R2-F5: resolve gibt den Hinweis zum unversionierten Ordner genau dann, wenn
    .skills/cache/ dabei entstand — nicht nach der Sperrdatei."""
    root, _ = decide_repo
    assert big(*TWO) == 0
    assert big(*TWO, question="Zweite?") == 0
    (root / ".skills" / "cache" / "decide" / "big-decisions.md.lock").unlink()   # Ordner bleibt
    capsys.readouterr()
    assert dl.main(["resolve", "D-1", "--answer", "B"]) == 0
    assert ".gitignore" not in capsys.readouterr().out
    shutil.rmtree(root / ".skills")
    monkeypatch.setattr(dl, "fcntl", None)
    monkeypatch.setattr(dl, "msvcrt", None)
    assert dl.main(["resolve", "D-2", "--answer", "B"]) == 0
    out = capsys.readouterr().out
    assert ".skills/cache/ steht nicht in der .gitignore" in out and "ohne Sperre" in out, out


def test_rules_and_template_with_bom(decide_repo, monkeypatch, tmp_path):
    """CP2-R2-F6: rules.md und die Vorlage werden mit utf-8-sig gelesen; ein BOM macht die erste
    Regel nicht ungültig und die Vorlage nicht unbrauchbar."""
    root, home = decide_repo
    rules = root / ".skills" / "decide" / "rules.md"
    rules.parent.mkdir(parents=True)
    rules.write_bytes(b"\xef\xbb\xbf" + "immer fragen: UI-Texte\n".encode("utf-8"))
    assert [(r.kind, r.topic) for r in dl.load_rules(root, home)] == [("immer fragen", "UI-Texte")]
    asset = tmp_path / "vorlage.md"
    asset.write_bytes(b"\xef\xbb\xbf" + (dl.LOG_HEADER + "\n\n# Große Entscheidungen (Vorlage)\n").encode("utf-8"))
    monkeypatch.setattr(dl, "LEDGER_ASSET", asset)
    assert add_small("UI-Texte", "Text?", "A: kurz", "gesucht: a.py — Treffer: a.py:1",
                     "--option", "A: kurz", "--option", "B: lang") == 0
    raw = (root / "docs" / "big-decisions.md").read_bytes()
    assert "# Große Entscheidungen (Vorlage)".encode("utf-8") in raw and not raw.startswith(b"\xef\xbb\xbf")
    assert "rule:UI-Texte" in ledger_text(root)


def test_key_pattern_with_inner_spaces(decide_repo, capsys):
    """CP2-R2-F7: Leerzeichen im Pfadmuster sind erlaubt, nur Rand-Leerraum fällt weg; Tab und
    Zeilenumbruch im Muster weist check_key weiter ab."""
    root, _ = decide_repo
    assert big(*TWO, key=" data-delete : docs/User Guides/*.md ") == 0, capsys.readouterr().err
    assert dl.read_ledger(root)[0][0]["key"] == "data-delete:docs/User Guides/*.md"
    for bad in ("data-delete:docs/User\tGuides/*.md", "data-delete:docs/User\nGuides/*.md"):
        assert big(*TWO, question="Zweite?", key=bad) == 1, bad
        assert "Tab oder Zeilenumbruch" in capsys.readouterr().err
    assert blocks_in(root) == ["D-1"]


# --- Funde des Prüfpunkts 2, Runde 3 (Mini-Runde F1–F4) ---------------------------------

def test_new_block_after_discarded_ledger_gets_its_row(decide_repo, capsys):
    """CP2-R3-F1: Wird die Ablage verworfen, bekommt ein neuer Block mit wiederverwendeter Nummer
    trotzdem seine Protokollzeile — eine alte Zeile mit derselben Nummer, aber anderer Frage
    verhindert sie nicht."""
    root, _ = decide_repo
    assert big(*TWO) == 0
    (root / "docs" / "big-decisions.md").unlink()
    capsys.readouterr()
    assert big(*TWO, question="Neue Frage?") == 0, capsys.readouterr().err
    out = capsys.readouterr().out
    assert "steht schon" not in out, out
    assert blocks_in(root) == ["D-1"]
    assert [(r[2], r[3], r[4]) for r in rows(root)] == [
        ("gross", "Datumsangaben parsen?", "D-1"), ("gross", "Neue Frage?", "D-1")]


def test_unversioned_notice_only_when_cache_appears_and_written(decide_repo, capsys):
    """CP2-R3-F2: Der Hinweis zu .skills/cache/ kommt genau dann, wenn der Ordner bei diesem
    Aufruf entstand und etwas geschrieben wurde — nicht in jeder neuen Sitzung, nicht nach einem
    resolve, das nichts geschrieben hat."""
    root, _ = decide_repo
    notice = ".skills/cache/ steht nicht in der .gitignore"
    assert add_small("CLI", "Kurz?", "ja", "gesucht: a.py — Treffer: a.py:1") == 0
    assert notice in capsys.readouterr().out
    assert add_small("CLI", "Kurz?", "ja", "gesucht: a.py — Treffer: a.py:1", "--session", "sitzung-2") == 0
    out = capsys.readouterr().out
    assert "Protokoll angelegt" in out and notice not in out, out
    assert big(*TWO, "--session", "sitzung-3") == 0
    out = capsys.readouterr().out
    assert "Protokoll angelegt" in out and notice not in out, out

    shutil.rmtree(root / ".skills")
    assert big(*TWO, question="Zweite?") == 0             # neuer Block legt den Ordner an
    assert notice in capsys.readouterr().out

    shutil.rmtree(root / ".skills")
    (root / "docs" / "big-decisions.md").unlink()
    assert dl.main(["resolve", "D-1", "--answer", "B"]) == 1
    captured = capsys.readouterr()
    assert "nichts geschrieben" in captured.err and notice not in captured.out + captured.err, captured


def test_unreadable_rules_are_reported(decide_repo, monkeypatch, capsys):
    """CP2-R3-F3: Eine unlesbare rules.md fällt nicht still weg — add und rules melden
    „Regeln <pfad> nicht lesbar (<Ursache>) — ohne diese Regeln eingeordnet“; eine fehlende bleibt still."""
    root, home = decide_repo
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: UI-Texte\n")
    unreadable(monkeypatch, "rules.md")
    want = "Regeln .skills/decide/rules.md nicht lesbar (Permission denied) — ohne diese Regeln eingeordnet"
    assert dl.load_rules(root, home) == []
    assert add_small("UI-Texte", "Text?", "kurz", "gesucht: a.py — Treffer: a.py:1") == 0
    captured = capsys.readouterr()
    assert want in captured.out + captured.err, captured
    assert big(*TWO) == 0
    captured = capsys.readouterr()
    assert want in captured.out + captured.err, captured
    assert dl.main(["rules"]) == 0
    assert want in capsys.readouterr().out
    assert "~/.skills" not in want                          # die fehlende Nutzerdatei bleibt still
    monkeypatch.undo()
    assert dl.main(["rules"]) == 0
    assert "nicht lesbar" not in capsys.readouterr().out


def test_same_block_by_request_and_normalized_file_values(decide_repo, capsys):
    """CP2-R3-F4: Ein wiederholter Auftrag vergleicht nur Frage, Schlüssel und Quelle; Werte aus
    der Datei werden wie die Argumente normalisiert; die Meldung nennt das abweichende Feld."""
    root, _ = decide_repo
    assert big("--approved-by-request", "nimm python-dateutil auf", question="Auftrag?") == 0
    assert big("--approved-by-request", "nimm python-dateutil auf", question="Auftrag?",
               *("--recommendation", "A")) == 0, capsys.readouterr().err
    assert "D-1 steht schon" in capsys.readouterr().out

    assert big(*TWO) == 0
    path = root / "docs" / "big-decisions.md"
    path.write_text(ledger_text(root).replace("Empfehlung: B, weil Stdlib", "Empfehlung: B,  weil Stdlib ")
                    .replace("- A: python-dateutil", "-  A:  python-dateutil"), encoding="utf-8")
    capsys.readouterr()
    assert big(*TWO) == 0, capsys.readouterr().err
    assert "D-2 steht schon" in capsys.readouterr().out
    assert blocks_in(root) == ["D-1", "D-2"]

    assert big("--option", "A: python-dateutil", "--option", "B: strptime", "--recommendation", "A") == 1
    err = capsys.readouterr().err
    assert "D-2 steht offen mit anderer Empfehlung — von Hand ändern" in err, err
    assert big("--option", "A: x", "--option", "B: strptime", "--recommendation", "B, weil Stdlib") == 1
    assert "D-2 steht offen mit anderen Optionen — von Hand ändern" in capsys.readouterr().err


# --- Task 3: check und references/reversibility.md --------------------------------------

LEDGER_HEAD = "<!-- skill: decide | schema: 1 | generated: python decide_log.py add -->\n\n# Große Entscheidungen\n"


def ledger_block(number, status, key, question="Frage?"):
    return (f"\n## D-{number} · 2026-11-02 · {status}\nFrage: {question}\nThema: T\nSchlüssel: {key}\n"
            "Optionen:\n- A: x\n- B: y\nEmpfehlung: B\nAntwort: —\nQuelle der Antwort: —\n")


def write_ledger(root, *blocks, head=LEDGER_HEAD):
    path = root / "docs" / "big-decisions.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(head + "".join(blocks), encoding="utf-8")
    return path


def test_read_ledger_gives_keys_with_status_for_check(decide_repo):
    """Abnehmer-Test Task 3: read_ledger auf einer von Hand geschriebenen Ablage mit einem
    freigegebenen und einem offenen Block liefert beide Schlüssel mit Status — mehr braucht check nicht."""
    root, _ = decide_repo
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml#python-dateutil"),
                 ledger_block(2, "offen", "migration:migrations/"))
    blocks, problem = dl.read_ledger(root)
    assert problem is None
    assert [(b["key"], b["status"]) for b in blocks] == [
        ("dependency:pyproject.toml#python-dateutil", "freigegeben"), ("migration:migrations/", "offen")]


def check_out(capsys, rev):
    """`main(["check", "--range=<rev>"])`; (exit, stdout, stderr). `=` lässt auch einen Bereich mit
    führendem `-` an argparse vorbei, damit check selbst ihn abweist."""
    code = dl.main(["check", f"--range={rev}"])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def reported(out):
    """Die gemeldeten Dateien, je Stelle eine Zeile „- <datei> — …“."""
    return [line[2:].split(" — ", 1)[0] for line in out.splitlines() if line.startswith("- ")]


def test_glob_matcher():
    def hits(pattern, path):
        return dl.glob_to_regex(pattern).fullmatch(path) is not None

    assert hits("db/**/*.sql", "db/schema.sql") and hits("db/**/*.sql", "db/a/b.sql")
    assert not hits("db/**/*.sql", "db/schema.sqlx") and not hits("db/**/*.sql", "x/db/schema.sql")
    assert hits("**/migrations/", "migrations/0002.py")
    assert hits("**/migrations/", "evals/fixtures/x/migrations/0001.py")
    assert not hits("**/migrations/", "app/migrations.py") and not hits("**/migrations/", "migrations")
    assert hits("requirements*.txt", "requirements-dev.txt") and not hits("requirements*.txt", "req/requirements.txt")
    assert hits("openapi.*", "openapi.yaml") and not hits("openapi.*", "api/openapi.yaml")
    assert not hits("*", "a/b") and hits("*", "ab") and not hits("a*", "a/b")
    assert hits("evals/fixtures/", "evals/fixtures/x/migrations/0001.py")
    assert hits("docs/User Guides/*.md", "docs/User Guides/a.md")
    assert hits("a?c", "abc") and not hits("a?c", "a/c")
    assert hits("a.b", "a.b") and not hits("a.b", "axb")              # alles andere wörtlich
    # `**/` am Ende eines Präfix-Musters: null oder mehr Ordner — direkte Kinder und tiefer
    assert hits("migrations/**/", "migrations/0001.py") and hits("migrations/**/", "migrations/a/b.py")
    assert not hits("migrations/**/", "migrations") and not hits("migrations/**/", "x/migrations/0001.py")
    assert hits("**/", "a.py") and hits("**/", "a/b.py")


def test_categories_from_reference():
    """Die Tabelle in references/reversibility.md liefert alle neun Kategorien mit Grad; die
    Schlusszeile von check entsteht aus ihr."""
    categories, problem = dl.load_categories(dl.REFERENCE)
    assert problem is None
    assert {name: c.grade for name, c in categories.items()} == {
        "api": "teilweise", "migration": "teilweise", "data-delete": "ungeprüft", "unsaved-work": "ungeprüft",
        "push": "ungeprüft", "external": "ungeprüft", "dependency": "teilweise", "permissions": "teilweise",
        "cost": "ungeprüft"}
    assert list(categories) == ["api", "migration", "data-delete", "unsaved-work", "push", "external",
                                "dependency", "permissions", "cost"]          # Reihenfolge der Schlusszeile
    assert "rule" not in categories                                 # rule vergleicht check nie
    assert categories["migration"].patterns == ("**/migrations/", "**/alembic/versions/", "db/**/*.sql")
    assert categories["dependency"].patterns == (
        "**/pyproject.toml", "**/requirements*.txt", "**/setup.py", "**/setup.cfg", "**/Pipfile", "**/package.json",
        "**/Cargo.toml", "**/go.mod", "**/Gemfile", "**/poetry.lock", "**/uv.lock", "**/Pipfile.lock",
        "**/package-lock.json", "**/yarn.lock", "**/pnpm-lock.yaml", "**/Cargo.lock", "**/go.sum", "**/Gemfile.lock")
    assert categories["permissions"].patterns == (".github/workflows/", "**/CODEOWNERS", ".claude/settings.json")
    assert categories["api"].patterns == ("openapi.*", "api/openapi.*")
    assert all(c.patterns == () for c in categories.values() if c.grade == "ungeprüft")
    assert all(c.meaning and c.meaning != "—" for c in categories.values())
    assert dl.tail_line(categories) == TAIL


def test_reference_missing_or_broken(decide_repo, monkeypatch, tmp_path, capsys):
    """Fehlt die Reference oder parst sie nicht: check endet mit 2 und dem Grund, nie mit Erfolg;
    add --class gross prüft Schlüssel gegen dieselbe Quelle."""
    root, _ = decide_repo
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    commit(root)
    monkeypatch.setattr(dl, "REFERENCE", tmp_path / "references" / "reversibility.md")
    code, out, err = check_out(capsys, "HEAD")
    assert code == 2 and "ungeprüft — references/reversibility.md fehlt" in err and out == ""

    ref = tmp_path / "references" / "reversibility.md"
    ref.parent.mkdir()
    ref.write_text("# Kategorien\n\nkeine Tabelle\n", encoding="utf-8")
    code, out, err = check_out(capsys, "HEAD")
    assert code == 2 and "ungeprüft — references/reversibility.md" in err and "Tabelle" in err, err
    head = "| Kategorie | Bedeutung | Beispiel | Grad | Pfadmuster | Grenze |\n| --- | --- | --- | --- | --- | --- |\n"
    ref.write_text(head + "| `api` | x | y | vielleicht | `openapi.*` | — |\n", encoding="utf-8")
    code, _, err = check_out(capsys, "HEAD")
    assert code == 2 and "vielleicht" in err, err
    ref.write_text(head + "| `api` | x | y | geprüft | — | — |\n", encoding="utf-8")
    code, _, err = check_out(capsys, "HEAD")
    assert code == 2 and "Pfadmuster" in err, err

    # dieselbe Quelle für add: eine zehnte Kategorie aus der Tabelle ist ein gültiger Schlüssel
    ref.write_text(head + "| `api` | x | y | teilweise | `openapi.*` | — |\n"
                   "| `infra` | Infrastruktur | Terraform | geprüft | `**/*.tf` | — |\n", encoding="utf-8")
    assert big(*TWO, key="infra:main.tf") == 0, capsys.readouterr().err
    assert big(*TWO, question="Zweite?", key="dependency:pyproject.toml") == 1
    assert "dependency" in capsys.readouterr().err
    ref.unlink()
    assert big(*TWO, question="Dritte?", key="api:openapi.yaml") == 1
    assert "references/reversibility.md fehlt" in capsys.readouterr().err
    assert big(*TWO, topic="UI-Texte", question="Vierte?", key="rule:UI-Texte") == 1   # ohne Regel weiter 1
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: UI-Texte\n")
    assert big(*TWO, topic="UI-Texte", question="Fünfte?", key="rule:UI-Texte") == 0  # rule braucht die Tabelle nicht


def test_check_untracked_and_hash_key(decide_repo, monkeypatch, tmp_path, capsys):
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "pyproject.toml").write_text("[project]\ndependencies = []\n", encoding="utf-8")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml#python-dateutil"))
    base = commit(root)

    # unversionierte Datei unter migrations/ wird gemeldet; ohne Änderung an pyproject.toml nur sie
    (root / "migrations").mkdir()
    (root / "migrations" / "0003_x.py").write_text("def up(): pass\n", encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["migrations/0003_x.py"], out
    assert out.splitlines()[-1] == TAIL

    # #python-dateutil: eine andere Abhängigkeit gibt die Datei nicht frei …
    (root / "pyproject.toml").write_text('[project]\ndependencies = ["requests"]\n', encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["migrations/0003_x.py", "pyproject.toml"], out
    line = next(line for line in out.splitlines() if line.startswith("- pyproject.toml"))
    assert "D-1" in line and "python-dateutil" in line, line
    # … eine hinzugefügte Zeile mit dem Text gibt sie frei, samt weiterer Änderungen in der Datei
    (root / "pyproject.toml").write_text('[project]\nname = "neu"\ndependencies = [\n  "python-dateutil>=2",\n]\n',
                                         encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert reported(out) == ["migrations/0003_x.py"], out
    # der Text in einer entfernten Zeile gibt nicht frei (Final-R2-F1): Entfernen braucht #-<text>
    after = commit(root)
    (root / "pyproject.toml").write_text('[project]\nname = "neu"\ndependencies = []\n', encoding="utf-8")
    code, out, _ = check_out(capsys, after)
    assert code == 1 and reported(out) == ["pyproject.toml"], out
    assert "„python-dateutil“ in keiner hinzugefügten Zeile" in out, out
    git(root, "checkout", "-q", "--", "pyproject.toml")

    # <a>..<b> lässt Arbeitsbaum und unversionierte Dateien aus
    (root / "migrations" / "0004_y.py").write_text("def up(): pass\n", encoding="utf-8")
    code, out, _ = check_out(capsys, f"{base}..{after}")
    assert code == 1 and reported(out) == ["migrations/0003_x.py"], out
    code, out, _ = check_out(capsys, f"{after}..{after}")
    assert code == 0 and "Keine Stelle ohne Freigabe" in out and out.splitlines()[-1] == TAIL, out
    # A^! und A^-<n> sind Bereiche (ein Commit gegen seine Eltern): ohne Arbeitsbaum und ohne
    # unversionierte Dateien; pyproject.toml gibt dort „python-dateutil>=2“ frei
    (root / "migrations" / "0005.py").write_text("def up(): pass\n", encoding="utf-8")
    for rev in ("HEAD^!", "HEAD^-1", "HEAD^-"):
        code, out, _ = check_out(capsys, rev)
        assert code == 1 and reported(out) == ["migrations/0003_x.py"], (rev, out)
    # eine einzelne Revision nimmt sie dazu
    code, out, _ = check_out(capsys, after)
    assert reported(out) == ["migrations/0004_y.py", "migrations/0005.py"], out

    # ein Bereich, den Git nicht kennt, oder einer, der wie eine Option aussieht: Exit 2
    code, out, err = check_out(capsys, "gibtsnicht")
    assert code == 2 and "ungeprüft" in err and "gibtsnicht" in err, err
    code, out, err = check_out(capsys, "--output=x")
    assert code == 2 and not (root / "x").exists()

    # ohne Git Exit 2: kein Repo, und kein git im PATH
    plain = tmp_path / "ohne-git"
    plain.mkdir()
    (plain / "pyproject.toml").write_text("x\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.chdir(plain)
    code, out, err = check_out(capsys, "HEAD")
    assert code == 2 and "ungeprüft — kein Git" in err and err.splitlines()[-1] == TAIL, err
    monkeypatch.chdir(root)
    empty = tmp_path / "leer"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert dl.check(root, "HEAD")[0] == 2
    assert "ungeprüft — kein Git" in dl.check(root, "HEAD")[1]


def test_consumer_rule_check(decide_repo, monkeypatch, capsys):
    """Ablage mit `schema: 2`: Freigaben übersprungen, sichtbar — check meldet jede Stelle."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    base = commit(root)
    head2 = "<!-- skill: decide | schema: 2 | generated: python decide_log.py add -->\n"
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"),
                 ledger_block(2, "freigegeben", "migration:migrations/"), head=head2)
    (root / "pyproject.toml").write_text("[project]\ndependencies = ['x']\n", encoding="utf-8")
    (root / "migrations").mkdir()
    (root / "migrations" / "0002.py").write_text("x\n", encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 1, out
    assert reported(out) == ["migrations/0002.py", "pyproject.toml"], out
    assert "docs/big-decisions.md schema 1 erwartet, 2 gefunden — Freigaben übersprungen" in out
    assert out.splitlines()[-1] == TAIL
    # ohne Kopfzeile ebenso
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"), head="# Große Entscheidungen\n")
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["migrations/0002.py", "pyproject.toml"], out
    assert "ohne Kopfzeile von decide — Freigaben übersprungen" in out


def test_check_key_matching(decide_repo, monkeypatch, capsys):
    """Eine Freigabe gilt nur mit passender Kategorie und passendem Muster; abgelehnt und offen
    geben nichts frei; rule:-Schlüssel vergleicht check nie; Präfix deckt Fixtures."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root)
    fixture = root / "evals" / "fixtures" / "dc-models" / "migrations"
    fixture.mkdir(parents=True)
    (fixture / "0001_initial.py").write_text("x\n", encoding="utf-8")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("x\n", encoding="utf-8")
    (root / "openapi.yaml").write_text("x\n", encoding="utf-8")
    (root / "app.py").write_text("x\n", encoding="utf-8")                # keine Kategorie
    write_ledger(root, ledger_block(1, "freigegeben", "data-delete:evals/fixtures/"),       # falsche Kategorie
                 ledger_block(2, "abgelehnt", "permissions:.github/workflows/"),
                 ledger_block(3, "freigegeben", "rule:openapi.yaml"),
                 ledger_block(4, "freigegeben", "api:api/openapi.*"))                       # anderes Muster
    code, out, _ = check_out(capsys, base)
    assert code == 1
    assert reported(out) == [".github/workflows/ci.yml", "evals/fixtures/dc-models/migrations/0001_initial.py",
                             "openapi.yaml"], out
    assert "D-2" in next(line for line in out.splitlines() if "ci.yml" in line)
    write_ledger(root, ledger_block(1, "freigegeben", "migration:evals/fixtures/"),
                 ledger_block(2, "freigegeben", "permissions:.github/workflows/"),
                 ledger_block(3, "freigegeben", "api:openapi.*"))
    code, out, _ = check_out(capsys, base)
    assert code == 0 and reported(out) == [] and out.splitlines()[-1] == TAIL, out

    # leeres `#`: add weist es ab; von Hand in der Ablage gibt es nichts frei (nicht die ganze Datei)
    assert big(*TWO, "--session", SESSION, key="dependency:pyproject.toml#  ") == 1
    assert "hat leeren Text nach #" in capsys.readouterr().err         # Grund aus parse_key (CP3-R3-F5)
    assert big(*TWO, "--session", SESSION, key="dependency:pyproject.toml#python-dateutil") == 0
    capsys.readouterr()
    (root / "pyproject.toml").write_text('[project]\ndependencies = ["requests"]\n', encoding="utf-8")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml#"),
                 ledger_block(2, "freigegeben", "migration:evals/fixtures/"),
                 ledger_block(3, "freigegeben", "permissions:.github/workflows/"),
                 ledger_block(4, "freigegeben", "api:openapi.*"))
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["pyproject.toml"], out
    assert "D-1" in out and "gibt nichts frei" in out, out


def test_check_sees_spec_patterns(decide_repo, monkeypatch, capsys):
    """Spec 28, check: Lockfiles, setup.py/setup.cfg/Pipfile, Manifeste in Unterordnern und
    CODEOWNERS an jeder Stelle sind Stellen; `**/`-Präfix-Muster in Schlüsseln geben direkte Kinder frei."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root)
    paths = ["poetry.lock", "setup.py", "setup.cfg", "Pipfile", "web/package.json", "web/package-lock.json",
             "docs/CODEOWNERS", "svc/go.sum", "migrations/0001.py"]
    for name in paths:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("x\n", encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == sorted(paths), out
    assert "- docs/CODEOWNERS — permissions (teilweise)" in out
    assert "- poetry.lock — dependency (teilweise)" in out
    write_ledger(root, ledger_block(1, "freigegeben", "migration:migrations/**/"),
                 ledger_block(2, "freigegeben", "dependency:**/"),
                 ledger_block(3, "freigegeben", "permissions:**/CODEOWNERS"))
    code, out, _ = check_out(capsys, base)
    assert code == 0 and reported(out) == [] and out.splitlines()[-1] == TAIL, out


def test_check_range_reads_ledger_from_end_revision(decide_repo, monkeypatch, capsys):
    """`<a>..<b>` liest die Freigaben aus `<b>`, nicht aus der Arbeitskopie; fehlt die Ablage in
    `<b>`, wie eine fehlende Ablage. Eine einzelne Revision liest die Arbeitskopie."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root, "Basis")
    git(root, "checkout", "-q", "-b", "feature")
    (root / "pyproject.toml").write_text('[project]\ndependencies = ["x"]\n', encoding="utf-8")
    feature = commit(root, "Abhängigkeit")

    # Freigabe nur in der Arbeitskopie, nicht in <b>: gemeldet, mit Grund „fehlt in <b>“
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"))
    code, out, _ = check_out(capsys, f"{base}..{feature}")
    assert code == 1 and reported(out) == ["pyproject.toml"], out
    assert f"Freigaben nicht gelesen (docs/big-decisions.md fehlt in {feature})" in out, out
    assert "kein Eintrag" not in out
    # dieselbe Freigabe für eine einzelne Revision: aus der Arbeitskopie, frei
    code, out, _ = check_out(capsys, base)
    assert code == 0 and reported(out) == [], out

    # Freigabe in <b> committet, in der Arbeitskopie gelöscht: frei, auch von einem anderen Branch aus
    feature = commit(root, "Freigabe")
    (root / "docs" / "big-decisions.md").unlink()
    code, out, _ = check_out(capsys, f"{base}..{feature}")
    assert code == 0 and reported(out) == [], out
    git(root, "checkout", "-q", "-f", "-b", "anders", base)
    write_ledger(root, ledger_block(1, "offen", "dependency:pyproject.toml"))
    for rev in (f"{base}..{feature}", f"{feature}^!"):
        code, out, _ = check_out(capsys, rev)
        assert code == 0 and reported(out) == [], (rev, out)
    # <a>...<b>: Basis die Merge-Base, Freigaben aus <b> (CP3-R3-F1)
    code, out, err = check_out(capsys, f"{base}...{feature}")
    assert code == 0 and reported(out) == [], (out, err)
    # in <b> offen, in der Arbeitskopie freigegeben: gemeldet mit dem Status aus <b>
    (root / "docs" / "big-decisions.md").unlink()
    git(root, "checkout", "-q", "feature")
    write_ledger(root, ledger_block(1, "offen", "dependency:pyproject.toml"))
    offen = commit(root, "wieder offen")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"))
    code, out, _ = check_out(capsys, f"{base}..{offen}")
    assert code == 1 and "D-1 dependency:pyproject.toml steht offen" in out, out


def test_check_reason_when_ledger_not_read(decide_repo, monkeypatch, capsys):
    """Fehlt, ist unlesbar oder übersprungen die Ablage, sagt jede Stelle „Freigaben nicht gelesen
    (<Grund>)“ statt „kein Eintrag mit passendem Schlüssel“."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root)
    (root / "pyproject.toml").write_text("x\n", encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    line = next(line for line in out.splitlines() if line.startswith("- pyproject.toml"))
    assert code == 1 and line.endswith("— Freigaben nicht gelesen (docs/big-decisions.md fehlt)"), out

    head2 = "<!-- skill: decide | schema: 2 | generated: python decide_log.py add -->\n"
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"), head=head2)
    code, out, _ = check_out(capsys, base)
    line = next(line for line in out.splitlines() if line.startswith("- pyproject.toml"))
    assert line.endswith("— Freigaben nicht gelesen (docs/big-decisions.md schema 1 erwartet, 2 gefunden)"), out
    assert "kein Eintrag" not in out

    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"))
    real = dl.read_file

    def deny(path):
        if Path(path).name == "big-decisions.md":
            raise dl.Unreadable(PermissionError(errno.EACCES, "Permission denied"))
        return real(path)

    monkeypatch.setattr(dl, "read_file", deny)
    code, out, _ = check_out(capsys, base)
    line = next(line for line in out.splitlines() if line.startswith("- pyproject.toml"))
    assert line.endswith("— Freigaben nicht gelesen (docs/big-decisions.md nicht lesbar (Permission denied))"), out


def test_check_git_timeout(decide_repo, monkeypatch, capsys):
    """Antwortet git nicht in GIT_TIMEOUT Sekunden: Exit 2 mit eigener Meldung, nicht „kein Git“ —
    auch wenn erst der Diff einer Datei für `#<text>` zu lange braucht."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml#python-dateutil"))
    base = commit(root)
    (root / "pyproject.toml").write_text('[project]\ndependencies = ["python-dateutil"]\n', encoding="utf-8")
    real = subprocess.run

    def slow(argv, *args, when=lambda argv: True, **kwargs):
        if argv[:1] == ["git"] and when(argv):
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))
        return real(argv, *args, **kwargs)

    expected = f"ungeprüft — git antwortet nicht in {dl.GIT_TIMEOUT} s"
    monkeypatch.setattr(dl.subprocess, "run", slow)
    code, out, err = check_out(capsys, base)
    assert code == 2 and expected in err and "kein Git" not in err and err.splitlines()[-1] == TAIL, err
    monkeypatch.setattr(dl.subprocess, "run", lambda argv, *a, **k: slow(argv, *a, when=lambda v: "-U0" in v, **k))
    code, out, err = check_out(capsys, base)
    assert code == 2 and expected in err and out == "", (out, err)


def test_check_goes_through_changed_files(decide_repo, monkeypatch, capsys):
    """check holt die Stellen über `changed_files` — ein Einstieg, eine Quelle."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root)
    (root / "pyproject.toml").write_text("x\n", encoding="utf-8")
    calls, real = [], dl.changed_files

    def spy(*args):
        calls.append(args)
        return real(*args)

    monkeypatch.setattr(dl, "changed_files", spy)
    files, problem = dl.changed_files(root, base)
    assert problem is None and list(files) == ["pyproject.toml"]
    calls.clear()
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["pyproject.toml"] and len(calls) == 1, (calls, out)


def test_check_rule_key_with_hash_stays_silent(decide_repo, monkeypatch, capsys):
    """CP3-R2-F1: `rule:C#` ist ein Regelschlüssel (Thema mit `#`), kein leerer Text nach `#` —
    check überspringt ihn still wie jeden `rule:`-Schlüssel."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    write_rules(root / ".skills" / "decide" / "rules.md", "immer fragen: C#\n")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root)
    write_ledger(root, ledger_block(1, "freigegeben", "rule:C#"),
                 ledger_block(2, "freigegeben", "dependency:pyproject.toml"))
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 0 and reported(out) == [], out
    assert "D-1" not in out and "leeren Text" not in out, out


def test_check_reason_comes_from_ledger_key(decide_repo, monkeypatch, capsys):
    """CP3-R2-F6: Der Grund im Hinweis ist der, mit dem `parse_key` den Schlüssel abweist — bei
    `a#b:c#` der leere Text nach `#`, nicht „nicht die Form“."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root)
    write_ledger(root, ledger_block(1, "freigegeben", "a#b:c#"), ledger_block(2, "freigegeben", "nur-text"))
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["pyproject.toml"], out
    assert "Hinweis: D-1 Schlüssel „a#b:c#“ hat leeren Text nach # — gibt nichts frei." in out, out
    assert f"Hinweis: D-2 Schlüssel „nur-text“ hat nicht die Form {dl.KEY_FORM} — gibt nichts frei." in out, out


def test_check_range_notations_via_rev_parse(decide_repo, monkeypatch, capsys):
    """CP3-R2-F2: Ein `git rev-parse <rev>` entscheidet — genau eine positive Revision ohne negative
    ist eine Einzelrevision (Arbeitsbaum, unversionierte Dateien, Ablage aus der Arbeitskopie), sonst
    ein Bereich mit der positiven als End-Revision; mehrere positive: Exit 2."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root, "Basis")
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"))
    commit(root, "Abhängigkeit mit Freigabe")
    (root / "migrations").mkdir()
    (root / "migrations" / "0001.py").write_text("x\n", encoding="utf-8")            # unversioniert
    since_base = ["docs/big-decisions.md", "migrations/0001.py", "pyproject.toml"]
    for rev, expected in (("HEAD", ["migrations/0001.py"]), ("HEAD~1", since_base), ("HEAD^@", since_base)):
        files, problem = dl.changed_files(root, rev)
        assert problem is None and files.end is None and list(files) == expected, (rev, problem, files.end)
    for rev in ("HEAD~1..HEAD", "HEAD^!"):
        files, problem = dl.changed_files(root, rev)
        assert problem is None and files.end == "HEAD", (rev, problem, files.end)       # wie angegeben (CP3-R3-F3)
        assert list(files) == ["docs/big-decisions.md", "pyproject.toml"], (rev, list(files))

    # HEAD^@ (ein Elternteil): Freigaben aus der Arbeitskopie, nicht „fehlt in HEAD^@“
    code, out, _ = check_out(capsys, "HEAD^@")
    assert code == 1 and reported(out) == ["migrations/0001.py"], out
    assert "fehlt in" not in out and "kein Eintrag mit passendem Schlüssel in docs/big-decisions.md" in out, out
    code, out, _ = check_out(capsys, "HEAD~1..HEAD")
    assert code == 0 and reported(out) == [] and "Freigaben aus HEAD;" in out, out
    # A...B: Bereich wie A..B, wenn A die Merge-Base ist (CP3-R3-F1)
    code, out, err = check_out(capsys, "HEAD~1...HEAD")
    assert code == 0 and reported(out) == [] and out.splitlines()[-1] == TAIL, (out, err)

    # Merge-Commit: HEAD^@ sind beide Eltern (mehrere Enden), HEAD^! ein Bereich mit Ende HEAD
    (root / "migrations" / "0001.py").unlink()
    git(root, "checkout", "-q", "-b", "seite", base)
    (root / "app.py").write_text("x\n", encoding="utf-8")
    commit(root, "Seite")
    git(root, "checkout", "-q", "-")
    git(root, "-c", "user.email=t@example.org", "-c", "user.name=t", "merge", "-q", "--no-ff", "-m", "Merge", "seite")
    code, out, err = check_out(capsys, "HEAD^@")
    assert code == 2 and "ungeprüft — Bereich mit mehreren Enden" in err, (out, err)
    files, problem = dl.changed_files(root, "HEAD^!")
    assert problem is None and files.end == "HEAD", (problem, files.end)


def test_check_range_ledger_problems_name_revision(decide_repo, monkeypatch, capsys):
    """CP3-R2-F3: Liest check die Ablage aus einer Revision, nennen Kopfzeilen- und Schema-Probleme
    „docs/big-decisions.md in <rev>“, nicht die Arbeitskopie. Ein BOM in der Revision stört nicht."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root, "Basis")
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    head2 = "<!-- skill: decide | schema: 2 | generated: python decide_log.py add -->\n"
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"), head=head2)
    end = commit(root, "Ablage schema 2")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"))     # Arbeitskopie gültig
    code, out, _ = check_out(capsys, f"{base}..{end}")
    where = f"docs/big-decisions.md in {end}"
    assert code == 1 and reported(out) == ["pyproject.toml"], out
    assert f"{where} schema 1 erwartet, 2 gefunden — Freigaben übersprungen" in out, out
    assert f"Freigaben nicht gelesen ({where} schema 1 erwartet, 2 gefunden)" in out, out

    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"), head="# Große Entscheidungen\n")
    end = commit(root, "Ablage ohne Kopfzeile")
    code, out, _ = check_out(capsys, f"{base}..{end}")
    assert code == 1 and f"docs/big-decisions.md in {end} ohne Kopfzeile von decide" in out, out

    path = write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"))
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    end = commit(root, "Ablage mit BOM")
    code, out, _ = check_out(capsys, f"{base}..{end}")
    assert code == 0 and reported(out) == [], out


# --- Funde des Prüfpunkts 3, Runde 3 (Mini-Runde F1–F5) ---------------------------------

def test_check_symmetric_range_uses_merge_base(decide_repo, monkeypatch, capsys):
    """CP3-R3-F1: `<a>...<b>` wie `git diff <a>...<b>` — Basis die Merge-Base, Ende `<b>` (leer:
    `HEAD`), ohne Arbeitsbaum; die Freigaben kommen aus `<b>`. `main` ist nach dem Abzweigen
    weitergelaufen, die Merge-Base ist also nicht `main` selbst."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    commit(root, "Basis")
    git(root, "branch", "-M", "main")
    git(root, "checkout", "-q", "-b", "feature")
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"))
    commit(root, "Abhängigkeit mit Freigabe")
    git(root, "checkout", "-q", "main")
    (root / "migrations").mkdir()
    (root / "migrations" / "0001.py").write_text("x\n", encoding="utf-8")
    commit(root, "Migration nur auf main")
    git(root, "checkout", "-q", "feature")
    (root / "migrations").mkdir(exist_ok=True)
    (root / "migrations" / "0002.py").write_text("x\n", encoding="utf-8")           # unversioniert
    write_ledger(root, ledger_block(1, "offen", "dependency:pyproject.toml"))         # Arbeitskopie: offen
    for rev in ("main...feature", "main...HEAD", "main..."):
        files, problem = dl.changed_files(root, rev)
        assert problem is None and list(files) == ["docs/big-decisions.md", "pyproject.toml"], (rev, problem)
        code, out, err = check_out(capsys, rev)
        assert code == 0 and reported(out) == [] and out.splitlines()[-1] == TAIL, (rev, out, err)
    # main..feature sähe die Migration von main als gelöscht — der Unterschied zur Merge-Base
    code, out, _ = check_out(capsys, "main..feature")
    assert code == 1 and reported(out) == ["migrations/0001.py"], out


def test_check_root_commit_bang_is_range(decide_repo, monkeypatch, capsys):
    """CP3-R3-F2: `R^!` auf dem ersten Commit ist ein Bereich ohne Arbeitsbaum, obwohl git rev-parse
    keine negative Revision nennt — Diff vom leeren Baum zu `R`, Ablage aus `R`."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    first = commit(root, "erster Commit")
    (root / "app.py").write_text("x\n", encoding="utf-8")
    commit(root, "zweiter")
    (root / "migrations").mkdir()
    (root / "migrations" / "0001.py").write_text("x\n", encoding="utf-8")            # unversioniert
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"),   # nur Arbeitskopie
                 ledger_block(2, "freigegeben", "migration:migrations/"))
    files, problem = dl.changed_files(root, f"{first}^!")
    assert problem is None and files.end is not None, (problem, files.end)
    assert list(files) == ["README.md", "pyproject.toml"], list(files)
    code, out, _ = check_out(capsys, f"{first}^!")
    assert code == 1 and reported(out) == ["pyproject.toml"], out
    assert f"Freigaben nicht gelesen (docs/big-decisions.md fehlt in {first})" in out, out


def test_check_range_names_revision_as_given(decide_repo, monkeypatch, capsys):
    """CP3-R3-F3: Meldungen nennen das Ende wie angegeben — bei annotierten Tags `v2`, nicht den
    Hash des Tag-Objekts; gelesen wird die Ablage aus dem Commit, auf den das Tag zeigt."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    tag = ["-c", "user.email=t@example.org", "-c", "user.name=t", "tag", "-a", "-m", "Tag"]
    (root / "README.md").write_text("x\n", encoding="utf-8")
    commit(root, "Basis")
    git(root, *tag, "v1")
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    commit(root, "Abhängigkeit")
    git(root, *tag, "v2")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"))
    commit(root, "Freigabe")
    git(root, *tag, "v3")
    hex40 = re.compile(r"\b[0-9a-f]{40}\b")

    code, out, _ = check_out(capsys, "v1..v2")
    assert code == 1 and reported(out) == ["pyproject.toml"], out
    assert "Freigaben nicht gelesen (docs/big-decisions.md fehlt in v2)" in out and "Freigaben aus v2;" in out, out
    assert not hex40.search(out), out
    for rev in ("v1..v3", "v1...v3", "v3^!"):
        files, problem = dl.changed_files(root, rev)
        assert problem is None and files.end == "v3", (rev, problem, files.end)
        code, out, _ = check_out(capsys, rev)
        assert code == 0 and reported(out) == [] and "Freigaben aus v3;" in out, (rev, out)
        assert not hex40.search(out), (rev, out)


def test_check_ledger_missing_by_exit_code_not_wording(decide_repo, monkeypatch, capsys):
    """CP3-R3-F4: Ob die Ablage in der Revision fehlt, sagt der Exit-Code von `git cat-file -e`, nicht
    der Wortlaut von stderr; ein Fehler beim Lesen danach heißt „nicht lesbar“."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root, "Basis")
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    end = commit(root, "ohne Ablage")
    real = subprocess.run

    def german(argv, *args, **kwargs):
        result = real(argv, *args, **kwargs)
        if argv[:1] == ["git"] and "cat-file" in argv and result.returncode != 0:
            message = "fatal: Pfad 'docs/big-decisions.md' existiert nicht in 'x'\n"
            result.stderr = message.encode() if isinstance(result.stderr, bytes) else message
        return result

    monkeypatch.setattr(dl.subprocess, "run", german)
    code, out, _ = check_out(capsys, f"{base}..{end}")
    assert code == 1 and reported(out) == ["pyproject.toml"], out
    assert f"Freigaben nicht gelesen (docs/big-decisions.md fehlt in {end})" in out, out
    assert "nicht lesbar" not in out, out

    (root / "docs" / "big-decisions.md").mkdir(parents=True)                         # ein Ordner, kein Blob
    (root / "docs" / "big-decisions.md" / "x").write_text("x\n", encoding="utf-8")
    end = commit(root, "Ablage als Ordner")
    code, out, _ = check_out(capsys, f"{base}..{end}")
    assert code == 1 and f"docs/big-decisions.md in {end} nicht lesbar" in out and "fehlt in" not in out, out


def test_tab_in_hand_written_key_is_refused_by_check_too(decide_repo, monkeypatch, capsys):
    """CP3-R3-F5: add und check lesen Schlüssel mit derselben Funktion — ein Tab im Pfadmuster, den
    add abweist, gibt auch von Hand in der Ablage nichts frei."""
    root, _ = decide_repo
    key = "migration:migrations/a\tb.py"
    assert big(*TWO, key=key) == 1
    assert "Tab oder Zeilenumbruch" in capsys.readouterr().err
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root, "Basis")
    (root / "migrations").mkdir()
    (root / "migrations" / "a\tb.py").write_text("x\n", encoding="utf-8")
    write_ledger(root, ledger_block(1, "freigegeben", key))
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["migrations/a\tb.py"], out
    assert "Hinweis: D-1 Schlüssel „migration:migrations/a\tb.py“ hat Tab oder Zeilenumbruch" in out, out


# --- brief (Task 4): Entscheidungsauftrag an einen Subagenten ------------------------------
# SUBAGENT ist bewusst ein Literal: der Satz aus Spec 28, Ablauf 5, wörtlich — nicht aus
# references/brief.md gelesen (dort liest ihn das Skript), damit eine Änderung dort hier auffällt.

SUBAGENT = ("Du arbeitest als Subagent. Trag keine Entscheidung und keine Frage mit decide_log.py ein und "
            "schreib nicht nach docs/big-decisions.md. Stößt du auf eine Frage mit zwei Lesarten oder auf "
            "einen teuer umkehrbaren Schritt, der nicht ausdrücklich in deinem Auftrag steht, entscheide und "
            "handle nicht, sondern nenn ihn in deiner Rückgabe: Frage, Optionen mit Belegen datei:zeile, "
            "Folgen, Umkehrbarkeit, Empfehlung. Der Hauptagent ordnet ihn ein.")
BRIEF_HEADER = "<!-- skill: decide | schema: 1 | generated: python decide_log.py brief --topic CLI -->"


def brief_file(root, n=1):
    return log_file(root).parent / f"brief-{n}.md"


def brief_sections(text):
    """Feld → Zeilen mit Text darunter, aus den Überschriften `## <Feld>`."""
    sections, current = {}, None
    for line in text.splitlines()[1:]:
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif line.strip() and current:
            sections[current].append(line)
    return sections


def filled_brief(question="Welche Bibliothek parst die Argumente der CLI?", extra=(), anlass=1):
    """Ein ausgefüllter Auftrag mit Kopfzeile; `anlass` Zeilen unter Anlass, `extra` danach."""
    return "\n".join([BRIEF_HEADER, "## Frage", question, "## Anlass",
                      *[f"Aufgabe Schritt {i}" for i in range(anlass)],
                      "## Feste Vorgaben", "- nur Stdlib (Spec 28)", "## Schon entschieden", "—",
                      "## Wo nachsehen", "- app/cli.py", "## Rückgabe", "Optionen mit Belegen.", SUBAGENT,
                      *extra]) + "\n"


def brief_check(capsys, path):
    code = dl.main(["brief", "--check", str(path)])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_brief_takes_entries_from_add_small(decide_repo):
    """Abnehmer von `add_small` (Task 1): zwei Einträge mit Themen CLI und Logging, der Auftrag zu
    CLI führt unter Schon entschieden nur den ersten."""
    root, home = decide_repo
    for topic, question, decision in (("CLI", "Kurzoption für --verbose?", "Kurzform -v"),
                                      ("Logging", "Format der Logzeilen?", "JSON")):
        args = SimpleNamespace(topic=topic, question=question, decision=decision,
                               evidence="gesucht: app/ — Treffer: app/cli.py:3", options=None, home=home)
        assert dl.add_small(root, SESSION, args)[0] == 0
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 0, message
    assert ".skills/cache/decide/sitzung-1/brief-1.md" in message, message
    text = brief_file(root).read_text(encoding="utf-8")
    [line] = brief_sections(text)["Schon entschieden"]
    assert "Kurzoption für --verbose?" in line and "Kurzform -v" in line and "app/cli.py:3" in line, line
    assert "Format der Logzeilen" not in text and "JSON" not in text, text


def test_brief_header_not_counted(decide_repo, capsys):
    """Die Kopfzeile zählt nicht zu den 25 Zeilen; Leerzeilen auch nicht."""
    root, _ = decide_repo
    path = brief_file(root)
    path.parent.mkdir(parents=True)
    text = filled_brief(anlass=13)                     # 25 Zeilen mit Text ohne Kopf
    assert len([line for line in text.splitlines()[1:] if line.strip()]) == 25
    path.write_text(text.replace("## Anlass\n", "## Anlass\n\n\n"), encoding="utf-8")
    code, out, _ = brief_check(capsys, path)
    assert code == 0 and "25 Zeilen" in out, out

    path.write_text(filled_brief(anlass=14), encoding="utf-8")
    code, out, _ = brief_check(capsys, path)
    assert code == 1 and "26 Zeilen ohne Kopf, höchstens 25" in out, out


def test_brief_return_sentence(decide_repo, capsys):
    """`brief --topic X` schreibt den Satz aus Spec 28, Ablauf 5, wörtlich unter Rückgabe;
    `brief --check` meldet sein Fehlen nicht (unterrichten, nicht mechanisch prüfen)."""
    root, _ = decide_repo
    assert dl.load_subagent_sentence(dl.BRIEF_REFERENCE) == (SUBAGENT, None)    # aus brief.md, eine Quelle
    assert dl.main(["brief", "--topic", "X"]) == 0
    text = brief_file(root).read_text(encoding="utf-8")
    assert SUBAGENT in brief_sections(text)["Rückgabe"], text
    assert text.count(SUBAGENT) == 1
    assert SUBAGENT in dl.BRIEF_REFERENCE.read_text(encoding="utf-8")       # brief.md zitiert ihn
    capsys.readouterr()

    filled = text.replace("## Frage\n", "## Frage\nWelche Bibliothek parst die Argumente?\n")
    brief_file(root).write_text(filled, encoding="utf-8")
    code, out, _ = brief_check(capsys, brief_file(root))
    assert code == 0, out
    brief_file(root).write_text(filled.replace(SUBAGENT + "\n", ""), encoding="utf-8")
    code, out, err = brief_check(capsys, brief_file(root))
    assert code == 0 and "Subagent" not in out + err, out + err


def test_wordlist_from_reference(decide_repo, tmp_path, monkeypatch, capsys):
    """Die Wortliste kommt aus references/brief.md — dieselbe Liste für Mensch und Parser; fehlt
    die Datei oder parst sie nicht, endet `brief --check` mit Exit 2, nie mit Erfolg."""
    root, _ = decide_repo
    words, problem = dl.load_wordlist(dl.BRIEF_REFERENCE)
    assert problem is None
    assert words == ("sollte", "besser", "lieber", "empfehle", "ich würde", "offensichtlich")

    path = brief_file(root)
    path.parent.mkdir(parents=True)
    path.write_text(filled_brief("Sollte die CLI besser argparse nutzen?"), encoding="utf-8")
    reference = tmp_path / "references" / "brief.md"
    reference.parent.mkdir()
    monkeypatch.setattr(dl, "BRIEF_REFERENCE", reference)
    code, out, err = brief_check(capsys, path)
    assert code == 2 and not out and "ungeprüft — references/brief.md fehlt" in err, (out, err)

    reference.write_text("# Auftrag\n\n## Wortliste\n\n- `argparse`\n\n## Danach\n\n- `sollte`\n", encoding="utf-8")
    assert dl.load_wordlist(reference) == (("argparse",), None)
    code, out, _ = brief_check(capsys, path)                   # gelesen, nicht im Skript hinterlegt
    assert code == 1 and "„argparse“" in out and "„sollte“" not in out, out

    for broken, reason in (("# Auftrag\n\n- `sollte`\n", "kein Abschnitt „## Wortliste“"),
                           ("## Wortliste\n\n## Danach\n\n- `sollte`\n", "ohne Listenpunkte"),
                           ("## Wortliste\n\nnur Prosa\n", "references/brief.md:3: „nur Prosa“ ist kein Listenpunkt"),
                           ("## Wortliste\n\n- sollte\n", "references/brief.md:3: Listenpunkt „- sollte“")):
        reference.write_text(broken, encoding="utf-8")
        assert dl.load_wordlist(reference)[0] == ()
        code, out, err = brief_check(capsys, path)
        assert code == 2 and err.startswith("ungeprüft — ") and reason in err, (broken, err)


def test_brief_words_whole_and_case_insensitive(decide_repo, capsys):
    """Ein Wort der Liste trifft als ganzes Wort, groß oder klein, nur in der Frage; eine Wortfolge
    auch über mehrere Leerzeichen."""
    root, _ = decide_repo
    path = brief_file(root)
    path.parent.mkdir(parents=True)
    path.write_text(filled_brief("Wie verbessern wir die Fehlermeldung, ohne dass Tests brechen?",
                                 anlass=1).replace("Aufgabe Schritt 0", "Ich würde lieber argparse nehmen"),
                    encoding="utf-8")
    code, out, _ = brief_check(capsys, path)
    assert code == 0, out
    path.write_text(filled_brief("Ich  würde fragen: OFFENSICHTLICH argparse?"), encoding="utf-8")
    code, out, _ = brief_check(capsys, path)
    assert code == 1 and "„ich würde“" in out and "„offensichtlich“" in out and "„sollte“" not in out, out


def test_brief_check_fields(decide_repo, capsys):
    """Gemeldet werden Felder außer den sechs, Text vor dem ersten Feld, fehlende und doppelte Felder."""
    root, _ = decide_repo
    path = brief_file(root)
    path.parent.mkdir(parents=True)
    text = filled_brief(extra=["## Frage", "Noch eine?"])
    text = text.replace(BRIEF_HEADER + "\n", BRIEF_HEADER + "\nMeine Einschätzung: argparse\n")
    path.write_text(text.replace("## Wo nachsehen\n- app/cli.py\n", ""), encoding="utf-8")
    code, out, _ = brief_check(capsys, path)
    assert code == 1, out
    assert "Text vor dem ersten Feld (Zeile 2)" in out, out
    assert "Feld „Frage“ steht doppelt" in out and "es fehlt: Wo nachsehen" in out, out


def test_brief_check_consumer_rule(decide_repo, capsys):
    """Ohne Kopfzeile von decide, mit höherem schema oder ohne Datei: Exit 2 „ungeprüft — …“."""
    root, _ = decide_repo
    path = brief_file(root)
    path.parent.mkdir(parents=True)
    code, _, err = brief_check(capsys, path)
    assert code == 2 and "ungeprüft — Auftrag" in err and "fehlt" in err, err
    path.write_text(filled_brief().split("\n", 1)[1], encoding="utf-8")
    code, _, err = brief_check(capsys, path)
    assert code == 2 and "ohne Kopfzeile von decide" in err, err
    path.write_text(filled_brief().replace("schema: 1", "schema: 2"), encoding="utf-8")
    code, _, err = brief_check(capsys, path)
    assert code == 2 and "schema 1 erwartet, 2 gefunden" in err, err


def test_brief_numbers_count_up_and_need_session(decide_repo, monkeypatch, capsys):
    """Jeder Auftrag bekommt die nächste Nummer; `brief --topic` braucht eine Sitzung, `--check` nicht."""
    root, home = decide_repo
    assert dl.write_brief(root, SESSION, "CLI", home)[0] == 0
    first = brief_file(root).read_text(encoding="utf-8")
    code, message = dl.write_brief(root, SESSION, "Logging", home)
    assert code == 0 and "brief-2.md" in message, message
    assert brief_file(root).read_text(encoding="utf-8") == first
    assert "--topic Logging -->" in brief_file(root, 2).read_text(encoding="utf-8").splitlines()[0]
    assert dl.write_brief(root, SESSION, "  ", home)[0] == 1

    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    capsys.readouterr()
    assert dl.main(["brief", "--topic", "CLI"]) == 1
    assert "--session" in capsys.readouterr().err
    assert not brief_file(root, 3).exists()
    code, out, _ = brief_check(capsys, brief_file(root))
    assert code == 0, out


def test_brief_reports_unreadable_rules_and_log(decide_repo, capsys):
    """Eine unlesbare Regeldatei meldet brief wie add (read_rules) und schreibt trotzdem; ein
    unlesbares Protokoll lässt den Auftrag aus — Schon entschieden wäre sonst still leer."""
    root, home = decide_repo
    (root / ".skills" / "decide" / "rules.md").mkdir(parents=True)          # ein Ordner: nicht lesbar
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 0 and "Hinweis: Regeln .skills/decide/rules.md nicht lesbar" in message, message
    assert brief_file(root).exists()

    log_file(root).mkdir(parents=True)
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 1 and "nicht lesbar" in message and "kein Auftrag geschrieben" in message, message
    assert not brief_file(root, 2).exists()


# --- Prüfpunkt 4: Funde F1–F12 an brief ---------------------------------------------------

def test_brief_big_questions_by_ledger_status(decide_repo, capsys):
    """F1: Eine große Frage steht unter Schon entschieden nur, wenn die Ablage sie freigegeben oder
    abgelehnt hat; eine offene steht unter Feste Vorgaben als „nicht entscheiden, nicht darauf
    aufbauen“; fehlt die Ablage oder wird sie übersprungen, ist der Status unbekannt."""
    root, home = decide_repo
    assert big(*TWO, topic="CLI", question="Neue Abhängigkeit für die CLI?") == 0
    assert big("--approved-by-request", "nimm argparse", topic="CLI", question="Parser wechseln?",
               key="dependency:pyproject.toml#argparse") == 0
    assert big(*TWO, topic="CLI", question="Spalte legacy_id löschen?", key="migration:migrations/") == 0
    assert dl.main(["resolve", "D-3", "--reject"]) == 0
    capsys.readouterr()

    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 0, message
    sections = brief_sections(brief_file(root).read_text(encoding="utf-8"))
    decided = sections["Schon entschieden"]
    assert len(decided) == 2, decided
    assert "Parser wechseln?" in decided[0] and "D-2 freigegeben" in decided[0] and "„nimm argparse“" in decided[0]
    assert "Spalte legacy_id löschen?" in decided[1] and "D-3 abgelehnt" in decided[1], decided
    assert not any("D-1" in line or "Neue Abhängigkeit" in line for line in decided), decided
    assert sections["Feste Vorgaben"] == [
        "- D-1 offen: Neue Abhängigkeit für die CLI? — nicht entscheiden, nicht darauf aufbauen"]

    ledger = root / "docs" / "big-decisions.md"
    ledger.write_text(ledger.read_text(encoding="utf-8").replace("schema: 1", "schema: 2"), encoding="utf-8")
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 0 and "schema 1 erwartet, 2 gefunden" in message, message
    sections = brief_sections(brief_file(root, 2).read_text(encoding="utf-8"))
    assert sections["Schon entschieden"] == ["—"]
    assert len(sections["Feste Vorgaben"]) == 4
    assert sections["Feste Vorgaben"][0].startswith("- Ablage docs/big-decisions.md nicht gelesen (")   # R3-F1
    assert all("Status unbekannt" in line and "nicht darauf aufbauen" in line
               for line in sections["Feste Vorgaben"][1:]), sections

    ledger.unlink()
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 0, message
    sections = brief_sections(brief_file(root, 3).read_text(encoding="utf-8"))
    assert sections["Schon entschieden"] == ["—"]
    assert [line.split(" Status unbekannt")[0] for line in sections["Feste Vorgaben"]] == ["- D-1", "- D-2", "- D-3"]
    assert "docs/big-decisions.md fehlt" in sections["Feste Vorgaben"][0]


def test_brief_check_path_from_subfolder(decide_repo, monkeypatch, capsys):
    """F2: Der Pfad, den brief --topic nennt, ist relativ zur Wurzel; brief --check findet ihn auch
    aus einem Unterordner."""
    root, home = decide_repo
    assert dl.write_brief(root, SESSION, "CLI", home)[0] == 0
    path = brief_file(root)
    path.write_text(path.read_text(encoding="utf-8").replace("## Frage\n", "## Frage\nWelche Bibliothek?\n"),
                    encoding="utf-8")
    (root / "sub").mkdir()
    monkeypatch.chdir(root / "sub")
    code, out, err = brief_check(capsys, ".skills/cache/decide/sitzung-1/brief-1.md")
    assert code == 0, (out, err)
    code, _, err = brief_check(capsys, "fehlt/brief-9.md")
    assert code == 2 and "fehlt" in err, err


def test_brief_warns_when_rules_alone_exceed_limit(decide_repo):
    """F3: Liegt der Auftrag schon ohne Frage, Anlass und Wo nachsehen über 25 Zeilen, sagt
    brief --topic das gleich; Exit bleibt 0, die Regeln bleiben alle stehen."""
    root, home = decide_repo
    rules = root / ".skills" / "decide" / "rules.md"
    write_rules(rules, "".join(f"immer fragen: Thema {n}\n" for n in range(18)))
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 0, message
    assert "Hinweis: Auftrag hat schon 27 Zeilen ohne Kopf, höchstens 25" in message, message
    assert "bleiben 0 Zeilen" in message and "Regeln oder ältere Einträge" in message, message
    assert len(brief_sections(brief_file(root).read_text(encoding="utf-8"))["Feste Vorgaben"]) == 18
    write_rules(rules, "".join(f"immer fragen: Thema {n}\n" for n in range(13)))   # 22 Zeilen: noch gut (R2-F4)
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 0 and "Hinweis: Auftrag hat schon" not in message, message


def test_brief_check_code_fences(decide_repo, capsys):
    """F4: In einem Codezaun ist `#` Text des Feldes, keine Überschrift; nach dem Zaun zählt sie wieder."""
    root, _ = decide_repo
    path = brief_file(root)
    path.parent.mkdir(parents=True)
    for fence in ("```", "~~~~"):
        path.write_text(filled_brief().replace("- app/cli.py\n", f"- app/cli.py\n{fence}sh\n# TODO\n## Hintergrund\n"
                                               f"{fence}\n"), encoding="utf-8")
        code, out, _ = brief_check(capsys, path)
        assert code == 0, (fence, out)
    path.write_text(filled_brief().replace("- app/cli.py\n", "- app/cli.py\n```\n# TODO\n```\n## Hintergrund\nx\n"),
                    encoding="utf-8")
    code, out, _ = brief_check(capsys, path)
    assert code == 1 and "„Hintergrund“" in out and "TODO" not in out, out
    path.write_text(filled_brief("Welche ```Lib``` sollte es sein?"), encoding="utf-8")   # kein Zaun am Zeilenanfang
    code, out, _ = brief_check(capsys, path)
    assert code == 1 and "„sollte“" in out and "es fehlt" not in out, out


def test_brief_words_with_markdown_emphasis(decide_repo, capsys):
    """F5: `_` grenzt ein Wort ab wie Leerraum (`_sollte_`); Buchstaben und Ziffern nicht."""
    root, _ = decide_repo
    path = brief_file(root)
    path.parent.mkdir(parents=True)
    path.write_text(filled_brief("Welche Lib _sollte_ man nehmen, __besser__ jetzt?"), encoding="utf-8")
    code, out, _ = brief_check(capsys, path)
    assert code == 1 and "„sollte“" in out and "„besser“" in out, out
    path.write_text(filled_brief("Welche Lib nehmen wir für sollte2 und verbessern_x?"), encoding="utf-8")
    code, out, _ = brief_check(capsys, path)
    assert code == 0, out


def test_wordlist_every_line_must_be_a_point(tmp_path):
    """F6: Im Abschnitt Wortliste ist jede nicht-leere Zeile ein Listenpunkt `- `/`* ` mit einem Wort in
    Backticks; jede andere ist ein Problem mit Zeilennummer, nichts wird still verworfen."""
    reference = tmp_path / "references" / "brief.md"
    reference.parent.mkdir()
    for text, line in (("## Wortliste\n\n- `sollte`\n+ `eindeutig`\n", 4),
                       ("## Wortliste\n\n1. `sollte`\n", 3),
                       ("## Wortliste\n\n- `sollte`\nnur Prosa\n", 4)):
        reference.write_text(text, encoding="utf-8")
        words, problem = dl.load_wordlist(reference)
        assert words == () and problem and problem.startswith(f"references/brief.md:{line}: "), (text, problem)
    reference.write_text("## Wortliste\n\n* `sollte`\n\n- `ich  würde`\n\n## Danach\nProsa\n", encoding="utf-8")
    assert dl.load_wordlist(reference) == (("sollte", "ich würde"), None)


def test_brief_interrupted_write_leaves_no_file(decide_repo, monkeypatch):
    """F7: Bricht das Schreiben nach dem Reservieren der Nummer ab, bleibt keine leere brief-<n>.md liegen."""
    root, home = decide_repo
    real_fdopen = os.fdopen

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    written = []

    def fdopen(fd, *args, **kwargs):                   # R2-F12: der Abbruch trifft das Schreiben über den Deskriptor
        handle = real_fdopen(fd, *args, **kwargs)
        written.append(fd)
        handle.write = interrupted
        return handle

    with monkeypatch.context() as patch:
        patch.setattr(dl.os, "fdopen", fdopen)
        with pytest.raises(KeyboardInterrupt):
            dl.write_brief(root, SESSION, "CLI", home)
    assert len(written) == 1, written
    folder = log_file(root).parent
    assert not [p.name for p in folder.iterdir() if p.name.startswith("brief-")]
    assert dl.write_brief(root, SESSION, "CLI", home)[0] == 0
    assert brief_file(root).read_text(encoding="utf-8").startswith("<!-- skill: decide")


def test_brief_header_comment_stays_closed(decide_repo, capsys):
    """F8: `--` aus dem Thema schließt den Kommentar der Kopfzeile nicht vorzeitig."""
    root, home = decide_repo
    for number, topic in enumerate(("a --> b", "x <!-- y --!> z"), 1):
        assert dl.write_brief(root, SESSION, topic, home)[0] == 0
        head = brief_file(root, number).read_text(encoding="utf-8").splitlines()[0]
        assert head.startswith("<!-- ") and head.endswith(" -->"), head
        assert head.count("-->") == 1 and "--!>" not in head, head      # nur das Ende schließt (Final-F10)
        assert dl.HEADER_RE.match(head), head
    code, _, err = brief_check(capsys, brief_file(root))
    assert code == 0, err


def test_brief_sentence_from_reference(decide_repo, tmp_path, monkeypatch):
    """F12: Den Satz für Subagenten liest brief --topic aus references/brief.md (ein Zitat im Abschnitt
    „## Der Satz für Subagenten“); fehlt er oder parst er nicht, Exit 2 und kein Auftrag."""
    root, home = decide_repo
    assert dl.load_subagent_sentence(dl.BRIEF_REFERENCE) == (SUBAGENT, None)
    reference = tmp_path / "references" / "brief.md"
    reference.parent.mkdir()
    monkeypatch.setattr(dl, "BRIEF_REFERENCE", reference)
    reference.write_text("# Auftrag\n\n## Der Satz für Subagenten\n\nProsa davor:\n\n> Neuer Satz,\n> zwei Zeilen.\n\n"
                         "Prosa danach.\n\n## Wortliste\n\n- `sollte`\n", encoding="utf-8")
    assert dl.write_brief(root, SESSION, "CLI", home)[0] == 0
    assert brief_sections(brief_file(root).read_text(encoding="utf-8"))["Rückgabe"][-1] == "Neuer Satz, zwei Zeilen."

    fehlt = "ungeprüft — Satz für Subagenten fehlt in references/brief.md"           # R2-F10: nach Ursache
    for broken, start in ((None, "ungeprüft — references/brief.md fehlt"),
                          ("# Auftrag\n\n> Satz ohne Abschnitt\n", fehlt),
                          ("## Der Satz für Subagenten\n\nnur Prosa\n", fehlt),
                          ("## Der Satz für Subagenten\n\n> eins\n\n> zwei\n",
                           "ungeprüft — Satz für Subagenten mehrfach in references/brief.md")):
        if broken is None:
            reference.unlink()
        else:
            reference.write_text(broken, encoding="utf-8")
        code, message = dl.write_brief(root, SESSION, "CLI", home)
        assert code == 2 and message.startswith(start), message
        assert not brief_file(root, 2).exists()


# --- Prüfpunkt 4, Runde 2: Funde F1–F12 an brief -------------------------------------------

def test_brief_open_questions_from_ledger_of_any_session(decide_repo, capsys):
    """R2-F1: Die Ablage gehört dem Repo. Ein Auftrag zum Thema nennt jede offene große Frage dieses
    Themas aus der Ablage unter Feste Vorgaben, auch ohne Zeile im eigenen Protokoll; freigegebene und
    abgelehnte aus anderen Sitzungen stehen unter Schon entschieden — jede nur einmal."""
    root, home = decide_repo
    assert big("--session", "A", *TWO, topic="CLI", question="Neue Abhängigkeit für die CLI?") == 0
    assert big("--session", "A", *TWO, topic="CLI", question="Spalte legacy_id löschen?",
               key="migration:migrations/") == 0
    assert big("--session", "A", *TWO, topic="Logging", question="Logformat wechseln?") == 0
    assert big("--session", "A", *TWO, topic="cli", question="Konfig umbenennen?", key="api:app/") == 0
    assert dl.main(["resolve", "D-2", "--reject"]) == 0
    assert dl.main(["resolve", "D-4", "--answer", "ja, mit Alias"]) == 0
    capsys.readouterr()

    code, message = dl.write_brief(root, SESSION, " cli ", home)          # andere Sitzung, leeres Protokoll
    assert code == 0, message
    sections = brief_sections(brief_file(root).read_text(encoding="utf-8"))
    assert sections["Feste Vorgaben"] == [
        "- D-1 offen: Neue Abhängigkeit für die CLI? — nicht entscheiden, nicht darauf aufbauen"], sections
    decided = sections["Schon entschieden"]
    assert len(decided) == 2, decided
    assert "Spalte legacy_id löschen?" in decided[0] and "D-2 abgelehnt" in decided[0], decided
    assert "Konfig umbenennen?" in decided[1] and "D-4 freigegeben: ja, mit Alias" in decided[1], decided
    assert "Logformat" not in brief_file(root).read_text(encoding="utf-8")

    code, message = dl.write_brief(root, "A", "CLI", home)                # eigene Sitzung: Protokoll und Ablage
    assert code == 0, message
    text = (root / ".skills" / "cache" / "decide" / "A" / "brief-1.md").read_text(encoding="utf-8")
    for did in ("D-1", "D-2", "D-4"):
        assert text.count(f"{did} ") == 1, (did, text)


def test_brief_names_quote_of_approving_request(decide_repo):
    """R2-F2: Bei einem per Auftrag freigegebenen Block nennt der Auftrag das Zitat, nicht nur
    „wie im Auftrag“."""
    root, home = decide_repo
    assert big("--approved-by-request", "nimm argparse", topic="CLI", question="Parser wechseln?",
               key="dependency:pyproject.toml#argparse") == 0
    assert dl.write_brief(root, SESSION, "CLI", home)[0] == 0
    [line] = brief_sections(brief_file(root).read_text(encoding="utf-8"))["Schon entschieden"]
    assert "D-1 freigegeben" in line and "„nimm argparse“" in line and "wie im Auftrag" not in line, line


def test_subagent_sentence_continuation_without_marker(decide_repo, tmp_path, monkeypatch):
    """R2-F3: Eine nicht-leere Zeile ohne `>` direkt im Zitat ist ein Problem mit Zeilennummer
    (Exit 2), kein still gekürzter Satz."""
    root, home = decide_repo
    reference = tmp_path / "references" / "brief.md"
    reference.parent.mkdir()
    monkeypatch.setattr(dl, "BRIEF_REFERENCE", reference)
    reference.write_text("## Der Satz für Subagenten\n\n> Du arbeitest als Subagent. … und\nschreib nicht.\n",
                         encoding="utf-8")
    sentence, problem = dl.load_subagent_sentence(reference)
    assert sentence is None and problem and "references/brief.md:4" in problem, problem
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 2 and message.startswith("ungeprüft — ") and "references/brief.md:4" in message, message
    assert not brief_file(root).exists()

    reference.write_text("## Der Satz für Subagenten\n\n> Ein Satz,\n> zwei Zeilen.\n\nProsa danach.\n",
                         encoding="utf-8")
    assert dl.load_subagent_sentence(reference) == ("Ein Satz, zwei Zeilen.", None)


def test_brief_hint_counts_the_three_empty_fields(decide_repo):
    """R2-F4: Der Hinweis kommt, sobald für Frage, Anlass und Wo nachsehen keine drei Zeilen mehr
    bleiben (mehr als 22), und nennt, wie viele bleiben."""
    root, home = decide_repo
    rules = root / ".skills" / "decide" / "rules.md"
    write_rules(rules, "".join(f"immer fragen: Thema {n}\n" for n in range(14)))     # 23 Zeilen
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 0, message
    assert "Hinweis: Auftrag hat schon 23 Zeilen ohne Kopf, höchstens 25" in message, message
    assert "bleiben 2 Zeilen" in message, message
    write_rules(rules, "".join(f"immer fragen: Thema {n}\n" for n in range(13)))     # 22 Zeilen: noch gut
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 0 and "Hinweis: Auftrag hat schon" not in message, message


def test_brief_open_questions_first_and_never_cut(decide_repo, capsys):
    """R2-F5: Die Zeilen zu offenen Fragen stehen am Anfang von Feste Vorgaben, und der Hinweis zur
    Länge sagt, nur Regeln zu kürzen."""
    root, home = decide_repo
    write_rules(root / ".skills" / "decide" / "rules.md", "".join(f"immer fragen: Thema {n}\n" for n in range(14)))
    assert big(*TWO, topic="CLI", question="Neue Abhängigkeit für die CLI?") == 0
    capsys.readouterr()
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 0, message
    rows_ = brief_sections(brief_file(root).read_text(encoding="utf-8"))["Feste Vorgaben"]
    assert rows_[0].startswith("- D-1 offen: ") and all(r.startswith("- Regel ") for r in rows_[1:]), rows_
    assert "Schon entschieden kürzen, die Zeilen zu offenen Fragen nie" in message, message   # R3-F3


def test_brief_duplicate_block_is_named(decide_repo, capsys):
    """R2-F6: Stehen zwei Blöcke mit derselben D-<n> und Frage in der Ablage, sagt der Auftrag
    „doppelt“, nicht „nicht in docs/big-decisions.md“."""
    root, home = decide_repo
    assert big(*TWO, topic="CLI", question="Neue Abhängigkeit?") == 0
    capsys.readouterr()
    ledger = root / "docs" / "big-decisions.md"
    text = ledger.read_text(encoding="utf-8")
    block = text[text.index("## D-1"):].rstrip("\n")
    ledger.write_text(text.rstrip("\n") + "\n\n" + block + "\n", encoding="utf-8")
    assert dl.write_brief(root, SESSION, "CLI", home)[0] == 0
    [line] = brief_sections(brief_file(root).read_text(encoding="utf-8"))["Feste Vorgaben"]
    assert "D-1 doppelt in docs/big-decisions.md" in line and "nicht in docs" not in line, line
    assert line.endswith("nicht darauf aufbauen"), line


def test_subagent_sentence_problem_by_cause(decide_repo, tmp_path, monkeypatch):
    """R2-F10: Die Meldung nennt die Ursache — nicht lesbar, mehrfach, fehlt."""
    root, home = decide_repo
    reference = tmp_path / "references" / "brief.md"
    reference.mkdir(parents=True)                                         # ein Ordner: nicht lesbar
    monkeypatch.setattr(dl, "BRIEF_REFERENCE", reference)
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 2 and message.startswith("ungeprüft — references/brief.md nicht lesbar ("), message
    reference.rmdir()
    for text, start in (("## Der Satz für Subagenten\n\n> eins\n\n> zwei\n",
                         "ungeprüft — Satz für Subagenten mehrfach in references/brief.md"),
                        ("## Der Satz für Subagenten\n\nnur Prosa\n",
                         "ungeprüft — Satz für Subagenten fehlt in references/brief.md")):
        reference.write_text(text, encoding="utf-8")
        code, message = dl.write_brief(root, SESSION, "CLI", home)
        assert code == 2 and message.startswith(start), message
    assert not brief_file(root).exists()


# --- Prüfpunkt 4, Runde 3: Funde F1–F5 an brief -------------------------------------------

UNREAD = "offene große Fragen zum Thema möglich; nichts entscheiden, was teuer umkehrbar ist, sondern zurückgeben"


def test_brief_names_unread_ledger_in_fixed_rules(decide_repo, capsys):
    """R3-F1: Ist die Ablage unlesbar oder übersprungen, steht das am Anfang von Feste Vorgaben — der
    Subagent darf nicht glauben, es gebe keine offenen großen Fragen. Fehlt sie, bleibt der Auftrag still."""
    root, home = decide_repo
    assert big("--session", "A", *TWO, topic="CLI", question="Neue Abhängigkeit für die CLI?") == 0
    capsys.readouterr()
    ledger = root / "docs" / "big-decisions.md"
    ledger.write_text(ledger.read_text(encoding="utf-8").replace("schema: 1", "schema: 2"), encoding="utf-8")
    assert dl.write_brief(root, SESSION, "CLI", home)[0] == 0
    fixed = brief_sections(brief_file(root).read_text(encoding="utf-8"))["Feste Vorgaben"]
    assert fixed == [f"- Ablage docs/big-decisions.md nicht gelesen (schema 1 erwartet, 2 gefunden) — {UNREAD}"], fixed

    ledger.unlink()
    ledger.mkdir()                                                        # ein Ordner: nicht lesbar
    assert dl.write_brief(root, SESSION, "CLI", home)[0] == 0
    [line] = brief_sections(brief_file(root, 2).read_text(encoding="utf-8"))["Feste Vorgaben"]
    assert line.startswith("- Ablage docs/big-decisions.md nicht gelesen (nicht lesbar (") and line.endswith(UNREAD), line

    ledger.rmdir()
    assert dl.write_brief(root, SESSION, "CLI", home)[0] == 0
    assert brief_sections(brief_file(root, 3).read_text(encoding="utf-8"))["Feste Vorgaben"] == []


def test_brief_names_open_block_without_topic(decide_repo, capsys):
    """R3-F2: Ein offener Block ohne Zeile Thema (von Hand bearbeitet) steht unter Feste Vorgaben mit
    dem Auftrag, zu prüfen, ob er das Thema betrifft; ein abweichendes Thema bleibt draußen."""
    root, home = decide_repo
    write_ledger(root, ledger_block(4, "offen", "api:app/", question="Logformat wechseln?"),
                 ledger_block(5, "offen", "migration:migrations/", question="Spalte löschen?").replace("Thema: T\n", ""),
                 ledger_block(6, "offen", "api:app/", question="Konfig umbenennen?").replace("Thema: T\n", "Thema:\n"),
                 ledger_block(7, "freigegeben", "api:app/", question="Alias?").replace("Thema: T\n", ""))
    assert dl.write_brief(root, SESSION, "CLI", home)[0] == 0
    fixed = brief_sections(brief_file(root).read_text(encoding="utf-8"))["Feste Vorgaben"]
    assert fixed == ["- D-5 offen, ohne Thema: Spalte löschen? — prüfen, ob sie das Thema betrifft",
                     "- D-6 offen, ohne Thema: Konfig umbenennen? — prüfen, ob sie das Thema betrifft"], fixed


def test_brief_hint_names_where_lines_come_from(decide_repo, capsys):
    """R3-F3: Füllen erledigte Blöcke zum Thema die Zeilen, rät der Hinweis nicht nur „Regeln kürzen“,
    sondern nennt die Herkunft und auch ältere Einträge unter Schon entschieden."""
    root, home = decide_repo
    write_ledger(root, *[ledger_block(n, "abgelehnt", "api:app/", question=f"Frage {n}?").replace("Thema: T", "Thema: CLI")
                         for n in range(1, 16)])
    code, message = dl.write_brief(root, SESSION, "CLI", home)
    assert code == 0, message
    assert "Hinweis: Auftrag hat schon 23 Zeilen ohne Kopf, höchstens 25" in message, message
    assert "0 Regeln, 15 unter Schon entschieden" in message, message
    assert ("Regeln oder ältere Einträge unter Schon entschieden kürzen, die Zeilen zu offenen Fragen nie"
            in message), message


def test_subagent_sentence_ends_at_fence_or_list(decide_repo, tmp_path, monkeypatch):
    """R3-F4: Ein Codezaun, ein Listenpunkt, eine Überschrift oder ein HTML-Kommentar direkt nach dem
    Zitat beendet es wie in Markdown; nur andere Textzeilen setzen es ohne `>` fort."""
    root, home = decide_repo
    reference = tmp_path / "references" / "brief.md"
    reference.parent.mkdir()
    monkeypatch.setattr(dl, "BRIEF_REFERENCE", reference)
    for after in ("```\nbeispiel\n```", "~~~\nx\n~~~", "- Punkt", "* Punkt", "+ Punkt", "1. Punkt",
                  "#hashtag", "<!-- Kommentar -->"):
        reference.write_text(f"## Der Satz für Subagenten\n\n> Ein Satz.\n{after}\n", encoding="utf-8")
        assert dl.load_subagent_sentence(reference) == ("Ein Satz.", None), after
    reference.write_text("## Der Satz für Subagenten\n\n> Ein Satz.\n```\nx\n```\n", encoding="utf-8")
    assert dl.write_brief(root, SESSION, "CLI", home)[0] == 0
    reference.write_text("## Der Satz für Subagenten\n\n> Ein Satz,\nweiter.\n", encoding="utf-8")
    sentence, problem = dl.load_subagent_sentence(reference)
    assert sentence is None and "references/brief.md:4" in problem, problem


def test_section_heading_inside_fence_is_not_the_section(decide_repo, tmp_path, monkeypatch, capsys):
    """R3-F5: Eine Überschrift in einem Beispiel-Codezaun ist nicht der Anfang des Abschnitts."""
    root, _ = decide_repo
    reference = tmp_path / "references" / "brief.md"
    reference.parent.mkdir()
    reference.write_text("# Auftrag\n\nBeispiel:\n\n```\n## Wortliste\n- `foo`\n```\n\n## Wortliste\n\n- `sollte`\n"
                         "\n## Der Satz für Subagenten\n\n~~~\n## Der Satz für Subagenten\n> Beispiel.\n~~~\n\n"
                         "> Echter Satz.\n", encoding="utf-8")
    assert dl.load_wordlist(reference) == (("sollte",), None)
    assert dl.load_subagent_sentence(reference) == ("Echter Satz.", None)
    monkeypatch.setattr(dl, "BRIEF_REFERENCE", reference)
    path = brief_file(root)
    path.parent.mkdir(parents=True)
    path.write_text(filled_brief(), encoding="utf-8")
    code, out, err = brief_check(capsys, path)
    assert code == 0, (out, err)


# --- Funde des finalen Prüfpunkts (F1–F11) ------------------------------------------------

def git_calls(monkeypatch, wanted):
    """Spioniert `subprocess.run` in decide_log.py aus; Liste der git-Aufrufe, für die `wanted(argv)` gilt."""
    calls, real = [], subprocess.run

    def spy(argv, *args, **kwargs):
        if argv[:1] == ["git"] and wanted(argv):
            calls.append(list(argv))
        return real(argv, *args, **kwargs)

    monkeypatch.setattr(dl.subprocess, "run", spy)
    return calls


def diff_revs(argv):
    """Die Revisionen eines `git diff`-Aufrufs: nach `diff` und den Optionen, vor `--`."""
    return [arg for arg in argv[argv.index("diff") + 1:argv.index("--")] if not arg.startswith("-")]


def merge(root, branch):
    git(root, "-c", "user.email=t@example.org", "-c", "user.name=t", "merge", "-q", "--no-ff", "-m", "Merge", branch)


def test_check_merge_bang_compares_with_first_parent(decide_repo, monkeypatch, capsys):
    """Final-F1: `M^!` auf einem Merge-Commit nennt eine positive und zwei negative Revisionen; check
    vergleicht mit dem ersten Elternteil (wie `M^1..M`) statt mit einem kombinierten Diff und meldet die
    Migration, die über den Merge kam — mit Hinweis in der Ausgabe."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    commit(root, "Basis")
    git(root, "branch", "-M", "main")
    git(root, "checkout", "-q", "-b", "seite")
    (root / "migrations").mkdir()
    (root / "migrations" / "1.py").write_text("x\n", encoding="utf-8")
    commit(root, "Migration auf dem Branch")
    git(root, "checkout", "-q", "main")
    (root / "app.py").write_text("x\n", encoding="utf-8")
    commit(root, "main weiter")
    merge(root, "seite")
    calls = git_calls(monkeypatch, lambda argv: "diff" in argv)
    code, out, err = check_out(capsys, "HEAD^!")
    assert code == 1 and reported(out) == ["migrations/1.py"], (out, err)
    assert "Merge: verglichen mit erstem Elternteil" in out, out
    assert calls and all(diff_revs(argv) == ["HEAD^1", "HEAD"] for argv in calls), calls
    files, problem = dl.changed_files(root, "HEAD^!")
    assert problem is None and files.end == "HEAD" and list(files) == ["migrations/1.py"], (problem, files.end)


def test_check_diff_always_gets_base_and_end(decide_repo, monkeypatch, capsys):
    """Final-F1/F5: Basis und Ende kommen aus der Ausgabe von `git rev-parse`; `git diff` bekommt nie die
    rohe Angabe, sondern `<basis> <ende>` — bzw. nur `<rev>` (gegen den Arbeitsbaum) bei einer
    Einzelrevision. Linearer Bereich, `HEAD^!`, `HEAD^-`, `<a>...<b>` mit Merge-Base ≠ linke Seite,
    Root-Commit `R^!` (leerer Baum) und `HEAD` mit unversionierter Datei."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    first = commit(root, "erster Commit")
    git(root, "branch", "-M", "main")
    (root / "app.py").write_text("x\n", encoding="utf-8")
    fork = commit(root, "app")
    git(root, "checkout", "-q", "-b", "feature")
    (root / "migrations").mkdir()
    (root / "migrations" / "0001.py").write_text("x\n", encoding="utf-8")
    commit(root, "Migration")
    git(root, "checkout", "-q", "main")
    (root / "db").mkdir()
    (root / "db" / "schema.sql").write_text("x\n", encoding="utf-8")
    commit(root, "main weiter")
    git(root, "checkout", "-q", "feature")
    (root / "migrations" / "0002.py").write_text("x\n", encoding="utf-8")            # unversioniert
    empty = git(root, "hash-object", "-t", "tree", "/dev/null").strip()
    cases = (
        (f"{first}..HEAD", [first, "HEAD"], ["app.py", "migrations/0001.py"]),
        ("HEAD^!", ["HEAD^1", "HEAD"], ["migrations/0001.py"]),
        ("HEAD^-", ["HEAD^1", "HEAD"], ["migrations/0001.py"]),
        ("main...feature", [fork, "feature"], ["migrations/0001.py"]),
        (f"{first}^!", [empty, first], ["README.md", "pyproject.toml"]),
        ("HEAD", ["HEAD"], ["migrations/0002.py"]),
    )
    for rev, revs, expected in cases:
        calls = git_calls(monkeypatch, lambda argv: "diff" in argv)
        files, problem = dl.changed_files(root, rev)
        assert problem is None and list(files) == expected, (rev, problem, list(files))
        assert files.revs == tuple(revs), (rev, files.revs)
        assert calls and all(diff_revs(argv) == revs for argv in calls), (rev, calls)
        assert (files.end is None) == (rev == "HEAD"), (rev, files.end)
    code, out, _ = check_out(capsys, "HEAD")
    assert code == 1 and reported(out) == ["migrations/0002.py"], out
    code, out, _ = check_out(capsys, "main...feature")
    assert code == 1 and reported(out) == ["migrations/0001.py"] and "Merge:" not in out, out


def test_key_pattern_must_be_relative_to_root(decide_repo, monkeypatch, capsys):
    """Final-F2: Ein führendes `./` im Pfadmuster fällt weg; ein absoluter Pfad oder `..` trifft nie einen
    Diff-Pfad — add weist ihn mit Exit 1 ab, check nennt ihn von Hand in der Ablage als Hinweis."""
    root, _ = decide_repo
    assert big(*TWO, key="dependency:./pyproject.toml") == 0, capsys.readouterr().err
    assert "\nSchlüssel: dependency:pyproject.toml\n" in ledger_text(root)
    capsys.readouterr()
    for bad in ("dependency:/srv/pyproject.toml", "dependency:../pyproject.toml", "migration:migrations/../x/",
                "migration:.."):
        assert big(*TWO, question=f"{bad}?", key=bad) == 1, bad
        assert "Pfadmuster muss relativ zur Repo-Wurzel sein" in capsys.readouterr().err, bad
    assert blocks_in(root) == ["D-1"]

    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root, "Basis")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:./pyproject.toml"),
                 ledger_block(2, "freigegeben", "migration:../migrations/"))
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (root / "migrations").mkdir()
    (root / "migrations" / "0001.py").write_text("x\n", encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["migrations/0001.py"], out
    assert ("Hinweis: D-2 Schlüssel „migration:../migrations/“ hat ein Pfadmuster außerhalb der Repo-Wurzel — "
            "Pfadmuster muss relativ zur Repo-Wurzel sein — gibt nichts frei.") in out, out


def test_repeated_add_after_resolve_asks_no_second_time(decide_repo, capsys):
    """Final-F3: Steht die Frage mit gleichem Schlüssel, gleichen Optionen und gleicher Empfehlung schon
    freigegeben in der Ablage, legt ein wiederholtes add keinen neuen offenen Block an; Exit 0, die Ausgabe
    nennt Status und Antwort, nur eine fehlende Protokollzeile wird nachgeholt. Nach abgelehnt ist es eine
    neue Frage (Final-R2-F3)."""
    root, _ = decide_repo
    assert big(*TWO) == 0
    assert dl.main(["resolve", "D-1", "--answer", "B: strptime"]) == 0
    capsys.readouterr()
    assert big(*TWO) == 0
    out = capsys.readouterr().out
    assert "D-1 ist schon freigegeben (Antwort: B: strptime)" in out, out
    assert "Bis zur Freigabe" not in out and "Protokollzeile für D-1 steht schon." in out, out
    assert blocks_in(root) == ["D-1"]
    assert big(*TWO, "--session", "sitzung-2") == 0                       # andere Sitzung: nur die Zeile
    assert "Protokollzeile für D-1 ergänzt." in capsys.readouterr().out
    assert [(r[2], r[4]) for r in rows(root, "sitzung-2")] == [("gross", "D-1")]

    assert big(*TWO, question="Zweite?") == 0
    assert dl.main(["resolve", "D-2", "--reject"]) == 0
    capsys.readouterr()
    other = ("--option", "A: x", "--option", "B: y", "--recommendation", "A")   # nach abgelehnt: neue Frage
    assert big(*other, question="Zweite?") == 0
    assert "D-2 war abgelehnt; neue Frage D-3" in capsys.readouterr().out
    assert blocks_in(root) == ["D-1", "D-2", "D-3"]
    assert [(r[2], r[4]) for r in rows(root)] == [("gross", "D-1"), ("gross", "D-2"), ("gross", "D-3")]
    # ein Auftrag nach der Ablehnung ist eine neue Antwort; nach einer Freigabe nicht
    assert big("--approved-by-request", "nimm doch python-dateutil", question="Zweite?") == 0
    assert big("--approved-by-request", "nimm python-dateutil", question="Datumsangaben parsen?") == 0
    assert "D-1 ist schon freigegeben" in capsys.readouterr().out
    assert blocks_in(root) == ["D-1", "D-2", "D-3", "D-4"]


def test_hash_key_ignores_removed_line(decide_repo, monkeypatch, capsys):
    """Final-R2-F1 (vorher Final-F4): `#<text>` trifft nur hinzugefügte Zeilen — das Entfernen der
    Abhängigkeit gibt es nicht frei, das Aufnehmen schon."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "pyproject.toml").write_text('[project]\ndependencies = [\n  "python-dateutil",\n  "requests",\n]\n',
                                         encoding="utf-8")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml#python-dateutil"))
    base = commit(root, "Basis")
    (root / "pyproject.toml").write_text('[project]\ndependencies = [\n  "requests",\n]\n', encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["pyproject.toml"], out
    assert "„python-dateutil“ in keiner hinzugefügten Zeile" in out, out
    (root / "pyproject.toml").write_text('[project]\ndependencies = [\n  "python-dateutil>=2",\n]\n',
                                         encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 0 and reported(out) == [], out


def test_atomic_writes_keep_lf_where_the_platform_translates(decide_repo, monkeypatch):
    """Final-F6: Übersetzt die Plattform Zeilenenden beim Schreiben im Textmodus (Windows: CRLF), bleiben
    Ablage und Protokoll trotzdem bei LF — nachgestellt, indem `open` im Textmodus ohne `newline` CRLF schreibt."""
    import builtins
    import io
    root, _ = decide_repo
    real = io.open

    def windows(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, *args, **kwargs):
        if "b" not in mode and newline is None and any(c in mode for c in "wax+"):
            newline = "\r\n"
        return real(file, mode, buffering, encoding, errors, newline, *args, **kwargs)

    monkeypatch.setattr(io, "open", windows)
    monkeypatch.setattr(builtins, "open", windows)
    assert big(*TWO) == 0
    assert dl.main(["resolve", "D-1", "--answer", "B"]) == 0
    monkeypatch.undo()
    assert b"\r" not in (root / "docs" / "big-decisions.md").read_bytes()
    assert b"\r" not in log_file(root).read_bytes()


def test_write_atomic_hidden_temp_and_orphans_removed(tmp_path, monkeypatch):
    """Final-F7: Die Nachbardatei beginnt mit einem Punkt (`.big-decisions.md.<pid>.tmp`); verwaiste
    Nachbardateien desselben Musters, älter als 60 s, räumt das nächste Schreiben weg, jüngere und
    fremde bleiben."""
    folder = tmp_path / "docs"
    folder.mkdir()
    target = folder / "big-decisions.md"
    old, fresh, other = (folder / ".big-decisions.md.4242.tmp", folder / ".big-decisions.md.4343.tmp",
                         folder / ".anders.md.4242.tmp")
    for path in (old, fresh, other):
        path.write_text("halb", encoding="utf-8")
    past = time.time() - 120
    for path in (old, other):
        os.utime(path, (past, past))
    seen, real = [], os.replace

    def spy(src, dst):
        seen.append(Path(src).name)
        return real(src, dst)

    monkeypatch.setattr(dl.os, "replace", spy)
    dl.write_atomic(target, "x\n")
    assert seen == [f".big-decisions.md.{os.getpid()}.tmp"], seen
    assert sorted(p.name for p in folder.iterdir()) == [".anders.md.4242.tmp", ".big-decisions.md.4343.tmp",
                                                        "big-decisions.md"]


def test_check_one_diff_for_all_hash_keys(decide_repo, monkeypatch, capsys):
    """Final-F8: Für alle Dateien mit `#<text>`-Freigabe ein `git diff -U0`, aufgeteilt an den Köpfen
    `diff --git` — auch bei Pfaden mit Leerzeichen, Umlaut oder Tab (von Git in Anführungszeichen)."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    paths = ["pyproject.toml", "ä b/pyproject.toml", "s\tv/pyproject.toml", "x\tok/pyproject.toml", "requirements.txt"]
    for name in paths:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("[project]\n", encoding="utf-8")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:**/pyproject.toml#python-dateutil"),
                 ledger_block(2, "freigegeben", "dependency:requirements.txt#requests"))
    base = commit(root, "Basis")
    for name in paths:
        text = "requests\n" if name == "requirements.txt" else "anderes\n" if name.startswith("s\t") else "python-dateutil\n"
        (root / name).write_text("[project]\n" + text, encoding="utf-8")
    calls = git_calls(monkeypatch, lambda argv: "-U0" in argv)
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["s\tv/pyproject.toml"], out
    assert len(calls) == 1, calls


def test_check_asks_git_for_root_once(decide_repo, monkeypatch, capsys):
    """Final-F9, seit Final-R3-F3: changed_files fragt zuerst in einem Aufruf, ob es einen Arbeitsbaum gibt,
    dann die Wurzel allein (`--show-toplevel`), dann Basis und Ende — Wurzel und Revisionen kommen nie aus
    derselben Ausgabe."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    base = commit(root, "Basis")
    (root / "pyproject.toml").write_text("x\n", encoding="utf-8")
    calls = git_calls(monkeypatch, lambda argv: "rev-parse" in argv)
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["pyproject.toml"], out
    assert len(calls) == 4, calls                                           # repo_root, dann changed_files
    assert calls[1][-3:] == ["--is-bare-repository", "--is-inside-work-tree", "--git-dir"], calls
    assert calls[2][-2:] == ["rev-parse", "--show-toplevel"], calls
    assert "--symbolic" in calls[3] and "--show-toplevel" not in calls[3], calls


def test_brief_header_command_stays_copyable(decide_repo):
    """Final-F10: Nur `-->` (und `--!>`) im Thema wird unschädlich gemacht; ein Thema mit `--` steht
    wörtlich im Befehl der Kopfzeile, der kopierte Befehl sucht dasselbe Thema."""
    root, home = decide_repo
    prefix = "<!-- skill: decide | schema: 1 | generated: "
    for number, topic in enumerate(("--verbose Hilfe", "a -- b", "x--y"), 1):
        assert dl.write_brief(root, SESSION, topic, home)[0] == 0
        head = brief_file(root, number).read_text(encoding="utf-8").splitlines()[0]
        assert head.startswith(prefix) and head.endswith(" -->") and dl.HEADER_RE.match(head), head
        command = head[len(prefix):-len(" -->")]
        flag = [f"--topic={topic}"] if topic.startswith("-") else ["--topic", topic]   # Final-R2-F4
        assert shlex.split(command) == ["python", "decide_log.py", "brief", *flag], head


# --- Funde des finalen Prüfpunkts, Runde 2 (F1–F9) ---------------------------------------

def test_hash_key_added_does_not_free_deletion(decide_repo, monkeypatch, capsys):
    """Final-R2-F1: `#<text>` trifft nur hinzugefügte Zeilen — `migration:migrations/#add_index` gibt das
    Anlegen der Migration frei, das Löschen derselben Datei nicht."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    write_ledger(root, ledger_block(1, "freigegeben", "migration:migrations/#add_index"))
    base = commit(root, "Basis")
    (root / "migrations").mkdir()
    (root / "migrations" / "0003_add_index.py").write_text("def up(): add_index('t', 'c')\n", encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 0 and reported(out) == [], out
    added = commit(root, "Migration")
    (root / "migrations" / "0003_add_index.py").unlink()
    code, out, _ = check_out(capsys, added)
    assert code == 1 and reported(out) == ["migrations/0003_add_index.py"], out
    assert "„add_index“ in keiner hinzugefügten Zeile" in out, out


def test_hash_minus_key_frees_only_removed_line(decide_repo, monkeypatch, capsys):
    """Final-R2-F1: `#-<text>` trifft nur entfernte Zeilen — `dependency:pyproject.toml#-python-dateutil` gibt
    das Entfernen der Abhängigkeit frei, das Aufnehmen nicht; `#-` ohne Text ist kein Schlüssel."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "pyproject.toml").write_text('[project]\ndependencies = [\n  "python-dateutil",\n  "requests",\n]\n',
                                         encoding="utf-8")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml#-python-dateutil"))
    base = commit(root, "Basis")
    (root / "pyproject.toml").write_text('[project]\ndependencies = [\n  "requests",\n]\n', encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 0 and reported(out) == [], out
    (root / "pyproject.toml").write_text('[project]\ndependencies = [\n  "python-dateutil",\n  "requests",\n'
                                         '  "python-dateutil-extra",\n]\n', encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["pyproject.toml"], out
    assert "„python-dateutil“ in keiner entfernten Zeile" in out, out
    assert dl.parse_key("dependency:pyproject.toml#- python-dateutil")[0] == (     # Final-R3-F4: Richtung getrennt
        "dependency", "pyproject.toml", "-", "python-dateutil")
    assert dl.parse_key("dependency:pyproject.toml#-  ") == (None, "hat leeren Text nach #-")


def test_repeated_add_after_reject_opens_new_question(decide_repo, capsys):
    """Final-R2-F3: Nach `abgelehnt` legt ein erneutes add einen neuen offenen Block an, mit Hinweis auf den
    alten; nach `freigegeben` nur bei anderen Optionen oder anderer Empfehlung."""
    root, _ = decide_repo
    assert big(*TWO) == 0
    assert dl.main(["resolve", "D-1", "--reject"]) == 0
    capsys.readouterr()
    assert big(*TWO) == 0
    out = capsys.readouterr().out
    assert "D-1 war abgelehnt; neue Frage D-2" in out and "D-2 offen in" in out, out
    assert blocks_in(root) == ["D-1", "D-2"]
    assert big(*TWO) == 0                                                  # Wiederholung: derselbe offene Block
    assert "D-2 steht schon offen" in capsys.readouterr().out
    assert dl.main(["resolve", "D-2", "--answer", "B"]) == 0
    capsys.readouterr()
    assert big(*TWO) == 0                                                  # gleiche Optionen: beantwortet
    assert "D-2 ist schon freigegeben (Antwort: B)" in capsys.readouterr().out
    other = ("--option", "A: x", "--option", "B: y", "--recommendation", "A")
    assert big(*other) == 0                                                # andere Optionen: neue Frage
    out = capsys.readouterr().out
    assert "D-2 war freigegeben; neue Frage D-3" in out and "D-3 offen in" in out, out
    assert blocks_in(root) == ["D-1", "D-2", "D-3"]


def test_brief_header_topic_with_leading_dash(decide_repo):
    """Final-R2-F4: Die Kopfzeile schreibt `--topic=<thema>`; auch ein Thema mit führendem `-` läuft im
    kopierten Befehl durch argparse."""
    root, home = decide_repo
    assert dl.write_brief(root, SESSION, "--dry-run", home)[0] == 0
    head = brief_file(root).read_text(encoding="utf-8").splitlines()[0]
    command = shlex.split(head[len("<!-- skill: decide | schema: 1 | generated: "):-len(" -->")])
    assert command[2:] == ["brief", "--topic=--dry-run"], head
    assert dl.main(command[2:]) == 0


def test_check_hash_diff_in_chunks_and_failure_is_visible(decide_repo, monkeypatch, capsys):
    """Final-R2-F5: Die Pfade für `#<text>` gehen in Blöcken von höchstens `DIFF_CHUNK` an `git diff`;
    scheitert ein Block, endet check mit Exit 2 statt still leerer Zeilen."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    names = [f"m{n}/pyproject.toml" for n in range(5)]
    for name in names:
        (root / name).parent.mkdir()
        (root / name).write_text("[project]\n", encoding="utf-8")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:**/pyproject.toml#python-dateutil"))
    base = commit(root, "Basis")
    for name in names:
        (root / name).write_text("[project]\npython-dateutil\n", encoding="utf-8")
    monkeypatch.setattr(dl, "DIFF_CHUNK", 2)
    calls = git_calls(monkeypatch, lambda argv: "-U0" in argv)
    code, out, _ = check_out(capsys, base)
    assert code == 0 and reported(out) == [], out
    assert [len(c[c.index("--", c.index("diff")) + 1:]) for c in calls] == [2, 2, 1], calls

    real = subprocess.run

    def broken(argv, *args, **kwargs):
        if argv[:1] == ["git"] and "-U0" in argv:
            raise OSError("Argumentliste zu lang")
        return real(argv, *args, **kwargs)

    monkeypatch.setattr(dl.subprocess, "run", broken)
    code, out, err = check_out(capsys, base)
    assert code == 2, (out, err)
    assert "ungeprüft — git diff für #<text>-Freigaben gescheitert (Argumentliste zu lang)" in err, err
    assert err.splitlines()[-1] == TAIL


def test_check_takes_root_from_git(decide_repo, monkeypatch, capsys):
    """Final-R2-F6: Fällt `repo_root` auf das Arbeitsverzeichnis zurück (hier ein Unterordner), nimmt check
    die Wurzel aus demselben `git rev-parse`, das Basis und Ende liest — die Ablage liegt dort."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("x\n", encoding="utf-8")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"))
    base = commit(root, "Basis")
    (root / "pyproject.toml").write_text("x\n", encoding="utf-8")
    monkeypatch.chdir(root / "src")
    monkeypatch.setattr(dl, "repo_root", lambda cwd: Path(cwd))
    code, out, _ = check_out(capsys, base)
    assert code == 0 and reported(out) == [] and "fehlt" not in out, out
    assert "1 Dateien im Diff, 1 mit Kategorie" in out, out


def test_check_range_without_common_base(decide_repo, monkeypatch, capsys):
    """Final-R2-F7: `<a>...<b>` ohne gemeinsame Historie: „keine gemeinsame Basis“, nicht „mehrere Enden“."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    commit(root, "main")
    main_branch = git(root, "branch", "--show-current").strip()
    git(root, "checkout", "-q", "--orphan", "waise")
    (root / "b.txt").write_text("b\n", encoding="utf-8")
    commit(root, "waise")
    code, out, err = check_out(capsys, f"waise...{main_branch}")
    assert code == 2, (out, err)
    assert f"ungeprüft — keine gemeinsame Basis (waise...{main_branch})" in err, err


# --- Funde des finalen Prüfpunkts, Runde 3 (Mini-Runde F1–F4) ------------------------------

def test_repeated_add_on_request_approval_asks_nothing(decide_repo, capsys):
    """Final-R3-F1: Steht die Frage mit gleichem Schlüssel per Auftrag freigegeben, legt ein späteres add
    mit Optionen keinen offenen Block an — die leeren Optionen des Auftragsblocks zählen nicht."""
    root, _ = decide_repo
    assert big("--approved-by-request", "nimm python-dateutil auf") == 0
    capsys.readouterr()
    assert big(*TWO) == 0
    out = capsys.readouterr().out
    assert "D-1 ist schon freigegeben (Auftrag: „nimm python-dateutil auf“)" in out, out
    assert "Bis zur Freigabe" not in out and "D-2" not in out, out
    assert blocks_in(root) == ["D-1"]


def test_only_newest_block_per_question_and_key_counts(decide_repo, capsys):
    """Final-R3-F2: Wird eine freigegebene Frage mit anderen Optionen neu gestellt, gilt nur der jüngste
    Block: check gibt den Schlüssel nicht mehr frei, add nimmt nicht den älteren als Antwort, brief
    zeigt ihn nicht mehr unter Schon entschieden."""
    root, home = decide_repo
    assert big(*TWO) == 0
    assert dl.main(["resolve", "D-1", "--answer", "B: strptime"]) == 0
    assert big("--option", "A: x", "--option", "B: y", "--recommendation", "A") == 0
    assert "D-1 war freigegeben; neue Frage D-2" in capsys.readouterr().out
    base = commit(root, "Basis")
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 1 and reported(out) == ["pyproject.toml"], out
    assert "D-2 dependency:pyproject.toml steht offen, D-1 überholt" in out, out

    assert big(*TWO) == 1                                     # alte Optionen: nicht D-1, sondern D-2 offen
    assert "D-2 steht offen mit anderen Optionen" in capsys.readouterr().err
    assert blocks_in(root) == ["D-1", "D-2"]

    code, message = dl.write_brief(root, SESSION, "Abhängigkeiten", home)
    assert code == 0, message
    sections = brief_sections(brief_file(root).read_text(encoding="utf-8"))
    assert sections["Schon entschieden"] == ["—"], sections
    assert [line for line in sections["Feste Vorgaben"] if "D-" in line] == [
        "- D-2 offen: Datumsangaben parsen? — nicht entscheiden, nicht darauf aufbauen"], sections


def test_check_in_bare_clone_and_git_dir(decide_repo, monkeypatch, tmp_path, capsys):
    """Final-R3-F3: Im Bare-Clone (CI-Hook) und aus `.git` heraus läuft check über einen Bereich und liest
    die Ablage aus dessen Ende; eine Einzelrevision braucht einen Arbeitsbaum (Exit 2 mit diesem Grund)."""
    root, _ = decide_repo
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    commit(root, "Basis")
    write_ledger(root, ledger_block(1, "freigegeben", "dependency:pyproject.toml"),
                 ledger_block(2, "freigegeben", "dependency:requirements.txt#requests"))
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (root / "requirements.txt").write_text("flask\n", encoding="utf-8")
    commit(root, "Abhängigkeiten")
    bare = tmp_path / "bare.git"
    git(tmp_path, "clone", "-q", "--bare", str(root), str(bare))
    for where in (bare, root / ".git"):
        monkeypatch.chdir(where)
        code, out, err = check_out(capsys, "HEAD~1..HEAD")
        assert code == 1 and reported(out) == ["requirements.txt"], (where, out, err)
        assert "„requests“ in keiner hinzugefügten Zeile" in out and "Freigaben aus HEAD;" in out, out
        assert out.splitlines()[-1] == TAIL
        code, out, err = check_out(capsys, "HEAD")
        assert code == 2, (where, out, err)
        assert "ungeprüft — Einzelrevision braucht einen Arbeitsbaum" in err, err
        assert err.splitlines()[-1] == TAIL


def test_hash_plus_key_for_added_line_with_leading_dash(decide_repo, capsys):
    """Final-R3-F4: `#+<text>` ist die ausdrückliche Form für hinzugefügte Zeilen und nötig, wenn der Text
    selbst mit `-` beginnt; parse_key liefert Richtung und Text getrennt; add schreibt `#<text>`, wo die
    Kurzform eindeutig ist, sonst `#+<text>`."""
    root, _ = decide_repo
    key = "dependency:requirements.txt#+--extra-index-url https://x"
    assert dl.parse_key(key)[0] == ("dependency", "requirements.txt", "+", "--extra-index-url https://x")
    assert dl.parse_key("dependency:requirements.txt#--extra-index-url https://x")[0] == (
        "dependency", "requirements.txt", "-", "-extra-index-url https://x")
    assert dl.parse_key("dependency:requirements.txt#requests")[0] == ("dependency", "requirements.txt", "+", "requests")
    assert dl.parse_key("dependency:requirements.txt#+ ") == (None, "hat leeren Text nach #+")
    assert dl.KEY_FORM == "<kategorie>:<pfadmuster>[#[+|-]<text>]"

    assert big("--approved-by-request", "Index ergänzen", question="Index?", key=key) == 0
    assert big("--approved-by-request", "nimm dateutil", key="dependency:pyproject.toml#+python-dateutil") == 0
    text = ledger_text(root)
    assert f"Schlüssel: {key}\n" in text and "Schlüssel: dependency:pyproject.toml#python-dateutil\n" in text, text
    (root / "requirements.txt").write_text("requests\n", encoding="utf-8")
    base = commit(root, "Basis")
    (root / "requirements.txt").write_text("--extra-index-url https://x\nrequests\n", encoding="utf-8")
    code, out, _ = check_out(capsys, base)
    assert code == 0 and reported(out) == [], out
