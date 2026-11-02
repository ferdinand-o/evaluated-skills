"""Tests für skills/decide/scripts/decide_log.py (Spec 28, Task 1): Wurzel und Sitzung,
Form der Belegzeile, Tabellenzeichen und Umlaute, Regeln aus Repo- und Nutzerdatei."""

import errno
import os
import re
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
from conftest import decide_add_small as add_small
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
    """Lesefehler auf `name` simulieren — als root greift Modus 0200 nicht."""
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if self.name == name:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)


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
    assert log_file(root).read_bytes() == before

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
    # eine andere Frage ist ein neuer Block, ebenso dieselbe Frage nach der Antwort
    assert big(*TWO, question="Andere Frage?") == 0
    assert dl.main(["resolve", "D-1", "--answer", "B"]) == 0
    assert big(*TWO) == 0
    assert blocks_in(root) == ["D-1", "D-2", "D-3"]
    # per Auftrag: derselbe Auftrag ein zweites Mal legt ebenfalls keinen Block an
    capsys.readouterr()
    assert big("--approved-by-request", "nimm python-dateutil auf", question="Auftrag?") == 0
    assert big("--approved-by-request", "nimm python-dateutil auf", question="Auftrag?") == 0
    assert "D-4 steht schon" in capsys.readouterr().out
    assert blocks_in(root) == ["D-1", "D-2", "D-3", "D-4"]
    assert [r[4] for r in rows(root)] == ["D-1", "D-2", "D-3", "D-4"]


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
    assert big(*TWO, question="Dritte?", key="dependency:pyproject .toml") == 1
    assert "Leerraum" in capsys.readouterr().err
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

    rules = dl.load_rules(root, home)
    answers = [rules, []]                    # zweiter Lesevorgang sähe die Regel nicht mehr
    monkeypatch.setattr(dl, "load_rules", lambda *_: answers.pop(0) if answers else [])
    assert add_small("UI-Texte", "Text 3?", "A", "gesucht: a.py — Treffer: a.py:1", *flags) == 0
    err = capsys.readouterr().err
    assert "per Regel hochgestuften Frage" in err and "--option" not in err, err


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
