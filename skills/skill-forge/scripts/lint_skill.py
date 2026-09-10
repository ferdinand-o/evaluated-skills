#!/usr/bin/env python3
"""Skill-Ordner gegen die Hausmethode prüfen. Tier 1: nur Stdlib.

Dreizehn Regeln aus Spec 00, `docs/artifact-header.md` und `docs/known-limits.md`
(Spec 17). Jede Regel liefert `pass`, `finding`, `hint` oder `unchecked` mit Grund;
`unchecked` und `hint` zählen nie als `pass` — ein übersprungener Check meldet nie
Erfolg. Das Skript importiert weder `evalkit` noch ein anderes Skill-Skript: Im
Eval-Workspace gibt es nur diesen Ordner, und Regeln, die `docs/`, `README.md` oder
fremde Skills brauchen, melden dort `unchecked`.

    python skills/skill-forge/scripts/lint_skill.py skills/<name> [--base REV] [--out lint.json]

Exit 0 ohne Befund, 1 mit Befund, 2 wenn der Skill-Ordner nicht lesbar ist oder der
Diff-Modus keine Grundlage hat. `lint.json` schreibt jede Regel als eigene Zeile
`{"id": …, "status": …, "reason": …}` — das ist der Vertrag, an den Evals per
`file_matches` binden.

`--base REV` (Diff-Modus): Der Lint läuft zusätzlich gegen den Stand des Ordners bei
REV; nur Befunde, die dort nicht schon standen, zählen für den Exit-Code. `evals_due`
sagt, ob die Änderung Frontmatter, Contract-Abschnitt oder eine Zeile berührt, auf die
ein Assertion-Pattern der eigenen `evals.json` greift.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1
SKILL_MD_MAX_LINES = 150
STATUSES = ("pass", "finding", "hint", "unchecked")

FRONTMATTER_ALLOWED = frozenset({"name", "description", "license", "version", "metadata", "allowed-tools"})
FRONTMATTER_REQUIRED = ("name", "description")
PROCESS_VERBS = ("runs", "builds", "generates", "produces", "collects", "renders",
                 "scans", "creates", "writes", "tracks", "enforces", "classifies")
PROCESS_VERB_RE = re.compile(r"\b(" + "|".join(PROCESS_VERBS) + r")\b", re.IGNORECASE)
TRIGGER_RE = re.compile(r"\bUse (when|for|this|it|to|before|after)\b|„[^“\"]+[\"“]|\"[^\"]{4,}\"", re.IGNORECASE)
BOUNDARY_RE = re.compile(r"\b[Nn]ot for\b|\bnicht für\b|\binstead\b|\bstattdessen\b")
GATE_WORD_RE = re.compile(r"\b(blockiert|erzwingt|stellt sicher)\b")
NEGATION_RE = re.compile(r"\b(nicht|nichts|nie|niemals|kein|keine|keinen|keinem|keiner|ohne)\b")
TIER_RE = re.compile(r"\bTier\s*(\d)\b")
CONJUNCTION_RE = re.compile(r" und | UND | statt | sowie ")
ANTI_CEREMONY_PREFIX = "anti-ceremony-"
EVAL_CLASSES = frozenset({"contract", "behavior"})
PATTERN_TYPES = frozenset({"file_matches", "output_matches"})
CONTRACT_HEADING_RE = re.compile(r"^## .*Contract", re.MULTILINE)
BOUNDARY_HEADING_RE = re.compile(r"^## .*Abgrenzung", re.MULTILINE)
REPORT_SECTION_RE = re.compile(r"^## Was nicht gemessen wurde", re.MULTILINE | re.IGNORECASE)
EXCEPTION_HEADING = "## Begründete Ausnahme"
# Kopiert aus evalkit/assertions.py — nicht importiert (Tier 1, kein Import fremder Skripte).
ARTIFACT_HEADER_RE = re.compile(
    r"^(?:<!--|#)\s*skill:\s*(?P<skill>[a-z0-9][a-z0-9-]*)\s*\|"
    r"\s*schema:\s*(?P<schema>\d+)\s*\|"
    r"\s*generated:\s*(?P<cmd>.+?)\s*(?:-->)?\s*$"
)
SPEC00_NAME = "Spec 00 – skill-foundation.md"


@dataclass(frozen=True)
class RuleResult:
    id: str
    status: str
    reason: str

    def as_dict(self) -> dict:
        return {"id": self.id, "status": self.status, "reason": self.reason}


@dataclass
class LintReport:
    skill: str
    skill_dir: Path
    repo_root: Path | None
    rules: list[RuleResult]

    @property
    def findings(self) -> list[RuleResult]:
        return [r for r in self.rules if r.status == "finding"]

    def summary(self) -> dict:
        return {s: sum(1 for r in self.rules if r.status == s) for s in STATUSES}


# --- Hilfen -----------------------------------------------------------------------

def find_repo_root(skill_dir: Path) -> Path | None:
    """Nächster Elternordner mit `specs/` oder `evals/`. Im Eval-Workspace liegt die
    Skill unter `.claude/skills/<name>/`, die Fixture-Dateien an der Wurzel — die Suche
    nach oben findet beides."""
    for parent in [skill_dir.resolve()] + list(skill_dir.resolve().parents):
        if (parent / "specs").is_dir() or (parent / "evals").is_dir():
            return parent
    return None


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def split_frontmatter(text: str) -> tuple[dict[str, str] | None, int]:
    """(Felder, Zeilenindex hinter dem Frontmatter). None, wenn kein Frontmatter."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, 0
    fields: dict[str, str] = {}
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return fields, i + 1
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", lines[i])
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return None, 0


def _units(text: str) -> list[str]:
    """Absätze, durch Leerzeilen getrennt; Tabellen- und Listenzeilen sind je eine
    eigene Einheit — eine Negation in der Nachbarzeile einer Tabelle zählt nicht."""
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        lines = para.split("\n")
        if any(re.match(r"^\s*(\||[-*+]\s|\d+\.\s)", l) for l in lines):
            units.extend(l for l in lines if l.strip())
        else:
            units.append(para)
    return units


def section(text: str, heading_re: re.Pattern) -> str | None:
    """Text eines `##`-Abschnitts bis zur nächsten `##`-Überschrift."""
    m = heading_re.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def section_line_range(text: str, heading_re: re.Pattern) -> tuple[int, int] | None:
    """(erste, letzte) Zeilennummer (1-basiert) eines Abschnitts inklusive Überschrift."""
    m = heading_re.search(text)
    if not m:
        return None
    start = text.count("\n", 0, m.start()) + 1
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.MULTILINE)
    end = text.count("\n", 0, m.end() + (nxt.start() if nxt else len(rest)))
    return start, max(start, end)


def load_evals_file(path: Path) -> tuple[list[dict] | None, str | None]:
    try:
        data = json.loads(_read(path))
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"nicht lesbar: {exc}"
    evals = data.get("evals") if isinstance(data, dict) else None
    if not isinstance(evals, list):
        return None, "kein Feld `evals` mit einer Liste"
    return evals, None


def _assertions(ev: dict) -> list[dict]:
    out = []
    for key in ("must", "must_not"):
        val = ev.get(key)
        if isinstance(val, list):
            out.extend(a for a in val if isinstance(a, dict))
    return out


# --- Regeln -----------------------------------------------------------------------

def rule_frontmatter(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return RuleResult("frontmatter", "finding", "SKILL.md fehlt")
    fields, _ = split_frontmatter(_read(md))
    if fields is None:
        return RuleResult("frontmatter", "finding", "kein Frontmatter (--- … ---) am Dateianfang")
    missing = [k for k in FRONTMATTER_REQUIRED if not fields.get(k)]
    extra = sorted(set(fields) - FRONTMATTER_ALLOWED)
    if missing or extra:
        parts = []
        if missing:
            parts.append("fehlt: " + ", ".join(missing))
        if extra:
            parts.append("nicht erlaubt (Spec 00 §5): " + ", ".join(extra))
        return RuleResult("frontmatter", "finding", "; ".join(parts))
    return RuleResult("frontmatter", "pass", "name und description, keine fremden Felder")


def rule_skill_md_lines(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return RuleResult("skill-md-lines", "finding", "SKILL.md fehlt")
    n = len(_read(md).splitlines())
    if n > SKILL_MD_MAX_LINES:
        return RuleResult("skill-md-lines", "finding", f"{n} Zeilen, erlaubt {SKILL_MD_MAX_LINES}")
    return RuleResult("skill-md-lines", "pass", f"{n} Zeilen (Grenze {SKILL_MD_MAX_LINES})")


def rule_description(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return RuleResult("description", "finding", "SKILL.md fehlt")
    fields, _ = split_frontmatter(_read(md))
    desc = (fields or {}).get("description", "")
    if not desc:
        return RuleResult("description", "finding", "keine description im Frontmatter")
    problems = []
    if not TRIGGER_RE.search(desc):
        problems.append('kein Trigger („Use when …" oder ein zitierter Auslöser)')
    if not BOUNDARY_RE.search(desc):
        problems.append('keine Abgrenzung („Not for …")')
    verbs = sorted({m.group(1).lower() for m in PROCESS_VERB_RE.finditer(desc)})
    if verbs:
        problems.append("Prozessverben statt Trigger: " + ", ".join(verbs))
    if problems:
        return RuleResult("description", "finding", "; ".join(problems))
    return RuleResult("description", "pass", "Trigger und Abgrenzung, kein Prozessverb")


def rule_gate_language(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return RuleResult("gate-language", "finding", "SKILL.md fehlt")
    if (skill_dir / "assets" / "hooks").is_dir():
        return RuleResult("gate-language", "pass", "assets/hooks/ vorhanden — G3-Wortwahl erlaubt")
    hits = []
    for unit in _units(_read(md)):
        m = GATE_WORD_RE.search(unit)
        if m and not NEGATION_RE.search(unit):
            hits.append(f"„{m.group(1)}\" in: {unit.strip()[:60]!r}")
    if hits:
        return RuleResult("gate-language", "finding",
                          "G3-Wort ohne assets/hooks/ und ohne Negation im Absatz (Spec 00 §4): " + " | ".join(hits))
    return RuleResult("gate-language", "pass", "kein G3-Wort ohne Negation, kein Hook nötig")


def rule_script_tier(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    scripts = sorted((skill_dir / "scripts").glob("*.py")) if (skill_dir / "scripts").is_dir() else []
    if not scripts:
        return RuleResult("script-tier", "pass", "keine Skripte (Tier 0)")
    siblings = {p.stem for p in scripts}
    problems = []
    for script in scripts:
        try:
            tree = ast.parse(_read(script))
        except SyntaxError as exc:
            problems.append(f"{script.name}: SyntaxError {exc.lineno}")
            continue
        m = TIER_RE.search(ast.get_docstring(tree) or "")
        if not m:
            problems.append(f"{script.name}: kein „Tier N\" im Modul-Docstring")
            continue
        if m.group(1) != "1":
            continue
        foreign = set()
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            for name in names:
                top = name.split(".")[0]
                if top not in sys.stdlib_module_names and top not in siblings:
                    foreign.add(top)
        if foreign:
            problems.append(f"{script.name}: Tier 1, importiert aber " + ", ".join(sorted(foreign)))
    if problems:
        return RuleResult("script-tier", "finding", "; ".join(problems))
    return RuleResult("script-tier", "pass", f"{len(scripts)} Skript(e) mit Tier-Deklaration, Tier 1 nur Stdlib")


def _evals_path(skill_dir: Path, repo_root: Path | None) -> Path | None:
    if repo_root is None or not (repo_root / "evals").is_dir():
        return None
    return repo_root / "evals" / skill_dir.name / "evals.json"


def rule_evals_exist(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    path = _evals_path(skill_dir, repo_root)
    if path is None:
        return RuleResult("evals-exist", "unchecked", "evals/ nicht im Workspace")
    if not path.is_file():
        return RuleResult("evals-exist", "finding", f"{path.relative_to(repo_root)} fehlt (Spec 00 §2)")
    evals, err = load_evals_file(path)
    if evals is None:
        return RuleResult("evals-exist", "finding", f"evals.json {err}")
    problems = []
    for i, ev in enumerate(evals):
        where = f"eval[{i}]"
        if not isinstance(ev, dict):
            problems.append(f"{where}: kein Objekt")
            continue
        if not isinstance(ev.get("id"), str) or not ev.get("id"):
            problems.append(f"{where}: id fehlt")
        if ev.get("class") not in EVAL_CLASSES:
            problems.append(f"{where}: class muss contract oder behavior sein")
        if not isinstance(ev.get("prompt"), str) or not ev.get("prompt"):
            problems.append(f"{where}: genau ein prompt als String")
        if not isinstance(ev.get("must"), list):
            problems.append(f"{where}: must fehlt")
    if problems:
        return RuleResult("evals-exist", "finding", "; ".join(problems))
    return RuleResult("evals-exist", "pass", f"{len(evals)} Eval(s), Grundschema vollständig")


def _loaded_evals(skill_dir: Path, repo_root: Path | None, rule_id: str) -> tuple[list[dict] | None, RuleResult | None]:
    path = _evals_path(skill_dir, repo_root)
    if path is None:
        return None, RuleResult(rule_id, "unchecked", "evals/ nicht im Workspace")
    if not path.is_file():
        return None, RuleResult(rule_id, "unchecked", "evals.json fehlt — der Befund steht bei evals-exist")
    evals, err = load_evals_file(path)
    if evals is None:
        return None, RuleResult(rule_id, "unchecked", f"evals.json {err} — der Befund steht bei evals-exist")
    return [e for e in evals if isinstance(e, dict)], None


def rule_anti_ceremony_eval(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    evals, early = _loaded_evals(skill_dir, repo_root, "anti-ceremony-eval")
    if early:
        return early
    ids = [str(e.get("id", "")) for e in evals]
    hits = [i for i in ids if i.startswith(ANTI_CEREMONY_PREFIX)]
    if hits:
        return RuleResult("anti-ceremony-eval", "pass", f"{hits[0]}")
    return RuleResult("anti-ceremony-eval", "finding",
                      f"keine Eval-ID mit Präfix `{ANTI_CEREMONY_PREFIX}` (Spec 00 §2)")


def rule_judge_claims(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    evals, early = _loaded_evals(skill_dir, repo_root, "judge-claims")
    if early:
        return early
    hits = []
    for ev in evals:
        for a in _assertions(ev):
            if a.get("type") == "judge" and isinstance(a.get("claim"), str) and CONJUNCTION_RE.search(a["claim"]):
                hits.append(str(ev.get("id")))
    if hits:
        return RuleResult("judge-claims", "hint",
                          'Konjunktion im Judge-Claim (known-limits „Judge": die Kette ist milder als ihre Teile): '
                          + ", ".join(hits))
    return RuleResult("judge-claims", "pass", "kein Judge-Claim mit Konjunktion")


def rule_fixture_git(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    evals, early = _loaded_evals(skill_dir, repo_root, "fixture-git")
    if early:
        return early
    fixtures_dir = repo_root / "evals" / "fixtures"
    if not fixtures_dir.is_dir():
        return RuleResult("fixture-git", "unchecked", "evals/fixtures/ nicht im Workspace")
    problems = []
    for ev in evals:
        name = ev.get("fixture")
        if not name:
            continue
        fdir = fixtures_dir / str(name)
        if not fdir.is_dir():
            problems.append(f"{ev.get('id')}: Fixture {name} fehlt")
            continue
        if any(a.get("type") == "git_head_unchanged" for a in _assertions(ev)):
            manifest = fdir / "fixture.json"
            wants_git = False
            if manifest.is_file():
                try:
                    wants_git = bool(json.loads(_read(manifest)).get("git", False))
                except json.JSONDecodeError:
                    wants_git = False
            if not wants_git:
                problems.append(f"{ev.get('id')}: git_head_unchanged, aber Fixture {name} ohne \"git\": true")
    if problems:
        return RuleResult("fixture-git", "finding", "; ".join(problems))
    return RuleResult("fixture-git", "pass", "alle Fixtures vorhanden, Git-Vorbedingungen erfüllt")


def rule_asset_headers(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    header_doc = repo_root / "docs" / "artifact-header.md" if repo_root else None
    assets = sorted(p for p in (skill_dir / "assets").rglob("*.md") if p.name != "SKILL.md") \
        if (skill_dir / "assets").is_dir() else []
    if not assets:
        return RuleResult("asset-headers", "pass", "keine Markdown-Assets außer SKILL.md-Gerüsten")
    if header_doc is None or not header_doc.is_file():
        return RuleResult("asset-headers", "unchecked", "docs/artifact-header.md nicht im Workspace")
    exceptions = header_doc.read_text(encoding="utf-8")
    exc_text = exceptions[exceptions.find(EXCEPTION_HEADING):] if EXCEPTION_HEADING in exceptions else ""
    problems = []
    for asset in assets:
        first = next((l.strip() for l in _read(asset).splitlines() if l.strip()), "")
        rel = asset.resolve().relative_to(repo_root.resolve()).as_posix() if asset.resolve().is_relative_to(repo_root.resolve()) else asset.name
        if ARTIFACT_HEADER_RE.match(first) or rel in exc_text or asset.name in exc_text:
            continue
        problems.append(rel)
    if problems:
        return RuleResult("asset-headers", "finding",
                          "ohne Kopfzeile und ohne Ausnahme in docs/artifact-header.md: " + ", ".join(problems))
    return RuleResult("asset-headers", "pass", f"{len(assets)} Asset(s) mit Kopfzeile oder Ausnahme")


def _routing_names(text: str) -> set[str]:
    """Skill-Namen in der Spalte „zuständig" der Routing-Matrix."""
    names: set[str] = set()
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set(cells[1]) <= set("-: "):
            continue
        names.update(re.findall(r"[a-z0-9][a-z0-9-]+", cells[1]))
    return names


def rule_routing(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    if repo_root is None:
        return RuleResult("routing", "unchecked", "README.md und Spec 00 nicht im Workspace")
    files = {"README.md": repo_root / "README.md", "Spec 00 §5": repo_root / "specs" / SPEC00_NAME}
    missing_files = [k for k, p in files.items() if not p.is_file()]
    if missing_files:
        return RuleResult("routing", "unchecked", ", ".join(missing_files) + " nicht im Workspace")
    absent = [k for k, p in files.items() if skill_dir.name not in _routing_names(_read(p))]
    if absent:
        return RuleResult("routing", "finding",
                          f"{skill_dir.name} fehlt in der Spalte „zuständig\" der Routing-Matrix: " + ", ".join(absent))
    return RuleResult("routing", "pass", "in beiden Routing-Matrizen unter „zuständig\"")


def rule_neighbors(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return RuleResult("neighbors", "finding", "SKILL.md fehlt")
    text = section(_read(md), BOUNDARY_HEADING_RE)
    if text is None:
        return RuleResult("neighbors", "unchecked", "kein Abschnitt „## Abgrenzung\" in SKILL.md")
    skills_dir = skill_dir.resolve().parent
    if repo_root is None or not skills_dir.is_dir():
        return RuleResult("neighbors", "unchecked", "Nachbar-Ordner nicht im Workspace")
    siblings = {p.name for p in skills_dir.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()} - {skill_dir.name}
    mentioned = sorted(s for s in siblings if re.search(rf"(?<![a-z0-9-]){re.escape(s)}(?![a-z0-9-])", text))
    if not mentioned:
        return RuleResult("neighbors", "pass", "Abgrenzung nennt keine Skill dieser Sammlung — nichts zu erwidern")
    silent = [s for s in mentioned if skill_dir.name not in _read(skills_dir / s / "SKILL.md")]
    if silent:
        return RuleResult("neighbors", "finding", "genannt, nennt aber nicht zurück: " + ", ".join(silent))
    return RuleResult("neighbors", "pass", "erwidert von: " + ", ".join(mentioned))


def rule_report_section(skill_dir: Path, repo_root: Path | None) -> RuleResult:
    if repo_root is None or not (repo_root / "docs").is_dir():
        return RuleResult("report-section", "unchecked", "docs/ nicht im Workspace")
    name = skill_dir.name
    report = repo_root / "docs" / "superpowers" / "reports" / f"{name}-report.md"
    limits = repo_root / "docs" / "known-limits.md"
    problems = []
    if not report.is_file():
        problems.append(f"docs/superpowers/reports/{name}-report.md fehlt")
    elif not REPORT_SECTION_RE.search(_read(report)):
        problems.append("Report ohne „## Was nicht gemessen wurde\"")
    if not limits.is_file():
        problems.append("docs/known-limits.md fehlt")
    elif not re.search(rf"^## {re.escape(name)}(?![a-z0-9-])", _read(limits), re.MULTILINE):
        problems.append(f"known-limits.md ohne „## {name}\"")
    if problems:
        return RuleResult("report-section", "finding", "; ".join(problems))
    return RuleResult("report-section", "pass", "Report-Pflichtsektion und known-limits-Abschnitt vorhanden")


RULES = [
    ("frontmatter", rule_frontmatter),
    ("skill-md-lines", rule_skill_md_lines),
    ("description", rule_description),
    ("gate-language", rule_gate_language),
    ("script-tier", rule_script_tier),
    ("evals-exist", rule_evals_exist),
    ("anti-ceremony-eval", rule_anti_ceremony_eval),
    ("judge-claims", rule_judge_claims),
    ("fixture-git", rule_fixture_git),
    ("asset-headers", rule_asset_headers),
    ("routing", rule_routing),
    ("neighbors", rule_neighbors),
    ("report-section", rule_report_section),
]
RULE_IDS = tuple(rule_id for rule_id, _ in RULES)


def lint_skill(skill_dir: Path | str, repo_root: Path | str | None = None) -> LintReport:
    """Alle dreizehn Regeln über einen Skill-Ordner. `repo_root=None` heißt: selbst
    suchen; wird keine gefunden, sind die Repo-Regeln `unchecked`."""
    skill_dir = Path(skill_dir)
    root = Path(repo_root) if repo_root is not None else find_repo_root(skill_dir)
    rules = [fn(skill_dir, root) for _, fn in RULES]
    return LintReport(skill_dir.name, skill_dir, root, rules)


# --- Diff-Modus -------------------------------------------------------------------

class DiffError(RuntimeError):
    """Kein Diff-Modus möglich: kein Git, unbekannte Revision, Ordner nicht im Repo."""


def _git(repo_root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False)
    except OSError as exc:
        raise DiffError(f"git nicht ausführbar: {exc}") from exc
    if proc.returncode != 0:
        raise DiffError(f"git {' '.join(args[:2])}: {proc.stderr.strip()[:120]}")
    return proc.stdout


def lint_at_base(skill_dir: Path | str, repo_root: Path | str, rev: str) -> LintReport:
    """Der Skill-Ordner, wie er bei `rev` war, gelintet gegen das heutige Repo. Nur der
    Ordner kommt aus Git; `docs/`, `evals/` und Nachbarn sind der Arbeitsstand — die
    Frage lautet „hat *diese Änderung* etwas gebrochen", nicht „wie sah das Repo aus"."""
    skill_dir, repo_root = Path(skill_dir).resolve(), Path(repo_root).resolve()
    if not skill_dir.is_relative_to(repo_root):
        raise DiffError(f"{skill_dir} liegt nicht unter {repo_root}")
    rel = skill_dir.relative_to(repo_root).as_posix()
    listing = _git(repo_root, "ls-tree", "-r", "--name-only", rev, "--", rel)
    with tempfile.TemporaryDirectory() as tmp:
        base_dir = Path(tmp) / rel
        for path in listing.split("\n"):
            if not path.strip():
                continue
            content = _git(repo_root, "show", f"{rev}:{path}")
            target = Path(tmp) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        if not base_dir.is_dir():
            raise DiffError(f"{rel} existiert bei {rev} nicht — keine Basis, alle Befunde sind neu")
        # Regeln, die den Repo-Kontext brauchen, sehen das echte Repo; Regeln über den
        # Ordner selbst sehen den Basisstand. `neighbors` schaut in `skill_dir.parent`
        # — dafür liegt der Basisordner an derselben relativen Stelle unter tmp.
        base_rules = lint_skill(base_dir, repo_root)
    return base_rules


def _changed_lines(repo_root: Path, rev: str, skill_dir: Path) -> tuple[list[str], dict[str, list[int]], dict[str, list[int]]]:
    """Geänderte Zeilen aus `git diff rev -- skill_dir`: (Texte, neue Zeilennummern je
    Datei, alte Zeilennummern je Datei)."""
    rel = skill_dir.resolve().relative_to(repo_root.resolve()).as_posix()
    diff = _git(repo_root, "diff", rev, "--", rel)
    texts: list[str] = []
    new_lines: dict[str, list[int]] = {}
    old_lines: dict[str, list[int]] = {}
    current: str | None = None
    old_no = new_no = 0
    for line in diff.split("\n"):
        if line.startswith("+++ "):
            current = line[4:].removeprefix("b/").strip()
            continue
        if line.startswith("--- ") or line.startswith("diff ") or line.startswith("index "):
            continue
        hunk = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk:
            old_no, new_no = int(hunk.group(1)), int(hunk.group(2))
            continue
        if current is None:
            continue
        if line.startswith("+"):
            texts.append(line[1:])
            new_lines.setdefault(current, []).append(new_no)
            new_no += 1
        elif line.startswith("-"):
            texts.append(line[1:])
            old_lines.setdefault(current, []).append(old_no)
            old_no += 1
        elif line.startswith("\\"):
            continue
        else:
            old_no += 1
            new_no += 1
    return texts, new_lines, old_lines


def _protected_ranges(text: str) -> list[tuple[int, int]]:
    ranges = []
    fields, end = split_frontmatter(text)
    if fields is not None:
        ranges.append((1, end))
    contract = section_line_range(text, CONTRACT_HEADING_RE)
    if contract:
        ranges.append(contract)
    return ranges


def evals_due(diff_lines: list[str], skill_dir: Path | str, repo_root: Path | str | None = None,
              rev: str | None = None) -> tuple[bool | str, str]:
    """(true/false/'unchecked', Grund). Mit `repo_root` und `rev` werden Frontmatter- und
    Contract-Bereich per Zeilennummer geprüft; ohne beides nur die Pattern-Treffer
    auf den Zeilentexten."""
    skill_dir = Path(skill_dir)
    root = Path(repo_root) if repo_root else find_repo_root(skill_dir)
    evals_path = _evals_path(skill_dir, root)
    reasons = []
    if evals_path is None or not evals_path.is_file():
        return "unchecked", "keine evals.json — ohne Assertions ist nicht bestimmbar, was eine Eval-relevante Änderung ist"
    evals, err = load_evals_file(evals_path)
    if evals is None:
        return "unchecked", f"evals.json {err}"
    patterns = []
    for ev in evals:
        if isinstance(ev, dict):
            for a in _assertions(ev):
                if a.get("type") in PATTERN_TYPES and isinstance(a.get("pattern"), str):
                    patterns.append(a["pattern"])
    md = skill_dir / "SKILL.md"
    if root is not None and rev is not None and md.is_file():
        _, new_nos, old_nos = _changed_lines(root, rev, skill_dir)
        rel_md = md.resolve().relative_to(root.resolve()).as_posix()
        current_ranges = _protected_ranges(_read(md))
        try:
            base_text = _git(root, "show", f"{rev}:{rel_md}")
        except DiffError:
            base_text = ""
        base_ranges = _protected_ranges(base_text)
        for nos, ranges, label in ((new_nos.get(rel_md, []), current_ranges, "neu"), (old_nos.get(rel_md, []), base_ranges, "alt")):
            for no in nos:
                for start, end in ranges:
                    if start <= no <= end:
                        what = "Frontmatter" if start == 1 else "Contract-Abschnitt"
                        reasons.append(f"{what} geändert (Zeile {no}, {label})")
                        break
        if not CONTRACT_HEADING_RE.search(_read(md)):
            reasons.append("Hinweis: kein Abschnitt „## … Contract\" in SKILL.md — nur Frontmatter und Patterns geprüft")
    for line in diff_lines:
        for pattern in patterns:
            try:
                if re.search(pattern, line):
                    reasons.append(f"Pattern {pattern!r} trifft geänderte Zeile {line.strip()[:50]!r}")
                    break
            except re.error:
                continue
    due = any(not r.startswith("Hinweis") for r in reasons)
    if not reasons:
        return False, f"keine Änderung an Frontmatter, Contract oder einer Zeile, auf die eines von {len(patterns)} Patterns greift"
    return due, "; ".join(reasons)


# --- Artefakt und CLI -------------------------------------------------------------

def lint_meta(skill_dir: Path | str, base: str | None = None) -> dict:
    cmd = f"python skills/skill-forge/scripts/lint_skill.py {shlex.quote(str(skill_dir))}"
    if base:
        cmd += f" --base {shlex.quote(base)}"
    return {"skill": "skill-forge", "schema": SCHEMA_VERSION, "generated": cmd}


def render_lint_json(report: LintReport, meta: dict, *, findings_mode: str = "all",
                     findings_at_base: list[str] | None = None, new_findings: list[str] | None = None,
                     evals_due_value: bool | str = "unchecked", evals_due_reason: str = "kein --base") -> str:
    """Jede Regel eine Zeile in fester Reihenfolge id, status, reason — der Vertrag für
    `file_matches` in den Evals. Deshalb von Hand gesetzt statt `json.dumps(indent=2)`."""
    head = {
        "_meta": meta,
        "skill": report.skill,
        "skill_dir": str(report.skill_dir),
        "repo_root": str(report.repo_root) if report.repo_root else None,
        "findings_mode": findings_mode,
        "findings_at_base": findings_at_base,
        "new_findings": new_findings if new_findings is not None else [r.id for r in report.findings],
        "evals_due": evals_due_value,
        "evals_due_reason": evals_due_reason,
        "summary": report.summary(),
    }
    lines = ["{"]
    for key, value in head.items():
        lines.append(f"  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)},")
    lines.append('  "rules": [')
    rule_lines = [f"    {json.dumps(r.as_dict(), ensure_ascii=False)}" for r in report.rules]
    lines.append(",\n".join(rule_lines))
    lines.append("  ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Skill-Ordner gegen die Hausmethode prüfen (Spec 17)")
    parser.add_argument("skill_dir", help="Pfad zum Skill-Ordner, z. B. skills/handoff")
    parser.add_argument("--base", help="Git-Revision: nur Befunde zählen, die gegenüber diesem Stand neu sind; liefert evals_due")
    parser.add_argument("--repo-root", help="Repo-Wurzel, sonst gesucht (nächster Elternordner mit specs/ oder evals/)")
    parser.add_argument("--out", help="lint.json zusätzlich schreiben")
    args = parser.parse_args(argv)

    skill_dir = Path(args.skill_dir)
    if not skill_dir.is_dir():
        print(f"Skill-Ordner nicht lesbar: {skill_dir}", file=sys.stderr)
        return 2
    report = lint_skill(skill_dir, args.repo_root)

    findings_mode, at_base, new_ids = "all", None, [r.id for r in report.findings]
    due, due_reason = "unchecked", "kein --base — evals_due nicht bestimmbar"
    if args.base:
        if report.repo_root is None:
            print("Diff-Modus braucht eine Repo-Wurzel (specs/ oder evals/ über dem Skill-Ordner)", file=sys.stderr)
            return 2
        try:
            base_report = lint_at_base(skill_dir, report.repo_root, args.base)
            texts, _, _ = _changed_lines(report.repo_root, args.base, skill_dir)
            due, due_reason = evals_due(texts, skill_dir, report.repo_root, args.base)
        except DiffError as exc:
            print(f"Diff-Modus nicht möglich: {exc}", file=sys.stderr)
            return 2
        findings_mode = "new-vs-base"
        at_base = [r.id for r in base_report.findings]
        new_ids = [r.id for r in report.findings if r.id not in at_base]

    for r in report.rules:
        print(f"[{r.status.upper():9}] {r.id}: {r.reason}")
    if findings_mode == "new-vs-base":
        print(f"Diff-Modus gegen {args.base}: {len(at_base)} Befund(e) an der Basis, {len(new_ids)} neu"
              + (": " + ", ".join(new_ids) if new_ids else ""))
    print(f"evals_due: {due} — {due_reason}")
    unchecked = [r.id for r in report.rules if r.status == "unchecked"]
    if unchecked:
        print("UNGEPRÜFT (nicht bestanden, nicht gescheitert): " + ", ".join(unchecked))
    print("Ergebnis: " + ("Befunde — " + ", ".join(new_ids) if new_ids else "kein neuer Befund"))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_lint_json(
            report, lint_meta(skill_dir, args.base), findings_mode=findings_mode,
            findings_at_base=at_base, new_findings=new_ids, evals_due_value=due, evals_due_reason=due_reason,
        ), encoding="utf-8")
    return 1 if new_ids else 0


if __name__ == "__main__":
    sys.exit(main())
