"""Strukturprüfung von evals/decide/evals.json (Spec 28, Abschnitt Evals). Läuft keine Evals —
kein Agentenlauf, kein `claude`-Aufruf.

Die Tests fangen die Fehler, die die Evals lautlos entwerten würden: ein Assertion-Typ, den
evalkit nicht kennt; ein fehlender Anti-Zeremonie-Eval; ein Token in `output_matches`, den die
Doktrin nicht mehr so schreibt (dann bliebe der Eval rot, ohne dass die Skill schlechter wäre);
Prompt oder Muster, die von der Eval-Tabelle der Spec abweichen.
"""

import json
import re

from conftest import REPO_ROOT, decide_script
from evalkit.schema import ASSERTION_TYPES, load_evals

EVALS_PATH = REPO_ROOT / "evals" / "decide" / "evals.json"
FIXTURES = REPO_ROOT / "evals" / "fixtures"
SKILL_MD = REPO_ROOT / "skills" / "decide" / "SKILL.md"
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


def _assertions(ev):
    return [*ev.must, *ev.must_not]


def _spec_evals_section():
    text = SPEC.read_text(encoding="utf-8")
    return text[text.index("### Evals"):text.index("## Alternatives considered")]


def test_evals_load_with_the_five_ids_of_the_spec():
    evals = load_evals(EVALS_PATH)
    assert [ev.id for ev in evals] == IDS
    assert all(ev.eval_class == "contract" for ev in evals)


def test_exactly_one_anti_ceremony_eval():
    ids = [ev.id for ev in load_evals(EVALS_PATH)]
    assert [i for i in ids if i.startswith("anti-ceremony-")] == ["anti-ceremony-order-in-file-needs-no-decision"]


def test_assertion_types_come_from_evalkit_only():
    raw = json.loads(EVALS_PATH.read_text(encoding="utf-8"))["evals"]
    for ev in raw:
        for assertion in [*ev["must"], *ev.get("must_not", [])]:
            assert assertion["type"] in ASSERTION_TYPES, (ev["id"], assertion["type"])


def test_prompts_are_verbatim_from_the_spec():
    """Spec 28 bricht die Prompts im Fließtext um; verglichen wird nach Zusammenziehen von Leerraum."""
    section = _spec_evals_section()
    paragraph = section[section.index("Prompts:"):section.index("Die Prompts 2 bis 5")]
    quoted = {int(n): " ".join(p.split()) for n, p in re.findall(r"(\d) „(.*?)\"", paragraph, re.DOTALL)}
    assert sorted(quoted) == [1, 2, 3, 4, 5]
    for number, ev in enumerate(load_evals(EVALS_PATH), 1):
        assert ev.prompt == quoted[number], ev.id


def test_patterns_and_paths_are_verbatim_from_the_spec_table():
    """Jedes Muster und jeder Pfad steht so in der Eval-Tabelle — `\\x7c` eingeschlossen."""
    table = _spec_evals_section()
    for ev in load_evals(EVALS_PATH):
        row = next(line for line in table.splitlines() if f"`{ev.id}`" in line)
        for assertion in _assertions(ev):
            assert f"`{assertion.type}`" in row, (ev.id, assertion.type)
            for value in (assertion.pattern, assertion.path):
                if value is not None:
                    assert f"`{value}`" in row, (ev.id, value)


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


def test_output_tokens_stand_verbatim_in_skill_md():
    """Jeder `output_matches`-Token ist ein Literal und steht wörtlich in SKILL.md.

    Ausnahme mit eigener Verdrahtung: Den Token der Schlusszeile von `check` erzeugt nicht die
    Doktrin, sondern `decide_log.py` (`tail_line` aus `references/reversibility.md`); SKILL.md
    verlangt nur, die Zeile „ungeprüft: …“ wörtlich weiterzugeben. Für ihn gilt: Er ist der
    Anfang der echten Schlusszeile, und SKILL.md nennt „<Kopf>: …“ mit demselben Kopf.
    """
    skill = SKILL_MD.read_text(encoding="utf-8")
    dl = decide_script()
    categories, problem = dl.load_categories(dl.REFERENCE)
    assert problem is None
    tail = dl.tail_line(categories)

    tokens = [a.pattern for ev in load_evals(EVALS_PATH) for a in _assertions(ev) if a.type == "output_matches"]
    assert tokens == ["Keine Entscheidung nötig", "ungeprüft: data-delete"]
    for token in tokens:
        assert not set(token) & REGEX_META, token
        if token in skill:
            continue
        head = token.split(":", 1)[0] + ":"
        assert tail.startswith(token), (token, tail)
        assert f"„{head} …“" in skill, f"SKILL.md verlangt die Zeile „{head} …“ nicht mehr"
