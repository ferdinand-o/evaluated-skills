"""deep-review (Spec 26): Messfixtures und review_kit.py.

`dr-seeded` trägt fünf eingebaute Fehler, `dr-seeded-clean` ist dieselbe Fixture ohne sie.
Beide bauen denselben Bereich `base..HEAD`; die Trefferquote misst der Report daran. Jeder
Fehler hängt an einer Stelle in `base`, die der Diff nicht berührt."""

import datetime as dt
import difflib
import json
import os
import re
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
PLAN_KEYS = ["_meta", "range", "base", "profile", "focus", "split", "split_at", "packet_size",
             "changed_lines", "packets", "file_keys", "not_reviewed"]
PACKET_KEYS = ["id", "files", "changed_lines", "range", "reused_from"]


def _kit():
    # Erst im Test laden: fehlt das Skript, scheitern nur die Tests, die es brauchen.
    return load_script(KIT_PATH)


def _lines(n, tag="x"):
    return "".join(f"{tag}_{i} = {i}\n" for i in range(n))


def _commit_repo(root, before, after):
    """Repo mit zwei Commits, Tag `base` auf dem ersten. Ein Wert None löscht die Datei."""
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
    root = _commit_repo(tmp_path, {"app/a.py": ""}, {"app/a.py": _lines(2), name: _lines(3)})
    with pytest.raises(kit.KitError, match="UTF-8"):
        kit.build_plan(root, "base..HEAD", "standard", "bugs", None, False)
    assert _runs(root) == []
    # Auch der Schreiber selbst: KitError, keine Temp-Datei.
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
    assert (stat.base, stat.merge_base, stat.target) == (_rev(root, "base"), _rev(root, "base"),
                                                         _rev(root, "HEAD"))


def test_f04_test_files_case_insensitive():
    kit = _kit()
    for path in ("UnitTests/FooTests.pas", "Tests/FooTest.py", "pkg/Test_foo.py",
                 "pkg/foo_TEST.py", "src/testfoo.pas", "src/FooTEST.pas"):
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
    assert plan["range"] == f"{empty}..{head}" and plan["base"] == empty


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
    assert stat.merge_base == fork and stat.base == _rev(root, "main")
    plan = kit.build_plan(root, "main..feature", "standard", "bugs", None, False)
    assert plan["changed_lines"] == 5
    assert plan["range"] == f"{fork}..{_rev(root, 'feature')}"
    assert plan["base"] == _rev(root, "main")


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
    cest, cet = dt.timezone(dt.timedelta(hours=2)), dt.timezone(dt.timedelta(hours=1))
    # Zeitumstellung 2026-10-25: 02:30 Sommerzeit liegt vor 02:10 Winterzeit.
    monkeypatch.setattr(kit, "_now", lambda: dt.datetime(2026, 10, 25, 2, 30, tzinfo=cest))
    first = kit.new_run_id(sha)
    monkeypatch.setattr(kit, "_now", lambda: dt.datetime(2026, 10, 25, 2, 10, tzinfo=cet))
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
