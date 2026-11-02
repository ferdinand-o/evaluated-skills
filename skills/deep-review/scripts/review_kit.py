#!/usr/bin/env python3
"""deep-review: Paketplan, Gegenstellen und Abdeckung für `/code-review`. Tier 1: nur Stdlib.

Das Skript reviewt nichts. Es schneidet einen Bereich `BASIS..ZIEL` nach einer festen
Schnittregel in Pakete, schreibt den Plan nach `.skills/cache/deep-review/<lauf>/plan.json`
und nimmt später die Ergebnisse je Paket an (Spec 26). Zielcode wird nie importiert oder
gestartet. Git schreibt nur Objekte und Refs unter `refs/deep-review/<lauf>/` (die
Hilfscommits der Paket-Bereiche, gebaut über einen temporären Index; der Vergleich mit dem
Arbeitsbaum läuft auf einer Kopie des Index); HEAD, Index und Arbeitsbaum des Nutzers
bleiben unberührt (E6).

Stand Task 3: Lauf-ID, JSON-Schreiber, Zählung über `git diff --numstat --no-renames`
ab der Merge-Basis, Einordnung (reviewt oder `not_reviewed` mit Grund), Schnittregel,
`build_plan`, Paket-Bereiche (`make_packet_range`) und `cleanup`.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import fnmatch
import functools
import json
import math
import os
import re
import secrets
import shlex
import shutil
import socket
import string
import subprocess
import tempfile
import time
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
    return done.stdout.decode("utf-8", errors="surrogateescape")


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
    return data


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
