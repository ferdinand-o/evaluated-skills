"""deep-review (Spec 26): Messfixtures und review_kit.py.

`dr-seeded` trägt fünf eingebaute Fehler, `dr-seeded-clean` ist dieselbe Fixture ohne sie.
Beide bauen denselben Bereich `base..HEAD`; die Trefferquote misst der Report daran. Jeder
Fehler hängt an einer Stelle in `base`, die der Diff nicht berührt."""

import datetime as dt
import difflib
import hashlib
import inspect
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import PurePosixPath

import pytest

from conftest import REPO_ROOT, git, load_script
from evalkit.workspace import prepare

FIXTURES = REPO_ROOT / "evals" / "fixtures"
SEEDED = FIXTURES / "dr-seeded"
CLEAN = FIXTURES / "dr-seeded-clean"
LOCATION_RE = re.compile(r"`([\w./-]+\.py):(\d+)`")
GIVEAWAYS = re.compile(r"\b(bug|fixme|todo|xxx|hack|absichtlich|eingebaut|seeded)\b", re.IGNORECASE)
SEGMENT_RE = re.compile(r"Fehler (\d) \(")


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
    base = seeded["commits"][0]["touch"]
    hunks = [(path, hunk) for path in sorted(code) for hunk in _hunks(code[path], fixed[path])]
    assert len(hunks) == 5, hunks

    def covers(path, line):
        return any(p == path and start <= line <= end for p, (start, end) in hunks)

    description = seeded["description"]
    starts = [m.start() for m in SEGMENT_RE.finditer(description)]
    assert [m.group(1) for m in SEGMENT_RE.finditer(description)] == ["1", "2", "3", "4", "5"]
    segments = [description[a:b] for a, b in zip(starts, starts[1:] + [len(description)])]
    covered = set()
    for segment in segments:
        named = [(path, int(line)) for path, line in LOCATION_RE.findall(segment)]
        in_diff = [(p, n) for p, n in named if p in code and covers(p, n)]
        # Der Vertrag liegt in base, in einer Datei, die base..HEAD nicht berührt.
        in_base = [(p, n) for p, n in named if p in base and p not in code and n <= len(base[p].splitlines())]
        assert in_diff and in_base, segment[:40]
        covered |= {(p, h) for p, h in hunks for q, n in in_diff if p == q and h[0] <= n <= h[1]}
    assert len(covered) == 5

    # Kein Hinweis im Code selbst: Kommentare und Docstrings verraten nichts.
    for path, text in code.items():
        assert not GIVEAWAYS.search(text), path

    # Die mitgelieferten Tests laufen auf beiden Fassungen grün — also trifft keiner die fünf.
    for name, fixture in (("seeded", SEEDED), ("clean", CLEAN)):
        ws = prepare(tmp_path / name, None, fixture)
        assert git(ws.root, "rev-parse", "--verify", "base").strip()
        assert git(ws.root, "diff", "--name-only", "base..HEAD").split() == sorted(code)
        assert not set(git(ws.root, "diff", "--name-only", "base..HEAD").split()) & {
            p for p, _ in LOCATION_RE.findall(description) if p not in code}
        done = _pytest(ws.root)
        assert done.returncode == 0, done.stdout + done.stderr
        assert " passed" in done.stdout


# --- review_kit.py: Lauf-ID, Plan und Schnittregel (Task 2) -----------------------------

KIT_PATH = "skills/deep-review/scripts/review_kit.py"
RUN_ID_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{6})-([0-9a-f]{7})-([0-9a-z]{4})$")
PLAN_KEYS = ["_meta", "range", "base", "target", "log_base", "root", "profile", "focus", "split",
             "split_at", "packet_size", "changed_lines", "packets", "file_keys", "not_reviewed"]
PACKET_KEYS = ["id", "files", "changed_lines", "range", "reused_from"]


def _kit():
    # Erst im Test laden: fehlt das Skript, scheitern nur die Tests, die es brauchen.
    return load_script(KIT_PATH)


def _lines(n, tag="x"):
    return "".join(f"{tag}_{i} = {i}\n" for i in range(n))


def _commit_repo(root, before, after):
    """Repo mit zwei Commits, Tag `base` auf dem ersten. Ein Wert None löscht die Datei,
    Bytes werden so geschrieben, wie sie sind."""
    git(root, "init", "--quiet", "--initial-branch=main")
    git(root, "config", "user.email", "t@example.invalid")
    git(root, "config", "user.name", "Test")
    for state, message in ((before, "basis"), (after, "änderung")):
        for rel, text in state.items():
            path = root / rel
            if text is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(text, bytes):
                path.write_bytes(text)
            else:
                path.write_text(text, encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "--quiet", "-m", message)
        if message == "basis":
            git(root, "tag", "base")
    return root


def _read_plan(root, plan):
    """plan.json des Laufs von der Platte; muss dem Rückgabewert von build_plan gleichen."""
    path = root / ".skills" / "cache" / "deep-review" / plan["_meta"]["run"] / "plan.json"
    text = path.read_text(encoding="utf-8")
    on_disk = json.loads(text)
    assert on_disk == plan
    return on_disk, text


def test_run_ids_do_not_collide(monkeypatch):
    kit = _kit()
    frozen = dt.datetime(2026, 11, 2, 14, 5, 9, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(kit, "_now", lambda: frozen)
    sha = "0123456789abcdef0123456789abcdef01234567"
    ids = [kit.new_run_id(sha) for _ in range(200)]
    assert len(set(ids)) == len(ids)
    for run_id in ids:
        match = RUN_ID_RE.match(run_id)
        assert match, run_id
        assert match.groups()[:3] == ("2026-11-02", "140509", "0123456")


def test_plan_single_packet_below_threshold(tmp_path):
    kit = _kit()
    root = _commit_repo(
        tmp_path,
        {"app/core.py": _lines(5), "lib/util.py": _lines(5, "y"), ".skills/cache/x.json": "{}\n"},
        {"app/core.py": _lines(5) + _lines(20, "neu"),  # +20
         "lib/util.py": _lines(5, "z"),                  # -5 +5
         ".skills/cache/x.json": _lines(500)},           # zählt nie
    )
    head = git(root, "rev-parse", "HEAD")
    resolved = f"{git(root, 'rev-parse', 'base').strip()}..{head.strip()}"
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)

    on_disk, text = _read_plan(root, plan)
    assert list(on_disk) == PLAN_KEYS
    assert on_disk["_meta"]["skill"] == "deep-review"
    assert on_disk["_meta"]["schema"] == 1
    assert "review_kit.py plan --range base..HEAD" in on_disk["_meta"]["generated"]
    assert RUN_ID_RE.match(on_disk["_meta"]["run"])
    assert text.endswith("\n") and '"_meta"' in text.splitlines()[1]

    assert on_disk["range"] == resolved and on_disk["base"] == git(root, "rev-parse", "base").strip()
    assert on_disk["profile"] == "standard" and on_disk["focus"] == "bugs"
    assert on_disk["split"] is False
    assert on_disk["split_at"] == kit.SPLIT_AT == 800
    assert on_disk["changed_lines"] == 30
    assert len(on_disk["packets"]) == 1
    packet = on_disk["packets"][0]
    assert list(packet) == PACKET_KEYS
    assert packet == {"id": "p1", "files": ["app/core.py", "lib/util.py"], "changed_lines": 30,
                      "range": resolved, "reused_from": None}
    assert on_disk["not_reviewed"] == []
    assert ".skills/cache/x.json" not in text
    assert kit.numstat(root, "base..HEAD").counts == {"app/core.py": 20, "lib/util.py": 10}
    # Keine Hilfscommits, HEAD unverändert.
    assert git(root, "for-each-ref", "refs/deep-review/") == ""
    assert git(root, "rev-parse", "HEAD") == head


def test_plan_cut_rule(tmp_path):
    kit = _kit()
    files = {"e/x.py": 10, "d/huge.py": 150, "c/big3.py": 30, "c/big2.py": 50, "c/big1.py": 60,
             "b/three.py": 40, "a/two.py": 20, "a/one.py": 30}
    packets = kit.cut_packets(files, 100)
    assert [(p["id"], p["files"], p["changed_lines"]) for p in packets] == [
        ("p1", ["a/one.py", "a/two.py", "b/three.py"], 90),  # zwei Verzeichnisse, ein Paket
        ("p2", ["c/big1.py"], 60),                           # Gruppe über 100 an Dateigrenzen
        ("p3", ["c/big2.py", "c/big3.py"], 80),
        ("p4", ["d/huge.py"], 150),                          # Datei über 100 allein
        ("p5", ["e/x.py"], 10),
    ]
    # Paare statt Dict liefern dasselbe.
    assert kit.cut_packets(sorted(files.items(), reverse=True), 100) == packets

    # Über split_at: geteilt, packet_size = kleiner von PACKET_SIZE und split_at.
    root = _commit_repo(
        tmp_path,
        {"pkg/a.py": "", "pkg/b.py": "", "zz/c.py": ""},
        {"pkg/a.py": _lines(30), "pkg/b.py": _lines(30, "b"), "zz/c.py": _lines(30, "c")},
    )
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", 50, False)
    _read_plan(root, plan)
    assert plan["split"] is True and plan["split_at"] == 50 and plan["packet_size"] == 50
    assert plan["changed_lines"] == 90
    assert [(p["id"], p["files"]) for p in plan["packets"]] == [
        ("p1", ["pkg/a.py"]), ("p2", ["pkg/b.py"]), ("p3", ["zz/c.py"])]
    assert all(list(p) == PACKET_KEYS for p in plan["packets"])

    big = kit.build_plan(root, "base..HEAD", "checkpoint", "bugs", 1000, False)
    assert big["split"] is False and big["packet_size"] == kit.PACKET_SIZE == 600
    assert [p["id"] for p in big["packets"]] == ["p1"]

    # Fokus security: ein Paket s1 über den ganzen Bereich, auch über split_at.
    sec = kit.build_plan(root, "base..HEAD", "standard", "security", 50, False)
    assert sec["split"] is False
    assert sec["packets"] == [{"id": "s1", "files": ["pkg/a.py", "pkg/b.py", "zz/c.py"],
                               "changed_lines": 90, "range": sec["range"], "reused_from": None}]
    assert git(root, "for-each-ref", "refs/deep-review/") == ""
    # Drei Pläne kurz nacheinander landen in drei Läufen.
    assert len({plan["_meta"]["run"], big["_meta"]["run"], sec["_meta"]["run"]}) == 3


def test_plan_not_reviewed(tmp_path):
    kit = _kit()
    root = _commit_repo(
        tmp_path,
        {"README.md": "# x\n", "app/old.py": _lines(7), "app/main.py": "", "tests/test_x.py": "",
         "docs/bild.png": "", "Proj.dproj": "", "src/AppTest.pas": "", "app/x_test.py": ""},
        {"README.md": "# x\n\nmehr\n", "app/old.py": None, "app/new.py": _lines(7),
         "app/main.py": _lines(3), "tests/test_x.py": _lines(4), "docs/bild.png": "neu\n",
         "Proj.dproj": "<x/>\n", "src/AppTest.pas": "unit AppTest;\n", "app/x_test.py": "a = 1\n"},
    )
    assert kit.classify("app/main.py", False) is None
    assert kit.classify("NEWS", False) and kit.classify("res/App.res", False)
    assert kit.classify("unittests/foo.py", False) and kit.classify("tests/test_x.py", True) is None
    assert kit.classify("README.md", True)
    assert kit.classify("app/license.py", False) is None

    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    _read_plan(root, plan)
    reasons = {e["file"]: e["reason"] for e in plan["not_reviewed"]}
    assert list(plan["not_reviewed"][0]) == ["file", "reason"]
    tests = {"tests/test_x.py", "src/AppTest.pas", "app/x_test.py"}
    assert set(reasons) == {"README.md", "docs/bild.png", "Proj.dproj"} | tests
    assert all(reasons.values())
    assert {reasons[t] for t in tests} != {reasons["README.md"]}
    # Umbenennung: gelöschte und neue Datei, je mit allen Zeilen.
    assert plan["packets"][0]["files"] == ["app/main.py", "app/new.py", "app/old.py"]
    assert plan["changed_lines"] == 3 + 7 + 7

    with_tests = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, True)
    assert set(with_tests["packets"][0]["files"]) == {"app/main.py", "app/new.py", "app/old.py"} | tests
    assert {e["file"] for e in with_tests["not_reviewed"]} == {"README.md", "docs/bild.png", "Proj.dproj"}
    assert with_tests["changed_lines"] == 17 + 4 + 1 + 1


# --- review_kit.py: Funde des Prüfpunkts nach Task 2 (F1–F17) ----------------------------

def _rev(root, rev):
    return git(root, "rev-parse", rev).strip()


def _runs(root):
    cache = root / ".skills" / "cache" / "deep-review"
    return sorted(p.name for p in cache.iterdir()) if cache.exists() else []


def test_f01_non_utf8_path_is_a_kit_error(tmp_path):
    kit = _kit()
    name = os.fsdecode(b"caf\xe9.py")
    # Der Plan bricht daran nicht ab (G7); der Schreiber weist solchen Text ab: KitError,
    # keine Temp-Datei.
    target = tmp_path / "out" / "x.json"
    with pytest.raises(kit.KitError, match="UTF-8"):
        kit.write_json(target, {"generated": "t"}, {"file": name})
    assert not target.parent.exists() or list(target.parent.iterdir()) == []


def test_f02_plan_stores_resolved_range(tmp_path):
    kit = _kit()
    root = _commit_repo(tmp_path, {"app/a.py": ""}, {"app/a.py": _lines(4)})
    base, head = _rev(root, "base"), _rev(root, "HEAD")
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    assert plan["range"] == f"{base}..{head}" and plan["base"] == base
    assert plan["packets"][0]["range"] == f"{base}..{head}"
    single = kit.build_plan(root, "HEAD", "standard", "bugs", None, False)
    assert single["range"] == f"{base}..{head}"
    assert single["packets"][0]["range"] == f"{base}..{head}"
    assert "--range HEAD " in single["_meta"]["generated"]


def test_f03_range_resolved_once(tmp_path, monkeypatch):
    kit = _kit()
    root = _commit_repo(tmp_path, {"app/a.py": ""}, {"app/a.py": _lines(4)})
    calls = []
    real = kit._git

    def spy(repo, *args):
        if args and args[0] == "rev-parse" and any(a.endswith("^{commit}") for a in args):
            calls.append(args)
        return real(repo, *args)

    monkeypatch.setattr(kit, "_git", spy)
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    assert len(calls) == 2, calls
    assert plan["_meta"]["run"].split("-")[4] == _rev(root, "HEAD")[:7]
    stat = kit.numstat(root, "base..HEAD")
    assert (stat.span.base, stat.span.target, stat.span.log_base) == (
        _rev(root, "base"), _rev(root, "HEAD"), _rev(root, "base"))


def test_f04_test_files_case_insensitive():
    kit = _kit()
    for path in ("UnitTests/FooTests.pas", "Tests/FooTest.py", "pkg/Test_foo.py",
                 "pkg/foo_TEST.py", "src/test_foo.pas", "src/FooTest.pas"):
        assert kit.classify(path, False) == kit.REASON_TEST, path
        assert kit.classify(path, True) is None, path
    for path in ("src/Latest.pas", "app/contest.py", "app/attest.py"):
        assert kit.classify(path, False) is None, path


def test_f05_root_commit_against_empty_tree(tmp_path):
    kit = _kit()
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "a.py").write_text(_lines(3), encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "erster")
    empty = git(tmp_path, "hash-object", "-t", "tree", "/dev/null").strip()
    head = _rev(tmp_path, "HEAD")
    plan = kit.build_plan(tmp_path, "HEAD", "standard", "bugs", None, False)
    assert plan["changed_lines"] == 3
    assert plan["base"] == empty and plan["target"] == head and plan["log_base"] is None


def test_f06_unknown_revision_names_it(tmp_path):
    kit = _kit()
    root = _commit_repo(tmp_path, {"app/a.py": ""}, {"app/a.py": _lines(4)})
    with pytest.raises(kit.KitError, match=r"'mian'.*unbekannt"):
        kit.build_plan(root, "mian..HEAD", "standard", "bugs", None, False)
    assert _runs(root) == []


def test_f07_two_dot_range_counts_from_merge_base(tmp_path):
    kit = _kit()
    root = _commit_repo(tmp_path, {"app/f.py": ""}, {"app/f.py": _lines(1)})
    fork = _rev(root, "HEAD")
    git(root, "checkout", "--quiet", "-b", "feature")
    (root / "app" / "f.py").write_text(_lines(6), encoding="utf-8")
    git(root, "commit", "--quiet", "-am", "feature")
    git(root, "checkout", "--quiet", "main")
    (root / "main").mkdir()
    (root / "main" / "big.py").write_text(_lines(50), encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "main wächst")
    stat = kit.numstat(root, "main..feature")
    assert stat.counts == {"app/f.py": 5}
    assert stat.span.base == fork and stat.span.log_base == _rev(root, "main")
    plan = kit.build_plan(root, "main..feature", "standard", "bugs", None, False)
    assert plan["changed_lines"] == 5
    assert plan["range"] == f"{fork}..{_rev(root, 'feature')}"


def test_f08_nothing_to_review_refuses(tmp_path):
    kit = _kit()
    root = _commit_repo(tmp_path, {"README.md": "# x\n", "tests/test_x.py": ""},
                        {"README.md": "# y\n", "tests/test_x.py": _lines(3)})
    with pytest.raises(kit.KitError, match="nichts zu reviewen"):
        kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    with pytest.raises(kit.KitError, match="nichts zu reviewen"):
        kit.build_plan(root, "base..base", "standard", "bugs", None, False)
    assert _runs(root) == []
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, True)
    assert plan["packets"][0]["files"] == ["tests/test_x.py"]


def test_f09_temp_file_is_private_and_removed(tmp_path, monkeypatch):
    kit = _kit()
    target = tmp_path / "plan.json"
    foreign = tmp_path / "plan.json.tmp"
    foreign.write_text("fremd", encoding="utf-8")
    kit.write_json(target, {"generated": "t"}, {"a": 1})
    assert foreign.read_text(encoding="utf-8") == "fremd"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["plan.json", "plan.json.tmp"]

    def boom(*_args):
        raise OSError("platte voll")

    monkeypatch.setattr(kit.os, "replace", boom)
    with pytest.raises((OSError, kit.KitError)):
        kit.write_json(tmp_path / "zwei.json", {"generated": "t"}, {"a": 1})
    assert sorted(p.name for p in tmp_path.iterdir()) == ["plan.json", "plan.json.tmp"]


def test_f10_failed_write_leaves_no_run_dir(tmp_path, monkeypatch):
    kit = _kit()
    root = _commit_repo(tmp_path, {"app/a.py": ""}, {"app/a.py": _lines(4)})

    def boom(*_args):
        raise kit.KitError("schreiben gescheitert")

    monkeypatch.setattr(kit, "write_json", boom)
    with pytest.raises(kit.KitError, match="schreiben gescheitert"):
        kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    assert _runs(root) == []


def test_f11_meta_cannot_override_fixed_fields(tmp_path):
    kit = _kit()
    for key in ("skill", "schema"):
        with pytest.raises(kit.KitError, match=key):
            kit.write_json(tmp_path / "x.json", {"generated": "t", key: 2}, {})
    assert not (tmp_path / "x.json").exists()
    data = kit.write_json(tmp_path / "x.json", {"generated": "t", "run": "r"}, {})
    assert data["_meta"] == {"skill": "deep-review", "schema": 1, "generated": "t", "run": "r"}


def test_f12_one_packet_is_not_split(tmp_path):
    kit = _kit()
    root = _commit_repo(tmp_path, {"app/big.py": ""}, {"app/big.py": _lines(900)})
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    assert plan["split"] is False and plan["changed_lines"] == 900
    assert [(p["id"], p["range"]) for p in plan["packets"]] == [("p1", plan["range"])]


def test_f13_cut_packets_rejects_bool():
    kit = _kit()
    with pytest.raises(kit.KitError):
        kit.cut_packets({"a.py": 1}, True)


def test_f14_missing_range_is_last_commit(tmp_path):
    kit = _kit()
    root = _commit_repo(tmp_path, {"app/a.py": ""}, {"app/a.py": _lines(4)})
    plan = kit.build_plan(root, None, "standard", "bugs", None, False)
    assert plan["range"] == f"{_rev(root, 'HEAD^')}..{_rev(root, 'HEAD')}"
    assert "--range HEAD " in plan["_meta"]["generated"]
    assert kit.numstat(root, None).counts == {"app/a.py": 4}
    with pytest.raises(kit.KitError):
        kit.numstat(root, "")


def test_f15_run_id_in_utc(monkeypatch):
    kit = _kit()
    assert kit._now().utcoffset() == dt.timedelta(0)
    sha = "0123456789abcdef0123456789abcdef01234567"
    utc = dt.timezone.utc
    # Zeitumstellung 2026-10-25: 02:30 Sommerzeit (00:30 UTC) liegt vor 02:10 Winterzeit
    # (01:10 UTC); in UTC sortiert die Lauf-ID richtig.
    monkeypatch.setattr(kit, "_now", lambda: dt.datetime(2026, 10, 25, 0, 30, tzinfo=utc))
    first = kit.new_run_id(sha)
    monkeypatch.setattr(kit, "_now", lambda: dt.datetime(2026, 10, 25, 1, 10, tzinfo=utc))
    second = kit.new_run_id(sha)
    assert first.startswith("2026-10-25-003000-") and second.startswith("2026-10-25-011000-")
    assert sorted([second, first]) == [first, second]


def test_f16_skills_excluded_by_pathspec(tmp_path, monkeypatch):
    kit = _kit()
    root = _commit_repo(tmp_path, {"app/a.py": "", ".skills/x.json": "{}\n"},
                        {"app/a.py": _lines(4), ".skills/x.json": _lines(9)})
    diffs = []
    real = kit._git

    def spy(repo, *args):
        if args and args[0] == "diff":
            diffs.append(args)
        return real(repo, *args)

    monkeypatch.setattr(kit, "_git", spy)
    assert kit.numstat(root, "base..HEAD").counts == {"app/a.py": 4}
    assert len(diffs) == 1 and any("exclude" in a and a.endswith(".skills") for a in diffs[0])
    # Aus einem Unterordner zählt dasselbe.
    assert kit.numstat(root / "app", "base..HEAD").counts == {"app/a.py": 4}


def test_f17_write_json_returns_normalized_data(tmp_path, monkeypatch):
    kit = _kit()

    def no_loads(*_args, **_kwargs):
        raise AssertionError("json.loads aufgerufen")

    with monkeypatch.context() as m:
        m.setattr(kit.json, "loads", no_loads)
        data = kit.write_json(tmp_path / "x.json", {"generated": "t"},
                              {"file": PurePosixPath("a/b.py"), "pair": (1, 2)})
    assert data == {"_meta": {"skill": "deep-review", "schema": 1, "generated": "t"},
                    "file": "a/b.py", "pair": [1, 2]}
    assert json.loads((tmp_path / "x.json").read_text(encoding="utf-8")) == data
    with pytest.raises(kit.KitError):
        kit.write_json(tmp_path / "y.json", {"generated": "t"}, {"file": PurePosixPath("/abs")})


# --- review_kit.py: Funde des zweiten Prüfpunkts nach Task 2 (G1–G10) ---------------------

def _root_repo(root, files):
    git(root, "init", "--quiet", "--initial-branch=main")
    git(root, "config", "user.email", "t@example.invalid")
    git(root, "config", "user.name", "Test")
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "erster")
    return root


def test_g01_pas_test_rule_uses_word_boundaries():
    kit = _kit()
    # Angepasst an die Segmentregel (H1, H4): `FooTEST` ist Foo + TEST, `MyTest2` My + Test + 2,
    # also Tests; `testfoo` und `TESTUNIT` haben kein Glied `Test`/`Tests` und sind keine.
    for path in ("src/AppTest.pas", "src/FooTests.pas", "src/TestUtils.pas", "src/FooTEST.pas",
                 "src/MyTestUnit.pas", "src/MyTest2.pas"):
        assert kit.classify(path, False) == kit.REASON_TEST, path
    for path in ("src/LATEST.pas", "src/CONTEST.pas", "src/ATTEST.pas", "src/GREATEST.pas",
                 "src/mytestunit.pas", "src/Latest.pas", "src/Contests.pas", "src/testfoo.pas",
                 "src/TESTUNIT.pas"):
        assert kit.classify(path, False) is None, path


def test_g02_root_commit_range_round_trips(tmp_path):
    kit = _kit()
    root = _root_repo(tmp_path, {"app/a.py": _lines(3)})
    head = _rev(root, "HEAD")
    plan = kit.build_plan(root, None, "standard", "bugs", None, False)
    # Angepasst an H2: das Paket eines Wurzel-Commit-Plans trägt range None.
    assert plan["range"] == head and plan["packets"][0]["range"] is None
    assert kit.numstat(root, plan["range"]).counts == {"app/a.py": 3}
    # Auch der normale Bereich lässt sich wieder einlesen.
    git(root, "commit", "--quiet", "--allow-empty", "-m", "leer")
    (root / "app" / "a.py").write_text(_lines(5), encoding="utf-8")
    git(root, "commit", "--quiet", "-am", "zwei")
    again = kit.build_plan(root, "HEAD~2..HEAD", "standard", "bugs", None, False)
    assert kit.numstat(root, again["range"]).counts == {"app/a.py": 2}


def test_g03_write_json_follows_umask(tmp_path):
    kit = _kit()
    for mask, mode in ((0o022, 0o644), (0o027, 0o640)):
        old = os.umask(mask)
        try:
            kit.write_json(tmp_path / f"{mask:o}.json", {"generated": "t"}, {"a": 1})
        finally:
            os.umask(old)
        assert (tmp_path / f"{mask:o}.json").stat().st_mode & 0o777 == mode, oct(mask)


def test_g04_git_failures_keep_their_cause(tmp_path, monkeypatch):
    kit = _kit()
    plain = tmp_path / "kein-repo"
    plain.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    with pytest.raises(kit.KitError) as info:
        kit.numstat(plain, None)
    assert "unbekannt" not in str(info.value) and "Git-Repo" in str(info.value)

    (tmp_path / "repo").mkdir()
    root = _commit_repo(tmp_path / "repo", {"app/a.py": ""}, {"app/a.py": _lines(2)})
    real = kit.subprocess.run

    def missing(cmd, **kwargs):
        if cmd[:2] == ["git", "rev-parse"] and any(a.endswith("^{commit}") for a in cmd):
            raise FileNotFoundError("git")
        return real(cmd, **kwargs)

    monkeypatch.setattr(kit.subprocess, "run", missing)
    with pytest.raises(kit.KitError) as info:
        kit.numstat(root, "HEAD")
    assert "unbekannt" not in str(info.value) and "nicht gestartet" in str(info.value)


def test_g05_numstat_counts_from_top_level_like_subagent_dev(tmp_path, monkeypatch):
    kit = _kit()
    root = _commit_repo(tmp_path, {"sub/a.py": "", "app/b.py": ""},
                        {"sub/a.py": _lines(2), "app/b.py": _lines(3)})
    assert kit.DIFF_PATHSPEC == (".", ":(exclude).skills")  # wie plan_to_tasks.changed_lines
    seen = []
    real = kit._git

    def spy(repo, *args):
        if args and args[0] == "diff":
            seen.append(repo)
        return real(repo, *args)

    monkeypatch.setattr(kit, "_git", spy)
    assert kit.numstat(root / "sub", None).counts == {"app/b.py": 3, "sub/a.py": 2}
    assert [p.resolve() for p in seen] == [root.resolve()]


def test_g06_plan_names_counted_base_target_and_log_base(tmp_path):
    kit = _kit()
    root = _commit_repo(tmp_path, {"app/f.py": ""}, {"app/f.py": _lines(1)})
    fork = _rev(root, "HEAD")
    git(root, "checkout", "--quiet", "-b", "feature")
    (root / "app" / "f.py").write_text(_lines(6), encoding="utf-8")
    git(root, "commit", "--quiet", "-am", "feature")
    git(root, "checkout", "--quiet", "main")
    (root / "app" / "f.py").write_text(_lines(9), encoding="utf-8")
    git(root, "commit", "--quiet", "-am", "main wächst")
    plan = kit.build_plan(root, "main..feature", "standard", "bugs", None, False)
    assert plan["base"] == fork
    assert plan["target"] == _rev(root, "feature")
    assert plan["log_base"] == _rev(root, "main")
    assert plan["range"] == f"{plan['base']}..{plan['target']}"


def test_g07_non_utf8_path_lands_in_not_reviewed(tmp_path):
    kit = _kit()
    name = os.fsdecode(b"assets/caf\xe9.png")
    files = {f"app/m{i}.py": _lines(2, f"m{i}") for i in range(50)}
    root = _commit_repo(tmp_path, {"app/m0.py": ""}, {**files, name: "x\n"})
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    _read_plan(root, plan)
    assert kit.REASON_NOT_UTF8 == "Pfad ist kein UTF-8"
    assert plan["not_reviewed"] == [{"file": "assets/caf\\xe9.png", "reason": kit.REASON_NOT_UTF8}]
    assert len(plan["packets"][0]["files"]) == 50 and plan["changed_lines"] == 100


def test_g08_write_json_rejects_nan_and_unwraps_subclasses(tmp_path):
    import enum

    kit = _kit()
    for bad in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(kit.KitError):
            kit.write_json(tmp_path / "x.json", {"generated": "t"}, {"v": bad})
    assert list(tmp_path.iterdir()) == []

    class Size(enum.IntEnum):
        BIG = 7

    class Name(str):
        def __str__(self):
            return "falsch"

    class Ratio(float):
        def __repr__(self):
            return "falsch"

    data = kit.write_json(tmp_path / "y.json", {"generated": "t"},
                          {Name("k"): Size.BIG, "n": Name("wert"), "r": Ratio(0.5), "b": True})
    assert [type(v) for v in (data["k"], data["n"], data["r"], data["b"])] == [int, str, float, bool]
    assert all(type(k) is str for k in data)
    assert json.loads((tmp_path / "y.json").read_text(encoding="utf-8")) == {
        "_meta": data["_meta"], "k": 7, "n": "wert", "r": 0.5, "b": True}


def test_g09_numstat_carries_its_span(tmp_path):
    kit = _kit()
    root = _commit_repo(tmp_path, {"app/a.py": ""}, {"app/a.py": _lines(4)})
    stat = kit.numstat(root, "base..HEAD")
    assert kit.Numstat._fields == ("counts", "span")
    assert stat.span == kit.split_range(root, "base..HEAD")
    assert kit.numstat(root, None).span == kit.split_range(root, "HEAD")


def test_g10_non_utc_now_is_refused(monkeypatch):
    kit = _kit()
    sha = "0123456789abcdef0123456789abcdef01234567"
    for when in (dt.datetime(2026, 11, 2, 14, 5, 9),
                 dt.datetime(2026, 11, 2, 14, 5, 9, tzinfo=dt.timezone(dt.timedelta(hours=1)))):
        monkeypatch.setattr(kit, "_now", lambda when=when: when)
        with pytest.raises(kit.KitError, match="UTC"):
            kit.new_run_id(sha)


# --- review_kit.py: Funde des dritten Prüfpunkts nach Task 2 (H1–H3) ----------------------

def test_h01_pas_test_rule_by_segments():
    kit = _kit()
    for name in ("MyApp.Tests.Utils", "DUnitX.Tests.Assert", "App.Test.Core", "Foo_Test_Helpers",
                 "MyTestsUnit", "FooTestsHelper", "FooTEST", "Test"):
        assert kit.classify(f"src/{name}.pas", False) == kit.REASON_TEST, name
        assert kit.classify(f"src/{name}.pas", True) is None, name
    for name in ("Testament", "TestimonialService", "Testing", "Tester", "LATEST", "CONTEST",
                 "Latest"):
        assert kit.classify(f"src/{name}.pas", False) is None, name


def test_h02_root_commit_plan_needs_helper_commits(tmp_path):
    kit = _kit()
    root = _root_repo(tmp_path, {"app/a.py": _lines(3)})
    head = _rev(root, "HEAD")
    plan = kit.build_plan(root, None, "standard", "bugs", None, False)
    on_disk, _ = _read_plan(root, plan)
    assert list(on_disk) == PLAN_KEYS
    assert plan["root"] is True and plan["range"] == head
    assert plan["packets"][0]["range"] is None
    assert kit.numstat(root, plan["range"]).counts == {"app/a.py": 3}
    sec = kit.build_plan(root, head, "standard", "security", None, False)
    assert sec["root"] is True and [p["range"] for p in sec["packets"]] == [None]
    assert "Hilfscommit" in kit.build_plan.__doc__

    (root / "app" / "a.py").write_text(_lines(5), encoding="utf-8")
    git(root, "commit", "--quiet", "-am", "zwei")
    normal = kit.build_plan(root, "HEAD", "standard", "bugs", None, False)
    assert normal["root"] is False
    assert normal["packets"][0]["range"] == normal["range"] == f"{head}..{_rev(root, 'HEAD')}"


def test_h03_non_utf8_source_file_has_its_own_reason(tmp_path):
    kit = _kit()
    source = os.fsdecode(b"app/caf\xe9.py")
    image = os.fsdecode(b"assets/caf\xe9.png")
    root = _commit_repo(tmp_path, {"app/m.py": ""},
                        {"app/m.py": _lines(2), source: "a = 1\n", image: "x\n"})
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    _read_plan(root, plan)
    assert kit.REASON_SOURCE_NOT_UTF8 == "Quelldatei mit Nicht-UTF-8-Pfad — nicht reviewt"
    assert plan["not_reviewed"] == [
        {"file": "app/caf\\xe9.py", "reason": kit.REASON_SOURCE_NOT_UTF8},
        {"file": "assets/caf\\xe9.png", "reason": kit.REASON_NOT_UTF8},
    ]
    assert plan["packets"][0]["files"] == ["app/m.py"]

    (tmp_path / "only").mkdir()
    only = _commit_repo(tmp_path / "only", {"app/m.py": ""}, {source: "a = 1\n"})
    with pytest.raises(kit.KitError, match=r"nichts zu reviewen.*app/caf\\xe9\.py"):
        kit.build_plan(only, "base..HEAD", "standard", "bugs", None, False)
    assert _runs(only) == []


def test_h04_pas_segments_split_capital_runs_and_digits():
    kit = _kit()
    for name in ("HTMLTest", "MyTest2", "XMLTests.Helper"):
        assert kit.classify(f"src/{name}.pas", False) == kit.REASON_TEST, name
    for name in ("HTMLTestament", "TESTUNIT", "Contest2"):
        assert kit.classify(f"src/{name}.pas", False) is None, name


# --- review_kit.py: Paket-Bereiche und cleanup (Task 3) ----------------------------------

IDENTITY = "deep-review <deep-review@localhost>"


def _no_identity(monkeypatch, root, home):
    """Kein user.name, keine Identität aus Umgebung, globaler oder System-Konfiguration;
    `user.useConfigOnly` verbietet git das Raten aus Rechnername und Login."""
    for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME",
                "GIT_COMMITTER_EMAIL", "EMAIL", "GIT_INDEX_FILE"):
        monkeypatch.delenv(key, raising=False)
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    git(root, "config", "--unset", "user.name")
    git(root, "config", "--unset", "user.email")
    git(root, "config", "user.useConfigOnly", "true")
    with pytest.raises(subprocess.CalledProcessError):
        git(root, "commit-tree", "-m", "x", f"{_rev(root, 'HEAD')}^{{tree}}")


def _user_state(root):
    """HEAD, Index-Hash und Status ohne `.skills/` — `status` ohne optionale Sperren, damit
    die Messung selbst den Index nicht auffrischt."""
    index = hashlib.sha256((root / ".git" / "index").read_bytes()).hexdigest()
    status = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), "status", "--porcelain",
         "--untracked-files=all"], capture_output=True, text=True, check=True).stdout
    status = "\n".join(line for line in status.splitlines() if ".skills/" not in line)
    head = git(root, "symbolic-ref", "-q", "HEAD") + _rev(root, "HEAD")
    return head, index, status


def _refs(root, prefix="refs/deep-review/"):
    return git(root, "for-each-ref", "--format=%(refname)", prefix).split()


def _name_status(root, rng):
    out = git(root, "diff", "--name-status", "--no-renames", rng)
    return sorted(tuple(line.split("\t")) for line in out.splitlines())


def _plan_on_disk(kit, root, run):
    return json.loads((kit.run_dir(root, run) / "plan.json").read_text(encoding="utf-8"))


def test_plan_packet_range_shows_only_the_packet(tmp_path, monkeypatch):
    kit = _kit()
    (tmp_path / "repo").mkdir()
    root = _commit_repo(
        tmp_path / "repo",
        {"a/mod.py": _lines(4), "b/gone.py": _lines(8, "g"), "README.md": "# x\n"},
        {"a/mod.py": _lines(2) + _lines(2, "neu"),   # M, 4 Zeilen
         "a/new.py": _lines(4, "n"),                 # A, 4 Zeilen
         "b/gone.py": None,                          # D, 8 Zeilen
         "README.md": "# x\n\nmehr\n"},              # nicht reviewt
    )
    # Zweiter Commit im Bereich: die Message von `bis` sind alle Messages von BASIS..ZIEL.
    (root / "a" / "new.py").write_text(_lines(5, "n"), encoding="utf-8")
    git(root, "commit", "--quiet", "-am", "zweite änderung\n\nmit Rumpf")
    _no_identity(monkeypatch, root, tmp_path / "home")

    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", 10, False)
    assert plan["split"] is True
    assert [(p["id"], p["files"], p["range"]) for p in plan["packets"]] == [
        ("p1", ["a/mod.py", "a/new.py"], None), ("p2", ["b/gone.py"], None)]
    run = plan["_meta"]["run"]

    # Ungespeicherte Änderung in einer Paketdatei und eine im Index.
    (root / "a" / "mod.py").write_text(_lines(1), encoding="utf-8")
    (root / "staged.py").write_text("s = 1\n", encoding="utf-8")
    git(root, "add", "staged.py")
    before = _user_state(root)

    ranges = {p["id"]: kit.make_packet_range(root, run, p, plan["base"], plan["target"])
              for p in plan["packets"]}
    assert _user_state(root) == before

    head = _rev(root, "HEAD")
    expected = {"p1": [("A", "a/new.py"), ("M", "a/mod.py")], "p2": [("D", "b/gone.py")]}
    message = git(root, "log", "--format=%B", f"{plan['log_base']}..{plan['target']}")
    assert "zweite änderung" in message and "\nänderung" in message
    for pid, rng in ranges.items():
        von, bis = rng.split("..")
        assert von == _rev(root, f"refs/deep-review/{run}/{pid}/von")
        assert bis == _rev(root, f"refs/deep-review/{run}/{pid}/bis")
        assert _name_status(root, rng) == expected[pid]
        assert _rev(root, f"{bis}^{{tree}}") == _rev(root, f"{head}^{{tree}}")
        assert _rev(root, f"{bis}^") == von and _rev(root, f"{von}^") == head
        assert git(root, "log", "-1", "--format=%an <%ae>|%cn <%ce>", bis).strip() == \
            f"{IDENTITY}|{IDENTITY}"
        assert git(root, "log", "-1", "--format=%B", von).strip() == f"deep-review {run} {pid}: Basis"
        assert git(root, "log", "-1", "--format=%B", bis).strip() == message.strip()

    on_disk = _plan_on_disk(kit, root, run)
    assert [p["range"] for p in on_disk["packets"]] == [ranges["p1"], ranges["p2"]]
    assert list(on_disk) == PLAN_KEYS + ["notes"]
    assert all(list(p) == PACKET_KEYS for p in on_disk["packets"])
    assert on_disk["_meta"]["run"] == run and on_disk["_meta"]["skill"] == "deep-review"
    # Der Arbeitsbaum weicht in a/mod.py von ZIEL ab: Hinweis für p1, keiner für p2.
    assert [(n["packet"], n["kind"], n["files"]) for n in on_disk["notes"]] == [
        ("p1", "worktree_differs", ["a/mod.py"])]
    assert all(n["text"] for n in on_disk["notes"])
    # Ein zweiter Aufruf baut nichts neu; eine Basis, die nicht zum Plan passt, ist ein Fehler.
    assert kit.make_packet_range(root, run, "p1", plan["base"], plan["target"]) == ranges["p1"]
    assert _plan_on_disk(kit, root, run)["notes"] == on_disk["notes"]
    with pytest.raises(kit.KitError, match="Plan"):
        kit.make_packet_range(root, run, "p1", head, head)

    # cleanup: keine Ref des Laufs bleibt; ein anderer Lauf bleibt, bis --stale ihn löscht.
    other = kit.build_plan(root, "base..HEAD", "standard", "bugs", 10, False)
    kit.make_packet_range(root, other["_meta"]["run"], "p2", other["base"], other["target"])
    third = kit.build_plan(root, "base..HEAD", "standard", "bugs", 10, False)
    kit.make_packet_range(root, third["_meta"]["run"], "p1", third["base"], third["target"])
    deleted = kit.cleanup(root, run, False)
    assert sorted(deleted) == sorted(f"refs/deep-review/{run}/{p}/{e}"
                                     for p in ("p1", "p2") for e in ("von", "bis"))
    assert _refs(root, f"refs/deep-review/{run}/") == []
    assert _refs(root, f"refs/deep-review/{other['_meta']['run']}/")
    kit.cleanup(root, third["_meta"]["run"], True)
    assert [r.split("/")[2] for r in _refs(root)] == [third["_meta"]["run"]] * 2
    kit.cleanup(root, None, True)
    assert _refs(root) == []
    assert kit.cleanup(root, run, False) == []
    with pytest.raises(kit.KitError):
        kit.cleanup(root, None, False)
    with pytest.raises(kit.KitError):
        kit.cleanup(root, "../x", False)
    assert _user_state(root) == before


def test_plan_packet_range_root_split_false_and_target_not_head(tmp_path):
    kit = _kit()
    # Bis split_at, kein Wurzel-Commit: der Originalbereich, keine Hilfscommits.
    (tmp_path / "repo").mkdir()
    root = _commit_repo(tmp_path / "repo", {"a/x.py": ""}, {"a/x.py": _lines(3)})
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    run = plan["_meta"]["run"]
    assert kit.make_packet_range(root, run, "p1", plan["base"], plan["target"]) == plan["range"]
    assert _refs(root) == []
    assert _plan_on_disk(kit, root, run)["notes"] == []
    with pytest.raises(kit.KitError, match="p9"):
        kit.make_packet_range(root, run, "p9", plan["base"], plan["target"])

    # ZIEL ist nicht HEAD: Hinweis im Plan.
    (root / "a" / "y.py").write_text(_lines(2), encoding="utf-8")
    git(root, "add", "a/y.py")
    tree = git(root, "write-tree").strip()
    git(root, "rm", "--quiet", "--cached", "a/y.py")
    (root / "a" / "y.py").unlink()
    side = git(root, "commit-tree", "-p", "HEAD", "-m", "seite", tree).strip()
    git(root, "update-ref", "refs/heads/side", side)
    off = kit.build_plan(root, "base..side", "standard", "bugs", None, False)
    assert off["packets"][0]["files"] == ["a/x.py", "a/y.py"]
    kit.make_packet_range(root, off["_meta"]["run"], "p1", off["base"], off["target"])
    notes = _plan_on_disk(kit, root, off["_meta"]["run"])["notes"]
    assert [(n["packet"], n["kind"], n["files"]) for n in notes] == [
        ("p1", "target_not_head", []), ("p1", "worktree_differs", ["a/y.py"])]

    # Wurzel-Commit: auch ein einzelnes Paket bekommt Hilfscommits mit leerer Basis.
    (tmp_path / "first").mkdir()
    first = _root_repo(tmp_path / "first", {"app/a.py": _lines(3), "README.md": "# r\n"})
    rplan = kit.build_plan(first, None, "standard", "bugs", None, False)
    assert rplan["root"] is True and rplan["packets"][0]["range"] is None
    rng = kit.make_packet_range(first, rplan["_meta"]["run"], rplan["packets"][0],
                                rplan["base"], rplan["target"])
    assert _name_status(first, rng) == [("A", "app/a.py")]
    assert git(first, "log", "-1", "--format=%B", rng.split("..")[1]).strip() == "erster"
    assert len(kit.cleanup(first, rplan["_meta"]["run"], False)) == 2
    assert _refs(first) == []


# --- review_kit.py: Funde des Prüfpunkts nach Task 3 (J1–J12) -----------------------------

def _split_plan(kit, root, rng="base..HEAD", split_at=10):
    plan = kit.build_plan(root, rng, "standard", "bugs", split_at, False)
    assert plan["split"] is True
    return plan, plan["_meta"]["run"]


def _spy_git(kit, monkeypatch):
    calls = []
    real = kit._git

    def spy(repo, *args, **kwargs):
        calls.append(args)
        return real(repo, *args, **kwargs)

    monkeypatch.setattr(kit, "_git", spy)
    return calls


def test_j01_file_and_directory_in_different_packets(tmp_path):
    kit = _kit()
    # Richtung 1: BASIS hat die Datei `pkg`, ZIEL löscht sie und legt `pkg/b.py` an.
    (tmp_path / "one").mkdir()
    one = _commit_repo(tmp_path / "one", {"pkg": _lines(8, "f")},
                       {"pkg": None, "pkg/b.py": _lines(8, "b")})
    # Richtung 2: BASIS hat `pkg/b.py`, ZIEL löscht sie und legt die Datei `pkg` an.
    two = tmp_path / "two"
    (two / "pkg").mkdir(parents=True)
    git(two, "init", "--quiet", "--initial-branch=main")
    git(two, "config", "user.email", "t@example.invalid")
    git(two, "config", "user.name", "Test")
    (two / "pkg" / "b.py").write_text(_lines(8, "b"), encoding="utf-8")
    git(two, "add", "-A")
    git(two, "commit", "--quiet", "-m", "basis")
    git(two, "tag", "base")
    git(two, "rm", "--quiet", "-r", "pkg")
    (two / "pkg").write_text(_lines(8, "f"), encoding="utf-8")
    git(two, "add", "-A")
    git(two, "commit", "--quiet", "-m", "änderung")

    for root, expected in ((one, {"p1": [("D", "pkg")], "p2": [("A", "pkg/b.py")]}),
                           (two, {"p1": [("A", "pkg")], "p2": [("D", "pkg/b.py")]})):
        plan, run = _split_plan(kit, root)
        assert [p["files"] for p in plan["packets"]] == [["pkg"], ["pkg/b.py"]]
        before = _user_state(root)
        for packet in plan["packets"]:
            rng = kit.make_packet_range(root, run, packet, plan["base"], plan["target"])
            assert _name_status(root, rng) == expected[packet["id"]], (root.name, packet["id"])
        assert _user_state(root) == before


def test_j02_two_packets_sequential_and_concurrent(tmp_path, monkeypatch):
    import threading
    import time
    import types

    kit = _kit()
    (tmp_path / "repo").mkdir()
    root = _commit_repo(tmp_path / "repo", {"a/x.py": "", "b/y.py": ""},
                        {"a/x.py": _lines(8), "b/y.py": _lines(8, "y")})
    plan, run = _split_plan(kit, root)
    assert [p["id"] for p in plan["packets"]] == ["p1", "p2"]

    # Gleichzeitig: p2 startet, während p1 seine Hilfscommits baut. Wartet p2 auf die
    # Sperre, meldet das sein erstes sleep; ohne Sperre läuft p2 ganz durch.
    waiting = threading.Event()

    def nap(seconds):
        waiting.set()
        time.sleep(min(seconds, 0.01))

    monkeypatch.setattr(kit, "time", types.SimpleNamespace(sleep=nap, monotonic=time.monotonic),
                        raising=False)
    real = kit._helper_commits
    errors, threads = [], []

    def second():
        try:
            kit.make_packet_range(root, run, "p2", plan["base"], plan["target"])
        except BaseException as exc:  # noqa: BLE001 — im Haupt-Thread prüfen
            errors.append(exc)

    def helper(*args, **kwargs):
        if not threads:
            thread = threading.Thread(target=second)
            threads.append(thread)
            thread.start()
            deadline = time.monotonic() + 20
            while thread.is_alive() and not waiting.is_set() and time.monotonic() < deadline:
                time.sleep(0.01)
        return real(*args, **kwargs)

    monkeypatch.setattr(kit, "_helper_commits", helper)
    first = kit.make_packet_range(root, run, "p1", plan["base"], plan["target"])
    threads[0].join(30)
    assert not threads[0].is_alive() and errors == []
    on_disk = _plan_on_disk(kit, root, run)
    ranges = [p["range"] for p in on_disk["packets"]]
    assert ranges[0] == first and ranges[1] is not None, ranges
    for pid, rng in zip(("p1", "p2"), ranges):
        assert rng == (f"{_rev(root, f'refs/deep-review/{run}/{pid}/von')}.."
                       f"{_rev(root, f'refs/deep-review/{run}/{pid}/bis')}")
    assert not (kit.run_dir(root, run) / "plan.lock").exists()

    # Nacheinander in einem frischen Lauf: beide Bereiche und beide Hinweise bleiben.
    monkeypatch.setattr(kit, "_helper_commits", real)
    (root / "a" / "x.py").write_text("anders\n", encoding="utf-8")
    (root / "b" / "y.py").write_text("anders\n", encoding="utf-8")
    plan, run = _split_plan(kit, root)
    got = [kit.make_packet_range(root, run, p, plan["base"], plan["target"]) for p in ("p1", "p2")]
    on_disk = _plan_on_disk(kit, root, run)
    assert [p["range"] for p in on_disk["packets"]] == got
    assert [(n["packet"], n["kind"]) for n in on_disk["notes"]] == [
        ("p1", "worktree_differs"), ("p2", "worktree_differs")]


def test_j03_range_after_cleanup_is_rebuilt(tmp_path):
    kit = _kit()
    (tmp_path / "repo").mkdir()
    root = _commit_repo(tmp_path / "repo", {"a/x.py": "", "b/y.py": ""},
                        {"a/x.py": _lines(8), "b/y.py": _lines(8, "y")})
    plan, run = _split_plan(kit, root)
    for pid in ("p1", "p2"):
        kit.make_packet_range(root, run, pid, plan["base"], plan["target"])
    other, other_run = _split_plan(kit, root)
    kit.make_packet_range(root, other_run, "p1", plan["base"], plan["target"])

    # cleanup setzt die Bereiche, deren Refs es löscht, im Plan zurück.
    assert len(kit.cleanup(root, run, False)) == 4
    assert [p["range"] for p in _plan_on_disk(kit, root, run)["packets"]] == [None, None]
    assert _plan_on_disk(kit, root, other_run)["packets"][0]["range"] is not None
    rng = kit.make_packet_range(root, run, "p1", plan["base"], plan["target"])
    von, bis = rng.split("..")
    assert von == _rev(root, f"refs/deep-review/{run}/p1/von")
    assert bis == _rev(root, f"refs/deep-review/{run}/p1/bis")

    # Fehlen die Refs, ohne dass der Plan es weiß (anderer Worktree, Hand), wird neu gebaut.
    git(root, "update-ref", "-d", f"refs/deep-review/{run}/p1/von")
    again = kit.make_packet_range(root, run, "p1", plan["base"], plan["target"])
    assert again.split("..")[0] == _rev(root, f"refs/deep-review/{run}/p1/von")
    assert _name_status(root, again) == [("M", "a/x.py")]

    # cleanup --stale räumt auch die Pläne der anderen Läufe auf.
    kit.cleanup(root, run, True)
    assert _plan_on_disk(kit, root, other_run)["packets"][0]["range"] is None
    assert _plan_on_disk(kit, root, run)["packets"][0]["range"] == again


def test_j04_worktree_check_runs_through_git_in_chunks(tmp_path, monkeypatch):
    kit = _kit()
    names = [f"a/{'langer_ordnername_' * 2}{i:02d}.py" for i in range(8)]
    (tmp_path / "repo").mkdir()
    root = _commit_repo(tmp_path / "repo", {n: "" for n in names} | {"a/gone.py": "g = 1\n"},
                        {n: _lines(1, f"v{i}") for i, n in enumerate(names)} | {"a/gone.py": None})
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    run = plan["_meta"]["run"]
    (root / names[1]).write_text("geändert\n", encoding="utf-8")
    (root / names[6]).unlink()
    os.utime(root / names[3], (1_000_000_000, 1_000_000_000))  # nur die Zeit: kein Unterschied
    (root / "a" / "gone.py").write_text("g = 2\n", encoding="utf-8")  # in ZIEL gelöscht, untracked
    before = _user_state(root)

    monkeypatch.setattr(kit, "ARG_CHUNK_CHARS", 120, raising=False)
    calls = _spy_git(kit, monkeypatch)
    kit.make_packet_range(root, run, "p1", plan["base"], plan["target"])
    assert _user_state(root) == before
    notes = _plan_on_disk(kit, root, run)["notes"]
    assert [(n["kind"], n["files"]) for n in notes] == [
        ("worktree_differs", sorted(["a/gone.py", names[1], names[6]]))]

    diffs = [c for c in calls if c and c[0] == "diff" and "--name-only" in c]
    assert len(diffs) > 1, calls
    assert not [c for c in calls if c and c[0] == "hash-object" and "--" in c]
    for call in diffs:
        specs = list(call[call.index("--") + 1:])
        assert specs and all(s.startswith(":(literal)") for s in specs)
        assert len(" ".join(specs)) <= 120 or len(specs) == 1


def test_j05_symlink_without_core_symlinks(tmp_path):
    kit = _kit()
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "--quiet", "--initial-branch=main")
    git(root, "config", "user.email", "t@example.invalid")
    git(root, "config", "user.name", "Test")
    (root / "a").mkdir()
    (root / "a" / "x.py").write_text(_lines(2), encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "basis")
    git(root, "tag", "base")
    os.symlink("x.py", root / "a" / "link.py")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "link")
    # Wie unter Windows ohne Symlinks: git legt den Link als Datei mit dem Ziel als Inhalt an.
    git(root, "config", "core.symlinks", "false")
    (root / "a" / "link.py").unlink()
    git(root, "checkout", "--", "a/link.py")
    assert not (root / "a" / "link.py").is_symlink()
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    run = plan["_meta"]["run"]
    kit.make_packet_range(root, run, "p1", plan["base"], plan["target"])
    assert _plan_on_disk(kit, root, run)["notes"] == []


def test_j06_base_object_keeps_the_cause(tmp_path, monkeypatch):
    kit = _kit()
    (tmp_path / "repo").mkdir()
    root = _commit_repo(tmp_path / "repo", {"a/x.py": ""}, {"a/x.py": _lines(2)})
    head = _rev(root, "HEAD")
    empty = git(root, "hash-object", "-t", "tree", "--stdin").strip()
    assert kit._base_object(root, head) == head
    assert kit._base_object(root, empty) == empty
    with pytest.raises(kit.KitError, match="unbekannt"):
        kit._base_object(root, "gibt-es-nicht")
    real = kit.subprocess.run

    def slow(cmd, **kwargs):
        if cmd[:2] == ["git", "rev-parse"] and any(a.endswith("^{commit}") for a in cmd):
            raise subprocess.TimeoutExpired(cmd, 1)
        return real(cmd, **kwargs)

    monkeypatch.setattr(kit.subprocess, "run", slow)
    with pytest.raises(kit.KitError, match="abgebrochen"):
        kit._base_object(root, head)


def test_j07_malformed_plan_is_a_kit_error(tmp_path):
    kit = _kit()
    (tmp_path / "repo").mkdir()
    root = _commit_repo(tmp_path / "repo", {"a/x.py": ""}, {"a/x.py": _lines(2)})
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    run = plan["_meta"]["run"]
    path = kit.run_dir(root, run) / "plan.json"
    good = json.loads(path.read_text(encoding="utf-8"))
    bad_packets = (["p1"], [{"id": ["p1"], "files": []}], [{"id": "p1", "files": "a/x.py"}],
                   [{"id": "p1", "files": ["a/x.py"], "range": 7}], {"p1": {}})
    for packets in bad_packets:
        path.write_text(json.dumps({**good, "packets": packets}), encoding="utf-8")
        with pytest.raises(kit.KitError, match="Plan"):
            kit.make_packet_range(root, run, "p1", plan["base"], plan["target"])
    for broken in ({"notes": [1]}, {"_meta": []}, {"target": 3}):
        path.write_text(json.dumps({**good, **broken}), encoding="utf-8")
        with pytest.raises(kit.KitError, match="Plan"):
            kit.make_packet_range(root, run, "p1", plan["base"], plan["target"])


def test_j08_tree_entries_list_only_the_packet_paths(tmp_path, monkeypatch):
    kit = _kit()
    (tmp_path / "repo").mkdir()
    root = _commit_repo(tmp_path / "repo",
                        {"a/[x].py": "", "a/x.py": _lines(3), "z/other.py": _lines(3)},
                        {"a/[x].py": _lines(8), "b/y.py": _lines(8, "y")})
    plan, run = _split_plan(kit, root)
    assert [p["files"] for p in plan["packets"]] == [["a/[x].py"], ["b/y.py"]]
    calls = _spy_git(kit, monkeypatch)
    rng = kit.make_packet_range(root, run, "p1", plan["base"], plan["target"])
    assert _name_status(root, rng) == [("M", "a/[x].py")]
    trees = [c for c in calls if c and c[0] == "ls-tree"]
    assert len(trees) == 2, trees
    for call in trees:
        assert "--" in call and list(call[call.index("--") + 1:]) == [":(literal)a/[x].py"]


def test_j09_message_once_per_run_head_per_call(tmp_path, monkeypatch):
    kit = _kit()
    (tmp_path / "repo").mkdir()
    root = _commit_repo(tmp_path / "repo", {"a/x.py": "", "b/y.py": "", "c/z.py": ""},
                        {"a/x.py": _lines(8), "b/y.py": _lines(8, "y"), "c/z.py": _lines(8, "z")})
    plan, run = _split_plan(kit, root)
    calls = _spy_git(kit, monkeypatch)
    for packet in plan["packets"]:
        kit.make_packet_range(root, run, packet, plan["base"], plan["target"])
    assert len(plan["packets"]) == 3
    assert len([c for c in calls if c and c[0] == "log"]) == 1
    # HEAD bei jedem Aufruf (K3): ein Checkout zwischen zwei Paketen fällt sonst nicht auf.
    assert len([c for c in calls if c and c[0] == "rev-parse" and "HEAD^{commit}" in c]) == 3


def test_j11_base_and_target_may_be_none_or_the_typed_basis(tmp_path):
    kit = _kit()
    (tmp_path / "repo").mkdir()
    root = _commit_repo(tmp_path / "repo", {"a/x.py": "", "b/y.py": ""},
                        {"a/x.py": _lines(8), "b/y.py": _lines(8, "y")})
    # BASIS ist weitergelaufen: Merge-Basis (`base`) und getippte BASIS (`side`) weichen ab.
    git(root, "checkout", "--quiet", "-b", "side", "base")
    (root / "c.py").write_text("c = 1\n", encoding="utf-8")
    git(root, "add", "c.py")
    git(root, "commit", "--quiet", "-m", "seite")
    git(root, "checkout", "--quiet", "main")
    plan, run = _split_plan(kit, root, "side..main")
    assert plan["base"] == _rev(root, "base") and plan["log_base"] == _rev(root, "side")
    first = kit.make_packet_range(root, run, "p1", None, None)
    assert kit.make_packet_range(root, run, "p1", "side", "main") == first
    assert kit.make_packet_range(root, run, "p1", "base", None) == first
    assert kit.make_packet_range(root, run, "p2", None, "main")
    with pytest.raises(kit.KitError, match="Plan"):
        kit.make_packet_range(root, run, "p1", "main", None)
    with pytest.raises(kit.KitError, match="Plan"):
        kit.make_packet_range(root, run, "p1", None, "side")


# --- review_kit.py: Funde des Prüfpunkts nach Task 3, zweite Runde (K1–K6) ---------------

def _dead_pid():
    """PID eines Prozesses, der schon beendet ist."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


def _two_packet_repo(tmp_path):
    (tmp_path / "repo").mkdir()
    return _commit_repo(tmp_path / "repo", {"a/x.py": "", "b/y.py": ""},
                        {"a/x.py": _lines(8), "b/y.py": _lines(8, "y")})


def test_k1_cleanup_does_not_wait_on_a_leftover_lock(tmp_path, monkeypatch):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    plan, run = _split_plan(kit, root)
    kit.make_packet_range(root, run, "p1", plan["base"], plan["target"])
    _, other = _split_plan(kit, root)
    # Lauf `run` brach in make_packet_range ab: seine Sperre bleibt liegen, ihr Besitzer
    # lebt (dieser Prozess). cleanup darf darauf nicht warten und liefert die Refs.
    lock = kit.run_dir(root, run) / "plan.lock"
    lock.write_text(f"{os.getpid()}\n", encoding="utf-8")
    monkeypatch.setattr(kit, "LOCK_WAIT", 0.3)
    deleted = kit.cleanup(root, other, True)
    assert deleted == sorted(f"refs/deep-review/{run}/p1/{e}" for e in ("von", "bis"))
    assert _refs(root) == [] and lock.exists()
    # Der Plan steht noch auf dem alten Bereich; make_packet_range baut neu, weil die Refs fehlen.
    lock.unlink()
    rng = kit.make_packet_range(root, run, "p1", None, None)
    assert rng.split("..")[0] == _rev(root, f"refs/deep-review/{run}/p1/von")


def test_k2_lock_of_a_dead_process_is_taken_over(tmp_path, monkeypatch):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    plan, run = _split_plan(kit, root)
    lock = kit.run_dir(root, run) / "plan.lock"
    monkeypatch.setattr(kit, "LOCK_WAIT", 0.3)
    lock.write_text(f"{_dead_pid()}\n", encoding="utf-8")
    assert kit.make_packet_range(root, run, "p1", None, None)
    assert not lock.exists()
    assert sorted(p.name for p in kit.run_dir(root, run).iterdir()) == ["plan.json"]
    # Lebt der Besitzer, wird gewartet — und die Meldung rät nicht zum Löschen.
    lock.write_text(f"{os.getpid()}\n", encoding="utf-8")
    with pytest.raises(kit.KitError, match="gesperrt") as caught:
        kit.make_packet_range(root, run, "p2", None, None)
    assert "lösch" not in str(caught.value) and str(os.getpid()) in str(caught.value)
    assert lock.read_text(encoding="utf-8") == f"{os.getpid()}\n"


def test_k3_head_is_read_on_every_call(tmp_path):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    plan, run = _split_plan(kit, root)
    kit.make_packet_range(root, run, "p1", None, None)
    assert _plan_on_disk(kit, root, run)["notes"] == []
    git(root, "commit", "--quiet", "--allow-empty", "-m", "weiter")   # HEAD läuft weiter
    kit.make_packet_range(root, run, "p2", None, None)
    notes = _plan_on_disk(kit, root, run)["notes"]
    assert [(n["packet"], n["kind"]) for n in notes] == [("p2", "target_not_head")]
    assert not hasattr(kit, "_RUN_CACHE")
    assert isinstance(kit._range_message.cache_info().maxsize, int)


def test_k4_index_copy_keeps_racy_entries_racy(tmp_path):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    git(root, "config", "core.trustctime", "false")
    plan, run = _split_plan(kit, root)
    # Gleich lange Änderung im selben Zeittakt wie der Index: nur der Inhalt verrät sie.
    # Datei und Index tragen eine alte Zeit, die Kopie entsteht Sekunden später.
    path = root / "a" / "x.py"
    then = (1_000_000_000, 1_000_000_000)
    os.utime(path, then)
    git(root, "update-index", "--refresh")
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("x", "q"), encoding="utf-8")
    os.utime(path, then)
    os.utime(root / ".git" / "index", then)
    kit.make_packet_range(root, run, "p1", None, None)
    notes = _plan_on_disk(kit, root, run)["notes"]
    assert [(n["kind"], n["files"]) for n in notes] == [("worktree_differs", ["a/x.py"])]


def test_k5_missing_index_is_one_unknown_note(tmp_path):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    plan, run = _split_plan(kit, root)
    (root / ".git" / "index").unlink()
    kit.make_packet_range(root, run, "p1", None, None)
    notes = _plan_on_disk(kit, root, run)["notes"]
    assert [(n["packet"], n["kind"], n["files"]) for n in notes] == [("p1", "worktree_unknown", [])]
    assert "Index fehlt" in notes[0]["text"]
    assert not (root / ".git" / "index").exists()


def test_k6_malformed_note_is_a_kit_error(tmp_path):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    plan, run = _split_plan(kit, root)
    path = kit.run_dir(root, run) / "plan.json"
    good = json.loads(path.read_text(encoding="utf-8"))
    note = {"packet": "p1", "kind": "worktree_differs", "files": ["a/x.py"], "text": "t"}
    for broken in ({"packet": ["p1"]}, {"kind": {}}, {"files": "a/x.py"}, {"files": [1]},
                   {"text": None}):
        path.write_text(json.dumps({**good, "notes": [{**note, **broken}]}), encoding="utf-8")
        with pytest.raises(kit.KitError, match="Plan"):
            kit.make_packet_range(root, run, "p1", None, None)
    path.write_text(json.dumps({**good, "notes": [note]}), encoding="utf-8")
    kit.make_packet_range(root, run, "p1", None, None)


# --- review_kit.py: Gegenstellen für Python (Task 4) ---------------------------------------

def _section(text):
    """Der Gegenstellen-Abschnitt eines Paketblocks — für ihn gilt die Kappung."""
    return text[text.index("## Gegenstellen"):]


def _collect_block(kit, root, rng="base..HEAD"):
    plan = kit.build_plan(root, rng, "standard", "bugs", None, False)
    packet = plan["packets"][0]
    found = kit.collect_python(root, plan["range"], packet["files"])
    return plan, found, kit.render_block(packet, found.entries, found.unresolved, None)


VENDOR_LIB = (
    "def _check(items):\n"
    "    if not isinstance(items, list):\n"
    "        raise TypeError(\"items muss eine Liste sein\")\n"
    "    return items\n"
    "\n"
    "\n"
    "def group(items, key):\n"
    "    \"\"\"Gruppiert Einträge nach einem Schlüssel.\n"
    "\n"
    "    Zweite Zeile.\"\"\"\n"
    "    _check(items)\n"
    "    if key is None:\n"
    "        raise ValueError(\"key fehlt\")\n"
    "    return {key(i): i for i in items}\n"
)
GROUPS = (
    "from vendor.lib import group\n"
    "\n"
    "\n"
    "def build(items):\n"
    "    try:\n"
    "        return group(items, key=len)\n"
    "    except (ValueError, TypeError, LookupError):\n"
    "        return {}\n"
)


def test_counterparts_python_except_and_raises(tmp_path):
    kit = _kit()
    before = {"vendor/__init__.py": "", "vendor/lib.py": VENDOR_LIB, "app/__init__.py": "",
              "app/groups.py": GROUPS,
              # gleichnamig, aber ohne Importbezug: nicht die Gegenstelle
              "tools/misc.py": "def group(x):\n    raise KeyError(x)\n",
              # Syntaxfehler am ZIEL, nicht im Paket: übersprungen und nur gezählt
              "tools/broken.py": "def kaputt(:\n"}
    after = {"app/groups.py": GROUPS.replace("(ValueError, TypeError, LookupError)",
                                             "(ValueError, LookupError)")}
    root = _commit_repo(tmp_path, before, after)
    plan, found, block = _collect_block(kit, root)

    assert found.unresolved == 0
    assert found.unparsed == []
    assert [(e["file"], e["line"], e["kind"]) for e in found.entries] == [
        ("app/groups.py", 7, "except")]
    assert found.entries[0]["lines"] == [
        "### app/groups.py:7 except (ValueError, LookupError)",
        "- Gegenstelle group [vendor/lib.py:7]: def group(items, key)",
        "  Doc: Gruppiert Einträge nach einem Schlüssel.",
        "  wirft: TypeError, ValueError",
        "    raise TypeError at vendor/lib.py:3",
        "    raise ValueError at vendor/lib.py:13",
    ]
    assert re.search(r"wirft:[^\n]*TypeError", block)
    assert "tools/misc.py" not in block and "Zweite Zeile" not in block

    # counterparts --run <lauf>: packets/<id>.md mit Kopfzeile, Bereich, Dateien und Block.
    run = plan["_meta"]["run"]
    written = kit.write_counterparts(root, run)
    md_path = kit.run_dir(root, run) / "packets" / "p1.md"
    assert [w["packet"] for w in written] == ["p1"]
    assert written[0]["path"] == f".skills/cache/deep-review/{run}/packets/p1.md"
    assert (written[0]["counterparts"], written[0]["shown"], written[0]["unresolved"]) == (1, 1, 0)
    md = md_path.read_text(encoding="utf-8")
    first = md.splitlines()[0]
    assert first.startswith("<!-- skill: deep-review | schema: 1 | ") and first.endswith(" -->")
    assert f"counterparts --run {run}" in first
    assert f"Bereich: `{plan['range']}`" in md
    assert "- `app/groups.py`" in md
    assert "\n".join(found.entries[0]["lines"]) in md
    assert re.search(r"wirft:[^\n]*TypeError", md) and "vendor/lib.py" in md
    assert "tools/broken.py" not in md
    assert "1 Python-Datei(en) außerhalb des Pakets am ZIEL nicht lesbar (Syntaxfehler" in md


PKG_MOD = (
    "class Klasse:\n"
    "    \"\"\"Lädt Einträge aus einer Datei.\"\"\"\n"
    "\n"
    "    def __init__(self, path, strict=True):\n"
    "        self.data = _load(path, strict=strict)\n"
    "\n"
    "\n"
    "def _load(path, strict):\n"
    "    return _parse(path, strict=strict)\n"
    "\n"
    "\n"
    "def _parse(path, strict):\n"
    "    if not strict:\n"
    "        return []\n"
    "    raise ValueError(path)\n"
)
OTHER_MOD = (
    "class Klasse:\n"
    "    def __init__(self, path, strict=True):\n"
    "        if strict:\n"
    "            raise KeyError(path)\n"
)
MAIN = (
    "import other.mod\n"
    "import pkg.mod\n"
    "\n"
    "\n"
    "def run(path):\n"
    "    first = other.mod.Klasse(path)\n"
    "    return pkg.mod.Klasse(path, strict=True), first\n"
)


def test_counterparts_python_flag_flow(tmp_path):
    kit = _kit()
    before = {"pkg/__init__.py": "", "pkg/mod.py": PKG_MOD, "other/__init__.py": "",
              "other/mod.py": OTHER_MOD, "app/main.py": MAIN}
    root = _commit_repo(tmp_path, before, {"app/main.py": MAIN.replace("strict=True", "strict=False")})
    _plan, found, block = _collect_block(kit, root)

    assert found.unresolved == 0 and found.unparsed == []
    assert [(e["file"], e["line"]) for e in found.entries] == [("app/main.py", 7)]
    assert found.entries[0]["lines"] == [
        "### app/main.py:7 ruft Klasse(...)",
        "- Gegenstelle Klasse [pkg/mod.py:1]: class Klasse: def __init__(self, path, strict=True)",
        "  Doc: Lädt Einträge aus einer Datei.",
        "  wirft: ValueError",
        "    raise ValueError at pkg/mod.py:15",
        "  geändert: strict=False; Weg:",
        "    pkg/mod.py:5: strict -> _load(strict=...) [pkg/mod.py:8]",
        "    pkg/mod.py:9: strict -> _parse(strict=...) [pkg/mod.py:12]",
        "    pkg/mod.py:13: if not strict: return []",
    ]
    # Der voll qualifizierte Pfad entscheidet: die gleichnamige, ebenfalls importierte
    # Klasse in other/mod.py ist nicht die Gegenstelle.
    assert "other/mod.py" not in block and "KeyError" not in block


STORE = "class Store:\n    def values(self):\n        raise RuntimeError(\"leer\")\n"


def test_counterparts_python_no_guessing(tmp_path):
    kit = _kit()
    before = {f"{d}/m.py": STORE for d in "abcd"}
    before.update({
        "app/report.py": "import json\n\n\ndef total(data):\n    return sum(data.values())\n",
        "app/known.py": "from a.m import Store\n\n\ndef first():\n    return Store().values()\n",
    })
    after = {"app/report.py": before["app/report.py"].replace("data.values())", "data.values()) + 1"),
             "app/known.py": before["app/known.py"].replace("Store().values()",
                                                            "list(Store().values())")}
    root = _commit_repo(tmp_path, before, after)
    _plan, found, block = _collect_block(kit, root)

    # `.values()` ohne Importbezug bei vier gleichnamigen Definitionen: nichts statt Raten,
    # aber gezählt. Mit Importbezug (`from a.m import Store`) löst derselbe Name auf.
    assert found.unresolved == 1
    assert [(e["file"], e["line"]) for e in found.entries] == [("app/known.py", 5)]
    assert found.entries[0]["lines"][:3] == [
        "### app/known.py:5 ruft values(...)",
        "- Gegenstelle Store.values [a/m.py:2]: def values(self)",
        "  wirft: RuntimeError",
    ]
    assert "app/report.py:" not in block
    assert not any(f"{d}/m.py" in block for d in "bcd")
    assert "1 nicht aufgelöst" in block


def test_counterparts_cap():
    kit = _kit()
    packet = {"id": "p2", "files": ["app/x.py", "web/y.ts"], "range": "aaa..bbb"}
    entries = [{"file": f"app/m{i:03}.py", "line": i + 1, "kind": "call",
                "lines": [f"### app/m{i:03}.py:{i + 1} ruft f(...)",
                          f"- Gegenstelle f [lib/f.py:{i + 1}]: def f(x)",
                          "  wirft: ValueError",
                          "    raise ValueError at lib/f.py:9 " + "x" * 40]}
               for i in range(400)]
    text = kit.render_block(packet, entries, 2, None)
    section = _section(text)
    assert sum(len("\n".join(e["lines"])) for e in entries) > kit.BLOCK_MAX_CHARS
    assert len(section) <= kit.BLOCK_MAX_CHARS
    shown = section.count("\n### ")
    assert 0 < shown < 400
    assert f"gekappt: {400 - shown} von 400 Stellen" in section
    # In Reihenfolge: die ersten Stellen stehen, die letzten fehlen.
    assert "app/m000.py:1 " in section and f"app/m{shown - 1:03}.py:" in section
    assert f"app/m{shown:03}.py:" not in section
    assert "Bereich: `aaa..bbb`" in text and "2 nicht aufgelöst" in section
    # Datei ohne Sammler: gesagt, nicht still.
    assert "- `web/y.ts` — Gegenstellen nicht gesammelt (Sprache)" in text

    small = _section(kit.render_block(packet, entries, 0, 2000))
    assert len(small) <= 2000 and "gekappt:" in small
    full = _section(kit.render_block(packet, entries, 0, 10 ** 6))
    assert "gekappt" not in full and full.count("\n### ") == 400
    with pytest.raises(kit.KitError):
        kit.render_block(packet, entries, 0, 10)


# --- Prüfpunkt nach Task 4: Funde L1–L11 -------------------------------------------------

LIB_STRICT = (
    "def f(x, strict=True):\n"
    "    if not strict:\n"
    "        return []\n"
    "    raise ValueError(x)\n"
    "\n"
    "\n"
    "def wrap(x, strict=True):\n"
    "    if strict:\n"
    "        raise TypeError(x)\n"
    "    return x\n"
)


def _entries_at(found, rel, line):
    return [e for e in found.entries if (e["file"], e["line"]) == (rel, line)]


def test_l01_two_calls_on_one_line_keep_their_changed_keyword(tmp_path):
    kit = _kit()
    caller = ("from lib import f, wrap\n\n\n"
              "def run(x):\n    return f(1) and f(2, strict=True)\n\n\n"
              "def nest(x):\n    return wrap(wrap(x, strict=True))\n\n\n"
              "def dup(x):\n    return f(5) + f(6)\n")
    after = caller.replace("strict=True", "strict=False").replace("f(5) + f(6)", "f(7) + f(8)")
    root = _commit_repo(tmp_path, {"lib.py": LIB_STRICT, "app/c.py": caller}, {"app/c.py": after})
    _plan, found, _block = _collect_block(kit, root)

    for line, flow in ((5, "lib.py:2: if not strict: return []"),
                       (9, "lib.py:8: if strict: raise TypeError(x)")):
        lines = [x for e in _entries_at(found, "app/c.py", line) for x in e["lines"]]
        assert "  geändert: strict=False; Weg:" in lines, (line, lines)
        assert f"    {flow}" in lines
    # Zwei Aufrufe mit derselben Gegenstelle und ohne geändertes Argument: ein Eintrag.
    assert len(_entries_at(found, "app/c.py", 13)) == 1
    assert all(set(e) == {"file", "line", "kind", "lines"} for e in found.entries)


def test_l02_upper_case_py_suffix_is_collected(tmp_path):
    kit = _kit()
    up = "from lib import f\n\n\ndef run():\n    return f(1)\n"
    root = _commit_repo(tmp_path, {"lib.py": LIB_STRICT, "app/Up.PY": up},
                        {"app/Up.PY": up.replace("f(1)", "f(2)")})
    plan, found, block = _collect_block(kit, root)
    assert plan["packets"][0]["files"] == ["app/Up.PY"]
    assert [(e["file"], e["line"], e["kind"]) for e in found.entries] == [("app/Up.PY", 5, "call")]
    assert "raise ValueError at lib.py:4" in block
    assert "nicht gesammelt" not in block


def test_l03_unreadable_packet_files_are_named(tmp_path):
    kit = _kit()
    root = _commit_repo(tmp_path, {"lib.py": LIB_STRICT, "app/x.py": "def ok():\n    return 1\n"},
                        {"app/x.py": "def ok(:\n    return 2\n"})
    os.symlink("../lib.py", root / "app" / "link.py")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "link")
    plan, found, _block = _collect_block(kit, root)
    assert plan["packets"][0]["files"] == ["app/link.py", "app/x.py"]
    assert found.unparsed == [("app/link.py", "Symlink"), ("app/x.py", "Syntaxfehler")]

    run = plan["_meta"]["run"]
    kit.write_counterparts(root, run)
    md = (kit.run_dir(root, run) / "packets" / "p1.md").read_text(encoding="utf-8")
    assert "- `app/x.py` — Datei am ZIEL nicht lesbar: Syntaxfehler" in md
    assert "- `app/link.py` — Datei am ZIEL nicht lesbar: Symlink" in md
    assert "2 Paketdatei(en) am ZIEL nicht lesbar" in md


def test_l04_repo_wide_unreadable_files_only_as_a_number(tmp_path):
    kit = _kit()
    before = {"lib.py": LIB_STRICT, "app/c.py": "from lib import f\n\n\ndef run():\n    return f(1)\n",
              "tools/broken.py": "def kaputt(:\n", "tools/also.py": "x = (\n"}
    root = _commit_repo(tmp_path, before,
                        {"app/c.py": before["app/c.py"].replace("f(1)", "f(2)")})
    plan, found, _block = _collect_block(kit, root)
    assert found.unparsed == []
    run = plan["_meta"]["run"]
    kit.write_counterparts(root, run)
    md = (kit.run_dir(root, run) / "packets" / "p1.md").read_text(encoding="utf-8")
    assert "tools/broken.py" not in md and "tools/also.py" not in md
    assert "2 Python-Datei(en) außerhalb des Pakets am ZIEL nicht lesbar" in md


def test_l05_flow_stopping_at_an_ambiguous_callee_is_counted(tmp_path):
    kit = _kit()
    load = "def _load(strict):\n    if strict:\n        raise KeyError()\n"
    before = {f"m{d}/x.py": load for d in "abcd"}
    before.update({
        "svc/core.py": "class Svc:\n    def run(self, strict=True):\n"
                       "        if strict:\n            pass\n"
                       "        return self._load(strict=strict)\n",
        "app/main.py": "from svc.core import Svc\n\n\ndef go():\n    return Svc().run(strict=True)\n",
    })
    root = _commit_repo(tmp_path, before, {"app/main.py": before["app/main.py"].replace(
        "strict=True", "strict=False")})
    _plan, found, _block = _collect_block(kit, root)
    assert [(e["file"], e["line"]) for e in found.entries] == [("app/main.py", 5)]
    assert "    svc/core.py:3: if strict: pass" in found.entries[0]["lines"]
    assert found.unresolved == 1


def test_l06_multi_line_keyword_value_changed_on_a_later_line(tmp_path):
    kit = _kit()
    lib = "def load(path, options=None):\n    if options:\n        return options\n    return path\n"
    caller = ("from lib import load\n\n\n"
              "def go(p):\n    return load(p, options=dict(\n        strict=True,\n    ))\n")
    root = _commit_repo(tmp_path, {"lib.py": lib, "app/c.py": caller},
                        {"app/c.py": caller.replace("strict=True", "strict=False")})
    _plan, found, _block = _collect_block(kit, root)
    assert [(e["file"], e["line"]) for e in found.entries] == [("app/c.py", 5)]
    assert found.entries[0]["lines"][-2:] == [
        "  geändert: options=dict(strict=False); Weg:",
        "    lib.py:2: if options: return options",
    ]


def _many_files_packet(n):
    return {"id": "p9", "range": "aaa..bbb",
            "files": [f"a/rather/long/directory/name/{i:05}/module_{i}.py" for i in range(n)]}


def test_l07_cap_holds_for_the_whole_block(tmp_path, monkeypatch):
    kit = _kit()
    entries = [{"file": "app/m.py", "line": i + 1, "kind": "call",
                "lines": [f"### app/m.py:{i + 1} ruft f(...)", "- Gegenstelle f [lib/f.py:1]: def f()",
                          "  wirft: ValueError", "    raise ValueError at lib/f.py:2"]}
               for i in range(600)]
    text = kit.render_block(_many_files_packet(3000), entries, 0, None)
    assert len(text) <= kit.BLOCK_MAX_CHARS
    assert "Dateien (3000):" in text
    listed = text.count("\n- `a/rather/")
    assert 0 < listed < 3000
    assert f"- … und {3000 - listed} weitere Datei(en) (gekappt)" in text
    shown = text.count("\n### ")
    assert 0 < shown < 600 and f"gekappt: {600 - shown} von 600 Stellen" in text
    # Wenige Stellen: die Dateiliste bekommt den Rest.
    few = kit.render_block(_many_files_packet(3000), entries[:2], 0, None)
    assert len(few) <= kit.BLOCK_MAX_CHARS and few.count("\n### ") == 2
    assert few.count("\n- `a/rather/") > listed

    # Das Artefakt packets/<id>.md mit Kopfzeile und Hinweisen bleibt unter der Grenze.
    before = {"lib.py": LIB_STRICT, "tools/broken.py": "def kaputt(:\n"}
    names = [f"pkg_with_a_rather_long_directory_name/module_number_{i:03}.py" for i in range(40)]
    before.update({n: "from lib import f\n\n\ndef run():\n    return f(1)\n" for n in names})
    root = _commit_repo(tmp_path, before, {n: before[n].replace("f(1)", "f(2)") for n in names})
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    monkeypatch.setattr(kit, "BLOCK_MAX_CHARS", 1500)
    kit.write_counterparts(root, plan["_meta"]["run"])
    md = (kit.run_dir(root, plan["_meta"]["run"]) / "packets" / "p1.md").read_text(encoding="utf-8")
    assert len(md) <= 1500
    assert "weitere Datei(en) (gekappt)" in md and "gekappt:" in md
    assert "1 Python-Datei(en) außerhalb des Pakets" in md


def test_l08_sources_come_as_bytes_from_git(tmp_path, monkeypatch):
    kit = _kit()
    latin = "# -*- coding: latin-1 -*-\nNAME = 'Müller'\n".encode("latin-1")
    root = _commit_repo(tmp_path, {"a.py": "x = 1\n"}, {"a.py": "x = 2\n"})
    (root / "b.py").write_bytes(latin)
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "latin")
    head = _rev(root, "HEAD")
    assert kit._git_bytes(root, "cat-file", "blob", f"{head}:b.py") == latin

    plain = kit._git

    def no_text_cat_file(repo, *args, **kwargs):
        assert args[0] != "cat-file", "cat-file --batch geht über _git_bytes"
        return plain(repo, *args, **kwargs)

    monkeypatch.setattr(kit, "_git", no_text_cat_file)
    sources, skipped = kit._python_sources(root, head)
    assert sources == {"a.py": b"x = 2\n", "b.py": latin} and skipped == {}


def test_l09_overlap_by_interval_against_sorted_lines():
    kit = _kit()
    lines = [2, 5, 9]
    assert [kit._touches(lines, a, b) for a, b in ((3, 4), (3, 5), (9, 20), (10, 20), (0, 1),
                                                    (2, 2), (6, 8), (1, 100))] == [
        False, True, True, False, False, True, False, True]
    assert kit._touches([], 1, 10) is False


def test_l10_flow_line_from_the_source_not_unparsed(tmp_path):
    kit = _kit()
    deep = "+".join(["1"] * 500)
    lib = ("def f(x, strict=True):\n    if not strict:\n"
           f"        y = {deep}\n        return y\n    raise ValueError(x)\n")
    caller = "from lib import f\n\n\ndef run():\n    return f(1, strict=True)\n"
    root = _commit_repo(tmp_path, {"lib.py": lib, "app/c.py": caller},
                        {"app/c.py": caller.replace("strict=True", "strict=False")})
    _plan, found, _block = _collect_block(kit, root)
    flow = [x for x in found.entries[0]["lines"] if x.startswith("    lib.py:2: ")]
    assert len(flow) == 1 and flow[0].startswith("    lib.py:2: if not strict: y = 1+1+1")
    assert len(flow[0]) <= 4 + len("lib.py:2: if not strict: ") + kit.DOC_CHARS + 1


def test_l11_raises_memoized_per_definition(tmp_path, monkeypatch):
    kit = _kit()
    assert kit.INDEX_CACHE_SIZE == 1 and kit._python_index.cache_info().maxsize == 1
    lib = "def helper(x):\n    raise ValueError(x)\n"
    calls = "".join(f"        a{i} = helper({i})\n" for i in range(60))
    caller = ("from lib import helper\n\n\ndef run():\n    try:\n" + calls
              + "    except KeyError:\n        return None\n")
    root = _commit_repo(tmp_path, {"lib.py": lib, "app/c.py": "x = 1\n"}, {"app/c.py": caller})
    real = kit._raises_in
    top = []

    def counting(index, rel, node, depth, seen):
        if depth == kit.RAISE_DEPTH:
            top.append((rel, node.lineno))
        return real(index, rel, node, depth, seen)

    monkeypatch.setattr(kit, "_raises_in", counting)
    _plan, found, _block = _collect_block(kit, root)
    assert len([e for e in found.entries if e["kind"] == "call"]) == 60
    assert [e["kind"] for e in found.entries].count("except") == 1
    assert top == [("lib.py", 1)]


# --- Prüfpunkt nach Task 4, zweite Runde: Funde M1–M7 ------------------------------------

def test_m1_segment_of_a_latin1_file_uses_the_decoded_line(tmp_path):
    kit = _kit()
    lib = ("# -*- coding: latin-1 -*-\n"
           "def f(x, strict=True):\n"
           "    if not strict or x == 'üü': foo()\n"
           "    raise ValueError(x)\n").encode("latin-1")
    caller = "from lib import f\n\n\ndef run():\n    return f(1, strict=True)\n"
    root = _commit_repo(tmp_path, {"lib.py": lib, "app/c.py": caller},
                        {"app/c.py": caller.replace("strict=True", "strict=False")})
    _plan, found, _block = _collect_block(kit, root)
    flow = [x for e in found.entries for x in e["lines"] if x.startswith("    lib.py:3: ")]
    assert flow == ["    lib.py:3: if not strict or x == 'üü': foo()"]


def test_m2_segment_after_a_bom_on_line_one():
    kit = _kit()
    index = kit._PyIndex({"a.py": b"\xef\xbb\xbfif x: foo(1)\n",
                          "b.py": b"\xef\xbb\xbf# coding: utf-8\nif x: foo(2)\n"})
    stmt = index.trees["a.py"].body[0]
    assert index.segment("a.py", stmt) == "if x: foo(1)"
    assert index.segment("a.py", stmt.body[0]) == "foo(1)"
    assert index.segment("b.py", index.trees["b.py"].body[0].body[0]) == "foo(2)"


QUALITY_INTRO = "## Gegenstellen\n\nGegenstellen nicht gesammelt (Fokus quality).\n"


def test_m3_render_block_reads_optional_packet_keys(tmp_path):
    kit = _kit()
    # Delphi ruft nur render_block: alles, was ein Block zeigen kann, steht im Paket-Dict.
    assert list(inspect.signature(kit._render).parameters) == [
        "packet", "entries", "unresolved", "cap"]
    for key in ("unreadable", "notes", "intro"):
        assert f"`{key}`" in kit.render_block.__doc__
    packet = {"id": "p1", "range": "a..b", "files": ["app/x.py", "app/y.py"],
              "unreadable": [("app/x.py", "Syntaxfehler")], "notes": ["Hinweis eins", "zwei"]}
    text = kit.render_block(packet, [], 0, None)
    assert "- `app/x.py` — Datei am ZIEL nicht lesbar: Syntaxfehler\n" in text
    assert "- `app/y.py`\n" in text
    assert "1 Paketdatei(en) am ZIEL nicht lesbar" in text
    assert text.endswith("\nHinweis eins\n\nzwei\n")
    # JSON-Form (Listen statt Tupel) gleich
    as_json = {**packet, "unreadable": [["app/x.py", "Syntaxfehler"]]}
    assert kit.render_block(as_json, [], 0, None) == text
    quality = kit.render_block({**packet, "intro": QUALITY_INTRO}, [], 0, None)
    assert "\n## Gegenstellen\n\nGegenstellen nicht gesammelt (Fokus quality).\n" in quality
    assert "nach der Sammelregel" not in quality
    # Hinweise zählen gegen cap und bleiben beim Kappen stehen.
    entries = [{"file": "app/x.py", "line": i, "kind": "call",
                "lines": [f"### app/x.py:{i} ruft f(...)", "- Gegenstelle f [l.py:1]: def f()"]}
               for i in range(1, 200)]
    capped = kit.render_block(packet, entries, 0, 1500)
    assert len(capped) <= 1500 and "gekappt:" in capped
    assert capped.endswith("\nHinweis eins\n\nzwei\n")
    for bad in ({"notes": "Hinweis"}, {"notes": [1]}, {"unreadable": [("a.py",)]},
                {"unreadable": "a.py"}, {"intro": ["x"]}):
        with pytest.raises(kit.KitError):
            kit.render_block({**packet, **bad}, [], 0, None)

    # write_counterparts schreibt genau render_block mit den Schlüsseln (Fokus quality).
    root = _commit_repo(tmp_path, {"a.py": "x = 1\n"}, {"a.py": "x = 2\n"})
    plan = kit.build_plan(root, "base..HEAD", "standard", "quality", None, False)
    run = plan["_meta"]["run"]
    kit.write_counterparts(root, run)
    md = (kit.run_dir(root, run) / "packets" / "p1.md").read_text(encoding="utf-8")
    header, body = md.split("\n", 1)
    rng = re.search(r"Bereich: `([^`]+)`", body).group(1)
    shown = {**plan["packets"][0], "range": rng, "intro": QUALITY_INTRO}
    assert body == kit.render_block(shown, [], 0, kit.BLOCK_MAX_CHARS - len(header) - 1)


def _link_commit(root, links, message="links"):
    for rel, dest in links.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        os.symlink(dest, root / rel)
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", message)


def _counterparts_md(kit, root, rng):
    plan = kit.build_plan(root, rng, "standard", "bugs", None, False)
    run = plan["_meta"]["run"]
    kit.write_counterparts(root, run)
    return (kit.run_dir(root, run) / "packets" / "p1.md").read_text(encoding="utf-8")


def test_m4_symlinks_to_indexed_files_are_not_counted(tmp_path):
    kit = _kit()
    caller = "from lib import f\n\n\ndef run():\n    return f(1)\n"
    before = {"lib.py": LIB_STRICT, "app/c.py": caller, "tools/broken.py": "def kaputt(:\n"}
    root = _commit_repo(tmp_path, before, {"lib.py": LIB_STRICT + "\n"})
    links = {f"compat/m{i}.py": "../lib.py" for i in range(30)}
    links["compat/chain.py"] = "m0.py"
    _link_commit(root, links)
    (root / "app" / "c.py").write_text(caller.replace("f(1)", "f(2)"), encoding="utf-8")
    git(root, "commit", "--quiet", "-am", "aufruf")
    md = _counterparts_md(kit, root, "HEAD~1..HEAD")
    assert ("\n1 Python-Datei(en) außerhalb des Pakets am ZIEL nicht lesbar (Syntaxfehler) — "
            "dort keine Gegenstellen gesucht.\n") in md
    assert "Symlink" not in md

    (tmp_path / "b").mkdir()
    other = _commit_repo(tmp_path / "b", {"lib.py": LIB_STRICT, "app/c.py": caller},
                         {"lib.py": LIB_STRICT + "\n"})
    _link_commit(other, {"compat/m.py": "../lib.py", "compat/lost.py": "../nirgends.py",
                         "compat/out.py": "../../draussen.py"})
    (other / "app" / "c.py").write_text(caller.replace("f(1)", "f(2)"), encoding="utf-8")
    git(other, "commit", "--quiet", "-am", "aufruf")
    md = _counterparts_md(kit, other, "HEAD~1..HEAD")
    assert "\n2 Python-Datei(en) außerhalb des Pakets am ZIEL nicht lesbar (Symlink) — " in md
    assert "Syntaxfehler" not in md


def test_m5_skipped_tree_entries_have_their_own_reason(tmp_path):
    kit = _kit()
    odd = os.fsdecode(b"app/\xff.py")
    root = _commit_repo(tmp_path, {"lib.py": LIB_STRICT, odd: "a = 1\n"}, {odd: "a = 2\n"})
    head = _rev(root, "HEAD")
    git(root, "update-index", "--add", "--cacheinfo", f"160000,{head},vendor/tool.py")
    git(root, "commit", "--quiet", "-m", "submodul")
    found = kit.collect_python(root, "base..HEAD", [odd, "vendor/tool.py"])
    assert found.unparsed == [(odd, kit.SKIP_NOT_UTF8), ("vendor/tool.py", kit.SKIP_GITLINK)]
    assert kit.SKIP_NOT_UTF8 != kit.NOT_IN_TARGET != kit.SKIP_GITLINK
    # Ein Submodul ist keine Python-Datei: nicht in der Zahl am Ende eines anderen Pakets.
    index = kit._PyIndex(*kit._python_sources(root, _rev(root, "HEAD")))
    assert index.not_indexed() == {odd: kit.SKIP_NOT_UTF8}


def test_m6_packet_files_as_paths_are_counted_like_strings():
    kit = _kit()
    packet = {"id": "p1", "range": "a..b", "files": [PurePosixPath("app/x.py"), "app/y.py"],
              "unreadable": [(PurePosixPath("app/y.py"), "Symlink"), ("app/x.py", "Syntaxfehler")]}
    text = kit.render_block(packet, [], 0, None)
    assert "- `app/x.py` — Datei am ZIEL nicht lesbar: Syntaxfehler\n" in text
    assert "- `app/y.py` — Datei am ZIEL nicht lesbar: Symlink\n" in text
    assert "2 Paketdatei(en) am ZIEL nicht lesbar" in text


def test_m7_two_calls_of_one_name_on_a_line_get_columns(tmp_path):
    kit = _kit()
    caller = ("from lib import f, wrap\n\n\n"
              "def run(x):\n    return f(1, strict=True) and f(2, strict=True)\n\n\n"
              "def dup(x):\n    return f(5) + f(6)\n\n\n"
              "def nest(x):\n    return wrap(wrap(x, strict=True))\n\n\n"
              "def uml(x):\n    return 'ä' + f(3, strict=True)\n")
    after = (caller.replace("f(1, strict=True)", "f(1, strict=False)")
             .replace("f(2, strict=True)", "f(2, strict=None)")
             .replace("f(5) + f(6)", "f(7) + f(8)").replace("x, strict=True", "x, strict=False")
             .replace("f(3, strict=True)", "f(3, strict=False)"))
    root = _commit_repo(tmp_path, {"lib.py": LIB_STRICT, "app/c.py": caller}, {"app/c.py": after})
    _plan, found, block = _collect_block(kit, root)
    heads = [e["lines"][0] for e in found.entries]
    assert len(heads) == len(set(heads)), heads
    line5 = after.splitlines()[4]
    cols = [line5.index("f(1"), line5.index("f(2")]
    at5 = _entries_at(found, "app/c.py", 5)
    assert [e["lines"][0] for e in at5] == [f"### app/c.py:5:{c + 1} ruft f(...)" for c in cols]
    assert "  geändert: strict=False; Weg:" in at5[0]["lines"]
    assert "  geändert: strict=None; Weg:" in at5[1]["lines"]
    # Gleiche Einträge fallen weiter zusammen; ein Eintrag je Name und Zeile ohne Spalte.
    assert [e["lines"][0] for e in _entries_at(found, "app/c.py", 9)] == [
        "### app/c.py:9 ruft f(...)"]
    line13 = after.splitlines()[12]
    assert sorted(e["lines"][0] for e in _entries_at(found, "app/c.py", 13)) == sorted(
        f"### app/c.py:13:{line13.index(s) + 1} ruft wrap(...)" for s in ("wrap(w", "wrap(x"))
    assert [e["lines"][0] for e in _entries_at(found, "app/c.py", 17)] == [
        "### app/c.py:17 ruft f(...)"]
    assert all(set(e) == {"file", "line", "kind", "lines"} for e in found.entries)
    assert block.count("### app/c.py:5:") == 2


# --- review_kit.py: Gegenstellen für Delphi (Task 5) ---------------------------------------

def _line_no(text, needle):
    """1-basierte Zeile des ersten Vorkommens von `needle` in `text`."""
    return text[:text.index(needle)].count("\n") + 1


TREE_PAS = (
    "unit Tree;\n"
    "\n"
    "interface\n"
    "\n"
    "uses\n"
    "  System.Generics.Collections, System.SysUtils;\n"
    "\n"
    "type\n"
    "  EParse = class(Exception);\n"
    "\n"
    "  TNode = class\n"
    "  public\n"
    "    Name: string;\n"
    "  end;\n"
    "\n"
    "  { Der Baum besitzt seine Knoten.\n"
    "    end }\n"
    "  TQueryTree = class(TObjectList<TNode>)\n"
    "  private\n"
    "    FDepth: Integer; // end\n"
    "  public\n"
    "    constructor Create;\n"
    "    function Find(const AName: string): TNode;\n"
    "  end;\n"
    "\n"
    "procedure Parse(const S: string; AMax: Integer = 0);\n"
    "\n"
    "implementation\n"
    "\n"
    "const\n"
    "  CEnd = 'end; end';\n"
    "\n"
    "constructor TQueryTree.Create;\n"
    "begin\n"
    "  inherited Create(True);\n"
    "  FDepth := 0;\n"
    "end;\n"
    "\n"
    "function TQueryTree.Find(const AName: string): TNode;\n"
    "begin\n"
    "  Result := nil;\n"
    "  for var N in Self do\n"
    "    if N.Name = AName then\n"
    "      Exit(N);\n"
    "end;\n"
    "\n"
    "procedure Parse(const S: string; AMax: Integer);\n"
    "begin\n"
    "  if S = '' then\n"
    "    Writeln('end'); (* end *)\n"
    "  { end } // end\n"
    "  if Length(S) > AMax then\n"
    "    raise EParse.Create('zu lang: end');\n"
    "end;\n"
    "\n"
    "end.\n"
)
QUERY_PAS = (
    "unit Query;\n"
    "\n"
    "interface\n"
    "\n"
    "uses\n"
    "  Tree;\n"
    "\n"
    "procedure Run(ATree: TQueryTree; N: TNode; const S: string);\n"
    "\n"
    "implementation\n"
    "\n"
    "procedure Run(ATree: TQueryTree; N: TNode; const S: string);\n"
    "begin\n"
    "  Writeln('begin end'); { end }\n"
    "  // end\n"
    "  ATree.Remove(N);\n"
    "end;\n"
    "\n"
    "end.\n"
)
QUERY_PAS_AFTER = QUERY_PAS.replace("  ATree.Remove(N);\n", "  ATree.Extract(N);\n  Parse(S);\n")


def test_counterparts_delphi(tmp_path):
    kit = _kit()
    before = {"Tree.pas": TREE_PAS, "Query.pas": QUERY_PAS, "vendor/__init__.py": "",
              "vendor/lib.py": VENDOR_LIB, "app/__init__.py": "", "app/groups.py": GROUPS}
    after = {"Query.pas": QUERY_PAS_AFTER,
             "app/groups.py": GROUPS.replace("(ValueError, TypeError, LookupError)",
                                             "(ValueError, LookupError)")}
    root = _commit_repo(tmp_path, before, after)
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    packet = plan["packets"][0]
    assert "Query.pas" in packet["files"]
    found = kit.collect_delphi(root, plan["range"], packet["files"])
    assert (found.unresolved, found.unparsed) == (0, [])

    extract = _line_no(QUERY_PAS_AFTER, "ATree.Extract")
    parse = _line_no(QUERY_PAS_AFTER, "Parse(S)")
    assert [(e["file"], e["line"], e["kind"]) for e in found.entries] == [
        ("Query.pas", extract, "owner"), ("Query.pas", parse, "call")]
    owner, call = found.entries
    assert owner["lines"][:3] == [
        f"### Query.pas:{extract} Extract auf ATree: TQueryTree",
        f"- Gegenstelle TQueryTree [Tree.pas:{_line_no(TREE_PAS, 'TQueryTree = class')}]: "
        "TQueryTree = class(TObjectList<TNode>)",
        f"  inherited Create(True) at Tree.pas:{_line_no(TREE_PAS, 'inherited Create')}",
    ]
    assert len(owner["lines"]) == 4
    assert owner["lines"][3].startswith("  Besitz (RTL): TObjectList<…>")
    assert "OwnsObjects standardmäßig wahr" in owner["lines"][3]
    # Kopf aus dem interface-Teil mit Default; raise hinter `end` in String und Kommentaren.
    impl = _line_no(TREE_PAS, "procedure Parse(const S: string; AMax: Integer);")
    assert call["lines"] == [
        f"### Query.pas:{parse} ruft Parse(...)",
        f"- Gegenstelle Parse [Tree.pas:{impl}]: "
        "procedure Parse(const S: string; AMax: Integer = 0)",
        f"  deklariert: Tree.pas:{_line_no(TREE_PAS, 'AMax: Integer = 0')}",
        "  wirft: EParse",
        f"    raise EParse at Tree.pas:{_line_no(TREE_PAS, 'raise EParse')}",
    ]
    block = kit.render_block(packet, found.entries, found.unresolved, None)
    for needle in ("TQueryTree = class(TObjectList<TNode>)", "inherited Create(True)",
                   "TObjectList", "AMax: Integer = 0", "raise EParse"):
        assert needle in block, needle
    assert "- `Query.pas` — " not in block

    # counterparts --run: Delphi und Python im selben Paketblock, nach Datei und Zeile.
    run = plan["_meta"]["run"]
    written = kit.write_counterparts(root, run)
    assert (written[0]["counterparts"], written[0]["shown"], written[0]["unresolved"]) == (3, 3, 0)
    md = (kit.run_dir(root, run) / "packets" / "p1.md").read_text(encoding="utf-8")
    assert "- `Query.pas`\n" in md
    assert md.index("\n".join(owner["lines"])) < md.index("\n".join(call["lines"])) < md.index(
        "### app/groups.py:7 except")


def test_mask_pascal_keeps_lines_and_columns():
    kit = _kit()
    text = ("s := 'it''s end'; t := '';  { end\n"
            "  end } x := 1; (* end\n"
            "*) y := '//'; // end\n"
            "z := '{'; w := #13'(*';\n"
            "m := '''\n"
            "  end\n"
            "  ''';\n"
            "u := 'offen\n"
            "end;\n")
    masked = kit.mask_pascal(text)
    assert len(masked) == len(text)
    assert [i for i, c in enumerate(masked) if c == "\n"] == [
        i for i, c in enumerate(text) if c == "\n"]
    assert re.findall(r"\w+", masked) == ["s", "t", "x", "1", "y", "z", "w", "13", "m", "u",
                                         "end"]
    assert masked.splitlines()[1].index("x := 1;") == text.splitlines()[1].index("x := 1;")


MANY_PAS = (
    "unit Many;\n\ninterface\n\ntype\n"
    + "".join(f"  T{c} = class\n    procedure Go(A: Integer = 0);\n  end;\n" for c in "ABCD")
    + "\nfunction Thing: TObject;\n\nimplementation\n\n"
    + "".join(f"procedure T{c}.Go(A: Integer);\nbegin\nend;\n\n" for c in "ABCD")
    + "function Thing: TObject;\nbegin\n  Result := nil;\nend;\n\nend.\n"
)
OWNER_PAS = (
    "unit Owner;\n"
    "\n"
    "interface\n"
    "\n"
    "uses\n"
    "  tree, System.Generics.Collections, Many;\n"
    "\n"
    "type\n"
    "  TBag = class(TObjectDictionary<string, TNode>)\n"
    "  public\n"
    "    constructor Create;\n"
    "  end;\n"
    "\n"
    "  TRunner = class\n"
    "  private\n"
    "    FTree: TQUERYTREE;\n"
    "    FBag: TBag;\n"
    "  public\n"
    "    procedure Done;\n"
    "  end;\n"
    "\n"
    "implementation\n"
    "\n"
    "constructor TBag.Create;\n"
    "begin\n"
    "  inherited Create([doOwnsValues]);\n"
    "end;\n"
    "\n"
    "procedure TRunner.Done;\n"
    "var\n"
    "  L: TObjectList<TNode>;\n"
    "  T: tquerytree;\n"
    "begin\n"
    "  L := nil;\n"
    "  T := nil;\n"
    "end;\n"
    "\n"
    "end.\n"
)
OWNER_PAS_AFTER = OWNER_PAS.replace(
    "  T := nil;\n",
    "  T := nil;\n  t.FREE;\n  L.Free;\n  FreeAndNil(FTree);\n  Self.FBag.Remove('x');\n"
    "  (Thing as TA).Go(1);\n")


def test_counterparts_delphi_receiver_from_var_and_field(tmp_path):
    kit = _kit()
    root = _commit_repo(tmp_path, {"Tree.pas": TREE_PAS, "Many.pas": MANY_PAS,
                                   "src/Owner.pas": OWNER_PAS},
                        {"src/Owner.pas": OWNER_PAS_AFTER})
    found = kit.collect_delphi(root, "base..HEAD", ["src/Owner.pas"])
    heads = {e["lines"][0]: e["lines"][1:] for e in found.entries}
    at = {needle: _line_no(OWNER_PAS_AFTER, needle)
          for needle in ("t.FREE", "L.Free", "FreeAndNil", "Self.FBag")}
    tree_head = (f"- Gegenstelle TQueryTree [Tree.pas:{_line_no(TREE_PAS, 'TQueryTree = class')}]: "
                 "TQueryTree = class(TObjectList<TNode>)")
    # var-Abschnitt, ohne Rücksicht auf Groß/Klein (uses tree, tquerytree, FREE)
    assert heads[f"### src/Owner.pas:{at['t.FREE']} FREE auf t: tquerytree"][0] == tree_head
    # Typ aus der RTL ohne Deklaration im Repo: nur der Besitz-Default
    rtl = heads[f"### src/Owner.pas:{at['L.Free']} Free auf L: TObjectList<TNode>"]
    assert len(rtl) == 1 and rtl[0].startswith("  Besitz (RTL): TObjectList<…>")
    # Klassenfeld
    assert heads[f"### src/Owner.pas:{at['FreeAndNil']} FreeAndNil auf FTree: TQUERYTREE"][0] \
        == tree_head
    # Self.Feld → TObjectDictionary-Ableitung mit ihrem inherited Create
    bag = heads[f"### src/Owner.pas:{at['Self.FBag']} Remove auf Self.FBag: TBag"]
    assert bag[:2] == [
        f"- Gegenstelle TBag [src/Owner.pas:{_line_no(OWNER_PAS, 'TBag = class')}]: "
        "TBag = class(TObjectDictionary<string, TNode>)",
        f"  inherited Create([doOwnsValues]) at src/Owner.pas:{_line_no(OWNER_PAS, 'inherited')}"]
    assert bag[2].startswith("  Besitz (RTL): TObjectDictionary<…>")
    # Go auf unbekanntem Empfänger: vier gleichnamige Methoden in den uses-Units, nicht geraten
    assert found.unresolved == 1
    assert len(found.entries) == 4


# --- review_kit.py: Funde des Prüfpunkts nach Task 5 (Delphi) -------------------------------

def _delphi_found(kit, tmp_path, before, after, files=None):
    """Repo aus `before`/`after` (wie `_commit_repo`), gesammelt über base..HEAD."""
    root = _commit_repo(tmp_path, before, after)
    return kit.collect_delphi(root, "base..HEAD", sorted(after) if files is None else files)


def _by_head(found):
    return {e["lines"][0]: e["lines"][1:] for e in found.entries}


def _tree_head():
    return (f"- Gegenstelle TQueryTree [Tree.pas:{_line_no(TREE_PAS, 'TQueryTree = class')}]: "
            "TQueryTree = class(TObjectList<TNode>)")


ESC_PAS = (
    "unit Esc;\n\ninterface\n\nuses\n  Tree;\n\ntype\n"
    "  TPair = record\n    &Begin, &End: TQueryTree;\n  end;\n\n"
    "  TC = class\n  public\n    procedure Run(var P: TPair);\n"
    "    procedure Check(A: Integer = 0);\n  end;\n\n"
    "implementation\n\n"
    "procedure TC.Run(var P: TPair);\nbegin\n  P.&End := nil;\nend;\n\n"
    "procedure TC.Check(A: Integer);\nbegin\n  raise EParse.Create('c');\nend;\n\nend.\n")
ESC_AFTER = ESC_PAS.replace("  P.&End := nil;\n", "  P.&End := nil;\n  P.&End.Free;\n  Check(1);\n")


def test_n01_escaped_keywords_stay_identifiers(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Tree.pas": TREE_PAS, "Esc.pas": ESC_PAS},
                          {"Esc.pas": ESC_AFTER})
    free, check = _line_no(ESC_AFTER, "P.&End.Free"), _line_no(ESC_AFTER, "Check(1)")
    heads = _by_head(found)
    assert heads[f"### Esc.pas:{free} Free auf P.&End: TQueryTree"][0] == _tree_head()
    assert "  wirft: EParse" in heads[f"### Esc.pas:{check} ruft Check(...)"]
    assert len(found.entries) == 2


BOX_PAS = (
    "unit Box;\n\ninterface\n\nuses\n  Tree;\n\ntype\n"
    "  TBox<T: record> = class\n  public\n    procedure Check(A: Integer = 0);\n  end;\n\n"
    "procedure Run(B: TBox<Integer>);\n\nimplementation\n\n"
    "procedure TBox<T>.Check(A: Integer);\nbegin\n  raise EParse.Create('b');\nend;\n\n"
    "procedure Run(B: TBox<Integer>);\nbegin\n  B := nil;\nend;\n\nend.\n")
BOX_AFTER = BOX_PAS.replace("  B := nil;\n", "  B := nil;\n  B.Check(1);\n")


def test_n02_record_constraint_opens_no_block(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Tree.pas": TREE_PAS, "Box.pas": BOX_PAS},
                          {"Box.pas": BOX_AFTER})
    call = _by_head(found)[f"### Box.pas:{_line_no(BOX_AFTER, 'B.Check(1)')} ruft Check(...)"]
    assert call[:3] == [
        f"- Gegenstelle TBox.Check [Box.pas:{_line_no(BOX_PAS, 'procedure TBox<T>.Check')}]: "
        "procedure Check(A: Integer = 0)",
        f"  deklariert: Box.pas:{_line_no(BOX_PAS, 'procedure Check(A: Integer = 0)')}",
        "  wirft: EParse"]


def test_n02_generic_method_head_is_no_call(tmp_path):
    kit = _kit()
    after = BOX_PAS.replace("raise EParse.Create('b');", "raise EParse.Create('c');").replace(
        "procedure TBox<T>.Check(A: Integer);", "procedure TBox<T>.Check(A: Integer); ")
    found = _delphi_found(kit, tmp_path, {"Tree.pas": TREE_PAS, "Box.pas": BOX_PAS},
                          {"Box.pas": after})
    assert found == kit.Collected([], 0, [])


CALLS_PAS = (
    "unit Calls;\n\ninterface\n\nuses\n  Tree;\n\ntype\n"
    "  TC = class\n  public\n    procedure Check;\n    class procedure Make;\n    procedure Run;\n"
    "  end;\n\n"
    "procedure Validate;\nfunction Pick<T>(A: T): T;\nprocedure Wrap(A: Integer);\n\n"
    "implementation\n\n"
    "procedure Validate;\nbegin\n  raise EParse.Create('v');\nend;\n\n"
    "function Pick<T>(A: T): T;\nbegin\n  raise EParse.Create('p');\nend;\n\n"
    "procedure Wrap(A: Integer);\nbegin\n  Pick<Integer>(A);\nend;\n\n"
    "procedure TC.Check;\nbegin\n  raise EParse.Create('c');\nend;\n\n"
    "class procedure TC.Make;\nbegin\n  raise EParse.Create('m');\nend;\n\n"
    "procedure TC.Run;\nvar\n  C: TC;\nbegin\n  C := nil;\nend;\n\nend.\n")
CALLS_AFTER = CALLS_PAS.replace(
    "  C := nil;\nend;",
    "  C := nil;\n  Validate;\n  C.Check;\n  TC.Make;\n  Check;\n  Pick<Integer>(1);\n  Wrap(2);\n"
    "  if C = nil then\n    C := nil;\nend;")


def test_n03_calls_without_parentheses_and_generic_calls(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Tree.pas": TREE_PAS, "Calls.pas": CALLS_PAS},
                          {"Calls.pas": CALLS_AFTER})
    first = _line_no(CALLS_AFTER, "  Validate;\n  C.Check")
    assert [e["lines"][0] for e in found.entries] == [
        f"### Calls.pas:{first + i} ruft {name}(...)"
        for i, name in enumerate(("Validate", "Check", "Make", "Check", "Pick", "Wrap"))]
    assert all("  wirft: EParse" in e["lines"] for e in found.entries)
    # Wrap wirft über den generischen Aufruf Pick<Integer>(A) — dieselbe Regel wie am Aufrufer.
    assert (f"    raise EParse at Calls.pas:{_line_no(CALLS_PAS, 'Create(' + chr(39) + 'p')}"
            in found.entries[-1]["lines"])
    assert found.unresolved == 0


HELPERS_PAS = (
    "unit Helpers;\n\ninterface\n\nuses\n  Tree;\n\nprocedure Helper(A: Integer);\n\n"
    "implementation\n\nprocedure Helper(A: Integer);\nbegin\n  raise EParse.Create('h');\nend;\n\n"
    "end.\n")
NESTED_PAS = (
    "unit Nested;\n\ninterface\n\nuses\n  Tree, Helpers;\n\ntype\n"
    "  ENested = class(EParse);\n\n"
    "  TC = class\n  public\n    procedure Run;\n  end;\n\n"
    "procedure Other;\nprocedure Wrap(A: Integer);\n\nimplementation\n\n"
    "procedure Other;\n\n  procedure Helper(A: Integer);\n  begin\n"
    "    raise ENested.Create('n');\n  end;\n\nbegin\n  Helper(0);\nend;\n\n"
    "procedure Wrap(A: Integer);\nbegin\n  Helper(A);\nend;\n\n"
    "procedure TC.Run;\nbegin\n  Wrap(0);\nend;\n\nend.\n")
NESTED_AFTER = NESTED_PAS.replace("  Wrap(0);\n", "  Wrap(0);\n  Helper(1);\n  Wrap(2);\n")


def test_n04_nested_routines_visible_only_inside_their_routine(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Tree.pas": TREE_PAS, "Helpers.pas": HELPERS_PAS,
                                          "Nested.pas": NESTED_PAS}, {"Nested.pas": NESTED_AFTER})
    impl = _line_no(HELPERS_PAS, "procedure Helper(A: Integer);\nbegin")
    assert [e["lines"][:2] for e in found.entries] == [[
        f"### Nested.pas:{_line_no(NESTED_AFTER, 'Helper(1)')} ruft Helper(...)",
        f"- Gegenstelle Helper [Helpers.pas:{impl}]: procedure Helper(A: Integer)"]]
    assert not any("ENested" in line for e in found.entries for line in e["lines"])


FMT_PAS = (
    "unit Fmt;\n\ninterface\n\nuses\n  Tree;\n\ntype\n  TFmt = class\n  public\n"
    "    function Format(const S: string): string;\n  end;\n\nimplementation\n\n"
    "function TFmt.Format(const S: string): string;\nbegin\n  raise EParse.Create(S);\nend;\n\n"
    "end.\n")
USEFMT_PAS = (
    "unit UseFmt;\n\ninterface\n\nuses\n  System.SysUtils, Fmt;\n\nprocedure Run;\n\n"
    "implementation\n\nprocedure Run;\nvar\n  S: string;\nbegin\n  S := '';\nend;\n\nend.\n")
USEFMT_AFTER = USEFMT_PAS.replace(
    "  S := '';\n",
    "  S := System.SysUtils.Format('%d', [1]);\n  S := SysUtils.Format('%d', [2]);\n")


def test_n05_unit_qualified_call_outside_the_repo_is_counted(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Tree.pas": TREE_PAS, "Fmt.pas": FMT_PAS,
                                          "UseFmt.pas": USEFMT_PAS}, {"UseFmt.pas": USEFMT_AFTER})
    assert found.entries == []
    assert found.unresolved == 2


OVL_PAS = (
    "unit Ovl;\n\ninterface\n\nuses\n  Tree;\n\ntype\n  TC = class\n  public\n"
    "    procedure Add(V: Integer); overload;\n    procedure Add(V: string); overload;\n  end;\n\n"
    "procedure Run(C: TC);\n\nimplementation\n\n"
    "procedure TC.Add(V: string);\nbegin\n  raise EParse.Create(V);\nend;\n\n"
    "procedure TC.Add(V: Integer);\nbegin\nend;\n\n"
    "procedure Run(C: TC);\nbegin\n  C := nil;\nend;\n\nend.\n")
OVL_AFTER = OVL_PAS.replace("  C := nil;\n", "  C := nil;\n  C.Add('x');\n")


def test_n06_overloads_match_by_parameter_types(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Tree.pas": TREE_PAS, "Ovl.pas": OVL_PAS},
                          {"Ovl.pas": OVL_AFTER})
    (entry,) = found.entries
    lines = entry["lines"]
    impl_s = _line_no(OVL_PAS, "procedure TC.Add(V: string)")
    impl_i = _line_no(OVL_PAS, "procedure TC.Add(V: Integer)")
    assert lines[1:3] == [f"- Gegenstelle TC.Add [Ovl.pas:{impl_s}]: procedure Add(V: string)",
                          f"  deklariert: Ovl.pas:{_line_no(OVL_PAS, 'Add(V: string); overload')}"]
    i = lines.index(f"- Gegenstelle TC.Add [Ovl.pas:{impl_i}]: procedure Add(V: Integer)")
    assert lines[i + 1] == f"  deklariert: Ovl.pas:{_line_no(OVL_PAS, 'Add(V: Integer); overload')}"


CLS_PAS = (
    "unit Cls;\n\ninterface\n\nuses\n  Tree;\n\ntype\n  TFmt = class\n"
    "    function Format(const S: string): string;\n    class function Make: TFmt;\n  end;\n\n"
    "procedure Run(F: TFmt);\n\nimplementation\n\n"
    "function TFmt.Format(const S: string): string;\nbegin\n  raise EParse.Create(S);\nend;\n\n"
    "class function TFmt.Make: TFmt;\nbegin\n  raise EParse.Create('m');\nend;\n\n"
    "procedure Run(F: TFmt);\nbegin\n  F := nil;\nend;\n\nend.\n")
CLS_AFTER = CLS_PAS.replace("  F := nil;\n", "  F := nil;\n  F.Format('x');\n  F := TFmt.Make();\n")


def test_n07_class_prefix_only_for_class_methods(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Tree.pas": TREE_PAS, "Cls.pas": CLS_PAS},
                          {"Cls.pas": CLS_AFTER})
    assert [e["lines"][1].split("]: ", 1)[1] for e in found.entries] == [
        "function Format(const S: string): string", "class function Make: TFmt"]


NODES_PAS = (
    "unit Nodes;\n\ninterface\n\nuses\n  System.Generics.Collections;\n\ntype\n"
    "  TNode = class;\n\n  TKids = class(TObjectList<TNode>)\n  end;\n\n"
    "  TNode = class\n  public\n    Kids: TKids;\n  end;\n\nimplementation\n\nend.\n")
TREES_PAS = (
    "unit Trees;\n\ninterface\n\nuses\n  Nodes;\n\ntype\n  TTree = class\n  public\n"
    "    Root: TNode;\n  end;\n\nimplementation\n\nend.\n")
APP_PAS = (
    "unit App;\n\ninterface\n\nuses\n  Trees;\n\nprocedure Run(T: TTree);\n\nimplementation\n\n"
    "procedure Run(T: TTree);\nbegin\n  T := nil;\nend;\n\nend.\n")
APP_AFTER = APP_PAS.replace("  T := nil;\n", "  T := nil;\n  T.Root.Kids.Remove(nil);\n")


def test_n08_field_types_resolve_in_the_declaring_unit(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Nodes.pas": NODES_PAS, "Trees.pas": TREES_PAS,
                                          "App.pas": APP_PAS}, {"App.pas": APP_AFTER})
    owner = _by_head(found)[
        f"### App.pas:{_line_no(APP_AFTER, 'T.Root.Kids')} Remove auf T.Root.Kids: TKids"]
    assert owner[0] == (f"- Gegenstelle TKids [Nodes.pas:{_line_no(NODES_PAS, 'TKids = class')}]: "
                        "TKids = class(TObjectList<TNode>)")
    assert owner[1].startswith("  Besitz (RTL): TObjectList<…>")


GLOB_PAS = (
    "unit Glob;\n\ninterface\n\nuses\n  Tree;\n\nvar\n  GTree: TQueryTree;\n\nprocedure Run;\n\n"
    "implementation\n\nvar\n  GLocal: TQueryTree;\n\n"
    "procedure Run;\nbegin\n  GTree := nil;\nend;\n\nend.\n")
GLOB_AFTER = GLOB_PAS.replace("  GTree := nil;\n",
                              "  GTree := nil;\n  GTree.Free;\n  GLocal.Free;\n")
GLOB2_PAS = (
    "unit Glob2;\n\ninterface\n\nuses\n  Glob;\n\nprocedure Run2;\n\nimplementation\n\n"
    "procedure Run2;\nbegin\n  Run;\nend;\n\nend.\n")
GLOB2_AFTER = GLOB2_PAS.replace("  Run;\n", "  Run;\n  GTree.Remove(nil);\n")


def test_n09_unit_level_variables_have_a_type(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Tree.pas": TREE_PAS, "Glob.pas": GLOB_PAS,
                                          "Glob2.pas": GLOB2_PAS},
                          {"Glob.pas": GLOB_AFTER, "Glob2.pas": GLOB2_AFTER})
    heads = _by_head(found)
    for rel, text, needle, head in (
            ("Glob.pas", GLOB_AFTER, "GTree.Free", "Free auf GTree: TQueryTree"),
            ("Glob.pas", GLOB_AFTER, "GLocal.Free", "Free auf GLocal: TQueryTree"),
            ("Glob2.pas", GLOB2_AFTER, "GTree.Remove", "Remove auf GTree: TQueryTree")):
        assert heads[f"### {rel}:{_line_no(text, needle)} {head}"][0] == _tree_head()


COND_PAS = (
    "unit Cond;\n\ninterface\n\nuses\n  Tree;\n\n"
    "procedure Run(A, B: Boolean);\nprocedure Other(L: TQueryTree);\n\nimplementation\n\n"
    "procedure Run(A, B: Boolean);\nbegin\n"
    "  {$IF Defined(X)}\n  if A then begin\n"
    "    {$IFDEF Y} Writeln('y'); {$ELSE} begin {$ENDIF}\n"
    "  {$ELSEIF Defined(Z)}\n  if B then begin\n  {$IFEND}\n"
    "    Writeln('x');\n  end;\nend;\n\n"
    "procedure Other(L: TQueryTree);\nbegin\n  L := nil;\nend;\n\nend.\n")
COND_AFTER = COND_PAS.replace("  L := nil;\n", "  L := nil;\n  L.Remove(nil);\n")
BROKEN_PAS = (
    "unit Broken;\n\ninterface\n\nuses\n  Tree;\n\nprocedure Run(A: Boolean; L: TQueryTree);\n\n"
    "implementation\n\nprocedure Run(A: Boolean; L: TQueryTree);\nbegin\n"
    "  {$IFDEF X}\n  if A then\n  {$ELSE}\n  if not A then begin\n  {$ENDIF}\n"
    "    L := nil;\n  {$IFNDEF X}\n  end;\n  {$ENDIF}\nend;\n\nend.\n")
BROKEN_AFTER = BROKEN_PAS.replace("    L := nil;\n", "    L := nil;\n    L.Remove(nil);\n")


def test_n10_only_the_first_branch_of_conditional_code(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Tree.pas": TREE_PAS, "Cond.pas": COND_PAS,
                                          "Broken.pas": BROKEN_PAS},
                          {"Cond.pas": COND_AFTER, "Broken.pas": BROKEN_AFTER})
    assert [e["lines"][:2] for e in found.entries] == [[
        f"### Cond.pas:{_line_no(COND_AFTER, 'L.Remove')} Remove auf L: TQueryTree", _tree_head()]]
    # Geht die Zählung auch im ersten Zweig nicht auf: nichts statt einer sicheren falschen Antwort.
    assert found.unparsed == [("Broken.pas", kit.SKIP_UNBALANCED)]
    assert kit.SKIP_UNBALANCED not in (kit.NOT_IN_TARGET, kit.SKIP_SYMLINK, kit.SKIP_SYNTAX)


PLAIN_PAS = (
    "unit Plain;\n\ninterface\n\ntype\n  TPlain = class\n  public\n    constructor Create;\n"
    "  end;\n\nimplementation\n\nconstructor TPlain.Create;\nbegin\n  inherited Create;\nend;\n\n"
    "end.\n")


def test_n11_changed_inherited_create_of_an_owning_list(tmp_path):
    kit = _kit()
    tree_after = TREE_PAS.replace("inherited Create(True)", "inherited Create(False)")
    plain_after = PLAIN_PAS.replace("inherited Create;", "inherited Create();")
    found = _delphi_found(kit, tmp_path, {"Tree.pas": TREE_PAS, "Plain.pas": PLAIN_PAS},
                          {"Tree.pas": tree_after, "Plain.pas": plain_after})
    line = _line_no(tree_after, "inherited Create(False)")
    (entry,) = found.entries
    assert entry["kind"] == "owner"
    assert entry["lines"][:3] == [f"### Tree.pas:{line} inherited Create auf Self: TQueryTree",
                                  _tree_head(), f"  inherited Create(False) at Tree.pas:{line}"]
    assert entry["lines"][3].startswith("  Besitz (RTL): TObjectList<…>")


SHARED_PAS = (
    "unit Shared;\n\ninterface\n\nprocedure Check(A: Integer);\n\nimplementation\n\n"
    "procedure Check(A: Integer);\nbegin\n  raise EShared.Create('s');\nend;\n\nend.\n")
MAIN_PAS = (
    "unit Main;\n\ninterface\n\nuses\n  Compat;\n\nprocedure Run;\n\nimplementation\n\n"
    "procedure Run;\nbegin\n  Check(0);\nend;\n\nend.\n")


def test_n12_delphi_symlinks_followed_and_outside_files_noted(tmp_path):
    kit = _kit()
    root = _commit_repo(tmp_path, {"lib/Shared.pas": SHARED_PAS, "app/Main.pas": MAIN_PAS},
                        {"lib/Shared.pas": SHARED_PAS + "\n"})
    _link_commit(root, {"app/Compat.pas": "../lib/Shared.pas", "app/Lost.pas": "../nirgends.pas"})
    (root / "app" / "Main.pas").write_text(MAIN_PAS.replace("Check(0)", "Check(1)"),
                                           encoding="utf-8")
    git(root, "commit", "--quiet", "-am", "aufruf")
    md = _counterparts_md(kit, root, "HEAD~1..HEAD")
    impl = _line_no(SHARED_PAS, "procedure Check(A: Integer);\nbegin")
    assert f"- Gegenstelle Check [app/Compat.pas:{impl}]: procedure Check(A: Integer)\n" in md
    assert ("\n1 Delphi-Datei(en) außerhalb des Pakets am ZIEL nicht lesbar (Symlink) — "
            "dort keine Gegenstellen gesucht.\n") in md
    assert "Python-Datei(en)" not in md


RTL_PAS = (
    "unit Rtl;\n\ninterface\n\nuses\n  System.Generics.Collections, Contnrs;\n\n"
    "procedure Run(S: TObjectStack<TObject>; Q: TObjectQueue<TObject>; L: TObjectList);\n\n"
    "implementation\n\n"
    "procedure Run(S: TObjectStack<TObject>; Q: TObjectQueue<TObject>; L: TObjectList);\n"
    "begin\n  S := nil;\nend;\n\nend.\n")
RTL_AFTER = RTL_PAS.replace("  S := nil;\n", "  S := nil;\n  S.Extract;\n  Q.Extract;\n"
                            "  L.Extract(nil);\n")


def test_n13_object_stack_queue_and_contnrs_list(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Rtl.pas": RTL_PAS}, {"Rtl.pas": RTL_AFTER})
    assert [(e["lines"][0], len(e["lines"])) for e in found.entries] == [
        (f"### Rtl.pas:{_line_no(RTL_AFTER, 'S.Extract')} Extract auf S: TObjectStack<TObject>", 2),
        (f"### Rtl.pas:{_line_no(RTL_AFTER, 'Q.Extract')} Extract auf Q: TObjectQueue<TObject>", 2),
        (f"### Rtl.pas:{_line_no(RTL_AFTER, 'L.Extract')} Extract auf L: TObjectList", 2)]
    stack, queue, plain = (e["lines"][1] for e in found.entries)
    assert stack.startswith("  Besitz (RTL): TObjectStack<…>: OwnsObjects standardmäßig wahr")
    assert queue.startswith("  Besitz (RTL): TObjectQueue<…>: OwnsObjects standardmäßig wahr")
    assert plain.startswith("  Besitz (RTL): TObjectList (Contnrs")
    assert "<…>" not in plain


SCOPES_PAS = (
    "unit Scopes;\n\ninterface\n\nuses\n  Tree, System.Classes, System.SysUtils, "
    "System.Generics.Collections;\n\nprocedure Run;\n\nimplementation\n\n"
    "procedure Run;\nvar\n  Proc: TProc<TQueryTree>;\nbegin\n"
    "  begin\n    var L: TObjectList<TNode> := nil;\n    L := nil;\n  end;\n"
    "  begin\n    var L: TStringList := nil;\n    L := nil;\n  end;\n"
    "  Proc := procedure(L: TQueryTree)\n    begin\n      L := nil;\n    end;\nend;\n\nend.\n")
SCOPES_AFTER = (SCOPES_PAS.replace("      L := nil;\n", "      L.Remove(nil);\n")
                .replace("    L := nil;\n", "    L.Free;\n"))


def test_n14_inline_and_anonymous_variables_by_visibility(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Tree.pas": TREE_PAS, "Scopes.pas": SCOPES_PAS},
                          {"Scopes.pas": SCOPES_AFTER})
    assert [e["lines"][0] for e in found.entries] == [
        f"### Scopes.pas:{_line_no(SCOPES_AFTER, 'L.Free')} Free auf L: TObjectList<TNode>",
        f"### Scopes.pas:{_line_no(SCOPES_AFTER, 'L.Remove')} Remove auf L: TQueryTree"]


TRUNC_PAS = "unit Trunc;\n\ninterface\n\ntype\n  TR = record\n    case Tag:"


def test_n15_truncated_variant_record_is_unparsed(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Trunc.pas": "unit Trunc;\n"}, {"Trunc.pas": TRUNC_PAS})
    assert found == kit.Collected([], 0, [("Trunc.pas", kit.SKIP_UNBALANCED)])


BIG_PAS = ("unit {};\n\ninterface\n\nprocedure X;\n\nimplementation\n\n"
           "procedure X;\nbegin\nend;\n\nend.\n")
LAZY_PAS = (
    "unit Lazy;\n\ninterface\n\nuses\n  Big1, Big2, Big3;\n\nprocedure Check(A: Integer = 0);\n"
    "procedure Run;\n\nimplementation\n\nprocedure Check(A: Integer);\nbegin\nend;\n\n"
    "procedure Run;\nbegin\n  Check(0);\nend;\n\nend.\n")


def test_n19_used_units_scanned_only_on_demand(tmp_path, monkeypatch):
    kit = _kit()
    scanned = []

    class Spy(kit._PasUnit):
        def __init__(self, rel, text):
            scanned.append(rel)
            super().__init__(rel, text)

    monkeypatch.setattr(kit, "_PasUnit", Spy)
    before = {f"Big{i}.pas": BIG_PAS.format(f"Big{i}") for i in (1, 2, 3)}
    before["Lazy.pas"] = LAZY_PAS
    found = _delphi_found(kit, tmp_path, before,
                          {"Lazy.pas": LAZY_PAS.replace("Check(0)", "Check(1)")})
    assert [e["lines"][0] for e in found.entries] == [
        f"### Lazy.pas:{_line_no(LAZY_PAS, 'Check(0)')} ruft Check(...)"]
    assert scanned == ["Lazy.pas"]


# --- review_kit.py: Funde des Prüfpunkts nach Task 5, zweite Runde (Delphi) -----------------

def _unit(name, interface, implementation, uses=""):
    """Kleine Unit: `uses` (ohne Liste: keine), interface- und implementation-Teil."""
    head = f"uses\n  {uses};\n\n" if uses else ""
    return (f"unit {name};\n\ninterface\n\n{head}{interface}\nimplementation\n\n"
            f"{implementation}\nend.\n")


def _raising(head, exc="EX"):
    """Implementierung `head` (ohne `;`), die `exc` wirft."""
    return f"{head};\nbegin\n  raise {exc}.Create('x');\nend;\n\n"


def _heads(found):
    return [e["lines"][0] for e in found.entries]


SETTINGS_PAS = _unit(
    "Settings",
    "type\n  TSettings = class\n  public\n    procedure Load(A: Integer = 0);\n  end;\n\n"
    "var\n  Settings: TSettings;\n",
    _raising("procedure TSettings.Load(A: Integer)"))
USESET_PAS = _unit("UseSet", "procedure Run;\n",
                   "procedure Run;\nbegin\n  Settings.Load(0);\nend;\n", uses="Settings")


def test_p01_variable_named_like_its_unit_shadows_the_unit(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Settings.pas": SETTINGS_PAS, "UseSet.pas": USESET_PAS},
                          {"UseSet.pas": USESET_PAS.replace("Load(0)", "Load(1)")})
    (entry,) = found.entries
    assert entry["lines"][:2] == [
        f"### UseSet.pas:{_line_no(USESET_PAS, 'Settings.Load')} ruft Load(...)",
        f"- Gegenstelle TSettings.Load [Settings.pas:"
        f"{_line_no(SETTINGS_PAS, 'procedure TSettings.Load')}]: procedure Load(A: Integer = 0)"]


BRANCH_PAS = _unit(
    "Branch", "procedure Check(A: Integer = 0);\nprocedure Run;\n",
    _raising("procedure Check(A: Integer)")
    + "procedure Run;\nbegin\n  {$IFDEF A}\n  Check(1);\n  {$ELSE}\n  Check(2);\n"
      "  {$ENDIF}\nend;\n")


def test_p02_changed_lines_in_a_skipped_branch_are_counted_and_named(tmp_path):
    kit = _kit()
    after = BRANCH_PAS.replace("Check(2)", "Check(3)").replace("Check(1)", "Check(4)")
    found = _delphi_found(kit, tmp_path, {"Branch.pas": BRANCH_PAS}, {"Branch.pas": after})
    # Der erste Zweig wird gelesen; die Zeile im {$ELSE}-Zweig steht gezählt und benannt da.
    assert _heads(found) == [f"### Branch.pas:{_line_no(after, 'Check(4)')} ruft Check(...)"]
    reason = f"1 {kit.SKIP_BRANCH} ({_line_no(after, 'Check(3)')})"
    assert found.unparsed == [("Branch.pas", reason)]
    block = kit.render_block({"id": "p1", "files": ["Branch.pas"], "unreadable": found.unparsed},
                             found.entries, found.unresolved, None)
    assert f"- `Branch.pas` — {reason}, dort keine Gegenstellen gesammelt\n" in block
    assert f"1 {kit.SKIP_BRANCH} in Paketdateien (in der Dateiliste genannt).\n" in block
    assert "nicht lesbar" not in block


PROPS_PAS = _unit(
    "Props",
    "type\n  TMy = class\n  public\n    function Count: Integer;\n  end;\n\n"
    "  TQ = class\n  public\n    procedure Clear;\n  end;\n\nprocedure Run(S: TObject);\n",
    _raising("function TMy.Count: Integer") + _raising("procedure TQ.Clear")
    + "procedure Run(S: TObject);\nvar\n  N: Integer;\nbegin\n  N := 0;\nend;\n")
PROPS_AFTER = PROPS_PAS.replace("  N := 0;\n",
                                "  N := S.Items.Count + 1;\n  Form1.Memo.Lines.Clear;\n")


def test_p03_parenless_on_an_unknown_receiver_is_never_guessed(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Props.pas": PROPS_PAS}, {"Props.pas": PROPS_AFTER})
    assert found.entries == []
    # Die Anweisung `Form1.Memo.Lines.Clear;` ist ein Aufruf: nicht geraten, aber gezählt.
    assert found.unresolved == 1


IDX_PAS = _unit("Idx", "procedure Idx(A: Integer = 0);\n", _raising("procedure Idx(A: Integer)"))
CMP_PAS = _unit("Cmp", "procedure Run;\n",
                "procedure Run;\nvar\n  Idx, Limit, Max: Integer;\nbegin\n  Idx := 0;\nend;\n",
                uses="Idx")


def test_p04_comparison_with_keywords_is_no_generic_call(tmp_path):
    kit = _kit()
    after = CMP_PAS.replace("  Idx := 0;\n",
                            "  if Idx < Limit or Max > (Limit - 1) then\n    Exit;\n")
    found = _delphi_found(kit, tmp_path, {"Idx.pas": IDX_PAS, "Cmp.pas": CMP_PAS},
                          {"Cmp.pas": after})
    assert found == kit.Collected([], 0, [])


HELP_PAS = _unit(
    "Help",
    "type\n  TCH = class helper for TObject\n  end;\n\n"
    "  TSH = record helper for string\n  end;\n\nprocedure Check(A: Integer = 0);\n"
    "procedure Run;\n",
    _raising("procedure Check(A: Integer)") + "procedure Run;\nbegin\n  Check(0);\nend;\n")


def test_p05_empty_helper_body_keeps_its_end(tmp_path):
    kit = _kit()
    after = HELP_PAS.replace("Check(0)", "Check(1)")
    found = _delphi_found(kit, tmp_path, {"Help.pas": HELP_PAS}, {"Help.pas": after})
    assert found.unparsed == []
    assert _heads(found) == [f"### Help.pas:{_line_no(after, 'Check(1)')} ruft Check(...)"]


PARK_PAS = _unit("Park", "procedure Check(A: Integer = 0);\nprocedure Run;\n",
                 _raising("procedure Check(A: Integer)")
                 + "procedure Run;\nbegin\n  Check(0);\nend;\n")
PARK_AFTER = PARK_PAS.replace("Check(0)", "Check(1)") + "\nprocedure Old;\nbegin\n  Check(2);\n"


def test_p06_text_after_the_final_end_is_not_scanned(tmp_path):
    kit = _kit()
    found = _delphi_found(kit, tmp_path, {"Park.pas": PARK_PAS}, {"Park.pas": PARK_AFTER})
    assert found.unparsed == []
    assert _heads(found) == [f"### Park.pas:{_line_no(PARK_AFTER, 'Check(1)')} ruft Check(...)"]


DATA_PAS = _unit(
    "DataUse",
    "type\n  TMy = class\n  public\n    function Count(A: Integer = 0): Integer;\n  end;\n\n"
    "  TC = class\n  public\n    Data: TExternal;\n    procedure Run;\n  end;\n",
    _raising("function TMy.Count(A: Integer): Integer")
    + "procedure TC.Run;\nbegin\n  Data.Items.Count(0);\nend;\n")


def test_p07_known_field_is_no_rtl_unit_scope(tmp_path):
    kit = _kit()
    after = DATA_PAS.replace("Count(0)", "Count(1)")
    found = _delphi_found(kit, tmp_path, {"DataUse.pas": DATA_PAS}, {"DataUse.pas": after})
    assert found.unresolved == 0
    assert [e["lines"][:2] for e in found.entries] == [[
        f"### DataUse.pas:{_line_no(after, 'Count(1)')} ruft Count(...)",
        f"- Gegenstelle TMy.Count [DataUse.pas:{_line_no(DATA_PAS, 'function TMy.Count')}]: "
        "function Count(A: Integer = 0): Integer"]]


BAD_PAS = _unit("Bad", "procedure Check(A: Integer = 0);\n",
                "procedure Check(A: Integer);\nbegin\n  if A then begin\n    Exit;\nend;\n")


def test_p08_unbalanced_packet_file_without_changed_lines_is_unparsed(tmp_path):
    kit = _kit()
    after = BAD_PAS.replace("    Exit;\n", "")
    found = _delphi_found(kit, tmp_path, {"Bad.pas": BAD_PAS}, {"Bad.pas": after})
    assert found == kit.Collected([], 0, [("Bad.pas", kit.SKIP_UNBALANCED)])


def test_p08_note_on_unbalanced_units_does_not_depend_on_packet_order(tmp_path):
    kit = _kit()
    one = _unit("Main1", "procedure Run;\n", "procedure Run;\nbegin\n  Run;\nend;\n")
    two = _unit("Main2", "procedure Run2;\n", "procedure Run2;\nbegin\n  Check(0);\nend;\n",
                uses="Bad")
    root = _commit_repo(tmp_path, {"a/Main1.pas": one, "b/Main2.pas": two, "c/Bad.pas": BAD_PAS},
                        {"a/Main1.pas": one.replace("  Run;\n", "  Run;\n  Run;\n"),
                         "b/Main2.pas": two.replace("Check(0)", "Check(1)")})
    plan, run = _split_plan(kit, root, split_at=1)
    assert [p["files"] for p in plan["packets"]] == [["a/Main1.pas"], ["b/Main2.pas"]]
    kit.write_counterparts(root, run)
    note = (f"\n1 Delphi-Datei(en) außerhalb des Pakets am ZIEL nicht lesbar "
            f"({kit.SKIP_UNBALANCED}) — dort keine Gegenstellen gesucht.\n")
    for pid in ("p1", "p2"):
        assert note in (kit.run_dir(root, run) / "packets" / f"{pid}.md").read_text("utf-8")


GSET_PAS = _unit("GSet", "var\n  GSettings: TObject;\n", "")
NAMES_PAS = _unit(
    "Names", "type\n  TP = procedure(const S: string = ''; X: Integer) of object;\n"
    "  TN = class\n  public\n    procedure Run;\n  end;\n\n"
    "procedure GSettings;\nprocedure L;\nprocedure P;\nprocedure C;\n"
    "procedure Use(A: TObject);\n",
    _raising("procedure GSettings") + _raising("procedure L") + _raising("procedure P")
    + _raising("procedure C") + "procedure Use(A: TObject);\nbegin\nend;\n")
INFER_PAS = _unit("Infer", "procedure Run(const P);\n",
                  "procedure Run(const P);\nconst\n  C = 1;\nbegin\n"
                  "  var L := TObject.Create;\n  Use(nil);\nend;\n", uses="Names, GSet")


def test_p09_names_of_values_are_no_parenless_calls(tmp_path):
    kit = _kit()
    after = INFER_PAS.replace("  Use(nil);\n",
                              "  Use(L);\n  Use(GSettings);\n  Use(P);\n  Use(C);\n")
    found = _delphi_found(kit, tmp_path, {"GSet.pas": GSET_PAS, "Names.pas": NAMES_PAS,
                                          "Infer.pas": INFER_PAS}, {"Infer.pas": after})
    assert found == kit.Collected([], 0, [])
    # `const` in den Parametern eines Prozedurtyps öffnet keinen const-Abschnitt.
    names = kit._PasUnit("Names.pas", NAMES_PAS)
    assert not names.broken and "tn" in names.classes and names.consts == set()


def test_p10_call_on_an_unbalanced_repo_unit_is_counted(tmp_path):
    kit = _kit()
    main = _unit("Main", "procedure Run;\n", "procedure Run;\nbegin\n  Bad.Check(0);\nend;\n",
                 uses="Bad")
    found = _delphi_found(kit, tmp_path, {"Bad.pas": BAD_PAS, "Main.pas": main},
                          {"Main.pas": main.replace("Check(0)", "Check(1)")})
    assert found == kit.Collected([], 1, [])


BADSHARED_PAS = BAD_PAS.replace("unit Bad;", "unit Shared;")


def _linked_repo(root, main):
    """lib/Shared.pas (Blöcke gehen nicht auf), app/Compat.pas → ../lib/Shared.pas, dann ein
    Commit, der den Aufruf in app/Main.pas ändert."""
    root.mkdir(parents=True)
    root = _commit_repo(root,{"lib/Shared.pas": BADSHARED_PAS, "app/Main.pas": main},
                        {"lib/Shared.pas": BADSHARED_PAS + "\n"})
    _link_commit(root, {"app/Compat.pas": "../lib/Shared.pas"})
    (root / "app" / "Main.pas").write_text(main.replace("Check(0)", "Check(1)"), encoding="utf-8")
    git(root, "commit", "--quiet", "-am", "aufruf")
    return root


def test_p11_unbalanced_symlink_target_noted_once_and_scanned_once(tmp_path, monkeypatch):
    kit = _kit()
    main = _unit("Main", "procedure Run;\n", "procedure Run;\nbegin\n  Check(0);\nend;\n",
                 uses="Compat")
    md = _counterparts_md(kit, _linked_repo(tmp_path / "note", main), "HEAD~1..HEAD")
    assert (f"\n1 Delphi-Datei(en) außerhalb des Pakets am ZIEL nicht lesbar "
            f"({kit.SKIP_UNBALANCED}) — dort keine Gegenstellen gesucht.\n") in md

    scanned = []

    class Spy(kit._PasUnit):
        def __init__(self, rel, text):
            scanned.append(rel)
            super().__init__(rel, text)

    monkeypatch.setattr(kit, "_PasUnit", Spy)
    root = _linked_repo(tmp_path / "scan", main.replace("  Compat;", "  Compat, Shared;"))
    kit.collect_delphi(root, "HEAD~1..HEAD", ["app/Main.pas"])
    assert sorted(scanned) == ["app/Main.pas", "lib/Shared.pas"]


# --- review_kit.py: Datei-Schlüssel und --since (Task 6) ---------------------------------

SINCE_C = 'def load(path):\n    if not path:\n        raise ValueError("leer")\n    return path\n'
SINCE_C_CHANGED = SINCE_C.replace("    return path\n",
                                  '    if path == "-":\n        raise KeyError(path)\n    return path\n')
SINCE_A = "from c import load\n\n\ndef run(p):\n    return load(p)\n"
SINCE_B = _lines(6, "b")


def _tick(kit, monkeypatch):
    """Die Uhr der Lauf-IDs läuft je Aufruf eine Sekunde weiter: spätere Läufe sortieren später."""
    moment = [dt.datetime(2026, 11, 2, 9, 0, 0, tzinfo=dt.timezone.utc)]

    def now():
        moment[0] += dt.timedelta(seconds=1)
        return moment[0]

    monkeypatch.setattr(kit, "_now", now)


def _commit_files(root, message, files):
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", message)
    return git(root, "rev-parse", "HEAD").strip()


def _since_repo(root):
    """t0 (Tag base): c.py wirft. t1: a.py (ruft c.load) und b.py. t2: b.py ändert sich, c.py
    nicht. Branch `gegenstelle` ab t1: b.py und c.py ändern sich (neue raise-Stelle in c.py)."""
    root.mkdir(parents=True)
    git(root, "init", "--quiet", "--initial-branch=main")
    git(root, "config", "user.email", "t@example.invalid")
    git(root, "config", "user.name", "Test")
    _commit_files(root, "basis", {"c.py": SINCE_C, "README.md": "# x\n"})
    git(root, "tag", "base")
    _commit_files(root, "t1", {"a.py": SINCE_A, "b.py": SINCE_B})
    git(root, "tag", "t1")
    git(root, "checkout", "--quiet", "-b", "gegenstelle")
    _commit_files(root, "t2c", {"b.py": SINCE_B + "b_neu = 1\n", "c.py": SINCE_C_CHANGED})
    git(root, "tag", "t2c")
    git(root, "checkout", "--quiet", "main")
    _commit_files(root, "t2", {"b.py": SINCE_B + "b_neu = 1\n"})
    git(root, "tag", "t2")
    return root


def _record(kit, root, plan, packet, findings, tool="test"):
    """Ergebnis eines früheren Laufs über `record` ablegen — dasselbe Format (`_meta.run`,
    `_meta.plan`), das `audit` annimmt und `--since` liest. Ein vorhandenes Ergebnis des
    Pakets wird vorher entfernt."""
    directory = _run_path(root, plan)
    (directory / "results" / f"{packet}.json").unlink(missing_ok=True)
    payload = root.parent / f"payload-{plan['_meta']['run']}-{packet}.json"
    payload.write_text(json.dumps(findings, ensure_ascii=False), encoding="utf-8")
    kit.record(directory, packet, tool, payload)


def _finding(path, line, summary):
    return {"file": path, "line": line, "summary": summary, "failure_scenario": f"{summary}!"}


def _run_path(root, plan):
    return root / ".skills/cache/deep-review" / plan["_meta"]["run"]


def test_since_per_file(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")

    # Zwei frühere Läufe über t0..t1 mit derselben Datei; der zweite ist der jüngere.
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    run_a2 = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    _record(kit, root, run_a, "p1", [_finding("a.py", 5, "alt A"), _finding("b.py", 1, "b alt")])
    _record(kit, root, run_a2, "p1", [_finding("a.py", 5, "neu A2"), _finding("b.py", 2, "b A2")])
    assert run_a["_meta"]["run"] < run_a2["_meta"]["run"]
    keys_a = run_a["file_keys"]
    assert list(keys_a) == ["a.py", "b.py"]
    assert all(re.fullmatch(r"[0-9a-f]{64}", v["key"]) and v["reused_from"] is None
               for v in keys_a.values())
    assert keys_a["a.py"]["key"] != keys_a["b.py"]["key"]
    assert [v["changed_lines"] for v in keys_a.values()] == [5, 6]
    assert run_a2["file_keys"] == keys_a

    # Lauf B über t0..t2: a.py gleich geblieben (Gegenstelle c.py auch), b.py geändert.
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    assert plan_b["file_keys"]["a.py"]["key"] == keys_a["a.py"]["key"]
    assert plan_b["file_keys"]["b.py"]["key"] != keys_a["b.py"]["key"]
    before = json.loads(json.dumps(plan_b))
    dirs = [_run_path(root, run_a), _run_path(root, run_a2)]
    for order in (dirs, dirs[::-1]):                    # die Reihenfolge der Läufe zählt nicht
        applied = kit.apply_since(plan_b, order)
        assert plan_b == before                          # die Eingabe bleibt, wie sie ist
        assert applied["file_keys"]["a.py"] == {
            "key": keys_a["a.py"]["key"], "changed_lines": 5,
            "base_blob": kit.ABSENT_MARK, "target_blob": "100644:" + _blob(root, "t2", "a.py"),
            "reused_from": run_a2["_meta"]["run"],       # der jüngere Lauf gilt
            "reused_chain": [run_a2["_meta"]["run"]],
            "findings": [_finding("a.py", 5, "neu A2")]}
        assert applied["file_keys"]["b.py"] == {
            "key": plan_b["file_keys"]["b.py"]["key"], "changed_lines": 7,
            "base_blob": kit.ABSENT_MARK, "target_blob": "100644:" + _blob(root, "t2", "b.py"),
            "reused_from": None}
        # b.py allein wird neu gepackt; ohne Hilfscommits baut erst `counterparts` den Bereich.
        assert applied["packets"] == [{"id": "p1", "files": ["b.py"], "changed_lines": 7,
                                       "range": None, "reused_from": None}]
        assert applied["split"] is True and applied["changed_lines"] == plan_b["changed_lines"]
        assert list(applied) == list(plan_b)

    # Ein jüngerer Lauf ohne angenommenes Ergebnis verdeckt den älteren nicht, und ohne
    # Ergebnisse wird nichts übernommen, obwohl die Schlüssel gleich sind.
    run_x = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    assert run_x["_meta"]["run"] > run_a2["_meta"]["run"]
    assert kit.apply_since(plan_b, [dirs[0], dirs[1], _run_path(root, run_x)])[
        "file_keys"]["a.py"]["reused_from"] == run_a2["_meta"]["run"]
    assert kit.apply_since(plan_b, [_run_path(root, run_x)]) == plan_b
    (_run_path(root, run_a2) / "results" / "p1.json").write_text("{kaputt", encoding="utf-8")
    assert kit.apply_since(plan_b, dirs)["file_keys"]["a.py"]["reused_from"] == run_a["_meta"]["run"]
    _record(kit, root, run_a2, "p1", [_finding("a.py", 5, "neu A2")])

    # Ein Lauf ohne Plan ist ein KitError, kein stilles Auslassen.
    with pytest.raises(kit.KitError, match="keinen Plan"):
        kit.apply_since(plan_b, [tmp_path / "2026-01-01-000000-abcdef0-zzzz"])

    # c.py ändert sich (die Gegenstelle von a.py): a.py steht auch ohne eigene Änderung neu an.
    plan_c = kit.build_plan(root, "base..t2c", "standard", "bugs", None, False)
    assert plan_c["file_keys"]["a.py"]["key"] != keys_a["a.py"]["key"]
    assert list(plan_c["file_keys"]) == ["a.py", "b.py", "c.py"]
    applied_c = kit.apply_since(plan_c, dirs)
    assert applied_c == plan_c                           # nichts übernommen, nichts umgepackt
    assert all(v["reused_from"] is None for v in applied_c["file_keys"].values())

    # Auf der Platte: plan_since schreibt den Plan zurück, mit dem Aufruf in _meta.generated.
    done = kit.plan_since(root, plan_b["_meta"]["run"], [run_a["_meta"]["run"],
                                                         run_a2["_meta"]["run"]])
    on_disk = json.loads((_run_path(root, plan_b) / "plan.json").read_text(encoding="utf-8"))
    assert on_disk == done and list(on_disk) == list(plan_b)
    assert done["file_keys"]["a.py"]["reused_from"] == run_a2["_meta"]["run"]
    assert done["_meta"]["generated"].endswith(
        f" --since {run_a['_meta']['run']},{run_a2['_meta']['run']}")
    assert git(root, "for-each-ref", "refs/deep-review/") == ""
    with pytest.raises(kit.KitError, match="sich selbst"):
        kit.plan_since(root, plan_b["_meta"]["run"], [plan_b["_meta"]["run"]])


def test_since_chain_all_reused_and_focus(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    _record(kit, root, run_a, "p1", [_finding("a.py", 5, "A")])
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    done_b = kit.plan_since(root, plan_b["_meta"]["run"], [run_a["_meta"]["run"]])
    _record(kit, root, done_b, "p1", [_finding("b.py", 3, "B")])

    # Lauf C über denselben Stand: a.py liegt (mit seinen Funden) im Plan von B, b.py in
    # dessen Ergebnis; nichts bleibt zu reviewen.
    plan_c = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    applied = kit.apply_since(plan_c, [_run_path(root, done_b)])
    assert applied["file_keys"]["a.py"]["reused_from"] == done_b["_meta"]["run"]
    assert applied["file_keys"]["a.py"]["findings"] == [_finding("a.py", 5, "A")]
    assert applied["file_keys"]["b.py"]["findings"] == [_finding("b.py", 3, "B")]
    assert applied["packets"] == [] and applied["split"] is True

    # Anderer Fokus: andere Schlüssel (kein Gegenstellen-Teil bei quality) und kein Übernehmen.
    quality = kit.build_plan(root, "base..t2", "standard", "quality", None, False)
    assert quality["file_keys"]["a.py"]["key"] != plan_c["file_keys"]["a.py"]["key"]
    assert kit.apply_since(quality, [_run_path(root, done_b)]) == quality
    sec = kit.build_plan(root, "base..t2", "standard", "security", None, False)
    assert kit.apply_since(sec, [_run_path(root, done_b)]) == sec


def test_file_keys_content_and_counterparts(tmp_path):
    kit = _kit()
    root = _since_repo(tmp_path / "repo")
    target = git(root, "rev-parse", "t1").strip()
    entry = {"file": "a.py", "line": 5, "kind": "call",
             "lines": ["### a.py:5 ruft load(...)", "- Gegenstelle load [c.py:1]: def load(path)",
                       "  wirft: ValueError"]}
    keys = kit.file_keys(root, target, ["b.py", "a.py"], [entry])
    assert list(keys) == ["a.py", "b.py"]
    assert all(re.fullmatch(r"[0-9a-f]{64}", v) for v in keys.values())
    assert keys == kit.file_keys(root, target, ["a.py", "b.py"], [entry])      # reihenfolgefrei
    # Die Gegenstellen-Zeilen der Datei gehen in den Schlüssel, die einer anderen Datei nicht.
    moved = {**entry, "lines": [*entry["lines"][:2], "  wirft: KeyError"]}
    other = {**entry, "file": "b.py"}
    assert kit.file_keys(root, target, ["a.py"], [moved])["a.py"] != keys["a.py"]
    both = kit.file_keys(root, target, ["a.py", "b.py"], [entry, other])
    assert both["a.py"] == keys["a.py"] and both["b.py"] != keys["b.py"]
    assert kit.file_keys(root, target, ["a.py"], [])["a.py"] != keys["a.py"]
    # Der Inhalt am ZIEL zählt, nicht der Arbeitsbaum.
    later = git(root, "rev-parse", "t2").strip()
    assert (kit.file_keys(root, later, ["b.py"], [])["b.py"]
            != kit.file_keys(root, target, ["b.py"], [])["b.py"])
    assert kit.file_keys(root, later, ["a.py"], [entry])["a.py"] == keys["a.py"]
    (root / "a.py").write_text("geändert\n", encoding="utf-8")
    assert kit.file_keys(root, target, ["a.py"], [entry])["a.py"] == keys["a.py"]
    # Eine Datei, die ZIEL nicht hat (gelöscht), bekommt einen eigenen Schlüssel.
    gone = kit.file_keys(root, git(root, "rev-parse", "base").strip(), ["a.py"], [])["a.py"]
    assert re.fullmatch(r"[0-9a-f]{64}", gone) and gone != keys["a.py"]


# --- Prüfpunkt 5: Funde F1–F9 zu Datei-Schlüssel und --since --------------------------------

def _fresh_repo(root):
    root.mkdir(parents=True)
    git(root, "init", "--quiet", "--initial-branch=main")
    git(root, "config", "user.email", "t@example.invalid")
    git(root, "config", "user.name", "Test")
    return root


def _blob(root, rev, path):
    return git(root, "rev-parse", f"{rev}:{path}").strip()


def _rewrite_plan(root, plan, change):
    """plan.json eines Laufs lesen, mit `change(data)` ändern und zurückschreiben."""
    path = _run_path(root, plan) / "plan.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_f1_since_reuses_only_when_coverage_chain_closes(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _fresh_repo(tmp_path / "chain")
    v1 = _lines(100, "v1")
    _commit_files(root, "t0", {"x.py": _lines(100, "v0"), "README.md": "# x\n"})
    git(root, "tag", "t0")
    _commit_files(root, "t1", {"x.py": v1})
    git(root, "tag", "t1")
    _commit_files(root, "t2", {"x.py": v1.replace("v1_4 = 4\n", "v1_4 = 44\n")})
    git(root, "tag", "t2")

    run_a0 = kit.build_plan(root, "t0..t1", "standard", "bugs", None, False)
    run_a = kit.build_plan(root, "t1..t2", "standard", "bugs", None, False)
    both = _finding("x.py", 7, "beide")
    _record(kit, root, run_a0, "p1", [_finding("x.py", 9, "A0"),
                                      {**both, "failure_scenario": "aus A0"}])
    _record(kit, root, run_a, "p1", [_finding("x.py", 5, "A"), both])
    plan_b = kit.build_plan(root, "t0..t2", "standard", "bugs", None, False)
    entry = plan_b["file_keys"]["x.py"]
    assert entry["key"] == run_a["file_keys"]["x.py"]["key"]          # gleicher Stand am ZIEL
    assert entry["base_blob"] == "100644:" + _blob(root, "t0", "x.py")
    assert entry["target_blob"] == "100644:" + _blob(root, "t2", "x.py")
    assert run_a["file_keys"]["x.py"]["base_blob"] == "100644:" + _blob(root, "t1", "x.py")
    assert run_a0["file_keys"]["x.py"]["target_blob"] == "100644:" + _blob(root, "t1", "x.py")

    # A sah nur t1..t2 (Zeile 5), B zählt t0..t2: ohne Kette nichts übernommen.
    assert kit.apply_since(plan_b, [_run_path(root, run_a)]) == plan_b
    assert kit.apply_since(plan_b, [_run_path(root, run_a0)]) == plan_b
    # A0 deckt t0..t1, A t1..t2: die Kette schließt sich, übernommen wird von A — mit den
    # Funden aller Glieder (der jüngste zuerst), ein Fund beider Läufe nur einmal.
    dirs = [_run_path(root, run_a0), _run_path(root, run_a)]
    for order in (dirs, dirs[::-1]):
        applied = kit.apply_since(plan_b, order)
        assert applied["file_keys"]["x.py"]["reused_from"] == run_a["_meta"]["run"]
        assert applied["file_keys"]["x.py"]["reused_chain"] == [run_a["_meta"]["run"],
                                                                run_a0["_meta"]["run"]]
        assert applied["file_keys"]["x.py"]["findings"] == [
            _finding("x.py", 5, "A"), both, _finding("x.py", 9, "A0")]
        assert applied["packets"] == []
    # Ohne Kette (A deckt alles selbst) besteht sie nur aus A.
    run_full = kit.build_plan(root, "t0..t2", "standard", "bugs", None, False)
    _record(kit, root, run_full, "p1", [_finding("x.py", 3, "voll")])
    alone = kit.apply_since(plan_b, [*dirs, _run_path(root, run_full)])["file_keys"]["x.py"]
    assert alone["reused_from"] == run_full["_meta"]["run"]
    assert alone["reused_chain"] == [run_full["_meta"]["run"]]
    assert alone["findings"] == [_finding("x.py", 3, "voll")]

    # Ein früherer Plan ohne die Blob-Felder übernimmt nichts und trägt keine Kette.
    def drop(data):
        del data["file_keys"]["x.py"]["base_blob"]
    _rewrite_plan(root, run_a0, drop)
    assert kit.apply_since(plan_b, dirs) == plan_b

    # Gelöscht: dieselbe Marke am ZIEL, aber ein anderer Stand an der Basis.
    root = _fresh_repo(tmp_path / "deleted")
    _commit_files(root, "d0", {"f.py": "v = 1\n", "README.md": "# x\n"})
    git(root, "tag", "d0")
    git(root, "rm", "--quiet", "f.py")
    git(root, "commit", "--quiet", "-m", "d1")
    git(root, "tag", "d1")
    git(root, "checkout", "--quiet", "-b", "other", "d0")
    _commit_files(root, "e1", {"f.py": "v = 2\n"})
    git(root, "tag", "e1")
    git(root, "rm", "--quiet", "f.py")
    git(root, "commit", "--quiet", "-m", "e2")
    git(root, "tag", "e2")
    gone_a = kit.build_plan(root, "d0..d1", "standard", "bugs", None, False)
    _record(kit, root, gone_a, "p1", [_finding("f.py", 1, "weg")])
    gone_b = kit.build_plan(root, "e1..e2", "standard", "bugs", None, False)
    assert gone_b["file_keys"]["f.py"]["key"] == gone_a["file_keys"]["f.py"]["key"]
    assert gone_b["file_keys"]["f.py"]["target_blob"] == gone_a["file_keys"]["f.py"]["target_blob"]
    assert not re.fullmatch(r"[0-9a-f]{40,64}", gone_b["file_keys"]["f.py"]["target_blob"])
    assert gone_b["file_keys"]["f.py"]["base_blob"] == "100644:" + _blob(root, "e1", "f.py")
    assert kit.apply_since(gone_b, [_run_path(root, gone_a)]) == gone_b
    again = kit.build_plan(root, "d0..d1", "standard", "bugs", None, False)
    assert kit.apply_since(again, [_run_path(root, gone_a)])["file_keys"]["f.py"][
        "reused_from"] == gone_a["_meta"]["run"]

    # Ein Submodul bekommt eine Marke mit seinem Commit, kein Blob-SHA.
    root = _fresh_repo(tmp_path / "gitlink")
    sha = _commit_files(root, "g0", {"README.md": "# x\n"})
    git(root, "tag", "g0")
    git(root, "update-index", "--add", "--cacheinfo", f"160000,{sha},vendor/sub")
    git(root, "commit", "--quiet", "-m", "g1")
    linked = kit.build_plan(root, "g0..HEAD", "standard", "bugs", None, False)
    marks = linked["file_keys"]["vendor/sub"]
    assert marks["target_blob"] != marks["base_blob"]
    assert sha in marks["target_blob"] and marks["target_blob"] != sha
    assert not re.fullmatch(r"[0-9a-f]{40,64}", marks["base_blob"])


def test_f2_since_needs_same_profile(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")
    cp = kit.build_plan(root, "base..t1", "checkpoint", "bugs", None, False)
    _record(kit, root, cp, "p1", [_finding("a.py", 5, "cp")])
    std = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    _record(kit, root, std, "p1", [_finding("a.py", 5, "std")])

    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    assert plan_b["file_keys"]["a.py"]["key"] == cp["file_keys"]["a.py"]["key"]
    assert kit.apply_since(plan_b, [_run_path(root, cp)]) == plan_b
    assert kit.apply_since(plan_b, [_run_path(root, cp), _run_path(root, std)])[
        "file_keys"]["a.py"]["reused_from"] == std["_meta"]["run"]
    plan_cp = kit.build_plan(root, "base..t2", "checkpoint", "bugs", None, False)
    assert kit.apply_since(plan_cp, [_run_path(root, std)]) == plan_cp
    assert kit.apply_since(plan_cp, [_run_path(root, std), _run_path(root, cp)])[
        "file_keys"]["a.py"]["reused_from"] == cp["_meta"]["run"]


def test_f3_plan_since_only_on_a_fresh_run(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    _record(kit, root, run_a, "p1", [_finding("a.py", 5, "A")])
    run_c = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    _record(kit, root, run_c, "p1", [_finding("a.py", 5, "C")])
    ids = run_a["_meta"]["run"], run_c["_meta"]["run"]

    def disk(plan):
        return (_run_path(root, plan) / "plan.json").read_bytes()

    # Schon mit --since geplant (mit oder ohne Übernahme): klarer Fehler, Plan bleibt.
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    kit.plan_since(root, plan_b["_meta"]["run"], [ids[0]])
    before = disk(plan_b)
    with pytest.raises(kit.KitError, match="bereits mit --since geplant"):
        kit.plan_since(root, plan_b["_meta"]["run"], list(ids))
    assert disk(plan_b) == before
    plan_n = kit.build_plan(root, "base..t2c", "standard", "bugs", None, False)
    assert kit.plan_since(root, plan_n["_meta"]["run"], [ids[0]])["packets"] == plan_n["packets"]
    with pytest.raises(kit.KitError, match="bereits mit --since geplant"):
        kit.plan_since(root, plan_n["_meta"]["run"], [ids[1]])

    # Artefakte des Laufs: der Fehler nennt sie, auf der Platte ändert sich nichts.
    plan_d = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    run_d = plan_d["_meta"]["run"]
    before = disk(plan_d)
    _record(kit, root, plan_d, "p1", [])
    with pytest.raises(kit.KitError, match=r"results/p1\.json"):
        kit.plan_since(root, run_d, [ids[0]])
    assert disk(plan_d) == before
    assert (_run_path(root, plan_d) / "results" / "p1.json").is_file()
    (_run_path(root, plan_d) / "results" / "p1.json").unlink()
    (_run_path(root, plan_d) / "packets").mkdir()
    (_run_path(root, plan_d) / "packets" / "p1.md").write_text("x\n", encoding="utf-8")
    with pytest.raises(kit.KitError, match=r"packets/p1\.md"):
        kit.plan_since(root, run_d, [ids[0]])
    (_run_path(root, plan_d) / "packets" / "p1.md").unlink()
    git(root, "update-ref", f"refs/deep-review/{run_d}/p1/von", "HEAD")
    with pytest.raises(kit.KitError, match=re.escape(f"refs/deep-review/{run_d}/p1/von")):
        kit.plan_since(root, run_d, [ids[0]])
    assert disk(plan_d) == before
    git(root, "update-ref", "-d", f"refs/deep-review/{run_d}/p1/von")
    assert kit.plan_since(root, run_d, [ids[0]])["file_keys"]["a.py"]["reused_from"] == ids[0]


def test_f4_youngest_run_by_time_then_results_mtime(tmp_path, monkeypatch):
    kit = _kit()
    moment = [dt.datetime(2026, 11, 2, 9, 0, 0, tzinfo=dt.timezone.utc)]
    monkeypatch.setattr(kit, "_now", lambda: moment[0])
    root = _since_repo(tmp_path / "repo")
    first = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    second = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    for plan, name in ((first, "eins"), (second, "zwei")):
        _record(kit, root, plan, "p1", [_finding("a.py", 5, name)])
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    low, high = sorted((first, second), key=lambda p: p["_meta"]["run"])
    assert low["_meta"]["run"][:17] == high["_meta"]["run"][:17]      # dieselbe Sekunde

    def stamp(plan, ns):
        os.utime(_run_path(root, plan) / "results" / "p1.json", ns=(ns, ns))

    dirs = [_run_path(root, first), _run_path(root, second)]
    for later, earlier in ((low, high), (high, low)):
        stamp(later, 2_000_000_000_000_000_000)
        stamp(earlier, 1_000_000_000_000_000_000)
        for order in (dirs, dirs[::-1]):
            assert kit.apply_since(plan_b, order)["file_keys"]["a.py"]["reused_from"] == \
                later["_meta"]["run"]

    # Eine spätere Sekunde schlägt jede Dateizeit.
    moment[0] += dt.timedelta(seconds=1)
    third = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    _record(kit, root, third, "p1", [_finding("a.py", 5, "drei")])
    stamp(third, 1)
    assert kit.apply_since(plan_b, [*dirs, _run_path(root, third)])["file_keys"]["a.py"][
        "reused_from"] == third["_meta"]["run"]


def test_f5_symlink_key_follows_the_real_file(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _fresh_repo(tmp_path / "repo")
    _commit_files(root, "t0", {"lib/real.py": "def f():\n    return 1\n", "README.md": "# x\n"})
    git(root, "tag", "base")
    os.symlink("lib/real.py", root / "a.py")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "t1")
    git(root, "tag", "t1")
    _commit_files(root, "t2", {"lib/real.py": "def f():\n    return 2\n"})
    git(root, "tag", "t2")
    git(root, "rm", "--quiet", "lib/real.py")
    git(root, "commit", "--quiet", "-m", "t3")
    git(root, "tag", "t3")

    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    _record(kit, root, run_a, "p1", [_finding("a.py", 1, "link")])
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    assert plan_b["file_keys"]["a.py"]["key"] != run_a["file_keys"]["a.py"]["key"]
    assert kit.apply_since(plan_b, [_run_path(root, run_a)])["file_keys"]["a.py"][
        "reused_from"] is None
    keys = [kit.file_keys(root, _rev(root, t), ["a.py"], [])["a.py"] for t in ("t1", "t2", "t3")]
    assert len(set(keys)) == 3 and all(re.fullmatch(r"[0-9a-f]{64}", k) for k in keys)


def test_cp5b_f2_symlink_key_follows_through_directory_links(tmp_path, monkeypatch):
    """F2 (Fix-Runde 2): ein Link über einen Ordner-Symlink folgt der echten Datei; ein Link
    auf einen Ordner bekommt eine Marke, ohne dass dessen Inhalt gelistet wird."""
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _fresh_repo(tmp_path / "repo")
    _commit_files(root, "t0", {"src/m.py": "def f():\n    return 1\n", "README.md": "# x\n"})
    git(root, "tag", "base")
    os.symlink("src", root / "lnk")
    os.symlink("lnk/m.py", root / "a.py")
    os.symlink(".", root / "d.py")
    os.symlink("src", root / "e.py")
    os.symlink("lnk/../src/m.py", root / "g.py")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "t1")
    git(root, "tag", "t1")
    _commit_files(root, "t2", {"src/m.py": "def f():\n    return 2\n"})
    git(root, "tag", "t2")

    t1, t2 = _rev(root, "t1"), _rev(root, "t2")
    keys = [kit.file_keys(root, t, ["a.py", "g.py"], []) for t in (t1, t2)]
    assert keys[0]["a.py"] != keys[1]["a.py"]
    assert keys[0]["g.py"] != keys[1]["g.py"]
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    _record(kit, root, run_a, "p1", [_finding("a.py", 1, "link")])
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    assert plan_b["file_keys"]["a.py"]["key"] != run_a["file_keys"]["a.py"]["key"]
    assert kit.apply_since(plan_b, [_run_path(root, run_a)])["file_keys"]["a.py"][
        "reused_from"] is None

    # Ein Link auf einen Ordner (oder die Wurzel): Marke, kein rekursives Listen des Ordners.
    outputs = []
    real = kit._git

    def spy(repo, *args, **kwargs):
        out = real(repo, *args, **kwargs)
        if "ls-tree" in args:
            outputs.append(out)
        return out

    monkeypatch.setattr(kit, "_git", spy)
    dirs = [kit.file_keys(root, t, ["d.py", "e.py"], []) for t in (t1, t2)]
    assert dirs[0] == dirs[1]
    assert not any("src/m.py" in out or "README.md" in out for out in outputs)


def test_cp5b_f3_mode_counts_in_the_coverage_chain(tmp_path, monkeypatch):
    """F3 (Fix-Runde 2): Symlink und reguläre Datei mit denselben Bytes sind nicht derselbe
    Stand an der Basis."""
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _fresh_repo(tmp_path / "repo")
    _commit_files(root, "c0", {"README.md": "# x\n"})
    git(root, "tag", "c0")
    os.symlink("b.py", root / "f.py")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "s0")
    git(root, "tag", "s0")
    (root / "f.py").unlink()
    _commit_files(root, "s1", {"f.py": "v = 1\n"})
    git(root, "tag", "s1")
    git(root, "checkout", "--quiet", "-b", "other", "c0")
    _commit_files(root, "r0", {"f.py": "b.py"})
    git(root, "tag", "r0")
    _commit_files(root, "r1", {"f.py": "v = 1\n"})
    git(root, "tag", "r1")
    assert _blob(root, "s0", "f.py") == _blob(root, "r0", "f.py")      # dieselben Bytes

    run_a = kit.build_plan(root, "s0..s1", "standard", "bugs", None, False)
    _record(kit, root, run_a, "p1", [_finding("f.py", 1, "A")])
    plan_b = kit.build_plan(root, "r0..r1", "standard", "bugs", None, False)
    a_marks, b_marks = run_a["file_keys"]["f.py"], plan_b["file_keys"]["f.py"]
    assert b_marks["key"] == a_marks["key"] and b_marks["target_blob"] == a_marks["target_blob"]
    assert a_marks["base_blob"] == "120000:" + _blob(root, "s0", "f.py")
    assert b_marks["base_blob"] == "100644:" + _blob(root, "r0", "f.py")
    assert b_marks["target_blob"] == "100644:" + _blob(root, "r1", "f.py")
    assert kit.apply_since(plan_b, [_run_path(root, run_a)]) == plan_b
    again = kit.build_plan(root, "s0..s1", "standard", "bugs", None, False)
    assert kit.apply_since(again, [_run_path(root, run_a)])["file_keys"]["f.py"][
        "reused_from"] == run_a["_meta"]["run"]


def test_f6_apply_since_packs_like_build_plan(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")
    calls = []
    real = kit._pack

    def spy(*args):
        calls.append(args)
        return real(*args)

    monkeypatch.setattr(kit, "_pack", spy)
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    assert calls == [({"a.py": 5, "b.py": 6}, "bugs", kit.SPLIT_AT, kit.PACKET_SIZE)]
    _record(kit, root, run_a, "p1", [_finding("a.py", 5, "A")])
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    kit.apply_since(plan_b, [_run_path(root, run_a)])
    assert calls[-1] == ({"b.py": 7}, "bugs", kit.SPLIT_AT, kit.PACKET_SIZE)

    # Eine andere Schnittregel gilt für beide.
    def other(files, focus, split_at, packet_size):
        return [{"id": f"q{i}", "files": [p], "changed_lines": n}
                for i, (p, n) in enumerate(sorted(files.items()), 1)]

    monkeypatch.setattr(kit, "_pack", other)
    plan_c = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    assert [p["id"] for p in plan_c["packets"]] == ["q1", "q2"] and plan_c["split"] is True
    applied = kit.apply_since(plan_c, [_run_path(root, run_a)])
    assert applied["packets"] == [{"id": "q1", "files": ["b.py"], "changed_lines": 7,
                                   "range": None, "reused_from": None}]


def test_f7_malformed_earlier_plan_is_a_kit_error(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    _record(kit, root, run_a, "p1", [_finding("a.py", 5, "A")])
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    path = _run_path(root, run_a) / "plan.json"
    good = path.read_text(encoding="utf-8")
    run = re.escape(run_a["_meta"]["run"])

    def nested(data):
        data["packets"][0]["files"] = [["a.py"], "b.py"]

    def no_lines(data):
        del data["file_keys"]["a.py"]["changed_lines"]

    def bad_blob(data):
        data["file_keys"]["a.py"]["base_blob"] = 5

    def keys_list(data):
        data["file_keys"] = ["a.py"]

    def bad_chain(data):
        data["file_keys"]["a.py"]["reused_chain"] = "x"

    for change, why in ((nested, "files"), (no_lines, "changed_lines"), (bad_blob, "base_blob"),
                        (keys_list, "file_keys"), (bad_chain, "reused_chain")):
        path.write_text(good, encoding="utf-8")
        _rewrite_plan(root, run_a, change)
        with pytest.raises(kit.KitError, match=f"{run}.*{why}|{why}.*{run}"):
            kit.apply_since(plan_b, [_run_path(root, run_a)])
    path.write_text(good, encoding="utf-8")
    assert kit.apply_since(plan_b, [_run_path(root, run_a)])["file_keys"]["a.py"]["reused_from"]


def test_f9_plan_since_returns_what_it_wrote(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    _record(kit, root, run_a, "p1", [_finding("a.py", 5, "A")])
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    loads = []
    real_load, real_write = kit._load_plan, kit._write_plan

    def load(*args):
        loads.append(args)
        return real_load(*args)

    def write(path, plan, notes=None):
        data = real_write(path, plan, notes)
        # Ein gleichzeitiger make_packet_range schreibt gleich danach.
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        on_disk["packets"][0]["range"] = "aaaa..bbbb"
        path.write_text(json.dumps(on_disk), encoding="utf-8")
        return data

    monkeypatch.setattr(kit, "_load_plan", load)
    monkeypatch.setattr(kit, "_write_plan", write)
    done = kit.plan_since(root, plan_b["_meta"]["run"], [run_a["_meta"]["run"]])
    assert len(loads) == 1
    assert done["packets"][0]["range"] is None
    assert done["file_keys"]["a.py"]["reused_from"] == run_a["_meta"]["run"]
    assert done["_meta"]["generated"].endswith(f" --since {run_a['_meta']['run']}")


# --- review_kit.py: record, merge und audit (Task 7) ---------------------------------------

FINDING_KEYS = ["file", "line", "summary", "failure_scenario", "packets", "reused_from", "sources"]
AUDIT_KEYS = ["_meta", "complete", "coverage", "missing", "stale", "lost_findings",
              "report_mismatch"]


def _payload(tmp_path, data, name="funde.json"):
    path = tmp_path / name
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    return path


def _cli(kit, root, command, *args):
    return kit.main([command, "--repo", str(root), *[str(a) for a in args]])


def _cli_record(kit, root, run, packet, payload, tool="/code-review"):
    return _cli(kit, root, "record", "--run", run, "--packet", packet, "--tool", tool, payload)


def _report(directory, run, findings, coverage, claim="vollständig", count=None, header=None,
            extra=()):
    """report.md wie nach assets/report-template.md: Kopfzeile (Bereich, Profil und Fokus aus
    plan.json, Werkzeug /code-review; `header` ersetzt Felder, None lässt eins weg), Funde,
    Abdeckung, die Zeilen `extra`, je Fund eine Zeile `datei:zeile — Zusammenfassung`."""
    plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
    fields = {"skill": "deep-review", "schema": "1",
              "generated": "Hauptagent nach assets/report-template.md", "run": run,
              "range": plan["range"], "profile": plan["profile"], "focus": plan["focus"],
              "tool": "/code-review", **(header or {})}
    head = " | ".join(f"{k}: {v}" for k, v in fields.items() if v is not None)
    lines = [f"<!-- {head} -->",
             "# deep-review", "",
             f"Funde: {len(findings) if count is None else count}",
             f"Abdeckung: {coverage} — {claim}", *extra, ""]
    for f in findings:
        where = f["file"] if f["line"] is None else f"{f['file']}:{f['line']}"
        lines.append(f"- `{where}` — {f['summary']}")
    path = directory / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_record_rejects_unknown_or_duplicate(tmp_path, capsys):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    plan, run = _split_plan(kit, root)
    assert [p["id"] for p in plan["packets"]] == ["p1", "p2"]
    directory = _run_path(root, plan)
    results = directory / "results"
    found = [
        {"file": "./a/x.py", "line": 3, "summary": "Grenze falsch",
         "failure_scenario": "x = 8 → IndexError", "severity": "high"},
        {"file": "b/y.py", "line": "4-6", "summary": "Zeile als Text", "failure_scenario": None},
        {"file": str(root / "a" / "x.py"), "line": None, "summary": "ohne Zeile"},
    ]
    payload = _payload(tmp_path, found)

    # Unbekanntes Paket: Exit 1 mit Meldung, nichts geschrieben — auch kein results/.
    assert _cli_record(kit, root, run, "p9", payload) == 1
    assert "p9" in capsys.readouterr().err
    assert not results.exists()
    with pytest.raises(kit.KitError, match="p9"):
        kit.record(directory, "p9", "/code-review", payload)
    # Kein gültiges Ergebnis: Exit 1, nichts geschrieben.
    broken = ([{"file": "a/x.py", "line": 1}],                           # summary fehlt
              [{"file": "a/x.py", "line": True, "summary": "s"}],         # line ist bool
              [{"file": "a/x.py", "line": -1, "summary": "s"}],
              [{"file": "/nicht/im/repo.py", "line": 1, "summary": "s"}],
              [{"file": "../x.py", "line": 1, "summary": "s"}],
              [{"file": "a/x.py", "line": 1, "summary": "s", "failure_scenario": 3}],
              ["a/x.py:1"], {"kein": "Fund"}, "kein json")
    for i, bad in enumerate(broken):
        assert _cli_record(kit, root, run, "p1", _payload(tmp_path, bad, f"bad{i}.json")) == 1, bad
        assert not results.exists(), bad
    assert _cli_record(kit, root, run, "p1", tmp_path / "fehlt.json") == 1
    assert _cli(kit, root, "record", "--run", "../x", "--packet", "p1", "--tool", "t", payload) == 1
    assert _cli_record(kit, root, run, "p1", payload, tool="") == 1
    assert not results.exists()

    # Eine leere Liste wird angenommen: ein Paket ohne Funde bekommt ein Ergebnis.
    assert _cli_record(kit, root, run, "p2", _payload(tmp_path, [], "leer.json")) == 0
    data = json.loads((results / "p2.json").read_text(encoding="utf-8"))
    assert list(data) == ["_meta", "findings"] and data["findings"] == []
    meta = data["_meta"]
    assert list(meta)[:3] == ["skill", "schema", "generated"]
    assert meta["skill"] == "deep-review" and meta["schema"] == 1
    assert "review_kit.py record --run " + run in meta["generated"]
    assert (meta["run"], meta["packet"], meta["tool"]) == (run, "p2", "/code-review")
    assert re.fullmatch(r"[0-9a-f]{64}", meta["plan"])

    # Ein zweites Ergebnis für dasselbe Paket: Exit 1, die Datei bleibt, wie sie war.
    before = (results / "p2.json").read_bytes()
    assert _cli_record(kit, root, run, "p2", payload) == 1
    assert "p2" in capsys.readouterr().err
    assert (results / "p2.json").read_bytes() == before
    with pytest.raises(kit.KitError, match="schon ein Ergebnis"):
        kit.record(directory, "p2", "/code-review", payload)

    # Felder fest und in fester Reihenfolge, Pfade repo-relativ; fremde Felder fallen weg.
    written = kit.record(directory, "p1", "/code-review", payload)
    expected = [
        {"file": "a/x.py", "line": 3, "summary": "Grenze falsch",
         "failure_scenario": "x = 8 → IndexError"},
        {"file": "b/y.py", "line": "4-6", "summary": "Zeile als Text", "failure_scenario": None},
        {"file": "a/x.py", "line": None, "summary": "ohne Zeile", "failure_scenario": None},
    ]
    assert written["findings"] == expected
    text = (results / "p1.json").read_text(encoding="utf-8")
    assert json.loads(text) == written and "→" in text          # ensure_ascii=False
    assert sorted(p.name for p in results.iterdir()) == ["p1.json", "p2.json"]
    # Das Format, das audit und apply_since annehmen (_read_result, Prüfpunkt 6 F5).
    accepted, why = kit._read_result(results / "p1.json", "p1", run, kit._plan_digest(plan, run), root)
    assert why is None and accepted.findings == expected and accepted.tool == "/code-review"
    # Ein Objekt mit `findings` (die Liste aus dem Brief) geht auch.
    plan2, run2 = _split_plan(kit, root)
    wrapped = _payload(tmp_path, {"findings": found[:1]}, "brief.json")
    assert _cli_record(kit, root, run2, "p1", wrapped, tool="review-brief") == 0
    accepted, why = kit._read_result(_run_path(root, plan2) / "results" / "p1.json", "p1", run2,
                                     kit._plan_digest(plan2, run2), root)
    assert why is None and accepted.findings == expected[:1] and accepted.tool == "review-brief"


def test_record_result_of_another_plan_is_not_reused(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    other = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    kit.record(_run_path(root, other), "p1", "/code-review",
               _payload(tmp_path, [_finding("a.py", 5, "A")]))
    # Das Ergebnis des anderen Laufs, in Lauf A kopiert: nicht angenommen, nichts übernommen.
    (_run_path(root, run_a) / "results").mkdir()
    (_run_path(root, run_a) / "results" / "p1.json").write_bytes(
        (_run_path(root, other) / "results" / "p1.json").read_bytes())
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    assert kit.apply_since(plan_b, [_run_path(root, run_a)]) == plan_b
    applied = kit.apply_since(plan_b, [_run_path(root, other)])
    assert applied["file_keys"]["a.py"]["reused_from"] == other["_meta"]["run"]


def test_merge_keeps_every_finding(tmp_path):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    plan, run = _split_plan(kit, root)
    directory = _run_path(root, plan)
    gap = kit.MERGE_LINE_GAP
    assert gap == 3
    p1 = [_finding("a/x.py", 3, "A"),
          _finding("b/y.py", 2, "Gegenstelle aus p1"),
          _finding("b/y.py", 30, "gleich")]
    p2 = [_finding("b/y.py", 4, "B"),                 # Abstand 2 zu b/y.py:2 → ein Fund
          _finding("b/y.py", 9, "C"),                 # Abstand 5 zu b/y.py:4 → eigener Fund
          _finding("b/y.py", 30, "gleich"),           # derselbe Fund aus zwei Paketen
          _finding("b/y.py", 30 + gap + 4, "fern"),   # Abstand gap + 4 → eigener Fund
          {"file": "a/x.py", "line": None, "summary": "ohne Zeile", "failure_scenario": None},
          {"file": "a/x.py", "line": None, "summary": "ohne Zeile 2", "failure_scenario": None},
          {"file": "b/y.py", "line": "20-22", "summary": "Bereich", "failure_scenario": None},
          _finding("b/y.py", 25, "nach Bereich")]     # Abstand 3 zum Ende von 20-22 → ein Fund
    assert _cli_record(kit, root, run, "p1", _payload(tmp_path, p1, "p1.json")) == 0
    assert _cli_record(kit, root, run, "p2", _payload(tmp_path, p2, "p2.json")) == 0

    assert _cli(kit, root, "merge", "--run", run) == 0
    path = directory / "findings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert list(data) == ["_meta", "findings"]
    meta = data["_meta"]
    assert meta["skill"] == "deep-review" and meta["schema"] == 1 and meta["run"] == run
    assert "review_kit.py merge --run " + run in meta["generated"]
    assert data == kit.merge(directory)                  # zweimal dasselbe
    merged = data["findings"]
    assert all(list(f) == FINDING_KEYS for f in merged)
    short = [(f["file"], f["line"], f["summary"], f["packets"]) for f in merged]
    assert short == [
        ("a/x.py", 3, "A", ["p1"]),
        ("a/x.py", None, "ohne Zeile", ["p2"]),
        ("a/x.py", None, "ohne Zeile 2", ["p2"]),
        ("b/y.py", 2, "Gegenstelle aus p1 | B", ["p1", "p2"]),
        ("b/y.py", 9, "C", ["p2"]),
        ("b/y.py", "20-22", "Bereich | nach Bereich", ["p2"]),
        ("b/y.py", 30, "gleich", ["p1", "p2"]),
        ("b/y.py", 30 + gap + 4, "fern", ["p2"]),
    ]
    two = merged[3]
    assert two["failure_scenario"] == "Gegenstelle aus p1! | B!"
    assert two["reused_from"] is None
    assert two["sources"] == [
        {"packet": "p1", "reused_from": None, "line": 2, "summary": "Gegenstelle aus p1",
         "failure_scenario": "Gegenstelle aus p1!"},
        {"packet": "p2", "reused_from": None, "line": 4, "summary": "B", "failure_scenario": "B!"}]
    assert merged[5]["failure_scenario"] == "nach Bereich!"
    assert len(merged[6]["sources"]) == 2 and merged[6]["failure_scenario"] == "gleich!"
    # Kein Fund verschwindet: jeder Fund aus results/ steht unter sources.
    assert sum(len(f["sources"]) for f in merged) == len(p1) + len(p2)
    # Die Felder, die fix-task liest (Spec 27): file, line, summary, failure_scenario.
    assert all(isinstance(f["file"], str) and f["summary"] for f in merged)


def test_merge_without_results_and_with_reused_findings(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)["_meta"]["run"]
    kit.record(kit.run_dir(root, run_a), "p1", "/code-review",
               _payload(tmp_path, [_finding("a.py", 5, "A"), _finding("b.py", 1, "alt")]))
    # Ohne Ergebnis: merge schreibt eine leere Liste (audit meldet das fehlende Paket).
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    assert kit.merge(_run_path(root, plan_b))["findings"] == []
    shutil.rmtree(_run_path(root, plan_b))
    # Mit --since: die übernommenen Funde aus file_keys kommen mit, Herkunft reused_from.
    assert _cli(kit, root, "plan", "--range", "base..t2", "--since", run_a) == 0
    runs = sorted(p.name for p in (root / ".skills/cache/deep-review").iterdir())
    assert runs[0] == run_a and len(runs) == 2
    directory = kit.run_dir(root, runs[1])
    plan_c = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
    assert plan_c["file_keys"]["a.py"]["reused_from"] == run_a
    assert plan_c["split"] is True and plan_c["range"] is not None
    assert [p["files"] for p in plan_c["packets"]] == [["b.py"]]
    kit.record(directory, "p1", "/code-review",
               _payload(tmp_path, [_finding("b.py", 7, "neu"), _finding("a.py", 6, "über a")], "c.json"))
    merged = kit.merge(directory)["findings"]
    assert [(f["file"], f["line"], f["summary"], f["packets"], f["reused_from"]) for f in merged] == [
        ("a.py", 5, "A | über a", ["p1"], run_a),
        ("b.py", 7, "neu", ["p1"], None)]
    assert merged[0]["sources"][0] == {"packet": None, "reused_from": run_a,
                                       "line": 5, "summary": "A", "failure_scenario": "A!"}


def test_audit(tmp_path, capsys):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    plan, run = _split_plan(kit, root)
    directory = _run_path(root, plan)
    p1 = [_finding("a/x.py", 3, "A")]
    p2 = [_finding("b/y.py", 4, "B"), {"file": "b/y.py", "line": None, "summary": "ohne",
                                       "failure_scenario": None}]

    def run_audit(report=None):
        code = _cli(kit, root, "audit", "--run", run, *(["--report", report] if report else []))
        data = json.loads((directory / "audit.json").read_text(encoding="utf-8"))
        assert list(data) == AUDIT_KEYS and data["_meta"]["run"] == run
        assert data["_meta"]["skill"] == "deep-review" and data["_meta"]["schema"] == 1
        assert "review_kit.py audit --run " + run in data["_meta"]["generated"]
        assert code == (0 if data["complete"] else 1)
        return data

    # Fehlendes Ergebnis: p2 hat keins → missing, complete false; ein ehrlicher Bericht passt.
    assert _cli_record(kit, root, run, "p1", _payload(tmp_path, p1, "p1.json")) == 0
    kit.merge(directory)
    _report(directory, run, p1, "1/2", claim="unvollständig")
    data = run_audit()
    assert data["missing"] == ["p2"] and data["complete"] is False
    assert data["stale"] == [] and data["lost_findings"] == [] and data["report_mismatch"] == []
    # Derselbe Bericht mit „vollständig" trotz Lücke → report_mismatch.
    _report(directory, run, p1, "1/2", claim="vollständig")
    data = run_audit()
    assert data["missing"] == ["p2"]
    assert any("vollständig" in m for m in data["report_mismatch"])

    # Ergebnis eines anderen Plans (anderer Lauf, kopiert) → stale, und das Paket fehlt weiter.
    other, other_run = _split_plan(kit, root)
    assert _cli_record(kit, root, other_run, "p2", _payload(tmp_path, p2, "p2.json")) == 0
    (directory / "results" / "p2.json").write_bytes(
        (_run_path(root, other) / "results" / "p2.json").read_bytes())
    kit.write_json(directory / "results" / "p7.json",
                   {"generated": "test", "packet": "p7", "tool": "t"}, {"findings": []})
    _report(directory, run, p1, "1/2", claim="unvollständig")
    data = run_audit()
    assert data["missing"] == ["p2"] and data["complete"] is False
    assert [s["packet"] for s in data["stale"]] == ["p2", "p7"]
    assert all(list(s) == ["packet", "reason"] and s["reason"] for s in data["stale"])
    assert data["report_mismatch"] == []
    (directory / "results" / "p2.json").unlink()
    (directory / "results" / "p7.json").unlink()

    # Fund fehlt in findings.json (merge lief vor dem zweiten record) → lost_findings.
    assert _cli_record(kit, root, run, "p2", _payload(tmp_path, p2, "p2.json")) == 0
    _report(directory, run, p1, "2/2", claim="unvollständig")
    data = run_audit()
    assert data["missing"] == [] and data["stale"] == [] and data["complete"] is False
    assert data["lost_findings"] == [
        {"file": "b/y.py", "line": 4, "summary": "B", "packet": "p2", "reused_from": None},
        {"file": "b/y.py", "line": None, "summary": "ohne", "packet": "p2", "reused_from": None}]

    # Sauberer Lauf → complete true, Exit 0.
    assert _cli(kit, root, "merge", "--run", run) == 0
    merged = json.loads((directory / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert len(merged) == 3
    clean = _report(directory, run, merged, "2/2")
    data = run_audit()
    assert data["complete"] is True, data
    assert (data["missing"], data["stale"], data["lost_findings"], data["report_mismatch"]) == \
        ([], [], [], [])
    assert data["_meta"]["report"] == f".skills/cache/deep-review/{run}/report.md"
    assert kit.audit(directory, clean)["complete"] is True
    clean_text = clean.read_text(encoding="utf-8")

    # Bericht mit falscher Fundzahl, falscher Abdeckung, fehlendem Fund, fremdem Lauf im Kopf.
    for change, needle in (({"count": 2}, "Funde"),
                           ({"coverage": "1/2"}, "Abdeckung"),
                           ({"findings": merged[:2]}, merged[2]["file"]),
                           ({"run": other_run}, other_run)):
        _report(directory, **{"run": run, "findings": merged, "coverage": "2/2", **change})
        data = run_audit()
        assert data["complete"] is False and data["missing"] == [], change
        assert any(needle in m for m in data["report_mismatch"]), (change, data["report_mismatch"])
    (directory / "report.md").write_text("# kein Kopf\n\nFunde: 3\nAbdeckung: 2/2\n", encoding="utf-8")
    assert any("Kopfzeile" in m for m in run_audit()["report_mismatch"])
    (directory / "report.md").unlink()
    assert any("Bericht" in m for m in run_audit()["report_mismatch"])
    # Ein anderer Pfad über --report.
    elsewhere = tmp_path / "bericht.md"
    elsewhere.write_text(clean_text, encoding="utf-8")
    assert run_audit(elsewhere)["complete"] is True

    # Ein Fund fehlt in findings.json (von Hand entfernt) → lost_findings.
    _report(directory, run, merged[1:], "2/2", claim="unvollständig")
    on_disk = json.loads((directory / "findings.json").read_text(encoding="utf-8"))
    kit.write_json(directory / "findings.json",
                   {k: v for k, v in on_disk["_meta"].items() if k not in ("skill", "schema")},
                   {"findings": merged[1:]})
    data = run_audit()
    assert data["lost_findings"] == [{"file": "a/x.py", "line": 3, "summary": "A", "packet": "p1",
                                      "reused_from": None}]
    assert data["complete"] is False and data["report_mismatch"] == []
    assert _cli(kit, root, "audit", "--run", "2026-01-01-000000-abcdef0-zzzz") == 1
    capsys.readouterr()


def test_audit_counts_reused_findings(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)["_meta"]["run"]
    kit.record(kit.run_dir(root, run_a), "p1", "/code-review",
               _payload(tmp_path, [_finding("a.py", 5, "A")]))
    # B: a.py übernommen, b.py in p1.
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    done_b = kit.plan_since(root, plan_b["_meta"]["run"], [run_a])
    run_b, dir_b = done_b["_meta"]["run"], _run_path(root, done_b)
    kit.record(dir_b, "p1", "/code-review", _payload(tmp_path, [_finding("b.py", 3, "B")], "b.json"))
    on_disk = kit.merge(dir_b)
    merged = on_disk["findings"]
    assert [(f["file"], f["reused_from"], f["packets"]) for f in merged] == [
        ("a.py", run_a, []), ("b.py", None, ["p1"])]
    _report(dir_b, run_b, merged, "1/1")
    assert kit.audit(dir_b, None)["complete"] is True
    # Fehlt der übernommene Fund in der Zahl des Berichts oder in findings.json: Lücke.
    _report(dir_b, run_b, merged[1:], "1/1")
    data = kit.audit(dir_b, None)
    assert data["complete"] is False and any("Funde" in m for m in data["report_mismatch"])
    kit.write_json(dir_b / "findings.json",
                   {k: v for k, v in on_disk["_meta"].items() if k not in ("skill", "schema")},
                   {"findings": merged[1:]})
    data = kit.audit(dir_b, None)
    assert data["lost_findings"] == [{"file": "a.py", "line": 5, "summary": "A", "packet": None,
                                      "reused_from": run_a}]
    assert data["complete"] is False
    assert any("vollständig" in m for m in data["report_mismatch"])     # Bericht sagt es trotzdem

    # C: alles übernommen, packets [] → Abdeckung trivial vollständig.
    plan_c = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    done_c = kit.plan_since(root, plan_c["_meta"]["run"], [run_b])
    assert done_c["packets"] == [] and done_c["split"] is True and done_c["range"] is not None
    dir_c = _run_path(root, done_c)
    merged_c = kit.merge(dir_c)["findings"]
    assert [(f["file"], f["summary"]) for f in merged_c] == [("a.py", "A"), ("b.py", "B")]
    _report(dir_c, done_c["_meta"]["run"], merged_c, "0/0")
    data = kit.audit(dir_c, None)
    assert data["complete"] is True and data["missing"] == [], data


def test_main_subcommands_exit_codes(tmp_path, capsys):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    head = git(root, "rev-parse", "HEAD")
    cache = root / ".skills/cache/deep-review"

    assert _cli(kit, root, "plan", "--range", "base..HEAD", "--split-at", "10") == 0
    out = capsys.readouterr().out
    (run,) = [p.name for p in cache.iterdir()]
    assert run in out and "p2" in out
    plan = json.loads((cache / run / "plan.json").read_text(encoding="utf-8"))
    assert plan["split"] is True and [p["id"] for p in plan["packets"]] == ["p1", "p2"]

    # --since mit unbekanntem oder kaputtem Lauf: Exit 1 und kein halber Lauf bleibt liegen.
    missing = "2026-01-01-000000-abcdef0-zzzz"
    assert _cli(kit, root, "plan", "--range", "base..HEAD", "--since", missing) == 1
    assert missing in capsys.readouterr().err
    assert [p.name for p in cache.iterdir()] == [run]
    assert _cli(kit, root, "plan", "--range", "base..HEAD", "--since", "kaputt") == 1
    assert [p.name for p in cache.iterdir()] == [run]
    # --since auf einen Lauf, der schon Ergebnisse hat, ist erlaubt; scheitert plan_since erst
    # nach build_plan (hier: der frühere Plan ist kaputt), bleibt kein neuer Lauf liegen.
    broken = cache / missing
    broken.mkdir()
    (broken / "plan.json").write_text("{kaputt", encoding="utf-8")
    assert _cli(kit, root, "plan", "--range", "base..HEAD", "--since", missing) == 1
    assert sorted(p.name for p in cache.iterdir()) == sorted([run, missing])
    shutil.rmtree(broken)
    # --soll-file: muss es geben; steht in _meta.
    assert _cli(kit, root, "plan", "--soll-file", tmp_path / "fehlt.md") == 1
    assert [p.name for p in cache.iterdir()] == [run]
    soll = root / "soll.md"
    soll.write_text("# Soll\n", encoding="utf-8")
    assert _cli(kit, root, "plan", "--range", "base..HEAD", "--profile", "checkpoint",
                "--soll-file", soll) == 0
    capsys.readouterr()
    (second,) = [p.name for p in cache.iterdir() if p.name != run]
    meta = json.loads((cache / second / "plan.json").read_text(encoding="utf-8"))["_meta"]
    assert meta["soll_file"] == "soll.md" and "--soll-file soll.md" in meta["generated"]
    assert _cli(kit, root, "plan", "--profile", "checkpoint", "--focus", "security") == 1
    assert _cli(kit, root, "plan", "--range", "gibtsnicht..HEAD") == 1
    assert len(list(cache.iterdir())) == 2

    # counterparts baut Paketblöcke und Hilfscommits; cleanup räumt sie weg.
    assert _cli(kit, root, "counterparts", "--run", run) == 0
    assert sorted(p.name for p in (cache / run / "packets").iterdir()) == ["p1.md", "p2.md"]
    assert git(root, "for-each-ref", "refs/deep-review/") != ""
    capsys.readouterr()
    assert _cli(kit, root, "cleanup", "--run", run) == 0
    assert git(root, "for-each-ref", "refs/deep-review/") == ""
    assert _cli(kit, root, "cleanup", "--stale") == 0
    assert _cli(kit, root, "cleanup") == 1
    assert _cli(kit, root, "counterparts", "--run", missing) == 1
    assert _cli(kit, root, "merge", "--run", missing) == 1
    assert git(root, "rev-parse", "HEAD") == head
    assert git(root, "status", "--porcelain", "--untracked-files=no") == ""

    # Falscher Aufruf: argparse, Exit 2.
    with pytest.raises(SystemExit) as stop:
        kit.main(["gibtsnicht"])
    assert stop.value.code == 2
    # Als Skript: python review_kit.py … mit demselben Exit.
    done = subprocess.run([sys.executable, str(REPO_ROOT / KIT_PATH), "merge", "--repo", str(root),
                           "--run", missing], capture_output=True, text=True)
    assert done.returncode == 1 and missing in done.stderr


# --- Prüfpunkt 6: Funde F1–F16 zu record, merge und audit -----------------------------------

def _single_run(kit, tmp_path, after, name="repo"):
    """Repo mit zwei Commits (die Dateien aus `after` erst leer, dann mit Inhalt) und ein Lauf
    über base..HEAD mit einem Paket p1 (`split: false`, der Anti-Zeremonie-Fall)."""
    root = tmp_path / name
    root.mkdir()
    _commit_repo(root, {rel: "" for rel in after}, after)
    plan = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    assert [p["id"] for p in plan["packets"]] == ["p1"] and plan["split"] is False
    return root, plan, plan["_meta"]["run"], _run_path(root, plan)


def test_cp6_f01_line_normalised_and_paths_with_spaces(tmp_path, capsys):
    kit = _kit()
    for raw, want in (("12-14", "12-14"), ("12 - 14", "12-14"), ("L12-L14", "12-14"),
                      ("12 bis 14", "12-14"), ("L12 bis L14", "12-14"), ("12–14", "12-14"),
                      ("14-12", "12-14"), ("3-3", 3), ("7", 7), ("L7", 7), (" 9 ", 9), (5, 5),
                      (0, 0), ("", None), ("  ", None), (None, None)):
        got = kit._clean_finding({"file": "a.py", "line": raw, "summary": "s"}, 1, tmp_path)
        assert got["line"] == want, raw
    for bad in ("irgendwo", "12, 40", "12-", "Zeile 12", "12-14-16", "L"):
        with pytest.raises(kit.KitError, match="Fund 2"):
            kit._clean_finding({"file": "a.py", "line": bad, "summary": "s"}, 2, tmp_path)

    root, plan, run, directory = _single_run(kit, tmp_path, {"src/my module.py": _lines(5),
                                                              "a.py": _lines(30)})
    bad = _payload(tmp_path, [{"file": "a.py", "line": "irgendwo", "summary": "s"}], "bad.json")
    assert _cli_record(kit, root, run, "p1", bad) == 1
    assert "irgendwo" in capsys.readouterr().err
    assert not (directory / "results").exists()
    found = [{"file": "src/my module.py", "line": 3, "summary": "Leerzeichen im Pfad"},
             {"file": "a.py", "line": "12 - 14", "summary": "Bereich"}]
    assert _cli_record(kit, root, run, "p1", _payload(tmp_path, found)) == 0
    stored = json.loads((directory / "results" / "p1.json").read_text(encoding="utf-8"))
    assert [f["line"] for f in stored["findings"]] == [3, "12-14"]
    merged = kit.merge(directory)["findings"]
    report = _report(directory, run, merged, "1/1")
    text = report.read_text(encoding="utf-8")
    assert "- `src/my module.py:3` — Leerzeichen im Pfad" in text and "- `a.py:12-14` — " in text
    data = kit.audit(directory, None)
    assert data["report_mismatch"] == [] and data["complete"] is True, data
    # Fehlt die Zeile mit dem Pfad mit Leerzeichen, meldet audit sie.
    _report(directory, run, merged[:1], "1/1", count=2)
    assert any("src/my module.py:3" in m for m in kit.audit(directory, None)["report_mismatch"])


def test_cp6_f02_cli_output_and_stdin_are_utf8_safe(tmp_path, monkeypatch):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    plan, run = _split_plan(kit, root)
    directory = _run_path(root, plan)

    def stream(data=b""):
        return io.TextIOWrapper(io.BytesIO(data), encoding="cp1252")

    out, err = stream(), stream()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    # stdout in cp1252: record schreibt das Ergebnis und endet mit 0, ohne UnicodeEncodeError.
    assert _cli_record(kit, root, run, "p1", _payload(tmp_path, [_finding("a/x.py", 3, "A")])) == 0
    assert (directory / "results" / "p1.json").is_file()
    out.flush()
    assert "p1.json" in out.buffer.getvalue().decode("utf-8", errors="replace")

    # stdin wird als UTF-8 gelesen, nicht in der Kodierung des Systems.
    text = json.dumps([{"file": "b/y.py", "line": 2, "summary": "Lösung"}], ensure_ascii=False)
    monkeypatch.setattr(sys, "stdin", stream(text.encode("utf-8")))
    assert _cli_record(kit, root, run, "p2", "-") == 0
    stored = json.loads((directory / "results" / "p2.json").read_text(encoding="utf-8"))
    assert stored["findings"][0]["summary"] == "Lösung"

    # Kein UTF-8 auf stdin: Exit 1 mit Meldung, kein Traceback, nichts geschrieben.
    plan2, run2 = _split_plan(kit, root)
    monkeypatch.setattr(sys, "stdin", stream(b'[{"file": "a/x.py", "line": 1, "summary": "\xff"}]'))
    assert _cli_record(kit, root, run2, "p1", "-") == 1
    err.flush()
    message = err.buffer.getvalue().decode("utf-8", errors="replace")
    assert "UTF-8" in message and "Traceback" not in message
    assert not (_run_path(root, plan2) / "results").exists()


def test_cp6_f03_report_with_a_bom_passes_the_header_check(tmp_path):
    kit = _kit()
    root, plan, run, directory = _single_run(kit, tmp_path, {"a.py": _lines(5)})
    kit.record(directory, "p1", "/code-review", _payload(tmp_path, []))
    kit.merge(directory)
    report = _report(directory, run, [], "1/1")
    report.write_text("﻿" + report.read_text(encoding="utf-8"), encoding="utf-8")
    data = kit.audit(directory, None)
    assert data["report_mismatch"] == [] and data["complete"] is True, data


def test_cp6_f04_since_keeps_findings_outside_the_packet_files(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    id_a = run_a["_meta"]["run"]
    assert [p["files"] for p in run_a["packets"]] == [["a.py", "b.py"]]
    outside = _finding("c.py", 3, "Gegenstelle wirft")          # c.py steht in keinem Paket
    _record(kit, root, run_a, "p1", [_finding("a.py", 5, "A"), outside])

    # Alle Dateien von p1 übernommen: der Fund zu c.py kommt mit, am ersten Eintrag (a.py).
    again = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    done = kit.plan_since(root, again["_meta"]["run"], [id_a])
    assert done["packets"] == []
    assert done["file_keys"]["a.py"]["findings"] == [_finding("a.py", 5, "A"), outside]
    assert done["file_keys"]["b.py"]["findings"] == []
    merged = kit.merge(_run_path(root, done))["findings"]
    assert [(f["file"], f["line"], f["reused_from"]) for f in merged] == [
        ("a.py", 5, id_a), ("c.py", 3, id_a)]
    # Ein Lauf, der den Fund von A übernommen hat, gibt ihn weiter.
    third = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    chained = kit.apply_since(third, [_run_path(root, done)])
    assert outside in chained["file_keys"]["a.py"]["findings"]

    # Nur a.py übernommen (b.py hat sich geändert): der Fund zu c.py nicht; b.py neu reviewt.
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    applied = kit.apply_since(plan_b, [_run_path(root, run_a)])
    assert applied["file_keys"]["a.py"]["reused_from"] == id_a
    assert applied["file_keys"]["a.py"]["findings"] == [_finding("a.py", 5, "A")]
    assert [p["files"] for p in applied["packets"]] == [["b.py"]]


def test_cp6_f05_since_accepts_results_like_audit(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    plan_b = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    directory = _run_path(root, run_a)
    _record(kit, root, run_a, "p1", [_finding("a.py", 5, "A")])
    result = directory / "results" / "p1.json"
    good = result.read_text(encoding="utf-8")
    assert kit.apply_since(plan_b, [directory])["file_keys"]["a.py"]["reused_from"] == \
        run_a["_meta"]["run"]

    def without_meta(data):
        del data["_meta"]

    def without_run(data):
        del data["_meta"]["run"]

    def without_plan(data):
        del data["_meta"]["plan"]

    def negative_line(data):
        data["findings"][0]["line"] = -1

    for change in (without_meta, without_run, without_plan, negative_line):
        data = json.loads(good)
        change(data)
        result.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        assert kit.apply_since(plan_b, [directory]) == plan_b, change.__name__
        # audit nimmt dasselbe Ergebnis auch nicht an.
        assert kit.audit(directory, None)["missing"] == ["p1"], change.__name__
    assert not hasattr(kit, "_result_findings")

    # _plan_digest einmal je früherem Plan, nicht je Paket.
    (tmp_path / "zwei").mkdir()
    root2 = _two_packet_repo(tmp_path / "zwei")
    first, _run = _split_plan(kit, root2)
    for pid in ("p1", "p2"):
        kit.record(_run_path(root2, first), pid, "/code-review",
                   _payload(tmp_path, [], f"{pid}.json"))
    second, _run = _split_plan(kit, root2)
    calls = []
    real = kit._plan_digest
    monkeypatch.setattr(kit, "_plan_digest", lambda *a: calls.append(a) or real(*a))
    assert kit.apply_since(second, [_run_path(root2, first)])["packets"] == []
    assert len(calls) == 1


def test_cp6_f06_cli_paths_are_resolved_against_the_cwd(tmp_path, monkeypatch):
    kit = _kit()
    work = tmp_path / "work"
    (work / "proj").mkdir(parents=True)
    root = _commit_repo(work / "proj", {"a.py": ""}, {"a.py": _lines(5)})
    (work / "specs").mkdir()
    (work / "specs" / "s.md").write_text("# Soll\n", encoding="utf-8")
    (work / "other").mkdir()
    monkeypatch.chdir(work / "other")
    assert kit.main(["plan", "--repo", str(root), "--profile", "checkpoint",
                     "--soll-file", "../specs/s.md"]) == 0
    (run,) = [p.name for p in (root / ".skills/cache/deep-review").iterdir()]
    directory = kit.run_dir(root, run)
    meta = json.loads((directory / "plan.json").read_text(encoding="utf-8"))["_meta"]
    assert meta["soll_file"] == str(work / "specs" / "s.md")
    assert meta["generated"].endswith(f"--soll-file {work / 'specs' / 's.md'}")

    # audit --report report.md aus /work: gelesen wird /work/report.md, _meta.report absolut.
    kit.record(directory, "p1", "/code-review", _payload(tmp_path, []))
    kit.merge(directory)
    _report(directory, run, [], "1/1").replace(work / "report.md")
    monkeypatch.chdir(work)
    assert kit.main(["audit", "--repo", str(root), "--run", run, "--report", "report.md"]) == 0
    data = json.loads((directory / "audit.json").read_text(encoding="utf-8"))
    assert data["_meta"]["report"] == str(work / "report.md")
    assert data["_meta"]["generated"].endswith(f"--report {work / 'report.md'}")
    assert data["complete"] is True, data


def test_cp6_f07_merge_groups_do_not_chain():
    kit = _kit()

    def groups(*lines):
        sources = [kit._Source(_finding("a.py", n, f"L{n}"), "p1", None) for n in lines]
        return [[s["line"] for s in f["sources"]] for f in kit._merge_sources(sources, {"p1": 0})]

    assert groups(10, 12) == [[10, 12]]
    assert groups(10, 13, 16) == [[10, 13], [16]]
    assert groups(16, 13, 10) == [[10, 13], [16]]
    assert groups(10, 15) == [[10], [15]]
    assert groups(10, 11, 12, 13, 14) == [[10, 11, 12, 13], [14]]
    assert groups("20-22", 25, 26) == [["20-22", 25], [26]]     # Abstand vom Ende des ersten


def test_cp6_f08_claim_is_the_whole_word_and_not_negated(tmp_path):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    plan, run = _split_plan(kit, root)
    directory = _run_path(root, plan)
    kit.record(directory, "p1", "/code-review",
               _payload(tmp_path, [_finding("a/x.py", 3, "vollständige Validierung fehlt")]))
    merged = kit.merge(directory)["findings"]
    extra = ["Die Vollständigkeit ist nicht gegeben.", "Der Lauf ist nicht mehr vollständig.",
             "Das Review ist nicht", "vollständig, p2 fehlt.", "Auch nicht  mehr\tvollständig.",
             "Unvollständig, wie gesagt."]
    _report(directory, run, merged, "1/2", claim="unvollständig", extra=extra)
    data = kit.audit(directory, None)
    assert data["missing"] == ["p2"] and data["report_mismatch"] == [], data
    _report(directory, run, merged, "1/2", claim="vollständig")
    assert any("vollständig" in m for m in kit.audit(directory, None)["report_mismatch"])
    _report(directory, run, merged, "1/2", claim="unvollständig", extra=["Alles ist vollständig."])
    assert any("vollständig" in m for m in kit.audit(directory, None)["report_mismatch"])


def test_cp6_f09_header_names_range_profile_focus_and_tool(tmp_path):
    kit = _kit()
    root, plan, run, directory = _single_run(kit, tmp_path, {"a.py": _lines(5)})
    kit.record(directory, "p1", "/code-review", _payload(tmp_path, []))
    kit.merge(directory)
    _report(directory, run, [], "1/1")
    assert kit.audit(directory, None)["report_mismatch"] == []
    for fields, needle in (({"range": None}, "range"), ({"tool": None}, "tool"),
                           ({"tool": ""}, "tool"), ({"profile": None}, "profile"),
                           ({"focus": None}, "focus"), ({"focus": "security"}, "focus"),
                           ({"range": "base..HEAD"}, "range"),
                           ({"tool": "/security-review"}, "tool")):
        _report(directory, run, [], "1/1", header=fields)
        mismatch = kit.audit(directory, None)["report_mismatch"]
        assert any(needle in m for m in mismatch), (fields, mismatch)


def test_cp6_f10_bad_reused_finding_is_a_kit_error(tmp_path, monkeypatch, capsys):
    kit = _kit()
    _tick(kit, monkeypatch)
    root, plan, run, directory = _single_run(kit, tmp_path, {"a.py": _lines(5)})

    def bad(data):
        data["file_keys"]["a.py"].update(reused_from="2026-01-01-000000-abcdef0-zzzz",
                                         findings=[{"summary": "x"}])

    _rewrite_plan(root, plan, bad)
    for command in ("merge", "audit"):
        assert _cli(kit, root, command, "--run", run) == 1, command
        err = capsys.readouterr().err
        assert run in err and "a.py" in err and "Traceback" not in err, err
    # Derselbe Plan als früherer Lauf (--since): derselbe KitError.
    later = kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    with pytest.raises(kit.KitError, match=re.escape(run)):
        kit.apply_since(later, [directory])


def test_cp6_f11_backslash_paths_are_posix(tmp_path):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    plan, run = _split_plan(kit, root)
    directory = _run_path(root, plan)
    assert kit._clean_finding({"file": ".\\a\\x.py", "summary": "s"}, 1, root)["file"] == "a/x.py"
    with pytest.raises(kit.KitError, match="kein Pfad im Repo"):
        kit._clean_finding({"file": "..\\x.py", "summary": "s"}, 1, root)
    kit.record(directory, "p1", "/code-review",
               _payload(tmp_path, [_finding("a\\x.py", 3, "A")], "1.json"))
    kit.record(directory, "p2", "/code-review",
               _payload(tmp_path, [_finding("a/x.py", 4, "B")], "2.json"))
    merged = kit.merge(directory)["findings"]
    assert [(f["file"], f["line"], f["packets"]) for f in merged] == [("a/x.py", 3, ["p1", "p2"])]


def test_cp6_f12_own_and_earlier_plans_share_one_check(tmp_path, monkeypatch):
    kit = _kit()
    _tick(kit, monkeypatch)
    root = _since_repo(tmp_path / "repo")
    run_a = kit.build_plan(root, "base..t1", "standard", "bugs", None, False)
    _record(kit, root, run_a, "p1", [_finding("a.py", 5, "A")])
    plan_b = kit.build_plan(root, "base..t2", "standard", "bugs", None, False)
    seen = []
    real = kit._checked_plan
    monkeypatch.setattr(kit, "_checked_plan", lambda d, r: seen.append(r) or real(d, r))
    kit.apply_since(plan_b, [_run_path(root, run_a)])
    kit.merge(_run_path(root, plan_b))
    kit.audit(_run_path(root, plan_b), None)
    assert seen == [run_a["_meta"]["run"], plan_b["_meta"]["run"], plan_b["_meta"]["run"]]


def test_cp6_f13_line_spans_parsed_once(monkeypatch):
    kit = _kit()
    calls = []
    real = kit._line_span
    monkeypatch.setattr(kit, "_line_span", lambda line: calls.append(line) or real(line))
    sources = [kit._Source(_finding("a.py", line, "s"), "p1", None) for line in (3, "5-6", None, 30)]
    merged = kit._merge_sources(sources, {"p1": 0})
    assert [f["line"] for f in merged] == [3, 30, None]
    assert len(calls) == len(sources)


def test_cp6_f14_cli_prints_what_audit_and_counterparts_return(tmp_path, monkeypatch, capsys):
    kit = _kit()
    root = _two_packet_repo(tmp_path)
    plan, run = _split_plan(kit, root)
    directory = _run_path(root, plan)
    callers = []
    real = kit._load_plan

    def spy(*args):
        callers.append(sys._getframe(1).f_code.co_name)
        return real(*args)

    monkeypatch.setattr(kit, "_load_plan", spy)
    assert _cli(kit, root, "counterparts", "--run", run) == 0
    out = capsys.readouterr().out
    on_disk = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
    ranges = [p["range"] for p in on_disk["packets"]]
    assert all(ranges)
    for packet in on_disk["packets"]:
        assert f"{packet['id']}: {packet['range']} · " in out
    assert [w["range"] for w in kit.write_counterparts(root, run)] == ranges

    kit.record(directory, "p1", "/code-review", _payload(tmp_path, []))
    kit.merge(directory)
    assert _cli(kit, root, "audit", "--run", run) == 1
    out = capsys.readouterr().out
    data = json.loads((directory / "audit.json").read_text(encoding="utf-8"))
    assert data["coverage"] == {"covered": 1, "total": 2}
    assert "Abdeckung: 1/2" in out
    assert not {"_cmd_counterparts", "_cmd_audit"} & set(callers), callers


def test_cp6_f15_run_path_parameter_and_report_length(tmp_path):
    kit = _kit()
    for fn, arity in ((kit.record, 4), (kit.merge, 1), (kit.audit, 2)):
        params = list(inspect.signature(fn).parameters)
        assert params[0] == "run_path" and len(params) == arity, (fn.__name__, params)
    root, plan, run, directory = _single_run(kit, tmp_path, {"a.py": _lines(40)})
    kit.record(directory, "p1", "/code-review",
               _payload(tmp_path, [_finding("a.py", n, f"F{n}") for n in (3, 13, 23)]))
    merged = kit.merge(directory)["findings"]
    assert len(merged) == 3
    base = len(_report(directory, run, merged, "1/1").read_text(encoding="utf-8").splitlines())
    for total, ok in ((24, True), (30, False)):
        report = _report(directory, run, merged, "1/1",
                         extra=[f"Zeile {i}" for i in range(total - base)])
        assert len(report.read_text(encoding="utf-8").splitlines()) == total
        mismatch = kit.audit(directory, None)["report_mismatch"]
        if ok:
            assert mismatch == [], mismatch
        else:
            assert any("30" in m and "24" in m for m in mismatch), mismatch
    # Mit mehreren Paketen (split: true) gilt die Grenze des Anti-Zeremonie-Falls nicht.
    (tmp_path / "zwei").mkdir()
    root2 = _two_packet_repo(tmp_path / "zwei")
    plan2, run2 = _split_plan(kit, root2)
    dir2 = _run_path(root2, plan2)
    for pid in ("p1", "p2"):
        kit.record(dir2, pid, "/code-review", _payload(tmp_path, [], f"{pid}.json"))
    kit.merge(dir2)
    _report(dir2, run2, [], "2/2", extra=[f"Zeile {i}" for i in range(40)])
    assert kit.audit(dir2, None)["report_mismatch"] == []
