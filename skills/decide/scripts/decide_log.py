#!/usr/bin/env python3
"""Protokoll eigener Entscheidungen für decide (Spec 28). Tier 1, nur Stdlib.

    decide_log.py rules                                     wirksame Regeln mit Datei
    decide_log.py add --class klein --topic T --question F --decision W --evidence BELEG
    decide_log.py summary                                   Einträge der laufenden Sitzung

Aufruf: `python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py"`. Repo-Wurzel ist
`git rev-parse --show-toplevel`, sonst das Arbeitsverzeichnis; `~` ist `HOME`. Die Sitzung
ist `--session`, sonst `CLAUDE_CODE_SESSION_ID`; fehlen beide, enden `add` und `summary`
mit Exit 1 und nennen `--session`.

Protokoll `.skills/cache/decide/<session>/log.md`: Kopfzeile, dann die Tabelle
`| zeit | thema | klasse | frage | entscheidung | beleg | regel |` mit `klasse` aus `klein`,
`annahme` (Belegzeile „nichts gefunden"), `gross`. `|` in Werten wird `¦`. Ein leeres
Protokoll gilt als fehlend. Unter der Sperrdatei `log.md.lock` (höchstens `LOCK_WAIT` Sekunden
Wartezeit, danach Exit 1) wird das Protokoll neu gelesen und atomar per `os.replace` ersetzt;
scheitert das Schreiben, endet `add` mit 1 und einer Zeile Grund.

Belegzeile `--evidence`: `gesucht: <ort> — Treffer: <datei:zeile>` oder
`gesucht: <ort> — nichts gefunden`. `.`, `,`, `;` und `)` am Ende fallen weg; nur der Trenner
vor dem Ergebnis wird aus ` - `, ` -- ` oder ` – ` zu ` — `. Pfade mit `./` oder `../` gelten
relativ zum Arbeitsverzeichnis, absolute Pfade (auch über Symlinks) unter der Wurzel werden
relativ zur Wurzel; andere Pfade bleiben, wie sie stehen. Danach prüft das Skript die Form.
Fehlt sie: „Keine Belegzeile", Exit 1, nichts geschrieben. Ob die Fundstelle stimmt, prüft es
nicht.

Regeln `.skills/decide/rules.md` (Repo) und `~/.skills/decide/rules.md` (Nutzer): je Zeile
`immer fragen: <thema>` oder `nie fragen: <thema>`; `#` am Zeilenanfang oder nach Leerraum
beginnt einen Kommentar. Ein Thema trifft, wenn es nach Kleinschreibung, Trimmen und
Zusammenziehen von Leerraum (`|` als `¦`, wie in der Tabelle) gleich `--topic` ist — dann gilt
die Schreibweise der Regel; enthält eines das andere ab einem Wortanfang, ist es nur ein
Hinweis. `immer fragen` geht vor `nie fragen` und stuft eine kleine Frage zur großen hoch;
`nie fragen` nimmt kleine Einträge aus `summary`. `rules` meldet je Thema einen Widerspruch.
`--option`, `--recommendation`, `--key` und `--approved-by-request` bei einer kleinen
Entscheidung meldet `add` als ignoriert (stderr, Exit bleibt 0).

Stand Task 1 des Plans: Die Ablage großer Fragen (`docs/big-decisions.md`) fehlt noch.
`add --class gross` und eine Hochstufung per `immer fragen` schreiben nichts und enden mit 1.
Das Skript meldet; es hält niemanden an. Exit 2 bei falschem Aufruf (argparse).
"""
import argparse
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

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
LOCK_WAIT = 2.0          # Sekunden, die add auf eine fremde Sperrdatei wartet
LOCK_POLL = 0.05         # Abstand der Versuche
WRITE_ATTEMPTS = 3
BIG_FLAGS = (("options", "--option"), ("recommendation", "--recommendation"), ("key", "--key"),
             ("approved_by_request", "--approved-by-request"))


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
    """(Regeln, ignorierte Zeilen als „<datei>:<zeile>: <text>“)."""
    rules, ignored = [], []
    for path, source in _rule_files(root, home):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
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
    return rules, ignored


def load_rules(root, home):
    """Alle Regeln aus Repo- und Nutzerdatei als `Rule`, Repo-Datei zuerst; fehlende Dateien
    zählen nicht, Kommentare und ungültige Zeilen fallen weg."""
    return read_rules(root, home)[0]


def _norm(topic):
    """Thema zum Vergleich, so wie es in der Tabellenzelle steht (`|` → `¦`, Leerraum
    zusammengezogen), klein geschrieben — add und summary vergleichen damit gleich."""
    return " ".join((topic or "").replace("|", "¦").split()).lower()


def _at_word_start(longer, shorter):
    """`shorter` steht in `longer` und beginnt dort einen Wort (`UI` in `UI-Texte`, nicht in `Build`)."""
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
    aufgelösten Symlinks auf beiden Seiten; sonst `path` unverändert."""
    root = Path(root)
    try:
        return Path(os.path.normpath(path)).relative_to(root).as_posix()
    except ValueError:
        pass
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError, RuntimeError):
        return path


def _norm_path(token, root):
    """Ein Token: `./…`/`../…` gegen das Arbeitsverzeichnis, ein absoluter Pfad unter der Wurzel
    relativ zur Wurzel; `:zeile` und ein Komma oder Semikolon am Ende bleiben stehen."""
    core, trail = re.match(r"^(.*?)([,;]*)$", token).groups()
    match = _LINE_SUFFIX.search(core)
    suffix = match.group(1) if match else ""
    path = core[: len(core) - len(suffix)]
    if path == ".." or path.startswith(("./", "../")):
        try:
            cwd = Path.cwd()
        except OSError:
            cwd = Path(root)
        path = _under_root(os.path.normpath(os.path.join(cwd, path)), root)
    elif os.path.isabs(path):
        path = _under_root(path, root)
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


def read_log(root, session):
    """Text des Protokolls; None, wenn es fehlt, nicht lesbar ist oder nur Leerraum enthält."""
    try:
        text = log_path(root, session).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return text if text.strip() else None


def header_problem(text, path_shown):
    """Konsumenten-Regel (docs/artifact-header.md): None, wenn die Kopfzeile passt."""
    first = next((line for line in text.splitlines() if line.strip()), "")
    match = HEADER_RE.match(first.strip())
    if not match or match.group("skill") != SKILL:
        return f"{path_shown} ohne Kopfzeile von decide — übersprungen"
    if int(match.group("schema")) > SCHEMA:
        return f"{path_shown} schema {SCHEMA} erwartet, {match.group('schema')} gefunden — übersprungen"
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
    Konsumenten-Regel; ein fehlendes Protokoll ist kein Problem."""
    text = read_log(root, session)
    if text is None:
        return [], None
    problem = header_problem(text, shown(log_path(root, session), root))
    return ([], problem) if problem else (parse_rows(text), None)


def write_atomic(path, text):
    """Schreibt über eine Nachbardatei und `os.replace`; wartet nur zwischen den Versuchen.
    Wirft OSError, wenn alle Versuche scheitern."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        for attempt in range(WRITE_ATTEMPTS):
            if attempt:
                time.sleep(0.05 * attempt)
            try:
                os.replace(tmp, path)
                return
            except OSError:
                continue
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.unlink(missing_ok=True)
    raise OSError(f"{path}: nicht schreibbar")


class LockBusy(Exception):
    """Die Sperrdatei bestand länger als `LOCK_WAIT` Sekunden; `args[0]` ist ihr Pfad."""


@contextmanager
def log_lock(path):
    """Sperrdatei `<log>.lock` neben dem Protokoll (`O_CREAT|O_EXCL`); wartet bis `LOCK_WAIT`
    Sekunden in Schritten von `LOCK_POLL`, dann `LockBusy`. Entfernt nur die eigene Sperre."""
    lock = path.with_name(path.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + LOCK_WAIT
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise LockBusy(lock) from None
            time.sleep(LOCK_POLL)
    try:
        try:
            os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        finally:
            os.close(fd)
        yield
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def append_row(root, session, values):
    """Hängt eine Zeile an; liest das Protokoll unter der Sperre unmittelbar davor neu.
    (angelegt, Problem). Wirft `LockBusy` oder OSError, wenn nicht geschrieben werden kann."""
    path = log_path(root, session)
    with log_lock(path):
        text = read_log(root, session)
        if text is not None:
            problem = header_problem(text, shown(path, root))
            if problem:
                return False, problem.replace("übersprungen", "nichts geschrieben")
        row = "| " + " | ".join(cell(values.get(c)) for c in COLUMNS) + " |"
        created = text is None
        body = f"{LOG_HEADER}\n\n{TABLE_HEAD}\n" if created else text.rstrip("\n") + "\n"
        write_atomic(path, body + row + "\n")
    return created, None


def unversioned_notice(root):
    """Hinweis, wenn `.skills/cache/` nicht ignoriert ist (Bootstrap, Spec 00 §1)."""
    try:
        out = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", ".skills/cache/decide/log.md"],
                             capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode == 1:
        return ("Hinweis: .skills/cache/ steht nicht in der .gitignore — dort ist ein unversionierter "
                "Ordner entstanden.")
    return None


# --- add --class klein ------------------------------------------------------------------

def add_small(root, session, args):
    """Kleine Entscheidung ins Protokoll; (exit, meldung).

    `args` ist ein argparse-Namespace oder ein Objekt mit den Attributen `topic`, `question`,
    `decision`, `evidence` (Strings oder None), `options` (Liste der `--option`-Werte oder None)
    und optional `home` (Path; Default `HOME`). Schreibt höchstens eine Zeile: `klein` mit
    Treffer, `annahme` mit „nichts gefunden“. Trifft eine Regel `immer fragen`, wäre die Frage
    groß — ohne zwei bis vier `--option` Exit 1; die Ablage selbst fehlt noch (Task 2).
    """
    root = Path(root)
    home = Path(getattr(args, "home", None) or home_dir())
    missing = [f"--{name}" for name in ("topic", "question", "decision")
               if not (getattr(args, name, None) or "").strip()]
    if missing:
        return 1, f"add --class klein: es fehlt {', '.join(missing)}; nichts geschrieben."
    evidence = normalize_evidence(getattr(args, "evidence", None), root)
    problem = evidence_problem(evidence)
    if problem:
        return 1, problem

    rules = load_rules(root, home)
    hits, hints = match_rules(rules, args.topic)
    always = [r for r in hits if r.kind == "immer fragen"]
    never = [r for r in hits if r.kind == "nie fragen"]
    notes = [f"Hinweis: Regel „{rule_label(r)}“ ({r.source}) ähnelt dem Thema „{args.topic.strip()}“ — "
             "nicht angewendet; trifft sie, das Thema wörtlich aus `rules` übernehmen." for r in hints]

    if always:
        rule = always[0]
        lines = []
        if never:
            lines.append(contradiction(always, never))
        options = [o for o in (getattr(args, "options", None) or []) if (o or "").strip()]
        if not 2 <= len(options) <= 4:
            lines.append(f"Regel immer fragen: {rule.topic} trifft — zwei bis vier --option nötig; "
                         "nichts geschrieben.")
        else:
            lines.append(f"Regel immer fragen: {rule.topic} trifft — die Frage ist groß; die Ablage in "
                         "docs/big-decisions.md ist noch nicht gebaut, nichts geschrieben.")
        return 1, "\n".join(notes + lines)

    topic = never[0].topic if never else args.topic.strip()
    klasse = "annahme" if evidence.endswith(" — nichts gefunden") else "klein"
    values = {"zeit": datetime.now().isoformat(timespec="seconds"), "thema": topic, "klasse": klasse,
              "frage": args.question, "entscheidung": args.decision, "beleg": evidence,
              "regel": rule_label(never[0]) if never else NONE}
    path_shown = shown(log_path(root, session), root)
    try:
        created, problem = append_row(root, session, values)
    except LockBusy as busy:
        return 1, (f"Protokoll gesperrt: {shown(busy.args[0], root)} besteht seit über {LOCK_WAIT:g} s — "
                   "läuft ein zweites add? Sonst die Sperrdatei löschen; nichts geschrieben.")
    except OSError as error:
        return 1, f"Protokoll {path_shown} nicht schreibbar ({error.strerror or error}); nichts geschrieben."
    if problem:
        return 1, problem

    what = "als Annahme (nichts gefunden)" if klasse == "annahme" else "als kleine Entscheidung"
    lines = notes + [f"Eingetragen {what}: {cell(topic)} — {cell(args.decision)} ({path_shown})"]
    if never:
        lines.append(f"Regel {rule_ref(never[0])} trifft — der Eintrag erscheint nicht in summary.")
    if created:
        lines.append(f"Protokoll angelegt: {path_shown}")
        notice = unversioned_notice(root)
        if notice:
            lines.append(notice)
    return 0, "\n".join(lines)


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
    shown_entries, hidden = [], 0
    for entry in entries:
        hits, _ = match_rules(rules, entry["thema"])
        silent = any(r.kind == "nie fragen" for r in hits) and not any(r.kind == "immer fragen" for r in hits)
        if silent and entry["klasse"] in ("klein", "annahme"):
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
        kind = {"annahme": "Annahme", "gross": "groß"}.get(e["klasse"], "klein")
        lines.append(f"- [{kind}] {e['thema']}: {e['frage']} → {e['entscheidung']} ({e['beleg']})")
    lines.append(f"Protokoll: {path_shown}")
    return 0, "\n".join(lines)


def list_rules(root, home):
    rules, ignored = read_rules(root, home)
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
    lines += [f"ignoriert: {line}" for line in ignored]
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
            code, message = 1, ("add --class gross: zwei bis vier --option, --key und --recommendation nötig; "
                                "die Ablage in docs/big-decisions.md ist noch nicht gebaut, nichts geschrieben.")
        else:
            args.home = home
            code, message = add_small(root, session, args)
            ignored = [flag for attr, flag in BIG_FLAGS if getattr(args, attr, None)]
            if code == 0 and ignored:
                warning = (f"Hinweis: {', '.join(ignored)} gehör{'en' if len(ignored) > 1 else 't'} zu "
                           "--class gross — bei einer kleinen Entscheidung ignoriert; ist die Frage groß, "
                           "mit --class gross eintragen.")
    print(message, file=sys.stdout if code == 0 else sys.stderr)
    if warning:
        print(warning, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main(None))
