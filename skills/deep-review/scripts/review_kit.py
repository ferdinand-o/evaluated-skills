#!/usr/bin/env python3
"""deep-review: Paketplan, Gegenstellen und Abdeckung für `/code-review`. Tier 1: nur Stdlib.

Das Skript reviewt nichts. Es schneidet einen Bereich `BASIS..ZIEL` nach einer festen
Schnittregel in Pakete, schreibt den Plan nach `.skills/cache/deep-review/<lauf>/plan.json`
und nimmt später die Ergebnisse je Paket an (Spec 26). Zielcode wird nie importiert oder
gestartet; Git liest nur.

Stand Task 2: Lauf-ID, JSON-Schreiber, Zählung über `git diff --numstat --no-renames`
ab der Merge-Basis, Einordnung (reviewt oder `not_reviewed` mit Grund), Schnittregel und
`build_plan`.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import re
import secrets
import shlex
import shutil
import string
import subprocess
import tempfile
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
# Dieselbe Ausnahme wie subagent-dev (plan_to_tasks.py, changed_lines), ab der Repo-Wurzel,
# damit beide Zähler dieselben Zeilen zählen, auch wenn `repo` ein Unterordner ist.
DIFF_PATHSPEC = (":(top)", ":(top,exclude).skills")

PROFILES = ("standard", "checkpoint")
FOCI = ("bugs", "security", "quality")

RUN_SUFFIX_CHARS = string.ascii_lowercase + string.digits
RUN_SUFFIX_LEN = 4
SHORT_SHA_LEN = 7

# Einordnung (Spec 26, Ablauf Schritt 2): Dateien ohne Quellcode werden nie reviewt,
# Testdateien nur mit --with-tests. Testmuster gelten ohne Rücksicht auf Groß/Klein.
DOC_SUFFIXES = frozenset({".md", ".markdown", ".rst"})
DOC_NAMES = frozenset({"NEWS", "CHANGES", "CHANGELOG", "AUTHORS", "LICENSE", "COPYING"})
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
                            ".tif", ".tiff"})
PROJECT_SUFFIXES = frozenset({".dproj", ".res"})
TEST_NAME_PATTERNS = ("test_*.py", "*_test.py")
# `*Test*.pas`: `Test` oder `TEST` irgendwo im Namen, `test` nur am Anfang — sonst wäre
# `Latest.pas` eine Testdatei.
TEST_PAS_STEM = re.compile(r"Test|TEST|^test")
TEST_DIRS = frozenset({"tests", "unittests"})

REASON_DOC = "keine Quelldatei: Doku"
REASON_IMAGE = "keine Quelldatei: Bild"
REASON_PROJECT = "keine Quelldatei: Delphi-Projekt oder Ressource"
REASON_TEST = "Testdatei: nur mit --with-tests"


class KitError(RuntimeError):
    """Ein Schritt ist gescheitert — mit einer Ursache, die der Nutzer versteht."""


# --- Git ----------------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> str:
    """git-Aufruf, der bei Fehlschlag wirft. Ausgabe als UTF-8, nie geraten; Bytes, die kein
    UTF-8 sind, bleiben als Surrogate erhalten und werden vor dem Schreiben abgewiesen."""
    try:
        done = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, stdin=subprocess.DEVNULL,
            timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise KitError(f"git {' '.join(args)} konnte nicht gestartet werden: {exc}") from exc
    if done.returncode != 0:
        stderr = done.stderr.decode("utf-8", errors="replace").strip()
        raise KitError(f"git {' '.join(args)} fehlgeschlagen: "
                       f"{stderr or f'Exit {done.returncode}'}")
    return done.stdout.decode("utf-8", errors="surrogateescape")


def _commit(repo: Path, rev: str) -> str:
    if not rev or rev.startswith("-"):
        raise KitError(f"ungültige Revision: {rev!r}")
    try:
        return _git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").strip()
    except KitError:
        raise KitError(f"Revision {rev!r} unbekannt oder kein Commit") from None


def _empty_tree(repo: Path) -> str:
    """SHA des leeren Baums im Hash-Format dieses Repos; schreibt nichts."""
    return _git(repo, "hash-object", "-t", "tree", "--stdin").strip()


class Span(NamedTuple):
    """Ein aufgelöster Bereich. `merge_base..target` wird gezählt und reviewt (wie
    `git diff BASIS...ZIEL`), `base..target` liefert die Commit-Messages (`git log`). Beim
    Wurzel-Commit sind `base` und `merge_base` der leere Baum; die Messages liefert dann
    `git log target`."""
    base: str
    merge_base: str
    target: str


class Numstat(NamedTuple):
    """Rückgabe von `numstat`: geänderte Zeilen je Datei und der Bereich, über den gezählt
    wurde — einmal aufgelöst, damit Plan und Lauf-ID denselben Commit meinen."""
    counts: dict
    base: str
    merge_base: str
    target: str


def split_range(repo: Path, rng) -> Span:
    """`BASIS..ZIEL` → Span. Eine einzelne Revision `X` heißt `X^..X`, beim Wurzel-Commit
    leerer Baum..X; ohne Bereich (None) der letzte Commit `HEAD`. Bei zwei Punkten wird ab
    der Merge-Basis gezählt. Drei Punkte sind abgelehnt — zwei Punkte zählen schon so."""
    rng = DEFAULT_RANGE if rng is None else rng
    if not isinstance(rng, str) or not rng.strip():
        raise KitError(f"leerer Bereich {rng!r} — gib BASIS..ZIEL oder eine Revision an")
    if "..." in rng:
        raise KitError("Bereich mit '...' nicht unterstützt — gib BASIS..ZIEL an")
    if ".." not in rng:
        target = _commit(repo, rng)
        parents = _git(repo, "rev-list", "--parents", "-n", "1", target).split()[1:]
        base = parents[0] if parents else _empty_tree(repo)
        return Span(base, base, target)
    base_rev, target_rev = rng.split("..", 1)
    base, target = _commit(repo, base_rev or "HEAD"), _commit(repo, target_rev or "HEAD")
    try:
        merge_base = _git(repo, "merge-base", base, target).strip()
    except KitError:
        raise KitError(f"Bereich {rng!r}: BASIS und ZIEL haben keine gemeinsame Basis") from None
    return Span(base, merge_base, target)


def _require_utf8(path: str) -> None:
    try:
        path.encode("utf-8")
    except UnicodeEncodeError:
        raw = path.encode("utf-8", errors="surrogateescape")
        raise KitError(f"Pfad ist kein UTF-8: {raw!r} — Datei umbenennen") from None


def numstat(repo, rng):
    """Geänderte Zeilen je Datei im Bereich: hinzugefügte plus gelöschte, nach Pfad sortiert.

    `git diff --numstat --no-renames MERGE-BASIS ZIEL`: eine Umbenennung ist eine gelöschte
    und eine neue Datei; Binärdateien zählen 0; `.skills/` schließt dieselbe Pathspec aus
    wie subagent-dev. Pfade sind repo-relativ in POSIX-Form, wie Git sie ausgibt; ein Pfad,
    der kein UTF-8 ist, bricht mit KitError ab. Rückgabe: `Numstat(counts, base,
    merge_base, target)`."""
    repo = Path(repo)
    span = split_range(repo, rng)
    out = _git(repo, "diff", "--numstat", "--no-renames", "--no-textconv", "--no-ext-diff",
               "-z", span.merge_base, span.target, "--", *DIFF_PATHSPEC)
    counts: dict[str, int] = {}
    for record in out.split("\0"):
        if not record:
            continue
        added, deleted, path = record.split("\t", 2)
        _require_utf8(path)
        lines = 0 if "-" in (added, deleted) else int(added) + int(deleted)
        counts[path] = counts.get(path, 0) + lines
    return Numstat(dict(sorted(counts.items())), *span)


# --- Einordnung und Schnittregel -------------------------------------------------------------

def classify(path, with_tests):
    """None, wenn die Datei reviewt wird; sonst der Grund für `not_reviewed`.

    Ohne Quellcode (nie reviewt): Doku (Markdown, reStructuredText, `NEWS` und Verwandte
    ohne Endung), Bilder, `.dproj`, `.res`. Tests (`test_*.py`, `*_test.py`, unter `tests/`
    oder `unittests/`, `*Test*.pas`, ohne Rücksicht auf Groß/Klein) nur mit `with_tests` —
    so lief die Messung."""
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
        or (suffix == ".pas" and TEST_PAS_STEM.search(pure.stem) is not None)
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
    stamp = _now().astimezone(dt.timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    while True:
        suffix = "".join(secrets.choice(RUN_SUFFIX_CHARS) for _ in range(RUN_SUFFIX_LEN))
        run_id = f"{stamp}-{short}-{suffix}"
        if run_id not in _ISSUED:
            _ISSUED.add(run_id)
            return run_id


def _normalize(value):
    """Wert so, wie er als JSON gelesen zurückkäme: Pfad-Objekte als repo-relative
    POSIX-Pfade, Tupel als Listen. Alles andere, was JSON nicht kennt, ist ein KitError."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise KitError(f"JSON-Schlüssel muss Text sein, nicht {key!r}")
            out[key] = _normalize(item)
        return out
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, PurePath):
        if value.is_absolute():
            raise KitError(f"absoluter Pfad in einem Artefakt: {value}")
        return value.as_posix()
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise KitError(f"nicht als JSON schreibbar: {type(value).__name__}")


def write_json(path, meta, payload):
    """Die eine Schreibfunktion für alle JSON-Artefakte des Laufs (Spec 26, E3).

    `_meta` zuerst mit `skill`, `schema` (fest, `meta` darf sie nicht setzen), dann den
    Feldern aus `meta` (Pflicht: `generated`, das Kommando); danach `payload` in seiner
    Reihenfolge. `ensure_ascii=False`, Pfad-Objekte als repo-relative POSIX-Pfade; Text, der
    kein UTF-8 ist, ist ein KitError. Schreibt über eine eigene Temp-Datei im Zielordner,
    ersetzt atomar und räumt die Temp-Datei bei jedem Fehler weg. Rückgabe: das geschriebene
    Objekt, so wie es von der Platte gelesen zurückkäme."""
    if "generated" not in meta:
        raise KitError("_meta braucht 'generated' (das Kommando)")
    reserved = [key for key in RESERVED_META if key in meta]
    if reserved:
        raise KitError(f"_meta-Felder {', '.join(reserved)} sind fest und nicht überschreibbar")
    if "_meta" in payload:
        raise KitError("payload darf kein eigenes _meta tragen")
    data = _normalize({"_meta": {"skill": SKILL_NAME, "schema": SCHEMA_VERSION, **meta},
                       **payload})
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    try:
        raw = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        bad = text[exc.start:exc.end].encode("utf-8", errors="surrogateescape")
        raise KitError(f"Text ist kein UTF-8 ({bad!r}) — Artefakt nicht geschrieben") from None
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
                                     delete=False) as handle:
        tmp = Path(handle.name)
    try:
        tmp.write_bytes(raw)
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

    `rng` None = der letzte Commit. Der Bereich wird einmal aufgelöst: `range` ist
    `<merge-basis>..<ziel>` als SHAs (gezählt und an `/code-review` gegeben), `base` die
    aufgelöste BASIS für die Commit-Messages (`git log base..ziel`); der Wortlaut des
    Auftrags steht in `_meta.generated`. `changed_lines` zählt die reviewten Dateien; die
    übrigen stehen mit Grund unter `not_reviewed`. Ohne reviewte Datei: KitError „nichts zu
    reviewen", kein Lauf. Bis `split_at` (None = `SPLIT_AT`) — oder wenn das Schneiden nur
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
    rng = DEFAULT_RANGE if rng is None else rng

    repo = Path(_git(Path(repo), "rev-parse", "--show-toplevel").strip())
    stat = numstat(repo, rng)
    resolved = f"{stat.merge_base}..{stat.target}"

    reviewed: dict[str, int] = {}
    not_reviewed = []
    for path, lines in stat.counts.items():
        reason = classify(path, with_tests)
        if reason is None:
            reviewed[path] = lines
        else:
            not_reviewed.append({"file": path, "reason": reason})
    if not reviewed:
        skipped = f", {len(not_reviewed)} Datei(en) ohne Review" if not_reviewed else ""
        raise KitError(f"nichts zu reviewen in {rng!r}: keine geänderte Quelldatei{skipped}")
    changed = sum(reviewed.values())
    packet_size = min(PACKET_SIZE, split_at)

    cut = cut_packets(reviewed, packet_size) if focus != "security" and changed > split_at else []
    split = len(cut) > 1
    if split:
        packets = [{**p, "range": None, "reused_from": None} for p in cut]
    else:
        packets = [{"id": "s1" if focus == "security" else "p1", "files": list(reviewed),
                    "changed_lines": changed, "range": resolved, "reused_from": None}]

    run_id, directory = _new_run_dir(repo, stat.target)
    meta = {"generated": _plan_command(rng, profile, focus, split_at, with_tests), "run": run_id}
    payload = {
        "range": resolved,
        "base": stat.base,
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
