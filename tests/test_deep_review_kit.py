"""deep-review (Spec 26): Messfixtures und review_kit.py.

`dr-seeded` trägt fünf eingebaute Fehler, `dr-seeded-clean` ist dieselbe Fixture ohne sie.
Beide bauen denselben Bereich `base..HEAD`; die Trefferquote misst der Report daran."""

import difflib
import json
import re
import subprocess
import sys

from conftest import REPO_ROOT, git
from evalkit.workspace import prepare

FIXTURES = REPO_ROOT / "evals" / "fixtures"
SEEDED = FIXTURES / "dr-seeded"
CLEAN = FIXTURES / "dr-seeded-clean"
LOCATION_RE = re.compile(r"`([\w./-]+\.py):(\d+)`")
GIVEAWAYS = re.compile(r"\b(bug|fixme|todo|xxx|hack|fehler|absichtlich|eingebaut|seeded)\b", re.IGNORECASE)


def _manifest(fixture):
    return json.loads((fixture / "fixture.json").read_text(encoding="utf-8"))


def _hunks(seeded_text, clean_text):
    """Abweichende Blöcke als Zeilenbereich (1-basiert, inklusiv) in der Seeded-Fassung."""
    matcher = difflib.SequenceMatcher(None, seeded_text.splitlines(), clean_text.splitlines(), autojunk=False)
    hunks = []
    for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        # Reine Einfügung in clean: die Stelle liegt zwischen Zeile i1 und i1 + 1.
        hunks.append((i1, i2 + 1) if i1 == i2 else (i1 + 1, i2))
    return hunks


def _pytest(root):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=root, capture_output=True, text=True, timeout=120, check=False,
    )


def test_seeded_fixtures(tmp_path):
    seeded, clean = _manifest(SEEDED), _manifest(CLEAN)
    for meta in (seeded, clean):
        assert meta["git"] is True
        assert len(meta["commits"]) == 2
        assert meta["commits"][0]["tag"] == "base"
        assert "tag" not in meta["commits"][1]
    # README.md liegt im Ordner, weil prepare() den Baseline-Commit ohne --allow-empty macht.
    for fixture in (SEEDED, CLEAN):
        assert sorted(p.name for p in fixture.iterdir()) == ["README.md", "fixture.json"]
    assert (SEEDED / "README.md").read_bytes() == (CLEAN / "README.md").read_bytes()

    # Gerüst, Commit-Messages und Dateimenge sind gleich; nur der Code-Commit weicht ab.
    assert seeded["commits"][0] == clean["commits"][0]
    assert [c["message"] for c in seeded["commits"]] == [c["message"] for c in clean["commits"]]
    code, fixed = seeded["commits"][1]["touch"], clean["commits"][1]["touch"]
    assert code.keys() == fixed.keys()

    # Genau fünf abweichende Stellen, jede in der description mit Datei:Zeile benannt.
    named = {(path, int(line)) for path, line in LOCATION_RE.findall(seeded["description"])}
    hunks = [(path, hunk) for path in sorted(code) for hunk in _hunks(code[path], fixed[path])]
    assert len(hunks) == 5, hunks
    for path, (start, end) in hunks:
        assert any(p == path and start <= line <= end for p, line in named), (path, start, end)
    for number in range(1, 6):
        assert f"Fehler {number}" in seeded["description"]
    assert {path for path, _ in hunks} | {path for path, _ in named} <= code.keys()

    # Kein Hinweis im Code selbst: Kommentare und Docstrings verraten nichts.
    for path, text in code.items():
        assert not GIVEAWAYS.search(text), path

    # Die mitgelieferten Tests laufen auf beiden Fassungen grün — also trifft keiner die fünf.
    for name, fixture in (("seeded", SEEDED), ("clean", CLEAN)):
        ws = prepare(tmp_path / name, None, fixture)
        assert git(ws.root, "rev-parse", "--verify", "base").strip()
        assert git(ws.root, "diff", "--name-only", "base..HEAD").split() == sorted(code)
        done = _pytest(ws.root)
        assert done.returncode == 0, done.stdout + done.stderr
        assert " passed" in done.stdout
