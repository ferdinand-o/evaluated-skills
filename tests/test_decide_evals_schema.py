"""Strukturprüfung von evals/decide/evals.json (Spec 28, Abschnitt Evals) und der Aufrufe in der
Doktrin. Läuft keine Evals — kein Agentenlauf, kein `claude`-Aufruf.

Die Tests fangen die Fehler, die die Evals lautlos entwerten würden: ein fehlender
Anti-Zeremonie-Eval; ein Token in `output_matches`, den die Doktrin nicht mehr so schreibt oder den
`check` nicht mehr so ausgibt (dann bliebe der Eval rot, ohne dass die Skill schlechter wäre);
Prompt, Muster oder Zahl der Assertions, die von der Eval-Tabelle der Spec abweichen; Vokabular
der Eval-Prompts in der Doktrin (dann mäße ein grüner Eval den Mustervergleich mit dem Beispiel,
nicht das Urteil); ein Aufruf in SKILL.md oder `references/option-memo.md`, der so, wie er dasteht,
nicht parst oder ein Pflichtfeld auslässt.
"""

import argparse
import json
import re
import shlex
from collections import Counter

from conftest import REPO_ROOT, decide_script
from evalkit.schema import ASSERTION_TYPES, load_evals

EVALS_PATH = REPO_ROOT / "evals" / "decide" / "evals.json"
FIXTURES = REPO_ROOT / "evals" / "fixtures"
SKILL_DIR = REPO_ROOT / "skills" / "decide"
SKILL_MD = SKILL_DIR / "SKILL.md"
OPTION_MEMO = SKILL_DIR / "references" / "option-memo.md"
REVERSIBILITY = SKILL_DIR / "references" / "reversibility.md"
SPEC = REPO_ROOT / "specs" / "Spec 28 – decide.md"

IDS = [
    "anti-ceremony-order-in-file-needs-no-decision",
    "small-decision-cites-repo-source",
    "side-decision-expensive-stays-open",
    "user-order-is-approval",
    "always-ask-rule-upgrades-small",
]
ROUTING = "roter Lauf zuerst als Routing-Fehler prüfen"
REGEX_META = set(".^$*+?{}[]\\|()")
CHECK_TOKEN_EVAL = "user-order-is-approval"      # sein output_matches-Token ist die Schlusszeile von check
# Wörter aus den Eval-Prompts (und `alt_kennung`, die Übersetzung von `legacy_id`), die kein
# Beispiel der Doktrin tragen darf.
EVAL_VOCABULARY = ("legacy_id", "alt_kennung", "verständlicher", "load_products", "Ladefunktion", "sync()",
                   "CONTRIBUTING.md", "nirgends mehr gelesen", "Aufgabe:")
CALL = 'python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" '
# Claude Code ersetzt `${CLAUDE_SKILL_DIR}` nur in der SKILL.md (Spec 25, lint `script-paths`); eine
# Reference schreibt `decide_log.py …` für den Aufruf, den die SKILL.md mit vollem Pfad nennt.
PREFIX = {"SKILL.md": CALL, "option-memo.md": "decide_log.py "}
FENCE_RE = re.compile(r"^\s*(```|~~~)")
PLACEHOLDER_RE = re.compile(r"<[^<>\s]+>")
SPAN_RE = re.compile(r"`([^`]+)`")
# Eine Inline-Code-Spanne, die so beginnt, ist ein Aufruf (in der SKILL.md nur im Codezaun erlaubt).
INLINE_CALL_RE = re.compile(r"decide_log\.py\s+\S|(add|resolve|check)\b.*\s--", re.DOTALL)
UPGRADED_TOPIC = "<regelthema>"     # Platzhalter für das Thema einer Regel `immer fragen`


def _spec_evals_section():
    text = SPEC.read_text(encoding="utf-8")
    return text[text.index("### Evals"):text.index("## Alternatives considered")]


def _cells(line):
    """Zellen einer Zeile der Eval-Tabelle der Spec; ein `|` in Backticks trennt nicht. Nicht
    `_table_cells` aus decide_log.py: Ein Muster dieser Tabelle trägt ein `|` in Backticks
    (`(migration|data-delete)` in Eval 3), das dort trennen würde."""
    cells, current, code = [], "", False
    for char in line.strip().strip("|"):
        if char == "`":
            code = not code
        if char == "|" and not code:
            cells.append(current.strip())
            current = ""
        else:
            current += char
    return [*cells, current.strip()]


def _row_assertions(cell):
    """(Typen mit Vielfachheit, Werte) einer Zelle Assertions: Ein Typ in Backticks beginnt eine
    Assertion, ein Wert nach „und“ eine weitere desselben Typs. Eine Klammer außerhalb von Backticks
    zählt samt Inhalt nicht — weder ihre Backtick-Werte noch ein „und“ darin."""
    types, values, depth, last, between = [], [], 0, None, ""
    for token in re.findall(r"`[^`]*`|[^`]+", cell):
        if not token.startswith("`"):
            for char in token:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth = max(depth - 1, 0)
                elif not depth:
                    between += char
            continue
        if depth:
            continue
        value = token[1:-1]
        if value in ASSERTION_TYPES:
            types.append(value)
            last = value
        else:
            if re.search(r"\bund\b", between) and last:
                types.append(last)
            values.append(value)
        between = ""
    return Counter(types), values


def _table_problems(evals):
    """Abweichungen zwischen `evals` und der Eval-Tabelle der Spec, in beiden Richtungen. Die Tabelle
    kennt nur must; ein Eintrag in must_not ist eine Abweichung, verglichen wird nur must."""
    table = _spec_evals_section().splitlines()
    column = _cells(next(line for line in table if line.startswith("|"))).index("Assertions")
    problems = []
    for ev in evals:
        if ev.must_not:
            problems.append((ev.id, "must_not nicht leer", [a.type for a in ev.must_not]))
        row = next(line for line in table if f"`{ev.id}`" in line)
        for assertion in ev.must:
            if f"`{assertion.type}`" not in row:
                problems.append((ev.id, assertion.type))
            for value in (assertion.pattern, assertion.path):
                if value is not None and f"`{value}`" not in row:
                    problems.append((ev.id, value))
        types, values = _row_assertions(_cells(row)[column])
        counted = Counter(a.type for a in ev.must)
        if types != counted:
            problems.append((ev.id, "Tabelle", dict(types), "evals.json", dict(counted)))
        known = {v for a in ev.must for v in (a.pattern, a.path) if v is not None}
        problems.extend((ev.id, "nur in der Tabelle", value) for value in values if value not in known)
    return problems


def test_evals_load_with_the_five_ids_of_the_spec():
    evals = load_evals(EVALS_PATH)
    assert [ev.id for ev in evals] == IDS
    assert all(ev.eval_class == "contract" for ev in evals)


def test_prompts_are_verbatim_from_the_spec():
    """Spec 28 bricht die Prompts im Fließtext um; verglichen wird nach Zusammenziehen von Leerraum."""
    section = _spec_evals_section()
    paragraph = section[section.index("Prompts:"):section.index("Die Prompts 2 bis 5")]
    quoted = {int(n): " ".join(p.split()) for n, p in re.findall(r"(\d) „(.*?)\"", paragraph, re.DOTALL)}
    assert sorted(quoted) == [1, 2, 3, 4, 5]
    for number, ev in enumerate(load_evals(EVALS_PATH), 1):
        assert ev.prompt == quoted[number], ev.id


def test_evals_match_the_spec_table_both_ways():
    """Jedes Muster und jeder Pfad steht so in der Eval-Tabelle — `\\x7c` eingeschlossen —, und
    jede Assertion der Tabellenzeile steht in evals.json."""
    assert _table_problems(load_evals(EVALS_PATH)) == []


def test_table_check_notices_a_deleted_assertion(tmp_path):
    raw = json.loads(EVALS_PATH.read_text(encoding="utf-8"))
    side = next(ev for ev in raw["evals"] if ev["id"] == "side-decision-expensive-stays-open")
    side["must"] = [a for a in side["must"] if a != {"type": "file_absent", "path": "migrations/0002_*.py"}]
    copy = tmp_path / "evals.json"
    copy.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    side_id = "side-decision-expensive-stays-open"
    assert _table_problems(load_evals(copy)) == [
        (side_id, "Tabelle", {"file_matches": 4, "artifact_header": 1, "file_absent": 1},
         "evals.json", {"file_matches": 4, "artifact_header": 1}),
        (side_id, "nur in der Tabelle", "migrations/0002_*.py"),
    ]


def test_table_check_notices_an_assertion_moved_to_must_not(tmp_path):
    """Die Tabelle der Spec kennt nur must; eine Assertion in must_not kehrt ihre Bedeutung um."""
    raw = json.loads(EVALS_PATH.read_text(encoding="utf-8"))
    side = next(ev for ev in raw["evals"] if ev["id"] == "side-decision-expensive-stays-open")
    moved = {"type": "file_absent", "path": "migrations/0002_*.py"}
    side["must"] = [a for a in side["must"] if a != moved]
    side["must_not"] = [moved]
    copy = tmp_path / "evals.json"
    copy.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    problems = _table_problems(load_evals(copy))
    assert ("side-decision-expensive-stays-open", "must_not nicht leer", ["file_absent"]) in problems


def test_row_assertions_skip_brackets_with_their_content():
    """Backtick-Werte und ein „und“ in Klammern zählen nicht."""
    types, values = _row_assertions("`file_matches` `app/m.py` (siehe `re.M` und `re.S`) auf `p`")
    assert (types, values) == (Counter({"file_matches": 1}), ["app/m.py", "p"])


def test_every_eval_has_a_git_fixture():
    for ev in load_evals(EVALS_PATH):
        meta = json.loads((FIXTURES / ev.fixture / "fixture.json").read_text(encoding="utf-8"))
        assert meta["git"] is True, ev.fixture
        assert meta["description"].strip(), ev.fixture


def test_notes_answer_the_discriminator_question():
    evals = {ev.id: ev for ev in load_evals(EVALS_PATH)}
    for ev in evals.values():
        assert "Diskriminator" in ev.notes, ev.id
    for eval_id in ("user-order-is-approval", "always-ask-rule-upgrades-small"):
        assert ROUTING in evals[eval_id].notes, eval_id


def _token_problems(skill, reference):
    """Was die `output_matches`-Token entwertet: Regex-Zeichen, ein Token, der nicht wörtlich auf
    einer Zeile von `skill` steht, und für den Token aus `CHECK_TOKEN_EVAL` eine Schlusszeile von
    check (`tail_line` aus `reference`), die nicht mit ihm beginnt."""
    dl = decide_script()
    categories, problem = dl.load_categories(reference)
    if problem:
        return [problem]
    tail = dl.tail_line(categories)
    problems = []
    for ev in load_evals(EVALS_PATH):
        for token in (a.pattern for a in ev.must if a.type == "output_matches"):
            if set(token) & REGEX_META:
                problems.append(f"{token}: Regex-Zeichen")
            if not any(token in line for line in skill.splitlines()):
                problems.append(f"„{token}“ steht auf keiner Zeile von SKILL.md")
            if ev.id == CHECK_TOKEN_EVAL and not tail.startswith(token):
                problems.append(f"Schlusszeile „{tail}“ beginnt nicht mit „{token}“")
    return problems


def test_output_tokens_stand_in_skill_md_and_in_the_check_tail():
    """Jeder `output_matches`-Token ist ein Literal und steht wörtlich auf einer Zeile von SKILL.md.
    Den Token der Schlusszeile von `check` erzeugt `decide_log.py` (`tail_line` aus
    `references/reversibility.md`); er muss deshalb auch der Anfang der echten Schlusszeile sein."""
    tokens = [a.pattern for ev in load_evals(EVALS_PATH) for a in ev.must if a.type == "output_matches"]
    assert tokens == ["Keine Entscheidung nötig", "ungeprüft: data-delete"]
    assert _token_problems(SKILL_MD.read_text(encoding="utf-8"), REVERSIBILITY) == []


def test_token_check_notices_a_reordered_reference_table(tmp_path):
    lines = REVERSIBILITY.read_text(encoding="utf-8").splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith("| `data-delete` |"))
    second = next(i for i, line in enumerate(lines) if line.startswith("| `unsaved-work` |"))
    lines[first], lines[second] = lines[second], lines[first]
    copy = tmp_path / "references" / "reversibility.md"
    copy.parent.mkdir()
    copy.write_text("".join(lines), encoding="utf-8")
    tail = decide_script().tail_line(decide_script().load_categories(copy)[0])
    assert tail.startswith("ungeprüft: unsaved-work, data-delete, ")
    assert _token_problems(SKILL_MD.read_text(encoding="utf-8"), copy) == [
        f"Schlusszeile „{tail}“ beginnt nicht mit „ungeprüft: data-delete“"]


def test_doctrine_borrows_no_eval_vocabulary():
    for path in [SKILL_MD, *sorted((SKILL_DIR / "references").glob("*.md"))]:
        text = path.read_text(encoding="utf-8")
        assert [word for word in EVAL_VOCABULARY if word in text] == [], path.name


def _calls(path):
    """(Aufrufe in Codezäunen, Stellen außerhalb): Fortsetzungen mit `\\` zusammengezogen. Außerhalb
    zählt eine Zeile mit `python ` oder `"$D"` und, in der SKILL.md, jede Inline-Code-Spanne nach
    `INLINE_CALL_RE` — auch über einen Zeilenumbruch."""
    calls, outside, fenced, pending, prose = [], [], False, "", []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE_RE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            if "python " in line or '"$D"' in line:
                outside.append(f"{path.name}:{number}")
            prose.append((number, line))
            continue
        text = pending + line.strip()
        if text.endswith("\\"):
            pending = text[:-1]
            continue
        pending = ""
        if "decide_log.py" in text:
            calls.append(text)
    if path.name == "SKILL.md":
        text = "\n".join(line for _, line in prose)
        starts = [sum(len(line) + 1 for _, line in prose[:i]) for i in range(len(prose))]
        for span in SPAN_RE.finditer(text):
            if INLINE_CALL_RE.match(span.group(1)):
                line = max(i for i, start in enumerate(starts) if start <= span.start())
                outside.append(f"{path.name}:{prose[line][0]}")
    return calls, outside


def _mandatory():
    """Pflichtfelder je Weg aus der Tabelle in option-memo.md: {Weg: (Flags, mit Optionen)}."""
    lines = OPTION_MEMO.read_text(encoding="utf-8").splitlines()
    start = lines.index("| Weg | Pflicht | Optionen | Schlüssel |")
    paths = {}
    for line in lines[start + 2:]:
        cells = decide_script()._table_cells(line)
        if cells is None:
            break
        weg, pflicht, optionen, _ = cells
        paths[weg] = (re.findall(r"`(--[a-z-]+)`", pflicht), optionen.startswith("zwei bis vier"))
    return paths


def _flag_dests(parser):
    """Option → dest des Unterbefehls `add`, aus dem echten Parser."""
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return {flag: action.dest for action in sub.choices["add"]._actions for flag in action.option_strings}


def _call_problems(path, prefix):
    """Was an den Aufrufen in `path` nicht stimmt, als Klartext (leer: alles in Ordnung). Ein klein-Aufruf
    mit dem Thema `<regelthema>` ist von `immer fragen` hochgestuft und braucht zwei bis vier `--option`
    wie ein großer; eine Tabellenänderung in option-memo.md wird Klartext, kein KeyError."""
    parser = decide_script().build_parser()
    dests = _flag_dests(parser)
    mandatory = _mandatory()
    calls, outside = _calls(path)
    problems = [f"{where}: Aufruf außerhalb eines Codezauns" for where in outside]
    if not calls:
        problems.append(f"{path.name}: kein Aufruf in einem Codezaun")
    for call in calls:
        if not call.startswith(prefix):
            problems.append(f"{path.name}: {call} — beginnt nicht mit {prefix}")
            continue
        upgraded = UPGRADED_TOPIC in call
        args = parser.parse_args(shlex.split(PLACEHOLDER_RE.sub("x", call[len(prefix):])))
        if args.action != "add":
            continue
        if args.cls == "klein":
            weg = next((w for w in mandatory if w.startswith("`add --class klein`")), None)
        elif args.approved_by_request:
            weg = next((w for w in mandatory if "--approved-by-request" in w), None)
        else:
            weg = "`add --class gross`" if "`add --class gross`" in mandatory else None
        if weg is None:
            problems.append(f"{OPTION_MEMO.name}: keine Zeile in „Pflichtfelder je Weg“ für {call}")
            continue
        flags, with_options = mandatory[weg]
        unknown = [f for f in flags if f not in dests]
        if unknown:
            problems.append(f"{OPTION_MEMO.name}: {weg} nennt {unknown}, die `add` nicht kennt")
            continue
        missing = [f for f in flags if not getattr(args, dests[f])]
        if missing:
            problems.append(f"{path.name}: {call} — fehlt {missing}")
        if with_options and (args.cls == "gross" or upgraded) and not 2 <= len(args.options or []) <= 4:
            problems.append(f"{path.name}: {call} — {len(args.options or [])} --option, erwartet zwei bis vier")
    return problems


def test_doctrine_calls_parse_with_their_mandatory_fields():
    """Jeder Aufruf in SKILL.md und option-memo.md steht in einem Codezaun — in der SKILL.md mit vollem
    Pfad (keine Shell-Variable, die den nächsten Bash-Aufruf nicht überlebt), in option-memo.md als
    `decide_log.py …` —, parst mit dem echten Parser, wenn `<…>` ersetzt ist, und trägt bei `add` die
    Pflichtfelder seines Wegs aus option-memo.md."""
    for path in (SKILL_MD, OPTION_MEMO):
        assert _call_problems(path, PREFIX[path.name]) == []


UPGRADED_SMALL = (CALL + 'add --class klein --topic "<regelthema>" --question "<frage>" --decision "<wahl>" '
                  '--evidence "gesucht: … — Treffer: <datei:zeile>"')


def test_call_check_notices_an_upgraded_small_call_without_options(tmp_path):
    """Ein von `immer fragen` hochgestufter klein-Aufruf (Thema `<regelthema>`) ohne `--option` endet im
    Skript mit Exit 1; der Abgleich meldet ihn."""
    doc = tmp_path / "SKILL.md"
    doc.write_text(f"```bash\n{UPGRADED_SMALL}\n```\n", encoding="utf-8")
    assert _call_problems(doc, CALL) == [f"SKILL.md: {UPGRADED_SMALL} — 0 --option, erwartet zwei bis vier"]


def test_call_check_notices_calls_in_prose(tmp_path):
    """Eine Inline-Code-Spanne in der SKILL.md, die mit `decide_log.py` und einem Unterbefehl oder mit
    einem Unterbefehl samt Option beginnt, ist ein Aufruf außerhalb eines Codezauns — auch umbrochen."""
    doc = tmp_path / "SKILL.md"
    doc.write_text("Prosa nennt `decide_log.py add --class gross --topic <t> --key …` ohne Frage,\n"
                   "dann `resolve D-<n>\n--answer …` und `decide_log.py` als Name.\n"
                   f"```bash\n{CALL}open\n```\n", encoding="utf-8")
    assert _call_problems(doc, CALL) == ["SKILL.md:1: Aufruf außerhalb eines Codezauns",
                                         "SKILL.md:2: Aufruf außerhalb eines Codezauns"]
