#!/usr/bin/env python3
"""deep-review: Paketplan, Gegenstellen und Abdeckung für `/code-review`. Tier 1: nur Stdlib.

Das Skript reviewt nichts. Es schneidet einen Bereich `BASIS..ZIEL` nach einer festen
Schnittregel in Pakete, schreibt den Plan nach `.skills/cache/deep-review/<lauf>/plan.json`
und nimmt später die Ergebnisse je Paket an (Spec 26). Zielcode wird nie importiert oder
gestartet. Git schreibt nur Objekte und Refs unter `refs/deep-review/<lauf>/` (die
Hilfscommits der Paket-Bereiche, gebaut über einen temporären Index; der Vergleich mit dem
Arbeitsbaum läuft auf einer Kopie des Index); HEAD, Index und Arbeitsbaum des Nutzers
bleiben unberührt (E6).

Stand Task 5: Lauf-ID, JSON-Schreiber, Zählung über `git diff --numstat --no-renames`
ab der Merge-Basis, Einordnung (reviewt oder `not_reviewed` mit Grund), Schnittregel,
`build_plan`, Paket-Bereiche (`make_packet_range`), `cleanup` und die Gegenstellen für
Python (`collect_python`; Zielcode nur per `ast` gelesen) und Delphi (`collect_delphi`,
Text-Scanner über `mask_pascal`), beide aus Git am ZIEL, mit `render_block` und
`write_counterparts`.
"""

from __future__ import annotations

import ast
import bisect
import contextlib
import datetime as dt
import fnmatch
import functools
import io
import json
import math
import os
import posixpath
import re
import secrets
import shlex
import shutil
import socket
import string
import subprocess
import tempfile
import time
import tokenize
import warnings
from pathlib import Path, PurePath, PurePosixPath
from typing import NamedTuple

# Grenzwerte (Spec 26, E7). Der Report nennt sie.
SPLIT_AT = 800            # bis hierher ein Paket über den Originalbereich
PACKET_SIZE = 600         # obere Paketgröße beim Teilen (kleiner von diesem Wert und split_at)
BLOCK_MAX_CHARS = 30000   # Gegenstellen-Block je Paket
MERGE_LINE_GAP = 3        # Funde derselben Datei mit höchstens diesem Abstand vereinigen
RAISE_DEPTH = 2           # raise-Stellen transitiv im selben Modul
FLAG_DEPTH = 4            # Weg eines Schlüsselwort-Arguments durch die Gegenstellen
AMBIGUOUS_MAX = 3         # mehr gleichnamige Definitionen ohne Importbezug: nicht raten
REPORT_BASE_LINES = 20    # Anti-Zeremonie: Bericht höchstens so viele Zeilen plus eine je Fund

SKILL_NAME = "deep-review"
SCHEMA_VERSION = 1
RESERVED_META = ("skill", "schema")
SCRIPT_CMD = "python skills/deep-review/scripts/review_kit.py"
CACHE_DIR = PurePosixPath(".skills/cache/deep-review")
DEFAULT_RANGE = "HEAD"    # ohne Bereich: der letzte Commit
# Dieselbe Pathspec wie subagent-dev (plan_to_tasks.py, changed_lines); `numstat` ruft git
# immer aus der Repo-Wurzel auf, `.` ist also das ganze Repo. Der Unterschied bleibt die
# Basis: subagent-dev zählt `since..HEAD` direkt gegen BASIS (aus seinem Arbeitsordner),
# hier wird ab der Merge-Basis gezählt — ist BASIS weitergelaufen, zählt subagent-dev dessen
# neuere Änderungen mit, dieser Zähler nicht.
DIFF_PATHSPEC = (".", ":(exclude).skills")
GIT_TIMEOUT = 120         # Sekunden je git-Aufruf

# Paket-Bereiche (E6): Hilfscommits nur unter REF_ROOT/<lauf>/<id>/{von,bis}, mit fester
# Identität, gebaut über einen temporären Index.
REF_ROOT = "refs/deep-review"
HELPER_NAME = "deep-review"
HELPER_EMAIL = "deep-review@localhost"
RUN_ID_RE = re.compile(r"\d{4}-\d{2}-\d{2}-\d{6}-[0-9a-f]{7}-[0-9a-z]{4}")
NOTE_TARGET_NOT_HEAD = "target_not_head"
NOTE_WORKTREE_DIFFERS = "worktree_differs"
NOTE_WORKTREE_UNKNOWN = "worktree_unknown"
PACKET_ID_RE = re.compile(r"[A-Za-z0-9_-]+")
# Pfade je git-Aufruf als Pathspecs: unter der Grenze von cmd.exe (8191 Zeichen) und der
# Windows-Kommandozeile (32767), mit Platz für git und die übrigen Argumente.
ARG_CHUNK_CHARS = 8000
LOCK_NAME = "plan.lock"   # Sperrdatei im Laufordner, solange plan.json geändert wird
LOCK_WAIT = 600           # Sekunden, die ein Aufruf auf die Sperre wartet
LOCK_POLL = 0.05          # Sekunden zwischen zwei Versuchen
MESSAGE_CACHE_SIZE = 64   # Commit-Messages so vieler Bereiche je Prozess zwischenspeichern

PROFILES = ("standard", "checkpoint")
FOCI = ("bugs", "security", "quality")

RUN_SUFFIX_CHARS = string.ascii_lowercase + string.digits
RUN_SUFFIX_LEN = 4
SHORT_SHA_LEN = 7

# Einordnung (Spec 26, Ablauf Schritt 2): Dateien ohne Quellcode werden nie reviewt,
# Testdateien nur mit --with-tests. Die Python-Muster und die Testordner gelten ohne
# Rücksicht auf Groß/Klein; die Delphi-Regel steht bei TEST_PAS_WORD.
DOC_SUFFIXES = frozenset({".md", ".markdown", ".rst"})
DOC_NAMES = frozenset({"NEWS", "CHANGES", "CHANGELOG", "AUTHORS", "LICENSE", "COPYING"})
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
                            ".tif", ".tiff"})
PROJECT_SUFFIXES = frozenset({".dproj", ".res"})
TEST_NAME_PATTERNS = ("test_*.py", "*_test.py")
# `.pas` nach Gliedern, auf den Namen ohne Endung: Er wird an `.` und `_` geteilt, jedes Stück
# in Wörter — ein großgeschriebenes Wort (`Test`), eine Folge von Großbuchstaben, die vor einem
# solchen Wort endet (`HTMLTest` → `HTML`, `Test`), sonst die ganze Folge (`FooTEST` → `Foo`,
# `TEST`), und Ziffern für sich (`MyTest2` → `My`, `Test`, `2`). Eine Testdatei ist es, wenn ein
# Glied `Test` oder `Tests` heißt, Groß/Klein egal: `MyApp.Tests.Utils`, `App.Test.Core`,
# `Foo_Test_Helpers`, `MyTestsUnit`, `FooTEST`, `HTMLTest`, `Test`. Sonst nicht — `Testament`,
# `TestimonialService`, `Testing`, `LATEST`, `CONTEST`, `Latest` sind keine Testdateien.
TEST_PAS_SPLIT = re.compile(r"[._]")
TEST_PAS_WORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
TEST_PAS_SEGMENTS = frozenset({"test", "tests"})
TEST_DIRS = frozenset({"tests", "unittests"})

REASON_DOC = "keine Quelldatei: Doku"
REASON_IMAGE = "keine Quelldatei: Bild"
REASON_PROJECT = "keine Quelldatei: Delphi-Projekt oder Ressource"
REASON_TEST = "Testdatei: nur mit --with-tests"
REASON_NOT_UTF8 = "Pfad ist kein UTF-8"
REASON_SOURCE_NOT_UTF8 = "Quelldatei mit Nicht-UTF-8-Pfad — nicht reviewt"


class KitError(RuntimeError):
    """Ein Schritt ist gescheitert — mit einer Ursache, die der Nutzer versteht."""


# --- Git ----------------------------------------------------------------------------------

class GitError(KitError):
    """git lief, endete aber mit Exit ≠ 0. `returncode` und `detail` (stderr) bleiben
    erhalten, damit Aufrufer nur die Fälle umdeuten, die sie kennen."""

    def __init__(self, message: str, returncode: int, detail: str) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.detail = detail


def _git(repo: Path, *args: str, env: dict | None = None, stdin: bytes | None = None) -> str:
    """git-Aufruf, der bei Fehlschlag wirft. Ausgabe als UTF-8, nie geraten; Bytes, die kein
    UTF-8 sind, bleiben als Surrogate erhalten (`os.fsdecode`-Form). `env` ersetzt die
    Umgebung (None: die des Prozesses), `stdin` geht als Bytes an git (None: leer).
    Fehlerarten wie bei `_git_bytes`."""
    return _git_bytes(repo, *args, env=env, stdin=stdin).decode("utf-8", errors="surrogateescape")


def _git_bytes(repo: Path, *args: str, env: dict | None = None,
               stdin: bytes | None = None) -> bytes:
    """Wie `_git`, aber die Ausgabe als Bytes — für Blob-Inhalte (`cat-file --batch`), die
    sonst einmal als Text und einmal als Bytes im Speicher lägen.

    Drei Fehlerarten mit eigener Meldung: git startet nicht (fehlt, Ordner fehlt) — KitError
    „konnte nicht gestartet werden"; Zeitgrenze — KitError „abgebrochen"; Exit ≠ 0 —
    GitError mit git's eigener Meldung."""
    feed = {"stdin": subprocess.DEVNULL} if stdin is None else {"input": stdin}
    try:
        done = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, env=env,
            timeout=GIT_TIMEOUT, check=False, **feed,
        )
    except subprocess.TimeoutExpired:
        raise KitError(f"git {' '.join(args)} nach {GIT_TIMEOUT} s abgebrochen") from None
    except (OSError, subprocess.SubprocessError) as exc:
        raise KitError(f"git {' '.join(args)} konnte nicht gestartet werden: {exc}") from exc
    if done.returncode != 0:
        stderr = done.stderr.decode("utf-8", errors="replace").strip()
        detail = stderr or f"Exit {done.returncode}"
        raise GitError(f"git {' '.join(args)} fehlgeschlagen: {detail}", done.returncode, detail)
    return done.stdout


class UnknownRevision(KitError):
    """Die Revision gibt es nicht oder sie ist kein Commit (Exit 1 von
    `rev-parse --verify --quiet`) — der einzige Fehler von `_commit`, den Aufrufer umdeuten
    dürfen."""


def _toplevel(repo) -> Path:
    """Repo-Wurzel zu `repo` (auch aus einem Unterordner). Kein Repo: KitError mit git's
    Meldung, nie „Revision unbekannt"."""
    repo = Path(repo)
    if not repo.is_dir():
        raise KitError(f"kein Git-Repository: Ordner {repo} fehlt")
    try:
        return Path(_git(repo, "rev-parse", "--show-toplevel").strip())
    except GitError as exc:
        raise KitError(f"kein Git-Repository: {repo} ({exc.detail})") from None


def _commit(repo: Path, rev: str) -> str:
    """SHA des Commits zu `rev`. Nur „gibt es nicht oder ist kein Commit" (Exit 1 von
    `rev-parse --verify --quiet`) heißt „unbekannt" (`UnknownRevision`); jeder andere
    Fehler behält seine Ursache."""
    if not rev or rev.startswith("-"):
        raise KitError(f"ungültige Revision: {rev!r}")
    try:
        return _git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").strip()
    except GitError as exc:
        if exc.returncode == 1:
            raise UnknownRevision(f"Revision {rev!r} unbekannt oder kein Commit") from None
        raise


def _empty_tree(repo: Path) -> str:
    """SHA des leeren Baums im Hash-Format dieses Repos; schreibt nichts."""
    return _git(repo, "hash-object", "-t", "tree", "--stdin").strip()


class Span(NamedTuple):
    """Ein aufgelöster Bereich. `base..target` wird gezählt und reviewt (wie
    `git diff BASIS...ZIEL`): `base` ist die Merge-Basis, beim Wurzel-Commit der leere Baum.
    `log_base` ist die aufgelöste BASIS für die Commit-Messages (`git log log_base..target`);
    beim Wurzel-Commit None, die Messages liefert dann `git log target`."""
    base: str
    target: str
    log_base: str | None


class Numstat(NamedTuple):
    """Rückgabe von `numstat`: geänderte Zeilen je Datei und der Bereich, über den gezählt
    wurde — einmal aufgelöst, damit Plan und Lauf-ID denselben Commit meinen."""
    counts: dict
    span: Span


def _requested_range(rng) -> str:
    """Der Bereich, wie der Auftrag ihn meint: None heißt der letzte Commit. Die einzige
    Stelle, an der dieser Standard gilt."""
    rng = DEFAULT_RANGE if rng is None else rng
    if not isinstance(rng, str) or not rng.strip():
        raise KitError(f"leerer Bereich {rng!r} — gib BASIS..ZIEL oder eine Revision an")
    return rng


def range_text(span: Span) -> str:
    """`range` für Plan und Pakete, das `split_range` wieder zu demselben Span auflöst:
    `<merge-basis>..<ziel>` als SHAs; beim Wurzel-Commit nur `<ziel>` — der leere Baum ist
    kein Commit und ginge in `A..B` nicht."""
    return span.target if span.log_base is None else f"{span.base}..{span.target}"


def split_range(repo: Path, rng) -> Span:
    """`BASIS..ZIEL` → Span. Eine einzelne Revision `X` heißt `X^..X`, beim Wurzel-Commit
    leerer Baum..X; ohne Bereich (None) der letzte Commit `HEAD`. Bei zwei Punkten wird ab
    der Merge-Basis gezählt. Drei Punkte sind abgelehnt — zwei Punkte zählen schon so."""
    rng = _requested_range(rng)
    if "..." in rng:
        raise KitError("Bereich mit '...' nicht unterstützt — gib BASIS..ZIEL an")
    if ".." not in rng:
        target = _commit(repo, rng)
        parents = _git(repo, "rev-list", "--parents", "-n", "1", target).split()[1:]
        if not parents:
            return Span(_empty_tree(repo), target, None)
        return Span(parents[0], target, parents[0])
    base_rev, target_rev = rng.split("..", 1)
    log_base, target = _commit(repo, base_rev or "HEAD"), _commit(repo, target_rev or "HEAD")
    try:
        merge_base = _git(repo, "merge-base", log_base, target).strip()
    except GitError as exc:
        if exc.returncode == 1:
            raise KitError(f"Bereich {rng!r}: BASIS und ZIEL haben keine gemeinsame Basis") from None
        raise
    return Span(merge_base, target, log_base)


def _is_utf8(path: str) -> bool:
    try:
        path.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _escaped(path: str) -> str:
    """Ein Pfad mit Surrogaten in lesbarer, schreibbarer Form: `caf\\xe9.png`."""
    return path.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="backslashreplace")


def numstat(repo, rng):
    """Geänderte Zeilen je Datei im Bereich: hinzugefügte plus gelöschte, nach Pfad sortiert.

    `git diff --numstat --no-renames MERGE-BASIS ZIEL` aus der Repo-Wurzel, auch wenn `repo`
    ein Unterordner ist: eine Umbenennung ist eine gelöschte und eine neue Datei;
    Binärdateien zählen 0; `.skills/` schließt dieselbe Pathspec aus wie subagent-dev. Pfade
    sind repo-relativ in POSIX-Form, wie Git sie ausgibt; ein Pfad, der kein UTF-8 ist,
    trägt Surrogate (`os.fsdecode`-Form) — `build_plan` führt ihn unter `not_reviewed`.
    Rückgabe: `Numstat(counts, span)`."""
    repo = _toplevel(repo)
    span = split_range(repo, rng)
    out = _git(repo, "diff", "--numstat", "--no-renames", "--no-textconv", "--no-ext-diff",
               "-z", span.base, span.target, "--", *DIFF_PATHSPEC)
    counts: dict[str, int] = {}
    for record in out.split("\0"):
        if not record:
            continue
        added, deleted, path = record.split("\t", 2)
        lines = 0 if "-" in (added, deleted) else int(added) + int(deleted)
        counts[path] = counts.get(path, 0) + lines
    return Numstat(dict(sorted(counts.items())), span)


# --- Einordnung und Schnittregel -------------------------------------------------------------

def classify(path, with_tests):
    """None, wenn die Datei reviewt wird; sonst der Grund für `not_reviewed`.

    Ohne Quellcode (nie reviewt): Doku (Markdown, reStructuredText, `NEWS` und Verwandte
    ohne Endung), Bilder, `.dproj`, `.res`. Tests nur mit `with_tests` — so lief die
    Messung: `test_*.py`, `*_test.py` und Dateien unter `tests/` oder `unittests/` ohne
    Rücksicht auf Groß/Klein; `.pas`, wenn ein Glied des Namens (geteilt an `.`, `_` und
    Wortgrenzen, Regel bei `TEST_PAS_WORD`) `Test` oder `Tests` heißt
    (`MyApp.Tests.Utils.pas`, `FooTEST.pas` ja, `Testament.pas`, `LATEST.pas` nein)."""
    pure = PurePosixPath(path)
    suffix = pure.suffix.lower()
    if suffix in DOC_SUFFIXES or pure.name.upper() in DOC_NAMES:
        return REASON_DOC
    if suffix in IMAGE_SUFFIXES:
        return REASON_IMAGE
    if suffix in PROJECT_SUFFIXES:
        return REASON_PROJECT
    if with_tests:
        return None
    name = pure.name.lower()
    is_test = (
        any(fnmatch.fnmatchcase(name, pattern) for pattern in TEST_NAME_PATTERNS)
        or (suffix == ".pas" and any(word.lower() in TEST_PAS_SEGMENTS
                                     for piece in TEST_PAS_SPLIT.split(pure.stem)
                                     for word in TEST_PAS_WORD.findall(piece)))
        or any(part.lower() in TEST_DIRS for part in pure.parts[:-1])
    )
    return REASON_TEST if is_test else None


def cut_packets(files, packet_size):
    """Pakete nach der Schnittregel (Spec 26, Ablauf Schritt 2).

    `files`: Dict Pfad → geänderte Zeilen oder Paare (Pfad, Zeilen). Dateien nach Pfad
    sortiert und nach Verzeichnis gruppiert, Gruppen in der Reihenfolge ihres ersten
    Auftretens. Gruppen füllen der Reihe nach Pakete bis `packet_size`; ein Paket nimmt
    mehrere Verzeichnisse auf. Eine Gruppe über `packet_size` wird an Dateigrenzen geteilt,
    eine Datei nie; eine Datei über `packet_size` ist ein eigenes Paket. Vorrang: Datei ganz
    vor Verzeichnis zusammen vor Paketgröße. IDs `p1`, `p2`, … in dieser Reihenfolge.

    Rückgabe: Liste von {"id", "files", "changed_lines"}."""
    if not isinstance(packet_size, int) or isinstance(packet_size, bool) or packet_size < 1:
        raise KitError(f"packet_size muss eine positive Zahl sein, nicht {packet_size!r}")
    items = files.items() if isinstance(files, dict) else files
    groups: dict[str, list[tuple[str, int]]] = {}
    for path, lines in sorted((str(p), int(n)) for p, n in items):
        groups.setdefault(PurePosixPath(path).parent.as_posix(), []).append((path, lines))

    chunks: list[list[tuple[str, int]]] = []
    current: list[tuple[str, int]] = []
    size = 0

    def close() -> None:
        nonlocal current, size
        if current:
            chunks.append(current)
        current, size = [], 0

    for group in groups.values():
        total = sum(n for _, n in group)
        if total <= packet_size:
            if size + total > packet_size:
                close()
            current.extend(group)
            size += total
            continue
        close()
        for path, lines in group:
            if lines > packet_size:
                close()
                chunks.append([(path, lines)])
                continue
            if size + lines > packet_size:
                close()
            current.append((path, lines))
            size += lines
    close()
    return [
        {"id": f"p{i}", "files": [p for p, _ in chunk], "changed_lines": sum(n for _, n in chunk)}
        for i, chunk in enumerate(chunks, 1)
    ]


# --- Lauf-ID und JSON -------------------------------------------------------------------

_ISSUED: set[str] = set()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def new_run_id(sha):
    """Lauf-ID `<JJJJ-MM-TT>-<HHMMSS>-<kurz-sha>-<4 Zufallszeichen>` in UTC.

    UTC, damit IDs auch über eine Zeitumstellung in der Reihenfolge ihres Entstehens
    sortieren. Zwei IDs aus demselben Prozess sind nie gleich, auch nicht in derselben
    Sekunde; zwischen Prozessen sichert `build_plan` über das Anlegen des Laufordners ab."""
    short = str(sha).strip().lower()[:SHORT_SHA_LEN]
    if len(short) < SHORT_SHA_LEN or any(c not in string.hexdigits for c in short):
        raise KitError(f"kein Commit-SHA: {sha!r}")
    now = _now()
    if now.utcoffset() != dt.timedelta(0):
        raise KitError(f"Zeit für die Lauf-ID muss UTC sein, nicht {now!r}")
    stamp = now.strftime("%Y-%m-%d-%H%M%S")
    while True:
        suffix = "".join(secrets.choice(RUN_SUFFIX_CHARS) for _ in range(RUN_SUFFIX_LEN))
        run_id = f"{stamp}-{short}-{suffix}"
        if run_id not in _ISSUED:
            _ISSUED.add(run_id)
            return run_id


def _normalize(value):
    """Wert so, wie er als JSON gelesen zurückkäme: Pfad-Objekte als repo-relative
    POSIX-Pfade, Tupel als Listen, Unterklassen von bool/int/float/str als deren schlichter
    Wert (eine IntEnum als Zahl, nie über ein eigenes `__str__`/`__repr__`). NaN, Infinity
    und alles andere, was JSON nicht kennt, sind ein KitError."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise KitError(f"JSON-Schlüssel muss Text sein, nicht {key!r}")
            out[str.__str__(key)] = _normalize(item)
        return out
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, PurePath):
        if value.is_absolute():
            raise KitError(f"absoluter Pfad in einem Artefakt: {value}")
        return value.as_posix()
    if value is None:
        return None
    if isinstance(value, bool):
        return value is True
    if isinstance(value, int):
        return int.__int__(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise KitError(f"keine endliche Zahl, in JSON nicht schreibbar: {float.__repr__(value)}")
        return float.__float__(value)
    if isinstance(value, str):
        return str.__str__(value)
    raise KitError(f"nicht als JSON schreibbar: {type(value).__name__}")


def write_json(path, meta, payload):
    """Die eine Schreibfunktion für alle JSON-Artefakte des Laufs (Spec 26, E3).

    `_meta` zuerst mit `skill`, `schema` (fest, `meta` darf sie nicht setzen), dann den
    Feldern aus `meta` (Pflicht: `generated`, das Kommando); danach `payload` in seiner
    Reihenfolge. `ensure_ascii=False`, Pfad-Objekte als repo-relative POSIX-Pfade; Text, der
    kein UTF-8 ist, und NaN/Infinity sind ein KitError. Schreibt über eine eigene Temp-Datei
    im Zielordner (Rechte nach der umask, wie eine normal angelegte Datei), ersetzt atomar und
    räumt die Temp-Datei bei jedem Fehler weg. Rückgabe: das geschriebene Objekt, so wie es
    von der Platte gelesen zurückkäme."""
    if "generated" not in meta:
        raise KitError("_meta braucht 'generated' (das Kommando)")
    reserved = [key for key in RESERVED_META if key in meta]
    if reserved:
        raise KitError(f"_meta-Felder {', '.join(reserved)} sind fest und nicht überschreibbar")
    if "_meta" in payload:
        raise KitError("payload darf kein eigenes _meta tragen")
    data = _normalize({"_meta": {"skill": SKILL_NAME, "schema": SCHEMA_VERSION, **meta},
                       **payload})
    try:
        text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    except ValueError as exc:
        raise KitError(f"nicht als JSON schreibbar: {exc}") from None
    _write_text(path, text)
    return data


def _write_text(path, text: str) -> None:
    """Text als UTF-8 atomar schreiben — für `write_json` und die Paketblöcke. Text, der kein
    UTF-8 ist, ist ein KitError. Schreibt über eine eigene Temp-Datei im Zielordner (Rechte
    nach der umask), ersetzt atomar und räumt die Temp-Datei bei jedem Fehler weg."""
    try:
        raw = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        bad = text[exc.start:exc.end].encode("utf-8", errors="surrogateescape")
        raise KitError(f"Text ist kein UTF-8 ({bad!r}) — Artefakt nicht geschrieben") from None
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # os.open mit 0o666: die umask wirkt wie bei jeder neuen Datei (NamedTemporaryFile legte
    # 0600 an); O_EXCL, damit keine fremde Datei überschrieben wird.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    for _ in range(100):
        tmp = path.parent / f".{path.name}.{secrets.token_hex(4)}.tmp"
        try:
            fd = os.open(tmp, flags, 0o666)
        except FileExistsError:
            continue
        break
    else:
        raise KitError(f"keine freie Temp-Datei neben {path}")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


# --- Plan ---------------------------------------------------------------------------------

def run_dir(repo, run_id) -> Path:
    """Ordner eines Laufs unter dem Repo: `.skills/cache/deep-review/<lauf>/`."""
    return Path(repo) / CACHE_DIR / run_id


def _new_run_dir(repo: Path, sha: str) -> tuple[str, Path]:
    for _ in range(100):
        run_id = new_run_id(sha)
        directory = run_dir(repo, run_id)
        try:
            directory.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return run_id, directory
    raise KitError("keine freie Lauf-ID gefunden")


def _plan_command(rng: str, profile: str, focus: str, split_at: int, with_tests: bool) -> str:
    cmd = (f"{SCRIPT_CMD} plan --range {shlex.quote(rng)} --profile {profile} "
           f"--focus {focus} --split-at {split_at}")
    return cmd + (" --with-tests" if with_tests else "")


def build_plan(repo, rng, profile, focus, split_at, with_tests):
    """Paketplan für `rng` schreiben und zurückgeben (Spec 26, Ablauf Schritt 2).

    `rng` None = der letzte Commit. Der Bereich wird einmal aufgelöst und steht dreifach
    eindeutig im Plan: `base` ist die gezählte Basis (Merge-Basis, beim Wurzel-Commit der
    leere Baum) — auf ihren Stand setzen die Paket-Bereiche die Paketdateien —, `target` das
    Ziel, `log_base` die aufgelöste BASIS für die Commit-Messages (`git log log_base..target`,
    beim Wurzel-Commit None: `git log target`). `range` ist `<base>..<target>` als SHAs,
    beim Wurzel-Commit nur `<target>` (`range_text`); `numstat(repo, range)` zählt wieder
    dasselbe. `root` ist true nur beim Wurzel-Commit: Ein Wurzel-Commit-Plan braucht immer
    Hilfscommits (ein Basis-Commit mit leerem Baum), denn `/code-review` läse das blanke
    `<target>` als Ref und reviewte einen leeren Diff — deshalb trägt dort jedes Paket
    `range: null`, bis die Hilfscommits den reviewbaren Bereich liefern. Der Wortlaut des
    Auftrags steht in `_meta.generated`. `changed_lines` zählt die
    reviewten Dateien; die übrigen stehen mit Grund unter `not_reviewed`, ein Pfad, der kein
    UTF-8 ist, in escapter Form (`caf\\xe9.png`) — als Quelldatei mit eigenem Grund
    `REASON_SOURCE_NOT_UTF8`, sonst `REASON_NOT_UTF8`. Ohne reviewte Datei: KitError
    „nichts zu reviewen", der solche Quelldateien nennt; kein Lauf. Bis `split_at` (None = `SPLIT_AT`) — oder wenn das Schneiden nur
    ein Paket ergäbe — ein Paket `p1` über den Originalbereich, `split: false`; sonst
    `split: true`, Pakete nach `cut_packets` mit `packet_size` = kleiner von `PACKET_SIZE`
    und `split_at`, deren `range` die Paket-Bereiche füllen. Fokus `security`: ein Paket
    `s1` über den ganzen Bereich, nie geteilt. `file_keys` bleibt leer, bis
    Datei-Schlüssel gesammelt werden. Die Lauf-ID steht in `_meta.run`; `plan.json` liegt
    in `run_dir(repo, run)`. Scheitert das Schreiben, bleibt kein Laufordner zurück."""
    if profile not in PROFILES:
        raise KitError(f"Profil {profile!r} unbekannt — erlaubt: {', '.join(PROFILES)}")
    if focus not in FOCI:
        raise KitError(f"Fokus {focus!r} unbekannt — erlaubt: {', '.join(FOCI)}")
    if profile == "checkpoint" and focus != "bugs":
        raise KitError("Profil checkpoint prüft nur Fokus bugs")
    split_at = SPLIT_AT if split_at is None else split_at
    if not isinstance(split_at, int) or isinstance(split_at, bool) or split_at < 1:
        raise KitError(f"split_at muss eine positive Zahl sein, nicht {split_at!r}")
    rng = _requested_range(rng)

    repo = _toplevel(repo)
    stat = numstat(repo, rng)
    span = stat.span
    resolved = range_text(span)

    reviewed: dict[str, int] = {}
    not_reviewed = []
    source_not_utf8 = []
    for path, lines in stat.counts.items():
        if not _is_utf8(path):
            # Erst einordnen: eine Quelldatei fehlt im Review, ein Bild oder Doku nicht.
            escaped = _escaped(path)
            if classify(escaped, with_tests) is None:
                source_not_utf8.append(escaped)
                not_reviewed.append({"file": escaped, "reason": REASON_SOURCE_NOT_UTF8})
            else:
                not_reviewed.append({"file": escaped, "reason": REASON_NOT_UTF8})
            continue
        reason = classify(path, with_tests)
        if reason is None:
            reviewed[path] = lines
        else:
            not_reviewed.append({"file": path, "reason": reason})
    if not reviewed:
        skipped = f", {len(not_reviewed)} Datei(en) ohne Review" if not_reviewed else ""
        sources = (f"; Quelldatei(en) mit Nicht-UTF-8-Pfad nicht reviewt: {', '.join(source_not_utf8)}"
                   if source_not_utf8 else "")
        raise KitError(f"nichts zu reviewen in {rng!r}: keine geänderte Quelldatei{skipped}{sources}")
    changed = sum(reviewed.values())
    packet_size = min(PACKET_SIZE, split_at)

    cut = cut_packets(reviewed, packet_size) if focus != "security" and changed > split_at else []
    split = len(cut) > 1
    root = span.log_base is None
    if split:
        packets = [{**p, "range": None, "reused_from": None} for p in cut]
    else:
        # Beim Wurzel-Commit ist `resolved` nur `<ziel>`; /code-review läse das als Ref und
        # reviewte einen leeren Diff — den Bereich liefern erst die Hilfscommits.
        packets = [{"id": "s1" if focus == "security" else "p1", "files": list(reviewed),
                    "changed_lines": changed, "range": None if root else resolved,
                    "reused_from": None}]

    run_id, directory = _new_run_dir(repo, span.target)
    meta = {"generated": _plan_command(rng, profile, focus, split_at, with_tests), "run": run_id}
    payload = {
        "range": resolved,
        "base": span.base,
        "target": span.target,
        "log_base": span.log_base,
        "root": root,
        "profile": profile,
        "focus": focus,
        "split": split,
        "split_at": split_at,
        "packet_size": packet_size,
        "changed_lines": changed,
        "packets": packets,
        "file_keys": {},
        "not_reviewed": not_reviewed,
    }
    try:
        return write_json(directory / "plan.json", meta, payload)
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise


# --- Paket-Bereiche und cleanup -------------------------------------------------------------

def _check_run_id(run_id) -> str:
    """Eine Lauf-ID in der Form von `new_run_id`; alles andere (auch `../x`) ist ein
    KitError, bevor daraus ein Pfad oder ein Ref-Name wird."""
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise KitError(f"keine Lauf-ID: {run_id!r}")
    return run_id


def _pid_alive(pid: int):
    """Lebt der Prozess `pid` auf diesem Rechner? True, False oder None (nicht prüfbar).
    POSIX: `os.kill(pid, 0)`; unter Windows über OpenProcess/GetExitCodeProcess, weil
    `os.kill` dort den Prozess beenden würde."""
    if pid <= 0:
        return None
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
            if not handle:
                return False if kernel32.GetLastError() == 87 else None  # INVALID_PARAMETER
            try:
                code = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return None
                return code.value == 259                        # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except (OSError, AttributeError):
            return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def _lock_owner(lock: Path):
    """Inhalt der Sperrdatei und ihr Besitzer: (Text, PID oder None, lebt: True/False/None).
    Der Besitzer zählt nur als tot, wenn die PID auf diesem Rechner nicht lebt; eine Sperre
    eines anderen Rechners oder ohne lesbare PID gilt als belegt. Fehlt die Datei: None."""
    try:
        text = lock.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None
    except OSError:
        return "", None, None
    fields = text.split()
    if not fields or not fields[0].isdigit():
        return text, None, None
    pid = int(fields[0])
    host = fields[1] if len(fields) > 1 else None
    if host is not None and host != socket.gethostname():
        return text, pid, None
    return text, pid, _pid_alive(pid)


def _break_lock(lock: Path, text: str) -> bool:
    """Die Sperre eines toten Besitzers entfernen, ohne eine frische zu treffen: umbenennen,
    dann prüfen, dass der Inhalt noch der gelesene ist — sonst (ein anderer hat sie eben
    übernommen) zurücklegen, wenn der Platz noch frei ist. False nur, wenn sie sich nicht
    umbenennen lässt; dann wartet der Aufrufer wie bei einer belegten Sperre."""
    grave = lock.with_name(f"{LOCK_NAME}.{os.getpid()}.{secrets.token_hex(4)}")
    try:
        os.rename(lock, grave)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    try:
        moved = grave.read_text(encoding="utf-8", errors="replace")
    except OSError:
        moved = None
    if moved != text:
        try:
            os.link(grave, lock)
        except OSError:
            pass
    grave.unlink(missing_ok=True)
    return True


@contextlib.contextmanager
def _plan_lock(directory: Path, run_id: str, wait=None):
    """Exklusive Sperre auf `plan.json` eines Laufs: Sperrdatei `plan.lock` im Laufordner,
    angelegt mit O_EXCL, mit PID und Rechnername des Besitzers, im `finally` wieder
    gelöscht. Lebt der Besitzer einer vorhandenen Sperre auf diesem Rechner nicht mehr
    (abgestürzter Aufruf), wird sie übernommen. Sonst wartet der Aufruf bis `wait` Sekunden
    (Default `LOCK_WAIT`); danach KitError „gesperrt" mit Pfad und Besitzer. Fehlt der
    Laufordner: KitError „hat keinen Plan"."""
    lock = directory / LOCK_NAME
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    deadline = time.monotonic() + (LOCK_WAIT if wait is None else wait)
    while True:
        try:
            fd = os.open(lock, flags, 0o666)
            break
        except FileExistsError:
            owner = _lock_owner(lock)
            if owner is None:
                continue
            text, pid, alive = owner
            if alive is False and _break_lock(lock, text):
                continue
            if time.monotonic() >= deadline:
                if alive is False:
                    who = f"Sperre des beendeten Prozesses {pid} lässt sich nicht entfernen"
                elif alive:
                    who = f"Prozess {pid} hält sie noch; später erneut aufrufen"
                elif pid is not None:
                    who = f"Besitzer {text.strip()} ist von hier aus nicht prüfbar"
                else:
                    who = "Sperrdatei ohne PID; läuft kein Aufruf mehr, sie entfernen"
                raise KitError(f"Plan von Lauf {run_id} ist gesperrt ({lock}) — {who}") from None
            time.sleep(LOCK_POLL)
        except FileNotFoundError:
            raise KitError(f"Lauf {run_id} hat keinen Plan ({directory / 'plan.json'})") from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()} {socket.gethostname()}\n")
        yield
    finally:
        lock.unlink(missing_ok=True)


def _load_plan(repo: Path, run_id: str) -> tuple[Path, dict]:
    """`plan.json` des Laufs, geprüft auf die Felder, die die Paket-Bereiche lesen: `_meta`
    ein Objekt, `base`/`target` Text, `log_base` Text oder null, `packets` eine Liste von
    Objekten mit eindeutiger `id` (Text aus Buchstaben, Ziffern, `_`, `-`), `files` (Liste
    von Text) und `range` (Text oder null), `notes` eine Liste von Objekten mit `packet`,
    `kind`, `text` (Text) und `files` (Liste von Text). Alles andere ist ein KitError, kein
    TypeError."""
    path = run_dir(repo, run_id) / "plan.json"
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise KitError(f"Lauf {run_id} hat keinen Plan ({path})") from None
    except (OSError, ValueError) as exc:
        raise KitError(f"Plan von Lauf {run_id} nicht lesbar: {exc}") from None

    def bad(why: str) -> KitError:
        return KitError(f"Plan von Lauf {run_id} ist kein deep-review-Plan ({why}): {path}")

    if not isinstance(plan, dict) or not all(k in plan for k in ("_meta", "base", "target",
                                                                   "log_base", "packets")):
        raise bad("Pflichtfelder fehlen")
    if not isinstance(plan["_meta"], dict):
        raise bad("_meta ist kein Objekt")
    for key in ("base", "target"):
        if not isinstance(plan[key], str) or not plan[key]:
            raise bad(f"{key} ist kein SHA")
    for key in ("log_base", "range"):
        if plan.get(key) is not None and not isinstance(plan[key], str):
            raise bad(f"{key} ist weder Text noch null")
    if not isinstance(plan["packets"], list):
        raise bad("packets ist keine Liste")
    seen = set()
    for packet in plan["packets"]:
        if not isinstance(packet, dict):
            raise bad(f"Paket {packet!r} ist kein Objekt")
        pid = packet.get("id")
        if not isinstance(pid, str) or not PACKET_ID_RE.fullmatch(pid) or pid in seen:
            raise bad(f"Paket-ID {pid!r} ungültig oder doppelt")
        seen.add(pid)
        files = packet.get("files")
        if not isinstance(files, list) or not all(isinstance(f, str) and f for f in files):
            raise bad(f"files von {pid} ist keine Liste von Pfaden")
        if packet.get("range") is not None and not isinstance(packet["range"], str):
            raise bad(f"range von {pid} ist weder Text noch null")
    notes = plan.get("notes", [])
    if not isinstance(notes, list) or not all(isinstance(n, dict) for n in notes):
        raise bad("notes ist keine Liste von Objekten")
    for note in notes:
        files = note.get("files")
        if not (all(isinstance(note.get(k), str) for k in ("packet", "kind", "text"))
                and isinstance(files, list) and all(isinstance(f, str) for f in files)):
            raise bad(f"Hinweis {note!r} braucht packet, kind, text (Text) und files "
                      "(Liste von Text)")
    return path, plan


def _write_plan(path: Path, plan: dict, notes=None) -> None:
    """`plan` zurückschreiben, `_meta` ohne die festen Felder, `notes` (die gegebenen, sonst
    die vorhandenen) als letzter Schlüssel."""
    meta = {k: v for k, v in plan["_meta"].items() if k not in RESERVED_META}
    payload = {k: v for k, v in plan.items() if k not in ("_meta", "notes")}
    if notes is not None:
        payload["notes"] = notes
    elif "notes" in plan:
        payload["notes"] = plan["notes"]
    write_json(path, meta, payload)


def _base_object(repo: Path, rev) -> str:
    """SHA der gezählten Basis: ein Commit, beim Wurzel-Commit der leere Baum. Nur „kein
    Commit" (`UnknownRevision`) fällt auf die Baum-Suche durch; Zeitgrenze, Startfehler und
    andere git-Fehler behalten ihre Ursache."""
    try:
        return _commit(repo, rev)
    except UnknownRevision:
        pass
    try:
        return _git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{tree}}").strip()
    except GitError as exc:
        if exc.returncode == 1:
            raise KitError(f"Basis {rev!r} unbekannt — weder Commit noch Baum") from None
        raise


def _head(repo: Path):
    """SHA von HEAD; None nur, wenn HEAD noch keinen Commit hat."""
    try:
        return _commit(repo, "HEAD")
    except UnknownRevision:
        return None


def _literal_chunks(paths):
    """Pfade als `:(literal)<pfad>`-Pathspecs in Stücken, deren Länge mit Trennzeichen
    `ARG_CHUNK_CHARS` nicht überschreitet — so bleibt jeder Aufruf unter der Grenze der
    Kommandozeile unter Windows. Ein einzelner längerer Pfad steht allein."""
    chunk: list[str] = []
    size = 0
    for path in paths:
        spec = f":(literal){path}"
        if chunk and size + 1 + len(spec) > ARG_CHUNK_CHARS:
            yield chunk
            chunk, size = [], 0
        size += len(spec) + (1 if chunk else 0)
        chunk.append(spec)
    if chunk:
        yield chunk


def _tree_entries(repo: Path, treeish: str, paths) -> dict:
    """Pfad → (Modus, Typ, SHA) für die `paths`, die in `treeish` liegen. `ls-tree` bekommt
    nur diese Pfade als `:(literal)`-Pathspecs (in Stücken, `_literal_chunks`), listet also
    nicht den ganzen Baum; übernommen wird nur, was genau einem Pfad gleicht — ein Pfad, der
    in `treeish` ein Ordner ist, zählt nicht."""
    wanted = sorted(set(paths))
    entries = {}
    for chunk in _literal_chunks(wanted):
        out = _git(repo, "ls-tree", "-r", "-z", "--full-tree", treeish, "--", *chunk)
        for record in out.split("\0"):
            if not record:
                continue
            info, path = record.split("\t", 1)
            if path in wanted:
                mode, kind, sha = info.split()
                entries[path] = (mode, kind, sha)
    return entries


def _worktree_differs(repo: Path, target: str, files, entries: dict) -> list:
    """Paketdateien, deren Stand im Arbeitsbaum von ZIEL abweicht. git vergleicht selbst:
    `git diff --name-only --no-renames ZIEL -- :(literal)<pfade>` (in Stücken), mit den
    Filtern und der Symlink-Behandlung des Repos (auch `core.symlinks=false`); ein
    Submodul nur, wenn sein ausgecheckter Commit abweicht. `git diff` frischt den Index auf
    und schreibt ihn trotz `GIT_OPTIONAL_LOCKS=0` — deshalb läuft es auf einer Kopie des
    Index (`GIT_INDEX_FILE`), der des Nutzers bleibt unberührt (E6). Die Kopie behält die
    Zeit des Index (`copy2`): sonst gälten „racy" Einträge als sauber, und eine gleich
    lange Änderung im selben Zeittakt fiele nicht auf. Dazu kommt, was git
    nicht sieht: eine Datei, die ZIEL gelöscht hat (`entries` = Einträge von ZIEL) und die
    ungetrackt noch da liegt (ein Ordner an ihrer Stelle zählt nicht). Fehlt der Index des
    Nutzers, ist nichts zu vergleichen — gegen einen leeren Index wiche jede Datei ab:
    Rückgabe None (Arbeitsbaum nicht geprüft)."""
    files = sorted(set(files))
    index = Path(_git(repo, "rev-parse", "--git-path", "index").strip())
    index = index if index.is_absolute() else repo / index
    if not index.is_file():
        return None
    differs: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="deep-review-index-") as tmp:
        copy = Path(tmp) / "index"
        shutil.copy2(index, copy)
        env = dict(os.environ)
        env.update(GIT_INDEX_FILE=str(copy), GIT_OPTIONAL_LOCKS="0")
        for chunk in _literal_chunks(files):
            out = _git(repo, "diff", "--name-only", "--no-renames", "--no-ext-diff",
                       "--ignore-submodules=dirty", "-z", target, "--", *chunk, env=env)
            differs.update(p for p in out.split("\0") if p)
    for path in files:
        disk = repo / path
        if (path not in entries and path not in differs and os.path.lexists(disk)
                and (disk.is_symlink() or not disk.is_dir())):
            differs.add(path)
    return sorted(differs)


def _range_notes(repo: Path, pid: str, head, target: str, files, entries: dict) -> list:
    """Hinweise für den Bericht: Der Reviewer liest den Arbeitsbaum, nicht ZIEL."""
    notes = []
    if head != target:
        where = head[:SHORT_SHA_LEN] if head else "ohne Commit"
        notes.append({"packet": pid, "kind": NOTE_TARGET_NOT_HEAD, "files": [],
                      "text": f"ZIEL {target[:SHORT_SHA_LEN]} ist nicht HEAD ({where}) — "
                              "der Reviewer liest den Arbeitsbaum, nicht ZIEL"})
    differs = _worktree_differs(repo, target, files, entries)
    if differs is None:
        notes.append({"packet": pid, "kind": NOTE_WORKTREE_UNKNOWN, "files": [],
                      "text": "Index fehlt, Arbeitsbaum nicht geprüft — der Reviewer liest "
                              "den Arbeitsbaum, ob er ZIEL gleicht, ist offen"})
    elif differs:
        notes.append({"packet": pid, "kind": NOTE_WORKTREE_DIFFERS, "files": differs,
                      "text": f"Arbeitsbaum weicht in {len(differs)} Paketdatei(en) von ZIEL "
                              "ab — der Reviewer liest den Arbeitsbaum"})
    return notes


@functools.lru_cache(maxsize=MESSAGE_CACHE_SIZE)
def _range_message(repo: Path, log_base, target: str) -> bytes:
    """Die Commit-Messages des Bereichs (das Soll): `git log log_base..target`, beim
    Wurzel-Commit `git log target`. Zwischengespeichert, begrenzt auf
    `MESSAGE_CACHE_SIZE` Bereiche — `log_base` und `target` sind SHAs, das Ergebnis also
    unveränderlich."""
    rev = target if log_base is None else f"{log_base}..{target}"
    out = _git(repo, "log", "--no-show-signature", "--format=%B", rev, "--")
    return out.encode("utf-8", errors="surrogateescape")


def _index_info(files, entries: dict, null: str) -> bytes:
    """`update-index --index-info`-Eingabe: die Paketdateien auf den Stand von `entries`.
    Erst entfernen, dann setzen — so steht keine Datei einem gleichnamigen Ordner im Weg."""
    records = [f"0 {null}\t{p}" for p in files if p not in entries]
    records += [f"{entries[p][0]} {entries[p][2]}\t{p}" for p in files if p in entries]
    return b"".join(r.encode("utf-8", errors="surrogateescape") + b"\0" for r in records)


def _helper_commits(repo: Path, run_id: str, pid: str, plan: dict, files,
                    target_entries: dict) -> tuple[str, str]:
    """`von` = ZIEL mit den Paketdateien auf dem Stand der gezählten Basis (Parent ZIEL),
    `bis` = `von` mit den Paketdateien auf dem Stand von ZIEL (Parent `von`, die Messages
    des Bereichs); beide unter `refs/deep-review/<lauf>/<id>/`. Nur temporärer Index,
    Objekte und diese Refs.

    Der Baum von `bis` ist der von ZIEL. Nur wenn eine Paketdatei auf dem Stand der Basis
    als Datei/Ordner mit einem Pfad außerhalb des Pakets kollidiert (BASIS hat die Datei
    `a`, ZIEL den Ordner `a/` eines anderen Pakets, oder umgekehrt), kann ein Baum nicht
    beides tragen: `von` verliert den fremden Pfad, und `bis` trägt ihn dann auch nicht —
    so zeigt `von..bis` weiter genau die Paketdateien."""
    target = plan["target"]
    null = "0" * len(target)
    von_info = _index_info(files, _tree_entries(repo, plan["base"], files), null)
    bis_info = _index_info(files, target_entries, null)
    message = _range_message(repo, plan["log_base"], target)
    with tempfile.TemporaryDirectory(prefix="deep-review-index-") as tmp:
        env = _helper_env(Path(tmp) / "index")
        _git(repo, "read-tree", target, env=env)
        _git(repo, "update-index", "-z", "--replace", "--index-info", env=env, stdin=von_info)
        von_tree = _git(repo, "write-tree", env=env).strip()
        von = _git(repo, "commit-tree", "--no-gpg-sign", "-p", target,
                   "-m", f"deep-review {run_id} {pid}: Basis", von_tree, env=env).strip()
        _git(repo, "update-index", "-z", "--replace", "--index-info", env=env, stdin=bis_info)
        bis_tree = _git(repo, "write-tree", env=env).strip()
        bis = _git(repo, "commit-tree", "--no-gpg-sign", "-p", von, "-F", "-",
                   bis_tree, env=env, stdin=message).strip()
    prefix = f"{REF_ROOT}/{run_id}/{pid}"
    _git(repo, "update-ref", "--stdin",
         stdin=f"update {prefix}/von {von}\nupdate {prefix}/bis {bis}\n".encode("utf-8"))
    return von, bis


def _helper_env(index_file: Path) -> dict:
    """Umgebung für die Hilfscommits: temporärer Index statt dem des Nutzers, feste
    Identität (kein user.name nötig), keine optionalen Sperren."""
    env = dict(os.environ)
    env.update(GIT_INDEX_FILE=str(index_file), GIT_OPTIONAL_LOCKS="0",
               GIT_AUTHOR_NAME=HELPER_NAME, GIT_AUTHOR_EMAIL=HELPER_EMAIL,
               GIT_COMMITTER_NAME=HELPER_NAME, GIT_COMMITTER_EMAIL=HELPER_EMAIL)
    return env


def _refs_hold(repo: Path, run_id: str, pid: str, rng: str) -> bool:
    """Stehen `refs/deep-review/<lauf>/<id>/von|bis` noch auf `rng` (`<von>..<bis>`)?"""
    prefix = f"{REF_ROOT}/{run_id}/{pid}/"
    found = {}
    for line in _git(repo, "for-each-ref", "--format=%(objectname) %(refname)",
                     prefix).splitlines():
        sha, ref = line.split(" ", 1)
        found[ref] = sha
    return f"{found.get(prefix + 'von')}..{found.get(prefix + 'bis')}" == rng


def _check_span(repo: Path, run_id: str, plan: dict, base, target) -> None:
    """`base` None, die gezählte Basis des Plans oder die getippte BASIS (`log_base`);
    `target` None oder ZIEL des Plans. Sonst KitError."""
    base_ok = base is None or _base_object(repo, base) in (plan["base"], plan["log_base"])
    target_ok = target is None or _commit(repo, target) == plan["target"]
    if not (base_ok and target_ok):
        raise KitError(f"Bereich {base}..{target} passt nicht zum Plan von Lauf {run_id} "
                       f"({plan['base']}..{plan['target']})")


def make_packet_range(repo, run_id, packet, base, target):
    """Reviewbarer Bereich eines Pakets; trägt ihn als `range` in `plan.json` ein.

    `packet` ist das Paket aus dem Plan (Dict) oder seine ID; maßgeblich sind die Dateien im
    Plan des Laufs. `base` und `target` dürfen None sein und heißen dann die Werte des Plans;
    sonst muss `base` die gezählte Basis (`base`) oder die getippte BASIS (`log_base`) des
    Plans meinen und `target` dessen `target` (Revision oder SHA), sonst KitError. Ein
    vorhandener `range` kommt ohne neue Refs zurück: bei `split: false` ohne Wurzel-Commit der
    Originalbereich, sonst ein früher gebauter, solange
    `refs/deep-review/<lauf>/<id>/von|bis` noch auf ihm stehen — fehlen sie (`cleanup`,
    anderer Worktree), wird neu gebaut. Sonst baut die Funktion zwei Hilfscommits (Spec 26,
    Paket-Bereich; E6): über einen temporären Index (`GIT_INDEX_FILE`) `read-tree ZIEL`, je
    Paketdatei Modus und Blob aus der gezählten Basis oder entfernt (beim Wurzel-Commit ist
    die Basis leer), `write-tree`, `commit-tree` als `deep-review <deep-review@localhost>`;
    `von` hat Parent ZIEL und die Message „deep-review <lauf> <id>: Basis", `bis` den Baum
    von ZIEL (Ausnahme Datei/Ordner-Kollision, `_helper_commits`), Parent `von` und die
    Commit-Messages des Bereichs; `update-ref refs/deep-review/<lauf>/<id>/von|bis`.
    `git diff von..bis` zeigt so genau die Paketdateien, der Reviewer sieht den vollen Code.
    HEAD, Index und Arbeitsbaum des Nutzers bleiben unberührt.

    Lesen, Bauen und Schreiben von `plan.json` laufen unter der Sperre `plan.lock` des
    Laufs (`_plan_lock`); der Plan wird darin neu gelesen — zwei Aufrufe für verschiedene
    Pakete desselben Laufs, auch gleichzeitig, verlieren nichts. Ist ZIEL nicht HEAD oder
    weicht der Arbeitsbaum in Paketdateien von ZIEL ab, steht ein Hinweis unter `notes` im
    Plan (`packet`, `kind` = `target_not_head` | `worktree_differs` | `worktree_unknown`
    — Index fehlt, Arbeitsbaum nicht geprüft —, `files`, `text`), weil
    der Reviewer den Arbeitsbaum liest; HEAD und Arbeitsbaum werden bei jedem Aufruf
    gelesen; jeder Aufruf ersetzt die Hinweise seines Pakets. `notes`
    steht als letzter Schlüssel nach `not_reviewed`. Rückgabe: der Bereich `<von>..<bis>`
    (SHAs) oder der vorhandene."""
    repo = _toplevel(repo)
    run_id = _check_run_id(run_id)
    pid = packet.get("id") if isinstance(packet, dict) else packet
    if not isinstance(pid, str):
        raise KitError(f"keine Paket-ID: {pid!r}")
    with _plan_lock(run_dir(repo, run_id), run_id):
        path, plan = _load_plan(repo, run_id)
        order = {p["id"]: i for i, p in enumerate(plan["packets"])}
        if pid not in order:
            raise KitError(f"Paket {pid!r} steht nicht im Plan von Lauf {run_id}")
        entry = plan["packets"][order[pid]]
        _check_span(repo, run_id, plan, base, target)
        target_sha = plan["target"]
        files = list(entry["files"])
        target_entries = _tree_entries(repo, target_sha, files)
        head = _head(repo)
        notes = _range_notes(repo, pid, head, target_sha, files, target_entries)
        rng = entry.get("range")
        if rng is not None and rng != plan.get("range") and not _refs_hold(repo, run_id, pid, rng):
            rng = None
        if rng is None:
            von, bis = _helper_commits(repo, run_id, pid, plan, files, target_entries)
            rng = entry["range"] = f"{von}..{bis}"
        kinds = (NOTE_TARGET_NOT_HEAD, NOTE_WORKTREE_DIFFERS, NOTE_WORKTREE_UNKNOWN)
        kept = [n for n in plan.get("notes", []) if n.get("packet") != pid] + notes
        kept.sort(key=lambda n: (order.get(n.get("packet"), len(order)),
                                 kinds.index(n["kind"]) if n.get("kind") in kinds else len(kinds)))
        _write_plan(path, plan, kept)
    return rng


def _reset_ranges(repo: Path, deleted) -> None:
    """Nach dem Löschen: je Lauf, dessen `plan.json` in diesem Repo liegt, die Pakete, deren
    `range` genau auf die gelöschten `von`/`bis` zeigte, wieder auf null — nur nach Kräften:
    unter der Sperre des Plans, ohne auf sie zu warten. Ein Lauf ohne Plan hier (anderer
    Worktree), mit unlesbarem Plan oder mit belegter Sperre bleibt, wie er ist;
    `make_packet_range` prüft die Refs ohnehin und baut dann neu (`_refs_hold`)."""
    built: dict[str, dict[str, dict[str, str]]] = {}
    for ref, sha in deleted:
        parts = ref.split("/")
        if len(parts) == 5 and parts[4] in ("von", "bis") and RUN_ID_RE.fullmatch(parts[2]):
            built.setdefault(parts[2], {}).setdefault(parts[3], {})[parts[4]] = sha
    for run_id, packets in sorted(built.items()):
        directory = run_dir(repo, run_id)
        if not (directory / "plan.json").is_file():
            continue
        try:
            with _plan_lock(directory, run_id, wait=0):
                path, plan = _load_plan(repo, run_id)
                changed = False
                for packet in plan["packets"]:
                    ends = packets.get(packet["id"], {})
                    if packet.get("range") is not None and \
                            packet["range"] == f"{ends.get('von')}..{ends.get('bis')}":
                        packet["range"] = None
                        changed = True
                if changed:
                    _write_plan(path, plan)
        except (KitError, OSError):
            continue


def cleanup(repo, run_id, stale):
    """Hilfscommit-Refs löschen, in einer Transaktion über `git update-ref --stdin`.

    `stale` falsch: alle Refs unter `refs/deep-review/<run_id>/` (`run_id` Pflicht).
    `stale` wahr: die Refs aller anderen Läufe — abgebrochener —, die von `run_id` bleiben;
    `run_id` None löscht alle unter `refs/deep-review/`. Refs gelten für alle Worktrees
    eines Repos: `stale` löscht auch die eines Laufs, der in einem anderen Worktree noch
    läuft. Jede Ref wird nur mit ihrem gelesenen Wert gelöscht. Danach steht in jedem
    `plan.json` dieses Repos, dessen Bereiche auf gelöschte Refs zeigten, dort wieder
    `range: null` (`_reset_ranges`, nach Kräften: eine belegte Sperre wird übersprungen,
    nicht abgewartet). Objekte, HEAD, Index und Arbeitsbaum bleiben.
    Rückgabe: die gelöschten Refs, sortiert — auch wenn ein Plan nicht zurückgesetzt wurde."""
    repo = _toplevel(repo)
    if run_id is not None:
        _check_run_id(run_id)
    elif not stale:
        raise KitError("cleanup braucht eine Lauf-ID (--run) oder --stale")
    own = None if run_id is None else f"{REF_ROOT}/{run_id}/"
    doomed = []
    for line in _git(repo, "for-each-ref", "--format=%(objectname) %(refname)",
                     f"{REF_ROOT}/").splitlines():
        sha, ref = line.split(" ", 1)
        mine = own is not None and ref.startswith(own)
        if mine != bool(stale):
            doomed.append((ref, sha))
    if doomed:
        commands = "".join(f"delete {ref} {sha}\n" for ref, sha in doomed)
        _git(repo, "update-ref", "--stdin", stdin=commands.encode("utf-8", errors="surrogateescape"))
        _reset_ranges(repo, doomed)
    return sorted(ref for ref, _ in doomed)


# --- Gegenstellen (Spec 26, Ablauf Schritt 3) -----------------------------------------------
#
# Übernommen aus dem gemessenen Prototyp `docs/superpowers/reports/review-bench/counterparts.py`:
# Auflösung über die Importe der Datei (spezifischster Importpfad), voll qualifizierte
# Modulpfade `a.b.C(...)` zuerst, raise-Stellen transitiv im selben Modul, Weg eines
# Schlüsselwort-Arguments, `except` → Ausnahmen der Aufrufe im try-Block; ohne Importbezug und
# mit mehr als `AMBIGUOUS_MAX` gleichnamigen Definitionen: nichts statt Raten, aber gezählt.

COUNTERPART_SUFFIXES = frozenset({".py", ".pas", ".dpr", ".dpk"})  # mit Sammler, klein
COUNTERPART_MAX_DEFS = 2   # Definitionen je Aufruf im Block (wie im Prototyp)
RAISE_LINES_MAX = 8        # raise-Zeilen je Gegenstelle
FLOW_LINES_MAX = 12        # Zeilen des Wegs je geändertem Schlüsselwort-Argument
DOC_CHARS = 240            # erste Docstring-Zeile höchstens so lang
INDEX_CACHE_SIZE = 1       # Definitions-Indizes so vieler (Repo, ZIEL) je Prozess
NO_COLLECTOR = "Gegenstellen nicht gesammelt (Sprache)"
NOT_IN_TARGET = "nicht als Datei im Baum des ZIELS"
SKIP_SYNTAX = "Syntaxfehler"
SKIP_SYMLINK = "Symlink"
SKIP_NOT_UTF8 = "Pfad nicht UTF-8"
SKIP_GITLINK = "Submodul (gitlink), keine Datei"
QUALITY_INTRO = "## Gegenstellen\n\nGegenstellen nicht gesammelt (Fokus quality).\n"
HUNK_RE = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_C_ESCAPES = {ord(k): ord(v) for k, v in
              {"a": "\a", "b": "\b", "t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r",
               '"': '"', "\\": "\\"}.items()}
_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)
_TRIES = (ast.Try, *((ast.TryStar,) if hasattr(ast, "TryStar") else ()))


class Collected(NamedTuple):
    """Rückgabe eines Sammlers (`collect_python`, `collect_delphi`).

    `entries`: je Stelle, die die Sammelregel trifft, ein Dict `{"file", "line", "kind",
    "lines"}` — `kind` `call` oder `except` (Python), `call` oder `owner` (Delphi: `###
    <datei>:<zeile> <Op> auf <Empfänger>: <Typ>`, dann je Klasse `- Gegenstelle …`,
    `  inherited Create(…) at <datei>:<zeile>`, `  Besitz (RTL): …`; ein Delphi-Aufruf
    trägt `  deklariert: <datei>:<zeile>` für den Kopf), `lines[0]` die Überschrift
    `### <datei>:<zeile> …` (`### <datei>:<zeile>:<spalte> …`, wenn eine Zeile mehrere
    Einträge für denselben Namen hat), danach die Zeilen `- Gegenstelle <Name> [<datei>:<zeile>]:
    <Signatur>`, `  Doc: …`, `  wirft: <Typen>`, `    raise <Typ> at <datei>:<zeile>`,
    `  geändert: <arg>=<wert>; Weg:` mit eingerückten Wegzeilen; sortiert nach Datei, Zeile,
    Art. `unresolved`: Aufrufe ohne Importbezug mit mehr als `AMBIGUOUS_MAX` gleichnamigen
    Definitionen — auch Weitergaben eines geänderten Arguments, deren Weg dort endet — nicht
    im Block, aber gezählt. `unparsed`: Paare `(datei, grund)` der eigenen Dateien (aus
    `files`), die der Sammler am ZIEL nicht lesen konnte (Python: `Syntaxfehler`,
    `Symlink`, `Pfad nicht UTF-8`, `Submodul (gitlink), keine Datei`; Delphi dieselben ohne
    `Syntaxfehler`, der Scanner lehnt nichts ab; sonst `NOT_IN_TARGET`), sortiert —
    übersprungen, im Paketblock genannt und gezählt."""
    entries: list
    unresolved: int
    unparsed: list


def _has_collector(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in COUNTERPART_SUFFIXES


def _under_skills(path: str) -> bool:
    return path == ".skills" or path.startswith(".skills/")


def _unquote_path(raw: str) -> str:
    """Pfad aus einer `---`/`+++`-Zeile von `git diff`: ohne den Tab, den git bei Pfaden mit
    Leerzeichen anhängt, und ohne C-Quoting (`"b/\\303\\244.py"` → `b/ä.py`)."""
    raw = raw[:-1] if raw.endswith("\t") else raw
    if len(raw) < 2 or raw[0] != '"' or raw[-1] != '"':
        return raw
    data = raw[1:-1].encode("utf-8", errors="surrogateescape")
    out = bytearray()
    i = 0
    while i < len(data):
        byte = data[i]
        if byte != 0x5C or i + 1 >= len(data):
            out.append(byte)
            i += 1
        elif 0x30 <= data[i + 1] <= 0x37:
            out.append(int(data[i + 1:i + 4], 8) & 0xFF)
            i += 4
        else:
            out.append(_C_ESCAPES.get(data[i + 1], data[i + 1]))
            i += 2
    return out.decode("utf-8", errors="surrogateescape")


def _changed_lines(repo: Path, span: Span, files) -> dict:
    """Geänderte Zeilen am ZIEL je Datei: `git diff -U0 BASIS ZIEL -- <dateien>` (Pathspecs in
    Stücken), ohne Umbenennungen, externe Diffs, Textconv und Farbe, mit festen Präfixen
    `a/` `b/` gegen `diff.noprefix`. Eine reine Löschung ändert keine Zeile am ZIEL; eine
    gelöschte Datei fehlt."""
    changed: dict[str, set] = {}
    for chunk in _literal_chunks(files):
        out = _git(repo, "diff", "-U0", "--no-renames", "--no-ext-diff", "--no-textconv",
                   "--no-color", "--src-prefix=a/", "--dst-prefix=b/", span.base, span.target,
                   "--", *chunk)
        current, header = None, False
        for line in out.split("\n"):
            if line.startswith("diff --git "):
                current, header = None, True
            elif header and line.startswith("+++ "):
                name = _unquote_path(line[4:])
                current = name[2:] if name.startswith("b/") else None
            elif line.startswith("@@"):
                header = False
                match = HUNK_RE.match(line)
                if match and current is not None:
                    start, count = int(match.group(1)), int(match.group(2) or 1)
                    if count:
                        changed.setdefault(current, set()).update(range(start, start + count))
    return changed


def _is_python(path: str) -> bool:
    """Python-Datei nach Endung, ohne Rücksicht auf Groß/Klein — wie `_has_collector`."""
    return PurePosixPath(path).suffix.lower() == ".py"


def _link_dest(path: str, raw: bytes):
    """Ziel eines Symlinks `path` im Repo (normalisiert, relativ zur Wurzel) oder None, wenn es
    absolut ist oder aus dem Repo hinausführt."""
    dest = raw.decode("utf-8", errors="surrogateescape")
    if not dest or dest.startswith("/"):
        return None
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(path), dest))
    return None if joined == ".." or joined.startswith("../") else joined


def _python_sources(repo: Path, target: str, links: dict | None = None) -> tuple[dict, dict]:
    """(Pfad → Bytes aller Python-Blobs am ZIEL, Pfad → Grund der übersprungenen), gelesen aus
    Git (`ls-tree`, `cat-file --batch` als Bytes), nie aus dem Arbeitsbaum. Ohne `.skills/`;
    im zweiten Dict stehen Einträge, die im Baum liegen, aber nicht gelesen werden: Symlinks
    (`SKIP_SYMLINK`), Pfade, die kein UTF-8 sind (`SKIP_NOT_UTF8`), und Submodule mit
    `.py`-Namen (`SKIP_GITLINK`). Ein übergebenes Dict `links` bekommt je Symlink sein Ziel
    im Repo (`_link_dest`, None ohne)."""
    return _tree_sources(repo, target, _is_python, links)


def _tree_sources(repo: Path, target: str, accept, links: dict | None = None) -> tuple[dict, dict]:
    """Wie `_python_sources`, für die Pfade, die `accept(pfad)` annimmt (Python, Delphi)."""
    blobs, skipped = [], {}
    for record in _git(repo, "ls-tree", "-r", "-z", "--full-tree", target).split("\0"):
        if not record:
            continue
        info, path = record.split("\t", 1)
        mode, kind, sha = info.split()
        if not accept(path) or _under_skills(path):
            continue
        if kind == "commit":
            skipped[path] = SKIP_GITLINK
        elif kind != "blob":
            continue
        elif not _is_utf8(path):
            skipped[path] = SKIP_NOT_UTF8
        elif mode == "120000":
            skipped[path] = SKIP_SYMLINK
            if links is not None:
                blobs.append((path, sha, True))
        else:
            blobs.append((path, sha, False))
    if not blobs:
        return {}, skipped
    feed = "".join(f"{sha}\n" for _, sha, _link in blobs).encode("ascii")
    data = _git_bytes(repo, "cat-file", "--batch", stdin=feed)
    sources, pos = {}, 0
    for path, _sha, is_link in blobs:
        end = data.index(b"\n", pos)
        fields = data[pos:end].split()
        if len(fields) != 3:
            raise KitError(f"git cat-file: unerwartete Antwort für {path}: {data[pos:end]!r}")
        size = int(fields[2])
        content = data[end + 1:end + 1 + size]
        if is_link:
            links[path] = _link_dest(path, content)
        else:
            sources[path] = content
        pos = end + 1 + size + 1
    return sources, skipped


def _walk_defs(tree):
    """Definitionen auf Modulebene und Methoden von Klassen auf Modulebene: (Klasse, Knoten)."""
    for node in tree.body:
        if isinstance(node, (*_FUNCS, ast.ClassDef)):
            yield None, node
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, _FUNCS):
                    yield node.name, item


class _PyIndex:
    """Alle Definitionen am ZIEL: Name → [(datei, qualname, knoten)]; Bäume je Datei;
    Python-Dateien ohne Baum in `unreadable` (Pfad → Grund: `Syntaxfehler`, `Symlink`,
    `Pfad nicht UTF-8`, Submodul) — übersprungen und gezählt. `links` hält je Symlink sein
    Ziel im Repo (None: keins), `raises_memo` die raise-Stellen je Definition, `source` die
    Bytes je Datei für Zeilen aus dem Quelltext."""

    def __init__(self, sources: dict, skipped: dict | None = None,
                 links: dict | None = None) -> None:
        self.trees: dict[str, ast.Module] = {}
        self.defs: dict[str, list] = {}
        self.unreadable: dict[str, str] = dict(skipped or {})
        self.links: dict[str, str | None] = dict(links or {})
        self.raises_memo: dict[tuple, list] = {}
        self.source: dict[str, bytes] = {}
        self._lines: dict[str, list] = {}
        self._prefixes: dict[str, set] = {}
        for rel in sorted(sources):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    tree = ast.parse(sources[rel], filename=rel)
            except (SyntaxError, ValueError, RecursionError, MemoryError):
                self.unreadable[rel] = SKIP_SYNTAX
                continue
            self.trees[rel] = tree
            self.source[rel] = sources[rel]
            for cls, node in _walk_defs(tree):
                qual = f"{cls}.{node.name}" if cls else node.name
                self.defs.setdefault(node.name, []).append((rel, qual, node))

    def not_indexed(self) -> dict:
        """Python-Dateien am ZIEL, in denen keine Gegenstelle gesucht wird (Pfad → Grund):
        `unreadable` ohne Submodule (keine Python-Dateien) und ohne Symlinks, deren Ziel —
        auch über weitere Symlinks — im Index steht; deren Definitionen sind unter dem Ziel
        schon gesucht."""
        out = {}
        for rel, reason in self.unreadable.items():
            if reason == SKIP_GITLINK:
                continue
            if reason == SKIP_SYMLINK and self._link_target(rel) in self.trees:
                continue
            out[rel] = reason
        return out

    def _link_target(self, rel: str):
        """Endziel eines Symlinks im Repo; None bei Zyklus oder Ziel außerhalb."""
        seen = set()
        while rel in self.links:
            if rel in seen:
                return None
            seen.add(rel)
            rel = self.links[rel]
            if rel is None:
                return None
        return rel

    def _utf8_lines(self, rel: str) -> list:
        """Zeilen einer Datei als UTF-8-Bytes, so wie `ast` sie misst: dekodiert nach
        Coding-Cookie bzw. BOM (`tokenize.detect_encoding`, `utf-8-sig` ohne BOM) und neu als
        UTF-8 kodiert — die Spalten der Knoten sind UTF-8-Offsets in der dekodierten Zeile.
        Getrennt nur an `\\n`, `\\r\\n`, `\\r` wie im Parser."""
        lines = self._lines.get(rel)
        if lines is None:
            raw = self.source.get(rel, b"")
            try:
                encoding = tokenize.detect_encoding(io.BytesIO(raw).readline)[0]
                text = raw.decode(encoding)
            except (SyntaxError, LookupError, UnicodeDecodeError):
                text = raw.decode("utf-8", errors="replace")
            lines = self._lines[rel] = text.encode("utf-8", errors="replace").splitlines()
        return lines

    def segment(self, rel: str, node) -> str:
        """Erste Zeile von `node` aus dem Quelltext, ab seiner Spalte (bei einzeiligen Knoten
        bis zu ihrem Ende), höchstens `DOC_CHARS` Zeichen — ohne `ast.unparse` des Knotens."""
        lines = self._utf8_lines(rel)
        if not 0 < node.lineno <= len(lines):
            return ""
        raw = lines[node.lineno - 1]
        end = node.end_col_offset if node.end_lineno == node.lineno else None
        text = raw[node.col_offset:end].decode("utf-8", errors="replace").strip()
        return text if len(text) <= DOC_CHARS else text[:DOC_CHARS] + "…"

    def column(self, rel: str, node) -> int:
        """Spalte von `node` in Zeichen, 1-basiert (wie `datei:zeile:spalte` in Compilern)."""
        lines = self._utf8_lines(rel)
        if not 0 < node.lineno <= len(lines):
            return node.col_offset + 1
        return len(lines[node.lineno - 1][:node.col_offset].decode("utf-8", errors="replace")) + 1

    def module_file(self, module):
        """Datei zu einem Modulpfad `a.b.c` (auch unter `src/`), sonst None."""
        if not module:
            return None
        base = module.replace(".", "/")
        for cand in (f"src/{base}.py", f"src/{base}/__init__.py", f"{base}.py",
                     f"{base}/__init__.py"):
            if cand in self.trees:
                return cand
        return None

    def import_prefixes(self, rel: str) -> set:
        """Dateien und Pakete (`pkg/`), aus denen `rel` Namen bezieht — der spezifischste
        Importpfad: `from a.b import C` nimmt `a/b/C.py`, wenn es die gibt, sonst `a/b.py`
        bzw. das Paket `a/b/`. Relative Importe gelten vom Paket der Datei aus."""
        if rel in self._prefixes:
            return self._prefixes[rel]
        out: set[str] = set()
        tree = self.trees.get(rel)

        def add(found):
            if found:
                out.add(found.rsplit("/", 1)[0] + "/" if found.endswith("__init__.py") else found)

        for node in ast.walk(tree) if tree is not None else ():
            if isinstance(node, ast.ImportFrom):
                module = _from_module(rel, node)
                for alias in node.names:
                    add(self.module_file(f"{module}.{alias.name}" if module else alias.name)
                        or self.module_file(module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "." in alias.name:
                        add(self.module_file(alias.name))
        self._prefixes[rel] = out
        return out

    def resolve(self, name: str, from_file: str):
        """(Definitionen, mehrdeutig) zu einem Namen: bevorzugt die eigene Datei, dann die
        importierten Dateien und Pakete; ohne Importbezug und mit mehr als `AMBIGUOUS_MAX`
        Kandidaten keine — `mehrdeutig` wahr."""
        cands = self.defs.get(name, [])
        if not cands:
            return [], False
        prefixes = self.import_prefixes(from_file)

        def rank(cand):
            rel = cand[0]
            if rel == from_file:
                return 0
            if any(rel == p or (p.endswith("/") and rel.startswith(p)) for p in prefixes):
                return 1
            return 2

        ranked = sorted(cands, key=rank)
        best = rank(ranked[0])
        if best == 2 and len(cands) > AMBIGUOUS_MAX:
            return [], True
        return [c for c in ranked if rank(c) == best][:COUNTERPART_MAX_DEFS], False

    def resolve_call(self, call: ast.Call, from_file: str):
        """Wie `resolve`, aber ein voll qualifizierter Modulpfad (`a.b.C(...)`) entscheidet
        zuerst."""
        name = _callee_name(call)
        if isinstance(call.func, ast.Attribute):
            module = _dotted(call.func.value)
            found = self.module_file(module) if module and "." in module else None
            if found:
                exact = [c for c in self.defs.get(name, []) if c[0] == found]
                if exact:
                    return exact[:COUNTERPART_MAX_DEFS], False
        return self.resolve(name or "", from_file)


def _from_module(rel: str, node: ast.ImportFrom):
    """Absoluter Modulpfad eines `from … import`; relative Importe vom Paket der Datei aus."""
    if not node.level:
        return node.module
    parts = PurePosixPath(rel).parent.parts
    if node.level - 1 > len(parts):
        return None
    package = list(parts[:len(parts) - (node.level - 1)])
    if node.module:
        package.append(node.module)
    return ".".join(package) or None


def _callee_name(call: ast.Call):
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


@functools.lru_cache(maxsize=INDEX_CACHE_SIZE)
def _python_index(repo: Path, target: str) -> _PyIndex:
    """Definitions-Index am ZIEL, je (Repo, SHA) einmal gebaut — `target` ist ein SHA, der
    Index also unveränderlich."""
    links: dict = {}
    sources, skipped = _python_sources(repo, target, links)
    return _PyIndex(sources, skipped, links)


def _target_def(node):
    """Was ein Aufruf erreicht: bei einer Klasse ihr `__init__` (None ohne), sonst die
    Funktion selbst."""
    if isinstance(node, ast.ClassDef):
        return next((b for b in node.body if isinstance(b, _FUNCS) and b.name == "__init__"),
                    None)
    return node


def _signature(node) -> str:
    if isinstance(node, ast.ClassDef):
        bases = [ast.unparse(b) for b in node.bases] + [ast.unparse(k) for k in node.keywords]
        head = f"class {node.name}" + (f"({', '.join(bases)})" if bases else "")
        init = _target_def(node)
        return f"{head}: {_signature(init)}" if init is not None else head
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({ast.unparse(node.args)})"


def _raises_in(index: _PyIndex, rel: str, node, depth: int, seen: set) -> list:
    """(Typ, Zeile) aller `raise` in `node`, transitiv über Aufrufe von Funktionen desselben
    Moduls bis `depth` Ebenen tief."""
    key = (rel, node.lineno)
    if key in seen:
        return []
    seen.add(key)
    out = []
    for item in ast.walk(node):
        if isinstance(item, ast.Raise) and item.exc is not None:
            exc = item.exc.func if isinstance(item.exc, ast.Call) else item.exc
            out.append((ast.unparse(exc), item.lineno))
        elif depth > 0 and isinstance(item, ast.Call):
            for drel, _qual, dnode in index.defs.get(_callee_name(item) or "", []):
                if drel == rel and isinstance(dnode, _FUNCS):
                    out += _raises_in(index, rel, dnode, depth - 1, seen)
    return out


def _raises(index: _PyIndex, rel: str, node) -> list:
    """raise-Stellen einer Definition (Tiefe `RAISE_DEPTH`), nach Zeile, ohne Doppelte — je
    Definition einmal berechnet (`index.raises_memo`)."""
    if node is None:
        return []
    key = (rel, node.lineno, node.col_offset)
    if key not in index.raises_memo:
        found = _raises_in(index, rel, node, RAISE_DEPTH, set())
        index.raises_memo[key] = sorted(set(found), key=lambda r: (r[1], r[0]))
    return index.raises_memo[key]


def _param_flow(index: _PyIndex, rel: str, fn, param: str, depth: int, seen: set,
                unresolved: set) -> list:
    """Wo landet ein Parameter: Bedingungen, die ihn prüfen, und Weitergaben als
    Schlüsselwort an aufgelöste Gegenstellen (rekursiv, `depth` Funktionen tief). Endet der
    Weg an einer mehrdeutigen Gegenstelle, zählt die Weitergabe in `unresolved`."""
    if depth == 0 or (rel, fn.lineno, param) in seen:
        return []
    seen.add((rel, fn.lineno, param))
    lines = []
    for item in ast.walk(fn):
        if isinstance(item, (ast.If, ast.IfExp, ast.While)) and any(
                isinstance(x, ast.Name) and x.id == param for x in ast.walk(item.test)):
            body = item.body if isinstance(item.body, list) else [item.body]
            first = index.segment(rel, body[0]) if body else ""
            lines.append(f"{rel}:{item.lineno}: if {ast.unparse(item.test)}: {first}")
        if isinstance(item, ast.Call):
            for kw in item.keywords:
                if isinstance(kw.value, ast.Name) and kw.value.id == param and kw.arg:
                    defs, ambiguous = index.resolve_call(item, rel)
                    if ambiguous:
                        unresolved.add((rel, item.lineno, item.col_offset))
                    for drel, qual, dnode in defs:
                        if isinstance(dnode, _FUNCS):
                            lines.append(f"{rel}:{item.lineno}: {param} -> {qual}({kw.arg}=...) "
                                         f"[{drel}:{dnode.lineno}]")
                            lines += _param_flow(index, drel, dnode, kw.arg, depth - 1, seen,
                                                 unresolved)
    return lines


def _counterpart_head(drel: str, qual: str, node, raises: list) -> list:
    """`- Gegenstelle …`, erste Docstring-Zeile, `wirft:` und die raise-Zeilen."""
    lines = [f"- Gegenstelle {qual} [{drel}:{node.lineno}]: {_signature(node)}"]
    doc = ast.get_docstring(node)
    if doc and doc.strip():
        lines.append("  Doc: " + doc.strip().splitlines()[0].strip()[:DOC_CHARS])
    if raises:
        lines.append("  wirft: " + ", ".join(sorted({t for t, _ in raises})))
        lines += [f"    raise {t} at {drel}:{n}" for t, n in raises[:RAISE_LINES_MAX]]
    return lines


def _touches(changed: list, start: int, end: int) -> bool:
    """Liegt eine der sortierten geänderten Zeilen in `start..end` (inklusiv)? Per Bisektion,
    ohne die Zeilen des Bereichs aufzuzählen."""
    pos = bisect.bisect_left(changed, start)
    return pos < len(changed) and changed[pos] <= end


def _handler_span(handler: ast.ExceptHandler) -> tuple[int, int]:
    end = handler.type.end_lineno if handler.type is not None else handler.lineno
    return handler.lineno, end


def _python_sites(index: _PyIndex, rel: str, tree, lines: set, unresolved: set) -> list:
    """Die Stellen einer Datei nach der Sammelregel (Spec 26, Schritt 3). Je Aufruf ein
    Eintrag (zwei Aufrufe derselben Funktion auf einer Zeile behalten je ihre geänderten
    Argumente); ein Eintrag, der einem früheren derselben Zeile gleicht, entfällt. Bleiben auf
    einer Zeile mehrere Einträge für denselben Namen, trägt ihre Überschrift die Spalte des
    Aufrufs: `### <datei>:<zeile>:<spalte> ruft <name>(...)` (Zeichen, 1-basiert)."""
    entries = []
    shown = set()
    calls: dict[tuple, list] = {}
    changed = sorted(lines)
    for node in ast.walk(tree):
        # geänderte except-Klausel: was können die Aufrufe im try-Block werfen?
        if isinstance(node, _TRIES):
            for handler in node.handlers:
                if not _touches(changed, *_handler_span(handler)):
                    continue
                found, reached = [], set()
                for stmt in node.body:
                    for call in ast.walk(stmt):
                        if not isinstance(call, ast.Call):
                            continue
                        defs, ambiguous = index.resolve_call(call, rel)
                        if ambiguous:
                            unresolved.add((rel, call.lineno, call.col_offset))
                        for drel, qual, dnode in defs:
                            raises = _raises(index, drel, _target_def(dnode))
                            if raises and (drel, dnode.lineno) not in reached:
                                reached.add((drel, dnode.lineno))
                                found.append(_counterpart_head(drel, qual, dnode, raises))
                if found:
                    caught = ast.unparse(handler.type) if handler.type is not None else "alles"
                    entries.append({"file": rel, "line": handler.lineno, "kind": "except",
                                    "lines": [f"### {rel}:{handler.lineno} except {caught}",
                                              *(x for part in found for x in part)]})
        if not isinstance(node, ast.Call) or not _touches(changed, node.lineno, node.end_lineno):
            continue
        name = _callee_name(node)
        if not name:
            continue
        defs, ambiguous = index.resolve_call(node, rel)
        if ambiguous:
            unresolved.add((rel, node.lineno, node.col_offset))
        if not defs:
            continue
        changed_kw = [kw for kw in node.keywords if kw.arg and _touches(
            changed, kw.lineno, kw.value.end_lineno)]
        body, throws = [], False
        for drel, qual, dnode in defs:
            target = _target_def(dnode)
            raises = _raises(index, drel, target)
            throws = throws or bool(raises)
            body += _counterpart_head(drel, qual, dnode, raises)
            if target is None:
                continue
            for kw in changed_kw:
                flow = _param_flow(index, drel, target, kw.arg, FLAG_DEPTH, set(), unresolved)
                if flow:
                    body.append(f"  geändert: {kw.arg}={ast.unparse(kw.value)}; Weg:")
                    body += [f"    {x}" for x in flow[:FLOW_LINES_MAX]]
        key = (node.lineno, name, tuple(body))
        if (changed_kw or throws) and key not in shown:
            shown.add(key)
            entry = {"file": rel, "line": node.lineno, "kind": "call",
                     "lines": [f"### {rel}:{node.lineno} ruft {name}(...)", *body]}
            entries.append(entry)
            calls.setdefault((node.lineno, name), []).append((entry, index.column(rel, node)))
    for (line, name), group in calls.items():
        if len(group) > 1:
            for entry, col in group:
                entry["lines"][0] = f"### {rel}:{line}:{col} ruft {name}(...)"
    return entries


def collect_python(repo, rng, files):
    """Gegenstellen der geänderten Python-Zeilen (Spec 26, Ablauf Schritt 3).

    `rng` wie bei `numstat` (`BASIS..ZIEL`, eine Revision, ein Paket-Bereich `von..bis`);
    `files` die Dateien, deren Stellen gesammelt werden — gezählt nur `.py` außerhalb von
    `.skills/`. Geänderte Zeilen aus `git diff -U0` über den Bereich, beschränkt auf `files`;
    der Code — die geänderten Dateien wie der Index aller Definitionen — kommt per `ast` aus
    dem Baum des ZIELS in Git, nie aus dem Arbeitsbaum, und wird nie importiert. Je Aufruf
    auf einer geänderten Zeile die erreichte Definition (aufgelöst über die Importe der Datei
    und voll qualifizierte Modulpfade, auch in vendortem Code), Signatur, erste
    Docstring-Zeile und raise-Stellen transitiv im selben Modul (`RAISE_DEPTH`); je
    geänderter `except`-Klausel die Ausnahmen der Aufrufe im try-Block; je geändertem
    Schlüsselwort-Argument sein Weg bis zu den Bedingungen (`FLAG_DEPTH`). Eine Stelle steht
    im Ergebnis, wenn eine ihrer Definitionen etwas wirft oder sie ein geändertes
    Schlüsselwort-Argument hat. Rückgabe: `Collected(entries, unresolved, unparsed)`."""
    repo = _toplevel(repo)
    wanted = sorted({str(f) for f in files if _is_python(str(f)) and not _under_skills(str(f))})
    if not wanted:
        return Collected([], 0, [])
    span = split_range(repo, rng)
    index = _python_index(repo, span.target)
    unresolved: set = set()
    entries = []
    unparsed = {rel: index.unreadable[rel] for rel in wanted if rel in index.unreadable}
    for rel, lines in sorted(_changed_lines(repo, span, wanted).items()):
        tree = index.trees.get(rel)
        if tree is not None:
            entries += _python_sites(index, rel, tree, lines, unresolved)
        elif rel not in unparsed:
            unparsed[rel] = NOT_IN_TARGET
    entries.sort(key=lambda e: (e["file"], e["line"], e["kind"]))
    return Collected(entries, len(unresolved), sorted(unparsed.items()))


# --- Gegenstellen für Delphi (Text-Scanner) -------------------------------------------------
#
# Kein Parser: `mask_pascal` blendet Strings und Kommentare aus (Zeilen und Spalten bleiben),
# danach zählt ein Token-Scanner Blöcke (`begin`/`case`/`try`/`asm`/`record` und Klassenrümpfe
# gegen `end`). Bezeichner ohne Rücksicht auf Groß/Klein. Gesucht wird in der eigenen Unit und
# in den Units ihrer `uses`-Listen; wie in Delphi verdeckt die zuletzt genannte Unit die
# früheren. Was der Scanner nicht sicher zuordnen kann, steht nicht im Block.

DELPHI_SUFFIXES = frozenset({".pas", ".dpr", ".dpk"})
DELPHI_RELEASES = frozenset({"extract", "remove", "free", "freeandnil", "setcontentstream"})
CLASS_CHAIN_MAX = 4        # Klassen je Empfängertyp im Block (die Klasse und ihre Basisklassen)
INHERITED_LINES_MAX = 4    # inherited-Zeilen je Klasse
OWNERSHIP_RTL = {          # Besitz-Default der RTL je Basisklasse (Schlüssel klein, ohne <…>)
    "tobjectlist": "TObjectList<…>: OwnsObjects standardmäßig wahr (Create(AOwnsObjects: "
                   "Boolean = True)) — Remove, Delete und Clear geben Elemente frei, Extract "
                   "nicht",
    "tobjectdictionary": "TObjectDictionary<…>: Besitz nur nach Ownerships im Konstruktor "
                         "(doOwnsKeys, doOwnsValues; das geerbte Create ohne sie besitzt "
                         "nichts) — Remove und Clear geben Besitztes frei, ExtractPair nicht",
}
_PAS_SPECIAL = re.compile(r"[{('/]")
_PAS_EOL = re.compile(r"[\r\n]")
_PAS_NOT_BLANK = re.compile(r"[^\r\n]")
_PAS_MULTILINE_END = re.compile(r"\n[ \t]*'''")
_PAS_TOKEN = re.compile(r"&?[^\W\d]\w*|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\$[0-9A-Fa-f]+|:=|\.\.|<>"
                        r"|<=|>=|\S")
_PAS_IDENT = re.compile(r"&?[^\W\d]\w*")
_PAS_SPACE = re.compile(r"\s+")
_PAS_TYPE_HEAD = re.compile(r"\s*&?([^\W\d][\w.]*)")
_PAS_QUOTED = re.compile(r"'([^']*)'")
_PAS_ROUTINES = frozenset({"procedure", "function", "constructor", "destructor", "operator"})
_PAS_STRUCTS = frozenset({"class", "record", "object", "interface", "dispinterface"})
# Vor einem Routinen-Wort steht bei einem Prozedurtyp oder einer anonymen Methode eines davon.
_PAS_TYPE_PREV = frozenset({"=", "to", ":", "of", "(", ",", ":="})
_PAS_PARAM_MODS = frozenset({"const", "var", "out", "constref"})
_PAS_DIRECTIVES = frozenset({
    "overload", "inline", "stdcall", "cdecl", "register", "pascal", "safecall", "winapi",
    "static", "virtual", "override", "reintroduce", "dynamic", "abstract", "final",
    "assembler", "platform", "deprecated", "experimental", "library", "varargs", "local",
    "message", "dispid", "export", "far", "near", "unsafe", "forward", "external", "noreturn"})
_PAS_KEYWORDS = frozenset({
    "and", "array", "as", "asm", "at", "begin", "case", "class", "const", "constructor",
    "destructor", "dispinterface", "div", "do", "downto", "else", "end", "except", "exports",
    "file", "finalization", "finally", "for", "function", "goto", "if", "implementation", "in",
    "inherited", "initialization", "inline", "interface", "is", "label", "library", "mod",
    "nil", "not", "object", "of", "on", "operator", "or", "packed", "procedure", "program",
    "property", "raise", "record", "repeat", "resourcestring", "set", "shl", "shr", "string",
    "then", "threadvar", "to", "try", "type", "unit", "until", "uses", "var", "while", "with",
    "xor"})
_PAS_NOT_TYPES = frozenset({"array", "set", "file", "packed", "procedure", "function",
                            "reference", "record", "class", "string"})
_PAS_PROPERTY_STOP = frozenset({"read", "write", "default", "nodefault", "stored", "index",
                                "implements", "readonly", "writeonly", "dispid", ";"})


def _pas_eol(text: str, pos: int) -> int:
    match = _PAS_EOL.search(text, pos)
    return match.start() if match else len(text)


def _pas_string_end(text: str, pos: int) -> int:
    """Ende des String-Literals ab dem `'` bei `pos`: `''` ist ein Anführungszeichen im
    String, ein String endet spätestens am Zeilenende; `'''` allein am Zeilenende öffnet einen
    mehrzeiligen String (Delphi 12), der an einer Zeile endet, die mit `'''` beginnt."""
    eol = _pas_eol(text, pos)
    if text.startswith("'''", pos) and not text[pos + 3:eol].strip():
        match = _PAS_MULTILINE_END.search(text, eol)
        return match.end() if match else len(text)
    j = pos + 1
    while True:
        k = text.find("'", j, eol)
        if k < 0:
            return eol
        if k + 1 < eol and text[k + 1] == "'":
            j = k + 2
            continue
        return k + 1


def _pas_mask(text: str, strings: bool) -> str:
    """Kommentare (`{ }`, `(* *)`, `//`) und, mit `strings`, String-Literale durch Leerzeichen
    ersetzt; Zeilenumbrüche bleiben, also auch Zeilen und Spalten."""
    pieces, pos, i, n = [], 0, 0, len(text)
    while True:
        match = _PAS_SPECIAL.search(text, i)
        if match is None:
            break
        i = match.start()
        char = text[i]
        if char == "{":
            j = text.find("}", i + 1)
            j = n if j < 0 else j + 1
        elif char == "(" or char == "/":
            if not text.startswith("(*" if char == "(" else "//", i):
                i += 1
                continue
            if char == "/":
                j = _pas_eol(text, i)
            else:
                j = text.find("*)", i + 2)
                j = n if j < 0 else j + 2
        else:
            j = _pas_string_end(text, i)
            if not strings:
                i = j
                continue
        pieces.append(text[pos:i])
        pieces.append(_PAS_NOT_BLANK.sub(" ", text[i:j]))
        pos = i = j
    pieces.append(text[pos:])
    return "".join(pieces)


def mask_pascal(text):
    """Object-Pascal-Quelltext mit ausgeblendeten `'…'`-Strings (auch `''` darin und
    mehrzeilige `'''`-Strings), `{ }`-, `(* *)`- und `//`-Kommentaren: jedes Zeichen darin
    wird ein Leerzeichen, Zeilenumbrüche bleiben — gleiche Länge, gleiche Zeilen und Spalten.
    Ein `end` in einem String oder Kommentar verschiebt so keinen Block. Compiler-Direktiven
    `{$…}` sind Kommentare und verschwinden mit."""
    return _pas_mask(str(text), strings=True)


def _pas_text(raw: bytes) -> str:
    """Quelltext einer Delphi-Datei: UTF-8 mit BOM, UTF-16 mit BOM, UTF-8, sonst Windows-1252
    (der Standard älterer Delphi-Projekte)."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace")
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _is_delphi(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in DELPHI_SUFFIXES


def _type_key(type_text):
    """Klassenname eines Typs, klein, ohne Unit-Präfix und ohne `<…>` — None ohne Namen."""
    match = _PAS_TYPE_HEAD.match(type_text or "")
    if not match:
        return None
    key = match.group(1).split(".")[-1].lower()
    return None if key in _PAS_NOT_TYPES else key


class _Tok(NamedTuple):
    low: str      # Bezeichner klein und ohne `&`, sonst das Zeichen selbst
    start: int
    end: int
    line: int
    ident: bool


class _PasHead:
    """Routinenkopf: Art, Name (Teile wie geschrieben), Parameter (klein → Typtext oder None),
    ob ein Parameter einen Default hat, Rückgabetyp, Signatur ohne `;`, Index des `;`."""
    __slots__ = ("kind", "parts", "low", "cls", "qual", "line", "params", "defaults", "ret",
                 "sig", "end")


class _PasClass:
    """Klassen-, Objekt- oder Record-Deklaration: Felder und Properties (klein → Typtext),
    Methodenköpfe (klein → [_PasHead]), Basisklasse als Schlüssel (`_type_key`)."""
    __slots__ = ("name", "low", "line", "sig", "parent", "fields", "methods")

    def __init__(self, name: str, line: int, sig: str, parent) -> None:
        self.name, self.low, self.line, self.sig, self.parent = name, name.lower(), line, sig, parent
        self.fields: dict[str, str] = {}
        self.methods: dict[str, list] = {}


class _PasImpl:
    """Implementierung einer Routine: Kopf, Rumpf `begin`…`end` als Token-Indizes, Variablen
    aus `var`-Abschnitten und Inline-`var`, umschließende Routine bei geschachtelten."""
    __slots__ = ("head", "outer", "begin", "stop", "end_line", "vars")

    def __init__(self, head: _PasHead, outer) -> None:
        self.head, self.outer = head, outer
        self.begin = self.stop = self.end_line = None
        self.vars: dict[str, str] = {}

    def top(self):
        impl = self
        while impl.outer is not None:
            impl = impl.outer
        return impl


class _PasUnit:
    """Eine Delphi-Datei, gescannt: `uses`-Listen (interface und implementation, auch
    `in '…'`), Klassen, Köpfe im interface-Teil, Implementierungen."""

    def __init__(self, rel: str, text: str) -> None:
        self.rel, self.text = rel, text
        self.clean = _pas_mask(text, strings=False)
        masked = _pas_mask(self.clean, strings=True)
        self.newlines = [m.start() for m in re.finditer("\n", text)]
        toks = []
        for match in _PAS_TOKEN.finditer(masked):
            word = match.group()
            ident = bool(_PAS_IDENT.fullmatch(word))
            toks.append(_Tok(word.lstrip("&").lower() if ident else word, match.start(),
                             match.end(), bisect.bisect_right(self.newlines, match.start()) + 1,
                             ident))
        self.toks = toks
        self.tok_lines = [t.line for t in toks]
        self.name = PurePosixPath(rel).stem.lower()
        self.uses: list[tuple] = []
        self.classes: dict[str, _PasClass] = {}
        self.decls: dict[str, list] = {}
        self.impls: list[_PasImpl] = []
        self.by_name: dict[str, list] = {}
        self._parse()

    # -- Hilfen über die Tokens
    def _t(self, j: int) -> str:
        return self.toks[j].low if 0 <= j < len(self.toks) else ""

    def _ident(self, j: int) -> bool:
        return 0 <= j < len(self.toks) and self.toks[j].ident

    def _word(self, j: int) -> str:
        tok = self.toks[j]
        return self.text[tok.start:tok.end].lstrip("&")

    def _text(self, start: int, end: int) -> str:
        """Quelltext ohne Kommentare, Leerraum zu einem Leerzeichen."""
        return _PAS_SPACE.sub(" ", self.clean[start:end]).strip()

    def _close(self, j: int) -> int:
        """Index der Klammer, die `(` oder `[` bei `j` schließt."""
        depth = 0
        for k in range(j, len(self.toks)):
            low = self.toks[k].low
            if low in ("(", "["):
                depth += 1
            elif low in (")", "]"):
                depth -= 1
                if depth == 0:
                    return k
        return len(self.toks) - 1

    def _close_angle(self, j: int) -> int:
        depth = 0
        for k in range(j, len(self.toks)):
            low = self.toks[k].low
            if low == "<":
                depth += 1
            elif low == ">":
                depth -= 1
                if depth == 0:
                    return k
            elif low in (";", "(", ")", ":=", "begin"):
                return k - 1
        return len(self.toks) - 1

    def _stmt_end(self, j: int) -> int:
        """Index des nächsten `;` außerhalb von Klammern."""
        depth = 0
        for k in range(j, len(self.toks)):
            low = self.toks[k].low
            if low in ("(", "["):
                depth += 1
            elif low in (")", "]"):
                depth -= 1
            elif low == ";" and depth <= 0:
                return k
        return len(self.toks) - 1

    def column(self, tok: _Tok) -> int:
        line_start = self.newlines[tok.line - 2] + 1 if tok.line > 1 else 0
        return tok.start - line_start + 1

    # -- Struktur
    def _structural(self, j: int) -> bool:
        """Steht `class`/`record`/… bei `j` für einen Typ (nach `=`, `packed`, bei `record`
        auch nach `:` und `of`) — nicht `class function`, `of object`, Unit-`interface`?"""
        low, prev = self._t(j), self._t(j - 1)
        if low == "record":
            return prev in ("=", ":", "of", "packed")
        return low in _PAS_STRUCTS and prev in ("=", "packed")

    def _struct_head(self, j: int):
        """(Index des Rumpfs oder None ohne Rumpf, Index danach, Basisliste (von, bis) oder
        None) für den Typ bei `j`."""
        low, k = self._t(j), j + 1
        if low == "class" and self._t(k) == "of":
            return None, k + 1, None
        while self._t(k) in ("sealed", "abstract"):
            k += 1
        if self._t(k) == "helper":
            k += 1
            if self._t(k) == "(":
                k = self._close(k) + 1
            if self._t(k) == "for":
                k += 1
                while self._ident(k) or self._t(k) == ".":
                    k += 1
            return k, k, None
        base = None
        if low != "record" and self._t(k) == "(":
            close = self._close(k)
            base, k = (k, close), close + 1
        if low != "record" and self._t(k) == ";":
            return None, k, base
        return k, k, base

    def _block_end(self, j: int) -> int:
        """Index des `end`, das den Block ab `j` schließt: `begin`, `try`, `case` (nicht im
        varianten Teil eines Records), `asm` (bis zum nächsten `end`), Typrümpfe."""
        toks, n, stack, k = self.toks, len(self.toks), [], j
        while k < n:
            low = toks[k].low
            if low == "asm":
                e = k + 1
                while e < n and toks[e].low != "end":
                    e += 1
                if not stack:
                    return min(e, n - 1)
                k = e + 1
                continue
            if low in ("begin", "try") or (low == "case" and (not stack or stack[-1] != "record")):
                stack.append(low)
            elif low in _PAS_STRUCTS and self._structural(k):
                body, after, _base = self._struct_head(k)
                if body is None:
                    k = after
                    continue
                stack.append("record" if low == "record" else "class")
                k = body
                continue
            elif low == "end":
                if stack:
                    stack.pop()
                if not stack:
                    return k
            k += 1
        return n - 1

    def _parse(self) -> None:
        toks, n = self.toks, len(self.toks)
        section, i = "implementation", 0
        if n and toks[0].low in ("unit", "program", "library", "package"):
            section = "head" if toks[0].low == "unit" else "implementation"
            i = self._stmt_end(0) + 1
        while i < n:
            low = toks[i].low
            if low == "interface" and section == "head":
                section = "interface"
            elif low == "implementation":
                section = "implementation"
            elif low == "uses":
                i = self._uses(i + 1)
                continue
            elif low in _PAS_STRUCTS and self._structural(i):
                i = self._struct(i)
                continue
            elif low in _PAS_ROUTINES and self._t(i - 1) not in _PAS_TYPE_PREV:
                head = self._head(i)
                if head is not None:
                    if section == "implementation":
                        i = self._impl(head, None)
                    else:
                        if head.cls is None:
                            self.decls.setdefault(head.low, []).append(head)
                        i = head.end + 1
                    continue
            i += 1

    def _uses(self, k: int) -> int:
        toks, n = self.toks, len(self.toks)
        while k < n and toks[k].low != ";":
            if not toks[k].ident:
                k += 1
                continue
            parts = [toks[k].low]
            k += 1
            while self._t(k) == "." and self._ident(k + 1):
                parts.append(toks[k + 1].low)
                k += 2
            path = None
            if self._t(k) == "in":
                stop = toks[k + 1].start if k + 1 < n else len(self.clean)
                quoted = _PAS_QUOTED.search(self.clean, toks[k].end, stop)
                path = quoted.group(1) if quoted else None
                k += 1
            self.uses.append((".".join(parts), path))
        return k + 1

    def _struct(self, i: int) -> int:
        """Typ bei `i` (nach `Name =`): als Klasse ablegen (class, object, record mit Namen);
        Index nach dem Typ."""
        body, after, base = self._struct_head(i)
        eq_i = i - 2 if self._t(i - 1) == "packed" else i - 1
        name_i = eq_i - 1
        if self._t(name_i) == ">":
            depth = 0
            while name_i >= 0:
                low = self._t(name_i)
                depth += low == ">"
                depth -= low == "<"
                name_i -= 1
                if depth == 0:
                    break
        kind = self._t(i)
        named = (self._ident(name_i) and self._t(eq_i) == "="
                 and kind in ("class", "object", "record"))
        cls = None
        if named and (body is not None or base is not None):
            sig_end = self.toks[base[1]].end if base else self.toks[i].end
            parent = None
            if base:
                depth, k, start = 0, base[0] + 1, base[0] + 1
                while k < base[1] and not (self._t(k) == "," and depth == 0):
                    depth += (self._t(k) in ("<", "(")) - (self._t(k) in (">", ")"))
                    k += 1
                if k > start:
                    parent = _type_key(self._text(self.toks[start].start, self.toks[k - 1].end))
            cls = _PasClass(self._word(name_i), self.toks[name_i].line,
                            self._text(self.toks[name_i].start, sig_end), parent)
            self.classes.setdefault(cls.low, cls)
        if body is None:
            return after
        end = self._block_end(i)
        if cls is not None and self.classes.get(cls.low) is cls:
            self._members(cls, body, end)
        return end + 1

    def _members(self, cls: _PasClass, start: int, end: int) -> None:
        toks, k = self.toks, start
        while k < end:
            low = toks[k].low
            if low in _PAS_STRUCTS and self._structural(k):
                k = self._struct(k)
                continue
            if low in _PAS_ROUTINES and self._t(k - 1) not in _PAS_TYPE_PREV:
                head = self._head(k)
                if head is not None:
                    cls.methods.setdefault(head.low, []).append(head)
                    k = head.end + 1
                    continue
            if low == "case":  # varianter Teil eines Records: `case [Name:] Typ of`
                while k < end and self._t(k) != "of":
                    if self._ident(k + 1) and self._t(k + 2) == ":" and self._t(k) == "case":
                        cls.fields[toks[k + 1].low] = self._text(toks[k + 3].start,
                                                                 toks[k + 3].end)
                    k += 1
                k += 1
                continue
            if self._t(k + 1) == ":" and self._t(k + 2) == "(":
                k += 3  # Marke eines varianten Teils `kA: (`; die Felder stehen in der Klammer
                continue
            if low == "property" and self._ident(k + 1):
                stop = min(self._stmt_end(k), end)
                j, depth = k + 2, 0
                while j < stop and not (self._t(j) == ":" and depth == 0):
                    depth += (self._t(j) == "[") - (self._t(j) == "]")
                    j += 1
                if j < stop:
                    e = j + 1
                    while e < stop and self._t(e) not in _PAS_PROPERTY_STOP:
                        e += 1
                    if e > j + 1:
                        cls.fields[toks[k + 1].low] = self._text(toks[j + 1].start,
                                                                 toks[e - 1].end)
                k = stop + 1
                continue
            if toks[k].ident and low not in _PAS_KEYWORDS and self._t(k + 1) in (",", ":"):
                decls, k = self._decls(k)
                cls.fields.update(decls)
                continue
            k += 1

    def _decls(self, k: int) -> tuple[dict, int]:
        """`A, B: Typ [= Wert];` ab `k`: (Name klein → Typtext, Index danach)."""
        toks, n = self.toks, len(self.toks)
        names = []
        while k < n and toks[k].ident and toks[k].low not in _PAS_KEYWORDS:
            names.append(toks[k].low)
            k += 1
            if self._t(k) != ",":
                break
            k += 1
        if not names or self._t(k) != ":":
            return {}, k + 1
        k += 1
        start, depth = k, 0
        while k < n:
            low = toks[k].low
            if low in ("(", "[", "<"):
                depth += 1
            elif low in (")", "]", ">"):
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and low in (";", "=", ":=", "in", "do"):
                break
            elif low in _PAS_STRUCTS and self._structural(k):
                k = self._block_end(k) + 1
                continue
            k += 1
        typ = self._text(toks[start].start, toks[k - 1].end) if k > start else ""
        depth = 0
        while k < n:
            low = toks[k].low
            if low in ("(", "["):
                depth += 1
            elif low in (")", "]"):
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and low == ";":
                k += 1
                break
            elif depth == 0 and low in ("begin", "end", "var", "const", "type", "in", "do"):
                break
            k += 1
        return ({name: typ for name in names} if typ else {}), k

    def _head(self, i: int):
        """Kopf ab dem Routinen-Wort bei `i` bis zum `;` (Direktiven danach gehören nicht
        dazu); None ohne Namen."""
        toks, n = self.toks, len(self.toks)
        start = toks[i - 1].start if self._t(i - 1) == "class" else toks[i].start
        k, parts = i + 1, []
        while self._ident(k):
            parts.append(self._word(k))
            k += 1
            if self._t(k) == "<":
                k = self._close_angle(k) + 1
            if self._t(k) == "." and self._ident(k + 1):
                k += 1
                continue
            break
        if not parts:
            return None
        head = _PasHead()
        head.kind, head.parts, head.line = toks[i].low, parts, toks[i].line
        head.low, head.qual = parts[-1].lower(), ".".join(parts)
        head.cls = parts[-2].lower() if len(parts) > 1 else None
        head.params, head.defaults, head.ret = {}, False, None
        if self._t(k) == "(":
            close = self._close(k)
            head.params, head.defaults = self._params(k + 1, close)
            k = close + 1
        if self._t(k) == ":":
            ret_start = k + 1
            while k < n and toks[k].low not in (";", "="):
                k += 1
            if k > ret_start:
                head.ret = self._text(toks[ret_start].start, toks[k - 1].end)
        while k < n and toks[k].low != ";":
            k += 1
        k = min(k, n - 1)
        head.end = k
        head.sig = self._text(start, toks[k].start if toks[k].low == ";" else toks[k].end)
        return head

    def _params(self, a: int, b: int) -> tuple[dict, bool]:
        """Parameterliste zwischen den Klammern: (Name klein → Typtext oder None, Default?)."""
        params, defaults, k = {}, False, a
        while k < b:
            g, depth = k, 0
            while g < b and not (self._t(g) == ";" and depth == 0):
                depth += (self._t(g) in ("(", "[", "<")) - (self._t(g) in (")", "]", ">"))
                g += 1
            j = k
            while j < g and (self._t(j) == "[" or self._t(j) in _PAS_PARAM_MODS):
                j = self._close(j) + 1 if self._t(j) == "[" else j + 1
            names = []
            while j < g and self._ident(j):
                names.append(self._t(j))
                j += 1
                if self._t(j) != ",":
                    break
                j += 1
            typ = None
            if j < g and self._t(j) == ":":
                e, depth = j + 1, 0
                while e < g and not (self._t(e) == "=" and depth == 0):
                    depth += (self._t(e) in ("(", "[", "<")) - (self._t(e) in (")", "]", ">"))
                    e += 1
                if e > j + 1:
                    typ = self._text(self.toks[j + 1].start, self.toks[e - 1].end)
                defaults = defaults or e < g
            for name in names:
                params[name] = typ
            k = g + 1
        return params, defaults

    def _impl(self, head: _PasHead, outer) -> int:
        """Implementierung ab dem Kopf: Direktiven, Deklarationen (mit geschachtelten
        Routinen und `var`-Abschnitten), Rumpf. Index danach."""
        toks, n = self.toks, len(self.toks)
        k = head.end + 1
        while k < n and toks[k].low in _PAS_DIRECTIVES:
            if toks[k].low in ("forward", "external"):
                return self._stmt_end(k) + 1
            k = self._stmt_end(k) + 1
        impl = _PasImpl(head, outer)
        while k < n:
            low = toks[k].low
            if low in ("begin", "asm"):
                stop = self._block_end(k)
                impl.begin, impl.stop, impl.end_line = k, stop, toks[stop].line
                for j in range(k, stop):
                    if toks[j].low == "var" and self._ident(j + 1):
                        impl.vars.update(self._decls(j + 1)[0])
                self.impls.append(impl)
                self.by_name.setdefault(head.low, []).append(impl)
                return stop + 1
            if low in _PAS_ROUTINES and self._t(k - 1) not in _PAS_TYPE_PREV:
                nested = self._head(k)
                if nested is not None:
                    k = self._impl(nested, impl)
                    continue
            elif low in ("var", "threadvar"):
                k += 1
                while (self._ident(k) and toks[k].low not in _PAS_KEYWORDS
                       and self._t(k + 1) in (",", ":")):
                    decls, k = self._decls(k)
                    impl.vars.update(decls)
                continue
            elif low in _PAS_STRUCTS and self._structural(k):
                k = self._struct(k)
                continue
            elif low in ("implementation", "initialization", "finalization", "end"):
                return k
            k += 1
        return n

    # -- Abfragen
    def decl_of(self, impl: _PasImpl):
        """Kopf der Deklaration zu einer Implementierung (Klassenrumpf oder interface-Teil);
        bei Überladungen der mit denselben Parameternamen, sonst nach Reihenfolge."""
        head = impl.head
        if impl.outer is not None:
            return None
        if head.cls:
            cls = self.classes.get(head.cls)
            cands = cls.methods.get(head.low, []) if cls else []
        else:
            cands = self.decls.get(head.low, [])
        if not cands:
            return None
        if head.params:
            same = [d for d in cands if list(d.params) == list(head.params)]
            if same:
                return same[0]
        siblings = [x for x in self.by_name.get(head.low, [])
                    if x.head.cls == head.cls and x.outer is None]
        if len(siblings) == len(cands) and impl in siblings:
            return cands[siblings.index(impl)]
        return cands[0]

    def enclosing(self, line: int):
        """Innerste Implementierung, deren Kopf bis `end` die Zeile enthält."""
        best = None
        for impl in self.impls:
            if impl.head.line <= line <= impl.end_line and (
                    best is None or impl.head.line >= best.head.line):
                best = impl
        return best

    def methods(self, cls_low: str, name: str) -> list:
        return [x for x in self.by_name.get(name, []) if x.head.cls == cls_low and x.outer is None]

    def standalone(self, name: str, nested: bool) -> list:
        return [x for x in self.by_name.get(name, [])
                if x.head.cls is None and (nested or x.outer is None)]

    def local_type(self, impl: _PasImpl, name: str):
        """Typ eines Namens in einer Routine: Parameter (der Implementierung, sonst der
        Deklaration), `var`, `Result`; dann die umschließenden Routinen."""
        while impl is not None:
            decl = self.decl_of(impl)
            params = impl.head.params or (decl.params if decl else {})
            if params.get(name):
                return params[name]
            if name in impl.vars:
                return impl.vars[name]
            ret = impl.head.ret or (decl.ret if decl else None)
            if name == "result" and ret:
                return ret
            impl = impl.outer
        return None

    def chain_before(self, dot: int):
        """Empfänger vor dem `.` bei `dot`: (Teile klein, Text) oder None, wenn davor kein
        einfacher Bezeichner-Pfad steht (Aufruf, Index, Typumwandlung)."""
        parts, j = [], dot - 1
        while self._ident(j) and self._t(j) not in _PAS_KEYWORDS:
            parts.insert(0, j)
            if self._t(j - 1) == "." and j - 2 >= 0:
                j -= 2
                continue
            break
        if not parts or self._t(parts[0] - 1) == ".":
            return None
        return [self._t(p) for p in parts], ".".join(self._word(p) for p in parts)

    def chain_after(self, k: int):
        """Bezeichner-Pfad ab `k` bis zur schließenden Klammer (`FreeAndNil(X.Y)`)."""
        parts = []
        while self._ident(k) and self._t(k) not in _PAS_KEYWORDS:
            parts.append(k)
            if self._t(k + 1) == "." and self._ident(k + 2):
                k += 2
                continue
            break
        if not parts or self._t(parts[-1] + 1) != ")":
            return None
        return [self._t(p) for p in parts], ".".join(self._word(p) for p in parts)

    def is_head_name(self, k: int) -> bool:
        """Ist der Bezeichner bei `k` der Name in einem Routinenkopf (`procedure TA.Foo(`)?"""
        j = k
        while self._t(j - 1) == "." and self._ident(j - 2):
            j -= 2
        return self._t(j - 1) in _PAS_ROUTINES

    def raise_type(self, k: int):
        """Typ nach `raise` ab `k`: `EFoo.Create(…)` → `EFoo`; None bei `raise;`."""
        parts = []
        while self._ident(k) and self._t(k) not in _PAS_KEYWORDS:
            parts.append(self._word(k))
            if self._t(k + 1) == "." and self._ident(k + 2):
                k += 2
                continue
            break
        while len(parts) > 1 and parts[-1].lower().startswith("create"):
            parts.pop()
        return ".".join(parts) or None

    def inherited_creates(self, cls_low: str) -> list:
        """(Text, Zeile) der `inherited Create(…)` und bloßen `inherited` in den
        Konstruktoren einer Klasse."""
        out = []
        for impl in self.impls:
            if impl.head.cls != cls_low or impl.head.kind != "constructor" or impl.outer:
                continue
            for k in range(impl.begin, impl.stop):
                if self._t(k) != "inherited":
                    continue
                nxt = self._t(k + 1)
                if nxt == "create":
                    end = self._close(k + 2) if self._t(k + 2) == "(" else k + 1
                    out.append((self._text(self.toks[k].start, self.toks[end].end),
                                self.toks[k].line))
                elif nxt in (";", "end", "else"):
                    out.append(("inherited", self.toks[k].line))
        return out


class _PasIndex:
    """Alle Delphi-Dateien am ZIEL: Bytes je Pfad, Units nach Namen (Dateiname ohne Endung,
    klein), gescannt erst bei Bedarf; `unreadable` wie beim Python-Index."""

    def __init__(self, sources: dict, skipped: dict) -> None:
        self.sources = sources
        self.unreadable = dict(skipped)
        self.lower_paths = {rel.lower(): rel for rel in sorted(sources)}
        self.by_unit: dict[str, list] = {}
        for rel in sorted(sources):
            if PurePosixPath(rel).suffix.lower() == ".pas":
                self.by_unit.setdefault(PurePosixPath(rel).stem.lower(), []).append(rel)
        self._units: dict[str, _PasUnit] = {}
        self._scope: dict[str, list] = {}
        self.raises_memo: dict[tuple, list] = {}

    def unit(self, rel: str):
        if rel not in self.sources:
            return None
        if rel not in self._units:
            self._units[rel] = _PasUnit(rel, _pas_text(self.sources[rel]))
        return self._units[rel]

    def scope(self, unit: _PasUnit) -> list:
        """Die Unit selbst, dann die Units ihrer `uses`-Listen, die zuletzt genannte zuerst
        (Delphi: sie verdeckt die früheren). Gleichnamige Units: die mit den meisten
        gemeinsamen Verzeichnissen, dann nach Pfad; `in '…'` geht vor."""
        rel = unit.rel
        if rel not in self._scope:
            found = []
            here = PurePosixPath(rel).parent.parts
            for name, path in unit.uses:
                hit = None
                if path:
                    cand = posixpath.normpath(posixpath.join(posixpath.dirname(rel),
                                                             path.replace("\\", "/")))
                    hit = self.lower_paths.get(cand.lower())
                if hit is None and self.by_unit.get(name):
                    def shared(c, here=here):
                        there = PurePosixPath(c).parent.parts
                        return next((i for i, (a, b) in enumerate(zip(here, there)) if a != b),
                                    min(len(here), len(there)))
                    hit = min(self.by_unit[name], key=lambda c: (-shared(c), c))
                if hit is not None and hit != rel and hit not in found:
                    found.append(hit)
            self._scope[rel] = [unit] + [self.unit(r) for r in reversed(found)]
        return self._scope[rel]

    def find_class(self, key, unit: _PasUnit):
        for scoped in self.scope(unit):
            if key in scoped.classes:
                return scoped, scoped.classes[key]
        return None

    def class_chain(self, key, unit: _PasUnit) -> tuple[list, str | None]:
        """([(unit, Klasse)] ab `key` über die Basisklassen im Repo, höchstens
        `CLASS_CHAIN_MAX`), Schlüssel der ersten Basisklasse außerhalb des Repos."""
        chain, seen = [], set()
        while key and len(chain) < CLASS_CHAIN_MAX:
            hit = self.find_class(key, unit)
            if hit is None or (hit[0].rel, key) in seen:
                break
            seen.add((hit[0].rel, key))
            chain.append(hit)
            unit, key = hit[0], hit[1].parent
        return chain, key

    def receiver(self, unit: _PasUnit, line: int, chain: list):
        """Typtext eines Empfängers `a.b.c` an einer Zeile: `Self`, Parameter, `var`,
        Feld oder Property der Klasse (auch geerbt), Klassenname; weiter über Felder."""
        first, rest = chain[0], chain[1:]
        impl = unit.enclosing(line)
        top = impl.top() if impl is not None else None
        typ = None
        if first == "self":
            typ = top.head.parts[-2] if top is not None and top.head.cls else None
        else:
            typ = unit.local_type(impl, first) if impl is not None else None
            if typ is None and top is not None and top.head.cls:
                typ = self._field(top.head.cls, first, unit)
            if typ is None:
                hit = self.find_class(first, unit)
                typ = hit[1].name if hit else None
        for part in rest:
            if typ is None:
                return None
            typ = self._field(_type_key(typ), part, unit)
        return typ

    def _field(self, cls_key, name: str, unit: _PasUnit):
        for _scoped, cls in self.class_chain(cls_key, unit)[0]:
            if name in cls.fields:
                return cls.fields[name]
        return None

    def resolve_call(self, unit: _PasUnit, line: int, receiver, name: str):
        """(Liste (unit, Implementierung), mehrdeutig) für einen Aufruf `name(`: ohne
        Empfänger die Methoden der eigenen Klasse, dann freie Routinen der Unit und der
        `uses`-Units; mit Unit-Namen als Empfänger dessen Routinen; mit bekanntem Typ nur
        dessen Klassenkette; sonst alle Methoden des Namens — mehr als `AMBIGUOUS_MAX`:
        mehrdeutig, nichts."""
        if receiver == []:
            impl = unit.enclosing(line)
            top = impl.top() if impl is not None else None
            if top is not None and top.head.cls:
                for scoped, cls in self.class_chain(top.head.cls, unit)[0]:
                    found = scoped.methods(cls.low, name)
                    if found:
                        return [(scoped, x) for x in found], False
            for scoped in self.scope(unit):
                found = scoped.standalone(name, nested=scoped is unit)
                if found:
                    return [(scoped, x) for x in found], False
            return [], False
        if receiver is not None:
            joined = ".".join(receiver)
            for scoped in self.scope(unit):
                if scoped.name == joined:
                    return [(scoped, x) for x in scoped.standalone(name, nested=False)], False
            typ = self.receiver(unit, line, receiver)
            if typ is not None:
                for scoped, cls in self.class_chain(_type_key(typ), unit)[0]:
                    found = scoped.methods(cls.low, name)
                    if found:
                        return [(scoped, x) for x in found], False
                return [], False
        found = [(scoped, x) for scoped in self.scope(unit)
                 for x in scoped.by_name.get(name, []) if x.head.cls and x.outer is None]
        if len(found) > AMBIGUOUS_MAX:
            return [], True
        return found, False

    def raises(self, unit: _PasUnit, impl: _PasImpl) -> list:
        """(Typ, Zeile) der `raise` im Rumpf, transitiv über Aufrufe von Routinen derselben
        Unit (eigene Klasse oder frei) bis `RAISE_DEPTH`; nach Zeile, ohne Doppelte."""
        key = (unit.rel, impl.head.line, impl.begin)
        if key not in self.raises_memo:
            found = self._raises_in(unit, impl, RAISE_DEPTH, set())
            self.raises_memo[key] = sorted(set(found), key=lambda r: (r[1], r[0]))
        return self.raises_memo[key]

    def _raises_in(self, unit: _PasUnit, impl: _PasImpl, depth: int, seen: set) -> list:
        key = (impl.head.line, impl.begin)
        if key in seen:
            return []
        seen.add(key)
        cls = impl.top().head.cls
        out = []
        for k in range(impl.begin, impl.stop):
            tok = unit.toks[k]
            if tok.low == "raise":
                typ = unit.raise_type(k + 1)
                if typ:
                    out.append((typ, tok.line))
            elif (depth > 0 and tok.ident and unit._t(k + 1) in ("(", ";")
                  and (unit._t(k - 1) != "." or unit._t(k - 2) == "self")):
                for callee in unit.by_name.get(tok.low, []):
                    if callee is not impl and callee.head.cls in (cls, None):
                        out += self._raises_in(unit, callee, depth - 1, seen)
        return out


def _delphi_sources(repo: Path, target: str) -> tuple[dict, dict]:
    return _tree_sources(repo, target, _is_delphi)


@functools.lru_cache(maxsize=INDEX_CACHE_SIZE)
def _delphi_index(repo: Path, target: str) -> _PasIndex:
    """Delphi-Index am ZIEL, je (Repo, SHA) einmal gebaut; Units werden erst bei Bedarf
    gescannt."""
    return _PasIndex(*_delphi_sources(repo, target))


def _owner_lines(index: _PasIndex, unit: _PasUnit, typ: str) -> list:
    """Klassendeklaration des Empfängertyps und seiner Basisklassen im Repo, je mit den
    `inherited Create(…)` ihrer Konstruktoren; erbt die Kette von einer Klasse mit
    Besitz-Default der RTL (`OWNERSHIP_RTL`), steht er dabei — auch ohne Deklaration im Repo."""
    chain, last = index.class_chain(_type_key(typ), unit)
    lines = []
    for scoped, cls in chain:
        lines.append(f"- Gegenstelle {cls.name} [{scoped.rel}:{cls.line}]: {cls.sig}")
        lines += [f"  {text} at {scoped.rel}:{line}"
                  for text, line in scoped.inherited_creates(cls.low)[:INHERITED_LINES_MAX]]
    if last in OWNERSHIP_RTL:
        lines.append(f"  Besitz (RTL): {OWNERSHIP_RTL[last]}")
    return lines


def _call_lines(index: _PasIndex, cands: list) -> tuple[list, bool]:
    """Zeilen je erreichter Implementierung und ob die Sammelregel greift (wirft etwas oder
    der Kopf hat einen Default-Wert)."""
    body, show = [], False
    for scoped, impl in cands[:COUNTERPART_MAX_DEFS]:
        decl = scoped.decl_of(impl)
        head = decl or impl.head
        raises = index.raises(scoped, impl)
        show = show or bool(raises) or head.defaults
        body.append(f"- Gegenstelle {impl.head.qual} [{scoped.rel}:{impl.head.line}]: {head.sig}")
        if decl is not None:
            body.append(f"  deklariert: {scoped.rel}:{decl.line}")
        if raises:
            body.append("  wirft: " + ", ".join(sorted({t for t, _ in raises})))
            body += [f"    raise {t} at {scoped.rel}:{n}" for t, n in raises[:RAISE_LINES_MAX]]
    return body, show


def _delphi_sites(index: _PasIndex, unit: _PasUnit, lines: set, unresolved: set) -> list:
    """Die Stellen einer Delphi-Datei nach der Sammelregel (Spec 26, Schritt 3): je Aufruf
    `Name(`/`Obj.Name(` auf einer geänderten Zeile (`call`), je `Extract`, `Remove`, `Free`,
    `FreeAndNil`, `SetContentStream` (`owner`). Mehrere Einträge gleicher Art und gleichen
    Namens auf einer Zeile tragen die Spalte wie bei Python."""
    rel, toks = unit.rel, unit.toks
    entries, shown, groups = [], set(), {}

    def add(kind, k, name, head, body):
        key = (toks[k].line, kind, name.lower(), tuple(body))
        if key in shown:
            return
        shown.add(key)
        entry = {"file": rel, "line": toks[k].line, "kind": kind,
                 "lines": [f"### {rel}:{toks[k].line} {head}", *body]}
        entries.append(entry)
        groups.setdefault((toks[k].line, kind, name.lower()), []).append(
            (entry, unit.column(toks[k]), head))

    for line in sorted(lines):
        lo = bisect.bisect_left(unit.tok_lines, line)
        hi = bisect.bisect_right(unit.tok_lines, line)
        for k in range(lo, hi):
            tok = toks[k]
            if not tok.ident:
                continue
            prev, nxt = unit._t(k - 1), unit._t(k + 1)
            if tok.low in DELPHI_RELEASES:
                found = None
                if tok.low == "freeandnil":
                    found = unit.chain_after(k + 2) if nxt == "(" else None
                elif prev == ".":
                    found = unit.chain_before(k - 1)
                typ = index.receiver(unit, line, found[0]) if found else None
                body = _owner_lines(index, unit, typ) if typ else []
                if body:
                    add("owner", k, tok.low, f"{unit._word(k)} auf {found[1]}: {typ}", body)
            if (nxt != "(" or tok.low in _PAS_KEYWORDS or prev == "inherited"
                    or unit.is_head_name(k)):
                continue
            if prev == ".":
                found = unit.chain_before(k - 1)
                receiver = found[0] if found else None   # None: Empfänger unbekannt
            else:
                receiver = []
            cands, ambiguous = index.resolve_call(unit, line, receiver, tok.low)
            if ambiguous:
                unresolved.add((rel, line, tok.start))
            body, show = _call_lines(index, cands) if cands else ([], False)
            if show:
                add("call", k, tok.low, f"ruft {unit._word(k)}(...)", body)
    for (line, _kind, _name), group in groups.items():
        if len(group) > 1:
            for entry, col, head in group:
                entry["lines"][0] = f"### {rel}:{line}:{col} {head}"
    return entries


def collect_delphi(repo, rng, files):
    """Gegenstellen der geänderten Delphi-Zeilen (Spec 26, Ablauf Schritt 3), per Text-Scanner.

    `rng` und `files` wie bei `collect_python`; gezählt nur `.pas`, `.dpr`, `.dpk` (ohne
    Rücksicht auf Groß/Klein) außerhalb von `.skills/`. Der Code kommt aus dem Baum des ZIELS
    in Git und wird nie ausgeführt; `mask_pascal` blendet Strings und Kommentare aus. Je
    Aufruf `Name(` oder `Obj.Name(` auf einer geänderten Zeile die Implementierung
    `procedure|function|constructor|destructor [TKlasse.]Name` aus der eigenen Unit und den
    Units der `uses`-Listen (Empfänger mit bekanntem Typ: nur dessen Klassenkette), ihr Kopf
    aus der Deklaration (interface-Teil oder Klassenrumpf) mit Default-Werten und ihre
    `raise`-Zeilen (transitiv in der Unit, `RAISE_DEPTH`); im Block, wenn sie etwas wirft
    oder einen Default-Wert zeigt. Je `Extract`, `Remove`, `Free`, `FreeAndNil` oder
    `SetContentStream` auf einer geänderten Zeile der Typ des Empfängers (Parameterliste,
    `var`-Abschnitt oder Inline-`var`, Feld oder Property der Klasse, `Self`), seine
    Klassendeklaration mit Basisklasse und den `inherited Create(…)` des Konstruktors, über
    die Basisklassen im Repo (`CLASS_CHAIN_MAX`); erbt sie von `TObjectList<…>` oder
    `TObjectDictionary<…>`, steht der Besitz-Default der RTL dabei. Format wie bei
    `Collected`, Arten `call` und `owner`; `unresolved` zählt Aufrufe auf unbekanntem
    Empfänger mit mehr als `AMBIGUOUS_MAX` gleichnamigen Methoden. Rückgabe:
    `Collected(entries, unresolved, unparsed)`."""
    repo = _toplevel(repo)
    wanted = sorted({str(f) for f in files if _is_delphi(str(f)) and not _under_skills(str(f))})
    if not wanted:
        return Collected([], 0, [])
    span = split_range(repo, rng)
    index = _delphi_index(repo, span.target)
    unresolved: set = set()
    entries = []
    unparsed = {rel: index.unreadable[rel] for rel in wanted if rel in index.unreadable}
    for rel, lines in sorted(_changed_lines(repo, span, wanted).items()):
        unit = index.unit(rel)
        if unit is not None:
            entries += _delphi_sites(index, unit, lines, unresolved)
        elif rel not in unparsed:
            unparsed[rel] = NOT_IN_TARGET
    entries.sort(key=lambda e: (e["file"], e["line"], e["kind"]))
    return Collected(entries, len(unresolved), sorted(unparsed.items()))


def _file_line(path: str, unreadable: dict) -> str:
    """Zeile der Dateiliste: eine Datei ohne Sammler oder ohne lesbaren Stand mit Hinweis."""
    if not _has_collector(path):
        return f"- `{path}` — {NO_COLLECTOR}\n"
    if path in unreadable:
        return f"- `{path}` — Datei am ZIEL nicht lesbar: {unreadable[path]}\n"
    return f"- `{path}`\n"


def _packet_extras(packet) -> tuple[dict, str, str | None]:
    """Die optionalen Schlüssel eines Pakets für `render_block`, geprüft: (Pfad → Grund aus
    `unreadable`, `notes` als Text fürs Ende, `intro` oder None). Falsche Form: KitError."""
    pairs = packet.get("unreadable") or []
    if not isinstance(pairs, (list, tuple)):
        raise KitError(f"unreadable muss eine Liste von Paaren (datei, grund) sein, "
                       f"nicht {pairs!r}")
    unreadable = {}
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2 or not isinstance(pair[1], str):
            raise KitError(f"unreadable: Paar (datei, grund) erwartet, nicht {pair!r}")
        unreadable[str(pair[0])] = pair[1]
    notes = packet.get("notes") or []
    if not isinstance(notes, (list, tuple)) or not all(isinstance(n, str) for n in notes):
        raise KitError(f"notes muss eine Liste von Texten sein, nicht {notes!r}")
    intro = packet.get("intro")
    if intro is not None and not isinstance(intro, str):
        raise KitError(f"intro muss ein Text sein, nicht {intro!r}")
    return unreadable, "".join(f"\n{note}\n" for note in notes), intro


def _render(packet, entries, unresolved, cap) -> tuple[str, int]:
    """`render_block` mit der Zahl der Stellen, die im Block stehen — dieselben vier
    Parameter, alles Weitere aus den optionalen Schlüsseln des Pakets."""
    cap = BLOCK_MAX_CHARS if cap is None else cap
    if not isinstance(cap, int) or isinstance(cap, bool) or cap < 1:
        raise KitError(f"cap muss eine positive Zahl sein, nicht {cap!r}")
    if not isinstance(unresolved, int) or isinstance(unresolved, bool) or unresolved < 0:
        raise KitError(f"unresolved muss eine Zahl ≥ 0 sein, nicht {unresolved!r}")
    unreadable, notes, intro = _packet_extras(packet)
    files = [str(f) for f in packet.get("files") or []]  # einmal als Text, für Zeilen und Zahl
    rng = packet.get("range")
    title = (f"# Paket {packet.get('id')}\n\n"
             + (f"Bereich: `{rng}`" if rng else "Bereich: noch nicht gebaut")
             + f"\n\nDateien ({len(files)}):\n")
    total = len(entries)
    if intro is None:
        intro = (f"\n## Gegenstellen\n\n{total} Stelle(n) nach der Sammelregel, mechanisch "
                 f"gesammelt (ohne Auswahl nach Verdacht); {unresolved} nicht aufgelöst (ohne "
                 "Importbezug und mehrdeutig: nichts statt Raten).\n")
        mine = sum(1 for f in files if f in unreadable)
        if mine:
            intro += (f"{mine} Paketdatei(en) am ZIEL nicht lesbar (übersprungen, in der "
                      "Dateiliste genannt).\n")
    else:
        intro = "\n" + intro
    rows = [_file_line(f, unreadable) for f in files]
    blocks = ["\n" + "\n".join(e["lines"]) + "\n" for e in entries]
    fixed = len(title) + len(intro) + len(notes)
    rows_size, blocks_size = sum(map(len, rows)), sum(map(len, blocks))
    if fixed + rows_size + blocks_size <= cap:
        return title + "".join(rows) + intro + "".join(blocks) + notes, total

    def more_files(omitted: int) -> str:
        return f"- … und {omitted} weitere Datei(en) (gekappt)\n"

    def notice(omitted: int) -> str:
        return (f"\n(gekappt: {omitted} von {total} Stellen nicht im Block — Grenze {cap} "
                "Zeichen je Paket)\n")

    budget = cap - fixed - len(more_files(len(files))) - len(notice(total))
    if budget < 0:
        raise KitError(f"cap {cap} zu klein für Kopf und Kappungshinweis des Blocks")
    # Die Dateiliste bekommt höchstens die Hälfte, außer die Stellen brauchen weniger.
    row_budget = max(budget // 2, budget - blocks_size)
    listed, size = 0, 0
    for row in rows:
        if size + len(row) > row_budget:
            break
        size += len(row)
        listed += 1
    left, shown = budget - size, 0
    for block in blocks:
        if len(block) > left:
            break
        left -= len(block)
        shown += 1
    text = title + "".join(rows[:listed])
    text += more_files(len(files) - listed) if listed < len(files) else ""
    text += intro + "".join(blocks[:shown])
    text += notice(total - shown) if shown < total else ""
    return text + notes, shown


def render_block(packet, entries, unresolved, cap):
    """Paketblock in Markdown: Kopf (Paket, Bereich, Dateien; eine Datei ohne Sammler mit
    „Gegenstellen nicht gesammelt (Sprache)") und Abschnitt `## Gegenstellen` mit der Zahl
    der Stellen und der nicht aufgelösten, dann je Stelle ihre `lines` (Format bei
    `Collected`) in der gegebenen Reihenfolge. Für jede Sprache dasselbe.

    `cap` (None = `BLOCK_MAX_CHARS`) begrenzt den ganzen Block in Zeichen. Passt er nicht,
    stehen von der Dateiliste (höchstens die Hälfte, außer die Stellen brauchen weniger) und
    von den Stellen die ersten, die passen, mit `- … und <n> weitere Datei(en) (gekappt)`
    und `(gekappt: <weggelassen> von <alle> Stellen nicht im Block — …)` — nie still. Ein
    `cap`, in den nicht einmal Überschriften und Hinweise passen, ist ein KitError. Die
    Kopfzeile des Artefakts (E3) setzt `write_counterparts` davor und zieht sie vom `cap`
    ab.

    Neben `id`, `range` und `files` liest der Block optionale Schlüssel des Pakets — jeder
    Sammler (Python, Delphi) erreicht alles, was ein Block zeigen kann, über diese vier
    Parameter; eine falsche Form ist ein KitError:

    - `unreadable`: Liste von Paaren `(datei, grund)` (Tupel oder JSON-Listen, etwa
      `Collected.unparsed`) — die Datei steht in der Dateiliste mit „Datei am ZIEL nicht
      lesbar: <grund>", die Zahl der betroffenen Paketdateien unter `## Gegenstellen`.
    - `notes`: Liste von Texten, je einer als eigener Absatz am Ende des Blocks (etwa die
      Zahl der nicht lesbaren Dateien außerhalb des Pakets).
    - `intro`: Text, der den Anfang des Abschnitts ab `## Gegenstellen` samt Zählzeilen
      ersetzt (etwa „Gegenstellen nicht gesammelt (Fokus quality).").

    Dateien und die Pfade in `unreadable` zählen als Text (`str`), auch als `Path`. Kopf,
    Hinweise und `notes` zählen gegen `cap` und werden nie gekappt.
    `write_counterparts` rendert über denselben Weg mit diesen Schlüsseln."""
    return _render(packet, entries, unresolved, cap)[0]


def write_counterparts(repo, run_id):
    """`counterparts --run <lauf>`: je Paket des Plans `packets/<id>.md` im Laufordner.

    Je Paket zuerst der reviewbare Bereich (`make_packet_range`; vorhandene Bereiche kommen
    ohne neue Refs zurück), dann die Gegenstellen (`collect_python` und `collect_delphi`,
    Einträge zusammen nach Datei, Zeile, Art; `unresolved` addiert, `unparsed` vereinigt)
    über den Bereich des Plans, beschränkt auf
    die Paketdateien — dieselben geänderten Zeilen wie im Paket-Bereich, der Code aber am
    ZIEL des Plans (`bis^{tree}` weicht bei einer Datei/Ordner-Kollision ab). Die Datei
    beginnt mit der Kopfzeile `<!-- skill: deep-review | schema: 1 | generated: … | packet:
    <id> -->`, dann der Block von `render_block` (über `_render`, dieselben vier Parameter,
    für die Zahl der gezeigten Stellen) für eine Kopie des Pakets mit den optionalen
    Schlüsseln: `unreadable` = `Collected.unparsed` (eigene Dateien ohne lesbaren Stand am
    ZIEL, mit Grund in der Dateiliste), `notes` = die übrigen nicht durchsuchten
    Python-Dateien des Repos als eine Zahl mit den vorkommenden Gründen
    (`_PyIndex.not_indexed`: ohne Submodule und ohne Symlinks auf indexierte Dateien) am Ende
    eines Python-Pakets, bei Fokus `quality` statt Gegenstellen `intro` = `QUALITY_INTRO`.
    Höchstens `BLOCK_MAX_CHARS` Zeichen je Datei, Kopfzeile eingeschlossen. Schreibt atomar,
    überschreibt einen früheren Block. Rückgabe: je Paket in
    Plan-Reihenfolge `{"packet", "path" (repo-relativ), "counterparts", "shown",
    "unresolved"}`."""
    repo = _toplevel(repo)
    run_id = _check_run_id(run_id)
    _path, plan = _load_plan(repo, run_id)
    plan_range = plan.get("range")
    if not isinstance(plan_range, str) or not plan_range:
        raise KitError(f"Plan von Lauf {run_id} hat keinen Bereich (range)")
    repo_unreadable = None
    written = []
    for packet in plan["packets"]:
        pid = packet["id"]
        rng = make_packet_range(repo, run_id, pid, None, None)
        shown_packet = {**packet, "range": rng}
        header = (f"<!-- skill: {SKILL_NAME} | schema: {SCHEMA_VERSION} | generated: "
                  f"{SCRIPT_CMD} counterparts --run {run_id} | packet: {pid} -->\n")
        cap = BLOCK_MAX_CHARS - len(header)
        if plan.get("focus") == "quality":
            shown_packet["intro"] = QUALITY_INTRO
            body, _shown = _render(shown_packet, [], 0, cap)
            total = shown = unresolved = 0
        else:
            py = collect_python(repo, plan_range, packet["files"])
            dl = collect_delphi(repo, plan_range, packet["files"])
            found = Collected(
                sorted(py.entries + dl.entries, key=lambda e: (e["file"], e["line"], e["kind"])),
                py.unresolved + dl.unresolved, sorted(py.unparsed + dl.unparsed))
            own = {str(f) for f in packet["files"] if _is_python(str(f))}
            notes = []
            if own:
                if repo_unreadable is None:
                    target = split_range(repo, plan_range).target
                    repo_unreadable = _python_index(repo, target).not_indexed()
                others = {p: r for p, r in repo_unreadable.items() if p not in own}
                if others:
                    reasons = ", ".join(sorted(set(others.values())))
                    notes = [f"{len(others)} Python-Datei(en) außerhalb des Pakets am ZIEL nicht "
                             f"lesbar ({reasons}) — dort keine Gegenstellen gesucht."]
            shown_packet.update(unreadable=found.unparsed, notes=notes)
            body, shown = _render(shown_packet, found.entries, found.unresolved, cap)
            total, unresolved = len(found.entries), found.unresolved
        rel = CACHE_DIR / run_id / "packets" / f"{pid}.md"
        _write_text(repo / rel, header + body)
        written.append({"packet": pid, "path": rel.as_posix(), "counterparts": total,
                        "shown": shown, "unresolved": unresolved})
    return written
