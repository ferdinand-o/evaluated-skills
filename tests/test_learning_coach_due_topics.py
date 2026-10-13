import json

from datetime import date

import pytest

from conftest import load_script

due_topics_mod = load_script("skills/learning-coach/scripts/due_topics.py")

ASSETS_PATH = None  # gesetzt in fixture unten


@pytest.fixture(autouse=True)
def _assets_path():
    global ASSETS_PATH
    ASSETS_PATH = due_topics_mod._default_assets_path()


def write_learner(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FULL_TOPIC = """\
<!-- skill: learning-coach | schema: 1 | generated: x -->

# Lernstand

## closures: JavaScript – Closures

- Gebiet: tech
- Beherrschungsgrad: 2
- Letzte Abfrage: 2026-08-10
- Nächste Fälligkeit: 2026-08-17
- Typische Fehler:
  - Verwechselt Closure mit Callback
  - Vergisst, dass die Variable per Referenz erfasst wird
- Offene Fragen:
  - Wie verhält sich das bei let vs var in Schleifen?
"""


# --- parse_learner: vollständiges Thema ---------------------------------------

def test_parse_full_topic():
    topics, warnings = due_topics_mod.parse_learner(FULL_TOPIC)
    assert warnings == []
    assert len(topics) == 1
    t = topics[0]
    assert t.slug == "closures"
    assert t.name == "JavaScript – Closures"
    assert t.gebiet == "tech"
    assert t.grade == 2
    assert t.last_query == date(2026, 8, 10)
    assert t.next_due == date(2026, 8, 17)
    assert t.typical_errors == [
        "Verwechselt Closure mit Callback",
        "Vergisst, dass die Variable per Referenz erfasst wird",
    ]
    assert t.open_questions == ["Wie verhält sich das bei let vs var in Schleifen?"]
    assert t.warnings == []


def test_parse_multiple_topics():
    text = FULL_TOPIC + "\n## rekursion: Rekursion\n\n- Beherrschungsgrad: 1\n"
    topics, _ = due_topics_mod.parse_learner(text)
    assert [t.slug for t in topics] == ["closures", "rekursion"]
    assert topics[1].grade == 1
    assert topics[1].next_due is None


# --- parse_learner: fehlende/unlesbare Felder (A4: nie stillschweigend) --------

def test_missing_next_due_is_none_not_crash():
    text = "## x: X\n\n- Beherrschungsgrad: 3\n- Letzte Abfrage: 2026-08-01\n"
    topics, _ = due_topics_mod.parse_learner(text)
    assert topics[0].next_due is None
    assert topics[0].warnings == []  # fehlend ist kein Warn-Fall, nur "leer"


def test_unreadable_date_warns_and_is_none():
    text = "## x: X\n\n- Nächste Fälligkeit: irgendwann\n"
    topics, _ = due_topics_mod.parse_learner(text)
    assert topics[0].next_due is None
    assert any("unlesbar" in w for w in topics[0].warnings)


def test_missing_grade_defaults_to_zero_with_warning():
    text = "## x: X\n\n- Nächste Fälligkeit: 2026-08-01\n"
    topics, _ = due_topics_mod.parse_learner(text)
    assert topics[0].grade == 0
    assert any("Beherrschungsgrad fehlt" in w for w in topics[0].warnings)


def test_grade_out_of_range_is_clamped_with_warning():
    text = "## x: X\n\n- Beherrschungsgrad: 9\n"
    topics, _ = due_topics_mod.parse_learner(text)
    assert topics[0].grade == 4
    assert any("außerhalb 0-4" in w for w in topics[0].warnings)


def test_malformed_heading_gets_derived_slug_and_warning():
    text = "## Nur ein Titel ohne Doppelpunkt\n\n- Beherrschungsgrad: 1\n"
    topics, _ = due_topics_mod.parse_learner(text)
    assert topics[0].slug == "nur-ein-titel-ohne-doppelpunkt"
    assert any("Kopfzeile ungültig" in w for w in topics[0].warnings)


def test_duplicate_slugs_are_flagged_at_file_level():
    text = "## x: Erstes X\n\n- Beherrschungsgrad: 1\n\n## x: Zweites X\n\n- Beherrschungsgrad: 2\n"
    topics, file_warnings = due_topics_mod.parse_learner(text)
    assert len(topics) == 2
    assert any("Doppelte Themen-Slugs" in w for w in file_warnings)


def test_empty_file_has_no_topics():
    topics, warnings = due_topics_mod.parse_learner("<!-- header -->\n\n# Lernstand\n")
    assert topics == []
    assert warnings == []


def test_example_topic_inside_html_comment_is_not_parsed():
    """Regression: Das Template zeigt ein Beispiel-Thema als '## slug: Name' innerhalb
    eines <!-- ... -->-Blocks. Das darf nicht als echtes Thema landen."""
    text = "<!--\n## beispiel: Beispiel-Thema\n\n- Beherrschungsgrad: 3\n-->\n\n# Lernstand\n"
    topics, _ = due_topics_mod.parse_learner(text)
    assert topics == []


# --- is_due / due_topics --------------------------------------------------------

def test_is_due_true_when_date_in_past():
    t = due_topics_mod.Topic("x", "X", None, 2, None, date(2020, 1, 1))
    assert due_topics_mod.is_due(t, date(2026, 8, 17)) is True


def test_is_due_false_when_date_in_future():
    t = due_topics_mod.Topic("x", "X", None, 2, None, date(2099, 1, 1))
    assert due_topics_mod.is_due(t, date(2026, 8, 17)) is False


def test_is_due_true_when_date_missing():
    t = due_topics_mod.Topic("x", "X", None, 2, None, None)
    assert due_topics_mod.is_due(t, date(2026, 8, 17)) is True


def test_due_topics_sorts_most_overdue_first():
    a = due_topics_mod.Topic("a", "A", None, 1, None, date(2026, 8, 1))
    b = due_topics_mod.Topic("b", "B", None, 1, None, date(2020, 1, 1))
    c = due_topics_mod.Topic("c", "C", None, 1, None, date(2099, 1, 1))  # nicht fällig
    result = due_topics_mod.due_topics([a, b, c], date(2026, 8, 17))
    assert [t.slug for t in result] == ["b", "a"]


# --- resolve_base_dir / ensure_learner ------------------------------------------

def test_resolve_base_dir_prefers_project_local(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".skills" / "learning-coach").mkdir(parents=True)
    home = tmp_path / "home"
    base_dir, is_local = due_topics_mod.resolve_base_dir(repo, "learning-coach", home=home)
    assert base_dir == repo / ".skills" / "learning-coach"
    assert is_local is True


def test_resolve_base_dir_falls_back_to_home(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    base_dir, is_local = due_topics_mod.resolve_base_dir(repo, "learning-coach", home=home)
    assert base_dir == home / ".skills" / "learning-coach"
    assert is_local is False


def test_ensure_learner_bootstraps_from_template(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    path, created = due_topics_mod.ensure_learner(repo, ASSETS_PATH, home=home)
    assert created is True
    assert path.is_file()
    assert "skill: learning-coach" in path.read_text(encoding="utf-8")
    assert "neu angelegt" in capsys.readouterr().out


def test_ensure_learner_does_not_overwrite_existing(tmp_path):
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    (home / ".skills" / "learning-coach").mkdir(parents=True)
    existing = home / ".skills" / "learning-coach" / "learner.md"
    existing.write_text("eigener Inhalt\n", encoding="utf-8")
    path, created = due_topics_mod.ensure_learner(repo, ASSETS_PATH, home=home)
    assert created is False
    assert path.read_text(encoding="utf-8") == "eigener Inhalt\n"


def test_exercises_path_uses_verified_research_namespace(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    path = due_topics_mod.exercises_path_for(repo, "closures", home=home)
    assert path == home / ".skills" / "verified-research" / "research" / "closures.exercises.json"


# --- exercises_status: fehlend/leer/kaputt/strukturell unerwartet (Review-Funde 3+6) --
#
# Top-Level-Form korrigiert nach Rückmeldung des Koordinators: exercise-forges
# echtes `export.py` liest `data.get("exercises", [])` — ein JSON-*Objekt* mit
# `"exercises"`-Liste, kein Top-Level-Array. Die ursprüngliche Fix-Runde hatte ein
# Top-Level-Array als "einzige tragfähige Annahme" aus dem Spec-13-Text abgeleitet;
# das war falsch, weil beide Skills parallel gebaut wurden und diese Annahme nie
# gegen den echten Erzeuger geprüft war.

def test_exercises_status_missing(tmp_path):
    status, _ = due_topics_mod.exercises_status(tmp_path / "nope.exercises.json")
    assert status == due_topics_mod.EXERCISES_STATUS_MISSING


def test_exercises_status_malformed_json(tmp_path):
    path = tmp_path / "x.exercises.json"
    path.write_text("{kaputt", encoding="utf-8")
    status, detail = due_topics_mod.exercises_status(path)
    assert status == due_topics_mod.EXERCISES_STATUS_MALFORMED
    assert "JSON" in detail


def test_exercises_status_top_level_array_is_malformed(tmp_path):
    """Ein bloßes Top-Level-Array ist jetzt die FALSCHE Form (frühere, korrigierte
    Annahme) — der echte Erzeuger liefert ein Objekt mit 'exercises'-Schlüssel."""
    path = tmp_path / "x.exercises.json"
    path.write_text('[{"typ": "mc"}]', encoding="utf-8")
    status, detail = due_topics_mod.exercises_status(path)
    assert status == due_topics_mod.EXERCISES_STATUS_MALFORMED
    assert "exercises" in detail


def test_exercises_status_missing_exercises_key_is_malformed(tmp_path):
    path = tmp_path / "x.exercises.json"
    path.write_text('{"topic": "css-grid"}', encoding="utf-8")
    status, detail = due_topics_mod.exercises_status(path)
    assert status == due_topics_mod.EXERCISES_STATUS_MALFORMED
    assert "exercises" in detail


def test_exercises_status_exercises_key_not_a_list_is_malformed(tmp_path):
    path = tmp_path / "x.exercises.json"
    path.write_text('{"exercises": "nicht-liste"}', encoding="utf-8")
    status, detail = due_topics_mod.exercises_status(path)
    assert status == due_topics_mod.EXERCISES_STATUS_MALFORMED
    assert "exercises" in detail


def test_exercises_status_empty_exercises_list(tmp_path):
    path = tmp_path / "x.exercises.json"
    path.write_text('{"exercises": []}', encoding="utf-8")
    status, detail = due_topics_mod.exercises_status(path)
    assert status == due_topics_mod.EXERCISES_STATUS_EMPTY
    assert "leer" in detail


VERIFIED = {
    "method": "blind_solve_mc",
    "checked_at": "2026-08-17",
    "protocol": {"chosen_index": 0},
}


def test_exercises_status_ok(tmp_path):
    path = tmp_path / "x.exercises.json"
    path.write_text(
        json.dumps({"exercises": [
            {"type": "multiple_choice", "verification": VERIFIED},
            {"type": "flashcard", "verification": dict(VERIFIED, method="blind_check_flashcard")},
        ]}),
        encoding="utf-8",
    )
    status, detail = due_topics_mod.exercises_status(path)
    assert status == due_topics_mod.EXERCISES_STATUS_OK
    assert "2 von 2" in detail


def test_exercises_status_ok_against_realistic_exporter_shape(tmp_path):
    """Gegen die reale Form von exercise-forges export.py geprüft, nicht nur gegen
    eine Ableitung: Metadaten neben 'exercises' dürfen vorkommen und stören nicht.
    Der Inhalt der Aufgaben (Stamm, Optionen, Musterlösung) bleibt ungeprüft — nur
    das `verification`-Objekt wird angesehen, und zwar nach derselben Ableitungs-
    regel wie beim Erzeuger, weil es dort kein `status`-Feld mehr gibt."""
    path = tmp_path / "x.exercises.json"
    path.write_text(
        json.dumps({
            "topic": "css-grid",
            "generated": "2026-08-17",
            "exercises": [
                {"type": "multiple_choice", "prompt": "...", "options": ["a", "b"],
                 "answer": "a", "verification": VERIFIED},
                {"type": "coding", "prompt": "...", "tests": "...",
                 "verification": dict(VERIFIED, method="blind_solve_coding")},
            ],
        }),
        encoding="utf-8",
    )
    status, detail = due_topics_mod.exercises_status(path)
    assert status == due_topics_mod.EXERCISES_STATUS_OK
    assert "2 von 2" in detail


def test_cli_due_reports_missing_phrase_for_empty_exercises_list(tmp_path, capsys):
    """Review-Fund 3: eine existierende, aber leere Aufgaben-Datei darf nicht als
    'Aufgaben gefunden' durchgehen — dieselbe mandatierte Phrase wie bei Datei-fehlt."""
    repo = tmp_path / "repo"
    write_learner(
        repo / ".skills" / "learning-coach" / "learner.md",
        "## css-grid: CSS – Grid-Layout\n\n- Beherrschungsgrad: 2\n- Nächste Fälligkeit: 2020-01-01\n",
    )
    ex_dir = repo / ".skills" / "verified-research" / "research"
    ex_dir.mkdir(parents=True)
    (ex_dir / "css-grid.exercises.json").write_text('{"exercises": []}', encoding="utf-8")

    rc = due_topics_mod.main(["--repo", str(repo), "due", "--today", "2026-08-17"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Keine verifizierten Aufgaben gefunden" in out
    assert "leer" in out


# --- next_grade / next_interval --------------------------------------------------

def test_next_grade_success_increments_capped_at_4():
    assert due_topics_mod.next_grade(3, "success") == 4
    assert due_topics_mod.next_grade(4, "success") == 4


def test_next_grade_failure_decrements_floored_at_0():
    assert due_topics_mod.next_grade(1, "failure") == 0
    assert due_topics_mod.next_grade(0, "failure") == 0


def test_next_grade_rejects_unknown_result():
    with pytest.raises(due_topics_mod.DueTopicsError, match="result"):
        due_topics_mod.next_grade(1, "vielleicht")


def test_next_interval_grows_with_success():
    new_grade, new_due = due_topics_mod.next_interval(2, "success", date(2026, 8, 17))
    assert new_grade == 3
    assert new_due == date(2026, 8, 17) + due_topics_mod.timedelta(days=7)


def test_next_interval_shrinks_with_failure():
    new_grade, new_due = due_topics_mod.next_interval(3, "failure", date(2026, 8, 17))
    assert new_grade == 2
    assert new_due == date(2026, 8, 17) + due_topics_mod.timedelta(days=3)


def test_next_interval_rejects_out_of_range_grade():
    with pytest.raises(due_topics_mod.DueTopicsError, match="grade"):
        due_topics_mod.next_interval(9, "success", date(2026, 8, 17))


# --- CLI end-to-end ---------------------------------------------------------------

def test_cli_due_reports_due_topic(tmp_path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    write_learner(
        repo / ".skills" / "learning-coach" / "learner.md",
        "## alt: Altes Thema\n\n- Beherrschungsgrad: 2\n- Nächste Fälligkeit: 2020-01-01\n",
    )
    monkeypatch.setenv("HOME", str(tmp_path / "unused-home"))
    rc = due_topics_mod.main(["--repo", str(repo), "due", "--today", "2026-08-17"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alt" in out
    assert "1 von 1 Themen fällig" in out
    assert "Abruf-Quiz-Budget" in out
    assert "Keine verifizierten Aufgaben gefunden" in out


def test_cli_due_reports_nothing_due(tmp_path, capsys):
    repo = tmp_path / "repo"
    write_learner(
        repo / ".skills" / "learning-coach" / "learner.md",
        "## x: X\n\n- Beherrschungsgrad: 4\n- Nächste Fälligkeit: 2099-01-01\n",
    )
    rc = due_topics_mod.main(["--repo", str(repo), "due", "--today", "2026-08-17"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "0 von 1 Themen fällig" in out
    assert "Nicht fällig" in out


def test_cli_due_bootstraps_when_missing(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = repo / "fake-home"
    monkeyless_args = ["--repo", str(repo), "due", "--today", "2026-08-17", "--assets", str(ASSETS_PATH)]
    # ensure_learner nutzt Path.home() intern, wenn kein home übergeben wird — hier
    # reicht das Bootstrap-Verhalten über den echten Home-Fallback nicht zu prüfen;
    # stattdessen projektlokal erzwingen, indem das Verzeichnis vorab existiert.
    (repo / ".skills" / "learning-coach").mkdir(parents=True)
    rc = due_topics_mod.main(monkeyless_args)
    assert rc == 0
    assert (repo / ".skills" / "learning-coach" / "learner.md").is_file()
    assert "Keine Themen erfasst." in capsys.readouterr().out


def test_cli_interval_success(capsys):
    rc = due_topics_mod.main(["interval", "--grade", "2", "--result", "success", "--today", "2026-08-17"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Grad: 2 -> 3" in out
    assert "2026-08-24" in out  # +7 Tage


def test_cli_interval_failure(capsys):
    rc = due_topics_mod.main(["interval", "--grade", "1", "--result", "failure", "--today", "2026-08-17"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Grad: 1 -> 0" in out
    assert "heute" in out  # Intervall 0 Tage bei Grad 0


def test_cli_interval_rejects_bad_result():
    with pytest.raises(SystemExit):
        due_topics_mod.main(["interval", "--grade", "1", "--result", "meh"])


# --- Schnittstelle: Pfad-Auflösung gegen den echten Erzeuger -------------------
#
# Beide Skills müssen für dasselbe Repo denselben Pfad berechnen. Die Divergenz,
# die diese Tests festnageln: learning-coach hing den Projekt-Override an der
# Basis `.skills/verified-research/`, exercise-forge am Unterverzeichnis
# `research/`. Existierte die Basis ohne `research/`, schrieb der Erzeuger nach
# `~` und der Konsument suchte im Projekt — dauerhaft "keine Aufgaben gefunden".

ef_export = load_script("skills/exercise-forge/scripts/export.py")
ef_verify = load_script("skills/exercise-forge/scripts/verify_blind.py")


def test_exercises_path_prefers_project_when_only_base_dir_exists(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".skills" / "verified-research").mkdir(parents=True)
    home = tmp_path / "home"
    path = due_topics_mod.exercises_path_for(repo, "closures", home=home)
    assert path == repo / ".skills" / "verified-research" / "research" / "closures.exercises.json"


@pytest.mark.parametrize(
    "existing",
    [
        None,                                    # weder Basis noch research/
        ".skills/verified-research",             # nur die Basis — der divergente Fall
        ".skills/verified-research/research",    # beides
    ],
)
def test_exercises_path_matches_exercise_forge(tmp_path, monkeypatch, existing):
    """Die Verdrahtung, nicht nur die zwei Seiten einzeln (Pitfall 'Die
    Verdrahtung ist ungetestet'): Konsument und Erzeuger müssen in jedem der drei
    Verzeichniszustände denselben Pfad liefern."""
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    if existing:
        (repo / existing).mkdir(parents=True)
    monkeypatch.setattr(ef_export.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(ef_verify.Path, "home", staticmethod(lambda: home))

    consumer = due_topics_mod.exercises_path_for(repo, "closures", home=home)
    assert consumer == ef_export.resolve_exercises_path("closures", repo=repo)
    assert consumer == ef_verify.resolve_exercises_path("closures", repo=repo)


# --- Prüfnachweis: has_verification_evidence ----------------------------------

def _exercise(**verification):
    return {"id": "x", "type": "multiple_choice", "verification": verification}


def test_evidence_requires_a_real_blind_gate_method():
    assert not due_topics_mod.has_verification_evidence(
        _exercise(method="not_run", checked_at="2026-08-01", protocol={})
    )
    assert not due_topics_mod.has_verification_evidence(
        _exercise(method="handgeprüft", checked_at="2026-08-01", protocol={})
    )


def test_evidence_requires_checked_at_and_protocol_object():
    assert not due_topics_mod.has_verification_evidence(
        _exercise(method="blind_solve_mc", protocol={})
    )
    assert not due_topics_mod.has_verification_evidence(
        _exercise(method="blind_solve_mc", checked_at="2026-08-01", protocol=None)
    )


def test_evidence_accepts_a_complete_verification_block():
    assert due_topics_mod.has_verification_evidence(
        _exercise(method="blind_solve_mc", checked_at="2026-08-01", protocol={"chosen_index": 1})
    )


def test_evidence_rejects_non_dict_entries():
    assert not due_topics_mod.has_verification_evidence("keine Aufgabe")
    assert not due_topics_mod.has_verification_evidence({"id": "x"})


# --- exercises_status: Prüfnachweis entscheidet über 'ok' ---------------------

def write_exercises(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_exercises_status_unverified_when_no_exercise_has_evidence(tmp_path):
    path = tmp_path / "t.exercises.json"
    write_exercises(path, {"exercises": [_exercise(method="not_run", detail="noch nicht geprüft")]})
    status, detail = due_topics_mod.exercises_status(path)
    assert status == due_topics_mod.EXERCISES_STATUS_UNVERIFIED
    assert "Prüfnachweis" in detail


def test_exercises_status_ok_counts_only_verified_exercises(tmp_path):
    path = tmp_path / "t.exercises.json"
    write_exercises(path, {"exercises": [
        _exercise(method="not_run"),
        _exercise(method="blind_solve_mc", checked_at="2026-08-01", protocol={"chosen_index": 0}),
    ]})
    status, detail = due_topics_mod.exercises_status(path)
    assert status == due_topics_mod.EXERCISES_STATUS_OK
    assert "1 von 2" in detail


def test_cli_due_reports_missing_phrase_for_unverified_exercises(tmp_path, capsys):
    """Der Regressionsschutz für die Schnittstelle: eine Datei voller ungeprüfter
    Aufgaben darf nie als verifizierter Bestand durchgehen."""
    repo = tmp_path / "repo"
    write_learner(
        repo / ".skills" / "learning-coach" / "learner.md",
        "# Lernstand\n\n## t: Thema\n\n- Beherrschungsgrad: 1\n- Nächste Fälligkeit: 2026-01-01\n",
    )
    write_exercises(
        repo / ".skills" / "verified-research" / "research" / "t.exercises.json",
        {"exercises": [_exercise(method="not_run")]},
    )
    rc = due_topics_mod.main(["--repo", str(repo), "due", "--today", "2026-06-01"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Keine verifizierten Aufgaben gefunden" in out


# --- Parser: nichts geht stillschweigend verloren ------------------------------

LOOSE_LIST = """\
# Lernstand

## t: Thema

- Gebiet: tech
- Beherrschungsgrad: 2
- Typische Fehler:
- Verwechselt Closure mit Callback
- Offene Fragen:
"""


def test_unindented_list_item_is_kept_with_warning():
    topics, _ = due_topics_mod.parse_learner(LOOSE_LIST)
    assert topics[0].typical_errors == ["Verwechselt Closure mit Callback"]
    assert any("ohne Einrückung" in w for w in topics[0].warnings)


def test_inline_list_value_is_kept_with_warning():
    text = "# Lernstand\n\n## t: Thema\n\n- Typische Fehler: Verwechselt Closure mit Callback\n"
    topics, _ = due_topics_mod.parse_learner(text)
    assert topics[0].typical_errors == ["Verwechselt Closure mit Callback"]
    assert any("inline" in w for w in topics[0].warnings)


def test_regular_field_after_a_list_label_is_not_swallowed():
    text = "# Lernstand\n\n## t: Thema\n\n- Typische Fehler:\n- Gebiet: tech\n- Beherrschungsgrad: 3\n"
    topics, _ = due_topics_mod.parse_learner(text)
    assert topics[0].typical_errors == []
    assert topics[0].gebiet == "tech"
    assert topics[0].grade == 3


# --- CLI: --today wird validiert, bevor etwas angelegt wird --------------------

def test_cli_due_rejects_bad_today_without_bootstrapping(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    home_learner = repo / ".skills" / "learning-coach" / "learner.md"
    rc = due_topics_mod.main(["--repo", str(repo), "due", "--today", "gestern"])
    assert rc == 2
    assert "--today" in capsys.readouterr().err
    assert not home_learner.exists()


def test_cli_interval_rejects_bad_today(capsys):
    rc = due_topics_mod.main(["interval", "--grade", "2", "--result", "success", "--today", "morgen"])
    assert rc == 2
    assert "--today" in capsys.readouterr().err
