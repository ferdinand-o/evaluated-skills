#!/usr/bin/env python3
"""Protokoll eigener Entscheidungen für decide (Spec 28). Tier 1, nur Stdlib.

    decide_log.py rules                         wirksame Regeln mit Datei und Zeile
    decide_log.py add --class klein …           kleine Entscheidung oder Annahme mit Belegzeile
    decide_log.py add --class gross …           große Frage als Block D-<n> (offen oder per Auftrag freigegeben)
    decide_log.py resolve D-<n> --answer "…" | --reject   Antwort auf eine offene große Frage eintragen
    decide_log.py open                          offene große Fragen
    decide_log.py summary                       Einträge der laufenden Sitzung
    decide_log.py check --range <rev>           teure Änderungen seit <rev> ohne Freigabe, dann Übergabe
    decide_log.py guard                         PreToolUse-Hook auf Bash: Hook-JSON auf stdin, Exit immer 0

Aufruf: `python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py"`. Repo-Wurzel ist einmal
`git rev-parse --show-toplevel` (`repo_root`), sonst das Arbeitsverzeichnis. Die Sitzung ist
`--session`, sonst `CLAUDE_CODE_SESSION_ID`; nur `add` und `summary` brauchen sie,
`check` nennt mit ihr die Einträge der Sitzung.

Ablageorte:
- `.skills/cache/decide/<session>/log.md` — Protokoll der Sitzung
- `docs/big-decisions.md` — Ablage großer Fragen (committet); Sperre unter `.skills/cache/decide/`
- `.skills/decide/rules.md` und `~/.skills/decide/rules.md` — Regeln `immer fragen` / `nie fragen`

Regeln und Formate stehen nicht hier, sondern an je einer Stelle: Kategorien, Pfadmuster,
Schlüssel und was check sieht in `references/reversibility.md` — eine zweite Liste der Kategorien
und Pfadmuster im Skript gibt es nicht. Nur die Mustertabelle von guard steht als Konstante
`GUARD_PATTERNS` hier, weil die Hook-Kopie unter `.claude/hooks/` ohne `references/` und `assets/`
läuft; `reversibility.md` trägt dieselbe Tabelle, ein Test hält beide gleich. Ablage, Optionen und Empfehlung in
`references/option-memo.md`; Vorlage des Auftrags an einen Subagenten in
`references/brief.md` (kein Skript liest sie); Ablauf, Belegzeile und Regeln in `SKILL.md`. Die Funktions-Docstrings
beschreiben das Verhalten im Einzelnen.

Exit-Codes: 0 Erfolg; 1 abgewiesen oder nicht geschrieben (Grund auf stderr) bzw. bei check
mindestens ein Befund (Bericht auf stdout); 2 falscher Aufruf (argparse) und jedes
„ungeprüft — …“ (kein Git, Git antwortet nicht, Reference fehlt oder parst nicht), nie ein Erfolg.
`guard` endet immer mit 0: Rückfrage (`ask`) oder „[decide] Hook ungeprüft — …“ stehen im JSON.
Das Skript meldet; anhalten kann nur guard als installierter Hook, bis der Nutzer antwortet.
"""
import argparse
import errno
import functools
import json
import os
import posixpath
import re
import shlex
import stat
import subprocess
import sys
import time
from contextlib import contextmanager, suppress
from datetime import date, datetime
from pathlib import Path
from typing import NamedTuple

try:
    import fcntl
except ImportError:                     # Windows
    fcntl = None
try:
    import msvcrt
except ImportError:                     # POSIX
    msvcrt = None

SKILL = "decide"
SCHEMA = 1
LOG_HEADER = f"<!-- skill: {SKILL} | schema: {SCHEMA} | generated: python decide_log.py add -->"
HEADER_RE = re.compile(r"^<!-- skill: (?P<skill>[a-z0-9-]+) \| schema: (?P<schema>\d+) \| generated: .* -->$")
COLUMNS = ("zeit", "thema", "klasse", "frage", "entscheidung", "beleg", "regel")
TABLE_HEAD = "| " + " | ".join(COLUMNS) + " |\n|" + " --- |" * len(COLUMNS)
EVIDENCE_RE = re.compile(r"^gesucht: .+ — (Treffer: \S+:\d+|nichts gefunden)$")
EVIDENCE_FORM = "„gesucht: <ort> — Treffer: <datei:zeile>“ oder „gesucht: <ort> — nichts gefunden“"
RULE_FILE = Path(".skills") / "decide" / "rules.md"
RULE_KINDS = ("immer fragen", "nie fragen")
SUMMARY_LIMIT = 10
NONE = "—"
LOCK_WAIT = 2.0          # Sekunden, die add auf eine belegte Sperre wartet
LOCK_POLL = 0.05         # Schlaf zwischen den Versuchen
WRITE_ATTEMPTS = 3
TMP_MAX_AGE = 60         # Sekunden: ältere Nachbardateien von write_atomic gelten als verwaist
NO_LOCK_ERRNOS = {getattr(errno, name) for name in ("ENOLCK", "EOPNOTSUPP", "ENOTSUP", "ENOSYS")
                  if hasattr(errno, name)}   # das Dateisystem kann nicht sperren: wie fehlende Module
BIG_FLAGS = (("options", "--option"), ("recommendation", "--recommendation"), ("key", "--key"),
             ("approved_by_request", "--approved-by-request"))
SMALL_FLAGS = (("decision", "--decision"), ("evidence", "--evidence"))

LEDGER = Path("docs") / "big-decisions.md"
LEDGER_SHOWN = LEDGER.as_posix()
SKILL_DIR = Path(__file__).resolve().parent.parent
LEDGER_ASSET = SKILL_DIR / "assets" / "big-decisions.md"
LEDGER_LOCK = Path(".skills") / "cache" / "decide" / "big-decisions.md"   # Sperrdatei: dies + „.lock“
# Die eine Quelle für Kategorien, Grad und Pfadmuster (load_categories); keine zweite Liste davon im Skript.
REFERENCE = SKILL_DIR / "references" / "reversibility.md"
REFERENCE_COLUMNS = ("Kategorie", "Bedeutung", "Beispiel", "Grad", "Pfadmuster", "Grenze")
GRADES = ("geprüft", "teilweise", "ungeprüft")
TAIL_GRADES = ("ungeprüft", "teilweise")       # die Schlusszeile von check nennt diese
RULE_CATEGORY = "rule"
GIT_TIMEOUT = 60
KEY_FORM = "<kategorie>:<pfadmuster>[#<text>]"
STATUSES = ("offen", "freigegeben", "abgelehnt")
SOURCE_USER = "Nutzer in Sitzung"
OPTIONS_BY_REQUEST = "— (Auftrag)"
ANSWER_BY_REQUEST = "wie im Auftrag"
_REQUEST_SOURCE_RE = re.compile(r"^Auftrag: „.*“$")      # Quelle eines Blocks per Auftrag
BLOCK_RE = re.compile(r"^## (?P<id>D-(?P<number>\d+)) · (?P<date>\S+) · (?P<status>\S+)\s*$")
BLOCK_NUMBER_RE = re.compile(r"(?m)^## D-(\d+)\b")
SKIPPED = " — Freigaben übersprungen"
FIELDS = (("question", "Frage"), ("topic", "Thema"), ("key", "Schlüssel"), ("options", "Optionen"),
          ("recommendation", "Empfehlung"), ("answer", "Antwort"), ("source", "Quelle der Antwort"))


class Category(NamedTuple):
    """Eine Zeile der Tabelle in `references/reversibility.md`: `name` (`"migration"`), `meaning`
    (Bedeutung, der Grund in check), `example`, `grade` (aus `GRADES`), `patterns` (Tupel der
    Pfadmuster, leer bei `ungeprüft`), `limit` (Grenze, `—` wenn keine)."""
    name: str
    meaning: str
    example: str
    grade: str
    patterns: tuple
    limit: str


class Rule(NamedTuple):
    """Eine Regel: `kind` ist „immer fragen“ oder „nie fragen“, `topic` die Schreibweise der
    Regel, `path` die Datei, `source` deren Anzeige (`.skills/…` oder `~/.skills/…`), `line`
    die Zeilennummer."""
    kind: str
    topic: str
    path: Path
    source: str
    line: int


# --- Wurzel, Sitzung, Pfade ------------------------------------------------------------

def repo_root(cwd):
    """`git rev-parse --show-toplevel` in `cwd`, sonst `cwd` selbst."""
    cwd = Path(cwd)
    try:
        out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return cwd


def session_id(arg):
    """`--session`, sonst `CLAUDE_CODE_SESSION_ID`, sonst None."""
    value = (arg or "").strip() or os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    return value or None


def valid_session(session):
    """Die Sitzung wird Ordnername: kein Pfadtrenner, nicht `.` oder `..`."""
    return bool(session) and not re.search(r"[/\\]", session) and session not in (".", "..")


def home_dir():
    home = os.environ.get("HOME")
    return Path(home) if home else Path.home()


def log_path(root, session):
    return Path(root) / ".skills" / "cache" / "decide" / session / "log.md"


def shown(path, root):
    """Pfad relativ zur Wurzel, wo möglich, mit `/`."""
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return str(path)


# --- Regeln -----------------------------------------------------------------------------

def _rule_files(root, home):
    files = [(Path(root) / RULE_FILE, RULE_FILE.as_posix()),
             (Path(home) / RULE_FILE, "~/" + RULE_FILE.as_posix())]
    try:
        if files[0][0].resolve() == files[1][0].resolve():
            return files[:1]
    except OSError:
        pass
    return files


def _strip_comment(line):
    """`#` am Zeilenanfang oder nach Leerraum beginnt einen Kommentar (`C#` bleibt ganz)."""
    return re.split(r"(?:^|\s)#", line, maxsplit=1)[0].strip()


def read_rules(root, home):
    """(Regeln, ignorierte Zeilen als „<datei>:<zeile>: <text>“, Hinweise zu unlesbaren
    Regeldateien). Eine fehlende Datei bleibt still."""
    rules, ignored, problems = [], [], []
    for path, source in _rule_files(root, home):
        try:
            text = read_file(path)
        except Unreadable as error:
            problems.append("Hinweis: " + unreadable_problem(error, f"Regeln {source}",
                                                             " — ohne diese Regeln eingeordnet"))
            continue
        if text is None:
            continue
        for number, raw in enumerate(text.splitlines(), 1):
            line = _strip_comment(raw)
            if not line:
                continue
            kind, sep, topic = line.partition(":")
            kind = " ".join(kind.lower().split())
            if sep and kind in RULE_KINDS and topic.strip():
                rules.append(Rule(kind, topic.strip(), path, source, number))
            else:
                ignored.append(f"{source}:{number}: {raw.strip()}")
    return rules, ignored, problems


def load_rules(root, home):
    """Alle Regeln aus Repo- und Nutzerdatei als `Rule`, Repo-Datei zuerst; fehlende Dateien
    zählen nicht, Kommentare und ungültige Zeilen fallen weg; unlesbare auch — die Hinweise dazu
    gibt `read_rules` aus demselben Lesevorgang (add und rules lesen nur darüber)."""
    return read_rules(root, home)[0]


def _norm(topic):
    """Thema zum Vergleich, so wie es in der Tabellenzelle steht (`|` → `¦`, Leerraum
    zusammengezogen), klein geschrieben — add und summary vergleichen damit gleich."""
    return " ".join((topic or "").replace("|", "¦").split()).lower()


def _at_word_start(longer, shorter):
    """`shorter` steht in `longer` und beginnt dort ein Wort (`UI` in `UI-Texte`, nicht in `Build`);
    beginnt `shorter` mit einem Nicht-Wortzeichen, darf es mitten im Wort beginnen, muss dann aber
    am Ende stehen oder vor einem Nicht-Wortzeichen (`.NET` in `ASP.NET`, nicht in `config.network`)."""
    if not re.match(r"\w", shorter):
        return re.search(re.escape(shorter) + r"(?!\w)", longer) is not None
    return re.search(r"(?<!\w)" + re.escape(shorter), longer) is not None


def match_rules(rules, topic):
    """(Treffer, Hinweise): Treffer sind gleich nach `_norm`, Hinweise enthalten das Thema oder
    sind darin enthalten, jeweils ab einem Wortanfang."""
    wanted = _norm(topic)
    hits, hints = [], []
    for rule in rules:
        have = _norm(rule.topic)
        if have == wanted:
            hits.append(rule)
        elif wanted and have and (_at_word_start(wanted, have) or _at_word_start(have, wanted)):
            hints.append(rule)
    return hits, hints


def rule_label(rule):
    return f"{rule.kind}: {rule.topic}"


def rule_ref(rule):
    return f"{rule_label(rule)} ({rule.source})"


def contradiction(always, never):
    """Eine Zeile für ein Thema mit Regeln beider Arten; jede Datei je Seite einmal."""
    def side(rules):
        return f"{rule_label(rules[0])} ({', '.join(dict.fromkeys(r.source for r in rules))})"
    return f"Widerspruch: {side(always)} und {side(never)} — immer fragen gilt."


# --- Belegzeile -------------------------------------------------------------------------

_LINE_SUFFIX = re.compile(r"((?::\d+)+)$")
_RESULT_RE = re.compile(r"^(?P<head>.*) (?:--|-|–|—) (?P<result>Treffer: \S+|nichts gefunden)$")
_TRAILING = " .,;)"


def _under_root(path, root):
    """Absoluter Pfad relativ zur Wurzel, wo er darunter liegt — erst wörtlich, dann mit
    aufgelösten Symlinks auf beiden Seiten; sonst None."""
    root = Path(root)
    try:
        return Path(os.path.normpath(path)).relative_to(root).as_posix()
    except ValueError:
        pass
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None


def _norm_path(token, root):
    """Ein Token: `./…`/`../…`/`.`/`..` gegen das Arbeitsverzeichnis und ein absoluter Pfad werden
    relativ zur Wurzel, wenn sie darunter liegen, sonst bleiben sie; `:zeile` und ein Komma oder
    Semikolon am Ende bleiben stehen."""
    core, trail = re.match(r"^(.*?)([,;]*)$", token).groups()
    match = _LINE_SUFFIX.search(core)
    suffix = match.group(1) if match else ""
    path = core[: len(core) - len(suffix)]
    if path in (".", "..") or path.startswith(("./", "../")):
        try:
            cwd = Path.cwd()
        except OSError:
            cwd = Path(root)
        path = _under_root(os.path.normpath(os.path.join(cwd, path)), root) or path
    elif os.path.isabs(path):
        path = _under_root(path, root) or path
    return path + suffix + trail


def normalize_evidence(text, root):
    """Belegzeile in Normalform: `.`/`,`/`;`/`)` am Ende weg, der Trenner vor dem Ergebnis
    (` - `, ` -- `, ` – `) wird ` — `, Pfade relativ zur Wurzel. Prüft die Form nicht — das
    macht `EVIDENCE_RE`."""
    text = " ".join((text or "").split()).rstrip(_TRAILING)
    match = _RESULT_RE.match(text)
    if match:
        text = f"{match.group('head')} — {match.group('result')}"
    return " ".join(_norm_path(token, root) for token in text.split(" "))


def evidence_problem(evidence):
    """None bei gültiger Form, sonst der Grund."""
    if not evidence:
        return ("Keine Belegzeile — add --class klein braucht --evidence "
                f"{EVIDENCE_FORM}; nichts geschrieben.")
    if EVIDENCE_RE.match(evidence):
        return None
    if not evidence.startswith("gesucht: "):
        detail = "sie beginnt nicht mit „gesucht: “"
    elif " — " not in evidence:
        detail = "es fehlt „— Treffer: <datei:zeile>“ oder „— nichts gefunden“"
    else:
        detail = "nach „—“ steht weder „Treffer: <datei:zeile>“ noch „nichts gefunden“"
    return f"Belegzeile hat die falsche Form ({detail}): „{evidence}“ — erwartet {EVIDENCE_FORM}; nichts geschrieben."


# --- Protokoll --------------------------------------------------------------------------

def cell(text):
    """Wert für eine Tabellenzelle: `|` wird `¦`, Zeilenumbrüche werden Leerzeichen."""
    value = " ".join(str(text if text is not None else "").replace("|", "¦").split())
    return value or NONE


class Unreadable(Exception):
    """Protokoll oder Ablage besteht, lässt sich aber nicht lesen; `args[0]` ist der OSError."""


def decode_text(data):
    """Text aus Bytes wie beim Lesen einer Datei: `utf-8-sig` (ein BOM fällt weg), Zeilenenden als
    `\n` — für `read_file`."""
    return data.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def read_file(path):
    """Rohtext von `path` (`decode_text`); None, wenn die Datei fehlt. Jeder andere Lesefehler
    wirft `Unreadable` — eine unlesbare Datei ist nicht fehlend."""
    try:
        return decode_text(Path(path).read_bytes())
    except FileNotFoundError:
        return None
    except OSError as error:
        raise Unreadable(error) from error


def _blank_is_missing(text):
    return text if text is not None and text.strip() else None


def read_log(root, session):
    """Text des Protokolls; None, wenn es fehlt oder nur Leerraum enthält; `Unreadable` sonst."""
    return _blank_is_missing(read_file(log_path(root, session)))


def unreadable_problem(error, what, tail="; nichts geschrieben."):
    """Eine Zeile Grund für eine unlesbare Datei; `what` nennt sie („Protokoll <pfad>“, Ablage)."""
    cause = error.args[0]
    return f"{what} nicht lesbar ({getattr(cause, 'strerror', None) or cause}){tail}"


def log_shown(root, session):
    return f"Protokoll {shown(log_path(root, session), root)}"


def header_problem(text, path_shown, tail="übersprungen"):
    """Konsumenten-Regel (docs/artifact-header.md): None, wenn die Kopfzeile passt, sonst der
    Grund, der mit „— <tail>“ endet."""
    first = next((line for line in text.splitlines() if line.strip()), "")
    match = HEADER_RE.match(first.strip())
    if not match or match.group("skill") != SKILL:
        return f"{path_shown} ohne Kopfzeile von decide — {tail}"
    if int(match.group("schema")) > SCHEMA:
        return f"{path_shown} schema {SCHEMA} erwartet, {match.group('schema')} gefunden — {tail}"
    return None


def parse_rows(text):
    """Einträge des Protokolls als dicts mit den Schlüsseln aus `COLUMNS`, älteste zuerst."""
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("| ") or line.startswith(("| zeit ", "| ---")):
            continue
        cells = [c.strip() for c in line[1:-1].split("|")]
        if len(cells) == len(COLUMNS):
            entries.append(dict(zip(COLUMNS, cells)))
    return entries


def log_entries(root, session):
    """(Einträge, Problem): Einträge der Sitzung, oder [] und ein Grund nach der
    Konsumenten-Regel oder weil es nicht lesbar ist; ein fehlendes Protokoll ist kein Problem."""
    try:
        text = read_log(root, session)
    except Unreadable as error:
        return [], unreadable_problem(error, log_shown(root, session), " — übersprungen")
    if text is None:
        return [], None
    problem = header_problem(text, shown(log_path(root, session), root))
    return ([], problem) if problem else (parse_rows(text), None)


def _remove_orphans(path):
    """Räumt verwaiste Nachbardateien von `path` weg (`.<name>.<pid>.tmp`, älter als `TMP_MAX_AGE`
    Sekunden — ein abgebrochener Prozess hinterlässt sie); jüngere gehören einem laufenden Schreiber."""
    pattern = re.compile(re.escape(f".{path.name}.") + r"\d+\.tmp")
    try:
        candidates = [p for p in path.parent.iterdir() if pattern.fullmatch(p.name)]
    except OSError:
        return
    limit = time.time() - TMP_MAX_AGE
    for orphan in candidates:
        try:
            if orphan.stat().st_mtime < limit:
                orphan.unlink()
        except OSError:
            pass


def write_atomic(path, text):
    """Schreibt über eine versteckte Nachbardatei `.<name>.<pid>.tmp` und `os.replace`; wartet nur
    zwischen den Versuchen. Zeilenenden bleiben `\\n` auf jeder Plattform (`newline=""`). Vorher räumt es
    verwaiste Nachbardateien weg (`_remove_orphans`). Scheitern alle Versuche, wirft es den letzten
    OSError weiter; ein Fehler beim Aufräumen der Nachbardatei verdeckt ihn nicht."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _remove_orphans(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8", newline="")
        for attempt in range(WRITE_ATTEMPTS):
            if attempt:
                time.sleep(0.05 * attempt)
            try:
                os.replace(tmp, path)
                return
            except OSError:
                if attempt == WRITE_ATTEMPTS - 1:
                    raise
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


class LockBusy(Exception):
    """Die Sperre war länger als `LOCK_WAIT` Sekunden belegt; `args[0]` ist der Pfad der Sperrdatei."""


def _try_lock(fd):
    """Sperrt `fd` ohne zu warten; wirft OSError, wenn ein anderer die Sperre hält."""
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    else:
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)


def lock_file(path):
    """Die Sperrdatei zu `path`: `<name>.lock` daneben."""
    return path.with_name(path.name + ".lock")


@contextmanager
def log_lock(path):
    """Sperre des Betriebssystems auf der offenen Datei `<log>.lock`; das Betriebssystem gibt sie
    mit dem Schließen frei, spätestens mit dem Ende des Prozesses. Ist sie belegt, neuer Versuch
    alle `LOCK_POLL` Sekunden bis `LOCK_WAIT`, dann `LockBusy`. Die Datei bleibt liegen. Liefert
    None, wenn gesperrt wurde, sonst die Ursache, warum ohne Sperre geschrieben wird (ohne `fcntl`
    und `msvcrt` oder bei `NO_LOCK_ERRNOS`); das melden `add` und `resolve`."""
    lock = lock_file(path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    if fcntl is None and msvcrt is None:
        yield "weder fcntl noch msvcrt verfügbar"
        return
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o644)
    locked, unlocked = False, None
    try:
        deadline = time.monotonic() + LOCK_WAIT
        while True:
            try:
                _try_lock(fd)
                locked = True
                break
            except (BlockingIOError, PermissionError) as error:     # belegt: EAGAIN bzw. EACCES
                if time.monotonic() >= deadline:
                    raise LockBusy(lock) from error
                time.sleep(LOCK_POLL)
            except OSError as error:
                if error.errno not in NO_LOCK_ERRNOS:
                    raise
                unlocked = error.strerror or str(error)
                break
        yield unlocked
    finally:
        if locked and fcntl is None:                    # msvcrt: Bereich vor dem Schließen freigeben
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        os.close(fd)


def append_row(root, session, values, once=False):
    """Hängt eine Zeile an; liest das Protokoll unter der Sperre unmittelbar davor neu.
    (angelegt, Problem, ohne Sperre: None oder Ursache, geschrieben). Mit `once` unterbleibt die
    Zeile, wenn schon eine mit gleicher `klasse`, `entscheidung` und `frage` steht (`gross` mit
    `D-<n>`; die Frage, weil eine verworfene Ablage Nummern wiederverwendet) — geprüft unter der Sperre. Wirft `LockBusy` oder OSError, wenn nicht geschrieben werden kann,
    `Unreadable`, wenn das vorhandene Protokoll nicht lesbar ist."""
    path = log_path(root, session)
    with log_lock(path) as unlocked:
        text = read_log(root, session)
        if text is not None:
            problem = header_problem(text, shown(path, root), "nichts geschrieben")
            if problem:
                return False, problem, unlocked, False
            if once and any(e["klasse"] == values.get("klasse") and e["entscheidung"] == values.get("entscheidung")
                            and e["frage"] == cell(values.get("frage")) for e in parse_rows(text)):
                return False, None, unlocked, False
        row = "| " + " | ".join(cell(values.get(c)) for c in COLUMNS) + " |"
        created = text is None
        body = f"{LOG_HEADER}\n\n{TABLE_HEAD}\n" if created else text.rstrip("\n") + "\n"
        write_atomic(path, body + row + "\n")
    return created, None, unlocked, True


def cache_exists(root):
    """Ob `.skills/cache/` steht — vor dem Schreiben festhalten, für `unversioned_notice`."""
    return (Path(root) / ".skills" / "cache").exists()


def unversioned_notice(root, existed, written):
    """Hinweis, wenn `.skills/cache/` bei diesem Aufruf entstand (`existed`: `cache_exists` vor dem
    Schreiben), der Aufruf etwas geschrieben hat und der Ordner nicht ignoriert ist (Bootstrap,
    Spec 00 §1); sonst None. Gemeinsam für add (klein und groß) und resolve."""
    if existed or not written or not cache_exists(root):
        return None
    try:
        out = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", ".skills/cache/decide/log.md"],
                             capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode == 1:
        return ("Hinweis: .skills/cache/ steht nicht in der .gitignore — dort ist ein unversionierter "
                "Ordner entstanden.")
    return None


# --- Ablage großer Fragen ---------------------------------------------------------------

def ledger_path(root):
    return Path(root) / LEDGER


def ledger_lock_path(root):
    """Pfad, dessen `.lock`-Nachbar die Ablage sperrt — unter `.skills/cache/decide/`, nicht in `docs/`."""
    return Path(root) / LEDGER_LOCK


def line_value(text):
    """Wert für eine Feldzeile der Ablage: Zeilenumbrüche werden Leerzeichen, leer wird `—`."""
    return " ".join(str(text if text is not None else "").split()) or NONE


def read_ledger_text(root):
    """Text der Ablage; None, wenn sie fehlt oder nur Leerraum enthält; `Unreadable` sonst."""
    return _blank_is_missing(read_file(ledger_path(root)))


def ledger_problem(text, tail="Freigaben übersprungen"):
    """Konsumenten-Regel für die Ablage: None, wenn die Kopfzeile passt, sonst der Grund."""
    return header_problem(text, LEDGER_SHOWN, tail)


_FIELD_RE = re.compile(r"^\s*(?P<label>[^:]+?)\s*:(?P<value>.*)$")
_LABELS = {label: name for name, label in FIELDS}


def field_of(line):
    """(Feldname, Wert) für eine Feldzeile der Ablage — auch leer („Antwort:“) oder mit Leerraum
    vor dem `:` —, sonst None."""
    match = _FIELD_RE.match(line)
    if match and match.group("label") in _LABELS:
        return _LABELS[match.group("label")], match.group("value").strip()
    return None


def parse_blocks(text):
    """Blöcke der Ablage, in Dateireihenfolge (siehe `read_ledger`). Ein Block reicht von seiner
    Überschrift bis vor die nächste Zeile mit `## `. Steht ein Feld doppelt, gilt das erste — wie
    für `resolve`."""
    blocks, current, in_options, seen = [], None, False, set()
    for line in text.splitlines():
        if line.startswith("## "):
            match = BLOCK_RE.match(line)
            current = None
            if match:
                current = {"id": match.group("id"), "number": int(match.group("number")),
                           "date": match.group("date"), "status": match.group("status"), "options": []}
                current.update({name: None for name, _ in FIELDS if name != "options"})
                blocks.append(current)
            in_options, seen = False, set()
            continue
        if current is None:
            continue
        field = field_of(line)
        if field:
            name, value = field
            in_options = name == "options" and name not in seen
            if name not in seen and name != "options":
                current[name] = value
            seen.add(name)
            continue
        if in_options and line.startswith("- "):
            current["options"].append(line[2:].strip())
    return blocks


def read_ledger(root):
    """(Blöcke, Problem) aus `docs/big-decisions.md` nach der Konsumenten-Regel.

    Blöcke: Liste von dicts in Dateireihenfolge mit den Schlüsseln `id` (`"D-3"`), `number` (3),
    `date` (`"2026-11-02"`), `status` (`"offen"`, `"freigegeben"`, `"abgelehnt"` oder was von Hand
    dort steht), `question`, `topic`, `key` (`"dependency:pyproject.toml#python-dateutil"`,
    `"rule:UI-Texte"`), `recommendation`, `answer`, `source` (Strings, `—` wie in der Datei, None
    wenn die Zeile fehlt) und `options` (Liste der Optionstexte ohne `- `; leer bei
    „Optionen: — (Auftrag)“). Problem: None, oder eine Zeile Grund — Kopfzeile fehlt, `schema`
    höher als 1 („docs/big-decisions.md schema 1 erwartet, 2 gefunden — Freigaben übersprungen“)
    oder unlesbar; dann sind die Blöcke []. Fehlt die Datei, ist das ([], None).
    """
    return _read_ledger(root)[:2]


def _read_ledger(root):
    """Wie `read_ledger`, dazu als drittes, ob die Datei existiert (aus demselben Lesevorgang)."""
    try:
        text = read_file(ledger_path(root))
    except Unreadable as error:
        return [], unreadable_problem(error, LEDGER_SHOWN, SKIPPED), True
    if _blank_is_missing(text) is None:
        return [], None, text is not None
    problem = ledger_problem(text)
    return ([], problem, True) if problem else (parse_blocks(text), None, True)


def ledger_template():
    """Anfang einer neuen Ablage aus `assets/big-decisions.md`; fehlt die Vorlage oder trägt sie
    nicht die Kopfzeile, nur die Kopfzeile und der Titel."""
    try:
        text = read_file(LEDGER_ASSET)
    except Unreadable:
        text = None
    if text and not header_problem(text, "assets/big-decisions.md") and not BLOCK_NUMBER_RE.search(text):
        return text
    return f"{LOG_HEADER}\n\n# Große Entscheidungen\n"


def render_block(number, day, status, fields):
    """Block `## D-<n> · <datum> · <status>` mit den Feldern aus `FIELDS`; `fields["options"]`
    ist eine Liste oder None (→ „Optionen: — (Auftrag)“)."""
    lines = [f"## D-{number} · {day} · {status}"]
    for name, label in FIELDS:
        if name == "options":
            options = fields.get("options")
            if options is None:
                lines.append(f"{label}: {OPTIONS_BY_REQUEST}")
            else:
                lines.append(f"{label}:")
                lines += [f"- {line_value(option)}" for option in options]
        else:
            lines.append(f"{label}: {line_value(fields.get(name))}")
    return "\n".join(lines)


def _same_question(block, status, fields):
    """Gleiche Frage, gleicher Schlüssel, gleicher Status — offen, oder freigegeben mit gleicher
    Quelle (derselbe Auftrag). Dateiwerte gehen wie die Argumente durch `line_value`."""
    return (block["status"] == status and line_value(block["question"]) == line_value(fields.get("question"))
            and line_value(block["key"]) == line_value(fields.get("key"))
            and (status == "offen" or line_value(block["source"]) == line_value(fields.get("source"))))


def _difference(block, status, fields):
    """Was außer `_same_question` abweicht: None, „anderen Optionen“ oder „anderer Empfehlung“.
    Per Auftrag (nicht offen) zählen Optionen und Empfehlung nicht; beide Seiten durch `line_value`."""
    if status != "offen":
        return None
    if [line_value(o) for o in block["options"]] != [line_value(o) for o in fields.get("options") or []]:
        return "anderen Optionen"
    if line_value(block["recommendation"]) != line_value(fields.get("recommendation")):
        return "anderer Empfehlung"
    return None


def _same_block(block, status, fields):
    """Steht `fields` mit `status` schon als dieser Block? `_same_question`, dazu bei offen gleiche
    Optionen und gleiche Empfehlung (`_difference`)."""
    return _same_question(block, status, fields) and _difference(block, status, fields) is None


def _asked_before(block, fields):
    """Gleiche Frage und gleicher Schlüssel (nach `line_value`), Status egal."""
    return (line_value(block["question"]) == line_value(fields.get("question"))
            and line_value(block["key"]) == line_value(fields.get("key")))


def _answered(block, status, fields):
    """Steht die Frage mit gleichem Schlüssel schon freigegeben da (`_asked_before`)? Eine offene Frage nur
    bei gleichen Optionen und gleicher Empfehlung (`_difference`), ein Auftrag (`status` freigegeben)
    immer; ein Block per Auftrag (Quelle „Auftrag: „…““) beantwortet sie unabhängig von den Optionen.
    Eine Ablehnung beantwortet nichts: danach ist ein add eine neue Frage oder ein neuer Auftrag."""
    return (block["status"] == "freigegeben" and _asked_before(block, fields)
            and (status != "offen" or _REQUEST_SOURCE_RE.match(line_value(block["source"]))
                 or _difference(block, "offen", fields) is None))


def _pair(block):
    """Frage und Schlüssel eines Blocks nach `line_value` — wofür nur der jüngste Block gilt."""
    return line_value(block["question"]), line_value(block["key"])


def _latest(blocks):
    """(gültig, überholt): für Frage plus Schlüssel gilt nur der jüngste Block (Spec 28). `gültig`: die
    Blöcke ohne jüngeren mit gleichem `_pair`, in Dateireihenfolge (zwei mit derselben höchsten Nummer
    bleiben beide); `überholt`: je gültigem Block (`id(block)`) die IDs der älteren, die er überholt."""
    top = {}
    for block in blocks:
        if _pair(block) not in top or block["number"] > top[_pair(block)]["number"]:
            top[_pair(block)] = block
    valid = [block for block in blocks if block["number"] == top[_pair(block)]["number"]]
    older = {}
    for block in blocks:
        if block["number"] < top[_pair(block)]["number"]:
            older.setdefault(id(top[_pair(block)]), []).append(block["id"])
    return valid, older


def append_block(root, status, fields):
    """Hängt einen Block an; liest die Ablage unter ihrer Sperre unmittelbar davor neu.
    (Nummer, angelegt, Problem, ohne Sperre: None oder Ursache, schon da: None oder der Block, früher:
    None oder der letzte beantwortete Block derselben Frage, auf den eine neue offene Frage folgt). Steht
    derselbe Block schon (`_same_block`) oder die Frage schon beantwortet (`_answered`), wird nichts
    geschrieben und „schon da“ ist dieser Block; weichen bei einer offenen Frage nur Optionen oder
    Empfehlung ab (`_same_question`), wird nichts geschrieben und das Problem nennt das Feld. Verglichen
    wird nur mit dem jüngsten Block gleicher Frage und gleichen Schlüssels (`_latest`). Wirft
    `LockBusy`, `Unreadable` oder OSError."""
    path = ledger_path(root)
    earlier = None
    with log_lock(ledger_lock_path(root)) as unlocked:
        text = read_ledger_text(root)
        if text is not None:
            problem = ledger_problem(text, "nichts geschrieben")
            if problem:
                return None, False, problem, unlocked, None, None
            prior = max((b for b in parse_blocks(text) if _asked_before(b, fields)),
                        key=lambda b: b["number"], default=None)
            if prior and (_same_block(prior, status, fields) or _answered(prior, status, fields)):
                return prior["number"], False, None, unlocked, prior, None
            other = prior if prior and _same_question(prior, status, fields) else None
            if other:
                how = " oder mit resolve beantworten" if status == "offen" else ""
                return None, False, (f"{other['id']} steht {status} mit {_difference(other, status, fields)} — "
                                     f"von Hand ändern{how} "
                                     f"({LEDGER_SHOWN}); nichts geschrieben."), unlocked, None, None
            if status == "offen" and prior and prior["status"] in ("freigegeben", "abgelehnt"):
                earlier = prior
        number = max((int(n) for n in BLOCK_NUMBER_RE.findall(text or "")), default=0) + 1
        created = text is None
        base = ledger_template() if created else text
        write_atomic(path, base.rstrip("\n") + "\n\n" + render_block(number, date.today().isoformat(), status, fields) + "\n")
    return number, created, None, unlocked, None, earlier


def _locked_problem(busy, root, what):
    return (f"{what} gesperrt: {shown(busy.args[0], root)} — nach {LOCK_WAIT:g} s aufgegeben "
            "(läuft ein zweites decide_log.py?); nichts geschrieben.")


def store_big(root, session, status, fields, row):
    """Legt einen Block in der Ablage an und die Protokollzeile `gross` mit `D-<n>`; (exit, Zeilen).
    Das Protokoll wird vorher geprüft, damit ein unlesbares nicht erst nach dem Block auffällt.
    Steht der Block schon (ein Wiederholungsaufruf) oder die Frage schon beantwortet („D-<n> ist schon
    <status> (Antwort: …)“, per Auftrag „(Auftrag: „…“)“), wird nur eine fehlende Protokollzeile ergänzt; ob sie fehlt, prüft
    `append_row` unter der Sperre des Protokolls."""
    root = Path(root)
    log_rel = shown(log_path(root, session), root)
    log_name = f"Protokoll {log_rel}"
    try:
        text = read_log(root, session)
    except Unreadable as error:
        return 1, [unreadable_problem(error, log_name)]
    problem = header_problem(text, log_rel, "nichts geschrieben") if text else None
    if problem:
        return 1, [problem]
    existed = cache_exists(root)
    try:
        number, created, problem, unlocked, existing, earlier = append_block(root, status, fields)
    except LockBusy as busy:
        return 1, [_locked_problem(busy, root, "Ablage")]
    except Unreadable as error:
        return 1, [unreadable_problem(error, LEDGER_SHOWN)]
    except OSError as error:
        return 1, [f"{LEDGER_SHOWN} nicht schreibbar ({error.strerror or error}); nichts geschrieben."]
    if problem:
        return 1, [problem]

    did = f"D-{number}"
    lines = ["angelegt: docs/big-decisions.md"] if created else []
    if earlier:
        lines.append(f"{earlier['id']} war {earlier['status']}; neue Frage {did}.")
    pending = (f"Bis zur Freigabe unterbleibt der Schritt; Antwort mit `resolve {did} --answer \"…\"` "
               "oder `--reject`.")
    if existing and not _same_block(existing, status, fields):          # schon beantwortet (`_answered`)
        source = line_value(existing["source"])
        told = source if _REQUEST_SOURCE_RE.match(source) else f"Antwort: {line_value(existing['answer'])}"
        lines.append(f"{did} ist schon {existing['status']} ({told}) in "
                     f"{LEDGER_SHOWN}: {line_value(fields['topic'])} — „{line_value(fields['question'])}“; "
                     "kein neuer Block.")
    elif existing:
        lines.append(f"{did} steht schon {status} in {LEDGER_SHOWN}: {line_value(fields['topic'])} — "
                     f"„{line_value(fields['question'])}“; kein zweiter Block."
                     + (f" {pending}" if status == "offen" else ""))
    elif status == "offen":
        lines.append(f"{did} offen in {LEDGER_SHOWN}: {line_value(fields['topic'])} — "
                     f"„{line_value(fields['question'])}“. {pending}")
    else:
        lines.append(f"{did} {status} in {LEDGER_SHOWN}: {line_value(fields['topic'])} — "
                     f"„{line_value(fields['question'])}“ ({line_value(fields['source'])}).")
    if unlocked and not existing:
        lines.append(f"Hinweis: Ablage ohne Sperre geschrieben ({unlocked}).")
    row = dict(row, entscheidung=did, klasse="gross")
    try:
        log_created, problem, log_unlocked, written = append_row(root, session, row, once=True)
    except LockBusy as busy:
        problem = _locked_problem(busy, root, "Protokoll")
    except Unreadable as error:
        problem = unreadable_problem(error, log_name)
    except OSError as error:
        problem = f"{log_name} nicht schreibbar ({error.strerror or error}); nichts geschrieben."
    if problem:
        notice = unversioned_notice(root, existed, not existing)
        return 1, lines + [f"Protokollzeile für {did} fehlt — {problem} Der Block steht in {LEDGER_SHOWN}."] + (
            [notice] if notice else [])
    if not written:
        lines.append(f"Protokollzeile für {did} steht schon.")
    elif existing:
        lines.append(f"Protokollzeile für {did} ergänzt.")
    if log_unlocked:
        lines.append(f"Hinweis: Protokoll ohne Sperre geschrieben ({log_unlocked}).")
    if log_created:
        lines.append(f"Protokoll angelegt: {log_rel}")
    notice = unversioned_notice(root, existed, written or not existing)
    if notice:
        lines.append(notice)
    return 0, lines


def parse_key(key):
    """((Kategorie, Muster, Text), None) eines Schlüssels `<kategorie>:<pfadmuster>[#<text>]`, oder
    (None, Grund), wenn er die Form nicht hat — die eine Prüfung der Form für `add` (`check_key`) und
    check. `#<text>` gilt nur für hinzugefügte Zeilen; ein Text, der mit `-` oder `+` beginnt, ist ein
    Fehler (Zyklus 2 streicht `#-<text>` und `#+<text>`: nur entfernte Zeilen gibt nur ein Schlüssel
    ohne Text frei). Leerraum um Kategorie, Pfadmuster und Text fällt weg, Leerraum im Text wird
    zusammengezogen; Leerzeichen im Pfadmuster bleiben, Tab und Zeilenumbruch darin sind ein Fehler,
    ebenso ein `#` ohne Text (der gäbe sonst die ganze Datei frei). Das Pfadmuster ist relativ zur
    Repo-Wurzel wie die Pfade im Diff: ein führendes `./` fällt weg; ein absoluter Pfad oder ein Teil
    `..` träfe nie eine Datei und ist ein Fehler („Pfadmuster muss relativ zur Repo-Wurzel sein“). Bei
    `rule:<thema>` ist alles nach `rule:` das Thema (auch mit `#`, etwa `rule:C#`), der Text leer."""
    category, sep, rest = (key or "").strip().partition(":")
    category = category.strip()
    if category == RULE_CATEGORY and sep and rest.strip():
        return (category, rest.strip(), ""), None
    pattern, hash_, text = rest.partition("#")
    pattern = pattern.strip()
    while pattern.startswith("./"):
        pattern = pattern[2:].lstrip("/")
    if not sep or not category or not pattern:
        return None, f"hat nicht die Form {KEY_FORM}"
    if re.search(r"[^\S ]", pattern):
        return None, f"hat Tab oder Zeilenumbruch im Pfadmuster „{line_value(pattern)}“"
    if re.match(r"[/\\]|[A-Za-z]:[/\\]", pattern) or ".." in re.split(r"[/\\]", pattern):
        return None, "hat ein Pfadmuster außerhalb der Repo-Wurzel — Pfadmuster muss relativ zur Repo-Wurzel sein"
    text = " ".join(text.split())
    if hash_ and not text:
        return None, "hat leeren Text nach #"
    if text[:1] in ("-", "+"):
        return None, (f"hat „#{text[:1]}“ — #<text> gilt nur für hinzugefügte Zeilen; nur entfernte Zeilen gibt "
                      "nur ein Schlüssel ohne Text frei")
    return (category, pattern, text), None


def check_key(key, topic, rules):
    """(Schlüssel, Problem): die Form aus `parse_key`, danach nur, was darüber hinausgeht — die
    Kategorie aus der Tabelle in `references/reversibility.md` (`load_categories`, dieselbe Quelle
    wie check), oder — mit und ohne Auftrag — `rule:<thema>`, wenn eine Regel `immer fragen` dieses
    Thema und `topic` trifft, dann in der Schreibweise der Regel."""
    shown_key = line_value(key)
    parts, why_not = parse_key(key)
    if parts is None:
        return None, f"Schlüssel „{shown_key}“ {why_not}; nichts geschrieben."
    category, pattern, text = parts
    if category == RULE_CATEGORY:
        hits = [r for r in match_rules(rules, pattern)[0] if r.kind == "immer fragen"]
        if not hits:
            return None, (f"Schlüssel „{shown_key}“: keine Regel „immer fragen: {pattern}“ — rule:<thema> nur, "
                          "wenn eine Regel immer fragen das Thema trifft; nichts geschrieben.")
        if _norm(hits[0].topic) != _norm(topic):
            return None, (f"Schlüssel „{shown_key}“ passt nicht zum Thema „{line_value(topic)}“ — "
                          f"rule:<thema> nimmt das Thema der Frage; nichts geschrieben.")
        return f"{RULE_CATEGORY}:{hits[0].topic}", None
    categories, problem = load_categories(REFERENCE)
    if problem:
        return None, f"Schlüssel „{shown_key}“ nicht prüfbar: {problem}; nichts geschrieben."
    if category not in categories:
        return None, (f"Schlüssel „{shown_key}“: Kategorie „{category}“ unbekannt — erlaubt: "
                      f"{', '.join(categories)}, oder rule:<thema> bei einer Regel immer fragen; "
                      "nichts geschrieben.")
    return f"{category}:{pattern}{'#' + text if text else ''}", None


def _options(args):
    return [o for o in (getattr(args, "options", None) or []) if (o or "").strip()]


def rule_hits(rules, topic):
    """(immer, nie, Hinweise) für `topic`: treffende Regeln je Art und die Hinweiszeilen — je
    ähnliche Regel eine, dazu der Widerspruch, wenn beide Arten treffen."""
    hits, hints = match_rules(rules, topic)
    always = [r for r in hits if r.kind == "immer fragen"]
    never = [r for r in hits if r.kind == "nie fragen"]
    notes = [f"Hinweis: Regel „{rule_label(r)}“ ({r.source}) ähnelt dem Thema „{topic.strip()}“ — "
             "nicht angewendet; trifft sie, das Thema wörtlich aus `rules` übernehmen." for r in hints]
    if always and never:
        notes.append(contradiction(always, never))
    return always, never, notes


def add_big(root, session, args):
    """Große Frage in die Ablage und ins Protokoll; (exit, meldung).

    `args`: argparse-Namespace oder Objekt mit `topic`, `question`, `key`, `recommendation`,
    `approved_by_request` (Strings oder None), `options` (Liste der `--option`-Werte oder None)
    und optional `home` (Path; Default `HOME`). Ohne `approved_by_request`: Status `offen`,
    zwei bis vier Optionen und `recommendation` Pflicht. Mit: Status `freigegeben`, Quelle
    `Auftrag: „<Zitat>“`, „Optionen: — (Auftrag)“; `options` wird ignoriert. Trifft eine Regel das
    Thema, gilt ihre Schreibweise; `nie fragen` stuft nicht herab, die Meldung sagt das.
    """
    root = Path(root)
    home = Path(getattr(args, "home", None) or home_dir())
    approved = line_value(getattr(args, "approved_by_request", None))
    approved = "" if approved == NONE else approved
    needed = ("topic", "question", "key") + (() if approved else ("recommendation",))
    missing = [f"--{name}" for name in needed if not (getattr(args, name, None) or "").strip()]
    if missing:
        return 1, f"add --class gross: es fehlt {', '.join(missing)}; nichts geschrieben."
    options = _options(args)
    if not approved and not 2 <= len(options) <= 4:
        return 1, (f"add --class gross: zwei bis vier --option nötig, {len(options)} angegeben; "
                   "nichts geschrieben.")

    rules, _, problems = read_rules(root, home)
    always, never, notes = rule_hits(rules, args.topic)
    notes = problems + notes
    topic = (always + never)[0].topic if always or never else args.topic.strip()
    key, problem = check_key(args.key, topic, rules)
    if problem:
        return 1, problem

    if never and not always:
        notes.append(f"Regel {rule_ref(never[0])} wirkt nicht auf große Entscheidungen — die Frage bleibt groß"
                     + (" und offen." if not approved else "."))
    if approved and options:
        notes.append("Hinweis: --option bei --approved-by-request ignoriert — der Auftrag hat die Wahl getroffen.")
    fields = {"question": args.question, "topic": topic, "key": key,
              "options": None if approved else options,
              "recommendation": getattr(args, "recommendation", None),
              "answer": ANSWER_BY_REQUEST if approved else NONE,
              "source": f"Auftrag: „{approved}“" if approved else NONE}
    regel = (rule_label(always[0]) if always
             else f"{rule_label(never[0])} (wirkt nicht auf groß)" if never else NONE)
    row = {"zeit": datetime.now().isoformat(timespec="seconds"), "thema": topic, "frage": args.question,
           "beleg": fields["source"], "regel": regel}
    code, lines = store_big(root, session, "freigegeben" if approved else "offen", fields, row)
    return code, "\n".join(notes + lines)


# --- resolve und open -------------------------------------------------------------------

def resolve(root, decision_id, answer, reject):
    """Antwort auf `D-<n>` eintragen; (exit, meldung). `answer` (String oder None) wird die
    Antwort, `reject` setzt `abgelehnt` (sonst `freigegeben`); Quelle wird „Nutzer in Sitzung“.
    Der Block bleibt stehen, nur Status, Antwort und Quelle ändern sich. Ohne Antwort und ohne
    `reject`, bei unbekannter oder doppelter ID, bei einem Block, der nicht offen ist, oder nach
    der Konsumenten-Regel Exit 1."""
    root = Path(root)
    match = re.fullmatch(r"[dD]-(\d+)", (decision_id or "").strip())
    if not match:
        return 1, f"resolve: „{decision_id}“ ist keine ID der Form D-<n>; nichts geschrieben."
    number = int(match.group(1))
    did = f"D-{number}"
    answer = line_value(answer)
    if answer == NONE and not reject:
        return 1, f"resolve {did}: --answer \"…\" oder --reject nötig; nichts geschrieben."
    status = "abgelehnt" if reject else "freigegeben"
    if answer == NONE:
        answer = "abgelehnt"
    existed = cache_exists(root)
    code, message = _resolve(root, did, number, answer, status, ledger_lock_path(root))
    notice = unversioned_notice(root, existed, code == 0)        # wie add (Spec 00 §1)
    return code, message + (f"\n{notice}" if notice else "")


def _resolve(root, did, number, answer, status, lock):
    """Der Teil von `resolve` unter der Sperre der Ablage; (exit, meldung)."""
    try:
        with log_lock(lock) as unlocked:
            text = read_ledger_text(root)
            if text is None:
                return 1, f"resolve {did}: {LEDGER_SHOWN} fehlt; nichts geschrieben."
            problem = ledger_problem(text, "nichts geschrieben")
            if problem:
                return 1, problem
            lines = text.split("\n")
            starts = [i for i, line in enumerate(lines)
                      if (m := BLOCK_RE.match(line)) and int(m.group("number")) == number]
            if len(starts) != 1:
                why = "steht mehrfach" if starts else "fehlt"
                return 1, f"resolve {did}: Block {did} {why} in {LEDGER_SHOWN}; nichts geschrieben."
            start = starts[0]
            end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
            head = BLOCK_RE.match(lines[start])
            before = head.group("status")
            if before != "offen":
                source = next((f[1] for f in map(field_of, lines[start + 1:end]) if f and f[0] == "source"), None)
                return 1, (f"resolve {did}: Block steht auf „{before}“ (Quelle der Antwort: {source or NONE}) — "
                           "resolve ändert nur offene Blöcke, von Hand bleibt es möglich; nichts geschrieben.")
            lines[start] = f"## {did} · {head.group('date')} · {status}"
            for name, label, value in (("answer", "Antwort", answer), ("source", "Quelle der Antwort", SOURCE_USER)):
                found = next((i for i in range(start + 1, end) if (field_of(lines[i]) or ("",))[0] == name), None)
                if found is None:
                    found = end
                    while found - 1 > start and not lines[found - 1].strip():
                        found -= 1
                    lines.insert(found, "")
                    end += 1
                lines[found] = f"{label}: {value}"
            write_atomic(ledger_path(root), "\n".join(lines))
    except LockBusy as busy:
        return 1, _locked_problem(busy, root, "Ablage")
    except Unreadable as error:
        return 1, unreadable_problem(error, LEDGER_SHOWN)
    except OSError as error:
        return 1, f"{LEDGER_SHOWN} nicht schreibbar ({error.strerror or error}); nichts geschrieben."
    message = (f"{did}: {before} → {status}; Antwort: {answer}; Quelle der Antwort: {SOURCE_USER} "
               f"({LEDGER_SHOWN}).")
    if unlocked:
        message += f"\nHinweis: Ablage ohne Sperre geschrieben ({unlocked})."
    return 0, message


def open_questions(root):
    """(exit, text): die Blöcke mit Status `offen` mit Datum, Thema, Frage, Schlüssel, Optionen
    und Empfehlung. Exit 1 nur, wenn die Konsumenten-Regel die Ablage überspringt."""
    return _open_questions(*_read_ledger(Path(root)))


def _open_questions(blocks, problem, exists):
    """`open_questions` aus einem schon gelesenen `_read_ledger` (check liest die Ablage nur einmal)."""
    if problem:
        return 1, problem
    if not exists:
        return 0, f"Keine offenen großen Fragen ({LEDGER_SHOWN} fehlt)."
    pending = [b for b in blocks if b["status"] == "offen"]
    if not pending:
        return 0, f"Keine offenen großen Fragen in {LEDGER_SHOWN}."
    lines = [f"Offene große Fragen in {LEDGER_SHOWN}: {len(pending)}"]
    for b in pending:
        lines.append(f"{b['id']} · {b['date']} · {b['topic'] or NONE}: {b['question'] or NONE}")
        lines.append(f"  Schlüssel: {b['key'] or NONE}")
        lines += [f"  - {option}" for option in b["options"]]
        lines.append(f"  Empfehlung: {b['recommendation'] or NONE}")
    return 0, "\n".join(lines)


# --- check: Kategorien, Pfadmuster, Diff ------------------------------------------------

def reference_shown(path):
    """`references/<name>` für eine Datei in einem Ordner `references`, sonst der Pfad."""
    path = Path(path)
    return f"{path.parent.name}/{path.name}" if path.parent.name == "references" else str(path)


def _table_cells(line):
    """Zellen einer Markdown-Tabellenzeile, getrimmt; None, wenn die Zeile keine ist."""
    line = line.strip()
    if not line.startswith("|"):
        return None
    inner = line[1:-1] if len(line) > 1 and line.endswith("|") else line[1:]
    return [c.strip() for c in inner.split("|")]


def _patterns(text):
    """(Muster, Problem) aus einer Zelle Pfadmuster: Muster in Backticks, durch Komma getrennt;
    `—`, `-` oder leer heißt keines."""
    if text in ("", "—", "-"):
        return (), None
    found = tuple(p.strip() for p in re.findall(r"`([^`]+)`", text))
    if not found or re.sub(r"`[^`]+`", "", text).strip(" ,") or not all(found):
        return (), f"Pfadmuster „{text}“ — erwartet Muster in Backticks, durch Komma getrennt, oder —"
    return found, None


def load_categories(path):
    """(Kategorien, Problem) aus der Tabelle in `references/reversibility.md` (`path`), bei jedem
    Aufruf neu gelesen.

    Kategorien: dict Name → `Category`, in Tabellenreihenfolge. Die Tabelle beginnt mit der
    Kopfzeile `| Kategorie | Bedeutung | Beispiel | Grad | Pfadmuster | Grenze |` und der
    Trennzeile und reicht bis zur ersten Zeile, die nicht mit `|` beginnt. Je Zeile: Kategorie als
    Name in Backticks (einmal, nicht `rule`), Grad aus `GRADES`, Pfadmuster nach `_patterns` —
    `geprüft` und `teilweise` mit mindestens einem, `ungeprüft` mit keinem —, Bedeutung nicht leer.
    Problem: None, oder eine Zeile Grund („references/reversibility.md fehlt“, nicht lesbar,
    keine Tabelle, Zeile <n>: …); dann sind die Kategorien {}."""
    where = reference_shown(path)
    try:
        text = read_file(path)
    except Unreadable as error:
        return {}, unreadable_problem(error, where, "")
    if text is None:
        return {}, f"{where} fehlt"
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if _table_cells(line) == list(REFERENCE_COLUMNS)), None)
    if start is None:
        return {}, f"{where}: keine Tabelle mit der Kopfzeile | {' | '.join(REFERENCE_COLUMNS)} |"
    rule = _table_cells(lines[start + 1]) if start + 1 < len(lines) else None
    if not rule or not all(re.fullmatch(r":?-{3,}:?", c) for c in rule):
        return {}, f"{where}:{start + 2}: Trennzeile | --- | … fehlt unter der Kopfzeile"
    categories = {}
    for number, line in enumerate(lines[start + 2:], start + 3):
        cells = _table_cells(line)
        if cells is None:
            break
        if len(cells) != len(REFERENCE_COLUMNS):
            return {}, f"{where}:{number}: {len(cells)} Zellen, erwartet {len(REFERENCE_COLUMNS)}"
        row = dict(zip(REFERENCE_COLUMNS, cells))
        match = re.fullmatch(r"`([a-z][a-z0-9-]*)`", row["Kategorie"])
        if not match:
            return {}, f"{where}:{number}: Kategorie „{row['Kategorie']}“ ist kein Name in Backticks"
        name = match.group(1)
        if name == RULE_CATEGORY:
            return {}, f"{where}:{number}: `{RULE_CATEGORY}` ist reserviert und hat keine Pfadmuster"
        if name in categories:
            return {}, f"{where}:{number}: Kategorie `{name}` steht doppelt"
        grade = row["Grad"]
        if grade not in GRADES:
            return {}, f"{where}:{number}: Grad „{grade}“ für `{name}` unbekannt — erlaubt: {', '.join(GRADES)}"
        patterns, problem = _patterns(row["Pfadmuster"])
        if problem:
            return {}, f"{where}:{number}: {problem}"
        if grade == "ungeprüft" and patterns:
            return {}, f"{where}:{number}: `{name}` ist ungeprüft und hat trotzdem Pfadmuster"
        if grade != "ungeprüft" and not patterns:
            return {}, f"{where}:{number}: `{name}` ist {grade} und braucht mindestens ein Pfadmuster"
        if row["Bedeutung"] in ("", "—", "-"):
            return {}, f"{where}:{number}: Bedeutung für `{name}` leer"
        categories[name] = Category(name, row["Bedeutung"], row["Beispiel"], grade, patterns, row["Grenze"] or NONE)
    if not categories:
        return {}, f"{where}: Tabelle ohne Zeilen"
    return categories, None


def tail_line(categories):
    """Die Schlusszeile von check: „ungeprüft: …; teilweise: …“ in Tabellenreihenfolge."""
    parts = []
    for grade in TAIL_GRADES:
        names = [c.name for c in categories.values() if c.grade == grade]
        if names:
            parts.append(f"{grade}: {', '.join(names)}")
    return "; ".join(parts) or "ungeprüft: —"


@functools.lru_cache(maxsize=None)
def glob_to_regex(pattern):
    """Regex (kompiliert, für `fullmatch` auf einen Pfad relativ zur Wurzel mit `/`) zu einem
    Pfadmuster: endet es auf `/`, ist es ein Präfix (jede Datei darunter); `**/` null oder mehr
    Ordner, `**` sonst beliebige Zeichen samt `/`, `*` beliebige Zeichen außer `/`, `?` ein
    Zeichen außer `/`, alles andere wörtlich. Ein Präfix, das auf `/**/` endet, ist dasselbe wie
    eines ohne (`x/**/` trifft `x/datei` und tiefer), `**/` allein trifft jede Datei. Selbst
    übersetzt statt `fnmatch` (dort trifft `*` auch `/`) oder `PurePath.full_match` (erst ab
    Python 3.13). Je Muster einmal übersetzt (`lru_cache`)."""
    prefix = pattern.endswith("/")
    body = pattern[:-1] if prefix else pattern
    rest = "/.+"
    if prefix:
        while body.endswith("/**"):                     # `**/` am Ende: null oder mehr Ordner
            body = body[:-3]
        if body == "**":
            body, rest = "", ".+"
    out, i = [], 0
    while i < len(body):
        if body.startswith("**/", i):
            out.append("(?:[^/]+/)*")
            i += 3
        elif body.startswith("**", i):
            out.append(".*")
            i += 2
        elif body[i] == "*":
            out.append("[^/]*")
            i += 1
        elif body[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(body[i]))
            i += 1
    if prefix:
        out.append(rest)
    return re.compile("".join(out))


def pattern_matches(pattern, path):
    return glob_to_regex(pattern).fullmatch(path) is not None


class NoGit(Exception):
    """`git` fehlt oder lässt sich nicht starten."""


class GitTimeout(Exception):
    """`git` antwortet nicht in `GIT_TIMEOUT` Sekunden."""


def timeout_problem():
    return f"git antwortet nicht in {GIT_TIMEOUT} s"


def _git(cwd, *args, raw=False):
    """Git mit Argumentliste in `cwd`, nie über eine Shell; `GitTimeout` nach `GIT_TIMEOUT`
    Sekunden, `NoGit`, wenn es nicht startet. `raw`: stdout als Bytes (`changed_lines`
    dekodiert die Zeilen selbst streng als UTF-8), stderr als Text."""
    command = ["git", "-C", str(cwd), "--literal-pathspecs", *args]
    try:
        if not raw:
            return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  stdin=subprocess.DEVNULL, timeout=GIT_TIMEOUT)
        result = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL, timeout=GIT_TIMEOUT)
    except subprocess.TimeoutExpired as error:
        raise GitTimeout(str(error)) from error
    except (OSError, subprocess.SubprocessError) as error:
        raise NoGit(str(error)) from error
    result.stderr = result.stderr.decode("utf-8", errors="replace")
    return result


def _git_error(result):
    return next((line.strip() for line in result.stderr.splitlines() if line.strip()), f"Exit {result.returncode}")


class Changes(list):
    """Die Stellen seit einer Revision: sortierte Pfade relativ zur Repo-Wurzel mit `/`. Dazu `top`
    (Wurzel des Repos), `untracked` (die unversionierten unter ihnen) und `commit` (der aufgelöste
    Commit, gegen den `git diff` den Arbeitsbaum vergleicht)."""

    def __init__(self, files=(), top=None, untracked=(), commit=None):
        super().__init__(files)
        self.top, self.untracked, self.commit = top, set(untracked), commit


_RANGE_RE = re.compile(r"^\^|\.\.|\^[!@-]")      # Bereichsschreibweisen; check nimmt eine Revision
UNREADABLE = "unlesbar — selbst prüfen"


def one_revision_problem(rev):
    """Der Grund für alles, was keine einzelne Revision ist („ungeprüft — …“ setzt check davor)."""
    return f"check nimmt eine Revision, nicht „{' '.join(rev.split())}“; den Bereich selbst prüfen"


def _work_tree(top):
    """(Wurzel, Problem): `git rev-parse --is-bare-repository --is-inside-work-tree --git-dir` in einem
    Aufruf — scheitert er, ist es kein Repo („kein Git“). Nur in einem Arbeitsbaum folgt
    `git rev-parse --show-toplevel` in einem eigenen Aufruf, die Wurzel ist dann dessen Ausgabe; im
    Bare-Repo oder in `.git` ist sie None (kein Arbeitsbaum)."""
    probe = _git(top, "rev-parse", "--is-bare-repository", "--is-inside-work-tree", "--git-dir")
    flags = probe.stdout.split("\n")
    if probe.returncode != 0 or len(flags) < 3:
        return None, "kein Git"
    if flags[0].strip() == "true" or flags[1].strip() != "true":
        return None, None
    shown = _git(top, "rev-parse", "--show-toplevel")
    path = shown.stdout.rstrip("\n")
    if shown.returncode != 0 or not path:
        return None, f"git rev-parse --show-toplevel fehlgeschlagen: {_git_error(shown)}"
    return Path(path), None


def changed_files(root, rev):
    """(Dateien, Problem): die Stellen seit `rev` als `Changes` — eine Liste der Pfade relativ zur
    Repo-Wurzel mit `/`, sortiert, dazu `top`, `untracked` und `commit`. Die eine Quelle für check.
    `root` ist die Repo-Wurzel, wie `main` sie mit `repo_root` bestimmt hat; `top` ist die Wurzel, die
    Git in einem eigenen `rev-parse --show-toplevel` nennt (`_work_tree`) — fiel `repo_root` auf ein
    Unterverzeichnis zurück, liest check trotzdem an der Wurzel. `top` steht auch bei einem Problem,
    sobald Git die Wurzel genannt hat — check liest die Übergabe dort.
    `rev` ist genau eine Revision: Eine Angabe mit `..`, `^!`, `^@` oder `^-`, eine leere, eine mit
    Leerraum, führendem `-` oder führendem `^` ist keine (`one_revision_problem`); Git bekommt sie nie.
    Eine, die `git rev-parse --verify <rev>^{commit}` nicht auflöst, ist „Revision „<rev>“ nicht
    gefunden (<erste Zeile der git-Meldung>)“. Dann `git diff <commit>` (Commits seit `<rev>` und
    Arbeitsbaum, mit dem aufgelösten Commit, nie der rohen Angabe) plus
    `git ls-files --others --exclude-standard`.
    Problem: None, „kein Git“ (kein `git` oder kein Repo), „kein Arbeitsbaum“ (Bare-Repo, `.git`),
    „git antwortet nicht in <n> s“, keine einzelne Revision, eine nicht gefundene oder der Grund, mit
    dem Git abbricht; dann sind die Dateien leer."""
    rev = (rev or "").strip()
    single = bool(rev) and not rev.startswith("-") and not re.search(r"\s", rev) and not _RANGE_RE.search(rev)
    try:
        top, problem = _work_tree(Path(root))
        if not single:
            return Changes(top=top), one_revision_problem(rev)
        if problem:
            return Changes(), problem
        if top is None:
            return Changes(), "kein Arbeitsbaum"
        resolved = _git(top, "rev-parse", "--verify", f"{rev}^{{commit}}")
        commit = resolved.stdout.strip()
        if resolved.returncode != 0 or not commit:
            return Changes(top=top), f"Revision „{rev}“ nicht gefunden ({_git_error(resolved)})"
        diff = _git(top, "diff", "--name-only", "-z", "--no-renames", "--no-ext-diff", commit, "--")
        if diff.returncode != 0:
            return Changes(top=top), f"git diff {rev} fehlgeschlagen: {_git_error(diff)}"
        files = {name for name in diff.stdout.split("\0") if name}
        others = _git(top, "ls-files", "--others", "--exclude-standard", "--full-name", "-z")
        if others.returncode != 0:
            return Changes(top=top), f"git ls-files --others fehlgeschlagen: {_git_error(others)}"
        untracked = {name for name in others.stdout.split("\0") if name} - files
    except GitTimeout:
        return Changes(), timeout_problem() if single else one_revision_problem(rev)
    except NoGit:
        return Changes(), "kein Git" if single else one_revision_problem(rev)
    return Changes(sorted(files | untracked), top, untracked, commit), None


_C_QUOTE = {"\a": "a", "\b": "b", "\t": "t", "\n": "n", "\v": "v", "\f": "f", "\r": "r", '"': '"', "\\": "\\"}


def _git_quoted(name):
    """`name`, wie Git ihn mit `core.quotePath=false` im Kopf `diff --git` schreibt: mit Steuerzeichen,
    `"` oder `\\` in Anführungszeichen mit C-Escapes (sonst Oktal), sonst wörtlich."""
    if not any(c in _C_QUOTE or c < " " or c == "\x7f" for c in name):
        return name
    return '"' + "".join("\\" + _C_QUOTE[c] if c in _C_QUOTE else f"\\{ord(c):03o}" if c < " " or c == "\x7f"
                         else c for c in name) + '"'


DIFF_CHUNK = 200
UNTRACKED_LIMIT = 1 << 20                           # Bytes, die check aus einer unversionierten Datei liest


def _read_untracked(path):
    """Bytes der unversionierten Datei `path`; None — unlesbar — für einen Symlink (Git sieht nur den
    Linktext), alles außer einer regulären Datei, mehr als `UNTRACKED_LIMIT` Bytes oder einen Lesefehler.
    Das Seltene geht so als Stelle an den Nutzer, statt einem Link nach `/dev/zero` zu folgen."""
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > UNTRACKED_LIMIT:
            return None
        handle = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
        try:
            file = os.fdopen(handle, "rb")
        except BaseException:
            os.close(handle)                            # fdopen hat den Deskriptor nicht übernommen
            raise
        with file:
            data = file.read(UNTRACKED_LIMIT + 1)
    except OSError:
        return None
    return None if len(data) > UNTRACKED_LIMIT else data


class DiffFailed(Exception):
    """`git diff` für die Zeilen der `#<text>`-Freigaben lieferte keinen Diff; die Ursache als Text."""


def _utf8_lines(chunks):
    """Die Zeilen (Bytes) streng als UTF-8 dekodiert; None bei ungültigem UTF-8."""
    try:
        return [chunk.decode("utf-8") for chunk in chunks]
    except UnicodeDecodeError:
        return None


def changed_lines(top, commit, paths, untracked):
    """{Pfad: hinzugefügte Zeilen, Leerraum zusammengezogen — oder None: unlesbar} jeder Datei aus
    `paths` seit `commit` (aus `changed_files`) — für `#<text>`. Eine unversionierte Datei ist ganz
    hinzugefügt. Die anderen kommen aus `git diff -U0 <commit>`, je höchstens `DIFF_CHUNK` Pfade ein
    Aufruf, aufgeteilt an den Köpfen `diff --git a/<p> b/<p>`, die das Skript je Pfad selbst so bildet,
    wie Git sie schreibt (`_git_quoted`). Unlesbar ist eine Datei, die sich nicht lesen lässt (eine
    unversionierte auch als Symlink oder über `UNTRACKED_LIMIT` Bytes, `_read_untracked`), deren
    Zeilen kein gültiges UTF-8 sind, deren Diff binär ist oder für die Git keinen Block liefert — eine
    Stelle „unlesbar — selbst prüfen“ statt eines eigenen Falls je Ursache. Scheitert `git diff`,
    `DiffFailed`; antwortet es nicht in `GIT_TIMEOUT` Sekunden, `GitTimeout` (check endet dann mit 2)."""
    found = {}
    for path in paths:
        if path in untracked:
            data = _read_untracked(Path(top, path))
            found[path] = None if data is None else _utf8_lines(data.removeprefix(b"\xef\xbb\xbf").splitlines())
    tracked = [path for path in paths if path not in untracked]
    for start in range(0, len(tracked), DIFF_CHUNK):
        chunk = tracked[start:start + DIFF_CHUNK]
        heads = {f"diff --git {_git_quoted('a/' + p)} {_git_quoted('b/' + p)}": p for p in chunk}
        try:
            result = _git(top, "-c", "core.quotePath=false", "diff", "--no-color", "--no-ext-diff", "--no-textconv",
                          "--no-renames", "--src-prefix=a/", "--dst-prefix=b/", "-U0", commit, "--", *chunk,
                          raw=True)
        except NoGit as error:
            raise DiffFailed(str(error)) from error
        if result.returncode != 0:
            raise DiffFailed(_git_error(result))
        added, current, in_hunk = {}, None, False
        for line in result.stdout.split(b"\n"):
            if line.startswith(b"diff --git "):
                current, in_hunk = heads.get(line.decode("utf-8", errors="replace")), False
                if current:
                    added[current] = []
            elif current is None or added[current] is None:
                continue
            elif line.startswith(b"@@"):
                in_hunk = True
            elif not in_hunk and line.startswith(b"Binary files "):
                added[current] = None
            elif in_hunk and line.startswith(b"+"):
                added[current].append(line[1:])
        for path in chunk:
            found[path] = None if added.get(path) is None else _utf8_lines(added[path])
    return {path: None if lines is None else [" ".join(line.split()) for line in lines]
            for path, lines in found.items()}


def _handover(root, session, home, ledger):
    """Die Abschnitte, die check vor der Schlusszeile anhängt — auf jedem Weg, auch mit Exit 2: die
    Einträge der Sitzung wie `summary` (nur mit gültiger Sitzung und mit Einträgen oder einem Grund,
    warum das Protokoll nicht gelesen wurde; ohne Sitzung entfällt der Teil still) und die offenen
    großen Fragen wie `open` (nur wenn es welche gibt). `ledger` ist das schon gelesene `_read_ledger`
    — check liest Ablage und Protokoll je einmal."""
    lines = []
    if session and valid_session(session):
        entries, problem = log_entries(root, session)
        if entries or problem:
            lines += _summary(root, session, home, entries, problem)[1].splitlines()
    if any(block["status"] == "offen" for block in ledger[0]):
        lines += _open_questions(*ledger)[1].splitlines()
    return lines


def check(root, rev, session, home):
    """Teure Änderungen seit der Revision `rev` (Commits und Arbeitsbaum) ohne freigegebenen Eintrag in
    `docs/big-decisions.md` (Arbeitskopie); (exit, text). Die Stellen kommen aus `changed_files`. Nach
    den Stellen die Übergabe (`_handover`: Einträge der Sitzung `session`, wenn es sie gibt, und offene
    große Fragen), dann die Schlusszeile `tail_line` („ungeprüft: data-delete, …; teilweise: api,
    migration, dependency, permissions“) — sie ist immer die letzte Zeile, außer ohne Reference.
    Exit 1 bei mindestens einer Stelle, sonst 0; Exit 2 bei fehlender oder kaputter Reference
    („ungeprüft — references/reversibility.md fehlt“), ohne Git („ungeprüft — kein Git“), ohne
    Arbeitsbaum („ungeprüft — kein Arbeitsbaum“), bei allem, was keine einzelne Revision ist
    („ungeprüft — check nimmt eine Revision, nicht „<angabe>“; den Bereich selbst prüfen“), bei einer
    Revision, die Git nicht auflöst („ungeprüft — Revision „<rev>“ nicht gefunden (<git-Meldung>)“) und
    wenn Git nicht in `GIT_TIMEOUT` Sekunden antwortet („ungeprüft — git antwortet nicht in <n> s“).
    Die Wurzel bestimmt `changed_files` einmal; Prüfung und Übergabe lesen dort auf jedem Weg, die
    Ablage einmal."""
    root = Path(root)
    changes, problem = changed_files(root, rev)
    top = changes.top or root
    ledger = _read_ledger(top)
    categories, missing = load_categories(REFERENCE)
    if missing:
        return 2, "\n".join([f"ungeprüft — {missing}"] + _handover(top, session, home, ledger))
    code, body = 2, [f"ungeprüft — {problem}"]
    if not problem:
        try:
            code, body = _check(changes, rev.strip(), categories, ledger)
        except GitTimeout:
            body = [f"ungeprüft — {timeout_problem()}"]
        except DiffFailed as error:
            body = [f"ungeprüft — git diff für #<text>-Freigaben gescheitert ({error})"]
        except NoGit:
            body = ["ungeprüft — kein Git"]
    return code, "\n".join(body + _handover(top, session, home, ledger) + [tail_line(categories)])


def _check(changes, rev, categories, ledger):
    """Der Vergleich zu `check`, nachdem die Stellen feststehen; (exit, Zeilen) ohne Übergabe und
    Schlusszeile. `ledger` ist `_read_ledger` an der Wurzel. Wirft `GitTimeout`, `DiffFailed` und `NoGit`."""
    top = changes.top
    blocks, ledger_note, exists = ledger
    notes = [ledger_note] if ledger_note else []
    unread = None                                       # Grund, warum keine Freigabe gelesen wurde
    if ledger_note:
        unread = ledger_note[:-len(SKIPPED)] if ledger_note.endswith(SKIPPED) else ledger_note
    elif not exists:
        unread = f"{LEDGER_SHOWN} fehlt"
    valid, older = _latest(blocks)                      # je Frage und Schlüssel gilt nur der jüngste Block
    entries = []
    for block in valid:
        parsed, why_not = parse_key(block["key"])
        if parsed is None:
            if block["status"] == "freigegeben":
                notes.append(f"Hinweis: {block['id']} Schlüssel „{block['key'] or NONE}“ {why_not} — "
                             "gibt nichts frei.")
            continue
        if parsed[0] == RULE_CATEGORY:
            continue                                    # rule:<thema> vergleicht check nie
        if parsed[0] not in categories:
            if block["status"] == "freigegeben":
                notes.append(f"Hinweis: {block['id']} Kategorie „{parsed[0]}“ steht nicht in "
                             f"{reference_shown(REFERENCE)} — gibt nichts frei.")
            continue
        entries.append((block, *parsed))

    # je Pfad die Kategorien, die er trifft, mit den Einträgen dieser Kategorie, deren Muster ihn trifft
    candidates = {path: [(c, [e for e in entries if e[1] == c.name and pattern_matches(e[2], path)])
                         for c in categories.values() if any(pattern_matches(p, path) for p in c.patterns)]
                  for path in changes}
    def needs_lines(matching):                          # ein Eintrag ohne Text gibt frei ohne Diff
        free = [e for e in matching if e[0]["status"] == "freigegeben"]
        return bool(free) and all(text for *_, text in free)

    wanted = [path for path, hit in candidates.items() if any(needs_lines(matching) for _, matching in hit)]
    lines = changed_lines(top, changes.commit, wanted, changes.untracked) if wanted else {}
    found, with_category = [], 0
    for path in changes:
        hit = candidates[path]
        with_category += bool(hit)
        for category, matching in hit:
            why = []
            for block, _, pattern, text in matching:
                label = f"{block['id']} {block['key']}"
                if block["status"] != "freigegeben":
                    gone = older.get(id(block))
                    why.append(f"{label} steht {block['status']}" + (f", {', '.join(gone)} überholt" if gone else ""))
                    continue
                added = lines.get(path, ())
                if not text or (added is not None and any(text in line for line in added)):
                    break
                if added is None:
                    if UNREADABLE not in why:
                        why.append(UNREADABLE)
                    continue
                why.append(f"{label} freigegeben, aber „{text}“ in keiner hinzugefügten Zeile")
            else:
                reason = "; ".join(why) or (f"Freigaben nicht gelesen ({unread})" if unread else
                                            f"kein Eintrag mit passendem Schlüssel in {LEDGER_SHOWN}")
                found.append(f"- {path} — {category.name} ({category.grade}): {category.meaning} — {reason}")

    summary_line = (f"Stellen ohne Freigabe: {len(found)}" if found else "Keine Stelle ohne Freigabe") + (
        f" (Revision {rev}; {len(changes)} Dateien im Diff, {with_category} mit Kategorie)")
    return (1 if found else 0), notes + [summary_line] + found


# --- add --class klein ------------------------------------------------------------------

def add_small(root, session, args):
    """Kleine Entscheidung ins Protokoll; (exit, meldung).

    `args` ist ein argparse-Namespace oder ein Objekt mit den Attributen `topic`, `question`,
    `decision`, `evidence` (Strings oder None), `options` (Liste der `--option`-Werte oder None)
    und optional `home` (Path; Default `HOME`). Schreibt höchstens eine Zeile: `klein` mit
    Treffer, `annahme` mit „nichts gefunden“. Trifft eine Regel `immer fragen`, ist die Frage
    groß: ohne zwei bis vier `--option` Exit 1, sonst ein Block `D-<n>` (offen, Schlüssel
    `rule:<thema>`, `--decision` als Empfehlung) und die Protokollzeile `gross` mit der Regel.
    """
    return _add_small(root, session, args)[:2]


def _add_small(root, session, args):
    """Wie `add_small`, dazu als drittes, ob eine Regel `immer fragen` hochgestuft hat — aus
    derselben Regel-Lesung, die das Ergebnis bestimmt (für die Warnung in `main`)."""
    root = Path(root)
    home = Path(getattr(args, "home", None) or home_dir())
    missing = [f"--{name}" for name in ("topic", "question", "decision")
               if not (getattr(args, name, None) or "").strip()]
    if missing:
        return 1, f"add --class klein: es fehlt {', '.join(missing)}; nichts geschrieben.", False
    evidence = normalize_evidence(getattr(args, "evidence", None), root)
    problem = evidence_problem(evidence)
    if problem:
        return 1, problem, False

    rules, _, problems = read_rules(root, home)
    always, never, notes = rule_hits(rules, args.topic)
    notes = problems + notes
    if always:
        rule = always[0]
        options = _options(args)
        if not 2 <= len(options) <= 4:
            return 1, "\n".join(notes + [f"Regel immer fragen: {rule.topic} trifft — zwei bis vier --option "
                                         "nötig; nichts geschrieben."]), True
        lines = [f"Regel {rule_ref(rule)} trifft — die Frage ist groß; --decision ist die Empfehlung."]
        fields = {"question": args.question, "topic": rule.topic, "key": f"{RULE_CATEGORY}:{rule.topic}",
                  "options": options, "recommendation": args.decision, "answer": NONE, "source": NONE}
        row = {"zeit": datetime.now().isoformat(timespec="seconds"), "thema": rule.topic,
               "frage": args.question, "beleg": evidence, "regel": rule_label(rule)}
        code, stored = store_big(root, session, "offen", fields, row)
        return code, "\n".join(notes + lines + stored), True

    topic = never[0].topic if never else args.topic.strip()
    klasse = "annahme" if evidence.endswith(" — nichts gefunden") else "klein"
    values = {"zeit": datetime.now().isoformat(timespec="seconds"), "thema": topic, "klasse": klasse,
              "frage": args.question, "entscheidung": args.decision, "beleg": evidence,
              "regel": rule_label(never[0]) if never else NONE}
    path_shown = shown(log_path(root, session), root)
    existed = cache_exists(root)
    try:
        created, problem, unlocked, written = append_row(root, session, values)
    except LockBusy as busy:
        return 1, _locked_problem(busy, root, "Protokoll"), False
    except Unreadable as error:
        return 1, unreadable_problem(error, log_shown(root, session)), False
    except OSError as error:
        return 1, f"Protokoll {path_shown} nicht schreibbar ({error.strerror or error}); nichts geschrieben.", False
    if problem:
        return 1, problem, False

    what = "als Annahme (nichts gefunden)" if klasse == "annahme" else "als kleine Entscheidung"
    lines = notes + [f"Eingetragen {what}: {cell(topic)} — {cell(args.decision)} ({path_shown})"]
    if never:
        lines.append(f"Regel {rule_ref(never[0])} trifft — der Eintrag erscheint nicht in summary.")
    if unlocked:
        lines.append(f"Hinweis: ohne Sperre geschrieben ({unlocked}); ein gleichzeitiges add kann "
                     "eine Zeile überschreiben.")
    if created:
        lines.append(f"Protokoll angelegt: {path_shown}")
    notice = unversioned_notice(root, existed, written)
    if notice:
        lines.append(notice)
    return 0, "\n".join(lines), False


def klasse_label(entry):
    """Anzeige der Klasse eines Protokolleintrags: `klein`, `Annahme`, `groß` — für summary."""
    return {"annahme": "Annahme", "gross": "groß"}.get(entry["klasse"], "klein")


# --- summary und rules ------------------------------------------------------------------

def summary(root, session, home):
    """(exit, text): Einträge der Sitzung ohne kleine Einträge mit Thema einer Regel
    `nie fragen`; bei mehr als zehn die zehn jüngsten und der Pfad des Protokolls."""
    root = Path(root)
    return _summary(root, session, home, *log_entries(root, session))


def _summary(root, session, home, entries, problem):
    """`summary` aus schon gelesenen `log_entries` (check liest das Protokoll nur einmal)."""
    if problem:
        return 1, problem
    path_shown = shown(log_path(root, session), root)
    if not entries:
        return 0, f"Keine Einträge in dieser Sitzung ({session})."
    rules = load_rules(root, home)
    never = {_norm(r.topic) for r in rules if r.kind == "nie fragen"}
    always = {_norm(r.topic) for r in rules if r.kind == "immer fragen"}
    shown_entries, hidden = [], 0
    for entry in entries:
        topic = _norm(entry["thema"])
        if topic in never and topic not in always and entry["klasse"] in ("klein", "annahme"):
            hidden += 1
        else:
            shown_entries.append(entry)
    lines = [f"Einträge der Sitzung {session}: {len(shown_entries)}"]
    if hidden:
        lines.append(f"ausgelassen per nie fragen: {hidden}")
    if len(shown_entries) > SUMMARY_LIMIT:
        lines.append(f"die {SUMMARY_LIMIT} jüngsten von {len(shown_entries)}, alle im Protokoll")
        shown_entries = shown_entries[-SUMMARY_LIMIT:]
    for e in shown_entries:
        lines.append(f"- [{klasse_label(e)}] {e['thema']}: {e['frage']} → {e['entscheidung']} ({e['beleg']})")
    lines.append(f"Protokoll: {path_shown}")
    return 0, "\n".join(lines)


def list_rules(root, home):
    rules, ignored, problems = read_rules(root, home)
    if not rules:
        lines = [f"Keine Regeln (gesucht: {', '.join(s for _, s in _rule_files(root, home))})."]
    else:
        lines = [f"{rule_label(r)} — {r.source}:{r.line}" for r in rules]
        by_topic = {}
        for rule in rules:
            by_topic.setdefault(_norm(rule.topic), []).append(rule)
        for group in by_topic.values():
            always = [r for r in group if r.kind == "immer fragen"]
            never = [r for r in group if r.kind == "nie fragen"]
            if always and never:
                lines.append(contradiction(always, never))
    lines += [f"ignoriert: {line}" for line in ignored] + problems
    return 0, "\n".join(lines)


# --- guard: PreToolUse-Hook auf Bash (G3, optional) ----------------------------------------
# Erkennen statt zerlegen (Spec 28): Muster über den ganzen Text, genau zerlegt wird nur ein schlichter `git push`.

_SQL_PROGRAMS = ("psql", "sqlite3", "mysql")
_W, _E = r"(?<![\w.-])", r"(?![\w.-])"                # Wortgrenzen: `/bin/rm` trifft, `format` nicht
_SEG = r"(?:\\[;&|]|[^;&|\n])*"                       # Rest des einfachen Befehls bis `;`, `&`, `|`, Zeilenende
_GIT_GLOBAL = r"(?:\s+(?:-[Cc]\s+(?:\"[^\"]*\"|'[^']*'|[^\s-]\S*)|--(?:git-dir|work-tree|namespace|config-env)\s+[^\s-]\S*|-\S+))*\s+"
_SQL = (r"(?:\b(?:DROP\s+(?:TABLE|DATABASE|SCHEMA|COLUMN)|TRUNCATE)\b|\bALTER\s+TABLE\b[^;]*?\bDROP\b"
        r"|\bDELETE\s+FROM\b(?!(?:[^;'\"&|]|&(?!&))*\bWHERE\b))")


def _start(command):
    """Muster: `git` mit globalen Optionen, `gh` Wort an Wort, sonst Wort 2 im Rest (`npm --tag x publish`)."""
    first, *rest = command.split()
    gap = _GIT_GLOBAL if first == "git" else r"\s+" if first == "gh" else _E + _SEG + r"?\s"
    return _W + first + (gap + r"\s+".join(rest) if rest else "") + _E


def _has(*options):
    """Lookahead: im Rest des einfachen Befehls steht eine der Optionen, mit Leerraum davor."""
    return rf"(?={_SEG}?\s(?:{'|'.join(options)}))"


# Mustertabelle (Kategorie, Befehl, Regex); dieselbe in `references/reversibility.md` („Befehle, die guard
# erkennt“), hier, weil die Hook-Kopie ohne `references/` läuft. Ein Test hält beide gleich.
GUARD_PATTERNS = tuple((category, command, _start(command) + condition) for category, command, condition in (
    ("push", "git push", ""), ("push", "gh pr merge", ""), ("push", "gh release create", ""),
    *(("external", f"gh {w}", "") for w in ("pr create", "pr comment", "pr close", "pr review", "pr edit", "issue create",
                                            "issue close", "issue comment", "repo delete", "release delete")),
    ("external", "gh api", _has(r"-X\s*(?!(?i:get)\b)\w", r"--method[=\s]\s*(?!(?i:get)\b)\w", r"-[fF]",
                                r"--(?:field|raw-field|input)" + _E)),
    *(("external", f"{program} publish", "") for program in ("npm", "yarn", "pnpm", "cargo", "uv", "poetry")),
    *(("external", command, "") for command in ("twine upload", "docker push", "terraform apply", "terraform destroy",
                                                "kubectl apply", "kubectl delete")),
    ("external", "curl", _has(r"-[a-zA-WYZ]*[dFT]", r"--(?:data|form)[\w-]*", r"--(?:json|upload-file)" + _E,
                              r"-[a-zA-Z]*X\s*(?!(?:GET|HEAD)\b)\w", r"--request[=\s]\s*(?!(?:GET|HEAD)\b)\w")),
    ("external", "wget", _has(r"--(?:post-data|post-file|method)" + _E)),
    ("data-delete", "rm", _has(r"-[a-zA-Z]*[rR]", r"--recursive" + _E)),      # Ausnahmeliste: `_rm_exempt`
    ("data-delete", "find", _has(r"-delete" + _E, rf"-(?:exec|execdir|ok|okdir)\s{_SEG}?{_W}rm{_E}")),
    ("data-delete", "git clean", _has(r"-[a-zA-Z]*f", r"--force" + _E)),
    ("data-delete", "git branch", "(?:" + _has(r"-[a-zA-Z]*D") + "|" + _has(r"--delete" + _E, r"-[a-zA-Z]*d")
     + _has(r"--force" + _E, r"-[a-zA-Z]*f") + ")"),
    ("unsaved-work", "git reset", _has(r"--(?:hard|merge|keep)" + _E)),
    ("unsaved-work", "git checkout", _has(r"(?:--|\.)(?=[\s;&|)]|$)", r"-[a-zA-Z]*f", r"--force" + _E)),
    ("unsaved-work", "git restore", rf"(?:(?!{_SEG}?\s(?:--staged{_E}|-[a-zA-Z]*S))|"
     + _has(r"--worktree" + _E, r"-[a-zA-Z]*W") + ")"),
    ("unsaved-work", "git switch", _has(r"-[a-zA-Z]*f", r"--(?:force|discard-changes)" + _E)),
    ("unsaved-work", "git stash drop", ""), ("unsaved-work", "git stash clear", ""),
)) + tuple(("data-delete", p, rf"(?is)\A(?=.*{_W}{p}{_E}).*?{_SQL}") for p in _SQL_PROGRAMS)
_GUARD_RES = [(category, command, re.compile(pattern)) for category, command, pattern in GUARD_PATTERNS]
_PUSH_RE = next(regex for _, command, regex in _GUARD_RES if command == "git push")
_PROGRAM_RE = re.compile(_W + "(?:" + "|".join(dict.fromkeys(c.split()[0] for _, c, _ in GUARD_PATTERNS)) + ")" + _E)
_REST_RE = re.compile(_SEG)
# Rumpf der Commit-Vorlage von Claude Code: `"$(cat <<'WORT'` … `WORT` `)"` ist Text, kein Befehl — nur direkt
# hinter einer Nachrichtenoption, nicht hinter `bash -c` oder `eval`.
_TEMPLATE_RE = re.compile(r"((?<!\S)(?:-[a-zA-Z]*[mF]|--(?:message|body|title|notes))(?:=|\s+))"
                          r"\"\$\(cat <<-? ?(['\"])([A-Za-z_][\w.-]*)\2[ \t]*\n"
                          r"(?:(?!^[ \t]*\3[ \t]*$).)*^[ \t]*\3[ \t]*\n\s*\)\"", re.S | re.M)  # bis zum ersten Endwort
_QUOTED_RE = re.compile(r"\\.|'[^']*'?|\"(?:\\.|[^\"\\])*\"?", re.S)
_REDIRECT_OK_RE = re.compile(r"2>&1|[12]?>[ \t]*/dev/null")
_NOT_PLAIN_RE = re.compile(r"[$`()<>|]|(?<!&)&(?!&)|" + _W + r"(?:cd|pushd|popd)" + _E)
_PUSH_QUIET = frozenset({"--set-upstream", "--verbose", "--quiet", "--no-verify", "--progress", "--porcelain"})
RM_EXEMPT_PREFIX = ".skills/cache/"                 # Ausnahmeliste für `rm -r` (Annahme Spec 28: regenerierbar)
RM_EXEMPT_PARTS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules",
                             "build", "dist", ".venv"})
GUARD_ALWAYS, GUARD_PLAIN = "immer Rückfrage", "Befehl nicht schlicht"
GUARD_SHOWN = 80                                    # Zeichen des Befehls im Grund (Annahme, nicht gemessen)
HOOK_UNCHECKED = "[decide] Hook ungeprüft"


def _rm_exempt(rest):
    """Ausnahmeliste: jedes Ziel hinter `rm` (shlex) ohne `..`, `~`, `$`, Backtick und Glob, relativ unter
    `.skills/cache/` oder mit einer Komponente aus `RM_EXEMPT_PARTS`, absolut unter `/tmp/`. Kein Ziel → nein.
    Nach `--` ist jedes Wort ein Ziel; Umleitungen (`2>/dev/null`, `> log`) sind keine."""
    with suppress(ValueError):                          # ein Fehler von shlex: keine Ausnahme
        paths, options, skip = [], True, False
        for word in shlex.split(rest):
            if skip or re.match(r"(?:\d*|&)[<>]", word):    # Umleitung; allein (`>`, `2>>`) mit Ziel im nächsten Wort
                skip = not skip and re.fullmatch(r"(?:\d*|&)[<>]+", word) is not None
            elif options and word.startswith("-"):
                options = word != "--"
            else:
                paths.append((word, posixpath.normpath(word)))
        return bool(paths) and not any(
            re.search(r"[~$`*?\[]", word) or ".." in word.split("/") or not (
                path.startswith("/tmp/") if path.startswith("/")
                else path.startswith(RM_EXEMPT_PREFIX) or RM_EXEMPT_PARTS & set(path.split("/")))
            for word, path in paths)
    return False


def _plain_push_part(text):
    """(Teil, Wörter) des einen `git push`, wenn `text` schlicht ist (Spec 28, Ablauf 4), sonst None."""
    # Anführungszeichen gleich lang maskiert; in doppelten bleiben unmaskiertes `$(` und Backtick stehen
    masked = _QUOTED_RE.sub(lambda m: re.sub(r"\\.|\$(?!\()|[^$`]" if m.group(0)[0] == '"' else r"(?s).",
                                             lambda c: "_" * len(c.group(0)), m.group(0)), text)
    for m in _REDIRECT_OK_RE.finditer(masked):
        masked, text = (s[:m.start()] + " " * len(m.group(0)) + s[m.end():] for s in (masked, text))
    cuts = [0] + [i for m in re.finditer(r"&&|;|\n", masked) for i in m.span()] + [len(text)]
    pushes = [part for part in (text[a:b] for a, b in zip(cuts[::2], cuts[1::2])) if _PUSH_RE.search(part)]
    if not _NOT_PLAIN_RE.search(masked) and len(pushes) == 1 and _PUSH_RE.match(pushes[0].strip()):
        with suppress(ValueError):                      # ein Fehler von shlex: nicht schlicht
            return pushes[0], shlex.split(pushes[0])
    return None


def _push_reason(words, directory):
    """Grund der Rückfrage für einen schlichten `git push` (Spec 28 „Push-Ziel“), None bei `--dry-run` oder
    wenn ein freigegebener Block `push:<muster>` ohne `#<text>` das Ziel `<remote>/<zweig>` trifft."""
    i = 1
    while i < len(words) and words[i] != "push":
        if words[i] != "-C" or i + 1 >= len(words):
            return GUARD_ALWAYS                         # jede globale Option außer `-C <pfad>`
        directory, i = directory / words[i + 1], i + 2
    args, git = words[i + 1:], functools.partial(_git, directory)
    longs = {arg.split("=", 1)[0] for arg in args if arg.startswith("--")}
    shorts = set("".join(arg[1:] for arg in args if arg.startswith("-") and not arg.startswith("--")))
    operands = [arg for arg in args if not arg.startswith("-")]
    if any(arg in ("-n", "--dry-run") and before not in ("-o", "--push-option")       # nur als eigenes Wort
           for before, arg in zip(["push"] + args, args)):
        return None
    if longs - _PUSH_QUIET or shorts - set("uvq") or len(operands) > 2:
        return GUARD_ALWAYS
    if len(operands) < 2:
        push = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{push}")
        target = push.stdout.strip() if push.returncode == 0 else ""
        if not target or (operands and not target.startswith(operands[0] + "/")):
            return GUARD_ALWAYS
    else:
        source, colon, dest = operands[1].partition(":")
        head = git("symbolic-ref", "-q", "--short", "HEAD") if source in ("HEAD", "@") else None
        if source.startswith("+") or (colon and not source) or (head and head.returncode) or (
                not head and git("show-ref", "--verify", "--quiet", f"refs/tags/{source}").returncode == 0):
            return GUARD_ALWAYS                         # Zwang, Löschen, abgelöster HEAD oder Tag als Quelle
        dest = re.sub(r"^refs/heads/", "", dest or (head.stdout.strip() if head else source))
        if dest.startswith("refs/") or not dest:
            return GUARD_ALWAYS
        target = f"{operands[0]}/{dest}"
    remote = target.split("/", 1)[0]
    config = git("config", "--get-regexp", r"^(push\.default|remote\..*\.(push|mirror))$").stdout
    for key, _, value in (line.partition(" ") for line in config.splitlines()):
        if (key, value) == ("push.default", "matching") or key == f"remote.{remote}.push" or (
                key == f"remote.{remote}.mirror" and value.lower() in ("", "true", "yes", "on", "1")):
            return GUARD_ALWAYS
    blocks, problem = read_ledger(repo_root(directory))     # jüngster Block je Frage und Schlüssel, wie bei check
    if any(key and key[0] == "push" and not key[2] and glob_to_regex(key[1]).fullmatch(target) for key in
           (parse_key(block["key"])[0] for block in _latest(blocks)[0] if block["status"] == "freigegeben")):
        return None
    return f"keine Freigabe mit Schlüssel push:{target} in {LEDGER_SHOWN}" + (f" ({problem})" if problem else "")


def _guard_hit(command, root, cwd=None):
    """(Kategorie, Befehl, Grund) der Rückfrage oder None (Spec 28, Ablauf 1–4); Subprozesse nur im Push-Fall."""
    if not _PROGRAM_RE.search(command):
        return None
    text, push = _TEMPLATE_RE.sub(r"\1''", command).replace("\\\n", " "), False
    # `;`, `&`, `|` in Anführungszeichen trennen nicht: gleich lange Kopie ohne sie; SQL sieht den Text selbst
    scan = _QUOTED_RE.sub(lambda m: re.sub(r"[;&|]", " ", m.group(0)), text)
    for category, name, pattern in _GUARD_RES:
        for m in pattern.finditer(text if name in _SQL_PROGRAMS else scan):
            if name == "git push":
                push = True
            elif not (name == "rm" and _rm_exempt(_REST_RE.match(scan, m.end()).group(0))):
                return category, text[m.start():_REST_RE.match(scan, m.start()).end()], GUARD_ALWAYS
    plain = _plain_push_part(text) if push else None
    if plain is None:
        return ("push", command, GUARD_PLAIN) if push else None
    try:
        why = _push_reason(plain[1], Path(cwd or root))
    except (NoGit, GitTimeout):
        why = GUARD_ALWAYS
    return None if why is None else ("push", plain[0], why)


def guard_decision(command, root, cwd=None):
    """None (nichts erkannt oder Push freigegeben) oder (Kategorie, Grund); `cwd` ist Default `root`."""
    hit = _guard_hit(command, root, cwd)
    return None if hit is None else (hit[0], hit[2])


def _hook_unchecked(why):
    return json.dumps({"systemMessage": f"{HOOK_UNCHECKED} — {why}"})


def guard(text):
    """Antwort auf das Hook-JSON (`tool_input.command`, `cwd`): "", `ask` mit „decide: <kategorie> — <befehl>:
    <grund>“ oder bei eigenem Fehler `systemMessage`. Wirft nie."""
    try:
        data = json.loads(text)
        tool_input = data.get("tool_input") if isinstance(data, dict) else None
        if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
            return _hook_unchecked("tool_input.command fehlt")
        cwd = data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else os.getcwd()
        hit = _guard_hit(tool_input["command"], None, cwd)
        if hit is None:
            return ""
        shown = " ".join(hit[1].split())                # höchstens `GUARD_SHOWN` Zeichen
        shown = shown if len(shown) <= GUARD_SHOWN else shown[:GUARD_SHOWN - 1] + "…"
        return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                                  "permissionDecisionReason": f"decide: {hit[0]} — {shown}: {hit[2]}"}})
    except json.JSONDecodeError as error:
        return _hook_unchecked(f"kein JSON auf stdin ({error.msg})")
    except Exception as error:                      # guard hält nie wegen eines eigenen Fehlers an
        return _hook_unchecked(f"{type(error).__name__}: {error}")


def _guard_main():
    """`guard`: stdin lesen, Antwort schreiben, immer Exit 0."""
    try:
        stream = getattr(sys.stdin, "buffer", None)
        out = guard(stream.read().decode("utf-8", errors="replace") if stream else sys.stdin.read())
    except Exception as error:
        out = _hook_unchecked(f"{type(error).__name__}: {error}")
    with suppress(Exception):
        print(out, end="\n" if out else "")
    return 0


# --- Kommandozeile ----------------------------------------------------------------------

def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--session", default=None, help="Sitzung (Default: CLAUDE_CODE_SESSION_ID)")
    parser = argparse.ArgumentParser(prog="decide_log.py", description="Protokoll eigener Entscheidungen (decide).")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("rules", help="wirksame Regeln mit Datei")
    add = sub.add_parser("add", parents=[common], help="Entscheidung eintragen")
    add.add_argument("--class", dest="cls", choices=["klein", "gross"], required=True)
    add.add_argument("--topic")
    add.add_argument("--question")
    add.add_argument("--decision")
    add.add_argument("--evidence")
    add.add_argument("--option", dest="options", action="append", default=None)
    add.add_argument("--recommendation")
    add.add_argument("--key")
    add.add_argument("--approved-by-request", dest="approved_by_request")
    sub.add_parser("summary", parents=[common], help="Einträge der laufenden Sitzung")
    res = sub.add_parser("resolve", help="Antwort auf eine große Frage eintragen")
    res.add_argument("decision_id", metavar="D-<n>")
    res.add_argument("--answer")
    res.add_argument("--reject", action="store_true")
    sub.add_parser("open", help="offene große Fragen")
    chk = sub.add_parser("check", parents=[common],
                         help="teure Änderungen seit einer Revision ohne Freigabe, dann Übergabe")
    chk.add_argument("--range", dest="rev", required=True, metavar="<rev>")
    sub.add_parser("guard", help="PreToolUse-Hook auf Bash: Hook-JSON auf stdin, Exit immer 0")
    return parser


def main(argv):
    """Einstieg; `argv` ohne Programmnamen (None: `sys.argv[1:]`). Gibt den Exit-Code zurück."""
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv == ["guard"]:
        return _guard_main()                        # vor allem anderen: der Hook endet immer mit 0
    args = build_parser().parse_args(argv)
    root = repo_root(Path.cwd())
    home = home_dir()

    warning = None
    if args.action == "rules":
        code, message = list_rules(root, home)
    elif args.action == "resolve":
        code, message = resolve(root, args.decision_id, args.answer, args.reject)
    elif args.action == "open":
        code, message = open_questions(root)
    elif args.action == "check":
        code, message = check(root, args.rev, session_id(args.session), home)
    else:
        session = session_id(args.session)
        if not session:
            code, message = 1, ("Keine Sitzung: CLAUDE_CODE_SESSION_ID ist nicht gesetzt — "
                                "--session <id> angeben; nichts geschrieben.")
        elif not valid_session(session):
            code, message = 1, f"Sitzung „{session}“ ungültig (kein / oder \\, nicht . oder ..) — --session <id> angeben."
        elif args.action == "summary":
            code, message = summary(root, session, home)
        elif args.cls == "gross":
            args.home = home
            code, message = add_big(root, session, args)
            ignored = [flag for attr, flag in SMALL_FLAGS if getattr(args, attr, None)]
            if code == 0 and ignored:
                warning = (f"Hinweis: {', '.join(ignored)} gehör{'en' if len(ignored) > 1 else 't'} zu "
                           "--class klein — bei einer großen Frage ignoriert.")
        else:
            args.home = home
            code, message, upgraded = _add_small(root, session, args)
            ignored = [flag for attr, flag in BIG_FLAGS
                       if getattr(args, attr, None) and not (upgraded and attr == "options")]
            if code == 0 and ignored:
                what = ("bei einer per Regel hochgestuften Frage ignoriert (--decision ist die Empfehlung, "
                        "der Schlüssel rule:<thema>)." if upgraded else
                        "bei einer kleinen Entscheidung ignoriert; ist die Frage groß, mit --class gross eintragen.")
                warning = (f"Hinweis: {', '.join(ignored)} gehör{'en' if len(ignored) > 1 else 't'} zu "
                           f"--class gross — {what}")
    # check: Stellen und Befunde sind ein Bericht
    report = code == 0 or (code == 1 and args.action == "check")
    print(message, file=sys.stdout if report else sys.stderr)
    if warning:
        print(warning, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main(None))
