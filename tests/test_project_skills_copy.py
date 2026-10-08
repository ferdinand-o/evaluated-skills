"""`.claude/skills/` ist die Projekt-Installation für die Arbeit an diesem Repo:
Cloud-Sessions laden Projekt-Skills aus dem Repo, Plugins dort nicht (Spec 22, Problem).
Installiert sind nur die Skills, die beim Entwickeln der Sammlung gebraucht werden
(`cc-meta` und der Teil von `cc-dev` ohne API- und Schema-Skills, Spec 20). Jede Kopie
muss byteweise dem Original unter `skills/` entsprechen; eine abweichende Datei ist
Drift, die der Test meldet (G2: kein Hook, nur der Befund)."""

from pathlib import Path

from conftest import REPO_ROOT

INSTALLED = REPO_ROOT / ".claude" / "skills"
IGNORED_DIRS = {"__pycache__"}

# Skills für die Entwicklung des Repos; eine neue Zeile hier plus Kopie nach .claude/skills/.
REPO_DEV_SKILLS = [
    "architecture-map",
    "debug-ledger",
    "dev-report",
    "feature-spec",
    "handoff",
    "impl-plan",
    "review-context",
    "skill-forge",
    "subagent-dev",
    "testing-strategy",
]


def _plugin_skills() -> list[str]:
    assert REPO_DEV_SKILLS == sorted(set(REPO_DEV_SKILLS))
    for name in REPO_DEV_SKILLS:
        assert (REPO_ROOT / "skills" / name / "SKILL.md").is_file(), name
    return REPO_DEV_SKILLS


def _files(root: Path) -> dict[str, bytes]:
    out = {}
    for p in root.rglob("*"):
        if p.is_file() and not (IGNORED_DIRS & set(p.relative_to(root).parts)):
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def test_installed_set_equals_repo_dev_skills():
    on_disk = sorted(p.name for p in INSTALLED.iterdir() if p.is_dir())
    assert on_disk == _plugin_skills(), "Installation und REPO_DEV_SKILLS weichen ab"


def test_installed_copies_match_originals_bytewise():
    drift = []
    for name in _plugin_skills():
        src, dst = _files(REPO_ROOT / "skills" / name), _files(INSTALLED / name)
        for rel in sorted(set(src) | set(dst)):
            if src.get(rel) != dst.get(rel):
                drift.append(f"{name}/{rel}")
    assert not drift, "Kopie unter .claude/skills/ weicht ab, neu kopieren: " + ", ".join(drift[:10])
