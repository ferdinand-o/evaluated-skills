#!/usr/bin/env python3
"""Plan -> Tasks für subagent-dev. Tier 1: nur Stdlib.

`generate` parst einen impl-plan- oder work-plan-Plan, baut die Datei- und
Interface-Überlappungsmatrix, fällt ein Gate-Urteil (parallel/sequenziell/keine
Delegation) und schreibt pro Task eine Handoff-Datei nach `.skills/cache/tasks/`.

`verify` prüft nach einem Dispatch mechanisch, ob ein Agent innerhalb seiner
Datei-Allowlist geblieben ist und ob die deklarierten `Produces`-Signaturen im
Ergebnis auftauchen. Fremder Code wird dafür nie importiert, nur mit `ast`
statisch gelesen (Vorab-Entscheidung A3).

Überlappung ist konservativ: Was nicht sicher ausgeschlossen werden kann, gilt
als Abhängigkeit (Vorab-Entscheidung B2) — ein übersehener Konflikt zerstört
Arbeitsstand, eine überflüssige Serialisierung kostet nur Zeit.

`lint` prüft einen Plan auf das Format, das `generate` liest; `lint-spec` prüft
die Skill-Spec davor (Kopfzeile mit Review-Vermerk, sieben Abschnitte, Eval-Tabelle,
Skill-Struktur, Tier, Abgrenzung) mit demselben Parser — der Konsument des Formats
ist sein Eigentümer (impl-plan Contract). Beides G2: meldet, blockiert nicht.
"""

import argparse
import ast
import json
import re
import shlex
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
# Wie STEP_RE, aber zeilenweise und mit dem Rest der Zeile — der Anfang des Step-Texts.
STEP_LINE_RE = re.compile(r"^-\s*\[[ xX]\]\s*\*\*(Step \d+:[^*]*)\*\*(.*)$")
# Backtick-Symbol mit Klammern (Funktion/Methode) — Name vor der ersten "(".
CALLABLE_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*)\(([^)]*)\)")
# Backtick-Symbol ohne Klammern (Klasse/Konstante) — nur, falls es kein
# Dateipfad ist (keine "/", keine bekannte Dateiendung).
BARE_SYMBOL_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*)`")
FILE_LIKE_SUFFIXES = (".py", ".md", ".json", ".yaml", ".yml", ".txt", ".sh")
# "Consumes:"/"Produces:" ohne Backtick-Symbol, aber auch keine echte Prosa —
# der explizite Leerfall, den der Plan selbst so benennt.
NOTHING_NEW_RE = re.compile(r"^\(?nichts neues\)?\.?$", re.IGNORECASE)
# Interface-Vokabular (Spec 16): `fn:name(args)`, `token:Name`, `file:pfad`.
# Additiv zu nackten Bezeichnern; jedes andere Präfix bleibt fail-closed.
PREFIXED_SYMBOL_RE = re.compile(r"`(fn|token|file):([^`]+)`")
# Kopfzeile eines Plans (docs/artifact-header.md): impl-plan (Spec 16) für Specs dieser
# Sammlung, work-plan (Spec 23) für fremde Repos.
PLAN_HEADER_RE = re.compile(r"^<!--\s*skill:\s*(impl-plan|work-plan)\s*\|\s*schema:\s*\d+\s*\|\s*generated:\s*.+?\s*-->$")
# Pfad-Segmente, die ein Glob-Muster statt eines konkreten Pfads markieren.
GLOB_CHARS = frozenset("*?[")
# Pflicht-Titel (E8): solche Tasks konsumieren laut Plan alle Produces und zählen
# nicht als Abnehmer.
MANDATORY_TITLES = ("Verifikation", "Evals", "Nachbarn", "known-limits", "Report")


class PlanParseError(ValueError):
    """Der Plan-Text folgt nicht dem Planformat von impl-plan und work-plan genug, um sicher geparst zu werden."""


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
    # (Titel, Text) je Step — `steps` bleibt der reine Titel für den Lint.
    step_texts: list[tuple[str, str]] = field(default_factory=list)
    # `file:`-Konsumpfade aus Consumes (Spec 16) — fließen in die Pfad-Überlappung
    # des Gates ein, nicht in den Symbolabgleich.
    consumed_files: list[str] = field(default_factory=list)


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
    Leerfall "nichts Neues" enthält — Prosa, aus der `extract_symbols`
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


BACKTICK_SPAN_RE = re.compile(r"`([^`]+)`")


def _interface_lines(block: str) -> tuple[str, str, list[str]]:
    """Consumes-/Produces-Zeile und alle übrigen nicht-leeren Zeilen des
    Interfaces-Blocks. Zeilengenau: Früher lief `Produces:` bis zum ersten Step
    und schluckte erklärende Prosa darunter — das machte die Task unbekannt und
    erzeugte ein `sequential` mit falscher Begründung (known-limits, Einsatz an
    Spec 15). Die Prosa wird jetzt separat zurückgegeben, damit `lint` sie
    benennen kann, statt dass sie das Verdikt still verschiebt.
    """
    text = _section(block, "**Interfaces:**", ("\n- [ ]", "\n- [x]", "\n- [X]"))
    fields: dict[str, list[str]] = {"consumes": [], "produces": []}
    active: str | None = None
    stray: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- Consumes:"):
            active = "consumes"
            fields[active].append(stripped[len("- Consumes:"):].strip())
        elif stripped.startswith("- Produces:"):
            active = "produces"
            fields[active].append(stripped[len("- Produces:"):].strip())
        elif stripped.startswith("-") and active is not None:
            # Unter-Bullet je Symbol — die übliche Form in diesem Repo
            # (`- Produces:` allein auf der Zeile, darunter eingerückt je ein
            # Symbol). Gehört zum aktiven Feld, nie zur Prosa.
            fields[active].append(stripped)
        else:
            stray.append(stripped)
    consumes = " ".join(s for s in fields["consumes"] if s).strip()
    produces = " ".join(s for s in fields["produces"] if s).strip()
    return consumes, produces, stray


def unextractable_backtick_spans(text: str) -> list[str]:
    """Backtick-Ausdrücke, aus denen `extract_symbols` kein Symbol zieht.

    Das ist die Lücke, die das Gate still geöffnet hat (known-limits, Einsatz an
    Spec 15): ``Unverified:``, ``Next:``, ``effort-ladder`` sind keine
    gültigen Bezeichner, liefern null Symbole — und galten trotzdem nicht als
    unbekannt, weil ein Backtick vorhanden war. Kein Symbol *und* nichts
    Unbekanntes hieß: keine Abhängigkeit. Jetzt gilt jeder solche Ausdruck als
    unbekannt (fail-closed), und `lint` sagt, welcher.
    """
    return [span for span in BACKTICK_SPAN_RE.findall(text) if symbol_kind(span) is None]


def _parse_interfaces(block: str) -> tuple[str, str, bool]:
    consumes, produces, _stray = _interface_lines(block)
    interfaces_unknown = (
        _has_unrecognized_prose(consumes)
        or _has_unrecognized_prose(produces)
        or bool(unextractable_backtick_spans(consumes))
        or bool(unextractable_backtick_spans(produces))
    )
    return consumes, produces, interfaces_unknown


def _parse_steps(block: str) -> list[str]:
    return [m.strip() for m in STEP_RE.findall(block)]


def parse_step_texts(block: str) -> list[tuple[str, str]]:
    """Je Step `(Titel, Text)`: der Text ist der Rest der Step-Zeile plus alle
    eingerückten Folgezeilen bis zum nächsten Step (Leerzeilen zählen mit, wenn
    danach wieder eingerückt weitergeht). Ein Step ohne Text liefert `""`.
    """
    steps: list[tuple[str, list[str]]] = []
    open_step = False
    for line in block.split("\n"):
        match = STEP_LINE_RE.match(line)
        if match:
            # Trenner zwischen Titel und Text („ — “, „, “) gehört nicht zum Text.
            steps.append((match.group(1).strip(), [match.group(2).lstrip(" \t—–,:")]))
            open_step = True
        elif open_step and (not line.strip() or line[0] in " \t"):
            steps[-1][1].append(line.strip())
        else:
            open_step = False
    return [(title, "\n".join(l for l in lines if l).strip()) for title, lines in steps]


def parse_plan(text: str) -> PlanDoc:
    """Parse einen impl-plan- oder work-plan-Plan in `PlanDoc`.

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
            "impl-plan- oder work-plan-Plan?"
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
        step_texts = parse_step_texts(block)
        consumed_files = [name for kind, name, _ in extract_symbols(consumes) if kind == "file"]
        tasks.append(PlanTask(
            id=task_id, title=title, files=files, files_unknown=files_unknown,
            consumes=consumes, produces=produces, interfaces_unknown=interfaces_unknown,
            steps=steps, step_texts=step_texts, consumed_files=consumed_files,
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


def extract_symbols(text: str) -> list[tuple[str, str, int | None]]:
    """Alle Interface-Symbole eines Consumes-/Produces-Texts als (kind, name, arity).

    Drei Präfixe (Spec 16): `fn:parse(line)` — Aufrufbares mit Arity;
    `token:Next` — wörtlicher Ausgabe-Token einer Doktrin; `file:docs/x.md` —
    Lese-Abhängigkeit auf eine Datei. Ohne Präfix gilt die bisherige Regel:
    ``name(a, b)`` ist ein Aufrufbares, ``Name`` ein Symbol ohne Arity, ein
    Dateipfad kein Symbol. Jedes andere Präfix (`foo:bar`) bleibt unerkannt —
    und damit fail-closed über `unextractable_backtick_spans`.
    """
    symbols: list[tuple[str, str, int | None]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, name: str, arity: int | None) -> None:
        if (kind, name) not in seen:
            seen.add((kind, name))
            symbols.append((kind, name, arity))

    for kind, body in PREFIXED_SYMBOL_RE.findall(text):
        body = body.strip()
        if kind == "fn":
            call = re.match(r"([A-Za-z_][A-Za-z0-9_.]*)\(([^)]*)\)$", body)
            if call:
                args = call.group(2).strip()
                add("fn", call.group(1), 0 if not args else len([a for a in args.split(",") if a.strip()]))
            elif re.match(r"[A-Za-z_][A-Za-z0-9_.]*$", body):
                add("fn", body, None)
        elif kind == "token" and body:
            add("token", body, None)
        elif kind == "file" and body:
            add("file", body, None)

    rest = PREFIXED_SYMBOL_RE.sub("", text)
    for name, args in CALLABLE_RE.findall(rest):
        args = args.strip()
        add("fn", name, 0 if not args else len([a for a in args.split(",") if a.strip()]))
    for name in BARE_SYMBOL_RE.findall(rest):
        if "/" in name or any(name.endswith(suf) for suf in FILE_LIKE_SUFFIXES):
            continue
        if ("fn", name) in seen:
            continue
        add("fn", name, None)
    return symbols


def symbol_kind(span: str) -> str | None:
    """Kind eines einzelnen Backtick-Inhalts, oder None, wenn er kein Symbol ist."""
    found = extract_symbols(f"`{span}`")
    return found[0][0] if found else None


def _symbol_pattern(name: str) -> str:
    """Wortgrenzen-sicheres Muster auch für Namen, die auf Nicht-Wortzeichen enden
    (`Unverified:`) — `\\b` würde dort nie greifen."""
    return rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])"


def _dependency_symbols(producer: PlanTask, consumer: PlanTask) -> list[str]:
    """Namen aller Symbole, die `consumer` konsumiert und `producer` produziert."""
    names: list[str] = []
    for kind, name, _ in extract_symbols(producer.produces):
        if kind == "file":
            continue  # Pfad-Überlappung, siehe build_overlap_graph
        if re.search(_symbol_pattern(name), consumer.consumes):
            names.append(name)
    return names


def _interface_dependency(producer: PlanTask, consumer: PlanTask) -> str | None:
    """Name des Symbols, falls `consumer` etwas konsumiert, das `producer` produziert."""
    names = _dependency_symbols(producer, consumer)
    return names[0] if names else None


def is_mandatory_title(title: str) -> bool:
    """Ist das eine Pflicht-Task (genau der Titel oder `<Titel> — …`)? Sie konsumiert
    laut Plan alle `Produces` und zählt deshalb nicht als Abnehmer."""
    return any(title == word or title.startswith(word + " —") for word in MANDATORY_TITLES)


def consumers_of(tasks: list[PlanTask]) -> dict[int, list[dict]]:
    """Task-ID -> Abnehmer: spätere Tasks, deren Consumes ein Produces-Symbol nennt.

    Je Abnehmer `{"task": id, "symbols": [...]}`; ein Symbol steht als `name`, mit
    erwarteter Arity aus dem Consumes des Abnehmers als `name(arity)`. Pflicht-Tasks
    sind keine Abnehmer; eine Task mit `interfaces_unknown` hat keine erkennbaren.
    """
    result: dict[int, list[dict]] = {t.id: [] for t in tasks}
    for i, producer in enumerate(tasks):
        if producer.interfaces_unknown:
            continue
        for consumer in tasks[i + 1:]:
            if is_mandatory_title(consumer.title):
                continue
            names = _dependency_symbols(producer, consumer)
            if not names:
                continue
            arity = {n: a for k, n, a in extract_symbols(consumer.consumes) if k == "fn"}
            result[producer.id].append({
                "task": consumer.id,
                "symbols": [n if arity.get(n) is None else f"{n}({arity[n]})" for n in names],
            })
    return result


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
                # `file:`-Konsumpfade (Spec 16): Wer eine Datei liest, die ein
                # anderer Task schreibt, hängt von ihm ab — Pfad gegen Files:.
                if not reason:
                    for consumed, writer in ((ta.consumed_files, tb.files), (tb.consumed_files, ta.files)):
                        if any(_paths_overlap(c, f.path) for c in consumed for f in writer):
                            reason = True
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
    produces = [s for s in extract_symbols(task.produces) if s[0] != "file"]
    others = [f"Task {t.id} – {t.title}" for t in doc.tasks if t.id != task.id]

    allowlist_md = "\n".join(f"- `{p}`" for p in allowlist) if allowlist else (
        "- (keine geparst — Allowlist unklar, gilt als leer und damit als riskant)"
    )
    # Titel als Listenpunkt, der Text eingerückt darunter — ein Step ohne Text bleibt eine Zeile.
    steps_md = "\n".join(
        f"- {title}" + "".join(f"\n  {l}" for l in text.split("\n") if l)
        for title, text in task.step_texts
    ) if task.step_texts else "- (keine Steps im Plan gefunden)"
    others_md = "\n".join(f"- {o}" for o in others) if others else "- (keine weiteren Tasks in diesem Plan)"

    machine_block = {
        "task_id": task.id,
        "plan": plan_path,
        "allowlist": allowlist,
        "produces": [{"kind": k, "name": n, "arity": a} for k, n, a in produces],
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
        ["git", *args], cwd=worktree, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60, check=False,
    )
    if done.returncode != 0:
        raise PlanParseError(f"git {' '.join(args)} fehlgeschlagen: {done.stderr.strip()}")
    return done.stdout


def check_allowlist(worktree: Path, base_ref: str, allowlist: list[str]) -> list[str]:
    """Geänderte Dateien (committed seit `base_ref` und uncommittete), die außerhalb
    der Allowlist liegen — exakte, Verzeichnis-Präfix- oder Suffix-Treffer
    (siehe `_paths_overlap`) zählen als erlaubt."""
    # -z überall: ohne -z setzt git Pfade mit Leerzeichen oder Nicht-ASCII-Zeichen in
    # Anführungszeichen und escapt sie (core.quotepath) — `specs/Spec 00 – x.md` passte
    # dann auf keinen Allowlist-Eintrag (beim Bau von Spec 20 und 21 beobachtet).
    committed = _git(worktree, "diff", "--name-only", "-z", f"{base_ref}...HEAD").split("\0")
    entries = _git(worktree, "status", "--porcelain", "-z", "--untracked-files=all").split("\0")

    dirty_paths: list[str] = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        dirty_paths.append(path)
        if "R" in code or "C" in code:
            # Mit -z steht eine (auch nur staged) Umbenennung als zwei Einträge,
            # erst der neue, dann der alte Pfad (L3). Beide zählen einzeln — ein
            # Task, der sich an seine Allowlist hielt, darf keinen Fehlalarm sehen.
            if i < len(entries) and entries[i]:
                dirty_paths.append(entries[i])
            i += 1

    changed = sorted({*committed, *dirty_paths} - {""})
    return [path for path in changed if not any(_paths_overlap(path, allowed) for allowed in allowlist)]


def check_produces(worktree: Path, allowlist: list[str], produces: list[tuple]) -> list[dict]:
    """Prüfe deklarierte Produces-Symbole gegen die Allowlist-Dateien, nach kind.

    `fn` per `ast` (Name + Arity), `token` per Textsuche des Namens in den
    Allowlist-Dateien — ein Doktrin-Token steht in einer SKILL.md, nicht in einem
    Funktionskopf, und `ast` würde ihn für jeden Doktrin-Task als `missing`
    melden (Spec-16-Review). Einträge dürfen (name, arity) oder (kind, name,
    arity) sein; ohne kind gilt `fn`.

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

    normalized: list[tuple[str, str, int | None]] = [
        (entry[0], entry[1], entry[2]) if len(entry) == 3 else ("fn", entry[0], entry[1]) for entry in produces
    ]
    text_cache: dict[str, str] = {}
    results: list[dict] = []
    for kind, name, expected_arity in normalized:
        if kind == "token":
            hit = False
            for relpath in allowlist:
                path = worktree / relpath
                if not path.is_file():
                    continue
                if relpath not in text_cache:
                    text_cache[relpath] = path.read_text(encoding="utf-8", errors="replace")
                if name in text_cache[relpath]:
                    hit = True
                    break
            results.append({
                "name": name, "status": "present" if hit else "missing",
                "detail": f"token {'gefunden' if hit else 'in keiner Allowlist-Datei gefunden'} (Textsuche)",
            })
            continue
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
    # `kind` fehlt in Task-Dateien vor Spec 16 — dann gilt `fn`, wie bisher.
    produces = [(p.get("kind", "fn"), p["name"], p["arity"]) for p in block["produces"]]

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



# --------------------------------------------------------------------------
# Lint — sagt, *warum* das Gate eine Task für unsicher hält (G2: meldet, blockiert nicht)
# --------------------------------------------------------------------------

PLACEHOLDER_RE = re.compile(r"\b(TBD|TODO|FIXME|XXX)\b|\?\?\?|<platzhalter>|<placeholder>", re.IGNORECASE)
SPEC_LINE_RE = re.compile(r"^\*\*Spec:\*\*\s*`([^`]+)`", re.MULTILINE)
KNOWN_FILE_VERBS = ("Create", "Modify", "Test", "Delete", "Rename")


@dataclass(frozen=True)
class LintFinding:
    task_id: int | None  # None = Plan-Ebene
    message: str

    def render(self) -> str:
        where = "Plan" if self.task_id is None else f"Task {self.task_id}"
        return f"{where}: {self.message}"


def _explain_files(block: str) -> list[str]:
    files_text = _section(block, "**Files:**", ("**Interfaces:**", "\n- [ ]", "\n- [x]", "\n- [X]"))
    if "**Files:**" not in block:
        return ["files_unknown: kein **Files:**-Block"]
    reasons: list[str] = []
    for line in BULLET_LINE_RE.findall(files_text):
        if FILE_LINE_RE.match(line) or RENAME_LINE_RE.match(line):
            continue
        reasons.append(
            f"files_unknown: Bullet-Zeile ohne bekanntes Verb {KNOWN_FILE_VERBS}: {line.strip()!r}"
        )
    if not BULLET_LINE_RE.findall(files_text):
        reasons.append("files_unknown: **Files:**-Block ohne Bullet-Zeilen")
    return reasons


def plan_kind(text: str) -> str | None:
    """`impl-plan`, `work-plan` oder None — aus der ersten nicht-leeren Zeile."""
    for line in text.splitlines():
        if line.strip():
            m = PLAN_HEADER_RE.match(line.strip())
            return m.group(1) if m else None
    return None


def check_header(text: str) -> str | None:
    """Befund, falls die erste nicht-leere Zeile keine Kopfzeile von impl-plan oder
    work-plan ist."""
    for line in text.splitlines():
        if line.strip():
            if PLAN_HEADER_RE.match(line.strip()):
                return None
            if line.strip().startswith("<!--"):
                return f"Kopfzeile fremd oder fehlerhaft: {line.strip()[:70]!r}"
            return "Kopfzeile fehlt (docs/artifact-header.md, skill: impl-plan oder work-plan)"
    return "Datei leer, keine Kopfzeile"


AUFTRAG_LINE_RE = re.compile(r"^\*\*Auftrag:\*\*\s*\S", re.MULTILINE)
FEATURE_SPEC_HEADER_RE = re.compile(r"^<!--\s*skill:\s*feature-spec\s*\|")


def check_work_plan(text: str, plan_path: Path | None) -> list[str]:
    """Regeln nur für work-plan (Spec 23): genau eine Quelle — `**Spec:**` oder
    `**Auftrag:**` — und als letzter Task `Verifikation`. `plan_path` bleibt für
    künftige Pfadregeln in der Signatur; heute prüft die Funktion nur den Text."""
    del plan_path
    masked = _mask_fenced_blocks(text)
    problems: list[str] = []
    has_spec = SPEC_LINE_RE.search(masked) is not None or "**Spec:**" in masked
    has_auftrag = AUFTRAG_LINE_RE.search(masked) is not None
    if has_spec and has_auftrag:
        problems.append("work-plan braucht genau eine Quelle: **Spec:** oder **Auftrag:**, nicht beide")
    elif not has_spec and not has_auftrag:
        problems.append("work-plan ohne Quelle: **Spec:** (feature-spec) oder **Auftrag:** fehlt")
    headers = list(TASK_HEADER_RE.finditer(masked))
    titles = [m.group(2).strip() for m in headers]
    if "Verifikation" not in titles:
        problems.append("work-plan ohne Task `Verifikation` (Spec 23: der letzte Task führt den Verifikationsbefehl aus)")
    elif titles[-1] != "Verifikation":
        problems.append("Task `Verifikation` ist nicht der letzte Task")
    return problems


def feature_spec_criteria(spec_text: str) -> list[str] | None:
    """Titel der `### `-Kriterien unter `## Akzeptanzkriterien` einer feature-spec-Spec,
    oder None, wenn die Datei keine feature-spec-Kopfzeile trägt."""
    first = next((line.strip() for line in spec_text.splitlines() if line.strip()), "")
    if not FEATURE_SPEC_HEADER_RE.match(first):
        return None
    titles: list[str] = []
    in_section = False
    for line in spec_text.splitlines():
        if line.startswith("## "):
            in_section = line.strip() == "## Akzeptanzkriterien"
        elif in_section and line.startswith("### "):
            titles.append(line[4:].strip())
    return titles


# Überschrift des Evals-Abschnitts: ab Ebene 2 (ein H1-Titel, der „Evals" nennt,
# machte sonst das ganze Dokument zum Abschnitt) und mit dem ganzen Wort — „Evaluation
# der Alternativen" ist kein Evals-Abschnitt, „Eval-Tabelle" und „§2 Evals" schon.
EVAL_HEADING_RE = re.compile(r"^(#{2,6})\s+.*\bevals?\b", re.IGNORECASE)
_ID_CELL_RE = re.compile(r"`([^`]+)`")


def spec_eval_table(spec_text: str) -> tuple[list[str], list[str]] | None:
    """Eval-Tabelle einer Spec: die erste Tabelle mit einer Spalte `id` **unter
    einer Überschrift, die „Eval" enthält** (`### Evals`, `## §2 Evals`). Tabellen
    anderswo — ein Contract mit einer Spalte `user_id` — zählen nicht. Liefert
    (ids, fehlerhafte Zeilen): eine Zeile, deren id-Zelle gefüllt ist, aber keinen
    Backtick-Wert trägt, wird gemeldet statt still übergangen. None, wenn es keine
    solche Tabelle gibt — ältere Specs nennen Evals in Prosa, dort wird nicht geraten.
    Codezäune sind maskiert: ein `# Kommentar` in einem Beispielblock ist keine
    Überschrift. Tiefere Unterüberschriften schließen den Abschnitt nicht."""
    lines = _mask_fenced_blocks(spec_text).splitlines()
    located = _locate_eval_table(lines)
    if located is None:
        return None
    return _eval_table_rows(lines, located)


def _eval_table_rows(lines: list[str], located: tuple[int, list[str]]) -> tuple[list[str], list[str]]:
    """(ids, fehlerhafte Zeilen) der Tabelle, die `_locate_eval_table` gefunden hat."""
    i, cells = located
    idx = cells.index("id")
    ids: list[str] = []
    malformed: list[str] = []
    for row in lines[i + 1:]:
        if not row.lstrip().startswith("|"):
            break
        row_cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(row_cells) <= idx or set(row_cells[idx]) <= set("-: "):
            continue
        match = _ID_CELL_RE.search(row_cells[idx])
        if match:
            ids.append(match.group(1))
        elif row_cells[idx]:
            malformed.append(row_cells[idx])
    return ids, malformed


def _locate_eval_table(lines: list[str]) -> tuple[int, list[str]] | None:
    """(Zeilenindex der Kopfzeile, Spaltennamen) der ersten Tabelle mit Spalte `id`
    unter einer Evals-Überschrift — die eine Definition, die `spec_eval_table` und
    `lint-spec` teilen."""
    in_evals, level = False, 0
    for i, line in enumerate(lines):
        heading = re.match(r"^(#{1,6})\s", line)
        if heading:
            depth = len(heading.group(1))
            if in_evals and depth <= level:
                in_evals = False
            if not in_evals and EVAL_HEADING_RE.match(line):
                in_evals, level = True, depth
            continue
        if not in_evals or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip().strip("`").lower() for c in line.strip().strip("|").split("|")]
        if "id" in cells:
            return i, cells
    return None


def spec_eval_ids(spec_text: str) -> list[str] | None:
    """Nur die IDs der Eval-Tabelle (siehe `spec_eval_table`); None ohne Tabelle."""
    table = spec_eval_table(spec_text)
    return None if table is None else table[0]


def _task_blocks(masked: str) -> list[tuple[int, re.Match, str]]:
    """(task_id, header, block) je Task. Ein Block endet am nächsten `### Task`-Header
    oder an der nächsten Überschrift bis Ebene 3 — ein `## Notizen` hinter dem letzten
    Task gehört zu keinem Task, und was dort steht, deckt keine Eval-ID."""
    headers = list(TASK_HEADER_RE.finditer(masked))
    stops = [m.start() for m in re.finditer(r"^#{1,3}\s", masked, re.MULTILINE)]
    blocks = []
    for header in headers:
        end = next((s for s in stops if s > header.start()), len(masked))
        blocks.append((int(header.group(1)), header, masked[header.end():end]))
    return blocks


def _id_pattern(eval_id: str) -> str:
    """Eine Eval-ID zählt nur als ganzes Wort — `note-carries-header` steckt sonst
    in `stale-note-carries-header-foo` und gälte als abgedeckt."""
    return rf"(?<![A-Za-z0-9_-]){re.escape(eval_id)}(?![A-Za-z0-9_-])"


def lint_meta(plan_path: Path | str, spec: Path | str | None = None, skill: str | None = None) -> dict:
    """`generated` ist das Kommando, so wie man es erneut eintippen würde
    (docs/artifact-header.md) — mit `--spec`/`--skill`, sonst reproduziert es
    die Befunde nicht."""
    return _artifact_meta("lint", plan_path, spec=spec, skill=skill)


def _artifact_meta(subcommand: str, path: Path | str, **flags: object) -> dict:
    """Kopfzeile eines JSON-Artefakts (docs/artifact-header.md): `generated` ist das
    Kommando mit allen gesetzten Flags, so wie man es erneut eintippen würde."""
    cmd = f"python skills/subagent-dev/scripts/plan_to_tasks.py {subcommand} {shlex.quote(str(path))}"
    for name, value in flags.items():
        if value:
            cmd += f" --{name.replace('_', '-')} {shlex.quote(str(value))}"
    return {"skill": "subagent-dev", "schema": SCHEMA_VERSION, "generated": cmd}


def _resolve_near(plan_path: Path | None, rel: Path) -> Path | None:
    candidates = [rel]
    if plan_path is not None:
        candidates += [parent / rel for parent in plan_path.resolve().parents]
    return next((c for c in candidates if c.is_file()), None)


def _explain_interfaces(block: str) -> list[str]:
    if "**Interfaces:**" not in block:
        return ["interfaces_unknown: kein **Interfaces:**-Block"]
    consumes, produces, stray = _interface_lines(block)
    reasons: list[str] = []
    for label, text in (("Consumes", consumes), ("Produces", produces)):
        if _has_unrecognized_prose(text):
            reasons.append(f"interfaces_unknown: {label} ist Prosa ohne Backtick-Symbol: {text!r}")
        for span in unextractable_backtick_spans(text):
            reasons.append(
                f"interfaces_unknown: {label} nennt `{span}` — kein gültiger Bezeichner "
                f"([A-Za-z_][A-Za-z0-9_.]*), kein Symbol extrahierbar (fail-closed)"
            )
    for kind, name, _ in extract_symbols(produces):
        if kind == "file":
            reasons.append(f"Produces nennt `file:{name}` — eine erzeugte Datei gehört in **Files:**, nicht in Produces")
    for line in stray:
        reasons.append(f"Prosa im Interfaces-Block, weder Consumes noch Produces: {line!r}")
    return reasons


@dataclass
class LintReport:
    findings: list[LintFinding]
    coverage: dict


def lint_report(
    text: str,
    plan_path: Path | None = None,
    spec_path: Path | None = None,
    skill: str | None = None,
) -> LintReport:
    """Befunde plus Coverage-Status. Wirft `PlanParseError` bei unparsbarem Plan
    — das ist kein Befund, das ist das Ende der Prüfung.

    Spec-Coverage (jede Eval-ID der Eval-Tabelle kommt in einem Task-Block vor)
    läuft gegen `spec_path` oder, ohne `--spec`, gegen die Datei aus der eigenen
    `**Spec:**`-Zeile — Coverage ist eine Eigenschaft des Plans, nicht des
    Aufrufs. `coverage["status"]` sagt `checked` oder `unchecked` mit Grund;
    ein übersprungener Abgleich sieht nie aus wie ein bestandener.
    `skill`: IDs aus `evals/<skill>/evals.json` müssen in der Spec vorkommen.
    Alles Befunde, keine Abbrüche (G2: meldet)."""
    doc = parse_plan(text)
    findings: list[LintFinding] = []
    masked = _mask_fenced_blocks(text)

    header_problem = check_header(text)
    if header_problem:
        findings.append(LintFinding(None, header_problem))
    kind = plan_kind(text)

    required = ("**Goal:**",) if kind == "work-plan" else ("**Goal:**", "**Spec:**")
    for field_name in required:
        if field_name not in masked:
            findings.append(LintFinding(None, f"Kopffeld {field_name} fehlt"))
    if kind == "work-plan":
        findings.extend(LintFinding(None, problem) for problem in check_work_plan(text, plan_path))
    spec_match = SPEC_LINE_RE.search(masked)
    if spec_match:
        spec_ref = Path(spec_match.group(1))
        resolved = _resolve_near(plan_path, spec_ref)
        if resolved is None:
            findings.append(LintFinding(None, f"**Spec:** zeigt auf {spec_ref} — Datei nicht gefunden"))
        elif spec_path is None:
            spec_path = resolved
        elif resolved.resolve() != Path(spec_path).resolve():
            findings.append(LintFinding(None, f"--spec {spec_path} weicht von der **Spec:**-Zeile ab ({spec_ref}) — eines von beiden ist falsch"))
    elif "**Spec:**" in masked:
        findings.append(LintFinding(None, "**Spec:** ohne Backtick-Pfad — der Lint kann die Spec nicht auflösen, Coverage bleibt ungeprüft"))

    coverage: dict = {
        "spec": str(spec_path) if spec_path is not None else None,
        "eval_table": False,
        "ids_checked": 0,
        "evals_file": None,
        "status": "unchecked",
        "reason": "keine Spec: weder --spec noch eine auflösbare **Spec:**-Zeile",
    }
    blocks = _task_blocks(masked)
    task_region = "\n".join(block for _, _, block in blocks)
    if kind == "work-plan" and spec_path is None:
        coverage["reason"] = "Quelle ist ein Auftrag, keine Spec"
    elif kind == "work-plan":
        spec_text = spec_path.read_text(encoding="utf-8")
        criteria = feature_spec_criteria(spec_text)
        if criteria is None:
            coverage["reason"] = "Spec ohne feature-spec-Kopfzeile — Kriterien nicht abgeglichen"
        else:
            coverage.update(ids_checked=len(criteria), status="checked", reason=None)
            # Kriterien-Titel stehen oft im Task-Titel; der zählt hier mit.
            titled_region = "\n".join(f"{header.group(0)}{block}" for _, header, block in blocks)
            for title in criteria:
                if title not in titled_region:
                    findings.append(LintFinding(None, f"Akzeptanzkriterium „{title}“ aus der Spec hat keinen Task"))
    elif spec_path is not None:
        spec_text = spec_path.read_text(encoding="utf-8")
        table = spec_eval_table(spec_text)
        if table is None:
            coverage["reason"] = "keine Eval-Tabelle mit Spalte `id` unter einer Evals-Überschrift in der Spec"
        else:
            ids, malformed = table
            coverage.update(eval_table=True, ids_checked=len(ids), status="checked", reason=None)
            for cell in malformed:
                findings.append(LintFinding(None, f"Eval-Tabelle der Spec: id-Zelle ohne Backtick-Wert, nicht prüfbar: {cell!r}"))
            for eval_id in ids:
                if not re.search(_id_pattern(eval_id), task_region):
                    findings.append(LintFinding(None, f"Eval-ID `{eval_id}` aus der Spec hat keinen Task"))
        if skill:
            evals_file = _resolve_near(plan_path, Path("evals") / skill / "evals.json")
            if evals_file is None:
                findings.append(LintFinding(None, f"evals/{skill}/evals.json nicht gefunden (--skill)"))
            else:
                coverage["evals_file"] = str(evals_file)
                try:
                    listed = [e.get("id", "") for e in json.loads(evals_file.read_text(encoding="utf-8")).get("evals", [])]
                except (json.JSONDecodeError, AttributeError) as exc:
                    listed = []
                    findings.append(LintFinding(None, f"evals/{skill}/evals.json nicht lesbar: {exc}"))
                for eval_id in listed:
                    if eval_id and not re.search(_id_pattern(eval_id), spec_text):
                        findings.append(LintFinding(None, f"Eval-ID `{eval_id}` aus evals/{skill}/evals.json fehlt in der Spec"))
    elif skill:
        findings.append(LintFinding(None, f"--skill {skill} ohne Spec: Abgleich evals/{skill}/evals.json ↔ Spec nicht möglich"))

    for m in PLACEHOLDER_RE.finditer(masked):
        line_no = masked.count("\n", 0, m.start()) + 1
        findings.append(LintFinding(None, f"Platzhalter {m.group(0)!r} in Zeile {line_no}"))

    for task_id, header, block in blocks:
        task = next(t for t in doc.tasks if t.id == task_id)
        if task.files_unknown:
            findings.extend(LintFinding(task_id, r) for r in _explain_files(block))
        for r in _explain_interfaces(block):
            findings.append(LintFinding(task_id, r))
        if not task.steps:
            findings.append(LintFinding(task_id, "keine Steps im Format `- [ ] **Step N: …**`"))
    return LintReport(findings, coverage)


def lint_plan(
    text: str,
    plan_path: Path | None = None,
    spec_path: Path | None = None,
    skill: str | None = None,
) -> list[LintFinding]:
    """Nur die Befunde — siehe `lint_report` für den Coverage-Status."""
    return lint_report(text, plan_path, spec_path=spec_path, skill=skill).findings


def _cmd_lint(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan)
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Plan nicht lesbar: {exc}", file=sys.stderr)
        return 2
    spec_path = Path(args.spec) if args.spec else None
    if spec_path is not None and not spec_path.is_file():
        print(f"Spec nicht gefunden: {spec_path}", file=sys.stderr)
        return 2
    try:
        report = lint_report(text, plan_path, spec_path=spec_path, skill=args.skill)
    except PlanParseError as exc:
        print(f"Plan nicht parsbar: {exc}", file=sys.stderr)
        return 2
    findings = report.findings
    if report.coverage["status"] != "checked":
        print(f"Hinweis: Spec-Coverage NICHT geprüft — {report.coverage['reason']}.")
    else:
        unit = "Eval-ID(s)" if report.coverage["eval_table"] else "Akzeptanzkriterien"
        print(f"Spec-Coverage geprüft: {report.coverage['ids_checked']} {unit} aus {report.coverage['spec']}.")

    if findings:
        for f in findings:
            print(f.render())
        print(f"{len(findings)} Befund(e). Das Gate wertet jede unsichere Task als Abhängigkeit — "
              f"Befunde beheben, nicht umformulieren, bis es 'parallel' sagt.")
    else:
        print("Keine Befunde — Plan ist für das Gate vollständig lesbar.")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "_meta": lint_meta(plan_path, spec=args.spec, skill=args.skill),
            "plan": str(plan_path),
            "coverage": report.coverage,
            "findings": [{"task": f.task_id, "message": f.message} for f in findings],
            "status": "clean" if not findings else "findings",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if findings else 0


# ---------------------------------------------------------------------------
# lint-spec: eine Skill-Spec dieser Sammlung prüfen, bevor impl-plan sie liest
# (docs/assessment-brainstorming.md §6 Punkt 3, Branch claude/assessment-brainstorming).
# Geprüft wird Form, nicht Inhalt: Kopfzeile, die sieben Abschnitte, Eval-Tabelle mit
# Pflichtspalten, Skill-Struktur, Tier je Skript, Abgrenzung gegen zwei Nachbarn,
# Gate-Wörter, Platzhalter — und der Review-Vermerk in der Kopfzeile, an dem Schritt 1
# von skill-forge (Review der Spec durch einen Subagenten) erkennbar wird. Der Lint
# gehört dem Konsumenten des Formats (impl-plan Contract), derselbe Parser wie
# `spec_eval_table`. G2: meldet.

SPEC_SECTIONS = ("Problem", "Constraints", "Approach", "Alternatives considered",
                 "Out of scope", "Open questions", "Next steps")
SPEC_HEADER_RE = re.compile(r"^Skill-Spezifikation\s*·\s*Zyklus\s*(\d+|NN)\b")  # NN: das Gerüst von skill-forge — als Platzhalter gemeldet
SPEC_REVIEW_NOTE = "Überarbeitet nach unabhängigem Review"
# Pflichtspalten der Eval-Tabelle (Specs 16/17); ein Tupel = eine von beiden genügt.
# Verglichen wird als Präfix des Spaltennamens: „Assertion" und „Assertions" gelten beide.
SPEC_EVAL_COLUMNS: tuple = ("id", "klasse", "fixture", ("assertion", "mechanismus"), "diskriminator")
SPEC_NUMBER_RE = re.compile(r"Spec\s+(\d+)")
SPEC_LINT_CUTOFF = 18  # Specs ab dieser Nummer müssen sauber sein; ältere sind Historie
# G3-Wortwahl nach Spec 00 §4: Verb und Substantiv („blockiert", „Abnahme-Blocker").
SPEC_GATE_WORD_RE = re.compile(r"\b(blockier\w*|\w*blocker\w*|erzwing\w*|stellt sicher)\b", re.IGNORECASE)
SPEC_NEGATION_RE = re.compile(r"\b(nicht|nichts|nie|niemals|kein\w*|statt|verworfen)\b", re.IGNORECASE)
# Nachbar-Kandidaten in der Abgrenzung: ein Skill-Name (auch ohne Bindestrich, wie
# `explain`) oder ein Name mit Namensraum (`superpowers:writing-skills`). Ob ein Kandidat
# zählt, entscheidet `skills/<name>/` unter der Repo-Wurzel bzw. der Namensraum.
SPEC_NAME_RE = re.compile(r"(?<![\w/.:])([a-z][a-z0-9-]*:[a-z][a-z0-9-]+|[a-z][a-z0-9-]{2,})(?![\w/:])")
SPEC_TREE_ROOT_RE = re.compile(r"^\s*skills/([a-z][a-z0-9-]*)/(?:\s+\S.*)?$")  # Anhang hinter der Wurzel erlaubt
SPEC_TREE_PREFIX_RE = re.compile(r"^[\s│├└─]*")
SPEC_TIER_RE = re.compile(r"\bTier\s*[0-3]\b")
SPEC_SCRIPT_EXT = (".py", ".sh")
SPEC_QUOTE_SPAN_RE = re.compile(r"„[^„“\"\n]{1,40}[\"“]")  # „TBD" in Prosa ist eine Erwähnung, kein Platzhalter
SPEC_UNIT_MARKER_RE = re.compile(r"^\s*(\||[-*+]\s|\d+\.\s)")


@dataclass(frozen=True)
class SpecFinding:
    rule: str
    message: str

    def render(self) -> str:
        return f"{self.rule}: {self.message}"


def spec_number(spec_path: Path | str | None) -> int | None:
    """Nummer aus dem Dateinamen (`Spec 17 – skill-forge.md` → 17); None ohne Nummer."""
    if spec_path is None:
        return None
    match = SPEC_NUMBER_RE.search(Path(spec_path).name)
    return int(match.group(1)) if match else None


def _spec_headings(masked: str) -> list[tuple[int, str]]:
    out = []
    for line in masked.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if match:
            out.append((len(match.group(1)), match.group(2)))
    return out


def _spec_section(masked: str, title_re: str, min_level: int = 2) -> str | None:
    """Text unter der ersten Überschrift (Ebene ≥ min_level), die `title_re` trifft,
    bis zur nächsten Überschrift gleicher oder höherer Ebene; None ohne Treffer."""
    lines = masked.splitlines()
    level = None
    body: list[str] = []
    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if match:
            depth = len(match.group(1))
            if level is not None and depth <= level:
                break
            if level is None and depth >= min_level and re.search(title_re, match.group(2), re.IGNORECASE):
                level = depth
            continue
        if level is not None:
            body.append(line)
    return "\n".join(body) if level is not None else None


def _spec_fences(text: str) -> tuple[list[list[str]], bool]:
    """(Inhalt jedes Codezauns ohne Markerzeilen, Zaun offen geblieben?) — dieselbe
    Zaun-Erkennung wie `_mask_fenced_blocks`: ein Marker darf eingerückt sein."""
    fences: list[list[str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if current is None:
                current = []
            else:
                fences.append(current)
                current = None
            continue
        if current is not None:
            current.append(line)
    return fences, current is not None


def _spec_structure(text: str) -> tuple[str | None, list[str] | None]:
    """(Skill-Name der Baumwurzel, Zeilen des Skill-Struktur-Blocks): der Zaun, dessen
    erste Zeile die Baumwurzel `skills/<name>/` ist. Ein Kommando-Zaun, der
    `skills/x/SKILL.md` nur nennt, ist kein Baum."""
    for fence in _spec_fences(text)[0]:
        content = [line for line in fence if line.strip()]
        if not content:
            continue
        root = SPEC_TREE_ROOT_RE.match(content[0])
        if root and any("SKILL.md" in line for line in content):
            return root.group(1), fence
    return None, None


def _spec_tree_entries(structure: list[str]) -> list[tuple[str, str]]:
    """(Pfad relativ zur Baumwurzel, Zeile) je Eintrag. Der Pfad-Token ist das erste
    Wort nach dem Baum-Präfix; Kommentare dahinter zählen nicht. Ordner (Token endet
    auf `/`) öffnen einen Kontext für tiefer eingerückte Zeilen, sodass `scripts/` +
    `    └── check.py` denselben Pfad ergibt wie `scripts/check.py`."""
    entries: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []  # (Einrückung, Ordnername)
    root_seen = False
    for line in structure:
        if not line.strip():
            continue
        stripped = SPEC_TREE_PREFIX_RE.sub("", line, count=1)
        token = stripped.split()[0] if stripped.split() else ""
        if not token:
            continue
        if not root_seen and SPEC_TREE_ROOT_RE.match(line):
            root_seen = True
            continue
        indent = len(SPEC_TREE_PREFIX_RE.match(line).group(0))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path = "".join(d for _, d in stack) + token
        entries.append((path, line))
        if token.endswith("/"):
            stack.append((indent, token))
    return entries


def _spec_tier_findings(entries: list[tuple[str, str]], own: set[str]) -> list[SpecFinding]:
    """Jedes Skript unter `scripts/` trägt „Tier N" in seiner Zeile — flach
    (`scripts/x.py Tier 1`) oder verschachtelt. Skripte anderer Skills
    (`skills/<andere>/…`), die eine Spec nur erweitert, sind nicht ihr Tier."""
    findings: list[SpecFinding] = []
    for path, line in entries:
        foreign = re.match(r"skills/([a-z][a-z0-9-]*)/", path)
        if foreign and foreign.group(1) not in own:
            continue
        if not path.endswith(SPEC_SCRIPT_EXT) or "scripts/" not in path:
            continue
        if not SPEC_TIER_RE.search(line):
            findings.append(SpecFinding("tier", f'{path} ohne „Tier N" in seiner Zeile der Skill-Struktur (Spec 00 §3)'))
    return findings


def _spec_own_names(text: str, spec_path: Path | str | None, tree_name: str | None) -> set[str]:
    """Dateiname und Baumwurzel — beide sind „diese Skill", auch wenn sie abweichen."""
    names = set()
    if spec_path is not None:
        match = re.search(r"Spec\s+\d+\s*[–-]\s*([a-z][a-z0-9-]*)", Path(spec_path).name)
        if match:
            names.add(match.group(1))
    if tree_name:
        names.add(tree_name)
    return names


def _spec_repo_root(spec_path: Path | str | None) -> Path | None:
    if spec_path is None:
        return None
    for parent in Path(spec_path).resolve().parents:
        if (parent / "skills").is_dir():
            return parent
    return None


def _spec_units(masked: str) -> list[str]:
    """Absätze, durch Leerzeilen getrennt; Tabellen- und Listenzeilen sind je eine
    eigene Einheit (wie `_units` in lint_skill.py) — die Spalte „nicht" im Tabellenkopf
    negiert nicht die Zeile darunter."""
    units: list[str] = []
    for para in re.split(r"\n\s*\n", masked):
        lines = [l for l in para.split("\n") if l.strip()]
        if not lines:
            continue
        if not any(SPEC_UNIT_MARKER_RE.match(l) for l in lines):
            units.append(para)
            continue
        current: list[str] = []
        for line in lines:
            if SPEC_UNIT_MARKER_RE.match(line) and current:
                units.append("\n".join(current))
                current = []
            current.append(line)  # eingerückte Fortsetzung eines Listenpunkts bleibt bei ihm
        if current:
            units.append("\n".join(current))
    return units


def lint_spec(text: str, spec_path: Path | str | None = None, repo_root: Path | str | None = None) -> list[SpecFinding]:
    """Formbefunde einer Skill-Spec. Alles Befunde, keine Abbrüche (G2: meldet).
    `repo_root` (sonst aus `spec_path` hergeleitet) entscheidet, welche Namen in
    der Abgrenzung als Skills zählen: Ordner unter `skills/` oder ein Name mit
    Namensraum (`superpowers:writing-skills`). Ohne Root zählen nur Namen mit
    Bindestrich oder Namensraum, und der Befund sagt das."""
    findings: list[SpecFinding] = []
    lines = _mask_fenced_blocks(text).splitlines()
    masked = "\n".join(lines)
    root = Path(repo_root) if repo_root is not None else _spec_repo_root(spec_path)

    # Offener Zaun: alles danach wäre maskiert, jede Meldung zeigte auf die falsche Stelle
    fences, unclosed = _spec_fences(text)
    if unclosed:
        findings.append(SpecFinding("fence", "ein Codezaun (```) wird nicht geschlossen — der Rest der Spec gilt als Code, die übrigen Befunde sind bis dahin unzuverlässig"))

    # Kopfzeile und Review-Vermerk
    header = None
    for line in text.splitlines()[:8]:
        if SPEC_HEADER_RE.match(line.strip()):
            header = line.strip()
            break
    if header is None:
        findings.append(SpecFinding("header", 'Kopfzeile „Skill-Spezifikation · Zyklus N · Entscheidung: …" fehlt in den ersten acht Zeilen'))
    elif SPEC_REVIEW_NOTE not in header:
        findings.append(SpecFinding("review-note", f'Kopfzeile ohne „{SPEC_REVIEW_NOTE}" — skill-forge Schritt 1: Review durch einen Subagenten (references/spec-reviewer-prompt.md), dann Vermerk, dann dieser Lint'))

    # Die sieben Abschnitte, in dieser Reihenfolge
    h2 = [title for depth, title in _spec_headings(masked) if depth == 2]
    positions = []
    for name in SPEC_SECTIONS:
        idx = next((i for i, t in enumerate(h2) if t.lower().startswith(name.lower())), None)
        if idx is None:
            findings.append(SpecFinding("sections", f'Abschnitt „## {name}" fehlt'))
        else:
            positions.append(idx)
    if positions != sorted(positions):
        findings.append(SpecFinding("sections", "Abschnitte nicht in der Reihenfolge des Templates: " + " / ".join(SPEC_SECTIONS)))

    # Eval-Tabelle — einmal gesucht, Kopfzeile und IDs aus demselben Fund
    located = _locate_eval_table(lines)
    ids: list[str] = []
    if located is None:
        findings.append(SpecFinding("eval-table", "keine Tabelle mit Spalte `id` unter einer Evals-Überschrift — ohne sie prüft impl-plan keine Coverage"))
    else:
        cells = located[1]
        ids, malformed = _eval_table_rows(lines, located)
        missing = []
        for col in SPEC_EVAL_COLUMNS:
            options = col if isinstance(col, tuple) else (col,)
            if not any(any(c.startswith(o) for c in cells) for o in options):
                missing.append(" oder ".join(options))
        if missing:
            findings.append(SpecFinding("eval-table", "Pflichtspalten fehlen: " + ", ".join(missing)))
        if malformed:
            findings.append(SpecFinding("eval-table", "id-Zellen ohne Backtick-Wert: " + ", ".join(malformed[:3])))
        if not ids:
            findings.append(SpecFinding("eval-table", "Eval-Tabelle ohne Zeilen"))
        elif not any(i.startswith("anti-ceremony-") for i in ids):
            findings.append(SpecFinding("eval-table", "keine ID mit Präfix `anti-ceremony-` (Spec 00 §2, Pflicht-Eval)"))

    # Skill-Struktur-Block, Tier je Skript, Hook im Baum
    tree_name, structure = _spec_structure(text)
    own = _spec_own_names(text, spec_path, tree_name)
    entries = _spec_tree_entries(structure) if structure else []
    if structure is None:
        findings.append(SpecFinding("skill-structure", "kein Codeblock, der mit der Baumwurzel `skills/<name>/` beginnt und `SKILL.md` enthält — impl-plan leitet daraus die Tasks ab"))
    else:
        findings.extend(_spec_tier_findings(entries, own))
    has_hook = any(path.startswith("assets/hooks") for path, _ in entries)

    # Abgrenzung gegen mindestens zwei Nachbarn
    section = _spec_section(masked, r"\bAbgrenzung\b", min_level=2)
    if section is None:
        findings.append(SpecFinding("abgrenzung", 'keine Überschrift „Abgrenzung" — zwei Konkurrenten mit Rückverweis (Spec 00 §5)'))
    else:
        candidates = {n for n in SPEC_NAME_RE.findall(section) if n not in own}
        if root is not None:
            names = {n for n in candidates if ":" in n or (root / "skills" / n).is_dir()}
            if len(names) < 2:
                findings.append(SpecFinding("abgrenzung", f"weniger als zwei Nachbarn erkannt (Ordner unter skills/ oder Name mit Namensraum): {sorted(names) or 'keiner'}"))
        else:
            names = {n for n in candidates if ":" in n or "-" in n}
            if len(names) < 2:
                findings.append(SpecFinding("abgrenzung", f"weniger als zwei Namen in der Abgrenzung: {sorted(names) or 'keiner'} (ohne Repo-Root zählen nur Namen mit Bindestrich oder Namensraum)"))

    # Gate-Wörter: G3-Wortwahl nur, wenn der Baum einen Hook trägt (Pfad-Token
    # `assets/hooks/…`, kein Kommentar). Negation gilt je Einheit: Absatz, Tabellen-
    # oder Listenzeile — wie `_units` in lint_skill.py.
    if not has_hook:
        hits = [u for u in _spec_units(masked) if SPEC_GATE_WORD_RE.search(u) and not SPEC_NEGATION_RE.search(u)]
        for hit in hits[:3]:
            first = next(line.strip() for line in hit.splitlines() if line.strip())
            findings.append(SpecFinding("gate-language", f"G3-Wort ohne Hook in der Skill-Struktur und ohne Negation in derselben Einheit (Spec 00 §4): {first[:90]!r}"))

    # Platzhalter — Inline-Code und „Zitate" sind maskiert (eine Spec, die den
    # Platzhalter-Scan beschreibt, trägt keinen).
    prose = "\n".join(BACKTICK_SPAN_RE.sub("`…`", line) for line in lines)  # zeilenweise: ein einzelner Backtick weiter oben verschiebt sonst die Paarung
    prose = SPEC_QUOTE_SPAN_RE.sub('„…"', prose)
    placeholders = sorted({m.group(0) for m in PLACEHOLDER_RE.finditer(prose)})
    # Template-Reste nur dort, wo sie Schaden tun: `Zyklus NN` in der Kopfzeile und
    # `<…>` in einer Eval-ID (impl-plan macht daraus einen Task). `<name>` in einem
    # Kommandobeispiel ist Konvention, kein Rest.
    if header and re.search(r"Zyklus\s+NN\b", header):
        placeholders.append("Zyklus NN")
    placeholders += sorted(i for i in ids if "<" in i)
    if placeholders:
        findings.append(SpecFinding("placeholders", "Platzhalter oder Template-Reste: " + ", ".join(placeholders)))

    return findings


def spec_lint_meta(spec_path: Path | str, repo_root: Path | str | None = None) -> dict:
    return _artifact_meta("lint-spec", spec_path, repo_root=repo_root)


def _cmd_lint_spec(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec)
    try:
        text = spec_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Spec nicht lesbar: {exc}", file=sys.stderr)
        return 2
    findings = lint_spec(text, spec_path, repo_root=args.repo_root)
    number = spec_number(spec_path)
    legacy = number is not None and number < args.cutoff
    for f in findings:
        print(f.render())
    if not findings:
        print("Keine Befunde — Spec trägt alles, was impl-plan und skill-forge lesen.")
    elif legacy:
        print(f"{len(findings)} Befund(e) — Spec {number} liegt vor dem Cutoff {args.cutoff}: Historie, kein Fehlschlag.")
    else:
        print(f"{len(findings)} Befund(e). Beheben, bevor impl-plan den Plan schreibt.")
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "_meta": spec_lint_meta(spec_path, args.repo_root),
            "spec": str(spec_path),
            "number": number,
            "cutoff": args.cutoff,
            "findings": [{"rule": f.rule, "message": f.message} for f in findings],
            "status": "clean" if not findings else ("legacy" if legacy else "findings"),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if findings and not legacy else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan -> Tasks für subagent-dev")
    sub = parser.add_subparsers(dest="command", required=True)

    spec_lint = sub.add_parser("lint-spec", help="Skill-Spec prüfen: Kopfzeile mit Review-Vermerk, sieben Abschnitte, Eval-Tabelle, Skill-Struktur, Tier, Abgrenzung, Gate-Wörter")
    spec_lint.add_argument("spec", help="Pfad zur Spec (specs/Spec NN – <name>.md)")
    spec_lint.add_argument("--repo-root", help="Repo-Wurzel für die Nachbarn-Prüfung; sonst aus dem Spec-Pfad hergeleitet")
    spec_lint.add_argument("--cutoff", type=int, default=SPEC_LINT_CUTOFF, help=f"Specs ab dieser Nummer müssen sauber sein (Default {SPEC_LINT_CUTOFF}); ältere melden, scheitern nicht")
    spec_lint.add_argument("--out", help="Befunde zusätzlich als JSON-Artefakt schreiben")
    spec_lint.set_defaults(func=_cmd_lint_spec)

    gen = sub.add_parser("generate", help="Plan parsen, Gate fällen, Task-Dateien schreiben")
    gen.add_argument("plan", help="Pfad zum impl-plan- oder work-plan-Plan")
    gen.add_argument("--tasks", help="Kommagetrennte Task-IDs, sonst alle")
    gen.add_argument("--out-dir", default=str(Path(".skills") / "cache" / "tasks"))
    gen.set_defaults(func=_cmd_generate)

    lint = sub.add_parser("lint", help="Plan prüfen: warum ist eine Task unsicher, wo stehen Platzhalter, fehlt etwas im Kopf")
    lint.add_argument("plan", help="Pfad zum Plan")
    lint.add_argument("--spec", help="Spec-Datei: jede Eval-ID ihrer Eval-Tabelle braucht einen Task")
    lint.add_argument("--skill", help="Skill-Name: IDs aus evals/<skill>/evals.json müssen in der Spec vorkommen")
    lint.add_argument("--out", help="Befunde zusätzlich als JSON-Artefakt schreiben")
    lint.set_defaults(func=_cmd_lint)

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
