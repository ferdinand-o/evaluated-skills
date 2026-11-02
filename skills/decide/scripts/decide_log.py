#!/usr/bin/env python3
"""Protokoll eigener Entscheidungen für decide (Spec 28). Tier 1, nur Stdlib.

    decide_log.py rules                                     wirksame Regeln mit Datei
    decide_log.py add --class klein --topic T --question F --decision W --evidence BELEG
    decide_log.py add --class gross --topic T --question F --key K --option "A: …" --option "B: …"
                      --recommendation E                    große Frage als Block D-<n>, offen
    decide_log.py add --class gross --topic T --question F --key K --approved-by-request "ZITAT"
                                                            große Frage, per Auftrag freigegeben
    decide_log.py resolve D-<n> --answer "…" | --reject     Antwort eintragen
    decide_log.py open                                      offene große Fragen
    decide_log.py summary                                   Einträge der laufenden Sitzung
    decide_log.py check --range <rev> | <a>..<b>            teure Änderungen im Diff ohne Freigabe

Aufruf: `python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py"`. Repo-Wurzel ist
`git rev-parse --show-toplevel`, sonst das Arbeitsverzeichnis; `~` ist `HOME`. Die Sitzung
ist `--session`, sonst `CLAUDE_CODE_SESSION_ID`; fehlen beide, enden `add` und `summary`
mit Exit 1 und nennen `--session`. `resolve`, `open` und `check` brauchen keine Sitzung: Die
Ablage gehört dem Repo, nicht einer Sitzung.

Protokoll `.skills/cache/decide/<session>/log.md`: Kopfzeile, dann die Tabelle
`| zeit | thema | klasse | frage | entscheidung | beleg | regel |` mit `klasse` aus `klein`,
`annahme` (Belegzeile „nichts gefunden"), `gross`. `|` in Werten wird `¦`. Ein leeres
Protokoll gilt als fehlend; ein vorhandenes, aber unlesbares nicht — dann enden `add` und
`summary` mit 1, und nichts wird geschrieben. Unter einer Sperre des Betriebssystems auf der
offenen Datei `log.md.lock` (`fcntl.flock` unter POSIX, `msvcrt.locking` unter Windows; sie endet
spätestens mit dem Prozess) wird das Protokoll neu gelesen und atomar per `os.replace` ersetzt.
Ist sie belegt, versucht `add` es bis `LOCK_WAIT` Sekunden lang erneut und endet dann mit 1
„Protokoll gesperrt“ und dem Pfad. Die Sperrdatei bleibt liegen und wird nie gelöscht. Fehlen
beide Module oder kann das Dateisystem nicht sperren (`ENOLCK`, `EOPNOTSUPP`, `ENOSYS`), schreibt
`add` ohne Sperre und sagt das mit der Ursache. Scheitert das Schreiben, endet `add` mit 1
und einer Zeile Grund.

Belegzeile `--evidence`: `gesucht: <ort> — Treffer: <datei:zeile>` oder
`gesucht: <ort> — nichts gefunden`. `.`, `,`, `;` und `)` am Ende fallen weg; nur der Trenner
vor dem Ergebnis wird aus ` - `, ` -- ` oder ` – ` zu ` — `. Pfade mit `./` oder `../`, `.` und `..`
gelten relativ zum Arbeitsverzeichnis; sie und absolute Pfade (auch über Symlinks) werden
relativ zur Wurzel, wenn sie darunter liegen; andere Pfade bleiben, wie sie stehen. Danach
prüft das Skript die Form. Fehlt sie: „Keine Belegzeile", Exit 1, nichts geschrieben. Ob die
Fundstelle stimmt, prüft es nicht.

Regeln `.skills/decide/rules.md` (Repo) und `~/.skills/decide/rules.md` (Nutzer): je Zeile
`immer fragen: <thema>` oder `nie fragen: <thema>`; `#` am Zeilenanfang oder nach Leerraum
beginnt einen Kommentar. Ein Thema trifft, wenn es nach Kleinschreibung, Trimmen und
Zusammenziehen von Leerraum (`|` als `¦`, wie in der Tabelle) gleich `--topic` ist — dann gilt
die Schreibweise der Regel; enthält eines das andere ab einem Wortanfang, ist es nur ein Hinweis.
Beginnt das kürzere mit einem Nicht-Wortzeichen wie `.NET`, darf es mitten im Wort beginnen, muss
dann aber am Ende stehen oder vor einem Nicht-Wortzeichen (`ASP.NET` ja, `config.network` nein).
`immer fragen` geht vor `nie fragen` und stuft eine kleine Frage zur großen hoch; `nie fragen`
nimmt kleine Einträge aus `summary`. `rules` meldet je Thema einen Widerspruch. Eine fehlende
Regeldatei bleibt still; eine vorhandene, aber unlesbare melden `add` und `rules` als „Hinweis:
Regeln <pfad> nicht lesbar (<Ursache>) — ohne diese Regeln eingeordnet“.
`--option`, `--recommendation`, `--key` und `--approved-by-request` bei einer kleinen
Entscheidung meldet `add` als ignoriert (stderr, Exit bleibt 0).

Ablage `docs/big-decisions.md` (committet): Kopfzeile, beim ersten Mal aus
`assets/big-decisions.md` angelegt und mit „angelegt: docs/big-decisions.md“ gemeldet, dann je
große Frage ein Block

    ## D-<n> · <datum> · <status>
    Frage: … / Thema: … / Schlüssel: … / Optionen: (je Zeile „- …“) / Empfehlung: …
    Antwort: … / Quelle der Antwort: …

(jedes Feld auf eigener Zeile). Status `offen`, `freigegeben`, `abgelehnt`; Quelle der Antwort
`Nutzer in Sitzung` (`resolve`), `Auftrag: „<Zitat>“` (`--approved-by-request`) oder `von Hand`.
Pflicht je Weg:
- `add --class gross`: `--topic`, `--question`, `--key`, `--recommendation`, zwei bis vier
  `--option`; Schlüssel `<kategorie>:<pfadmuster>[#<text>]` mit Kategorie aus
  `references/reversibility.md` (`load_categories`; fehlt sie oder parst sie nicht, Exit 1), oder
  `rule:<thema>`, wenn eine Regel `immer fragen` das Thema trifft — sonst Exit 1.
- `add --class gross --approved-by-request "<Zitat>"`: `--topic`, `--question`, `--key` wie oben
  (auch `rule:<thema>` — konkreter Auftrag vor Regel); Status `freigegeben`,
  „Optionen: — (Auftrag)“.
- `add --class klein`, von `immer fragen` hochgestuft: wie klein, dazu zwei bis vier `--option`
  (sonst Exit 1 „Regel immer fragen: <thema> trifft — zwei bis vier --option nötig“);
  `--decision` wird die Empfehlung, der Schlüssel `rule:<thema>`.
`nie fragen` stuft eine große Frage nie herab; die Ausgabe sagt das. Jeder große Eintrag steht
zusätzlich als Protokollzeile `gross` mit `D-<n>` unter `entscheidung`. Die Nummer ist die
höchste in der Datei plus eins. Steht schon ein Block mit gleicher Frage, gleichem Schlüssel und
gleichem Status — offen mit gleichen Optionen und gleicher Empfehlung, freigegeben mit gleicher
Quelle (derselbe Auftrag; Optionen und Empfehlung zählen dann nicht) —, legt `add` keinen zweiten
an, meldet „D-<n> steht schon“ (bei offen mit derselben Anweisung wie beim neuen Block) und ergänzt
nur eine fehlende Protokollzeile. Verglichen wird nach `line_value` auf beiden Seiten (doppelter
Leerraum aus der Datei stört nicht). Ob die Zeile fehlt (`gross` mit derselben `D-<n>` und Frage —
nach einer verworfenen Ablage kehren Nummern wieder), prüft es unter der Sperre des Protokolls.
Weichen nur Optionen oder Empfehlung ab, Exit 1 „D-<n> steht offen mit anderen Optionen“ bzw. „mit
anderer Empfehlung — von Hand ändern oder mit resolve beantworten“, nichts geschrieben. Schlüssel:
Leerraum um Kategorie und Pfadmuster fällt weg, Leerzeichen im Pfadmuster bleiben, Tab und
Zeilenumbruch darin sind ein Fehler, ebenso ein `#` ohne Text (Exit 1 „leerer Text nach #“).
Steht ein Feld in einem Block doppelt, gilt das erste — beim Lesen wie für `resolve`. `resolve`
ändert nur Blöcke mit Status `offen` (sonst Exit 1 mit Status und Quelle; von Hand bleibt es
möglich), dort Überschrift-Status, Antwort und Quelle — Felder auch leer oder mit Leerraum vor
dem `:` —, und lässt den Block stehen; schreibt es ohne Sperre, sagt es das wie `add`. `add` und
`resolve` melden „.skills/cache/ steht nicht in der .gitignore“ genau dann, wenn der Ordner bei
diesem Aufruf entstand, nicht ignoriert ist und der Aufruf etwas geschrieben hat. Die Ablage wird
unter der Sperre `.skills/cache/decide/big-decisions.md.lock` (nicht neben der Datei, `docs/` wird
committet) neu gelesen und per `write_atomic` ersetzt; gelesen wird mit `utf-8-sig` (ein BOM aus
dem Editor stört nicht; ebenso bei Protokoll, Regeln und Vorlage), geschrieben ohne BOM.
Konsumenten-Regel (docs/artifact-header.md): fehlt die Kopfzeile von decide oder ist `schema`
höher als 1, überspringen `read_ledger` und `open` die Datei sichtbar („docs/big-decisions.md
schema 1 erwartet, 2 gefunden — Freigaben übersprungen“), `add` und `resolve` schreiben nichts.

`check --range <rev>` holt die Stellen über `changed_files`. Ob `<rev>` eine einzelne Revision
oder ein Bereich ist, sagt ein Aufruf `git rev-parse <rev> --`: Genau eine positive Revision ohne
negative (`HEAD`, `HEAD~1`, `HEAD^@` bei einem Elternteil) ist eine einzelne Revision; check liest
dann `git diff <rev>` (Commits seit `<rev>` und Arbeitsbaum) und die unversionierten Dateien aus
`git ls-files --others --exclude-standard`, die Freigaben aus der Arbeitskopie von
`docs/big-decisions.md`. Sonst ist es ein Bereich ohne Arbeitsbaum (`<a>..<b>`, `A^!`, `A^-<n>`):
Arbeitsbaum und unversionierte Dateien bleiben aus, die Freigaben kommen aus der Ablage in der
End-Revision (der einen positiven), gelesen mit einem Aufruf `git cat-file blob <end>:<pfad>` und
dekodiert wie die Arbeitskopie (`decode_text`). Fehlt sie dort, gilt sie als fehlend; Meldungen zu
ihr nennen „docs/big-decisions.md in <end>“. Mehrere positive Revisionen (`<a>...<b>`, `HEAD^@`
bei einem Merge) enden mit Exit 2 „ungeprüft — Bereich mit mehreren Enden“. Git läuft über
`subprocess` mit Argumentliste, nie über eine Shell; ein Bereich mit führendem `-` ist kein
Bereich. Eine Stelle ist eine Datei im Diff (geändert, neu, gelöscht, unversioniert; Umbenennung
als Löschen plus Neuanlage). Ihre Kategorien kommen aus den
Pfadmustern der Tabelle in `references/reversibility.md` — der einen Quelle für Kategorien, Grad
und Muster. Muster mit `/` am Ende sind ein Präfix (`x/**/` wie `x/`: trifft `x/datei` und
tiefer), sonst ein Glob, den `glob_to_regex` selbst übersetzt und je Muster zwischenspeichert (`*`
und `?` ohne `/`, `**/` null oder mehr Ordner, `**` sonst alles), relativ zur Repo-Wurzel. Frei ist
eine Stelle, wenn ein Block mit Status `freigegeben` einen Schlüssel derselben Kategorie trägt,
dessen Muster die Datei trifft und — mit `#<text>` — dessen Text in einer hinzugefügten Zeile der
Datei steht (Leerraum zusammengezogen; bei einer unversionierten Datei ist jede Zeile
hinzugefügt). Ein Schlüssel mit `#` ohne Text gibt nichts frei (Hinweis). `rule:`-Schlüssel
vergleicht check nie. Fehlt die Ablage, ist sie unlesbar oder überspringt die Konsumenten-Regel
sie, sagt check das und meldet jede Stelle mit „Freigaben nicht gelesen (<Grund>)“ statt „kein
Eintrag mit passendem Schlüssel“. Ausgabe auf stdout: je Stelle
„- <datei> — <kategorie> (<grad>): <Bedeutung aus der Tabelle> — <warum nicht frei>“, als letzte
Zeile immer „ungeprüft: data-delete, unsaved-work, push, external, cost; teilweise: api,
migration, dependency, permissions“ (aus der Spalte Grad). Exit 1 bei mindestens einer Stelle,
sonst 0. Exit 2 auf stderr, nie ein Erfolg: „ungeprüft — kein Git“ (kein `git` oder kein Repo),
„ungeprüft — git antwortet nicht in <n> s“ (`GIT_TIMEOUT`, auch beim Diff einer einzelnen Datei
für `#<text>`), ein Bereich, den Git nicht kennt, und „ungeprüft — references/reversibility.md
fehlt“ bzw. der Grund, warum sie nicht parst (dann ohne Schlusszeile — sie käme aus der Datei).

Das Skript meldet; es hält niemanden an. Exit 2 bei falschem Aufruf (argparse).
"""
import argparse
import errno
import functools
import os
import re
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
    zählen nicht, Kommentare und ungültige Zeilen fallen weg; unlesbare auch — die meldet
    `rule_problems`."""
    return read_rules(root, home)[0]


def rule_problems(root, home):
    """Hinweise „Regeln <pfad> nicht lesbar (<Ursache>) — ohne diese Regeln eingeordnet“ je
    unlesbarer Regeldatei; [] wenn alle lesbar sind oder fehlen. Für add und rules."""
    return read_rules(root, home)[2]


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


def write_atomic(path, text):
    """Schreibt über eine Nachbardatei und `os.replace`; wartet nur zwischen den Versuchen.
    Scheitern alle Versuche, wirft es den letzten OSError weiter; ein Fehler beim Aufräumen der
    Nachbardatei verdeckt ihn nicht."""
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


def append_block(root, status, fields):
    """Hängt einen Block an; liest die Ablage unter ihrer Sperre unmittelbar davor neu.
    (Nummer, angelegt, Problem, ohne Sperre: None oder Ursache, schon da). Steht derselbe Block
    schon (`_same_block`), wird nichts geschrieben und „schon da“ ist True; weichen nur Optionen oder
    Empfehlung ab (`_same_question`), wird nichts geschrieben und das Problem nennt das Feld. Wirft
    `LockBusy`, `Unreadable` oder OSError."""
    path = ledger_path(root)
    with log_lock(ledger_lock_path(root)) as unlocked:
        text = read_ledger_text(root)
        if text is not None:
            problem = ledger_problem(text, "nichts geschrieben")
            if problem:
                return None, False, problem, unlocked, False
            blocks = parse_blocks(text)
            same = next((b for b in blocks if _same_block(b, status, fields)), None)
            if same:
                return same["number"], False, None, unlocked, True
            other = next((b for b in blocks if _same_question(b, status, fields)), None)
            if other:
                how = " oder mit resolve beantworten" if status == "offen" else ""
                return None, False, (f"{other['id']} steht {status} mit {_difference(other, status, fields)} — "
                                     f"von Hand ändern{how} "
                                     f"({LEDGER_SHOWN}); nichts geschrieben."), unlocked, False
        number = max((int(n) for n in BLOCK_NUMBER_RE.findall(text or "")), default=0) + 1
        created = text is None
        base = ledger_template() if created else text
        write_atomic(path, base.rstrip("\n") + "\n\n" + render_block(number, date.today().isoformat(), status, fields) + "\n")
    return number, created, None, unlocked, False


def _locked_problem(busy, root, what):
    return (f"{what} gesperrt: {shown(busy.args[0], root)} — nach {LOCK_WAIT:g} s aufgegeben "
            "(läuft ein zweites decide_log.py?); nichts geschrieben.")


def store_big(root, session, status, fields, row):
    """Legt einen Block in der Ablage an und die Protokollzeile `gross` mit `D-<n>`; (exit, Zeilen).
    Das Protokoll wird vorher geprüft, damit ein unlesbares nicht erst nach dem Block auffällt.
    Steht der Block schon (ein Wiederholungsaufruf), wird nur eine fehlende Protokollzeile ergänzt;
    ob sie fehlt, prüft `append_row` unter der Sperre des Protokolls."""
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
        number, created, problem, unlocked, existing = append_block(root, status, fields)
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
    pending = (f"Bis zur Freigabe unterbleibt der Schritt; Antwort mit `resolve {did} --answer \"…\"` "
               "oder `--reject`.")
    if existing:
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


def check_key(key, topic, rules):
    """(Schlüssel, Problem): `<kategorie>:<pfadmuster>[#<text>]` mit Kategorie aus der Tabelle in
    `references/reversibility.md` (`load_categories`, dieselbe Quelle wie check),
    oder — mit und ohne Auftrag — `rule:<thema>`, wenn eine Regel `immer fragen` dieses Thema und
    `topic` trifft, dann in der Schreibweise der Regel. Leerraum um Kategorie, Pfadmuster und Text
    fällt weg; Leerzeichen im Pfadmuster bleiben, Tab und Zeilenumbruch darin sind ein Fehler, ebenso
    ein `#` ohne Text („leerer Text nach #“) — check läse ihn sonst als „kein Text“."""
    raw = (key or "").strip()
    key = line_value(raw)
    category, sep, rest = raw.partition(":")
    category = category.strip()
    if category == RULE_CATEGORY and sep:
        hits = [r for r in match_rules(rules, rest)[0] if r.kind == "immer fragen"]
        if not hits:
            return None, (f"Schlüssel „{key}“: keine Regel „immer fragen: {rest.strip()}“ — rule:<thema> nur, "
                          "wenn eine Regel immer fragen das Thema trifft; nichts geschrieben.")
        if _norm(hits[0].topic) != _norm(topic):
            return None, (f"Schlüssel „{key}“ passt nicht zum Thema „{line_value(topic)}“ — "
                          f"rule:<thema> nimmt das Thema der Frage; nichts geschrieben.")
        return f"{RULE_CATEGORY}:{hits[0].topic}", None
    pattern, hash_, text = rest.partition("#")
    pattern = pattern.strip()
    if not sep or not pattern:
        return None, f"Schlüssel „{key}“ hat nicht die Form {KEY_FORM}; nichts geschrieben."
    if re.search(r"[^\S ]", pattern):
        return None, (f"Schlüssel „{key}“: Tab oder Zeilenumbruch im Pfadmuster „{line_value(pattern)}“ — "
                      f"Form {KEY_FORM}; nichts geschrieben.")
    if hash_ and not text.strip():
        return None, f"Schlüssel „{key}“: leerer Text nach # — Form {KEY_FORM}; nichts geschrieben."
    categories, problem = load_categories(REFERENCE)
    if problem:
        return None, f"Schlüssel „{key}“ nicht prüfbar: {problem}; nichts geschrieben."
    if category not in categories:
        return None, (f"Schlüssel „{key}“: Kategorie „{category}“ unbekannt — erlaubt: "
                      f"{', '.join(categories)}, oder rule:<thema> bei einer Regel immer fragen; "
                      "nichts geschrieben.")
    return f"{category}:{pattern}{hash_}{' '.join(text.split())}", None


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

    rules = load_rules(root, home)
    always, never, notes = rule_hits(rules, args.topic)
    notes = rule_problems(root, home) + notes
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
    `decode_text`), stderr als Text unter `LC_ALL=C` (Meldungen von Git erkennbar englisch)."""
    command = ["git", "-C", str(cwd), "--literal-pathspecs", *args]
    try:
        if not raw:
            return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=GIT_TIMEOUT)
        result = subprocess.run(command, capture_output=True, timeout=GIT_TIMEOUT, env={**os.environ, "LC_ALL": "C"})
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
    (Wurzel des Repos; None ohne Git), `untracked` (die unversionierten unter ihnen) und `end`
    (Revision, aus der check die Ablage liest; None: die Arbeitskopie)."""

    def __init__(self, files=(), top=None, untracked=(), end=None):
        super().__init__(files)
        self.top, self.untracked, self.end = top, set(untracked), end


def _revision_ends(top, rev):
    """(einzeln, Ende, Problem) aus einem Aufruf `git rev-parse <rev> --`: genau eine positive
    Revision ohne negative ist eine einzelne Revision (`HEAD`, `HEAD~1`, `HEAD^@` bei einem
    Elternteil; Ende None — mit Arbeitsbaum); sonst ein Bereich, Ende die eine positive Revision
    (`<a>..<b>`, `A^!`, `A^-<n>`). Mehrere positive (`<a>...<b>`, `HEAD^@` bei einem Merge) oder
    keine: Problem."""
    result = _git(top, "rev-parse", rev, "--")
    if result.returncode != 0:
        return False, None, f"git rev-parse {rev} fehlgeschlagen: {_git_error(result)}"
    names = [line.strip() for line in result.stdout.splitlines() if line.strip() and line.strip() != "--"]
    positive = [name for name in names if not name.startswith("^")]
    if len(positive) > 1:
        return False, None, f"Bereich mit mehreren Enden ({rev})"
    if not positive:
        return False, None, f"Bereich „{rev}“ ohne End-Revision"
    if len(names) == 1:
        return True, None, None
    return False, positive[0], None


def changed_files(root, rev):
    """(Dateien, Problem): die Stellen des Bereichs als `Changes` — eine Liste der Pfade relativ
    zur Repo-Wurzel mit `/`, sortiert, dazu `top`, `untracked` und `end`. Die eine Quelle für check.
    Einzelne Revision oder Bereich sagt `_revision_ends`. Eine einzelne Revision: `git diff <rev>`
    (Commits seit `<rev>` und Arbeitsbaum) plus `git ls-files --others --exclude-standard`, Ablage
    aus der Arbeitskopie (`end` None). Ein Bereich: nur `git diff`, `end` ist seine End-Revision.
    Problem: None, „kein Git“ (kein `git` oder kein Repo), „git antwortet nicht in <n> s“, ein
    ungültiger Bereich (leer, mit Leerraum oder führendem `-`), einer mit mehreren Enden oder der
    Grund, mit dem Git abbricht; dann sind die Dateien leer."""
    rev = (rev or "").strip()
    if not rev or rev.startswith("-") or re.search(r"\s", rev):
        return Changes(), f"Bereich „{rev}“ ungültig — erwartet <rev> oder <a>..<b>"
    try:
        top = _git(root, "rev-parse", "--show-toplevel")
        if top.returncode != 0 or not top.stdout.strip():
            return Changes(), "kein Git"
        top = Path(top.stdout.strip())
        single, end, problem = _revision_ends(top, rev)
        if problem:
            return Changes(top=top), problem
        diff = _git(top, "diff", "--name-only", "-z", "--no-renames", "--no-ext-diff", rev, "--")
        if diff.returncode != 0:
            return Changes(top=top), f"git diff {rev} fehlgeschlagen: {_git_error(diff)}"
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
    return Changes(sorted(files | untracked), top, untracked, end), None


def added_lines(top, rev, path, untracked):
    """Hinzugefügte Zeilen von `path` im Bereich, Leerraum zusammengezogen; eine unversionierte
    Datei ist ganz hinzugefügt. Kann Git den Diff nicht liefern, [] (die Datei bleibt gemeldet);
    antwortet es nicht in `GIT_TIMEOUT` Sekunden, `GitTimeout` (check endet dann mit 2)."""
    if path in untracked:
        try:
            text = read_file(Path(top) / path) or ""
        except Unreadable:
            return []
        lines = text.splitlines()
    else:
        try:
            result = _git(top, "diff", "--no-color", "--no-ext-diff", "--no-renames", "-U0", rev, "--", path)
        except NoGit:
            return []
        if result.returncode != 0:
            return []
        lines, in_hunk = [], False
        for line in result.stdout.splitlines():
            if line.startswith("diff --git "):
                in_hunk = False
            elif line.startswith("@@"):
                in_hunk = True
            elif in_hunk and line.startswith("+"):
                lines.append(line[1:])
    return [" ".join(line.split()) for line in lines]


def _ledger_at(top, rev):
    """Wie `_read_ledger`, aber aus `<rev>:docs/big-decisions.md` (für einen Bereich ohne
    Arbeitsbaum) mit einem Aufruf `git cat-file blob`, dekodiert mit `decode_text`; fehlt sie in
    `rev`, ist das ([], None, False). Meldungen nennen „docs/big-decisions.md in <rev>“."""
    shown_as = f"{LEDGER_SHOWN} in {rev}"
    blob = _git(top, "cat-file", "blob", f"{rev}:{LEDGER_SHOWN}", raw=True)
    if blob.returncode != 0:
        if re.search(r"does not exist in|exists on disk, but not in", blob.stderr):
            return [], None, False
        return [], f"{shown_as} nicht lesbar ({_git_error(blob)}){SKIPPED}", True
    return _ledger_from_text(decode_text(blob.stdout), shown_as)


def _ledger_key(key):
    """((Kategorie, Muster, Text), None) eines Schlüssels aus der Ablage, oder (None, Grund), wenn
    er die Form nicht hat — auch bei `#` ohne Text (der gäbe sonst die ganze Datei frei). Bei
    `rule:<thema>` ist alles nach `rule:` das Thema (auch mit `#`, etwa `rule:C#`); check
    überspringt solche Schlüssel."""
    category, sep, rest = (key or "").partition(":")
    category = category.strip()
    if category == RULE_CATEGORY and sep and rest.strip():
        return (category, rest.strip(), ""), None
    pattern, hash_, text = rest.partition("#")
    pattern = pattern.strip()
    if not sep or not category or not pattern:
        return None, f"hat nicht die Form {KEY_FORM}"
    if hash_ and not text.strip():
        return None, "hat leeren Text nach #"
    return (category, pattern, " ".join(text.split())), None


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
    notes = [ledger_note] if ledger_note else []
    unread = None                                       # Grund, warum keine Freigabe gelesen wurde
    if ledger_note:
        unread = ledger_note[:-len(SKIPPED)] if ledger_note.endswith(SKIPPED) else ledger_note
    elif not exists:
        unread = f"{LEDGER_SHOWN} fehlt" + (f" in {end}" if end is not None else "")
        notes.append(f"{unread} — keine Freigaben.")
    entries = []
    for block in blocks:
        parsed, why_not = _ledger_key(block["key"])
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

    found, added_cache, with_category = [], {}, 0
    for path in changes:
        hit = [c for c in categories.values() if any(pattern_matches(p, path) for p in c.patterns)]
        with_category += bool(hit)
        for category in hit:
            matching = [e for e in entries if e[1] == category.name and pattern_matches(e[2], path)]
            why = []
            for block, _, pattern, text in matching:
                label = f"{block['id']} {block['key']}"
                if block["status"] != "freigegeben":
                    why.append(f"{label} steht {block['status']}")
                    continue
                if not text:
                    break
                if path not in added_cache:
                    added_cache[path] = added_lines(top, rev, path, changes.untracked)
                if any(text in line for line in added_cache[path]):
                    break
                why.append(f"{label} freigegeben, aber „{text}“ in keiner hinzugefügten Zeile")
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

    always, never, notes = rule_hits(load_rules(root, home), args.topic)
    notes = rule_problems(root, home) + notes
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
        kind = {"annahme": "Annahme", "gross": "groß"}.get(e["klasse"], "klein")
        lines.append(f"- [{kind}] {e['thema']}: {e['frage']} → {e['entscheidung']} ({e['beleg']})")
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
    report = code == 0 or (args.action == "check" and code == 1)     # check: Stellen sind ein Bericht
    print(message, file=sys.stdout if report else sys.stderr)
    if warning:
        print(warning, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main(None))
