import pytest

from conftest import load_script

export_stubs = load_script("skills/feature-spec/scripts/export_stubs.py")


VALID_SPEC = """\
<!-- skill: feature-spec | schema: 1 | generated: x -->
# Feature: Notifications

## Problem
Aufgaben mit Fälligkeitsdatum werden verpasst.

## Non-Goals
- Kein plattformübergreifendes Settings-Sync.

## Annahmen
- Annahme: läuft über EmailService.

## Ansatz
Ein Job prüft stündlich.

## Akzeptanzkriterien

### Erinnerung wird verschickt
- Given eine Aufgabe hat ein Fälligkeitsdatum in 24 Stunden
- And der Nutzer hat Erinnerungen nicht deaktiviert
- When der geplante Erinnerungs-Job läuft
- Then verschickt EmailService eine Erinnerungsmail
- And der Versand wird vermerkt

### Keine doppelte Erinnerung
- Given eine Erinnerung wurde bereits verschickt
- When der Job erneut läuft
- Then verschickt EmailService keine zweite Mail

## Offene Fragen
- Stornierung bei Verschiebung? — Entscheider: du.
"""


def lines_of(text: str) -> list[str]:
    return text.splitlines()


# --- slugify --------------------------------------------------------------


def test_slugify_basic():
    assert export_stubs.slugify("Erinnerung wird verschickt") == "erinnerung-wird-verschickt"


def test_slugify_umlauts():
    assert export_stubs.slugify("Fälligkeits-Erinnerung") == "faelligkeits-erinnerung"


def test_slugify_empty_falls_back():
    assert export_stubs.slugify("!!!") == "kriterium"


def test_slugify_truncates_long_titles():
    long_title = "x" * 100
    assert len(export_stubs.slugify(long_title)) <= 60


# --- derive_feature ---------------------------------------------------------


def test_derive_feature_from_feature_heading(tmp_path):
    lines = lines_of(VALID_SPEC)
    spec_path = tmp_path / "irrelevant.md"
    assert export_stubs.derive_feature(lines, spec_path) == "notifications"


def test_derive_feature_falls_back_to_first_h1(tmp_path):
    lines = ["# Nur ein Titel", "", "## Non-Goals", "- x"]
    spec_path = tmp_path / "whatever.md"
    assert export_stubs.derive_feature(lines, spec_path) == "nur-ein-titel"


def test_derive_feature_falls_back_to_filename(tmp_path):
    lines = ["kein Heading hier"]
    spec_path = tmp_path / "mein-feature.md"
    assert export_stubs.derive_feature(lines, spec_path) == "mein-feature"


# --- parse_spec: positive path ---------------------------------------------


def test_parse_spec_returns_two_criteria_with_bundled_gwt():
    criteria = export_stubs.parse_spec(lines_of(VALID_SPEC))
    assert [c.title for c in criteria] == [
        "Erinnerung wird verschickt",
        "Keine doppelte Erinnerung",
    ]
    first = criteria[0]
    assert first.slug == "erinnerung-wird-verschickt"
    assert first.given == (
        "eine Aufgabe hat ein Fälligkeitsdatum in 24 Stunden",
        "der Nutzer hat Erinnerungen nicht deaktiviert",
    )
    assert first.when == ("der geplante Erinnerungs-Job läuft",)
    assert first.then == (
        "verschickt EmailService eine Erinnerungsmail",
        "der Versand wird vermerkt",
    )


def test_parse_spec_and_continues_last_category():
    second = export_stubs.parse_spec(lines_of(VALID_SPEC))[1]
    assert second.given == ("eine Erinnerung wurde bereits verschickt",)
    assert second.then == ("verschickt EmailService keine zweite Mail",)


# --- parse_spec: negative paths, one problem per test ----------------------


def test_parse_spec_missing_non_goals_raises():
    spec = VALID_SPEC.replace(
        "## Non-Goals\n- Kein plattformübergreifendes Settings-Sync.\n\n", ""
    )
    with pytest.raises(export_stubs.SpecParseError) as exc_info:
        export_stubs.parse_spec(lines_of(spec))
    assert any("Non-Goals fehlt" in p for p in exc_info.value.problems)


def test_parse_spec_empty_non_goals_raises():
    spec = VALID_SPEC.replace("- Kein plattformübergreifendes Settings-Sync.\n", "")
    with pytest.raises(export_stubs.SpecParseError) as exc_info:
        export_stubs.parse_spec(lines_of(spec))
    assert any("Non-Goals ist leer" in p for p in exc_info.value.problems)


def test_parse_spec_missing_acceptance_section_raises():
    lines = lines_of(VALID_SPEC)
    ak_start, ak_end = export_stubs._find_section(lines, "Akzeptanzkriterien")
    spec_lines = lines[:ak_start] + lines[ak_end:]
    with pytest.raises(export_stubs.SpecParseError) as exc_info:
        export_stubs.parse_spec(spec_lines)
    assert any("Akzeptanzkriterien fehlt" in p for p in exc_info.value.problems)


def test_parse_spec_section_without_criteria_raises():
    spec = """\
## Non-Goals
- x

## Akzeptanzkriterien

Hier steht kein einziges Kriterium.
"""
    with pytest.raises(export_stubs.SpecParseError) as exc_info:
        export_stubs.parse_spec(lines_of(spec))
    assert any("enthält keine Kriterien" in p for p in exc_info.value.problems)


def test_parse_spec_prose_criterion_reports_correct_line_number():
    spec = """\
## Non-Goals
- x

## Akzeptanzkriterien

### Valides Kriterium
- Given a
- When b
- Then c

### Prosa-Kriterium
Wenn der Nutzer etwas tut, passiert etwas anderes.
"""
    lines = lines_of(spec)
    heading_line = next(
        i + 1 for i, line in enumerate(lines) if line.strip() == "### Prosa-Kriterium"
    )
    with pytest.raises(export_stubs.SpecParseError) as exc_info:
        export_stubs.parse_spec(lines)
    assert any(f"Zeile {heading_line}:" in p for p in exc_info.value.problems)
    assert any("Prosa-Kriterium" in p for p in exc_info.value.problems)


def test_parse_spec_bullet_without_gwt_keyword_reports_its_own_line():
    spec = """\
## Non-Goals
- x

## Akzeptanzkriterien

### K1
- Given a
- irgendwas ohne Schlüsselwort
- When b
- Then c
"""
    lines = lines_of(spec)
    bad_line = next(
        i + 1 for i, line in enumerate(lines) if "irgendwas ohne" in line
    )
    with pytest.raises(export_stubs.SpecParseError) as exc_info:
        export_stubs.parse_spec(lines)
    assert any(f"Zeile {bad_line}:" in p for p in exc_info.value.problems)


def test_parse_spec_and_without_preceding_keyword_raises():
    spec = """\
## Non-Goals
- x

## Akzeptanzkriterien

### K1
- And das kommt zu früh
- When b
- Then c
"""
    with pytest.raises(export_stubs.SpecParseError) as exc_info:
        export_stubs.parse_spec(lines_of(spec))
    assert any("'And' ohne vorausgehendes" in p for p in exc_info.value.problems)


def test_parse_spec_missing_then_category_raises():
    spec = """\
## Non-Goals
- x

## Akzeptanzkriterien

### K1
- Given a
- When b
"""
    with pytest.raises(export_stubs.SpecParseError) as exc_info:
        export_stubs.parse_spec(lines_of(spec))
    assert any("fehlt then" in p for p in exc_info.value.problems)


def test_parse_spec_slug_collision_raises():
    spec = """\
## Non-Goals
- x

## Akzeptanzkriterien

### Erinnerung senden!
- Given a
- When b
- Then c

### Erinnerung senden?
- Given a
- When b
- Then c
"""
    with pytest.raises(export_stubs.SpecParseError) as exc_info:
        export_stubs.parse_spec(lines_of(spec))
    assert any("denselben Slug" in p for p in exc_info.value.problems)


def test_parse_spec_combined_failure_reports_both_problems():
    """Non-Goals fehlt UND ein Kriterium ist Prosa — beide Meldungen zusammen,
    Beweis dass gesammelt statt beim ersten Fehler abgebrochen wird."""
    spec = """\
## Akzeptanzkriterien

### Prosa
Nur Fließtext, keine Liste.
"""
    with pytest.raises(export_stubs.SpecParseError) as exc_info:
        export_stubs.parse_spec(lines_of(spec))
    problems = exc_info.value.problems
    assert any("Non-Goals fehlt" in p for p in problems)
    assert any("nicht als Given/When/Then formuliert" in p for p in problems)
    assert len(problems) == 2


# --- overwrite protection: pytest -------------------------------------------


def test_should_write_pytest_true_for_missing_file(tmp_path):
    target = tmp_path / "test_x_y.py"
    assert export_stubs.should_write_pytest(target) is True


def test_should_write_pytest_true_when_both_markers_present(tmp_path):
    target = tmp_path / "test_x_y.py"
    target.write_text(
        '# spec-stub: y\n"""alt"""\n@pytest.mark.skip("stub: noch nicht implementiert")\n'
        "def test_x_y():\n    ...\n",
        encoding="utf-8",
    )
    assert export_stubs.should_write_pytest(target) is True


def test_should_write_pytest_false_when_skip_marker_removed(tmp_path):
    """Jemand hat den Test implementiert und den skip-Marker entfernt."""
    target = tmp_path / "test_x_y.py"
    target.write_text(
        '# spec-stub: y\n"""alt"""\ndef test_x_y():\n    assert True\n',
        encoding="utf-8",
    )
    assert export_stubs.should_write_pytest(target) is False


def test_should_write_pytest_false_when_header_missing(tmp_path):
    """Fremde Datei am selben Pfad, nie von export_stubs.py erzeugt."""
    target = tmp_path / "test_x_y.py"
    target.write_text(
        '"""von Hand geschrieben"""\n@pytest.mark.skip("stub: noch nicht implementiert")\n'
        "def test_x_y():\n    ...\n",
        encoding="utf-8",
    )
    assert export_stubs.should_write_pytest(target) is False


def test_should_write_pytest_false_when_skip_marker_commented_out(tmp_path):
    """Der naheliegendste Weg, einen Stub zu aktivieren: die Skip-Zeile
    auskommentieren statt löschen. Header und Marker-Text stehen noch im
    Dateiinhalt — should_write_pytest darf trotzdem nicht True liefern,
    sonst überschreibt der nächste Export eine fertige Implementierung."""
    target = tmp_path / "test_x_y.py"
    target.write_text(
        '# spec-stub: y\n"""alt"""\n'
        '# @pytest.mark.skip("stub: noch nicht implementiert")\n'
        "def test_x_y():\n    assert echte_implementierung() == 42\n",
        encoding="utf-8",
    )
    assert export_stubs.should_write_pytest(target) is False


def test_should_write_pytest_false_when_marker_only_mentioned_in_docstring(tmp_path):
    """Der Marker-Text steht als Zitat in einem Docstring, nicht als aktive
    Decorator-Zeile — zählt nicht als aktiver Marker."""
    target = tmp_path / "test_x_y.py"
    target.write_text(
        '# spec-stub: y\n'
        '"""\n'
        '@pytest.mark.skip("stub: noch nicht implementiert")\n'
        "Das oben ist nur als Beispiel im Docstring zitiert, kein echter Marker.\n"
        '"""\n'
        "def test_x_y():\n    assert echte_implementierung() == 42\n",
        encoding="utf-8",
    )
    assert export_stubs.should_write_pytest(target) is False


def test_should_write_pytest_true_when_active_marker_line_matches_exactly(tmp_path):
    """Gegenprobe: eine echte, unveränderte Decorator-Zeile bleibt aktiv,
    auch wenn der Marker-Text zusätzlich (harmlos) im Docstring vorkommt."""
    target = tmp_path / "test_x_y.py"
    target.write_text(
        '# spec-stub: y\n'
        '"""Erwähnt @pytest.mark.skip("stub: noch nicht implementiert") im Text."""\n'
        '@pytest.mark.skip("stub: noch nicht implementiert")\n'
        "def test_x_y():\n    ...\n",
        encoding="utf-8",
    )
    assert export_stubs.should_write_pytest(target) is True


# --- overwrite protection: vitest -------------------------------------------


def test_should_write_vitest_true_for_missing_file(tmp_path):
    assert export_stubs.should_write_vitest(tmp_path / "x.y.test.ts") is True


def test_should_write_vitest_true_when_both_markers_present(tmp_path):
    target = tmp_path / "x.y.test.ts"
    target.write_text("// spec-stub: y\nit.todo('y');\n", encoding="utf-8")
    assert export_stubs.should_write_vitest(target) is True


def test_should_write_vitest_false_when_todo_removed(tmp_path):
    target = tmp_path / "x.y.test.ts"
    target.write_text("// spec-stub: y\nit('y', () => { expect(1).toBe(1); });\n", encoding="utf-8")
    assert export_stubs.should_write_vitest(target) is False


def test_should_write_vitest_false_when_header_missing(tmp_path):
    target = tmp_path / "x.y.test.ts"
    target.write_text("it.todo('y');\n", encoding="utf-8")
    assert export_stubs.should_write_vitest(target) is False


def test_should_write_vitest_false_when_todo_commented_out(tmp_path):
    """Analog zu Defekt 1 bei pytest: die it.todo-Zeile auskommentiert statt
    entfernt, während eine echte Implementierung daneben steht."""
    target = tmp_path / "x.y.test.ts"
    target.write_text(
        "// spec-stub: y\n// it.todo('y');\n"
        "it('y', () => { expect(echteImplementierung()).toBe(42); });\n",
        encoding="utf-8",
    )
    assert export_stubs.should_write_vitest(target) is False


# --- write_pytest_stubs / write_vitest_stubs --------------------------------


def test_write_pytest_stubs_creates_files_with_markers(tmp_path):
    criteria = export_stubs.parse_spec(lines_of(VALID_SPEC))
    out_dir = tmp_path / "tests"
    spec_path = tmp_path / "notifications.md"
    created, skipped = export_stubs.write_pytest_stubs(criteria, "notifications", spec_path, out_dir)
    assert len(created) == 2
    assert skipped == []
    text = (out_dir / "test_notifications_erinnerung_wird_verschickt.py").read_text(encoding="utf-8")
    assert text.startswith("# spec-stub: erinnerung-wird-verschickt")
    assert export_stubs.PYTEST_SKIP_MARKER in text
    assert "def test_notifications_erinnerung_wird_verschickt():" in text


def test_write_pytest_stubs_reexport_overwrites_when_markers_intact(tmp_path):
    criteria = export_stubs.parse_spec(lines_of(VALID_SPEC))
    out_dir = tmp_path / "tests"
    spec_path = tmp_path / "notifications.md"
    export_stubs.write_pytest_stubs(criteria, "notifications", spec_path, out_dir)
    target = out_dir / "test_notifications_erinnerung_wird_verschickt.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# manuell angehängt\n", encoding="utf-8")

    created, skipped = export_stubs.write_pytest_stubs(criteria, "notifications", spec_path, out_dir)
    assert target.as_posix() in created
    assert "# manuell angehängt" not in target.read_text(encoding="utf-8")


def test_write_pytest_stubs_reexport_skips_when_implemented(tmp_path):
    criteria = export_stubs.parse_spec(lines_of(VALID_SPEC))
    out_dir = tmp_path / "tests"
    spec_path = tmp_path / "notifications.md"
    export_stubs.write_pytest_stubs(criteria, "notifications", spec_path, out_dir)
    target = out_dir / "test_notifications_erinnerung_wird_verschickt.py"
    implemented = "# spec-stub: erinnerung-wird-verschickt\ndef test_x():\n    assert True\n"
    target.write_text(implemented, encoding="utf-8")

    created, skipped = export_stubs.write_pytest_stubs(criteria, "notifications", spec_path, out_dir)
    assert target.as_posix() not in created
    assert target.as_posix() in skipped
    assert target.read_text(encoding="utf-8") == implemented


def test_write_pytest_stubs_does_not_clobber_implementation_with_commented_marker(tmp_path):
    """Reproduziert den Defekt aus dem Review: Skip-Zeile auskommentiert statt
    gelöscht, Header und Marker-Text stehen textuell noch da. Vor dem Fix lieferte
    should_write_pytest True (Substring-Suche über den ganzen Dateitext) und der
    Re-Export überschrieb die fertige Implementierung mit einem leeren Stub."""
    criteria = export_stubs.parse_spec(lines_of(VALID_SPEC))
    out_dir = tmp_path / "tests"
    spec_path = tmp_path / "notifications.md"
    export_stubs.write_pytest_stubs(criteria, "notifications", spec_path, out_dir)

    target = out_dir / "test_notifications_erinnerung_wird_verschickt.py"
    echte_implementierung = (
        "# spec-stub: erinnerung-wird-verschickt\n"
        '# @pytest.mark.skip("stub: noch nicht implementiert")\n'
        "def test_notifications_erinnerung_wird_verschickt():\n"
        "    assert send_reminder(due_in_hours=24) is True\n"
    )
    target.write_text(echte_implementierung, encoding="utf-8")

    created, skipped = export_stubs.write_pytest_stubs(criteria, "notifications", spec_path, out_dir)
    assert target.as_posix() not in created
    assert target.as_posix() in skipped
    assert target.read_text(encoding="utf-8") == echte_implementierung


def test_write_vitest_stubs_creates_todo_files(tmp_path):
    criteria = export_stubs.parse_spec(lines_of(VALID_SPEC))
    out_dir = tmp_path / "tests-js"
    spec_path = tmp_path / "notifications.md"
    created, skipped = export_stubs.write_vitest_stubs(criteria, "notifications", spec_path, out_dir)
    assert len(created) == 2
    text = (out_dir / "notifications.erinnerung-wird-verschickt.test.ts").read_text(encoding="utf-8")
    assert text.startswith("// spec-stub: erinnerung-wird-verschickt")
    assert "it.todo(" in text


# --- main(): integration -----------------------------------------------------


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_main_success_exit_zero_and_prints_paths(tmp_path, capsys):
    spec_path = _write(tmp_path, "spec.md", VALID_SPEC)
    out_dir = tmp_path / "tests"
    rc = export_stubs.main([str(spec_path), "--out-dir", str(out_dir)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "erzeugt:" in out
    assert list(out_dir.glob("test_*.py"))


def test_main_refuses_and_writes_no_files_at_all(tmp_path, capsys):
    """Der wichtigste Testfall: ein valides plus ein Prosa-Kriterium -> Exit != 0,
    KEINE der beiden Stub-Dateien entsteht, auch nicht die des validen Kriteriums."""
    spec = """\
<!-- skill: feature-spec | schema: 1 | generated: x -->
# Feature: Mixed

## Non-Goals
- nichts

## Akzeptanzkriterien

### Valides Kriterium
- Given a
- When b
- Then c

### Prosa-Kriterium
Wenn etwas passiert, passiert etwas anderes.
"""
    spec_path = _write(tmp_path, "spec.md", spec)
    out_dir = tmp_path / "tests"
    rc = export_stubs.main([str(spec_path), "--out-dir", str(out_dir)])
    assert rc != 0
    assert not out_dir.exists()
    err = capsys.readouterr().err
    assert "Zeile" in err
    assert "Given" in err and "When" in err and "Then" in err
    assert "Keine Stub-Datei wurde geschrieben." in err


def test_main_missing_spec_file_returns_one(tmp_path, capsys):
    rc = export_stubs.main([str(tmp_path / "nicht-da.md")])
    assert rc == 1
    assert "nicht gefunden" in capsys.readouterr().err


def test_main_reexport_after_removing_skip_marker_leaves_file_untouched(tmp_path, capsys):
    spec_path = _write(tmp_path, "spec.md", VALID_SPEC)
    out_dir = tmp_path / "tests"
    export_stubs.main([str(spec_path), "--out-dir", str(out_dir)])
    capsys.readouterr()  # ersten Lauf aus dem Puffer entfernen

    target = out_dir / "test_notifications_erinnerung_wird_verschickt.py"
    implemented = "# spec-stub: erinnerung-wird-verschickt\ndef test_x():\n    assert True\n"
    target.write_text(implemented, encoding="utf-8")

    rc = export_stubs.main([str(spec_path), "--out-dir", str(out_dir)])
    assert rc == 0
    assert target.read_text(encoding="utf-8") == implemented

    out = capsys.readouterr().out
    assert f"übersprungen (bereits implementiert): {target.as_posix()}" in out


def test_main_with_vitest_flag_creates_both_stub_kinds(tmp_path):
    spec_path = _write(tmp_path, "spec.md", VALID_SPEC)
    out_dir = tmp_path / "tests"
    vitest_dir = tmp_path / "tests-js"
    rc = export_stubs.main([
        str(spec_path), "--out-dir", str(out_dir), "--vitest", "--vitest-out-dir", str(vitest_dir),
    ])
    assert rc == 0
    assert list(out_dir.glob("test_*.py"))
    assert list(vitest_dir.glob("*.test.ts"))
