"""Tests für skills/reddit-research/scripts/rr.py (select, remap, tally)."""

import json
import math

import pytest
from conftest import load_script

rr = load_script("skills/reddit-research/scripts/rr.py")


def write_jsonl(path, rows, tail=""):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows) + tail, encoding="utf-8")


def tag(thread, n, cats, *, author="u1", ts=1_730_000_000, relevant=True, **extra):
    row = {"item_id": f"t1_{thread}_{n}", "thread_id": f"t3_{thread}", "subreddit": "A", "author": author,
           "created_utc": ts, "kind": "comment", "relevant": relevant, "categories": cats}
    row.update(extra)
    return row


def run(args, capsys):
    rr.sys.argv = ["rr.py", *map(str, args)]
    rr.main()
    return capsys.readouterr()


# --- wilson ---------------------------------------------------------------------

def test_wilson_bounds():
    assert rr.wilson(0, 0) == (0.0, 0.0)
    lo, hi = rr.wilson(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)
    assert rr.wilson(10, 10)[1] == 1.0 and rr.wilson(0, 10)[0] == 0.0


def test_period_of():
    assert rr.period_of(1_730_000_000, "quarter") == "2024-Q4"
    assert rr.period_of(1_730_000_000, "half") == "2024-H2"
    assert rr.period_of("kein Datum", "month") == "unknown"


# --- select ---------------------------------------------------------------------

def test_select_dedupes_prefix_filters_and_spreads(tmp_path, capsys):
    rows = [{"id": f"t3_p{i}", "subreddit": "A", "num_comments": 10 + i, "score": i,
             "created_utc": 1_730_000_000 + i * 8_000_000, "selftext_length": 50} for i in range(8)]
    rows.append({"id": "p1", "subreddit": "A", "num_comments": 99, "created_utc": 1, "selftext_length": 5})  # Duplikat
    rows.append({"id": "low", "subreddit": "A", "num_comments": 1, "created_utc": 1, "selftext_length": 5})
    rows.append({"id": "img", "subreddit": "A", "num_comments": 50, "created_utc": 1, "selftext_length": 0})
    write_jsonl(tmp_path / "c.jsonl", rows, tail="{kaputt\n")
    out = tmp_path / "b"
    res = run(["select", tmp_path / "c.jsonl", "--out", out, "--text-only", "--per-subreddit", "4",
               "--batch-size", "3"], capsys)
    assert "invalid lines: 1" in res.out
    batches = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out.glob("batch_*.json"))]
    ids = [t["id"] for b in batches for t in b["threads"]]
    assert len(ids) == 4 == len(set(ids))
    assert all(not i.startswith("t3_") for i in ids)
    assert "low" not in ids and "img" not in ids
    assert [len(b["threads"]) for b in batches] == [3, 1]


def test_select_warns_about_stale_batches(tmp_path, capsys):
    out = tmp_path / "b"
    out.mkdir()
    (out / "batch_009.json").write_text("{}", encoding="utf-8")
    write_jsonl(tmp_path / "c.jsonl", [{"id": "x", "subreddit": "A", "num_comments": 9, "created_utc": 1,
                                         "selftext_length": 5}])
    res = run(["select", tmp_path / "c.jsonl", "--out", out], capsys)
    assert "WARNUNG" in res.err and (out / "batch_009.json").exists()


# --- remap ----------------------------------------------------------------------

def test_remap_moves_other_and_survives_truncated_line(tmp_path, capsys):
    rows = [tag("a", 1, ["OTHER"], other_label=" Foo "), tag("a", 2, ["C01"], advice="None"),
            tag("a", 3, ["OTHER"], other_label="Bar")]
    write_jsonl(tmp_path / "b1.jsonl", rows, tail='{"item_id": "t1_cut", "thr\n')
    (tmp_path / "map.json").write_text(json.dumps({"C02": ["foo"]}), encoding="utf-8")
    res = run(["remap", tmp_path / "*.jsonl", "--map", tmp_path / "map.json", "--out", tmp_path / "f"], capsys)
    assert "remapped items: 1" in res.out and "invalid lines skipped: 1" in res.out
    out = [json.loads(line) for line in (tmp_path / "f" / "b1.jsonl").read_text(encoding="utf-8").splitlines()]
    assert out[0]["categories"] == ["C02"] and out[0]["remapped_from_other"] == " Foo "
    assert out[1]["advice"] is None
    assert out[2]["categories"] == ["OTHER"]
    assert (tmp_path / "b1.jsonl").read_text(encoding="utf-8").count("Foo") == 1, "Original bleibt unberührt"


# --- tally ----------------------------------------------------------------------

def test_tally_counts_threads_not_items(tmp_path, capsys):
    rows = [tag("a", i, ["C01"]) for i in range(5)]                      # ein Thread, fünf Treffer
    rows += [tag("b", 1, ["C02"], author="u2"), tag("c", 1, ["C01", "C02"], author="u3"),
             tag("d", 1, [], relevant=False), tag("d", 2, ["C01"], relevant=False)]
    rows.append(rows[0])                                                  # doppelte item_id
    write_jsonl(tmp_path / "t.jsonl", rows, tail="{kaputt\n")
    (tmp_path / "cb.json").write_text(json.dumps({"categories": [{"id": "C01", "label": "Eins"},
                                                                  {"id": "C02", "label": "Zwei"}]}), encoding="utf-8")
    run(["tally", tmp_path / "t.jsonl", "--codebook", tmp_path / "cb.json", "--out-json", tmp_path / "r.json"], capsys)
    res = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert res["n_units"] == 3 and res["items_relevant"] == 7 and res["invalid_lines"] == 1
    shares = {c["category"]: c for c in res["categories"]}
    assert shares["C01"]["units"] == 2 and shares["C02"]["units"] == 2
    assert shares["C01"]["share"] == pytest.approx(2 / 3)
    assert math.isclose(shares["C01"]["ci95"][0], rr.wilson(2, 3)[0])
    assert res["unknown_categories"] == []


def test_tally_flags_category_missing_from_codebook(tmp_path, capsys):
    write_jsonl(tmp_path / "t.jsonl", [tag("a", 1, ["C99"])])
    (tmp_path / "cb.json").write_text(json.dumps({"categories": [{"id": "C01"}]}), encoding="utf-8")
    res = run(["tally", tmp_path / "t.jsonl", "--codebook", tmp_path / "cb.json"], capsys)
    assert "WARNUNG" in res.out and "C99" in res.out


def test_tally_thread_period_is_the_posts_period(tmp_path, capsys):
    q4, q1 = 1_730_000_000, 1_740_000_000   # 2024-Q4, 2025-Q1
    rows = [tag("a", 0, ["C01"], ts=q4), tag("a", 1, ["C01"], ts=q1)]   # Kommentar ein Quartal später
    write_jsonl(tmp_path / "t.jsonl", rows)
    res = run(["tally", tmp_path / "t.jsonl", "--by", "period", "--period", "quarter"], capsys)
    assert "2024-Q4 | 1" in res.out and "2025-Q1" not in res.out


def test_tally_author_unit_ignores_deleted(tmp_path, capsys):
    rows = [tag("a", 1, ["C01"], author="u1"), tag("b", 1, ["C01"], author="[deleted]"),
            tag("c", 1, ["C01"], author="u1")]
    write_jsonl(tmp_path / "t.jsonl", rows)
    run(["tally", tmp_path / "t.jsonl", "--unit", "author", "--out-json", tmp_path / "r.json"], capsys)
    assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["n_units"] == 1
