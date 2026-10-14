import json
import stat
from pathlib import Path

import pytest

import evalkit.runner as runner_module
from evalkit.report import EvalResult, exit_code
from evalkit.runner import grade, main, run_one
from evalkit.schema import Assertion, Eval


def make_fake_cli(tmp_path: Path, body: str) -> str:
    script = tmp_path / "fake-claude"
    script.write_text("#!/bin/bash\n" + body, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def make_minimal_skill(tmp_path: Path, name: str = "s") -> Path:
    skill_dir = tmp_path / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
    return skill_dir


def make_eval(must=(), must_not=(), eval_class="contract"):
    return Eval(id="e", eval_class=eval_class, prompt="p", must=tuple(must), must_not=tuple(must_not))


def test_passes_when_all_must_hold(tmp_path):
    (tmp_path / "handoff.md").write_text("x", encoding="utf-8")
    ev = make_eval(must=[Assertion(type="file_exists", path="handoff.md")])
    assert grade(ev, tmp_path, {}, {}).passed


def test_fails_when_a_must_is_unmet(tmp_path):
    ev = make_eval(must=[Assertion(type="file_exists", path="handoff.md")])
    result = grade(ev, tmp_path, {}, {})
    assert not result.passed
    assert "must" in result.failures[0]


def test_must_not_is_inverted(tmp_path):
    """must_not ist erfüllt, wenn die Beobachtung NICHT zutrifft."""
    ev = make_eval(
        must=[Assertion(type="file_absent", path="egal.md")],
        must_not=[Assertion(type="file_exists", path="CLAUDE.md")],
    )
    assert grade(ev, tmp_path, {}, {}).passed
    (tmp_path / "CLAUDE.md").write_text("x", encoding="utf-8")
    result = grade(ev, tmp_path, {}, {})
    assert not result.passed
    assert "must_not" in result.failures[0]


def test_judge_verdicts_are_honoured(tmp_path):
    ev = make_eval(
        must=[Assertion(type="judge", claim="A")],
        eval_class="behavior",
    )
    assert grade(ev, tmp_path, {}, {"A": True}).passed
    assert not grade(ev, tmp_path, {}, {"A": False}).passed


def test_missing_judge_verdict_is_a_failure(tmp_path):
    ev = make_eval(must=[Assertion(type="judge", claim="A")], eval_class="behavior")
    result = grade(ev, tmp_path, {}, {})
    assert not result.passed
    assert "kein Urteil" in result.failures[0]


def test_run_one_survives_unexpected_exception_and_reports_harness_error(tmp_path, monkeypatch):
    """Eine kaputte Fixture (oder jeder andere unerwartete Fehler in einer aufgerufenen
    Funktion) darf den Batch nicht mit einem unbehandelten Traceback beenden — run_one()
    muss ihn als Harness-Fehler zurückgeben, damit die Schleife in main() weiterläuft."""
    ev = make_eval(must=[Assertion(type="file_exists", path="x")])
    skill_dir = tmp_path / "skills" / "s"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: s\n---\n", encoding="utf-8")

    def boom(*args, **kwargs):
        raise ZeroDivisionError("kaputt")

    monkeypatch.setattr(runner_module, "prepare", boom)

    result = run_one(
        ev, skill_dir=skill_dir, fixtures_dir=tmp_path / "fixtures",
        cli="claude", timeout=5, keep=False,
    )

    assert result.skipped
    assert not result.passed
    assert "ZeroDivisionError" in result.failures[0]
    assert ev.id in result.failures[0]
    # Genau dieses Ergebnis muss exit_code() auf 2 (Harness-Fehler) abbilden, nicht auf
    # Pythons Standard-1 oder ein stillschweigendes Durchwinken als normaler Fehlschlag.
    assert exit_code([result]) == 2


def test_run_one_happy_path_against_fake_cli(tmp_path):
    """run_one() hat vor diesem Fix keinen Test für den Happy Path — jeden echten Lauf
    nimmt aber genau dieser Pfad. Das Fake-CLI-Shellskript legt eine Datei an, wie es
    ein echter Agent im Workspace täte."""
    skill_dir = make_minimal_skill(tmp_path)
    cli = make_fake_cli(tmp_path, 'echo "neu" > new.txt\necho "erledigt"\nexit 0\n')
    ev = Eval(
        id="happy", eval_class="contract", prompt="p",
        must=(Assertion(type="file_exists", path="new.txt"),),
    )

    result = run_one(
        ev, skill_dir=skill_dir, fixtures_dir=tmp_path / "fixtures",
        cli=cli, timeout=10, keep=False,
    )

    assert result.passed
    assert not result.skipped
    assert result.failures == ()


def test_run_one_cleans_up_workspace_in_finally(tmp_path, monkeypatch):
    """run_one() räumt den Wegwerf-Workspace im finally auf — auch im Erfolgsfall,
    nicht nur bei Fehlern. Ohne Test wäre eine versehentliche Regel "nur bei Fehlschlag
    aufräumen" unbemerkt geblieben."""
    skill_dir = make_minimal_skill(tmp_path)
    cli = make_fake_cli(tmp_path, "exit 0\n")
    ev = Eval(
        id="cleanup", eval_class="contract", prompt="p",
        must=(Assertion(type="file_absent", path="nope.txt"),),
    )

    created: dict[str, str] = {}
    real_mkdtemp = runner_module.tempfile.mkdtemp

    def spy_mkdtemp(*args, **kwargs):
        path = real_mkdtemp(*args, **kwargs)
        created["path"] = path
        return path

    monkeypatch.setattr(runner_module.tempfile, "mkdtemp", spy_mkdtemp)

    run_one(
        ev, skill_dir=skill_dir, fixtures_dir=tmp_path / "fixtures",
        cli=cli, timeout=10, keep=False,
    )

    assert created.get("path"), "mkdtemp wurde nicht aufgerufen — Test greift nicht"
    assert not Path(created["path"]).exists()


def test_main_exits_2_when_skill_filter_matches_nothing(tmp_path, capsys):
    """main() und run_one() haben keine Unit-Tests, obwohl jeder echte Lauf durch sie
    geht. Ein Filter, der keine Skill trifft, muss Exit-Code 2 liefern (Harness-Fehler:
    zu eng oder evals/ leer), nicht 0 oder 1."""
    evals_dir = tmp_path / "evals"
    (evals_dir / "handoff").mkdir(parents=True)
    (evals_dir / "handoff" / "evals.json").write_text(
        json.dumps({
            "evals": [{
                "id": "x", "class": "contract", "prompt": "p",
                "must": [{"type": "file_exists", "path": "a"}],
            }]
        }),
        encoding="utf-8",
    )

    code = main([
        "--evals-dir", str(evals_dir),
        "--skills-dir", str(tmp_path / "skills"),
        "--skill", "does-not-exist-xyzzy",
    ])

    assert code == 2
    assert "Keine Evals" in capsys.readouterr().out


def test_home_skills_state_ignores_missing_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_module, "HOME_SKILLS", tmp_path / "gibt-es-nicht")
    assert runner_module._home_skills_state() == {}


def test_escapes_outside_the_workspace_are_reported(tmp_path, monkeypatch, capsys):
    """Ein Lauf, der unter ~/.skills schreibt, muss das melden.

    Spec 00 schickt Artefakte ohne Repo-Kontext nach ~/.skills/<skill>/, und der
    Harness isoliert HOME nicht. Eine Skill, deren Fixture kein .git mitbringt,
    schreibt deshalb regelkonform außerhalb jeder Assertion -- real geschehen und
    nur zufällig aufgefallen, weil sechs Evals mit "Datei existiert nicht"
    fielen, während die Dateien tadellos erzeugt worden waren, nur woanders.
    """
    home = tmp_path / "skills-home"
    (home / "visual-summary" / "summaries").mkdir(parents=True)
    monkeypatch.setattr(runner_module, "HOME_SKILLS", home)

    before = runner_module._home_skills_state()
    (home / "visual-summary" / "summaries" / "one-pager-x.md").write_text("neu", encoding="utf-8")
    runner_module._report_escapes(before, runner_module._home_skills_state(), "irgendein-eval")

    out = capsys.readouterr().out
    assert "WARNUNG [irgendein-eval]" in out
    assert "one-pager-x.md" in out
    assert '"git": true' in out


def test_untouched_home_reports_nothing(tmp_path, monkeypatch, capsys):
    home = tmp_path / "skills-home"
    home.mkdir()
    monkeypatch.setattr(runner_module, "HOME_SKILLS", home)
    state = runner_module._home_skills_state()
    runner_module._report_escapes(state, state, "irgendein-eval")
    assert capsys.readouterr().out == ""


# --- Spec 18: --without-skill und Sichtbarkeitsprüfung --------------------------------

def _init_line(skills):
    return json.dumps({"type": "system", "subtype": "init", "skills": skills})


def _verdict_line(claim, holds=True):
    payload = json.dumps({"verdicts": [{"claim": claim, "holds": holds, "why": "x"}]})
    return json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": payload}]}})


def make_stream_cli(tmp_path: Path, skills, *, touch: str = "new.txt") -> str:
    """Fake-CLI, das wie `claude -p` ein stream-json-Transcript schreibt: erst ein
    Fremd-Ereignis, dann das init-Ereignis mit `skills`, dann legt es eine Datei an."""
    body = (
        "echo '" + json.dumps({"type": "active_goal", "value": None}) + "'\n"
        "echo '" + _init_line(skills) + "'\n"
        f"echo neu > {touch}\n"
        "exit 0\n"
    )
    return make_fake_cli(tmp_path, body)


def _file_eval(eval_id="e", path="new.txt"):
    return Eval(id=eval_id, eval_class="contract", prompt="p", must=(Assertion(type="file_exists", path=path),))


def _run(tmp_path, cli, ev, **kwargs):
    skill_dir = tmp_path / "skills" / "s"
    if not skill_dir.is_dir():
        make_minimal_skill(tmp_path)
    return run_one(ev, skill_dir=skill_dir, fixtures_dir=tmp_path / "fixtures", cli=cli, timeout=10, keep=False, **kwargs)


def test_without_skill_visible_skill_is_harness_error(tmp_path):
    """Die Skill ist ohne Installation sichtbar (Profil, Plugin, Fixture) — das ist
    keine Baseline. Der Grund steht in `failures`, damit exit_code 2 liefert."""
    cli = make_stream_cli(tmp_path, ["deep-research", "s"])
    result = _run(tmp_path, cli, _file_eval(), without_skill=True)
    assert result.skipped
    assert result.baseline
    assert "Baseline unmöglich" in result.failures[0]
    assert "s" in result.failures[0]


def test_without_skill_grades_when_skill_absent(tmp_path):
    cli = make_stream_cli(tmp_path, ["deep-research", "verify"])
    result = _run(tmp_path, cli, _file_eval(), without_skill=True)
    assert not result.skipped
    assert result.baseline
    assert result.passed
    assert result.note == ""


def test_without_skill_installs_nothing_in_the_workspace(tmp_path):
    """Der Agent darf im Baseline-Workspace kein .claude/skills/ vorfinden."""
    body = (
        "echo '" + _init_line(["verify"]) + "'\n"
        "if [ -e .claude/skills ]; then echo installiert > seen.txt; fi\n"
        "exit 0\n"
    )
    cli = make_fake_cli(tmp_path, body)
    ev = Eval(id="e", eval_class="contract", prompt="p", must=(Assertion(type="file_absent", path="seen.txt"),))
    assert _run(tmp_path, cli, ev, without_skill=True).passed


def test_with_skill_missing_from_init_is_harness_error(tmp_path):
    """Normalmodus: Der Agent sah die Skill nicht (Frontmatter, das die CLI nicht
    parst; fehlgeschlagene Installation). Ein Verdikt wäre falsch rot oder falsch grün."""
    cli = make_stream_cli(tmp_path, ["deep-research", "verify"])
    result = _run(tmp_path, cli, _file_eval())
    assert result.skipped
    assert not result.baseline
    assert "nicht sichtbar" in result.failures[0]


def test_with_skill_visible_grades_normally(tmp_path):
    cli = make_stream_cli(tmp_path, ["deep-research", "s"])
    result = _run(tmp_path, cli, _file_eval())
    assert result.passed and not result.skipped and not result.baseline
    assert result.note == ""


def test_without_skills_field_verdict_is_unchanged(tmp_path):
    """Klartext-CLI, kein init-Ereignis: in beiden Modi das Verdikt wie heute, nur mit
    dem Hinweis, dass die Sichtbarkeit ungeprüft blieb — nie ein SKIP."""
    cli = make_fake_cli(tmp_path, 'echo "neu" > new.txt\necho "erledigt"\nexit 0\n')
    plain = _run(tmp_path, cli, _file_eval())
    base = _run(tmp_path, cli, _file_eval(), without_skill=True)
    for result in (plain, base):
        assert result.passed and not result.skipped
        assert "ungeprüft" in result.note
    assert not plain.baseline and base.baseline


def test_skill_name_defaults_to_the_skill_dir_name(tmp_path):
    """Bestehende Aufrufer geben keinen Namen mit — der Ordnername gilt."""
    skill_dir = make_minimal_skill(tmp_path, "probe")
    cli = make_stream_cli(tmp_path, ["probe"])
    result = run_one(_file_eval(), skill_dir=skill_dir, fixtures_dir=tmp_path / "fixtures", cli=cli, timeout=10, keep=False)
    assert result.passed and not result.skipped


def test_visibility_is_checked_on_the_eval_agent_not_the_judge(tmp_path):
    """Der Judge läuft über denselben run_agent in einem leeren Verzeichnis und sieht
    nichts installiert. Würde sein Transcript geprüft, wäre jeder behavior-Eval SKIP."""
    body = (
        'case "$PWD" in\n'
        "  *judge*) echo '" + _init_line([]) + "'; echo '" + _verdict_line("A") + "' ;;\n"
        "  *) echo '" + _init_line(["s"]) + "'; echo neu > new.txt ;;\n"
        "esac\nexit 0\n"
    )
    cli = make_fake_cli(tmp_path, body)
    ev = Eval(id="e", eval_class="behavior", prompt="p", must=(Assertion(type="judge", claim="A"),))
    result = _run(tmp_path, cli, ev)
    assert result.passed, result.failures
    assert not result.skipped


def _evals_dir(tmp_path):
    evals_dir = tmp_path / "evals"
    (evals_dir / "s").mkdir(parents=True)
    (evals_dir / "s" / "evals.json").write_text(
        json.dumps({"evals": [{"id": "x", "class": "contract", "prompt": "p",
                               "must": [{"type": "file_exists", "path": "new.txt"}]}]}),
        encoding="utf-8",
    )
    return evals_dir


def test_main_without_skill_exits_one_when_an_eval_is_green_without_skill(tmp_path, capsys):
    make_minimal_skill(tmp_path)
    cli = make_stream_cli(tmp_path, ["verify"])
    args = ["--evals-dir", str(_evals_dir(tmp_path)), "--skills-dir", str(tmp_path / "skills"), "--cli", cli]
    assert main(args + ["--without-skill"]) == 1
    out = capsys.readouterr().out
    assert "[GRÜN OHNE SKILL] x — misst nichts" in out
    assert "ohne Skill" in out.splitlines()[0]


def test_main_with_skill_exits_zero_for_the_same_green_eval(tmp_path, capsys):
    make_minimal_skill(tmp_path)
    cli = make_stream_cli(tmp_path, ["s"])
    args = ["--evals-dir", str(_evals_dir(tmp_path)), "--skills-dir", str(tmp_path / "skills"), "--cli", cli]
    assert main(args) == 0
    assert "[PASS] x" in capsys.readouterr().out


def test_permissions_reach_agent_and_judge(tmp_path):
    """--permissions gilt für den Eval-Agenten und den Judge; beide laufen über run_agent."""
    body = (
        'echo "$@" >> "' + str(tmp_path / "argv.log") + '"\n'
        'case "$PWD" in\n'
        "  *judge*) echo '" + _init_line([]) + "'; echo '" + _verdict_line("A") + "' ;;\n"
        "  *) echo '" + _init_line(["s"]) + "'; echo neu > new.txt ;;\n"
        "esac\nexit 0\n"
    )
    cli = make_fake_cli(tmp_path, body)
    ev = Eval(id="e", eval_class="behavior", prompt="p", must=(Assertion(type="judge", claim="A"),))
    skill_dir = make_minimal_skill(tmp_path, "s")
    result = run_one(ev, skill_dir=skill_dir, fixtures_dir=tmp_path / "fixtures", cli=cli, timeout=10,
                     keep=False, permissions="allowed-tools")
    assert result.passed, result.failures
    calls = [c for c in (tmp_path / "argv.log").read_text(encoding="utf-8").splitlines() if c.startswith("-p ")]
    assert len(calls) == 2 and all("--allowedTools" in c and "bypassPermissions" not in c for c in calls)


def test_root_refusal_is_loud_not_a_silent_skip(tmp_path, capsys):
    """Verweigert die CLI den Rechte-Modus, nennt der Runner Ursache und Abhilfe."""
    cli = make_fake_cli(tmp_path, 'echo "--dangerously-skip-permissions cannot be used with root/sudo '
                                  'privileges for security reasons" >&2\nexit 1\n')
    result = _run(tmp_path, cli, _file_eval())
    assert not result.passed
    assert "Rechte-Modus" in result.note and "--permissions allowed-tools" in " ".join(result.failures)
    assert "--permissions allowed-tools" in capsys.readouterr().err


def test_main_accepts_permissions_flag(tmp_path):
    make_minimal_skill(tmp_path)
    cli = make_stream_cli(tmp_path, ["s"])
    args = ["--evals-dir", str(_evals_dir(tmp_path)), "--skills-dir", str(tmp_path / "skills"), "--cli", cli]
    assert main(args + ["--permissions", "allowed-tools"]) == 0
