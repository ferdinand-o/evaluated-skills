#!/usr/bin/env python3
"""reddit-research helper. Tier 1: nur Stdlib.

  select  - dedupe candidate threads, rank them, spread them over subreddits
            and time periods, and write work batches for the tagging workers
  remap   - move OTHER items to categories by their other_label (map file),
            writing corrected copies; the original tag files stay untouched
  tally   - count tagged items per category by thread, author or item,
            with 95 % Wilson intervals and breakdowns by subreddit or period
"""
import argparse
import collections
import datetime as dt
import glob
import json
import math
import os
import sys


def read_jsonl(patterns):
    rows, bad = [], 0
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        bad += 1
    return rows, bad


def period_of(ts, size):
    try:
        d = dt.datetime.fromtimestamp(float(ts), tz=dt.timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return "unknown"
    if size == "month":
        return f"{d.year}-{d.month:02d}"
    if size == "quarter":
        return f"{d.year}-Q{(d.month - 1) // 3 + 1}"
    if size == "half":
        return f"{d.year}-H{1 if d.month <= 6 else 2}"
    return str(d.year)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# ── select ──────────────────────────────────────────────────────────────────

def cmd_select(args):
    rows, bad = read_jsonl(args.candidates)
    seen, cands = set(), []
    for r in rows:
        tid = str(r.get("id", "")).removeprefix("t3_")
        if not tid or tid in seen:
            continue
        seen.add(tid)
        if int(r.get("num_comments") or 0) < args.min_comments:
            continue
        if args.text_only and int(r.get("selftext_length") or 0) == 0 and not r.get("selftext"):
            continue
        r["id"] = tid
        cands.append(r)

    by_sub = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in cands:
        by_sub[r.get("subreddit", "?")][period_of(r.get("created_utc"), args.period)].append(r)

    chosen = []
    for sub, periods in by_sub.items():
        for items in periods.values():
            items.sort(key=lambda r: (int(r.get("num_comments") or 0), int(r.get("score") or 0)), reverse=True)
        quota = args.per_subreddit
        picked = []
        # round-robin over periods so every period is represented
        while len(picked) < quota and any(periods.values()):
            for key in sorted(periods):
                if periods[key] and len(picked) < quota:
                    picked.append(periods[key].pop(0))
        chosen.extend(picked)

    if args.max_total and len(chosen) > args.max_total:
        chosen.sort(key=lambda r: int(r.get("num_comments") or 0), reverse=True)
        chosen = chosen[: args.max_total]

    os.makedirs(args.out, exist_ok=True)
    stale = sorted(glob.glob(os.path.join(args.out, "batch_*.json")))
    if stale:
        print(f"WARNUNG: {len(stale)} Batch-Datei(en) in {args.out} werden überschrieben; übrige alte bleiben liegen", file=sys.stderr)
    batches = [chosen[i:i + args.batch_size] for i in range(0, len(chosen), args.batch_size)]
    for i, batch in enumerate(batches, 1):
        path = os.path.join(args.out, f"batch_{i:03d}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"batch": i, "threads": [
                {k: r.get(k) for k in ("id", "subreddit", "title", "num_comments", "score", "created_utc")}
                for r in batch]}, handle, ensure_ascii=False, indent=1)

    per_sub = collections.Counter(r.get("subreddit") for r in chosen)
    print(f"candidates read: {len(rows)} (invalid lines: {bad}), unique: {len(seen)}, eligible: {len(cands)}")
    print(f"selected: {len(chosen)} threads in {len(batches)} batches -> {args.out}")
    for sub, n in per_sub.most_common():
        print(f"  {sub}: {n}")


# ── remap ───────────────────────────────────────────────────────────────────

def cmd_remap(args):
    with open(args.map, encoding="utf-8") as handle:
        mapping = json.load(handle)  # {"C15": ["label a", "label b"], ...}
    label_to_cat = {label.strip().lower(): cat for cat, labels in mapping.items() for label in labels}
    os.makedirs(args.out, exist_ok=True)
    moved, files, skipped = collections.Counter(), 0, 0
    for pattern in args.tags:
        for path in sorted(glob.glob(pattern)):
            files += 1
            target = os.path.join(args.out, os.path.basename(path))
            with open(path, encoding="utf-8") as src, open(target, "w", encoding="utf-8") as dst:
                for line in src:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        skipped += 1  # abgeschnittene Zeile eines abgebrochenen Workers; tally zählt sie als ungültig
                        continue
                    if row.get("advice") in ("None", "null", ""):
                        row["advice"] = None
                    cats = row.get("categories") or []
                    label = (row.get("other_label") or "").strip().lower()
                    if "OTHER" in cats and label in label_to_cat:
                        new = label_to_cat[label]
                        row["categories"] = sorted({c for c in cats if c != "OTHER"} | {new})
                        row["remapped_from_other"] = row.get("other_label")
                        moved[new] += 1
                    dst.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"files: {files} -> {args.out}; remapped items: {sum(moved.values())}; invalid lines skipped: {skipped}")
    for cat, n in moved.most_common():
        print(f"  {cat}: {n}")


# ── tally ───────────────────────────────────────────────────────────────────

REQUIRED = ("item_id", "thread_id", "subreddit", "relevant", "categories")


def unit_key(row, unit):
    if unit == "thread":
        return row.get("thread_id")
    if unit == "author":
        author = row.get("author")
        return None if author in (None, "", "[deleted]") else author
    return row.get("item_id")


def stats(rows, unit, labels):
    units = {unit_key(r, unit) for r in rows} - {None}
    n = len(units)
    per_cat = collections.defaultdict(set)
    constructive = collections.Counter()
    for r in rows:
        key = unit_key(r, unit)
        if key is None:
            continue
        for cat in r.get("categories") or []:
            per_cat[cat].add(key)
            if r.get("constructive") is True:
                constructive[cat] += 1
    table = []
    for cat, keys in per_cat.items():
        k = len(keys)
        lo, hi = wilson(k, n)
        table.append({"category": cat, "label": labels.get(cat, cat), "units": k,
                      "share": k / n if n else 0.0, "ci95": [lo, hi],
                      "constructive_items": constructive[cat]})
    table.sort(key=lambda t: (-t["units"], t["category"]))

    stance = collections.Counter()
    by_unit = collections.defaultdict(collections.Counter)
    for r in rows:
        key = unit_key(r, unit)
        if key is not None and r.get("stance"):
            by_unit[key][r["stance"]] += 1
    for counts in by_unit.values():
        top = counts.most_common()
        stance["mixed" if len(top) > 1 and top[0][1] == top[1][1] else top[0][0]] += 1
    return n, table, dict(stance)


def cmd_tally(args):
    rows, bad = read_jsonl(args.tags)
    labels = {}
    if args.codebook:
        with open(args.codebook, encoding="utf-8") as handle:
            book = json.load(handle)
        labels = {c["id"]: c.get("label", c["id"]) for c in book.get("categories", [])}

    seen, valid, invalid = set(), [], 0
    for r in rows:
        if any(f not in r for f in REQUIRED):
            invalid += 1
            continue
        if r["item_id"] in seen:
            continue
        seen.add(r["item_id"])
        valid.append(r)
    relevant = [r for r in valid if r.get("relevant") is True]
    unknown = sorted({c for r in relevant for c in r.get("categories") or []} - set(labels)) if labels else []

    n, table, stance = stats(relevant, args.unit, labels)
    groups = {}
    if args.by != "none":
        # a thread belongs to the period of its earliest item (normally the post),
        # so long discussions are not counted in two periods
        start = {}
        for r in valid:
            ts = r.get("created_utc")
            if isinstance(ts, (int, float)) and (r["thread_id"] not in start or ts < start[r["thread_id"]]):
                start[r["thread_id"]] = ts
        buckets = collections.defaultdict(list)
        for r in relevant:
            if args.by == "subreddit":
                g = r.get("subreddit")
            else:
                g = period_of(start.get(r["thread_id"], r.get("created_utc")), args.period)
            buckets[g].append(r)
        for g in sorted(buckets):
            gn, gt, gs = stats(buckets[g], args.unit, labels)
            groups[g] = {"n": gn, "categories": gt, "stance": gs}

    result = {"unit": args.unit, "n_units": n, "items_total": len(valid), "items_relevant": len(relevant),
              "invalid_lines": bad + invalid, "unknown_categories": unknown,
              "categories": table, "stance": stance, "by": args.by, "groups": groups}
    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=1)

    unit_word = {"thread": "Threads", "author": "Autoren", "item": "Beiträge"}[args.unit]
    print(f"Basis: {n} {unit_word} mit relevanten Beiträgen "
          f"({len(relevant)} relevante von {len(valid)} getaggten Items; {bad + invalid} ungültige Zeilen)")
    if unknown:
        print(f"WARNUNG: Kategorien fehlen im Codebuch: {', '.join(unknown)}")
    print()
    print(f"| Kategorie | {unit_word} | Anteil | 95 %-Intervall | konstruktive Beiträge |")
    print("| --- | ---: | ---: | ---: | ---: |")
    for t in table:
        lo, hi = t["ci95"]
        print(f"| {t['label']} | {t['units']} | {t['share']:.0%} | {lo:.0%}–{hi:.0%} | {t['constructive_items']} |")
    if stance:
        print()
        print(f"Haltung ({unit_word}): "
              + ", ".join(f"{k} {v}" for k, v in sorted(stance.items(), key=lambda x: -x[1])))
    if groups:
        print()
        cats = [t["category"] for t in table][: args.top]
        head = " | ".join(labels.get(c, c) for c in cats)
        print(f"| {args.by} | N | {head} |")
        print("| --- | ---: |" + " ---: |" * len(cats))
        for g, data in groups.items():
            share = {t["category"]: t["share"] for t in data["categories"]}
            cells = " | ".join(f"{share.get(c, 0):.0%}" for c in cats)
            print(f"| {g} | {data['n']} | {cells} |")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("select", help="choose threads and write work batches")
    s.add_argument("candidates", nargs="+", help="JSONL file(s)/globs with candidate threads")
    s.add_argument("--out", default="batches")
    s.add_argument("--min-comments", type=int, default=5)
    s.add_argument("--per-subreddit", type=int, default=60)
    s.add_argument("--max-total", type=int, default=0)
    s.add_argument("--batch-size", type=int, default=12)
    s.add_argument("--period", choices=["month", "quarter", "half", "year"], default="quarter")
    s.add_argument("--text-only", action="store_true", help="drop link/image/video posts without text")
    s.set_defaults(func=cmd_select)

    m = sub.add_parser("remap", help="move OTHER items to categories by other_label")
    m.add_argument("tags", nargs="+", help="JSONL file(s)/globs with tagged items")
    m.add_argument("--map", required=True, help='JSON {"C15": ["label", ...], ...}')
    m.add_argument("--out", default="tags_final")
    m.set_defaults(func=cmd_remap)

    t = sub.add_parser("tally", help="count tagged items per category")
    t.add_argument("tags", nargs="+", help="JSONL file(s)/globs with tagged items")
    t.add_argument("--codebook", help="codebook.json for category labels")
    t.add_argument("--unit", choices=["thread", "author", "item"], default="thread")
    t.add_argument("--by", choices=["none", "subreddit", "period"], default="none")
    t.add_argument("--period", choices=["month", "quarter", "half", "year"], default="half")
    t.add_argument("--top", type=int, default=6, help="categories shown in the breakdown table")
    t.add_argument("--out-json")
    t.set_defaults(func=cmd_tally)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
