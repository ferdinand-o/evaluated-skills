"""Schema-Test für evals/human-prose/evals.json (Spec 19, Task 6): lädt über evalkit,
und die Regexe treffen die Fixture-Texte so, wie die Spec es sagt."""

import json
import re
from pathlib import Path

from conftest import REPO_ROOT
from evalkit.schema import load_evals

EVALS = REPO_ROOT / "evals" / "human-prose" / "evals.json"
FIXTURES = REPO_ROOT / "evals" / "fixtures"


def _eval(eid):
    return next(e for e in load_evals(EVALS) if e.id == eid)


def test_loads_and_has_the_five_ids_from_the_spec():
    ids = [e.id for e in load_evals(EVALS)]
    assert ids == [
        "anti-ceremony-short-mail-no-measurement", "revise-writes-before-and-after",
        "vague-text-asks-instead-of-inventing", "long-draft-ends-with-measurement-line",
        "routing-sounds-like-ai-without-skill-name",
    ]
    assert all(e.eval_class == "contract" for e in load_evals(EVALS))
    assert all("iskriminator" in e.notes for e in load_evals(EVALS))


def test_fixtures_exist_with_git_and_at_least_one_file():
    for e in load_evals(EVALS):
        fixture = FIXTURES / e.fixture
        manifest = json.loads((fixture / "fixture.json").read_text(encoding="utf-8"))
        assert manifest["git"] is True, e.fixture
        assert [p for p in fixture.iterdir() if p.name != "fixture.json"], f"{e.fixture}: eine Git-Fixture ohne Datei scheitert am leeren Commit"


def test_revise_must_not_patterns_hit_the_fixture_before_the_run():
    text = (FIXTURES / "hp-cache" / "text.md").read_text(encoding="utf-8")
    for a in _eval("revise-writes-before-and-after").must_not:
        assert re.search(a.pattern, text, re.MULTILINE), a.pattern
    assert len(re.findall(r"(?i)zusammenfassend lässt sich sagen|es ist wichtig zu beachten|entscheidende Rolle", text)) == 3


def test_vague_fixture_has_the_vague_phrases_and_no_number():
    text = (FIXTURES / "hp-vague" / "text.md").read_text(encoding="utf-8")
    ev = _eval("vague-text-asks-instead-of-inventing")
    number, vague = ev.must_not
    assert not re.search(number.pattern, text)
    assert re.search(vague.pattern, text)


def test_measurement_line_pattern_matches_the_scripts_summary_format():
    ev = _eval("long-draft-ends-with-measurement-line")
    line = next(a for a in ev.must if a.type == "output_matches").pattern
    assert re.search(line, "Nachgemessen: 9 pass, 3 Befunde, 2 ungeprüft", re.MULTILINE)
    assert not re.search(line, "Nachgemessen: alles gut", re.MULTILINE)


def test_meta_pattern_matches_json_dumps_with_indent():
    payload = json.dumps({"_meta": {"skill": "human-prose", "schema": 1}}, indent=2)
    pattern = next(a for a in _eval("routing-sounds-like-ai-without-skill-name").must if a.type == "file_matches").pattern
    assert re.search(pattern, payload)
