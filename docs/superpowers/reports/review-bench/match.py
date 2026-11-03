"""Vorauswahl: welcher Lauf nennt welchen Fehler? Ergebnis wird von Hand nachgeprueft."""
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
B = pathlib.Path(os.environ["BENCH"])
TRUTH = json.loads((HERE / "truth.json").read_text())

# je Fehler: Datei-Muster und Inhalts-Muster (eines muss in der Naehe stehen; bei deep-review im
# selben Fund, siehe kit_findings). Alle Muster, auch die Datei-Muster, sind regulaere Ausdruecke
# ohne Gross/Klein; (?-i:...) verlangt die Schreibweise. Ein Muster nennt den Fehler selbst, nicht
# ein Wort, das in jedem Fund derselben Datei stehen kann ("own", "cache", "Remove", "double").
OWNERSHIP = r"(?:\bowns?\b|\bowned\b|ownership|OwnsObjects|\bleak|\bLeck|Besitz)"
EXTRACT = r"(?-i:\bExtract\b)(?!\s+(?:the|a|an|this|that|these|those|it|them|into)\b)"  # Methode, nicht Verb
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
    "E3": (r"RangeMedia", [r"SetContentStream", r"double.?free", r"freed twice", r"Doppel.?freigabe",
                           r"use.after.free", r"LFileStream\s*:=\s*nil"]),
    "E4": (r"Middleware\.OIDC", [r"UnixToDateTime", r"\bUTC\b", r"local time"]),
    "E5": (r"CSV", [r"QuoteChar", r"quote"]),
    "E6": (r"JWKS", [r"IsCacheExpired", r"SecondsBetween[^\n]{0,80}<=", r"<=\s*FCacheTTLSeconds",
                     r"(?:every|each) (?:request|call|validation|token)",
                     r"(?:inverted|reversed|flipped|swapped|backwards?)[^\n]{0,40}"
                     r"(?:comparison|condition|check|operator)",
                     r"(?:comparison|condition|check|operator)[^\n]{0,40}"
                     r"(?:inverted|reversed|flipped|swapped|backwards)",
                     r"expired[^\n]{0,40}\bfresh\b"]),
    "D1": (r"AST2MSSQL", [EXTRACT + r"[^\n]{0,120}" + OWNERSHIP,
                          OWNERSHIP + r"[^\n]{0,120}" + EXTRACT, r"\bleak", r"\bLeck"]),
    "D2": (r"Indy\.Request", [r"IsDuplicatedHeader", r"lNameLen", r"off.by.one", r"duplicat"]),
    "D3": (r"MVCFramework\.Router\b(?!\.\w)|(?<![\w.])(?:MVCFramework\.)?Router\.pas",
           [r"Params\[J\b", r"\bJ\s*-\s*1\b", r"\brollback\b|\broll(?:s|ed|ing)?.back\b", r"off.by.one"]),
    "D4": (r"WebSocket", [r"MaxPayloadLength", r"ParseFrame", r"payload"]),
    "D5": (r"MVCFramework\.Session\b(?!\.\w)|(?<![\w.])(?:MVCFramework\.)?Session\.pas",
           [r"fSecure", r"aSecure", r"Secure"]),
    "D6": (r"SQLGenerators\.MSSQL", [r"@@IDENTITY", r"SCOPE_IDENTITY"]),
}


def read_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def result_text(path: pathlib.Path, with_kit: bool = True) -> str:
    """Schlusstext des Laufs; mit with_kit bei deep-review dazu report.md und findings.json des
    Laufordners (nur zum Lesen von Hand; abgeglichen wird dort je Fund, kit_findings)."""
    data = read_json(path)
    text = (data.get("result") or "") if isinstance(data, dict) else ""
    kit = path.with_suffix(".kit")
    if with_kit and kit.is_dir():
        for extra in sorted(kit.rglob("report.md")) + sorted(kit.rglob("findings.json")):
            text += "\n" + extra.read_text(errors="replace")
    return text


def kit_findings(path: pathlib.Path):
    """Fundobjekte aus findings.json des deep-review-Laufordners, None ohne Laufordner oder ohne
    findings.json (dann gilt das Zeichenfenster ueber den Schlusstext wie bei den anderen)."""
    kit = path.with_suffix(".kit")
    if not kit.is_dir():
        return None
    files = sorted(kit.rglob("findings.json"))
    if not files:
        print(f"{path.stem}: Laufordner ohne findings.json, Abgleich ueber den Schlusstext",
              file=sys.stderr)
        return None
    items = []
    for f in files:
        data = read_json(f)
        found = data.get("findings") if isinstance(data, dict) else None
        if not isinstance(found, list):
            print(f"{f}: kein findings-Feld, uebersprungen", file=sys.stderr)
            continue
        items += [item for item in found if isinstance(item, dict)]
    return items


def finding_hit(item: dict, seed_id: str) -> bool:
    """Ein Fund von deep-review: Datei-Muster auf sein `file`, Inhalts-Muster auf seine eigene
    `summary` und sein `failure_scenario`, nie auf benachbarte Funde."""
    fkey, words = KEYS[seed_id]
    file = item.get("file")
    if not isinstance(file, str) or not re.search(fkey, file, re.I):
        return False
    own = "\n".join(t for t in (item.get("summary"), item.get("failure_scenario"))
                    if isinstance(t, str))
    return any(re.search(w, own, re.I) for w in words)


def candidates(text: str, seed_id: str) -> bool:
    """Klartext eines Werkzeugs: Inhalts-Muster im Fenster um eine Nennung der Datei."""
    fkey, words = KEYS[seed_id]
    for m in re.finditer(fkey, text, re.I):
        window = text[max(0, m.start() - 600): m.end() + 900]
        if any(re.search(w, window, re.I) for w in words):
            return True
    return False


def hits(path: pathlib.Path, truth: list) -> list:
    items = kit_findings(path)
    if items is not None:
        return [t["id"] for t in truth if any(finding_hit(i, t["id"]) for i in items)]
    text = result_text(path, with_kit=False)
    return [t["id"] for t in truth if candidates(text, t["id"])]


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
        found = hits(f, truth)
        data = read_json(f)
        cost = data.get("total_cost_usd") if isinstance(data, dict) else None
        rows.append((f.stem, f"{len(found)}/{len(truth)}", " ".join(found), cost))
    for r in rows:
        print(f"{r[0]:22} {r[1]:5} {r[2]:30} {r[3]}")
    if len(sys.argv) > 1:
        print(result_text(B / "out" / f"{sys.argv[1]}.json"))


if __name__ == "__main__":
    main()
