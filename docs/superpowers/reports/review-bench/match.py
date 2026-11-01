"""Vorauswahl: welcher Lauf nennt welchen Fehler? Ergebnis wird von Hand nachgeprueft."""
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
B = pathlib.Path(os.environ["BENCH"])
TRUTH = json.loads((HERE / "truth.json").read_text())

# je Fehler: Datei-Stichwort und Inhalts-Stichworte (eines muss in der Naehe stehen)
KEYS = {
    "P1": ("download.py", [r"HEADERS", r"\.copy\(\)", r"shared.*header", r"module.level"]),
    "P2": ("req_dependency_group", [r"TypeError"]),
    "P3": ("wheel.py", [r"_build_tag", r"build_tag", r"empty tuple", r"\(\)"]),
    "P4": ("lock.py", [r"ignore_installed"]),
    "P5": ("cmdoptions", [r"rpartition", r"partition", r"drive", r"Windows"]),
    "P6": ("package_finder", [r"hashes", r"cache key", r"_best_candidates"]),
    "R1": ("wheel_builder", [r"source_dir", r"assert"]),
    "R2": ("wheel.py", [r"StringIO", r"redirect_stdout", r"StreamWrapper", r"3\.9"]),
    "Q1": ("wheel.py", [r"traversal", r"assert_no_path_traversal", r"zip.?slip", r"outside"]),
    "Q2": ("prepare.py", [r"is not None", r"empty Hashes", r"HashMismatch", r"__bool__"]),
    "Q3": ("req_file", [r"COMMENT_RE", r"fragment", r"#sha256", r"#egg", r"comment"]),
    "Q4": ("check.py", [r"prerelease", r"pre-release"]),
    "Q5": ("wheel.py", [r"hexdigest", r"RECORD", r"rehash"]),
    "Q6": ("req_install", [r"hash_options", r"copy", r"mutat"]),
    "E1": ("RefreshToken", [r"AddOrSetValue", r"Used", r"record", r"reuse"]),
    "E2": ("RefreshToken", [r"OneSecond", r"days", r"ATTLSeconds"]),
    "E3": ("RangeMedia", [r"double", r"SetContentStream", r"owner", r"free"]),
    "E4": ("OIDC", [r"UnixToDateTime", r"UTC", r"local time"]),
    "E5": ("CSV", [r"QuoteChar", r"quote"]),
    "E6": ("JWKS", [r"IsCacheExpired", r"<=", r"every request", r"cache"]),
    "D1": ("AST2MSSQL", [r"Extract", r"leak", r"Leck", r"own"]),
    "D2": ("Indy.Request", [r"IsDuplicatedHeader", r"lNameLen", r"off.by.one", r"duplicat"]),
    "D3": ("Router", [r"Params\[J", r"J - 1", r"rollback", r"Remove", r"off.by.one"]),
    "D4": ("WebSocket", [r"MaxPayloadLength", r"ParseFrame", r"payload"]),
    "D5": ("Session", [r"fSecure", r"aSecure", r"Secure"]),
    "D6": ("MSSQL", [r"@@IDENTITY", r"SCOPE_IDENTITY"]),
}


def result_text(path: pathlib.Path) -> str:
    try:
        return json.loads(path.read_text()).get("result") or ""
    except Exception:
        return ""


def candidates(text: str, seed_id: str) -> bool:
    fkey, words = KEYS[seed_id]
    for m in re.finditer(re.escape(fkey), text):
        window = text[max(0, m.start() - 600): m.end() + 900]
        if any(re.search(w, window, re.I) for w in words):
            return True
    return False


def main() -> None:
    rows = []
    for f in sorted((B / "out").glob("*.json")):
        repo = "-".join(f.stem.split("-")[:2])
        text = result_text(f)
        if not f.stat().st_size:
            continue
        hits = [t["id"] for t in TRUTH[repo] if candidates(text, t["id"])]
        try:
            cost = json.loads(f.read_text()).get("total_cost_usd")
        except Exception:
            cost = None
        rows.append((f.stem, len(hits), " ".join(hits), cost))
    for r in rows:
        print(f"{r[0]:22} {r[1]}  {r[2]:30} {r[3]}")
    if len(sys.argv) > 1:
        print(result_text(B / "out" / f"{sys.argv[1]}.json"))


if __name__ == "__main__":
    main()
