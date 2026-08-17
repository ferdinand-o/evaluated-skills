#!/usr/bin/env python3
"""Plan -> Tasks für subagent-dev. Tier 1: nur Stdlib.

`generate` parst einen superpowers:writing-plans-Plan, baut die Datei- und
Interface-Überlappungsmatrix, fällt ein Gate-Urteil (parallel/sequenziell/keine
Delegation) und schreibt pro Task eine Handoff-Datei nach `.skills/cache/tasks/`.

`verify` prüft nach einem Dispatch mechanisch, ob ein Agent innerhalb seiner
Datei-Allowlist geblieben ist und ob die deklarierten `Produces`-Signaturen im
Ergebnis auftauchen. Fremder Code wird dafür nie importiert, nur mit `ast`
statisch gelesen (Vorab-Entscheidung A3).

Überlappung ist konservativ: Was nicht sicher ausgeschlossen werden kann, gilt
als Abhängigkeit (Vorab-Entscheidung B2) — ein übersehener Konflikt zerstört
Arbeitsstand, eine überflüssige Serialisierung kostet nur Zeit.
"""

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = 1
PARALLEL_THRESHOLD = 3

TASK_HEADER_RE = re.compile(r"^### Task (\d+):\s*(.+?)\s*$", re.MULTILINE)
FILE_LINE_RE = re.compile(r"^-\s*(?:Create|Modify|Test|Delete):\s*`([^`]+)`", re.MULTILINE)
RENAME_LINE_RE = re.compile(r"^-\s*Rename:\s*`([^`]+)`\s*->\s*`([^`]+)`", re.MULTILINE)
# Jede Bullet-Zeile im Files:-Block — dient als Sicherheitsnetz: Was hier eine
# Zeile mehr zählt als FILE_LINE_RE/RENAME_LINE_RE zusammen erkannt haben, ist
# eine Zeile, deren Vokabular der Parser nicht kennt (Fix D2).
BULLET_LINE_RE = re.compile(r"^-\s*.+$", re.MULTILINE)
LINE_RANGE_RE = re.compile(r"^(?P<path>.+?)(?::\d+(?:-\d+)?)?$")
STEP_RE = re.compile(r"^-\s*\[[ xX]\]\s*\*\*(Step \d+:[^*]*)\*\*", re.MULTILINE)
# Backtick-Symbol mit Klammern (Funktion/Methode) — Name vor der ersten "(".
CALLABLE_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*)\(([^)]*)\)")
# Backtick-Symbol ohne Klammern (Klasse/Konstante) — nur, falls es kein
# Dateipfad ist (keine "/", keine bekannte Dateiendung).
BARE_SYMBOL_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*)`")
FILE_LIKE_SUFFIXES = (".py", ".md", ".json", ".yaml", ".yml", ".txt", ".sh")
# "Consumes:"/"Produces:" ohne Backtick-Symbol, aber auch keine echte Prosa —
# der explizite Leerfall, den der Plan selbst so benennt.
NOTHING_NEW_RE = re.compile(r"^\(?nichts neues\)?\.?$", re.IGNORECASE)
# Pfad-Segmente, die ein Glob-Muster statt eines konkreten Pfads markieren.
GLOB_CHARS = frozenset("*?[")


class PlanParseError(ValueError):
    """Der Plan-Text folgt nicht dem superpowers:writing-plans-Format genug, um sicher geparst zu werden."""


@dataclass(frozen=True)
class FileRef:
    raw: str
    path: str


@dataclass(frozen=True)
class PlanTask:
    id: int
    title: str
    files: list[FileRef]
    files_unknown: bool
    consumes: str
    produces: str
    interfaces_unknown: bool
    steps: list[str]


@dataclass(frozen=True)
class PlanDoc:
    global_constraints: str
    tasks: list[PlanTask]


@dataclass(frozen=True)
class GateResult:
    verdict: str  # "parallel" | "sequential" | "no-delegate"
    parallel_group: list[int]
    reasoning: str
    components: list[list[int]] = field(default_factory=list)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def _mask_fenced_blocks(text: str) -> str:
    """Blende Zeilen innerhalb von ```-Codezäunen aus (gleiche Länge, gleiche
    Zeilenzahl, damit alle Offsets im Rest des Parsers gültig bleiben).

    Ein Plan, der (wie dieser hier) Beispiel-Pläne als Codeblock zitiert, hätte
    sonst verschachtelte `### Task N:`-, `**Files:**`- oder `- [ ]`-Zeilen, die
    der Parser für echte Plan-Struktur hält. Ohne Maskierung wäre das ein
    stiller Fehlschlag (doppelte Task-IDs oder falsch geparste Sektionen),
    keine Fehlermeldung — genau der Fall, den A4 verbietet.
    """
    lines = text.split("\n")
    in_fence = False
    out: list[str] = []
    for line in lines:
        if line.lstrip().startswith("```"):
            out.append(line)
            in_fence = not in_fence
            continue
        out.append(" " * len(line) if in_fence else line)
    return "\n".join(out)


def _section(block: str, start_marker: str, end_markers: tuple[str, ...]) -> str:
    """Text zwischen `start_marker` und dem nächsten der `end_markers` (oder Blockende)."""
    start = block.find(start_marker)
    if start == -1:
        return ""
    start += len(start_marker)
    end = len(block)
    for marker in end_markers:
        pos = block.find(marker, start)
        if pos != -1:
            end = min(end, pos)
    return block[start:end].strip("\n")


def _strip_range(raw: str) -> str:
    match = LINE_RANGE_RE.match(raw)
    return match.group("path") if match else raw


def _parse_files(block: str) -> tuple[list[FileRef], bool]:
    """Files:-Block parsen. `files_unknown=True`, sobald auch nur eine Bullet-
    Zeile im Block keinem bekannten Muster entspricht (Fix D2) — nicht nur bei
    einem komplett leeren Block. Eine Zeile, die der Plan-Autor mit eigenem
    Vokabular schreibt (z. B. ein selbst erfundenes `Rename:`, ein Tippfehler),
    verschwindet sonst spurlos statt die Task als unsicher zu markieren.
    """
    files_text = _section(block, "**Files:**", ("**Interfaces:**", "\n- [ ]", "\n- [x]", "\n- [X]"))

    refs: list[FileRef] = []
    matched_lines = 0

    for raw in FILE_LINE_RE.findall(files_text):
        refs.append(FileRef(raw=raw, path=_strip_range(raw)))
        matched_lines += 1

    for old_raw, new_raw in RENAME_LINE_RE.findall(files_text):
        # Ein Rename betrifft zwei Pfade — beide gehören in die Allowlist und
        # in die Überlappungsprüfung; wer die alte ODER die neue Datei anfasst,
        # kollidiert mit diesem Task.
        refs.append(FileRef(raw=old_raw, path=_strip_range(old_raw)))
        refs.append(FileRef(raw=new_raw, path=_strip_range(new_raw)))
        matched_lines += 1

    total_lines = len(BULLET_LINE_RE.findall(files_text))
    unparsed_lines_exist = matched_lines < total_lines
    files_unknown = len(refs) == 0 or unparsed_lines_exist
    return refs, files_unknown


def _has_unrecognized_prose(text: str) -> bool:
    """True, wenn `text` etwas außer Backtick-Symbolen oder dem expliziten
    Leerfall "nichts Neues" enthält — Prosa, aus der `extract_produced_symbols`
    kein Symbol ziehen kann, aber die trotzdem eine echte Abhängigkeit benennen
    könnte (Fix D3). Enthält der Text ein Backtick, gilt er als geparst, auch
    wenn drumherum Prosa steht — sonst wäre "Consumes: `parse()` aus Task 1"
    fälschlich unbekannt, obwohl das Symbol explizit genannt und erkannt wird.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if NOTHING_NEW_RE.match(stripped):
        return False
    return "`" not in stripped


def _parse_interfaces(block: str) -> tuple[str, str, bool]:
    text = _section(block, "**Interfaces:**", ("\n- [ ]", "\n- [x]", "\n- [X]"))
    consumes = ""
    produces = ""
    consumes_start = text.find("- Consumes:")
    produces_start = text.find("- Produces:")
    if consumes_start != -1:
        end = produces_start if produces_start > consumes_start else len(text)
        consumes = text[consumes_start + len("- Consumes:"):end].strip()
    if produces_start != -1:
        produces = text[produces_start + len("- Produces:"):].strip()
    interfaces_unknown = _has_unrecognized_prose(consumes) or _has_unrecognized_prose(produces)
    return consumes, produces, interfaces_unknown


def _parse_steps(block: str) -> list[str]:
    return [m.strip() for m in STEP_RE.findall(block)]


def parse_plan(text: str) -> PlanDoc:
    """Parse einen superpowers:writing-plans-Plan in `PlanDoc`.

    Wirft `PlanParseError`, wenn kein einziger `### Task N:`-Header gefunden
    wird — ein leerer Task-Zerlegung wäre sonst ein stiller Erfolg über einem
    Plan, den der Parser gar nicht verstanden hat (Vorab-Entscheidung A4).

    Zitierte Beispiel-Pläne in ```-Codeblöcken (wie in diesem Plan selbst)
    werden vor jeder Struktur-Erkennung ausmaskiert — siehe `_mask_fenced_blocks`.
    """
    text = _mask_fenced_blocks(text)
    headers = list(TASK_HEADER_RE.finditer(text))
    if not headers:
        raise PlanParseError(
            "kein einziger '### Task N: Titel'-Header gefunden — ist das ein "
            "superpowers:writing-plans-Plan?"
        )

    gc_start = text.find("## Global Constraints")
    global_constraints = ""
    if gc_start != -1:
        gc_end = len(text)
        for marker in ("\n## ", "\n---"):
            pos = text.find(marker, gc_start + len("## Global Constraints"))
            if pos != -1:
                gc_end = min(gc_end, pos)
        global_constraints = text[gc_start:gc_end].strip()
        # Die eigene "## Global Constraints"-Überschrift wird nicht mitkopiert —
        # render_task_file setzt bereits eine eigene Überschrift darüber.
        global_constraints = global_constraints[len("## Global Constraints"):].strip("\n")

    tasks: list[PlanTask] = []
    for i, header in enumerate(headers):
        block_start = header.end()
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[block_start:block_end]
        task_id = int(header.group(1))
        title = header.group(2)
        files, files_unknown = _parse_files(block)
        consumes, produces, interfaces_unknown = _parse_interfaces(block)
        steps = _parse_steps(block)
        tasks.append(PlanTask(
            id=task_id, title=title, files=files, files_unknown=files_unknown,
            consumes=consumes, produces=produces, interfaces_unknown=interfaces_unknown,
            steps=steps,
        ))

    seen: set[int] = set()
    for t in tasks:
        if t.id in seen:
            raise PlanParseError(f"Task-ID {t.id} ist im Plan doppelt vergeben")
        seen.add(t.id)

    return PlanDoc(global_constraints=global_constraints, tasks=tasks)


# --------------------------------------------------------------------------
# Überlappungsmatrix
# --------------------------------------------------------------------------


def _normalize_parts(path: str) -> tuple[str, ...]:
    """Pfad-Segmente für den Überlappungsvergleich: Backslashes zu Slashes
    (Windows-Schreibweise, D2), kleingeschrieben (Groß-/Kleinschreibungs-
    Drift zwischen zwei Plan-Autoren, D2), führendes `/` entfernt — ein
    absoluter Pfad wird dadurch mit einem relativen vergleichbar, siehe
    `_paths_overlap`s Suffix-Prüfung.
    """
    normalized = path.strip().rstrip("/").replace("\\", "/").lower()
    return PurePosixPath(normalized).parts


def _glob_root(parts: tuple[str, ...]) -> tuple[str, ...]:
    """Der konkrete Präfix eines Pfads vor dem ersten Glob-Segment.

    `src/**/*.py` und `src/*.py` liefern beide `("src",)`: Ohne Dateisystem-
    Zugriff kann nicht sicher ausgeschlossen werden, was ein Glob trifft —
    konservativ gilt deshalb sein ganzer Wurzel-Ordner als betroffen (B2).
    """
    root: list[str] = []
    for part in parts:
        if any(c in part for c in GLOB_CHARS):
            break
        root.append(part)
    return tuple(root)


def _paths_overlap(a: str, b: str) -> bool:
    pa, pb = _normalize_parts(a), _normalize_parts(b)
    if any(c in seg for seg in pa for c in GLOB_CHARS):
        pa = _glob_root(pa)
    if any(c in seg for seg in pb for c in GLOB_CHARS):
        pb = _glob_root(pb)
    if not pa or not pb:
        return False
    shorter, longer = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    # Verzeichnis-Präfix (eine Task nennt einen Ordner, die andere eine Datei
    # darin) ODER Suffix (ein absoluter Pfad endet auf denselben relativen
    # Pfad wie die andere Task) — beide Richtungen zählen als Überlappung.
    return longer[: len(shorter)] == shorter or longer[len(longer) - len(shorter):] == shorter


def extract_produced_symbols(text: str) -> list[tuple[str, int | None]]:
    """Name + Arity aus \\`name(a, b)\\`-Backtick-Spans; bloße Symbole ohne Klammern
    (Klassen, Konstanten) liefern Arity `None` — nur Präsenz wird geprüft."""
    symbols: list[tuple[str, int | None]] = []
    seen_names: set[str] = set()
    for name, args in CALLABLE_RE.findall(text):
        args = args.strip()
        arity = 0 if not args else len([a for a in args.split(",") if a.strip()])
        symbols.append((name, arity))
        seen_names.add(name)
    for name in BARE_SYMBOL_RE.findall(text):
        if name in seen_names:
            continue
        if "/" in name or any(name.endswith(suf) for suf in FILE_LIKE_SUFFIXES):
            continue
        symbols.append((name, None))
        seen_names.add(name)
    return symbols


def _interface_dependency(producer: PlanTask, consumer: PlanTask) -> str | None:
    """Name des Symbols, falls `consumer` etwas konsumiert, das `producer` produziert."""
    for name, _ in extract_produced_symbols(producer.produces):
        if re.search(rf"\b{re.escape(name)}\b", consumer.consumes):
            return name
    return None


def build_overlap_graph(tasks: list[PlanTask]) -> dict[int, set[int]]:
    """Task-ID -> Menge der Task-IDs, mit denen sie nicht parallel laufen darf."""
    overlap: dict[int, set[int]] = {t.id: set() for t in tasks}

    for i, ta in enumerate(tasks):
        for tb in tasks[i + 1:]:
            reason = False

            if ta.files_unknown or tb.files_unknown:
                reason = True
            else:
                for fa in ta.files:
                    for fb in tb.files:
                        if _paths_overlap(fa.path, fb.path):
                            reason = True
                            break
                    if reason:
                        break

            if not reason:
                if ta.interfaces_unknown or tb.interfaces_unknown:
                    # Prosa ohne Backtick-Symbol in Consumes:/Produces: könnte eine
                    # echte Abhängigkeit benennen, die der Parser nicht lesen kann
                    # (Fix D3) — konservativ überlappt eine solche Task mit jeder
                    # anderen, statt stillschweigend "keine Überlappung" zu urteilen.
                    reason = True
                elif _interface_dependency(ta, tb) or _interface_dependency(tb, ta):
                    reason = True

            if reason:
                overlap[ta.id].add(tb.id)
                overlap[tb.id].add(ta.id)

    return overlap


def _connected_components(task_ids: list[int], overlap: dict[int, set[int]]) -> list[list[int]]:
    remaining = set(task_ids)
    components: list[list[int]] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        component: set[int] = set()
        while stack:
            node = stack.pop()
            if node in component or node not in remaining:
                continue
            component.add(node)
            stack.extend(overlap.get(node, set()) & remaining)
        components.append(sorted(component))
        remaining -= component
    return sorted(components, key=lambda c: c[0])


def gate_verdict(tasks: list[PlanTask], overlap: dict[int, set[int]]) -> GateResult:
    """Fälle das Delegations-Urteil über genau die übergebene Task-Menge.

    Auch "keine Delegation" ist ein Ergebnis mit Begründung, kein Fehlschlag.
    """
    task_ids = [t.id for t in tasks]
    components = _connected_components(task_ids, overlap)
    singletons = [c[0] for c in components if len(c) == 1]
    multi = [c for c in components if len(c) > 1]

    if len(task_ids) < 2:
        return GateResult(
            verdict="no-delegate",
            parallel_group=[],
            reasoning=(
                f"Nur {len(task_ids)} Task(s) betrachtet — für Delegation braucht es "
                "mehr als einen Task."
            ),
            components=components,
        )

    if len(singletons) >= PARALLEL_THRESHOLD:
        blocked = [tid for c in multi for tid in c]
        reasoning = (
            f"{len(singletons)} Tasks ohne erkannte Datei- oder Interface-Überlappung "
            f"(Tasks {singletons}) — ab der Schwelle von {PARALLEL_THRESHOLD} lohnt "
            "sich Parallelisierung. "
        )
        if blocked:
            reasoning += (
                f"Tasks {blocked} überlappen erkennbar mit mindestens einer anderen "
                "Task und bleiben sequenziell bzw. im Hauptkontext."
            )
        else:
            reasoning += "Keine der geprüften Datei- oder Interface-Signale zeigt eine Überlappung."
        return GateResult(
            verdict="parallel", parallel_group=sorted(singletons), reasoning=reasoning,
            components=components,
        )

    if multi:
        # Mindestens ein Paar Tasks ist über Datei oder Interface gekoppelt —
        # diese Kopplung erzwingt eine Reihenfolge, unabhängig von der
        # Parallel-Schwelle. Sequenzieller Dispatch bleibt sinnvoll, nur eben
        # nicht gleichzeitig.
        reasoning = (
            f"Nur {len(singletons)} von {len(task_ids)} Tasks sind ohne erkannte "
            f"Überlappung — das liegt unter der Schwelle von {PARALLEL_THRESHOLD} "
            f"parallel-fähigen Paketen. Tasks {[tid for c in multi for tid in c]} sind "
            "über eine erkannte Datei- oder Interface-Überlappung gekoppelt (oder als "
            "unsicher markiert, siehe files_unknown/interfaces_unknown) und müssen in "
            "dieser Reihenfolge laufen — sequenzieller Dispatch statt Parallelisierung."
        )
        return GateResult(verdict="sequential", parallel_group=[], reasoning=reasoning, components=components)

    # Alle Tasks sind zwar ohne erkannte Überlappung (jede für sich parallel-
    # sicher), aber es sind zu wenige, um den Dispatch-Overhead zu
    # rechtfertigen — und nichts zwingt eine Reihenfolge. Delegation lohnt
    # sich hier nicht.
    reasoning = (
        f"{len(singletons)} Tasks, keine mit erkannter Datei- oder Interface-"
        f"Überlappung — das liegt unter der Schwelle von {PARALLEL_THRESHOLD} "
        "parallel-fähigen Paketen, und nichts erzwingt eine Reihenfolge. Delegation "
        "lohnt sich hier nicht; im Hauptkontext oder ohne Subagenten erledigen."
    )
    return GateResult(verdict="no-delegate", parallel_group=[], reasoning=reasoning, components=components)


# --------------------------------------------------------------------------
# Task-Dateien
# --------------------------------------------------------------------------


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "task"


def _header(command: str) -> str:
    return f"<!-- skill: subagent-dev | schema: {SCHEMA_VERSION} | generated: {command} -->"


def render_task_file(task: PlanTask, doc: PlanDoc, plan_path: str) -> str:
    allowlist = [f.path for f in task.files]
    produces = extract_produced_symbols(task.produces)
    others = [f"Task {t.id} – {t.title}" for t in doc.tasks if t.id != task.id]

    allowlist_md = "\n".join(f"- `{p}`" for p in allowlist) if allowlist else (
        "- (keine geparst — Allowlist unklar, gilt als leer und damit als riskant)"
    )
    steps_md = "\n".join(f"- {s}" for s in task.steps) if task.steps else "- (keine Steps im Plan gefunden)"
    others_md = "\n".join(f"- {o}" for o in others) if others else "- (keine weiteren Tasks in diesem Plan)"

    machine_block = {
        "task_id": task.id,
        "plan": plan_path,
        "allowlist": allowlist,
        "produces": [{"name": n, "arity": a} for n, a in produces],
    }

    return (
        f"{_header(f'python skills/subagent-dev/scripts/plan_to_tasks.py generate {plan_path}')}\n\n"
        f"# Task {task.id}: {task.title}\n\n"
        f"## Ziel\n\n{task.title}\n\n"
        f"## Datei-Allowlist\n\n"
        f"Außerhalb dieser Dateien wird nicht geschrieben:\n\n{allowlist_md}\n\n"
        f"## Interfaces\n\n"
        f"- Consumes: {task.consumes or '(nichts Neues)'}\n"
        f"- Produces: {task.produces or '(nichts Neues)'}\n\n"
        f"## Akzeptanzkriterien\n\n{steps_md}\n\n"
        f"## Global Constraints\n\n{doc.global_constraints or '(keine im Plan gefunden)'}\n\n"
        f"## Nicht-Ziele\n\n"
        f"Alles außerhalb der Datei-Allowlist oben. Andere Tasks dieses Plans "
        f"gehören nicht hierher:\n\n{others_md}\n\n"
        f"```json\n{json.dumps(machine_block, indent=2, ensure_ascii=False)}\n```\n"
    )


def parse_task_machine_block(text: str) -> dict:
    match = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
    if not match:
        raise PlanParseError("Task-Datei enthält keinen ```json-Maschinenblock")
    return json.loads(match.group(1))


def write_tasks(doc: PlanDoc, plan_path: str, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    if not out_dir.exists():
        print(f"Lege {out_dir} an (erster Lauf)")
    out_dir.mkdir(parents=True, exist_ok=True)

    overlap = build_overlap_graph(doc.tasks)
    gate = gate_verdict(doc.tasks, overlap)

    gate_payload = {
        "_meta": {
            "skill": "subagent-dev",
            "schema": SCHEMA_VERSION,
            "generated": f"python skills/subagent-dev/scripts/plan_to_tasks.py generate {plan_path}",
        },
        "plan": plan_path,
        "tasks": [
            {
                "id": t.id, "title": t.title, "files": [f.path for f in t.files],
                "files_unknown": t.files_unknown, "interfaces_unknown": t.interfaces_unknown,
            }
            for t in doc.tasks
        ],
        "overlap": {str(k): sorted(v) for k, v in overlap.items()},
        "verdict": gate.verdict,
        "parallel_group": gate.parallel_group,
        "reasoning": gate.reasoning,
        "components": gate.components,
    }
    (out_dir / "gate.json").write_text(json.dumps(gate_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    task_files: dict[int, Path] = {}
    for task in doc.tasks:
        rendered = render_task_file(task, doc, plan_path)
        target = out_dir / f"task-{task.id}-{_slug(task.title)}.md"
        target.write_text(rendered, encoding="utf-8")
        task_files[task.id] = target

    return {"gate": gate, "task_files": task_files}


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------


def _git(worktree: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=worktree, capture_output=True, text=True, timeout=60, check=False,
    )
    if done.returncode != 0:
        raise PlanParseError(f"git {' '.join(args)} fehlgeschlagen: {done.stderr.strip()}")
    return done.stdout


def check_allowlist(worktree: Path, base_ref: str, allowlist: list[str]) -> list[str]:
    """Geänderte Dateien (committed seit `base_ref` und uncommittete), die außerhalb
    der Allowlist liegen — exakte, Verzeichnis-Präfix- oder Suffix-Treffer
    (siehe `_paths_overlap`) zählen als erlaubt."""
    committed = _git(worktree, "diff", "--name-only", f"{base_ref}...HEAD").splitlines()
    dirty = _git(worktree, "status", "--porcelain").splitlines()

    dirty_paths: list[str] = []
    for line in dirty:
        if not line.strip():
            continue
        body = line[3:].strip()
        if " -> " in body:
            # `git status --porcelain` schreibt eine (auch nur staged, nicht
            # committete) Umbenennung als "alt.py -> neu.py" in einer Zeile
            # (L3). Ungeteilt übernommen wäre das ein Pfad, der weder alt noch
            # neu ist und mit keinem Allowlist-Eintrag matchen kann — ein
            # Fehlalarm gegen einen Task, der sich an seine Allowlist hielt.
            old_path, _, new_path = body.partition(" -> ")
            dirty_paths.append(old_path.strip())
            dirty_paths.append(new_path.strip())
        else:
            dirty_paths.append(body)

    changed = sorted({*committed, *dirty_paths} - {""})
    return [path for path in changed if not any(_paths_overlap(path, allowed) for allowed in allowlist)]


def check_produces(worktree: Path, allowlist: list[str], produces: list[tuple[str, int | None]]) -> list[dict]:
    """Prüfe deklarierte Produces-Symbole per `ast` gegen die Allowlist-Dateien.

    Nie ein Import — fremder Code aus einem gerade dispatchten Agenten wird
    ausschließlich statisch gelesen (Vorab-Entscheidung A3).

    `ast.walk` kennt keinen Scope — zwei gleichnamige, fachlich unabhängige
    Definitionen (Top-Level-Funktion + verschachtelte Hilfsfunktion, oder
    gleichnamige Methoden zweier Klassen) sind über den ganzen Baum hinweg
    nicht unterscheidbar. Statt die zuletzt gefundene Definition stillschweigend
    gewinnen zu lassen (L2), werden alle Arities gesammelt: Passt mindestens
    eine zur erwarteten, gilt das Symbol als vorhanden; passt keine, aber es
    gibt mehrere unterschiedliche Definitionen, ist das Ergebnis `ambiguous`
    statt eines geratenen PASS oder FAIL.
    """
    found: dict[str, list[int]] = {}
    for relpath in allowlist:
        path = worktree / relpath
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args.args
                if args and args[0].arg in ("self", "cls"):
                    args = args[1:]
                found.setdefault(node.name, []).append(len(args))
            elif isinstance(node, ast.ClassDef):
                found.setdefault(node.name, []).append(-1)  # -1: keine Arity, nur Präsenz

    results: list[dict] = []
    for name, expected_arity in produces:
        if name not in found:
            results.append({"name": name, "status": "missing", "detail": "in keiner Allowlist-Datei gefunden"})
            continue
        arities = found[name]
        distinct = sorted(set(arities))
        if expected_arity is None or -1 in distinct:
            results.append({"name": name, "status": "present", "detail": "gefunden (Arity ungeprüft)"})
        elif expected_arity in distinct:
            note = "" if len(distinct) == 1 else f"; weitere Definitionen mit Arities {distinct}"
            results.append({
                "name": name, "status": "present",
                "detail": f"gefunden mit {expected_arity} Parametern{note}",
            })
        elif len(distinct) > 1:
            results.append({
                "name": name, "status": "ambiguous",
                "detail": (
                    f"{len(distinct)} unterschiedliche Definitionen mit den Arities {distinct} "
                    f"gefunden, keine davon {expected_arity} — nicht eindeutig, welche maßgeblich "
                    "ist (kein Scope-Abgleich ohne Import, Vorab-Entscheidung A3)"
                ),
            })
        else:
            results.append({
                "name": name, "status": "arity_mismatch",
                "detail": f"erwartet {expected_arity} Parameter, gefunden {distinct[0]}",
            })
    return results


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cmd_generate(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan)
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Plan nicht lesbar: {exc}", file=sys.stderr)
        return 1
    try:
        doc = parse_plan(text)
    except PlanParseError as exc:
        print(f"Plan nicht parsbar: {exc}", file=sys.stderr)
        return 1

    if args.tasks:
        wanted = {int(x) for x in args.tasks.split(",")}
        doc = PlanDoc(global_constraints=doc.global_constraints, tasks=[t for t in doc.tasks if t.id in wanted])
        if not doc.tasks:
            print("Keine der angegebenen Task-IDs im Plan gefunden.", file=sys.stderr)
            return 1

    result = write_tasks(doc, str(plan_path), Path(args.out_dir))
    gate: GateResult = result["gate"]
    print(f"{len(doc.tasks)} Task(s) verarbeitet -> {args.out_dir}")
    print(f"Gate-Urteil: {gate.verdict}")
    print(gate.reasoning)
    if gate.parallel_group:
        print(f"Parallel-Gruppe: Tasks {gate.parallel_group}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    task_file = Path(args.task_file)
    try:
        block = parse_task_machine_block(task_file.read_text(encoding="utf-8"))
    except (OSError, PlanParseError, json.JSONDecodeError) as exc:
        print(f"Task-Datei nicht lesbar: {exc}", file=sys.stderr)
        return 1

    worktree = Path(args.worktree)
    allowlist = block["allowlist"]
    produces = [(p["name"], p["arity"]) for p in block["produces"]]

    # Fix D1: Ohne --base wird die Allowlist-Prüfung nicht "bestanden", sondern
    # übersprungen — und ein übersprungenes Gate meldet nie stillschweigend
    # Erfolg (Spec 00 §3, Sichtbarkeits-Regel). `allowlist_checked=False` macht
    # das sichtbar; das Gesamtverdikt kann dann höchstens "unverified" sein,
    # nie "pass" — es sei denn, ein anderer Teil (Produces) ist bereits
    # eindeutig gescheitert, dann bleibt es ehrlich "fail".
    allowlist_checked = bool(args.base)
    violations = check_allowlist(worktree, args.base, allowlist) if allowlist_checked else []
    produce_results = check_produces(worktree, allowlist, produces)
    produces_ok = all(r["status"] == "present" for r in produce_results)

    if violations or not produces_ok:
        verdict = "fail"
    elif not allowlist_checked:
        verdict = "unverified"
    else:
        verdict = "pass"
    ok = verdict == "pass"

    if allowlist_checked:
        print(f"Allowlist-Verstöße: {len(violations)}")
        for v in violations:
            print(f"  außerhalb der Allowlist: {v}")
    else:
        print("Allowlist-Prüfung: ÜBERSPRUNGEN (--base fehlt) — nicht geprüft, nicht bestanden")
    for r in produce_results:
        print(f"  {r['name']}: {r['status']} — {r['detail']}")
    print(f"Verdikt: {verdict.upper()}")

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_meta": {
                "skill": "subagent-dev",
                "schema": SCHEMA_VERSION,
                "generated": (
                    f"python skills/subagent-dev/scripts/plan_to_tasks.py verify "
                    f"--task-file {args.task_file} --worktree {args.worktree}"
                    + (f" --base {args.base}" if args.base else "")
                ),
            },
            "task_file": str(task_file),
            "worktree": str(worktree),
            "allowlist_checked": allowlist_checked,
            "allowlist_violations": violations,
            "produces": produce_results,
            "verdict": verdict,
            "ok": ok,
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Verify-Ergebnis geschrieben -> {out_path}")

    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan -> Tasks für subagent-dev")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Plan parsen, Gate fällen, Task-Dateien schreiben")
    gen.add_argument("plan", help="Pfad zum superpowers:writing-plans-Plan")
    gen.add_argument("--tasks", help="Kommagetrennte Task-IDs, sonst alle")
    gen.add_argument("--out-dir", default=str(Path(".skills") / "cache" / "tasks"))
    gen.set_defaults(func=_cmd_generate)

    ver = sub.add_parser("verify", help="Allowlist + Produces-Signaturen gegen einen Worktree prüfen")
    ver.add_argument("--task-file", required=True)
    ver.add_argument("--worktree", required=True)
    ver.add_argument(
        "--base",
        help=(
            "Basis-Revision für git diff. Ohne --base wird die Allowlist NICHT geprüft "
            "(nicht stillschweigend als bestanden gewertet) — das Gesamtverdikt ist dann "
            "höchstens 'unverified', nie 'pass' (Fix D1)."
        ),
    )
    ver.add_argument("--out", help="Verify-Ergebnis zusätzlich als JSON-Artefakt schreiben (z. B. .skills/cache/tasks/verify-task-1.json)")
    ver.set_defaults(func=_cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
