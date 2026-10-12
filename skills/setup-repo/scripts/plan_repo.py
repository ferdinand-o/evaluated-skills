#!/usr/bin/env python3
"""Schreibt den Einrichtungsplan eines Repos (setup-repo, Spec 22). Tier 1.

    python plan_repo.py [--repo <pfad>] [--classes '<json>'] [--with-verify-hook] [--deny-secrets]

Liest `.skills/cache/setup-repo/detect.json` und `candidates.json`, schreibt nur
`.skills/cache/setup-repo/plan.md`: oben die Ansicht für den Nutzer, darunter den Block
`json setup-repo-plan` mit Hash (Format: references/plan-format.md). Klassen je Kandidat
kommen aus `--classes`; ohne Angabe gelten die Klassen des letzten Plans, sonst „offen".
Der Hash kennt weder Ort noch HEAD noch Zeilenenden; `.claude/skills/` steht nie im Block.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS = SKILL_DIR / "assets"
CACHE = Path(".skills") / "cache" / "setup-repo"
GENERATED = "python skills/setup-repo/scripts/plan_repo.py"
HEADER = f"<!-- skill: setup-repo | schema: 1 | generated: {GENERATED} -->"
BLOCK_INFO = "json setup-repo-plan"
BUDGET_LIMIT = 150
CLASSES = ("ableitbar", "werkzeug", "regel", "offen")
CLASS_LABELS = {"ableitbar": "ableitbar", "werkzeug": "Werkzeug", "regel": "Regel", "offen": "offen"}
GITIGNORE_LINES = [".skills/cache/", ".claude/settings.local.json"]
DENY_SECRETS = ["Read(./.env)", "Read(./.env.*)", "Read(./**/*.pem)", "Read(./**/*.key)"]
ALL_IN_ONE = ("check", "verify", "ci", "validate")
PARTS = ("lint", "typecheck", "test")
IMPORT_RE = re.compile(r"^@(\S+)\s*$")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _read(path: Path) -> str | None:
    try:
        return _norm(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def _sha(text: str | None) -> str | None:
    return None if text is None else hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan_hash(block) -> str:
    body = {k: v for k, v in block.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


# --- Verifikation ------------------------------------------------------------------

def _runner_choice(names, prefix: str, source: str):
    names = list(names)
    for name in ALL_IN_ONE:
        if name in names:
            parts = [f"{prefix} {name}"] + [f"{prefix} {p}" for p in PARTS if p in names]
            return f"{prefix} {name}", f"{source}: {name}", parts
    found = [p for p in PARTS if p in names]
    if found:
        parts = [f"{prefix} {p}" for p in found]
        return " && ".join(parts), f"{source}: {', '.join(found)}", parts
    return None


def _choose(detect: dict):
    runners = detect.get("runners", {})
    pm = runners.get("package_manager") or "npm"
    candidates = [(runners.get("make", []), "make", "Makefile"), (runners.get("just", []), "just", "justfile"),
                  (runners.get("npm", {}), f"{pm} run", "package.json")]
    for tool, prefix in (("poe", "poe"), ("pdm", "pdm run"), ("hatch", "hatch run")):
        candidates.append((runners.get("pyproject", {}).get(tool, []), prefix, f"pyproject.toml ({tool})"))
    for names, prefix, source in candidates:
        choice = _runner_choice(names, prefix, source)
        if choice:
            command, src, parts = choice
            return {"command": command, "source": src, "derived": False}, parts
    if detect.get("pytest_config") and detect.get("tests"):
        return ({"command": "python -m pytest", "source": "pyproject.toml [tool.pytest.ini_options]",
                 "derived": False}, ["python -m pytest"])
    dprojs = detect.get("delphi_projects") or []
    if dprojs:
        return {"command": f"msbuild {dprojs[0]}", "source": f"{dprojs[0]} (abgeleitet)", "derived": True}, []
    return {"command": None, "source": None, "derived": False}, []


def choose_verification(detect) -> dict:
    """Befehl aus vorhandenen Runner-Einträgen; Delphi abgeleitet; sonst None."""
    return _choose(detect)[0]


# --- Inhalte -----------------------------------------------------------------------

def _slug(text: str) -> str:
    text = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (slug[:40].rsplit("-", 1)[0] if len(slug) > 40 and "-" in slug[:40] else slug[:40]) or "regel"


def _rule_line(c: dict) -> str:
    return f"- {c['text']} (Quelle: {c['source']})"


def _verification_texts(v: dict) -> tuple[str, str]:
    if v["command"] is None:
        return ("keine — ungeprüft",
                "Kein Runner-Eintrag gefunden. Welche Tests fehlen, klärt testing-strategy; setup-repo legt "
                "keine Runner-Ziele an.")
    if v["derived"]:
        return (f"`{v['command']}` (abgeleitet, ungeprüft)",
                f"Abgeleitet aus {v['source'].removesuffix(' (abgeleitet)')}, nicht aus einem Runner-Eintrag — "
                "ungeprüft und nicht freigegeben.")
    return f"`{v['command']}`", f"Quelle: {v['source']}. Vor jeder Erfolgsmeldung laufen lassen."


def _new_claude_md(detect: dict, v: dict, rules: list[str]) -> str:
    template = _norm((ASSETS / "CLAUDE.md.tmpl").read_text(encoding="utf-8"))
    verification, note = _verification_texts(v)
    agents = "@AGENTS.md" if detect.get("agents_md") and not detect.get("claude_files") else ""
    values = {"agents_import": agents, "verification": verification, "verification_note": note,
              "rules": "\n".join(rules) if rules else "Keine geernteten Regeln ohne Geltungsbereich."}
    lines = []
    for line in template.splitlines():
        if line.strip() == "{{agents_import}}" and not agents:
            continue
        for key, value in values.items():
            line = line.replace("{{" + key + "}}", value)
        lines.append(line)
    return "\n".join(lines) + "\n"


def _append_claude_md(existing: str, v: dict, rules: list[str]) -> str:
    parts = []
    if not re.search(r"^Verifikation:", existing, re.MULTILINE):
        verification, note = _verification_texts(v)
        parts.append(f"## Verifikation (setup-repo)\n\nVerifikation: {verification}\n\n{note}\n")
    new_rules = [r for r in rules if r not in existing]
    if new_rules:
        parts.append("## Konventionen (setup-repo)\n\n" + "\n".join(new_rules) + "\n")
    if not parts:
        return ""
    lead = "\n" if existing.endswith("\n") else "\n\n"
    return lead + "\n".join(parts)


def _rule_file(c: dict) -> str:
    paths = "\n".join(f'  - "{p}"' for p in c["paths"])
    return f"---\npaths:\n{paths}\n---\n{HEADER}\n# Regel {c['id']}\n\n{_rule_line(c)}\n"


# --- Budget ------------------------------------------------------------------------

def _has_paths(text: str) -> bool:
    m = FRONTMATTER_RE.match(text)
    return bool(m and re.search(r"^paths:", m.group(1), re.MULTILINE))


def _always_loaded(root: Path, after: dict[str, str | None]) -> int:
    def content(rel: str) -> str | None:
        return after[rel] if rel in after else _read(root / rel)

    total = 0
    for rel in ("CLAUDE.md", ".claude/CLAUDE.md"):
        text = content(rel)
        if text is None:
            continue
        total += len(text.splitlines())
        base = Path(rel).parent
        for line in text.splitlines():
            m = IMPORT_RE.match(line)
            if m:
                imported = content((base / m.group(1)).as_posix())
                total += len(imported.splitlines()) if imported else 0
    rules_dir = root / ".claude" / "rules"
    rule_paths = {p.relative_to(root).as_posix() for p in rules_dir.rglob("*.md")} if rules_dir.is_dir() else set()
    rule_paths |= {p for p in after if p.startswith(".claude/rules/") and p.endswith(".md")}
    for rel in sorted(rule_paths):
        text = content(rel)
        if text and not _has_paths(text):
            total += len(text.splitlines())
    return total


# --- Plan --------------------------------------------------------------------------

def _classify(candidates: list[dict], classes: dict) -> list[dict]:
    out = []
    for c in candidates:
        value = (classes or {}).get(c["id"], "offen")
        cls, paths = (value.get("class"), value.get("paths") or []) if isinstance(value, dict) else (value, [])
        if cls not in CLASSES:
            raise ValueError(f"{c['id']}: unbekannte Klasse {cls!r} — erlaubt: {', '.join(CLASSES)}")
        if cls != "regel":
            paths = []
        out.append({"id": c["id"], "text": c["text"], "source": c["source"], "checked_by": c.get("checked_by"),
                    "class": cls, "paths": [str(p) for p in paths]})
    return out


def _plugins(detect: dict) -> dict[str, bool]:
    project = set(detect.get("project_skills") or [])
    result: dict[str, bool] = {}
    for p in detect.get("plugins") or []:
        if project & set(p.get("skills") or []):
            result[p["id"]] = False
        elif p.get("name") == "cc-ui" and detect.get("frontend"):
            result[p["id"]] = True
    return dict(sorted(result.items()))


def build_plan(repo_root, detect, candidates, options) -> dict:
    """Der Block samt Hash; liest das Repo, schreibt nichts."""
    root = Path(repo_root)
    options = options or {}
    verification, parts = _choose(detect)
    cands = _classify(candidates or [], options.get("classes") or {})
    rules = [_rule_line(c) for c in cands if c["class"] == "regel" and not c["paths"]]
    operations: list[dict] = []

    target = next((f for f in ("CLAUDE.md", ".claude/CLAUDE.md") if (root / f).is_file()), None)
    if target is None:
        operations.append({"path": "CLAUDE.md", "action": "create",
                           "content": _new_claude_md(detect, verification, rules)})
    else:
        extra = _append_claude_md(_read(root / target) or "", verification, rules)
        if extra:
            operations.append({"path": target, "action": "append", "content": extra})

    for c in cands:
        if c["class"] != "regel" or not c["paths"]:
            continue
        content, rel, n = _rule_file(c), f".claude/rules/{c['id']}-{_slug(c['text'])}.md", 2
        while (existing := _read(root / rel)) is not None and existing != content:
            rel, n = f".claude/rules/{c['id']}-{_slug(c['text'])}-{n}.md", n + 1
        if existing != content:
            operations.append({"path": rel, "action": "create", "content": content})

    verify_hook = bool(options.get("verify_hook")) and verification["command"] is not None \
        and not verification["derived"]
    if verify_hook:
        operations.append({"path": ".claude/hooks/verify_stop.py", "action": "copy",
                           "content": _norm((ASSETS / "runtime" / "verify_stop.py").read_text(encoding="utf-8"))})

    plugins = _plugins(detect)
    if plugins:
        operations.append({"path": ".claude/settings.local.json", "action": "merge-json",
                           "patch": {"enabledPlugins": plugins}})

    present = {line.strip().lstrip("/") for line in (_read(root / ".gitignore") or "").splitlines()}
    missing = [line for line in GITIGNORE_LINES if line not in present]
    if missing:
        operations.append({"path": ".gitignore", "action": "gitignore", "lines": missing})

    patch: dict = {}
    allow = [f"Bash({p})" for p in parts]
    deny = DENY_SECRETS if options.get("deny_secrets") else []
    if allow or deny:
        patch["permissions"] = {k: v for k, v in (("allow", allow), ("deny", deny)) if v}
    if verify_hook:
        patch["hooks"] = json.loads((ASSETS / "hooks" / "verify-stop.json").read_text(encoding="utf-8"))["hooks"]
    if patch:
        operations.append({"path": ".claude/settings.json", "action": "merge-json", "patch": patch})

    after: dict[str, str | None] = {}
    for op in operations:
        if op["action"] == "create":
            after[op["path"]] = op["content"]
        elif op["action"] == "append":
            after[op["path"]] = (_read(root / op["path"]) or "") + op["content"]

    block = {
        "schema": 1,
        "verification": verification,
        "candidates": cands,
        "options": {"verify_hook": verify_hook, "deny_secrets": bool(options.get("deny_secrets"))},
        "plugins": plugins,
        "budget": {"lines": _always_loaded(root, after), "limit": BUDGET_LIMIT},
        "operations": operations,
        "base": {op["path"]: _sha(_read(root / op["path"])) for op in operations},
    }
    block["hash"] = plan_hash(block)
    return block


# --- Ansicht -----------------------------------------------------------------------

def _op_view(op: dict) -> list[str]:
    lines = [f"### `{op['path']}` ({op['action']})", ""]
    if op["action"] in ("create", "append"):
        body = op["content"].splitlines()
        shown = [f"+{line}" for line in body[:40]] + ([f"… {len(body) - 40} Zeilen mehr"] if len(body) > 40 else [])
        lines += ["```diff", *shown, "```"]
    elif op["action"] == "merge-json":
        lines += ["Gemischt wird:", "", "```json", json.dumps(op["patch"], ensure_ascii=False, indent=2), "```"]
    elif op["action"] == "copy":
        lines.append(f"Kopie von `assets/runtime/{Path(op['path']).name}` ({len(op['content'].splitlines())} Zeilen).")
    elif op["action"] == "gitignore":
        lines += ["```diff", *[f"+{line}" for line in op["lines"]], "```", "(nur fehlende Zeilen werden angehängt)"]
    return lines + [""]


def render_plan(block) -> str:
    v = block["verification"]
    verification, note = _verification_texts(v)
    lines = [HEADER, "# setup-repo — Plan", "", "## Verifikation", "", f"Verifikation: {verification}", "", note, ""]
    lines += ["## Kandidaten", ""]
    if not block["candidates"]:
        lines.append("Keine Regelkandidaten gefunden.")
    for c in block["candidates"]:
        label = CLASS_LABELS[c["class"]] + (f" ({', '.join(c['paths'])})" if c["paths"] else "")
        checked = f" — geprüft von {c['checked_by']}" if c.get("checked_by") else ""
        lines.append(f"- {c['text']} · {c['source']} · {label}{checked}")
    open_ids = [c["id"] for c in block["candidates"] if c["class"] == "offen"]
    if open_ids:
        lines += ["", f"Offen: {', '.join(open_ids)} — Klassen über `plan_repo.py --classes` eintragen "
                      "(references/rules-harvest.md)."]
    budget = block["budget"]
    lines += ["", "## Budget", "", f"Immer geladen nach apply: {budget['lines']} von {budget['limit']} Zeilen "
              "(CLAUDE.md samt Importen, Rules ohne `paths`)."]
    if budget["lines"] > budget["limit"]:
        lines.append(f"**Befund: Budget überschritten um {budget['lines'] - budget['limit']} Zeilen** — kürzen über "
                     "Klassifikation (`werkzeug`, `ableitbar`, `paths`).")
    lines += ["", "## Plugins je Repo", ""]
    if block["plugins"]:
        lines += [f"- `{pid}`: {'an' if on else 'aus'}" for pid, on in block["plugins"].items()]
        lines.append("Steht in `.claude/settings.local.json` (persönlich, nicht committet).")
    else:
        lines.append("ungeprüft — Plugin-ID nicht gefunden; `apply` schreibt keine `enabledPlugins`.")
    lines += ["", "## Hooks (abwählbar)", ""]
    if v["command"] is None or v["derived"]:
        lines.append("- Verifikations-Hook: nicht angeboten — kein belegter Verifikationsbefehl.")
    elif block["options"]["verify_hook"]:
        lines.append("- Verifikations-Hook (`Stop`, `.claude/hooks/verify_stop.py`): **an** — hält das Turn-Ende an, "
                     "solange die Verifikation rot ist, höchstens dreimal in Folge. Abwählen: neu planen ohne "
                     "`--with-verify-hook`.")
    else:
        lines.append("- Verifikations-Hook (`Stop`): aus — zuschalten mit `--with-verify-hook`.")
    if block["options"]["deny_secrets"]:
        lines.append("- `permissions.deny` für `.env` und Schlüsseldateien: an.")
    else:
        lines.append("- `permissions.deny` für `.env` und Schlüsseldateien: aus — zuschalten mit `--deny-secrets`.")
    lines.append("  Ein Read-Deny gilt für die Datei-Werkzeuge und erkannte Bash-Dateikommandos, nicht für beliebige "
                 "Unterprozesse.")
    lines += ["", "## Änderungen", ""]
    if not block["operations"]:
        lines += ["Keine — das Repo entspricht schon dem Plan.", ""]
    for op in block["operations"]:
        lines += _op_view(op)
    lines += ["## Hinweise", "",
              "- `.skills/cache/` ist bis `apply` im Repo unversioniert sichtbar; `apply` ergänzt `.gitignore`.",
              "- `apply` läuft erst nach Bestätigung, in einem eigenen Aufruf, und committet nie.", "",
              "## Block für apply", "", "```" + BLOCK_INFO,
              json.dumps(block, ensure_ascii=False, indent=2, sort_keys=True), "```", ""]
    return "\n".join(lines)


# --- CLI ---------------------------------------------------------------------------

def _previous_classes(plan_path: Path) -> dict:
    text = _read(plan_path)
    if not text:
        return {}
    m = re.search(r"^```" + re.escape(BLOCK_INFO) + r"\n(.*?)^```", text, re.MULTILINE | re.DOTALL)
    try:
        block = json.loads(m.group(1)) if m else {}
    except ValueError:
        return {}
    return {c["id"]: (c["text"], {"class": c["class"], "paths": c.get("paths") or []})
            for c in block.get("candidates", []) if isinstance(c, dict) and "id" in c}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".")
    parser.add_argument("--classes", default="{}")
    parser.add_argument("--with-verify-hook", action="store_true")
    parser.add_argument("--deny-secrets", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.repo).resolve()
    cache = root / CACHE
    try:
        detect = json.loads((cache / "detect.json").read_text(encoding="utf-8"))
        candidates = json.loads((cache / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    except (OSError, ValueError, KeyError, TypeError):
        print(f"kein lesbares detect.json oder candidates.json unter {cache} — zuerst detect_repo.py und "
              "harvest_rules.py laufen lassen", file=sys.stderr)
        return 2
    try:
        given = json.loads(args.classes)
        if not isinstance(given, dict):
            raise ValueError("--classes muss ein JSON-Objekt sein")
    except ValueError as exc:
        print(f"--classes: {exc}", file=sys.stderr)
        return 2
    plan_path = cache / "plan.md"
    texts = {c["id"]: c["text"] for c in candidates}
    classes = {cid: value for cid, (text, value) in _previous_classes(plan_path).items() if texts.get(cid) == text}
    classes.update(given)
    try:
        block = build_plan(root, detect, candidates, {"classes": classes, "verify_hook": args.with_verify_hook,
                                                      "deny_secrets": args.deny_secrets})
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    plan_path.write_text(render_plan(block), encoding="utf-8", newline="\n")
    v = block["verification"]
    print(f"Repo: {root}")
    print(f"Verifikation: {v['command'] or 'keine — ungeprüft'}" + (" (abgeleitet)" if v["derived"] else ""))
    print(f"Kandidaten: {len(block['candidates'])}, offen: {sum(c['class'] == 'offen' for c in block['candidates'])}")
    print(f"Budget: {block['budget']['lines']} von {block['budget']['limit']} Zeilen")
    print(f"Operationen: {len(block['operations'])}; Hash {block['hash'][:12]}")
    print(f"geschrieben: {plan_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
