"""deep-review (Spec 26): Messfixtures und review_kit.py.

`dr-seeded` trägt fünf eingebaute Fehler, `dr-seeded-clean` ist dieselbe Fixture ohne sie.
Beide bauen denselben Bereich `base..HEAD`; die Trefferquote misst der Report daran. Jeder
Fehler hängt an einer Stelle in `base`, die der Diff nicht berührt."""

import datetime as dt
import difflib
import hashlib
import inspect
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
