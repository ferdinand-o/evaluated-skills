#!/usr/bin/env python3
"""Protokoll eigener Entscheidungen für decide (Spec 28). Tier 1, nur Stdlib.

    decide_log.py rules                         wirksame Regeln mit Datei und Zeile
    decide_log.py add --class klein …           kleine Entscheidung oder Annahme mit Belegzeile
    decide_log.py add --class gross …           große Frage als Block D-<n> (offen oder per Auftrag freigegeben)
    decide_log.py resolve D-<n> --answer "…" | --reject   Antwort auf eine offene große Frage eintragen
    decide_log.py open                          offene große Fragen
    decide_log.py summary                       Einträge der laufenden Sitzung
    decide_log.py check --range <rev>           teure Änderungen im Diff ohne Freigabe
    decide_log.py brief --topic T               Auftrag an einen Subagenten schreiben (brief-<n>.md)
    decide_log.py brief --check <datei>         Auftrag vor dem Dispatch prüfen

Aufruf: `python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py"`. Repo-Wurzel ist einmal
`git rev-parse --show-toplevel` (`repo_root`), sonst das Arbeitsverzeichnis. Die Sitzung ist
`--session`, sonst `CLAUDE_CODE_SESSION_ID`; nur `add`, `summary` und `brief --topic` brauchen sie.

Ablageorte:
- `.skills/cache/decide/<session>/log.md` — Protokoll der Sitzung, `brief-<n>.md` daneben
- `docs/big-decisions.md` — Ablage großer Fragen (committet); Sperre unter `.skills/cache/decide/`
- `.skills/decide/rules.md` und `~/.skills/decide/rules.md` — Regeln `immer fragen` / `nie fragen`

Regeln und Formate stehen nicht hier, sondern an je einer Stelle: Kategorien, Pfadmuster,
Schlüssel und was check sieht in `references/reversibility.md`; Ablage, Optionen und Empfehlung in
`references/option-memo.md`; Form des Auftrags, Satz für Subagenten und Wortliste in
`references/brief.md`; Ablauf, Belegzeile und Regeln in `SKILL.md`. Die Funktions-Docstrings
beschreiben das Verhalten im Einzelnen.

Exit-Codes: 0 Erfolg; 1 abgewiesen oder nicht geschrieben (Grund auf stderr) bzw. bei check und
`brief --check` mindestens ein Befund (Bericht auf stdout); 2 falscher Aufruf (argparse) und jedes
„ungeprüft — …“ (kein Git, Git antwortet nicht, Reference fehlt oder parst nicht), nie ein Erfolg.
Das Skript meldet; es hält niemanden an.
"""
import argparse
import errno
import functools
import os
import re
import shlex
import subprocess
import sys
import time
from contextlib import contextmanager
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
# Die eine Quelle für Kategorien, Grad und Pfadmuster (load_categories); keine Liste im Skript.
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
BLOCK_RE = re.compile(r"^## (?P<id>D-(?P<number>\d+)) · (?P<date>\S+) · (?P<status>\S+)\s*$")
BLOCK_NUMBER_RE = re.compile(r"(?m)^## D-(\d+)\b")
SKIPPED = " — Freigaben übersprungen"
FIELDS = (("question", "Frage"), ("topic", "Thema"), ("key", "Schlüssel"), ("options", "Optionen"),
          ("recommendation", "Empfehlung"), ("answer", "Antwort"), ("source", "Quelle der Antwort"))

# Auftrag an einen Subagenten (brief). Die Wortliste steht in references/brief.md (load_wordlist).
BRIEF_REFERENCE = SKILL_DIR / "references" / "brief.md"
BRIEF_FIELDS = ("Frage", "Anlass", "Feste Vorgaben", "Schon entschieden", "Wo nachsehen", "Rückgabe")
BRIEF_LIMIT = 25                # Zeilen mit Text ohne Kopfzeile
BRIEF_EMPTY = 3                 # Frage, Anlass, Wo nachsehen: je mindestens eine Zeile vom Hauptagenten
WORDLIST_HEADING = "## Wortliste"
# Der Satz für Subagenten (Spec 28, Ablauf 5) steht nur in references/brief.md, als Zitat in diesem
# Abschnitt (load_subagent_sentence); `brief --check` prüft ihn bewusst nicht.
SENTENCE_HEADING = "## Der Satz für Subagenten"
RETURN_FORM = ("Je Option: Belege `datei:zeile`, Folgen, Umkehrbarkeit; dann eine Empfehlung mit Grund. "
               "Kleine Entscheidungen unterwegs mit Belegzeile `gesucht: … — Treffer: datei:zeile`.")
NOT_DECIDED = "nicht entscheiden, nicht darauf aufbauen"
LEDGER_UNREAD = ("offene große Fragen zum Thema möglich; nichts entscheiden, was teuer umkehrbar ist, "
                 "sondern zurückgeben")
NO_TOPIC_CHECK = "prüfen, ob sie das Thema betrifft"
_HEADING_RE = re.compile(r"^ {0,3}#{1,6}\s+(?P<name>.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
_QUOTE_RE = re.compile(r"^ {0,3}>\s?(?P<text>.*)$")
# Beginnt eine Zeile direkt nach einem Zitat so, endet das Zitat wie in Markdown (load_subagent_sentence).
_QUOTE_END_RE = re.compile(r"^ {0,3}(?:```|~~~|[-*+] |\d+\. |#|<!--)")


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
    gibt `read_rules` aus demselben Lesevorgang (add, brief und rules lesen nur darüber)."""
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
    `\n` — für `read_file` und für die Ablage aus einer Revision (`_ledger_at`)."""
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


def ledger_problem(text, tail="Freigaben übersprungen", shown_as=LEDGER_SHOWN):
    """Konsumenten-Regel für die Ablage: None, wenn die Kopfzeile passt, sonst der Grund; `shown_as`
    nennt die Ablage („docs/big-decisions.md in <rev>“, wenn aus einer Revision gelesen)."""
    return header_problem(text, shown_as, tail)


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
    return _ledger_from_text(text)


def _ledger_from_text(text, shown_as=LEDGER_SHOWN):
    """(Blöcke, Problem, existiert) aus dem Rohtext der Ablage (None: fehlt) — für die Arbeitskopie
    (`_read_ledger`) und für eine Revision (`_ledger_at`, dann nennt `shown_as` sie)."""
    if _blank_is_missing(text) is None:
        return [], None, text is not None
    problem = ledger_problem(text, shown_as=shown_as)
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
    immer. Eine Ablehnung beantwortet nichts: danach ist ein add eine neue Frage oder ein neuer Auftrag."""
    return (block["status"] == "freigegeben" and _asked_before(block, fields)
            and (status != "offen" or _difference(block, "offen", fields) is None))


def append_block(root, status, fields):
    """Hängt einen Block an; liest die Ablage unter ihrer Sperre unmittelbar davor neu.
    (Nummer, angelegt, Problem, ohne Sperre: None oder Ursache, schon da: None oder der Block, früher:
    None oder der letzte beantwortete Block derselben Frage, auf den eine neue offene Frage folgt). Steht
    derselbe Block schon (`_same_block`) oder die Frage schon beantwortet (`_answered`), wird nichts
    geschrieben und „schon da“ ist dieser Block; weichen bei einer offenen Frage nur Optionen oder
    Empfehlung ab (`_same_question`), wird nichts geschrieben und das Problem nennt das Feld. Wirft
    `LockBusy`, `Unreadable` oder OSError."""
    path = ledger_path(root)
    earlier = None
    with log_lock(ledger_lock_path(root)) as unlocked:
        text = read_ledger_text(root)
        if text is not None:
            problem = ledger_problem(text, "nichts geschrieben")
            if problem:
                return None, False, problem, unlocked, None, None
            blocks = parse_blocks(text)
            same = next((b for b in blocks if _same_block(b, status, fields)), None) \
                or next((b for b in blocks if _answered(b, status, fields)), None)
            if same:
                return same["number"], False, None, unlocked, same, None
            other = next((b for b in blocks if _same_question(b, status, fields)), None)
            if other:
                how = " oder mit resolve beantworten" if status == "offen" else ""
                return None, False, (f"{other['id']} steht {status} mit {_difference(other, status, fields)} — "
                                     f"von Hand ändern{how} "
                                     f"({LEDGER_SHOWN}); nichts geschrieben."), unlocked, None, None
            if status == "offen":
                earlier = next((b for b in reversed(blocks) if b["status"] in ("freigegeben", "abgelehnt")
                                and _asked_before(b, fields)), None)
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
    <status> (Antwort: …)“), wird nur eine fehlende Protokollzeile ergänzt; ob sie fehlt, prüft
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
        lines.append(f"{did} ist schon {existing['status']} (Antwort: {line_value(existing['answer'])}) in "
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
    check. `#<text>` meint hinzugefügte Zeilen, `#-<text>` entfernte; der Text behält dann sein
    führendes `-`. Leerraum um Kategorie, Pfadmuster und Text fällt weg, Leerraum im Text wird
    zusammengezogen; Leerzeichen im Pfadmuster bleiben, Tab und Zeilenumbruch darin sind ein Fehler,
    ebenso ein `#` oder `#-` ohne Text (der gäbe sonst die ganze Datei frei). Das Pfadmuster ist relativ zur Repo-Wurzel wie die
    Pfade im Diff: ein führendes `./` fällt weg; ein absoluter Pfad oder ein Teil `..` träfe nie eine
    Datei und ist ein Fehler („Pfadmuster muss relativ zur Repo-Wurzel sein“). Bei `rule:<thema>` ist
    alles nach `rule:` das Thema (auch mit `#`, etwa `rule:C#`), der Text leer."""
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
    sign = "-" if text.strip().startswith("-") else ""
    words = " ".join(text.strip()[len(sign):].split())
    if hash_ and not words:
        return None, f"hat leeren Text nach #{sign}"
    return (category, pattern, sign + words), None


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
    root = Path(root)
    blocks, problem, exists = _read_ledger(root)
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
    Sekunden, `NoGit`, wenn es nicht startet. `raw`: stdout als Bytes (zum Dekodieren mit
    `decode_text`), stderr als Text."""
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
    """Die Stellen eines Bereichs: sortierte Pfade relativ zur Repo-Wurzel mit `/`. Dazu `top`
    (Wurzel des Repos), `untracked` (die unversionierten unter ihnen), `end` (Revision, aus der check
    die Ablage liest; None: die Arbeitskopie), `revs` (Basis und Ende für `git diff`, bei einer
    Einzelrevision nur sie) und `notes` (Hinweise für die Ausgabe, etwa zum Merge)."""

    def __init__(self, files=(), top=None, untracked=(), end=None, revs=(), notes=()):
        super().__init__(files)
        self.top, self.untracked, self.end = top, set(untracked), end
        self.revs, self.notes = tuple(revs), tuple(notes)


MERGE_NOTE = "Merge: verglichen mit erstem Elternteil"


def _top_level(rev):
    """`rev`, der Inhalt von `{…}` (`@{…}`, `^{…}`) gleich lang durch `_` ersetzt: `^!` und `^-` zählen
    nur außerhalb."""
    return re.sub(r"\{[^{}]*\}", lambda match: "{" + "_" * (len(match.group()) - 2) + "}", rev)


def _revision_ends(top, rev):
    """(einzeln, Ende, Revisionen für `git diff`, Hinweise, Problem, Wurzel) aus einem Aufruf
    `git rev-parse --git-dir --show-toplevel --symbolic <rev> --`: Basis und Ende stehen ausdrücklich in
    dessen Ausgabe, `git diff` bekommt nie die rohe Angabe; die Wurzel (`--show-toplevel`, sonst `top`)
    nimmt `changed_files` statt `top`. Fehlt die erste Zeile (`--git-dir`), ist es kein Repo.
    Eine positive und eine negative Revision (`<a>..<b>`, `<rev>^-<n>`, `<rev>^!` mit einem Elternteil):
    Basis die negative, Ende die positive. Eine positive und mehrere negative (`<merge>^!`): Basis der
    erste Elternteil, wie `<merge>^1..<merge>`, mit Hinweis `MERGE_NOTE`. Zwei positive mit negativen
    (`<a>...<b>`; rev-parse nennt `<b>`, `<a>`, `^<merge-base>`): Basis die Merge-Base, Ende `<b>`;
    ohne Merge-Base (keine gemeinsame Historie) fehlen die negativen: Problem „keine gemeinsame Basis“.
    Eine positive ohne negative: Einzelrevision (Diff gegen den Arbeitsbaum, Ende None) — außer die
    Angabe enthält `^!` oder `^-` außerhalb von `{…}`: der Root-Commit, Basis der leere Baum. Mehrere
    positive ohne negative (`HEAD^@` bei einem Merge) oder keine: Problem. Das Ende heißt, wie rev-parse
    `--symbolic` es nennt — wie angegeben (`v2`, nicht der Hash des Tag-Objekts)."""
    result = _git(top, "rev-parse", "--git-dir", "--show-toplevel", "--symbolic", rev, "--")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return False, None, (), (), "kein Git", top
    if result.returncode != 0:
        return False, None, (), (), f"git rev-parse {rev} fehlgeschlagen: {_git_error(result)}", top
    top = Path(lines[1]) if len(lines) > 1 else top
    names = [name for name in lines[2:] if name != "--"]
    positive = [name for name in names if not name.startswith("^")]
    negative = [name[1:] for name in names if name.startswith("^")]
    if len(positive) == 1 and len(negative) == 1:
        return False, positive[0], (negative[0], positive[0]), (), None, top
    if len(positive) == 1 and negative:
        return False, positive[0], (negative[0], positive[0]), (f"{MERGE_NOTE} ({negative[0]}).",), None, top
    if len(positive) == 2 and negative:
        notes = (f"Mehrere Merge-Basen: verglichen mit {negative[0]}.",) if len(negative) > 1 else ()
        return False, positive[0], (negative[0], positive[0]), notes, None, top
    if len(positive) == 2 and "..." in _top_level(rev):
        return False, None, (), (), f"keine gemeinsame Basis ({rev})", top
    if len(positive) > 1:
        return False, None, (), (), f"Bereich mit mehreren Enden ({rev})", top
    if not positive:
        return False, None, (), (), f"Bereich „{rev}“ ohne End-Revision", top
    if re.search(r"\^[!-]", _top_level(rev)):                     # R^! auf dem ersten Commit
        empty = _git(top, "hash-object", "-t", "tree", "--stdin")
        if empty.returncode != 0:
            return False, None, (), (), f"git hash-object fehlgeschlagen: {_git_error(empty)}", top
        return False, positive[0], (empty.stdout.strip(), positive[0]), (), None, top
    return True, None, (positive[0],), (), None, top


def changed_files(root, rev):
    """(Dateien, Problem): die Stellen des Bereichs als `Changes` — eine Liste der Pfade relativ
    zur Repo-Wurzel mit `/`, sortiert, dazu `top`, `untracked`, `end`, `revs` und `notes`. Die eine
    Quelle für check. `root` ist die Repo-Wurzel, wie `main` sie mit `repo_root` bestimmt hat; `top`
    ist die Wurzel, die Git im selben `rev-parse` wie Basis und Ende nennt (`_revision_ends`) — fiel
    `repo_root` auf ein Unterverzeichnis zurück, liest check trotzdem an der Wurzel.
    Basis und Ende sagt `_revision_ends`. Eine einzelne Revision: `git diff <rev>` (Commits seit `<rev>`
    und Arbeitsbaum) plus `git ls-files --others --exclude-standard`, Ablage aus der Arbeitskopie (`end`
    None). Ein Bereich: nur `git diff <basis> <ende>`, `end` ist das Ende, wie angegeben.
    Problem: None, „kein Git“ (kein `git` oder kein Repo), „git antwortet nicht in <n> s“, ein
    ungültiger Bereich (leer, mit Leerraum oder führendem `-`), einer mit mehreren Enden, einer ohne
    gemeinsame Basis oder der Grund, mit dem Git abbricht; dann sind die Dateien leer."""
    rev = (rev or "").strip()
    if not rev or rev.startswith("-") or re.search(r"\s", rev):
        return Changes(), f"Bereich „{rev}“ ungültig — erwartet <rev> oder <a>..<b>"
    top = Path(root)
    try:
        single, end, revs, notes, problem, top = _revision_ends(top, rev)
        if problem:
            return Changes(top=top), problem
        diff = _git(top, "diff", "--name-only", "-z", "--no-renames", "--no-ext-diff", *revs, "--")
        if diff.returncode != 0:
            return Changes(top=top), f"git diff {' '.join(revs)} fehlgeschlagen: {_git_error(diff)}"
        files = {name for name in diff.stdout.split("\0") if name}
        untracked = set()
        if single:
            others = _git(top, "ls-files", "--others", "--exclude-standard", "--full-name", "-z")
            if others.returncode != 0:
                return Changes(top=top), f"git ls-files --others fehlgeschlagen: {_git_error(others)}"
            untracked = {name for name in others.stdout.split("\0") if name} - files
    except GitTimeout:
        return Changes(), timeout_problem()
    except NoGit:
        return Changes(), "kein Git"
    return Changes(sorted(files | untracked), top, untracked, end, revs, notes), None


_C_QUOTE = {"\a": "a", "\b": "b", "\t": "t", "\n": "n", "\v": "v", "\f": "f", "\r": "r", '"': '"', "\\": "\\"}


def _git_quoted(name):
    """`name`, wie Git ihn mit `core.quotePath=false` im Kopf `diff --git` schreibt: mit Steuerzeichen,
    `"` oder `\\` in Anführungszeichen mit C-Escapes (sonst Oktal), sonst wörtlich."""
    if not any(c in _C_QUOTE or c < " " or c == "\x7f" for c in name):
        return name
    return '"' + "".join("\\" + _C_QUOTE[c] if c in _C_QUOTE else f"\\{ord(c):03o}" if c < " " or c == "\x7f"
                         else c for c in name) + '"'


DIFF_CHUNK = 200


class DiffFailed(Exception):
    """`git diff` für die Zeilen der `#<text>`-Freigaben lieferte keinen Diff; die Ursache als Text."""


def changed_lines(top, revs, paths, untracked):
    """{Pfad: {"+": hinzugefügte Zeilen, "-": entfernte}} jeder Datei aus `paths` im Bereich (`revs` aus
    `changed_files`), Leerraum zusammengezogen — für `#<text>` und `#-<text>`. Eine unversionierte Datei
    ist ganz hinzugefügt. Die anderen kommen aus `git diff -U0`, je höchstens `DIFF_CHUNK` Pfade ein
    Aufruf, aufgeteilt an den Köpfen `diff --git a/<p> b/<p>`, die das Skript je Pfad selbst so bildet,
    wie Git sie schreibt (`_git_quoted`). Liefert Git einen Block nicht, `DiffFailed`; antwortet es
    nicht in `GIT_TIMEOUT` Sekunden, `GitTimeout` (check endet dann mit 2)."""
    found = {path: {"+": [], "-": []} for path in paths}
    for path in paths:
        if path in untracked:
            try:
                found[path]["+"] = (read_file(Path(top) / path) or "").splitlines()
            except Unreadable:
                pass
    tracked = [path for path in paths if path not in untracked]
    for start in range(0, len(tracked), DIFF_CHUNK):
        chunk = tracked[start:start + DIFF_CHUNK]
        heads = {f"diff --git {_git_quoted('a/' + p)} {_git_quoted('b/' + p)}": p for p in chunk}
        try:
            result = _git(top, "-c", "core.quotePath=false", "diff", "--no-color", "--no-ext-diff", "--no-textconv",
                          "--no-renames", "--src-prefix=a/", "--dst-prefix=b/", "-U0", *revs, "--", *chunk)
        except NoGit as error:
            raise DiffFailed(str(error)) from error
        if result.returncode != 0:
            raise DiffFailed(_git_error(result))
        current, in_hunk = None, False
        for line in result.stdout.split("\n"):
            if line.startswith("diff --git "):
                current, in_hunk = heads.get(line), False
            elif line.startswith("@@"):
                in_hunk = True
            elif in_hunk and current and line[:1] in ("+", "-"):
                found[current][line[0]].append(line[1:])
    return {path: {sign: [" ".join(line.split()) for line in lines] for sign, lines in signs.items()}
            for path, signs in found.items()}


def _ledger_at(top, rev):
    """Wie `_read_ledger`, aber aus `<rev>^{commit}:docs/big-decisions.md` (für einen Bereich ohne
    Arbeitsbaum; ein annotiertes Tag zählt als sein Commit). Ob sie dort steht, sagt der Exit-Code
    von `git cat-file -e` — nicht der Wortlaut von Git; fehlt sie in `rev`, ist das ([], None, False).
    Dann liest `git cat-file blob` sie, dekodiert mit `decode_text`; scheitert das, ist sie nicht
    lesbar. Meldungen nennen „docs/big-decisions.md in <rev>“, `rev` wie angegeben."""
    shown_as = f"{LEDGER_SHOWN} in {rev}"
    spec = f"{rev}^{{commit}}:{LEDGER_SHOWN}"
    if _git(top, "cat-file", "-e", spec).returncode != 0:
        return [], None, False
    blob = _git(top, "cat-file", "blob", spec, raw=True)
    if blob.returncode != 0:
        return [], f"{shown_as} nicht lesbar ({_git_error(blob)}){SKIPPED}", True
    return _ledger_from_text(decode_text(blob.stdout), shown_as)


def check(root, rev):
    """Teure Änderungen im Bereich `rev` ohne freigegebenen Eintrag in `docs/big-decisions.md`;
    (exit, text). Braucht keine Sitzung. Die Stellen kommen aus `changed_files`; die Freigaben bei
    einer einzelnen Revision aus der Arbeitskopie, bei einem Bereich ohne Arbeitsbaum aus der Ablage
    in dessen End-Revision. Exit 1 bei mindestens einer Stelle, sonst 0; Exit 2 bei fehlender oder
    kaputter Reference („ungeprüft — references/reversibility.md fehlt“), ohne Git („ungeprüft —
    kein Git“), wenn Git nicht in `GIT_TIMEOUT` Sekunden antwortet („ungeprüft — git antwortet
    nicht in <n> s“) oder bei einem Bereich, den Git nicht kennt. Jede Ausgabe außer der ohne
    Reference endet mit `tail_line` („ungeprüft: data-delete, …; teilweise: api, migration,
    dependency, permissions“)."""
    categories, problem = load_categories(REFERENCE)
    if problem:
        return 2, f"ungeprüft — {problem}"
    tail = tail_line(categories)
    changes, problem = changed_files(Path(root), rev)
    if problem:
        return 2, f"ungeprüft — {problem}\n{tail}"
    try:
        return _check(changes, rev.strip(), categories, tail)
    except GitTimeout:
        return 2, f"ungeprüft — {timeout_problem()}\n{tail}"
    except DiffFailed as error:
        return 2, f"ungeprüft — git diff für #-Freigaben gescheitert ({error})\n{tail}"
    except NoGit:
        return 2, f"ungeprüft — kein Git\n{tail}"


def _check(changes, rev, categories, tail):
    """Der Vergleich zu `check`, nachdem die Stellen feststehen; wirft `GitTimeout` und `NoGit`."""
    top, end = changes.top, changes.end
    if end is None:
        blocks, ledger_note, exists = _read_ledger(top)
        where = LEDGER_SHOWN
    else:
        blocks, ledger_note, exists = _ledger_at(top, end)
        where = f"{LEDGER_SHOWN} in {end}"
    notes = list(changes.notes) + ([ledger_note] if ledger_note else [])
    unread = None                                       # Grund, warum keine Freigabe gelesen wurde
    if ledger_note:
        unread = ledger_note[:-len(SKIPPED)] if ledger_note.endswith(SKIPPED) else ledger_note
    elif not exists:
        unread = f"{LEDGER_SHOWN} fehlt" + (f" in {end}" if end is not None else "")
        notes.append(f"{unread} — keine Freigaben.")
    entries = []
    for block in blocks:
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
    lines = changed_lines(top, changes.revs, wanted, changes.untracked) if wanted else {}
    found, with_category = [], 0
    for path in changes:
        hit = candidates[path]
        with_category += bool(hit)
        for category, matching in hit:
            why = []
            for block, _, pattern, text in matching:
                label = f"{block['id']} {block['key']}"
                if block["status"] != "freigegeben":
                    why.append(f"{label} steht {block['status']}")
                    continue
                sign = text[:1] if text.startswith("-") else "+"
                needle = text[1:] if sign == "-" else text
                if not text or any(needle in line for line in lines.get(path, {}).get(sign, ())):
                    break
                where_lines = "entfernten" if sign == "-" else "hinzugefügten"
                why.append(f"{label} freigegeben, aber „{needle}“ in keiner {where_lines} Zeile")
            else:
                reason = "; ".join(why) or (f"Freigaben nicht gelesen ({unread})" if unread else
                                            f"kein Eintrag mit passendem Schlüssel in {where}")
                found.append(f"- {path} — {category.name} ({category.grade}): {category.meaning} — {reason}")

    source = f"Freigaben aus {end}; " if end is not None else ""
    summary_line = (f"Stellen ohne Freigabe: {len(found)}" if found else "Keine Stelle ohne Freigabe") + (
        f" (Bereich {rev}; {source}{len(changes)} Dateien im Diff, {with_category} mit Kategorie)")
    return (1 if found else 0), "\n".join(notes + [summary_line] + found + [tail])


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


# --- brief: Auftrag an einen Subagenten -------------------------------------------------

def brief_path(root, session, number):
    return log_path(root, session).parent / f"brief-{number}.md"


def _fence_step(fence, line):
    """(Zaun nach `line`, ob `line` außerhalb eines Codezauns steht und selbst keiner ist). `fence` ist
    der offene Zaun (```` ``` ```` oder `~~~`, mindestens drei) oder None; geschlossen wird er von einem
    Zaun derselben Art, mindestens gleicher Länge und ohne Info-Text. Ein ```` ``` ```` mit `` ` `` im
    Info-Text ist kein Zaun. Für `check_brief` und `_section_lines`."""
    marker = _FENCE_RE.match(line)
    if fence:
        if marker and marker.group("fence")[0] == fence[0] and len(marker.group("fence")) >= len(fence) \
                and not marker.group("info").strip():
            return None, False
        return fence, False
    if marker and not (marker.group("fence")[0] == "`" and "`" in marker.group("info")):
        return marker.group("fence"), False
    return None, True


def _section_lines(path, heading):
    """(Zeilen, Problem) des Abschnitts `heading` (`## …`) in `path`, bei jedem Aufruf neu gelesen; der
    Abschnitt beginnt an der ersten Überschrift `heading` außerhalb eines Codezauns (ein Beispiel im Zaun
    zählt nicht). Zeilen als (Nummer, Zeile, außerhalb eines Codezauns) bis zur nächsten Überschrift
    außerhalb eines Codezauns (`_fence_step`). Problem: None, oder „<datei> fehlt“, „<datei> nicht lesbar (<Ursache>)“,
    „<datei>: kein Abschnitt „<heading>““; dann sind die Zeilen None. Für `load_wordlist` und
    `load_subagent_sentence`."""
    where = reference_shown(path)
    try:
        text = read_file(path)
    except Unreadable as error:
        return None, unreadable_problem(error, where, "")
    if text is None:
        return None, f"{where} fehlt"
    lines = text.splitlines()
    start, fence = None, None
    for i, line in enumerate(lines):
        fence, plain = _fence_step(fence, line)
        if plain and line.strip() == heading:
            start = i
            break
    if start is None:
        return None, f"{where}: kein Abschnitt „{heading}“"
    section, fence = [], None
    for number, line in enumerate(lines[start + 1:], start + 2):
        fence, plain = _fence_step(fence, line)
        if plain and _HEADING_RE.match(line):
            break
        section.append((number, line, plain))
    return section, None


def load_wordlist(path):
    """(Wörter, Problem) aus dem Abschnitt `## Wortliste` in `references/brief.md` (`path`), bei jedem
    Aufruf neu gelesen (`_section_lines`). Wörter: Tupel in Dateireihenfolge, klein, Leerraum
    zusammengezogen. Im Abschnitt steht bis zur nächsten Überschrift nur ein Listenpunkt je Zeile (`- `
    oder `* `, dann ein Wort oder eine Wortfolge in Backticks) oder eine Leerzeile. Problem: None, oder
    eine Zeile Grund (fehlt, nicht lesbar, kein Abschnitt, eine Zeile anderer Form — auch Prosa, `+ `
    oder ein Codezaun — mit ihrer Nummer, doppelt, keine Listenpunkte); dann (). Nichts wird still
    verworfen."""
    where = reference_shown(path)
    section, problem = _section_lines(path, WORDLIST_HEADING)
    if problem:
        return (), problem
    words = []
    for number, line, _ in section:
        stripped = line.strip()
        if not stripped:
            continue
        match = re.fullmatch(r"[-*]\s+`([^`]+)`", stripped)
        word = " ".join(match.group(1).split()).lower() if match else ""
        if not word:
            if re.match(r"(?:[-*+]|\d+[.)])(?:\s|$)", stripped):
                return (), f"{where}:{number}: Listenpunkt „{stripped}“ — erwartet „- `<wort>`“ oder „* `<wort>`“"
            return (), (f"{where}:{number}: „{stripped}“ ist kein Listenpunkt — im Abschnitt "
                        f"„{WORDLIST_HEADING}“ stehen nur Listenpunkte „- `<wort>`“")
        if word in words:
            return (), f"{where}:{number}: `{word}` steht doppelt"
        words.append(word)
    if not words:
        return (), f"{where}: Abschnitt „{WORDLIST_HEADING}“ ohne Listenpunkte"
    return tuple(words), None


def load_subagent_sentence(path):
    """(Satz, Problem) aus dem Abschnitt `## Der Satz für Subagenten` in `references/brief.md` (`path`),
    bei jedem Aufruf neu gelesen (`_section_lines`) — der einen Quelle des Satzes aus Spec 28, Ablauf 5.
    Der Satz ist das eine Zitat bis zur nächsten Überschrift: Zeilen mit `> ` ohne Leerzeile dazwischen,
    zu einer Zeile zusammengezogen; Prosa davor und danach (nach einer Leerzeile) zählt nicht, Zeilen in
    einem Codezaun sind kein Zitat. Problem nach Ursache, dann ist der Satz None: „references/brief.md
    fehlt“, „references/brief.md nicht lesbar (<Ursache>)“, „Satz für Subagenten fehlt in
    references/brief.md (<grund>)“ (kein Abschnitt, kein oder leeres Zitat), „Satz für Subagenten
    mehrfach in references/brief.md (Zeile <n> …)“, „references/brief.md:<n>: … ohne „>““ für eine
    nicht-leere Zeile ohne `>` direkt im Zitat — sie würde den Satz sonst still kürzen. Beginnt diese
    Zeile mit ```` ``` ````, `~~~`, `- `, `* `, `+ `, einer Ziffer mit `. `, `#` oder `<!--`
    (`_QUOTE_END_RE`), endet das Zitat dort wie in Markdown; nur andere Textzeilen sind ein Problem."""
    where = reference_shown(path)
    missing = f"Satz für Subagenten fehlt in {where}"
    section, problem = _section_lines(path, SENTENCE_HEADING)
    if problem:
        return None, (f"{missing} (kein Abschnitt „{SENTENCE_HEADING}“)"
                      if problem.startswith(f"{where}: kein Abschnitt") else problem)
    quotes, inside = [], False
    for number, line, plain in section:
        quote = _QUOTE_RE.match(line) if plain else None
        if quote and not inside:
            if quotes:
                return None, f"Satz für Subagenten mehrfach in {where} (Zeile {number}: ein zweites Zitat)"
            quotes.append([])
        if quote:
            quotes[-1].append(quote.group("text"))
        elif inside and line.strip() and not _QUOTE_END_RE.match(line):
            return None, (f"{where}:{number}: „{line.strip()}“ setzt das Zitat ohne „>“ fort — jede Zeile "
                          "des Satzes beginnt mit „> “")
        inside = bool(quote)
    sentence = " ".join(" ".join(quotes[0]).split()) if quotes else ""
    if not sentence:
        return None, f"{missing} (kein Zitat „> …“ im Abschnitt „{SENTENCE_HEADING}“)"
    return sentence, None


def klasse_label(entry):
    """Anzeige der Klasse eines Protokolleintrags: `klein`, `Annahme`, `groß` — für summary und brief."""
    return {"annahme": "Annahme", "gross": "groß"}.get(entry["klasse"], "klein")


def _decided_line(entry):
    return f"- [{klasse_label(entry)}] {entry['frage']} → {entry['entscheidung']} ({entry['beleg']})"


_REQUEST_SOURCE_RE = re.compile(r"^Auftrag: „.*“$")


def _block_line(did, question, group, unknown):
    """(entschieden, Zeile) für die große Frage `did`/`question` mit ihren Blöcken `group` aus der Ablage.
    `freigegeben` (mit Antwort; bei Quelle „Auftrag: „…““ statt „wie im Auftrag“ das Zitat) und
    `abgelehnt` sind entschieden; `offen` und jeder unbekannte Status — Ablage fehlt oder übersprungen
    (`unknown`), Block fehlt, steht doppelt oder trägt einen anderen Status — stehen unter Feste Vorgaben
    als „nicht entscheiden, nicht darauf aufbauen“ (Spec 28, Ablauf 4)."""
    status = group[0]["status"] if len(group) == 1 and not unknown else None
    answer = line_value(group[0]["answer"]) if status else NONE
    if status == "freigegeben":
        source = line_value(group[0]["source"])
        if answer in (NONE, ANSWER_BY_REQUEST) and _REQUEST_SOURCE_RE.match(source):
            answer = source
        return True, f"- [groß] {question} → {did} freigegeben: {answer} ({LEDGER_SHOWN})"
    if status == "abgelehnt":
        told = f": {answer}" if answer not in (NONE, "abgelehnt") else ""
        return True, f"- [groß] {question} → {did} abgelehnt{told} ({LEDGER_SHOWN})"
    if status == "offen":
        return False, f"- {did} offen: {question} — {NOT_DECIDED}"
    if unknown:
        why = unknown
    elif len(group) > 1:
        why = f"{did} doppelt in {LEDGER_SHOWN}"
    elif group:
        why = f"Status „{status}“ in {LEDGER_SHOWN}"
    else:
        why = f"nicht in {LEDGER_SHOWN}"
    return False, f"- {did} Status unbekannt ({why}): {question} — {NOT_DECIDED}"


def _entry_lines(root, entries, topic):
    """(Schon entschieden, Feste Vorgaben zu großen Fragen, Hinweise, Zahl der Zeilen zur nicht gelesenen
    Ablage am Anfang der Feste Vorgaben) für das Thema `topic`: zuerst die
    Einträge `entries` der Sitzung in Protokollreihenfolge, dann jeder weitere Block der Ablage, dessen
    Thema nach `_norm` gleich `topic` ist — die Ablage gehört dem Repo, eine offene Frage aus einer
    anderen Sitzung bindet den Subagenten genauso. Kleine und Annahmen sind entschieden
    (`_decided_line`); eine große Frage ist `D-<n>` mit gleicher Frage (nach einer verworfenen Ablage
    kehren Nummern wieder) und steht nur einmal da, eingeordnet von `_block_line`. Fehlt die Ablage,
    überspringt die Konsumenten-Regel sie (dann ein Hinweis), ist der Status großer Protokolleinträge
    unbekannt. Ist die Ablage unlesbar oder übersprungen, beginnen die Feste Vorgaben mit „- Ablage
    docs/big-decisions.md nicht gelesen (<Grund>) — offene große Fragen zum Thema möglich; nichts
    entscheiden, was teuer umkehrbar ist, sondern zurückgeben“ (`LEDGER_UNREAD`); fehlt sie, nicht. Ein
    offener Block ohne Thema (Zeile fehlt oder leer) steht als „- D-<n> offen, ohne Thema: <frage> —
    prüfen, ob sie das Thema betrifft“ darunter; ein abweichendes Thema bleibt draußen — ob es passt,
    ist G1."""
    blocks, problem, exists = _read_ledger(root)
    notes, unknown, unread = [], None, []
    if problem:
        notes.append(f"Hinweis: {problem}")
        unknown = f"{LEDGER_SHOWN} übersprungen"
        why = problem.removeprefix(f"{LEDGER_SHOWN} ").removesuffix(SKIPPED)
        unread.append(f"- Ablage {LEDGER_SHOWN} nicht gelesen ({why}) — {LEDGER_UNREAD}")
    elif not exists:
        unknown = f"{LEDGER_SHOWN} fehlt"
    groups = {}
    for block in blocks:
        groups.setdefault((block["id"], cell(block["question"])), []).append(block)
    decided, pending, done = [], [], set()
    for entry in entries:
        if entry["klasse"] != "gross":
            decided.append(_decided_line(entry))
            continue
        key = (entry["entscheidung"], entry["frage"])
        if key in done:
            continue
        done.add(key)
        ok, line = _block_line(*key, groups.get(key, []), unknown)
        (decided if ok else pending).append(line)
    wanted = _norm(topic)
    for key, group in groups.items():
        if key in done:
            continue
        if any(_norm(b["topic"]) == wanted for b in group):
            done.add(key)
            ok, line = _block_line(*key, group, None)
            (decided if ok else pending).append(line)
        elif any(b["status"] == "offen" and line_value(b["topic"]) == NONE for b in group):
            done.add(key)
            pending.append(f"- {key[0]} offen, ohne Thema: {key[1]} — {NO_TOPIC_CHECK}")
    return decided, unread + pending, notes, len(unread)


def _comment_safe(text):
    """Nutzertext für den generated-Teil einer Kopfzeile: nur `-->` und `--!>`, die den HTML-Kommentar
    vorzeitig schlössen, werden unschädlich (`-- >`, `--! >`); alles andere bleibt, wie es ist — auch
    `--`, damit der Befehl in der Kopfzeile wörtlich kopierbar bleibt. Nur bei einem Thema mit `-->`
    sucht der kopierte Befehl ein anderes Thema."""
    return text.replace("--!>", "--! >").replace("-->", "-- >")


def _write_new(path, text):
    """Legt `path` exklusiv an und schreibt `text` über denselben Deskriptor (`utf-8`, `\\n`); False,
    wenn die Datei schon steht. Bricht das Schreiben ab — Fehler oder Unterbrechung —, wird die Datei
    entfernt und der Fehler weitergereicht: keine leere oder halbe brief-<n>.md bleibt liegen."""
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o666)
    except FileExistsError:
        return False
    try:
        try:
            handle = os.fdopen(fd, "w", encoding="utf-8", newline="")
        except BaseException:
            os.close(fd)
            raise
        with handle:
            handle.write(text)
    except BaseException:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return True


def write_brief(root, session, topic, home):
    """(exit, meldung): schreibt `.skills/cache/decide/<session>/brief-<n>.md` mit Kopfzeile und den
    sechs Feldern aus `references/brief.md` als `## <Feld>`. Das Skript füllt Feste Vorgaben (zuerst,
    ist die Ablage unlesbar oder übersprungen, „- Ablage docs/big-decisions.md nicht gelesen (<Grund>) —
    …“; dann jede offene große Frage des Themas als „- D-<n> offen: <frage> — nicht entscheiden, nicht
    darauf aufbauen“, jede, deren Status die Ablage nicht sagt, als „Status unbekannt“ und jeden offenen
    Block ohne Thema als „- D-<n> offen, ohne Thema: <frage> — prüfen, ob sie das Thema betrifft“; dann
    jede Regel aus `read_rules` mit Datei und Zeile), Schon entschieden (Einträge der Sitzung, deren Thema nach `_norm`
    gleich `topic` ist, und freigegebene oder abgelehnte Blöcke des Themas aus der Ablage, aus jeder
    Sitzung — `_entry_lines`; `—`, wenn keiner) und Rückgabe (`RETURN_FORM` und der Satz aus
    `load_subagent_sentence`); Frage, Anlass und Wo nachsehen bleiben leer. Die Kopfzeile nennt den
    Befehl wörtlich, bei einem Thema mit führendem `-` als `--topic=<thema>`, damit argparse es nimmt;
    nur `-->` im Thema wird dort `-- >` (`_comment_safe`). Unlesbare Regeldateien meldet es wie add und schreibt trotzdem. Bleiben für die drei
    leeren Felder keine `BRIEF_EMPTY` Zeilen unter `BRIEF_LIMIT`, sagt ein Hinweis das mit den
    verbleibenden Zeilen und ihrer Herkunft (Regeln, Schon entschieden, offene Fragen; Exit bleibt 0) und
    rät, Regeln oder ältere Einträge unter Schon entschieden zu kürzen, nie die Zeilen zu offenen Fragen.
    Fehlt der Satz für Subagenten in `references/brief.md` oder parst er nicht: Exit 2 „ungeprüft — …“
    mit der Ursache aus `load_subagent_sentence`, nichts geschrieben. Ein unlesbares Protokoll oder eines ohne
    passende Kopfzeile: Exit 1, kein Auftrag — Schon entschieden wäre sonst still leer. Die Nummer ist
    die höchste vorhandene plus eins, exklusiv angelegt und über denselben Deskriptor geschrieben
    (`_write_new`; zwei gleichzeitige Aufrufe bekommen zwei Nummern, ein Abbruch hinterlässt keine
    Datei)."""
    root, home = Path(root), Path(home)
    topic = " ".join((topic or "").split())
    if not topic:
        return 1, "brief: es fehlt --topic; kein Auftrag geschrieben."
    sentence, problem = load_subagent_sentence(BRIEF_REFERENCE)
    if problem:
        return 2, f"ungeprüft — {problem}; kein Auftrag geschrieben."
    try:
        text = read_log(root, session)
    except Unreadable as error:
        return 1, unreadable_problem(error, log_shown(root, session), "; kein Auftrag geschrieben.")
    entries = []
    if text is not None:
        problem = header_problem(text, shown(log_path(root, session), root), "kein Auftrag geschrieben")
        if problem:
            return 1, problem
        entries = [e for e in parse_rows(text) if _norm(e["thema"]) == _norm(topic)]
    rules, _, notes = read_rules(root, home)
    decided, pending, ledger_notes, unread = _entry_lines(root, entries, topic)

    body = [f"<!-- skill: {SKILL} | schema: {SCHEMA} | generated: python decide_log.py brief "
            f"--topic{'=' if topic.startswith('-') else ' '}{_comment_safe(shlex.quote(topic))} -->",
            "", "## Frage", "", "## Anlass", "",
            "## Feste Vorgaben", *pending, *[f"- Regel {rule_label(r)} ({r.source}:{r.line})" for r in rules], "",
            "## Schon entschieden", *(decided or [NONE]), "",
            "## Wo nachsehen", "",
            "## Rückgabe", RETURN_FORM, sentence]
    content = "\n".join(body) + "\n"
    folder = log_path(root, session).parent
    existed = cache_exists(root)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        taken = [int(m.group(1)) for p in folder.iterdir() if (m := re.fullmatch(r"brief-(\d+)\.md", p.name))]
        number = max(taken, default=0) + 1
        while not _write_new(brief_path(root, session, number), content):
            number += 1
    except OSError as error:
        return 1, (f"Auftrag unter {shown(folder, root)} nicht schreibbar ({error.strerror or error}); "
                   "kein Auftrag geschrieben.")
    path_shown = shown(brief_path(root, session, number), root)
    count = sum(1 for line in content.splitlines()[1:] if line.strip())
    open_count = len(pending) - unread
    lines = notes + ledger_notes + [
        f"Auftrag geschrieben: {path_shown} — Schon entschieden: {len(decided)}, Feste Vorgaben: "
        f"{len(rules)} Regel{'' if len(rules) == 1 else 'n'}"
        + (f", {open_count} große Frage{'' if open_count == 1 else 'n'} ohne Freigabe" if open_count else "")
        + ".",
        f"Frage, Anlass und Wo nachsehen ausfüllen (Feste Vorgaben ergänzen), dann brief --check {path_shown}."]
    if count > BRIEF_LIMIT - BRIEF_EMPTY:
        lines.append(f"Hinweis: Auftrag hat schon {count} Zeilen ohne Kopf, höchstens {BRIEF_LIMIT} (davon "
                     f"{len(rules)} Regel{'' if len(rules) == 1 else 'n'}, {len(decided)} unter Schon entschieden, "
                     f"{len(pending)} zu offenen Fragen); für Frage, Anlass und Wo nachsehen bleiben "
                     f"{max(BRIEF_LIMIT - count, 0)} Zeilen, mindestens {BRIEF_EMPTY} nötig — Regeln oder ältere "
                     "Einträge unter Schon entschieden kürzen, die Zeilen zu offenen Fragen nie")
    notice = unversioned_notice(root, existed, True)
    if notice:
        lines.append(notice)
    return 0, "\n".join(lines)


def _word_re(word):
    """Ein Wort der Wortliste als ganzes Wort: davor und danach kein Buchstabe und keine Ziffer — `_`
    grenzt ab wie Leerraum (`_sollte_` trifft); Groß/klein egal, Leerraum in Wortfolgen beliebig."""
    return re.compile(r"(?<![^\W_])" + r"\s+".join(re.escape(w) for w in word.split()) + r"(?![^\W_])",
                      re.IGNORECASE)


def _resolve_brief(path, root):
    """Ein relativer Pfad, der im Arbeitsverzeichnis nicht steht, gilt relativ zur Repo-Wurzel `root` —
    so nennt ihn `brief --topic`. Ist `root` None, wird sie erst dann bestimmt (`repo_root`)."""
    if path.is_absolute() or path.exists():
        return path
    candidate = (repo_root(Path.cwd()) if root is None else Path(root)) / path
    return candidate if candidate.exists() else path


def check_brief(path):
    """(exit, meldung) für einen Auftrag: Exit 1 mit je Befund einer Zeile — mehr als `BRIEF_LIMIT`
    Zeilen mit Text ohne Kopfzeile (Leerzeilen zählen nicht), eine Überschrift außer den sechs
    Feldern, Text vor dem ersten Feld, ein fehlendes oder doppeltes Feld, Wörter aus
    `load_wordlist(BRIEF_REFERENCE)` in der Frage (`_word_re`) —, sonst 0. Zeilen in einem Codezaun
    (```` ``` ```` oder `~~~`, bis zum schließenden Zaun derselben Art und mindestens gleicher Länge)
    sind Text des Feldes, keine Überschriften; nur außerhalb eines Zauns beginnt eine Überschrift ein
    Feld. Ein relativer Pfad, der im Arbeitsverzeichnis fehlt, wird gegen die Repo-Wurzel aufgelöst
    (`_resolve_brief`). Den Satz für Subagenten prüft es bewusst nicht. Exit 2 „ungeprüft — …“, wenn
    die Wortliste nicht gelesen werden kann, die Datei fehlt oder nicht lesbar ist, oder die
    Konsumenten-Regel sie überspringt (Kopfzeile von decide fehlt, `schema` höher als 1)."""
    return _check_brief(path, None)


def _check_brief(path, root):
    """`check_brief` mit der Repo-Wurzel `root`, die `main` schon kennt (None: erst bei Bedarf bestimmt)."""
    given = Path(path)
    words, problem = load_wordlist(BRIEF_REFERENCE)
    if problem:
        return 2, f"ungeprüft — {problem}"
    path = _resolve_brief(given, root)
    where = f"Auftrag {given}"
    try:
        text = read_file(path)
    except Unreadable as error:
        return 2, "ungeprüft — " + unreadable_problem(error, where, "")
    if text is None:
        return 2, f"ungeprüft — {where} fehlt"
    problem = header_problem(text, str(given))
    if problem:
        return 2, f"ungeprüft — {problem}"

    lines = text.splitlines()
    head = next(i for i, line in enumerate(lines) if line.strip())
    findings, seen, question = [], [], []
    count, current, outside, fence = 0, None, False, None
    for number, line in enumerate(lines[head + 1:], head + 2):
        if not line.strip():
            continue
        count += 1
        fence, plain = _fence_step(fence, line)
        heading = _HEADING_RE.match(line) if plain else None
        if heading:
            name = " ".join(heading.group("name").split())
            if name not in BRIEF_FIELDS:
                findings.append(f"- Feld „{name}“ (Zeile {number}) gehört nicht in den Auftrag — erlaubt sind nur "
                                f"{', '.join(BRIEF_FIELDS)}")
            elif name in seen:
                findings.append(f"- Feld „{name}“ steht doppelt (Zeile {number})")
            else:
                seen.append(name)
            current = name
        elif current is None and not outside:
            outside = True
            findings.append(f"- Text vor dem ersten Feld (Zeile {number}) — jede Zeile gehört unter eines der "
                            "sechs Felder")
        elif current == "Frage":
            question.append(line)
    if count > BRIEF_LIMIT:
        findings.insert(0, f"- {count} Zeilen ohne Kopf, höchstens {BRIEF_LIMIT} (Leerzeilen zählen nicht)")
    missing = [name for name in BRIEF_FIELDS if name not in seen]
    if missing:
        findings.append(f"- es fehlt: {', '.join(missing)}")
    asked = " ".join(question)
    hits = [word for word in words if _word_re(word).search(asked)]
    if hits:
        findings.append(f"- Frage wertet: {', '.join(f'„{w}“' for w in hits)} (Wortliste "
                        f"{reference_shown(BRIEF_REFERENCE)}) — neutral fragen")
    if findings:
        return 1, "\n".join([f"{where}: {len(findings)} Befund{'' if len(findings) == 1 else 'e'}"] + findings)
    return 0, (f"{where}: {count} Zeilen, sechs Felder, kein Wort der Wortliste in der Frage. "
               "Andere Wertungen prüft brief --check nicht.")


# --- summary und rules ------------------------------------------------------------------

def summary(root, session, home):
    """(exit, text): Einträge der Sitzung ohne kleine Einträge mit Thema einer Regel
    `nie fragen`; bei mehr als zehn die zehn jüngsten und der Pfad des Protokolls."""
    root = Path(root)
    entries, problem = log_entries(root, session)
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
    chk = sub.add_parser("check", help="teure Änderungen im Diff ohne Freigabe")
    chk.add_argument("--range", dest="rev", required=True, metavar="<rev>|<a>..<b>")
    brf = sub.add_parser("brief", parents=[common], help="Auftrag an einen Subagenten schreiben oder prüfen")
    what = brf.add_mutually_exclusive_group(required=True)
    what.add_argument("--topic", help="Auftrag zu diesem Thema schreiben (braucht eine Sitzung)")
    what.add_argument("--check", metavar="<datei>", help="Auftrag vor dem Dispatch prüfen")
    return parser


def main(argv):
    """Einstieg; `argv` ohne Programmnamen (None: `sys.argv[1:]`). Gibt den Exit-Code zurück."""
    argv = sys.argv[1:] if argv is None else list(argv)
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
        code, message = check(root, args.rev)
    elif args.action == "brief" and args.check is not None:
        code, message = _check_brief(Path(args.check), root)
    else:
        session = session_id(args.session)
        if not session:
            code, message = 1, ("Keine Sitzung: CLAUDE_CODE_SESSION_ID ist nicht gesetzt — "
                                "--session <id> angeben; nichts geschrieben.")
        elif not valid_session(session):
            code, message = 1, f"Sitzung „{session}“ ungültig (kein / oder \\, nicht . oder ..) — --session <id> angeben."
        elif args.action == "summary":
            code, message = summary(root, session, home)
        elif args.action == "brief":
            code, message = write_brief(root, session, args.topic, home)
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
    # check und brief --check: Stellen und Befunde sind ein Bericht
    report = code == 0 or (code == 1 and (args.action == "check"
                                          or (args.action == "brief" and args.check is not None)))
    print(message, file=sys.stdout if report else sys.stderr)
    if warning:
        print(warning, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main(None))
