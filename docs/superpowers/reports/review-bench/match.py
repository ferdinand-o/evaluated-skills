"""Vorauswahl: welcher Lauf nennt welchen Fehler? Ergebnis wird von Hand nachgeprueft."""
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
B = pathlib.Path(os.environ["BENCH"])
TRUTH = json.loads((HERE / "truth.json").read_text())

# je Fehler: Datei-Muster und Inhalts-Muster (eines muss in der Naehe stehen). Alle Muster sind
# regulaere Ausdruecke ohne Gross/Klein; (?-i:...) verlangt die Schreibweise. Ein Muster nennt
# den Fehler selbst, nicht ein Wort, das in jedem Fund derselben Datei stehen kann.
KEYS = {
    "P1": (r"download\.py", [r"HEADERS", r"\.copy\(\)", r"shared[^\n]{0,40}header", r"module.level"]),
    "P2": (r"req_dependency_group", [r"TypeError"]),
    "P3": (r"models/wheel\.py", [r"build_tag", r"empty tuple", r"\(\)[^\n]{0,40}falsy", r"falsy[^\n]{0,40}\(\)"]),
    "P4": (r"(?<![\w-])lock\.py", [r"ignore_installed"]),
    "P5": (r"cmdoptions", [r"rpartition", r"\bpartition", r"\bdrive\b", r"Windows"]),
    "P6": (r"package_finder", [r"hashes", r"cache key", r"_best_candidates"]),
    "R1": (r"wheel_builder", [r"source_dir", r"\bassert\b"]),
    "R2": (r"install/wheel\.py", [r"StringIO", r"redirect_stdout", r"StreamWrapper", r"3\.9"]),
    "Q1": (r"install/wheel\.py", [r"traversal", r"assert_no_path_traversal", r"zip.?slip", r"outside"]),
    "Q2": (r"prepare\.py", [r"is not None", r"empty Hashes", r"HashMismatch", r"__bool__"]),
    "Q3": (r"req_file", [r"COMMENT_RE", r"fragment", r"#sha256", r"#egg", r"comment"]),
    "Q4": (r"check\.py", [r"prerelease", r"pre-release"]),
    "Q5": (r"install/wheel\.py", [r"hexdigest", r"(?-i:RECORD)", r"rehash"]),
    "Q6": (r"req_install", [r"hash_options", r"copy", r"mutat"]),
    "E1": (r"RefreshToken", [r"AddOrSetValue", r"lOld\.Used", r"(?-i:\bUsed\b)\s*(?:flag|field|:=)",
                             r"\brecord\b[^\n]{0,60}\b(?:cop|value)", r"TryGetValue", r"\breuse"]),
    "E2": (r"RefreshToken", [r"OneSecond", r"ATTLSeconds", r"\bseconds?\b[^\n]{0,80}\bdays\b",
                             r"\bdays\b[^\n]{0,80}\bseconds?\b", r"\bTage\b"]),
    "E3": (r"RangeMedia", [r"double", r"SetContentStream", r"owner", r"\bfree"]),
    "E4": (r"Middleware\.OIDC", [r"UnixToDateTime", r"\bUTC\b", r"local time"]),
    "E5": (r"CSV", [r"QuoteChar", r"quote"]),
    "E6": (r"JWKS", [r"IsCacheExpired", r"<=", r"every request", r"cache"]),
    "D1": (r"AST2MSSQL", [r"Extract", r"\bleak", r"\bLeck", r"\bown(?:s|ed|er|ership)?\b", r"Besitz"]),
    "D2": (r"Indy\.Request", [r"IsDuplicatedHeader", r"lNameLen", r"off.by.one", r"duplicat"]),
    "D3": (r"Router", [r"Params\[J", r"J - 1", r"rollback", r"Remove", r"off.by.one"]),
    "D4": (r"WebSocket", [r"MaxPayloadLength", r"ParseFrame", r"payload"]),
    "D5": (r"Session", [r"fSecure", r"aSecure", r"Secure"]),
    "D6": (r"SQLGenerators\.MSSQL", [r"@@IDENTITY", r"SCOPE_IDENTITY"]),
}


def read_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def result_text(path: pathlib.Path) -> str:
    """Schlusstext des Laufs; bei deep-review dazu report.md und findings.json des Laufordners."""
    data = read_json(path)
    text = (data.get("result") or "") if isinstance(data, dict) else ""
    kit = path.with_suffix(".kit")
    if kit.is_dir():
        for extra in sorted(kit.rglob("report.md")) + sorted(kit.rglob("findings.json")):
            text += "\n" + extra.read_text(errors="replace")
    return text


def candidates(text: str, seed_id: str) -> bool:
    fkey, words = KEYS[seed_id]
    for m in re.finditer(fkey, text):
        window = text[max(0, m.start() - 600): m.end() + 900]
        if any(re.search(w, window, re.I) for w in words):
            return True
    return False


def main() -> None:
    rows = []
    for f in sorted((B / "out").glob("*.json")):
        if not f.stat().st_size:
            continue
        repo = "-".join(f.stem.split("-")[:2])
        truth = TRUTH.get(repo)
        if truth is None:
            print(f"{f.stem}: kein Eintrag '{repo}' in truth.json, uebersprungen", file=sys.stderr)
            continue
        text = result_text(f)
        hits = [t["id"] for t in truth if candidates(text, t["id"])]
        data = read_json(f)
        cost = data.get("total_cost_usd") if isinstance(data, dict) else None
        rows.append((f.stem, f"{len(hits)}/{len(truth)}", " ".join(hits), cost))
    for r in rows:
        print(f"{r[0]:22} {r[1]:5} {r[2]:30} {r[3]}")
    if len(sys.argv) > 1:
        print(result_text(B / "out" / f"{sys.argv[1]}.json"))


if __name__ == "__main__":
    main()
