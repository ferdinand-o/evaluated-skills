"""Wegwerf-Workspace pro Eval: Fixture kopieren, Skill installieren, Baseline ziehen."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from evalkit.assertions import EXCLUDED_PREFIXES, GIT_HEAD_KEY, current_git_head, file_sha256

FIXTURE_MANIFEST = "fixture.json"


class WorkspaceError(RuntimeError):
    """Der Workspace konnte nicht aufgebaut werden."""


@dataclass(frozen=True)
class Workspace:
    root: Path
    baseline: dict[str, str]


def snapshot(root: Path) -> dict[str, str]:
    """relpath -> sha256 für alle Dateien außerhalb von .git/ und .claude/."""
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            # is_file() folgt Symlinks. Ein vom getesteten Agenten angelegter
            # Symlink könnte aus dem Workspace herauszeigen (z. B. auf ~/.ssh/id_rsa);
            # würden wir ihm folgen, landete der Inhalt des Ziels gehasht in der
            # Baseline und über dump_changed_files sogar im Judge-Prompt, also in
            # einem API-Aufruf. Symlinks werden deshalb nie beobachtet.
            continue
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(EXCLUDED_PREFIXES):
            continue
        result[rel] = file_sha256(path)
    return result


def _copytree(src: Path, dst: Path, *, what: str, **kwargs: object) -> None:
    """shutil.copytree, aber mit WorkspaceError statt rohem shutil.Error/OSError.

    Ein toter Symlink oder ein Berechtigungsproblem in einer Fixture darf nicht als
    unbehandelter Traceback durch den Runner brechen — genau wie bei git und
    fixture.json muss ein Fehler an dieser Stelle als WorkspaceError ankommen.
    """
    try:
        shutil.copytree(src, dst, **kwargs)
    except (shutil.Error, OSError) as exc:
        raise WorkspaceError(f"{what} konnte nicht kopiert werden ({src} -> {dst}): {exc}") from exc


def _git(root: Path, *args: str) -> None:
    try:
        done = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkspaceError(f"git {' '.join(args)} konnte nicht gestartet werden: {exc}") from exc
    if done.returncode != 0:
        raise WorkspaceError(f"git {' '.join(args)} fehlgeschlagen: {done.stderr.strip()}")


def _init_git(root: Path) -> None:
    _git(root, "init", "--quiet", "--initial-branch=main")
    _git(root, "config", "user.email", "evals@example.invalid")
    _git(root, "config", "user.name", "Eval Harness")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "fixture baseline")


def _safe_relpath(raw: object, where: str) -> Path:
    """Fixture-Pfade dürfen den Workspace nicht verlassen (wie in schema.py)."""
    if not isinstance(raw, str) or not raw:
        raise WorkspaceError(f"{where}: Pfad muss ein nicht-leerer String sein, war {raw!r}")
    candidate = PurePosixPath(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise WorkspaceError(f"{where}: Pfad {raw!r} ist absolut oder enthält '..'")
    return Path(raw)


def _apply_commits(root: Path, commits: object) -> None:
    """Erzeuge je Eintrag einen Commit — das Historien-Feld aus dem Manifest.

    Ohne das kann keine Skill geprüft werden, die Git-Verläufe liest: eine ruhige
    Woche, eine Revert-Kette oder eine Release-Range brauchen mehrere Commits.
    """
    if not isinstance(commits, list):
        raise WorkspaceError(f"fixture.json: 'commits' muss eine Liste sein, war {type(commits).__name__}")

    for index, entry in enumerate(commits):
        where = f"fixture.json: commits[{index}]"
        if not isinstance(entry, dict):
            raise WorkspaceError(f"{where}: Eintrag muss ein Objekt sein")
        message = entry.get("message")
        if not isinstance(message, str) or not message:
            raise WorkspaceError(f"{where}: 'message' fehlt oder ist leer")

        for raw_path, content in (entry.get("touch") or {}).items():
            target = root / _safe_relpath(raw_path, where)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(content), encoding="utf-8")

        for raw_path in entry.get("delete") or []:
            target = root / _safe_relpath(raw_path, where)
            if target.is_file():
                target.unlink()

        _git(root, "add", "-A")
        _git(root, "commit", "--quiet", "--allow-empty", "-m", message)

        tag = entry.get("tag")
        if tag:
            if not isinstance(tag, str):
                raise WorkspaceError(f"{where}: 'tag' muss ein String sein")
            _git(root, "tag", tag)


def prepare(dest: Path, skill_dir: Path | None, fixture_dir: Path | None) -> Workspace:
    """Baue einen frischen Workspace unter `dest` auf und liefere seine Baseline.

    `skill_dir=None` ist der Baseline-Workspace für `--without-skill` (Spec 18):
    dieselbe Fixture, dieselbe Git-Historie, derselbe Snapshot — nur wird nichts nach
    `.claude/skills/` installiert. Bringt die Fixture selbst einen Skill-Ordner mit,
    bleibt er; ob der Agent dadurch die Skill sieht, prüft der Runner am
    `skills`-Feld des Transcripts, nicht der Workspace.
    """
    if skill_dir is not None:
        skill_dir = Path(skill_dir)
        if not (skill_dir / "SKILL.md").is_file():
            raise WorkspaceError(f"Skill-Verzeichnis ohne SKILL.md: {skill_dir}")

    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)

    wants_git = False
    manifest: dict = {}
    if fixture_dir is not None:
        fixture_dir = Path(fixture_dir)
        if not fixture_dir.is_dir():
            raise WorkspaceError(f"Fixture nicht gefunden: {fixture_dir}")
        manifest_path = fixture_dir / FIXTURE_MANIFEST
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise WorkspaceError(f"fixture.json ungültig: {manifest_path}: {exc}") from exc
        else:
            manifest = {}
        wants_git = bool(manifest.get("git", False))
        _copytree(
            fixture_dir, dest, what="Fixture",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(FIXTURE_MANIFEST),
        )

    # Der Baseline-Commit ("fixture baseline") entsteht, bevor die Skill installiert
    # wird — sonst landet die Skill selbst im Commit, und ein Agent, der sich per
    # `git log`/`git status` erdet, hält die Installationsspuren des Harness für
    # Projektinhalt (Punkt 4 des Schluss-Reviews; bei der größten Skill der Sammlung
    # wären das 977 von 1007 Zeilen des Baseline-Commits).
    if wants_git:
        _init_git(dest)

    declared_commits = manifest.get("commits") if fixture_dir is not None else None
    if declared_commits is not None:
        if not wants_git:
            raise WorkspaceError("fixture.json: 'commits' verlangt \"git\": true")
        _apply_commits(dest, declared_commits)

    if skill_dir is not None:
        skill_target = dest / ".claude" / "skills" / skill_dir.name
        if skill_target.exists():
            # Eine Fixture, die selbst schon einen .claude/skills/<name>/-Unterbaum
            # mitbringt, wird von der echten Skill stillschweigend überschrieben — das
            # verdient eine sichtbare Warnung statt eines lautlosen Verlusts (Punkt 5).
            print(f"Warnung: Fixture bringt bereits {skill_target.relative_to(dest)} mit — wird überschrieben")
        skill_target.parent.mkdir(parents=True, exist_ok=True)
        _copytree(skill_dir, skill_target, what="Skill", dirs_exist_ok=True)

    baseline = snapshot(dest)
    baseline[GIT_HEAD_KEY] = current_git_head(dest) if wants_git else None
    return Workspace(root=dest, baseline=baseline)


def dump_changed_files(root: Path, baseline: dict[str, str], *, max_bytes: int = 20_000) -> str:
    """Inhalt aller Dateien, die der Lauf neu angelegt oder verändert hat.

    Der Judge urteilt über das erzeugte Artefakt, nicht über die Schlussantwort des
    Agenten — ohne diesen Dump könnte er inhaltliche Behauptungen gar nicht prüfen.
    """
    chunks: list[str] = []
    budget = max_bytes
    for rel, digest in sorted(snapshot(root).items()):
        if baseline.get(rel) == digest:
            continue
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        if "\x00" in text:
            # Nullbytes sind gültiges UTF-8 und überleben errors="replace" — aber
            # `subprocess` verbietet sie in Argumenten, und der Dump geht als Argument
            # in den Judge-Aufruf. Ohne diesen Zweig stirbt jede behavior-Eval mit
            # `ValueError: embedded null byte`, sobald der Agent zufällig eine
            # Binärdatei hinterlässt — ein einziges __pycache__/*.pyc genügt. Der
            # Inhalt hilft dem Judge ohnehin nicht; die Existenz der Datei schon.
            chunks.append(f"--- DATEI: {rel} --- (binär, {len(text)} Zeichen, Inhalt ausgelassen)")
            continue
        if len(text) > budget:
            text = text[:budget] + "\n… (gekürzt)"
        chunks.append(f"--- DATEI: {rel} ---\n{text}")
        budget -= min(len(text), budget)
        if budget <= 0:
            break
    return "\n\n".join(chunks) if chunks else "(keine Datei wurde angelegt oder verändert)"
