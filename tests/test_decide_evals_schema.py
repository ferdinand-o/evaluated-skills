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
                   "CONTRIBUTING.md")
CALL = 'python "${CLAUDE_SKILL_DIR}/scripts/decide_log.py" '
# Claude Code ersetzt `${CLAUDE_SKILL_DIR}` nur in der SKILL.md (Spec 25, lint `script-paths`); eine
# Reference schreibt `decide_log.py …` für den Aufruf, den die SKILL.md mit vollem Pfad nennt.
PREFIX = {"SKILL.md": CALL, "option-memo.md": "decide_log.py "}
FENCE_RE = re.compile(r"^\s*(```|~~~)")
PLACEHOLDER_RE = re.compile(r"<[^<>\s]+>")
FLAG_DEST = {"--topic": "topic", "--question": "question", "--key": "key", "--recommendation": "recommendation",
             "--decision": "decision", "--evidence": "evidence"}


def _assertions(ev):
    return [*ev.must, *ev.must_not]


def _spec_evals_section():
    text = SPEC.read_text(encoding="utf-8")
    return text[text.index("### Evals"):text.index("## Alternatives considered")]


def _cells(line):
    """Zellen einer Markdown-Tabellenzeile; ein `|` in Backticks trennt nicht."""
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
    Assertion, ein Wert nach „und“ eine weitere desselben Typs; Backticks in Klammern zählen nicht."""
    types, values, depth, last, between = [], [], 0, None, ""
    for token in re.findall(r"`[^`]*`|[^`]+", cell):
        if not token.startswith("`"):
            depth += token.count("(") - token.count(")")
            between += token
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
    """Abweichungen zwischen `evals` und der Eval-Tabelle der Spec, in beiden Richtungen."""
    table = _spec_evals_section().splitlines()
    problems = []
    for ev in evals:
        row = next(line for line in table if f"`{ev.id}`" in line)
        for assertion in _assertions(ev):
            if f"`{assertion.type}`" not in row:
                problems.append((ev.id, assertion.type))
            for value in (assertion.pattern, assertion.path):
                if value is not None and f"`{value}`" not in row:
                    problems.append((ev.id, value))
        types, values = _row_assertions(_cells(row)[4])
        if types != Counter(a.type for a in _assertions(ev)):
            problems.append((ev.id, "Tabelle", dict(types), "evals.json", dict(Counter(a.type for a in _assertions(ev)))))
        known = {v for a in _assertions(ev) for v in (a.pattern, a.path) if v is not None}
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
    assert _table_problems(load_evals(copy))


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
        for token in (a.pattern for a in _assertions(ev) if a.type == "output_matches"):
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
    tokens = [a.pattern for ev in load_evals(EVALS_PATH) for a in _assertions(ev) if a.type == "output_matches"]
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
    assert _token_problems(SKILL_MD.read_text(encoding="utf-8"), copy)


def test_doctrine_borrows_no_eval_vocabulary():
    for path in [SKILL_MD, *sorted((SKILL_DIR / "references").glob("*.md"))]:
        text = path.read_text(encoding="utf-8")
        assert [word for word in EVAL_VOCABULARY if word in text] == [], path.name


def _calls(path):
    """(Aufrufe in Codezäunen, Zeilen mit `python ` außerhalb); Fortsetzungen mit `\\` zusammengezogen."""
    calls, outside, fenced, pending = [], [], False, ""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE_RE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            if "python " in line or '"$D"' in line:
                outside.append(f"{path.name}:{number}")
            continue
        text = pending + line.strip()
        if text.endswith("\\"):
            pending = text[:-1]
            continue
        pending = ""
        if "decide_log.py" in text:
            calls.append(text)
    return calls, outside


def _mandatory():
    """Pflichtfelder je Weg aus der Tabelle in option-memo.md: {Weg: (Flags, mit Optionen)}."""
    lines = OPTION_MEMO.read_text(encoding="utf-8").splitlines()
    start = lines.index("| Weg | Pflicht | Optionen | Schlüssel |")
    paths = {}
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        weg, pflicht, optionen, _ = _cells(line)
        paths[weg] = (re.findall(r"`(--[a-z-]+)`", pflicht), optionen.startswith("zwei bis vier"))
    return paths


def test_doctrine_calls_parse_with_their_mandatory_fields():
    """Jeder Aufruf in SKILL.md und option-memo.md steht in einem Codezaun — in der SKILL.md mit vollem
    Pfad (keine Shell-Variable, die den nächsten Bash-Aufruf nicht überlebt), in option-memo.md als
    `decide_log.py …` —, parst mit dem echten Parser, wenn `<…>` ersetzt ist, und trägt bei `add` die
    Pflichtfelder seines Wegs aus option-memo.md."""
    parser = decide_script().build_parser()
    mandatory = _mandatory()
    for path in (SKILL_MD, OPTION_MEMO):
        calls, outside = _calls(path)
        assert calls, path.name
        assert outside == [], outside
        for call in calls:
            prefix = PREFIX[path.name]
            assert call.startswith(prefix), call
            args = parser.parse_args(shlex.split(PLACEHOLDER_RE.sub("x", call[len(prefix):])))
            if args.action != "add":
                continue
            if args.cls == "klein":
                weg = next(w for w in mandatory if w.startswith("`add --class klein`"))
            elif args.approved_by_request:
                weg = next(w for w in mandatory if "--approved-by-request" in w)
            else:
                weg = "`add --class gross`"
            flags, with_options = mandatory[weg]
            assert [f for f in flags if not getattr(args, FLAG_DEST[f])] == [], (path.name, call)
            if with_options and args.cls == "gross":
                assert 2 <= len(args.options or []) <= 4, (path.name, call)
