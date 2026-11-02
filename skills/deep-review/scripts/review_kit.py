#!/usr/bin/env python3
"""deep-review: Paketplan, Gegenstellen und Abdeckung für `/code-review`. Tier 1: nur Stdlib.

Das Skript reviewt nichts. Es schneidet einen Bereich `BASIS..ZIEL` nach einer festen
Schnittregel in Pakete, schreibt den Plan nach `.skills/cache/deep-review/<lauf>/plan.json`
und nimmt später die Ergebnisse je Paket an (Spec 26). Zielcode wird nie importiert oder
gestartet; Git liest nur.

Stand Task 2: Lauf-ID, JSON-Schreiber, Zählung über `git diff --numstat --no-renames`,
Einordnung (reviewt oder `not_reviewed` mit Grund), Schnittregel und `build_plan`.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import secrets
import shlex
import string
import subprocess
from pathlib import Path, PurePath, PurePosixPath

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
SCRIPT_CMD = "python skills/deep-review/scripts/review_kit.py"
CACHE_DIR = PurePosixPath(".skills/cache/deep-review")
IGNORED_PREFIX = ".skills/"

PROFILES = ("standard", "checkpoint")
FOCI = ("bugs", "security", "quality")

RUN_SUFFIX_CHARS = string.ascii_lowercase + string.digits
RUN_SUFFIX_LEN = 4
SHORT_SHA_LEN = 7

# Einordnung (Spec 26, Ablauf Schritt 2): Dateien ohne Quellcode werden nie reviewt,
# Testdateien nur mit --with-tests.
DOC_SUFFIXES = frozenset({".md", ".markdown", ".rst"})
DOC_NAMES = frozenset({"NEWS", "CHANGES", "CHANGELOG", "AUTHORS", "LICENSE", "COPYING"})
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
                            ".tif", ".tiff"})
PROJECT_SUFFIXES = frozenset({".dproj", ".res"})
TEST_NAME_PATTERNS = ("test_*.py", "*_test.py")
TEST_PAS_PATTERN = "*Test*.pas"
TEST_DIRS = frozenset({"tests", "unittests"})

REASON_DOC = "keine Quelldatei: Doku"
REASON_IMAGE = "keine Quelldatei: Bild"
REASON_PROJECT = "keine Quelldatei: Delphi-Projekt oder Ressource"
REASON_TEST = "Testdatei: nur mit --with-tests"


class KitError(RuntimeError):
    """Ein Schritt ist gescheitert — mit einer Ursache, die der Nutzer versteht."""


# --- Git ----------------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> str:
    """git-Aufruf, der bei Fehlschlag wirft. Ausgabe als UTF-8, nie geraten."""
    try:
        done = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise KitError(f"git {' '.join(args)} konnte nicht gestartet werden: {exc}") from exc
    if done.returncode != 0:
        stderr = done.stderr.decode("utf-8", errors="replace").strip()
        raise KitError(f"git {' '.join(args)} fehlgeschlagen: {stderr}")
    return done.stdout.decode("utf-8", errors="surrogateescape")


def _commit(repo: Path, rev: str) -> str:
    if not rev or rev.startswith("-"):
        raise KitError(f"ungültige Revision: {rev!r}")
    return _git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").strip()


def split_range(repo: Path, rng: str) -> tuple[str, str]:
    """`BASIS..ZIEL` → (Basis-SHA, Ziel-SHA). Eine einzelne Revision `X` heißt `X^..X`
    (Standard: der letzte Commit). Drei Punkte bräuchten eine Merge-Base und sind abgelehnt."""
    if "..." in rng:
        raise KitError("Bereich mit '...' nicht unterstützt — gib BASIS..ZIEL an")
    if ".." in rng:
        base, target = rng.split("..", 1)
        base, target = base or "HEAD", target or "HEAD"
    else:
        base, target = f"{rng}^", rng
    return _commit(repo, base), _commit(repo, target)


def _ignored(path: str) -> bool:
    return path == IGNORED_PREFIX.rstrip("/") or path.startswith(IGNORED_PREFIX)


def numstat(repo, rng):
    """Geänderte Zeilen je Datei im Bereich: hinzugefügte plus gelöschte, nach Pfad sortiert.

    `git diff --numstat --no-renames`: eine Umbenennung ist eine gelöschte und eine neue
    Datei; Binärdateien zählen 0; Pfade unter `.skills/` zählen nie. Pfade sind
    repo-relativ in POSIX-Form, wie Git sie ausgibt."""
    repo = Path(repo)
    base, target = split_range(repo, rng)
    out = _git(repo, "diff", "--numstat", "--no-renames", "--no-textconv", "--no-ext-diff",
               "-z", base, target, "--")
    counts: dict[str, int] = {}
    for record in out.split("\0"):
        if not record:
            continue
        added, deleted, path = record.split("\t", 2)
        if _ignored(path):
            continue
        lines = 0 if "-" in (added, deleted) else int(added) + int(deleted)
        counts[path] = counts.get(path, 0) + lines
    return dict(sorted(counts.items()))


# --- Einordnung und Schnittregel -------------------------------------------------------------

def classify(path, with_tests):
    """None, wenn die Datei reviewt wird; sonst der Grund für `not_reviewed`.

    Ohne Quellcode (nie reviewt): Doku (Markdown, reStructuredText, `NEWS` und Verwandte
    ohne Endung), Bilder, `.dproj`, `.res`. Tests (`test_*.py`, `*_test.py`, unter `tests/`
    oder `unittests/`, `*Test*.pas`) nur mit `with_tests` — so lief die Messung."""
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
    is_test = (
        any(fnmatch.fnmatchcase(pure.name, pattern) for pattern in TEST_NAME_PATTERNS)
        or (suffix == ".pas" and fnmatch.fnmatchcase(pure.stem + ".pas", TEST_PAS_PATTERN))
        or any(part in TEST_DIRS for part in pure.parts[:-1])
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
    if not isinstance(packet_size, int) or packet_size < 1:
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
    return dt.datetime.now()


def new_run_id(sha):
    """Lauf-ID `<JJJJ-MM-TT>-<HHMMSS>-<kurz-sha>-<4 Zufallszeichen>` in Ortszeit.

    Zwei IDs aus demselben Prozess sind nie gleich, auch nicht in derselben Sekunde;
    zwischen Prozessen sichert `build_plan` über das Anlegen des Laufordners ab."""
    short = str(sha).strip().lower()[:SHORT_SHA_LEN]
    if len(short) < SHORT_SHA_LEN or any(c not in string.hexdigits for c in short):
        raise KitError(f"kein Commit-SHA: {sha!r}")
    stamp = _now().strftime("%Y-%m-%d-%H%M%S")
    while True:
        suffix = "".join(secrets.choice(RUN_SUFFIX_CHARS) for _ in range(RUN_SUFFIX_LEN))
        run_id = f"{stamp}-{short}-{suffix}"
        if run_id not in _ISSUED:
            _ISSUED.add(run_id)
            return run_id


def _json_default(value):
    if isinstance(value, PurePath):
        if value.is_absolute():
            raise ValueError(f"absoluter Pfad in einem Artefakt: {value}")
        return value.as_posix()
    raise TypeError(f"nicht als JSON schreibbar: {type(value).__name__}")


def write_json(path, meta, payload):
    """Die eine Schreibfunktion für alle JSON-Artefakte des Laufs (Spec 26, E3).

    `_meta` zuerst mit `skill`, `schema`, dann den Feldern aus `meta` (Pflicht:
    `generated`, das Kommando); danach `payload` in seiner Reihenfolge. `ensure_ascii=False`,
    Pfad-Objekte als repo-relative POSIX-Pfade. Schreibt über eine Temp-Datei und ersetzt
    atomar. Rückgabe: das geschriebene Objekt."""
    if "generated" not in meta:
        raise KitError("_meta braucht 'generated' (das Kommando)")
    if "_meta" in payload:
        raise KitError("payload darf kein eigenes _meta tragen")
    data = {"_meta": {"skill": SKILL_NAME, "schema": SCHEMA_VERSION, **meta}, **payload}
    text = json.dumps(data, ensure_ascii=False, indent=2, default=_json_default) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return json.loads(text)


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

    `changed_lines` zählt die reviewten Dateien; die übrigen stehen mit Grund unter
    `not_reviewed`. Bis `split_at` (None = `SPLIT_AT`) ein Paket `p1` über den
    Originalbereich, `split: false`; darüber `split: true`, Pakete nach `cut_packets` mit
    `packet_size` = kleiner von `PACKET_SIZE` und `split_at`, deren `range` die
    Paket-Bereiche füllen. Fokus `security`: ein Paket `s1` über den ganzen Bereich, nie
    geteilt. `file_keys` bleibt leer, bis Datei-Schlüssel gesammelt werden. Die Lauf-ID
    steht in `_meta.run`; `plan.json` liegt in `run_dir(repo, run)`."""
    if profile not in PROFILES:
        raise KitError(f"Profil {profile!r} unbekannt — erlaubt: {', '.join(PROFILES)}")
    if focus not in FOCI:
        raise KitError(f"Fokus {focus!r} unbekannt — erlaubt: {', '.join(FOCI)}")
    if profile == "checkpoint" and focus != "bugs":
        raise KitError("Profil checkpoint prüft nur Fokus bugs")
    split_at = SPLIT_AT if split_at is None else split_at
    if not isinstance(split_at, int) or isinstance(split_at, bool) or split_at < 1:
        raise KitError(f"split_at muss eine positive Zahl sein, nicht {split_at!r}")

    repo = Path(_git(Path(repo), "rev-parse", "--show-toplevel").strip())
    counts = numstat(repo, rng)
    _, target = split_range(repo, rng)

    reviewed: dict[str, int] = {}
    not_reviewed = []
    for path, lines in counts.items():
        reason = classify(path, with_tests)
        if reason is None:
            reviewed[path] = lines
        else:
            not_reviewed.append({"file": path, "reason": reason})
    changed = sum(reviewed.values())
    packet_size = min(PACKET_SIZE, split_at)
    split = focus != "security" and changed > split_at

    if not reviewed:
        packets = []
    elif split:
        packets = [{**p, "range": None, "reused_from": None} for p in cut_packets(reviewed, packet_size)]
    else:
        packets = [{"id": "s1" if focus == "security" else "p1", "files": list(reviewed),
                    "changed_lines": changed, "range": rng, "reused_from": None}]

    run_id, directory = _new_run_dir(repo, target)
    meta = {"generated": _plan_command(rng, profile, focus, split_at, with_tests), "run": run_id}
    payload = {
        "range": rng,
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
    return write_json(directory / "plan.json", meta, payload)
