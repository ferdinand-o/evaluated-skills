import json

import pytest

from conftest import load_script, REPO_ROOT

lint = load_script("skills/sql-schema-architect/scripts/lint_schema.py")

SKILL_DIR = REPO_ROOT / "skills" / "sql-schema-architect"

HEADER = "<!-- skill: sql-schema-architect | schema: 1 | generated: von Hand -->"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def full_steckbrief(table, access_pattern="Lookup per id, ~10 req/s."):
    return (
        f"{HEADER}\n# Tabelle: {table}\n\n"
        f"## Zweck\nSpeichert {table}.\n\n"
        f"## Owner\nPlatform-Team\n\n"
        f"## Erwartetes Wachstum\nlangsam\n\n"
        f"## Hauptzugriffsmuster\n{access_pattern}\n"
    )


CLEAN_MODEL = '''
class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    email = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
'''


def test_load_conventions_reads_default_preset():
    conventions = lint.load_conventions(REPO_ROOT, skill_dir=SKILL_DIR)
    assert conventions["required_columns"] == ["created_at", "updated_at"]


def test_load_conventions_applies_project_override(tmp_path):
    write(tmp_path / ".skills" / "sql-schema-architect" / "conventions.json",
          json.dumps({"required_columns": ["created_at"]}))
    conventions = lint.load_conventions(tmp_path, skill_dir=SKILL_DIR)
    assert conventions["required_columns"] == ["created_at"]
    # Andere Default-Felder bleiben erhalten, das Override ersetzt nur Top-Level-Keys.
    assert "types" in conventions


def test_load_conventions_raises_on_invalid_override_json(tmp_path):
    write(tmp_path / ".skills" / "sql-schema-architect" / "conventions.json", "{not json")
    with pytest.raises(lint.LintError, match="JSON"):
        lint.load_conventions(tmp_path, skill_dir=SKILL_DIR)


def test_load_conventions_raises_when_default_missing(tmp_path):
    with pytest.raises(lint.LintError, match="Preset fehlt"):
        lint.load_conventions(tmp_path, skill_dir=tmp_path / "nope")


# --- Naming -----------------------------------------------------------------------------

def test_check_naming_flags_camel_case_column():
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    userEmail = Column(Text)
''')
    findings = lint.check_naming(result.tables)
    assert any("userEmail" in f["message"] for f in findings)


def test_check_naming_clean_model_has_no_findings():
    erd = lint._load_gen_erd()
    result = erd.scan_source(CLEAN_MODEL)
    assert lint.check_naming(result.tables) == []


def test_check_naming_skips_unresolvable_tables():
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class Widget(Base):
    __tablename__ = f"{PREFIX}_widgets"
    badName = Column(Text)
''')
    assert lint.check_naming(result.tables) == []


# --- Typen -----------------------------------------------------------------------------

def test_check_types_flags_varchar():
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class User(Base):
    __tablename__ = "users"
    name = Column(String(50))
''')
    findings = lint.check_types(result.tables, {"types": {"reject_varchar": True}})
    assert any("name" in f["message"] and "String(50)" in f["message"] for f in findings)


def test_check_types_flags_naive_datetime():
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class User(Base):
    __tablename__ = "users"
    created_at = Column(DateTime)
''')
    findings = lint.check_types(result.tables, {"types": {"reject_datetime_without_timezone": True}})
    assert any("created_at" in f["message"] for f in findings)


def test_check_types_accepts_timezone_aware_datetime():
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class User(Base):
    __tablename__ = "users"
    created_at = Column(DateTime(timezone=True))
''')
    findings = lint.check_types(result.tables, {"types": {"reject_datetime_without_timezone": True}})
    assert findings == []


def test_check_types_respects_disabled_rules():
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class User(Base):
    __tablename__ = "users"
    name = Column(String(50))
''')
    findings = lint.check_types(result.tables, {"types": {"reject_varchar": False}})
    assert findings == []


# --- Review-Fund 4: SQLAlchemy-2.0-Stil (Mapped[T]) darf nicht stillschweigend ungeprueft bleiben

def test_check_types_reports_unresolved_type_instead_of_silently_skipping():
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
''')
    findings = lint.check_types(result.tables, {"types": {"reject_varchar": True, "reject_datetime_without_timezone": True}})
    assert len(findings) == 2
    assert all(f["rule"] == "type_coverage" for f in findings)
    assert any("id" in f["message"] and "int" in f["message"] for f in findings)


def test_check_types_unresolved_column_does_not_also_fire_varchar_or_datetime_rules():
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class User(Base):
    __tablename__ = "users"
    created_at: Mapped[object] = mapped_column()
''')
    findings = lint.check_types(result.tables, {"types": {"reject_varchar": True, "reject_datetime_without_timezone": True}})
    assert len(findings) == 1
    assert findings[0]["rule"] == "type_coverage"


# --- Pflichtspalten ----------------------------------------------------------------------

def test_check_required_columns_flags_missing():
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
''')
    findings = lint.check_required_columns(result.tables, {"required_columns": ["created_at", "updated_at"]})
    messages = " ".join(f["message"] for f in findings)
    assert "created_at" in messages and "updated_at" in messages


def test_check_required_columns_passes_when_present():
    erd = lint._load_gen_erd()
    result = erd.scan_source(CLEAN_MODEL)
    findings = lint.check_required_columns(result.tables, {"required_columns": ["created_at", "updated_at"]})
    assert findings == []


# --- FK-Verhalten ------------------------------------------------------------------------

def test_check_foreign_keys_flags_missing_ondelete():
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class Order(Base):
    __tablename__ = "orders"
    user_id = Column(BigInteger, ForeignKey("users.id"))
''')
    findings = lint.check_foreign_keys(result.tables, {"foreign_keys": {"ondelete_required": True}})
    assert len(findings) == 1
    assert "ondelete" in findings[0]["message"]


def test_check_foreign_keys_passes_with_explicit_ondelete():
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class Order(Base):
    __tablename__ = "orders"
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
''')
    findings = lint.check_foreign_keys(result.tables, {"foreign_keys": {"ondelete_required": True}})
    assert findings == []


# --- Steckbrief-Vertrag -------------------------------------------------------------------

def test_check_steckbriefe_flags_missing_file(tmp_path):
    erd = lint._load_gen_erd()
    result = erd.scan_source(CLEAN_MODEL)
    findings = lint.check_steckbriefe(result.tables, lint.load_conventions(REPO_ROOT, skill_dir=SKILL_DIR), tmp_path)
    assert any(f["rule"] == "steckbrief" and "kein Steckbrief" in f["message"] for f in findings)


def test_check_steckbriefe_flags_missing_header(tmp_path):
    write(tmp_path / "docs" / "schema" / "users.md", "# Tabelle: users\n\n## Zweck\nx\n\n## Owner\nx\n\n## Erwartetes Wachstum\nx\n\n## Hauptzugriffsmuster\nx\n")
    erd = lint._load_gen_erd()
    result = erd.scan_source(CLEAN_MODEL)
    findings = lint.check_steckbriefe(result.tables, lint.load_conventions(REPO_ROOT, skill_dir=SKILL_DIR), tmp_path)
    assert any("Kopfzeile" in f["message"] for f in findings)


def test_check_steckbriefe_flags_empty_section(tmp_path):
    text = f"{HEADER}\n# Tabelle: users\n\n## Zweck\n\n## Owner\nx\n\n## Erwartetes Wachstum\nx\n\n## Hauptzugriffsmuster\nx\n"
    write(tmp_path / "docs" / "schema" / "users.md", text)
    erd = lint._load_gen_erd()
    result = erd.scan_source(CLEAN_MODEL)
    findings = lint.check_steckbriefe(result.tables, lint.load_conventions(REPO_ROOT, skill_dir=SKILL_DIR), tmp_path)
    assert any("Zweck" in f["message"] and "leer" in f["message"] for f in findings)


def test_check_steckbriefe_flags_missing_section():
    erd = lint._load_gen_erd()
    result = erd.scan_source(CLEAN_MODEL)
    conventions = lint.load_conventions(REPO_ROOT, skill_dir=SKILL_DIR)
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        write(repo / "docs" / "schema" / "users.md", f"{HEADER}\n# Tabelle: users\n\n## Zweck\nx\n\n## Owner\nx\n")
        findings = lint.check_steckbriefe(result.tables, conventions, repo)
    messages = " ".join(f["message"] for f in findings)
    assert "Erwartetes Wachstum" in messages
    assert "Hauptzugriffsmuster" in messages


def test_check_steckbriefe_complete_has_no_findings(tmp_path):
    write(tmp_path / "docs" / "schema" / "users.md", full_steckbrief("users"))
    erd = lint._load_gen_erd()
    result = erd.scan_source(CLEAN_MODEL)
    findings = lint.check_steckbriefe(result.tables, lint.load_conventions(REPO_ROOT, skill_dir=SKILL_DIR), tmp_path)
    assert findings == []


def test_check_steckbriefe_flags_index_without_access_pattern(tmp_path):
    text = f"{HEADER}\n# Tabelle: users\n\n## Zweck\nx\n\n## Owner\nx\n\n## Erwartetes Wachstum\nx\n\n## Hauptzugriffsmuster\n\n"
    write(tmp_path / "docs" / "schema" / "users.md", text)
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class User(Base):
    __tablename__ = "users"
    email = Column(Text, index=True)
''')
    findings = lint.check_steckbriefe(result.tables, lint.load_conventions(REPO_ROOT, skill_dir=SKILL_DIR), tmp_path)
    assert any(f["rule"] == "index_pattern" for f in findings)


def test_check_steckbriefe_index_with_documented_pattern_is_clean(tmp_path):
    write(tmp_path / "docs" / "schema" / "users.md", full_steckbrief("users", access_pattern="Lookup per email beim Login."))
    erd = lint._load_gen_erd()
    result = erd.scan_source('''
class User(Base):
    __tablename__ = "users"
    email = Column(Text, index=True)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
''')
    findings = lint.check_steckbriefe(result.tables, lint.load_conventions(REPO_ROOT, skill_dir=SKILL_DIR), tmp_path)
    assert not any(f["rule"] == "index_pattern" for f in findings)


# --- sqlfluff-Degradation (R4) --------------------------------------------------------

def test_sqlfluff_status_reports_missing_tool_visibly(monkeypatch):
    monkeypatch.setattr(lint.shutil, "which", lambda name: None)
    status = lint.sqlfluff_status(None)
    assert status["available"] is False
    assert "nicht installiert" in status["note"]
    assert "Kernprüfungen liefen trotzdem" in status["note"]
    assert status["findings"] == []


def test_sqlfluff_status_when_available_but_no_path(monkeypatch):
    monkeypatch.setattr(lint.shutil, "which", lambda name: "/usr/bin/sqlfluff")
    status = lint.sqlfluff_status(None)
    assert status["available"] is True
    assert status["findings"] == []


# --- run_lint / main --------------------------------------------------------------------

def test_run_lint_writes_findings_for_missing_steckbrief(tmp_path):
    write(tmp_path / "models.py", CLEAN_MODEL)
    report = lint.run_lint(tmp_path, tmp_path / "models.py", None, SKILL_DIR)
    assert report["_meta"]["skill"] == "sql-schema-architect"
    assert any(f["rule"] == "steckbrief" for f in report["findings"])


def test_main_writes_report_to_cache(tmp_path, monkeypatch, capsys):
    write(tmp_path / "models.py", '''
class User(Base):
    __tablename__ = "users"
    userEmail = Column(String(50))
''')
    monkeypatch.chdir(tmp_path)
    rc = lint.main(["models.py", "--skill-dir", str(SKILL_DIR)])
    assert rc == 1
    report = json.loads((tmp_path / ".skills" / "cache" / "lint-schema-report.json").read_text(encoding="utf-8"))
    assert len(report["findings"]) > 1
    out = capsys.readouterr().out
    assert "sqlfluff" in out.lower()


def test_main_exits_zero_when_clean(tmp_path, monkeypatch):
    write(tmp_path / "models.py", CLEAN_MODEL)
    write(tmp_path / "docs" / "schema" / "users.md", full_steckbrief("users"))
    monkeypatch.chdir(tmp_path)
    rc = lint.main(["models.py", "--skill-dir", str(SKILL_DIR)])
    assert rc == 0


def test_main_rejects_nonexistent_models_path(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = lint.main(["nope.py", "--skill-dir", str(SKILL_DIR)])
    assert rc == 1
    assert "existiert nicht" in capsys.readouterr().err


def test_main_json_mode_emits_valid_json(tmp_path, monkeypatch, capsys):
    write(tmp_path / "models.py", CLEAN_MODEL)
    write(tmp_path / "docs" / "schema" / "users.md", full_steckbrief("users"))
    monkeypatch.chdir(tmp_path)
    rc = lint.main(["models.py", "--skill-dir", str(SKILL_DIR), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"] == []


# --- Preset-Auflösung ------------------------------------------------------------
#
# Testlauf-Fund (2026-08-21): Der in SKILL.md dokumentierte Aufruf
# `python <skill-dir>/scripts/lint_schema.py <models>` bricht mit exit 1 ab, weil das
# Default-Preset über einen repo-relativen Pfad gegen --repo gesucht wurde. Der Pfad
# existiert nur im evaluated-skills-Repo selbst; in jedem anderen Projekt — und in jeder
# installierten Skill — zeigt er ins Leere. Das Skript muss sein eigenes mitgeliefertes
# Preset finden, ohne dass der Aufrufer ein Flag kennt.


def test_load_conventions_finds_shipped_preset_without_skill_dir_flag(tmp_path):
    """Fremdes Projekt ohne skills/-Baum: das Preset der Skill muss trotzdem laden."""
    conventions = lint.load_conventions(tmp_path)
    assert conventions, "Preset wurde nicht geladen"
    assert "tables" in conventions or "naming" in conventions or conventions


def test_load_conventions_still_honours_explicit_skill_dir(tmp_path):
    """Das --skill-dir-Flag bleibt wirksam und schlägt den Default."""
    preset = tmp_path / "skill" / "assets" / "conventions.json"
    preset.parent.mkdir(parents=True)
    preset.write_text(json.dumps({"marker": "explizit"}), encoding="utf-8")
    assert lint.load_conventions(tmp_path, tmp_path / "skill")["marker"] == "explizit"
