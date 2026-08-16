import json
import pytest
from evalkit.schema import Assertion, Eval, EvalSchemaError, load_evals


def write(tmp_path, payload):
    path = tmp_path / "evals.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


MINIMAL = {
    "evals": [
        {
            "id": "handoff-creates-file",
            "class": "contract",
            "prompt": "Wir hören hier auf für heute.",
            "must": [{"type": "file_exists", "path": "handoff.md"}],
        }
    ]
}


def test_loads_minimal_eval(tmp_path):
    evals = load_evals(write(tmp_path, MINIMAL))
    assert len(evals) == 1
    assert evals[0] == Eval(
        id="handoff-creates-file",
        eval_class="contract",
        prompt="Wir hören hier auf für heute.",
        must=(Assertion(type="file_exists", path="handoff.md"),),
        must_not=(),
        fixture=None,
        notes="",
    )


def test_rejects_contract_eval_with_judge_assertion(tmp_path):
    payload = {
        "evals": [
            {
                "id": "x",
                "class": "contract",
                "prompt": "p",
                "must": [{"type": "judge", "claim": "es ist gut"}],
            }
        ]
    }
    with pytest.raises(EvalSchemaError, match="contract"):
        load_evals(write(tmp_path, payload))


def test_rejects_empty_must(tmp_path):
    payload = {"evals": [{"id": "x", "class": "behavior", "prompt": "p", "must": []}]}
    with pytest.raises(EvalSchemaError, match="must"):
        load_evals(write(tmp_path, payload))


def test_rejects_duplicate_ids(tmp_path):
    ev = {"id": "same", "class": "contract", "prompt": "p",
          "must": [{"type": "file_exists", "path": "a"}]}
    with pytest.raises(EvalSchemaError, match="doppelt"):
        load_evals(write(tmp_path, {"evals": [ev, dict(ev)]}))


def test_rejects_file_matches_without_pattern(tmp_path):
    payload = {
        "evals": [
            {"id": "x", "class": "contract", "prompt": "p",
             "must": [{"type": "file_matches", "path": "a.md"}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match="pattern"):
        load_evals(write(tmp_path, payload))


def test_rejects_invalid_regex_pattern(tmp_path):
    """Eine kaputte Regex muss beim Laden auffallen, nicht nach dem Agentenlauf."""
    payload = {
        "evals": [
            {"id": "x", "class": "contract", "prompt": "p",
             "must": [{"type": "file_matches", "path": "a.md", "pattern": "^## Status ["}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match="Regex"):
        load_evals(write(tmp_path, payload))


def test_output_matches_needs_pattern_not_path(tmp_path):
    payload = {
        "evals": [
            {"id": "x", "class": "contract", "prompt": "p",
             "must": [{"type": "output_matches"}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match="pattern"):
        load_evals(write(tmp_path, payload))


def test_rejects_unknown_assertion_type(tmp_path):
    payload = {
        "evals": [
            {"id": "x", "class": "contract", "prompt": "p",
             "must": [{"type": "vibes_good", "path": "a"}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match="vibes_good"):
        load_evals(write(tmp_path, payload))


def test_rejects_absolute_path(tmp_path):
    """`root / '/etc/passwd'` liefert `/etc/passwd` — ein absoluter Pfad ersetzt die
    Workspace-Wurzel vollständig und ließe den Eval gegen das echte Repo laufen."""
    payload = {
        "evals": [
            {"id": "x", "class": "contract", "prompt": "p",
             "must": [{"type": "file_exists", "path": "/etc/passwd"}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match="absolut"):
        load_evals(write(tmp_path, payload))


def test_rejects_path_with_dotdot_component(tmp_path):
    payload = {
        "evals": [
            {"id": "x", "class": "contract", "prompt": "p",
             "must": [{"type": "file_exists", "path": "../../etc/passwd"}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match=r"\.\."):
        load_evals(write(tmp_path, payload))


def test_rejects_non_string_path(tmp_path):
    """`root / 123` würde erst beim Grading — nach dem bezahlten Agentenlauf — mit
    TypeError scheitern, aufgefangen nur vom generischen Sicherheitsnetz in run_one()."""
    payload = {
        "evals": [
            {"id": "x", "class": "contract", "prompt": "p",
             "must": [{"type": "file_exists", "path": 123}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match="Zeichenkette"):
        load_evals(write(tmp_path, payload))


def test_rejects_non_string_pattern(tmp_path):
    payload = {
        "evals": [
            {"id": "x", "class": "contract", "prompt": "p",
             "must": [{"type": "file_matches", "path": "a.md", "pattern": 123}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match="Zeichenkette"):
        load_evals(write(tmp_path, payload))


def test_rejects_non_string_claim(tmp_path):
    payload = {
        "evals": [
            {"id": "x", "class": "behavior", "prompt": "p",
             "must": [{"type": "judge", "claim": 123}]}
        ]
    }
    with pytest.raises(EvalSchemaError, match="Zeichenkette"):
        load_evals(write(tmp_path, payload))
