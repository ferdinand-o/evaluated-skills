"""Tests für skills/decide/scripts/decide_log.py (Spec 28, Task 1): Wurzel und Sitzung,
Form der Belegzeile, Tabellenzeichen und Umlaute, Regeln aus Repo- und Nutzerdatei."""

import os
import re
import threading
import time
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


def test_concurrent_add_keeps_both_rows(decide_repo, monkeypatch):
    """F3: Ein zweites add zwischen Lesen und Ersetzen des ersten verliert keine Zeile."""
    root, home = decide_repo
    assert dl.add_small(root, SESSION, small_args(home, question="Vorher?"))[0] == 0
    read_log, paused, release = dl.read_log, threading.Event(), threading.Event()

    def slow_read(*args):
        text = read_log(*args)
        if threading.current_thread().name == "A" and not paused.is_set():
            paused.set()
            release.wait(5)
        return text

    monkeypatch.setattr(dl, "read_log", slow_read)
    codes = {}

    def run(name):
        codes[name] = dl.add_small(root, SESSION, small_args(home, question=f"Frage {name}?"))[0]

    first = threading.Thread(target=run, args=("A",), name="A")
    first.start()
    assert paused.wait(5)
    second = threading.Thread(target=run, args=("B",), name="B")
    second.start()
    second.join(0.3)                                # ohne Sperre ist B hier schon fertig
    release.set()
    first.join(5)
    second.join(5)
    assert codes == {"A": 0, "B": 0}
    assert sorted(r[3] for r in rows(root)) == ["Frage A?", "Frage B?", "Vorher?"]
    assert not log_file(root).with_name("log.md.lock").exists()


def test_lock_timeout_writes_nothing(decide_repo, monkeypatch, capsys):
    """F3: Bleibt die Sperre bestehen, endet add nach der Zeitgrenze mit 1 und sichtbarem Grund."""
    root, _ = decide_repo
    assert add_small("CLI", "Vorher?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    lock = log_file(root).with_name("log.md.lock")
    lock.write_text("fremd\n", encoding="utf-8")
    monkeypatch.setattr(dl, "LOCK_WAIT", 0.1, raising=False)
    capsys.readouterr()
    assert add_small("CLI", "Danach?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 1
    err = capsys.readouterr().err
    assert "log.md.lock" in err and "nichts geschrieben" in err, err
    assert [r[3] for r in rows(root)] == ["Vorher?"]
    assert lock.read_text(encoding="utf-8") == "fremd\n"     # fremde Sperre bleibt


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
    assert add_small("Parser", "Trenner?", ";", "gesucht: . — Treffer: ./parser.py:12") == 0
    assert rows(root)[0][5] == "gesucht: . — Treffer: src/parser.py:12"


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
    assert not log_file(root).with_name("log.md.lock").exists()

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


def dead_pid():
    """PID eines eben beendeten Prozesses."""
    import subprocess
    import sys
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


@pytest.mark.skipif(os.name == "nt", reason="unter Windows zählt nur das Alter der Sperre")
def test_lock_of_dead_process_is_taken_over(decide_repo, capsys):
    """R2-F3: Eine Sperre, deren Prozess nicht mehr lebt (add per SIGKILL beendet), wird übernommen."""
    root, _ = decide_repo
    assert add_small("CLI", "Vorher?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    lock = log_file(root).with_name("log.md.lock")
    lock.write_text(f"{dead_pid()} 0123456789abcdef\n", encoding="ascii")
    assert add_small("CLI", "Danach?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0, capsys.readouterr().err
    assert [r[3] for r in rows(root)] == ["Vorher?", "Danach?"]
    assert not lock.exists()


def test_old_lock_is_taken_over(decide_repo, capsys):
    """R2-F3: Eine Sperre, die älter als 30 s ist, wird übernommen — auch wenn ihr Prozess noch lebt."""
    root, _ = decide_repo
    assert add_small("CLI", "Vorher?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    lock = log_file(root).with_name("log.md.lock")
    lock.write_text(f"{os.getpid()} fedcba9876543210\n", encoding="ascii")
    old = time.time() - 31
    os.utime(lock, (old, old))
    assert add_small("CLI", "Danach?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0, capsys.readouterr().err
    assert [r[3] for r in rows(root)] == ["Vorher?", "Danach?"]
    assert not lock.exists()


def test_lock_timeout_names_pid_and_age(decide_repo, monkeypatch, capsys):
    """R2-F3: Bei Zeitgrenze nennt die Meldung PID und Alter der Sperre."""
    root, _ = decide_repo
    assert add_small("CLI", "Vorher?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 0
    lock = log_file(root).with_name("log.md.lock")
    lock.write_text(f"{os.getpid()} 0011223344556677\n", encoding="ascii")
    old = time.time() - 5
    os.utime(lock, (old, old))
    monkeypatch.setattr(dl, "LOCK_WAIT", 0.1)
    capsys.readouterr()
    assert add_small("CLI", "Danach?", "kurz", "gesucht: cli.py — Treffer: cli.py:3") == 1
    err = capsys.readouterr().err
    assert re.search(rf"PID {os.getpid()}, \d+ s alt", err), err
    assert "nichts geschrieben" in err
    assert lock.exists()


def test_foreign_lock_is_not_removed(decide_repo, monkeypatch):
    """R2-F4: Ersetzt jemand die Sperre während add läuft, entfernt add sie am Ende nicht."""
    root, home = decide_repo
    assert dl.add_small(root, SESSION, small_args(home, question="Vorher?"))[0] == 0
    lock = log_file(root).with_name("log.md.lock")
    foreign = f"{os.getpid()} ffffffffffffffff\n"
    read_log = dl.read_log

    def swap_lock(*args):
        lock.unlink()                               # von Hand gelöscht, C sperrt neu
        lock.write_text(foreign, encoding="ascii")
        return read_log(*args)

    monkeypatch.setattr(dl, "read_log", swap_lock)
    assert dl.add_small(root, SESSION, small_args(home, question="A?"))[0] == 0
    assert lock.read_text(encoding="ascii") == foreign


def test_lock_retries_on_permission_error(decide_repo, monkeypatch):
    """R2-F5: PermissionError beim Anlegen der Sperre (Windows, Sperre wird gerade gelöscht)
    wird wie FileExistsError innerhalb der Zeitgrenze wiederholt."""
    root, home = decide_repo
    real_open, calls = dl.os.open, []

    def flaky_open(path, *args, **kwargs):
        if str(path).endswith(".lock") and not calls:
            calls.append(path)
            raise PermissionError(13, "Access is denied", str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(dl.os, "open", flaky_open)
    code, message = dl.add_small(root, SESSION, small_args(home))
    assert code == 0, message
    assert calls and len(rows(root)) == 1
    assert not log_file(root).with_name("log.md.lock").exists()


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
