import json

import pytest

from conftest import load_script

gate = load_script("skills/sql-schema-architect/scripts/migration_gate.py")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- Extraktion: upgrade()/downgrade(), op-Aufrufe -----------------------------------

def test_parse_revision_finds_upgrade_and_downgrade(tmp_path):
    rev = write(tmp_path / "r.py", """
def upgrade():
    op.create_table('widgets')

def downgrade():
    op.drop_table('widgets')
""")
    info = gate.parse_revision(rev)
    assert info.has_upgrade is True
    assert info.has_downgrade is True
    assert info.downgrade_empty is False
    assert [op.method for op in info.ops] == ["create_table"]


def test_parse_revision_missing_upgrade(tmp_path):
    rev = write(tmp_path / "r.py", """
def downgrade():
    pass
""")
    info = gate.parse_revision(rev)
    assert info.has_upgrade is False
    assert info.ops == []


def test_parse_revision_rejects_invalid_python(tmp_path):
    rev = write(tmp_path / "r.py", "def upgrade(:\n    pass\n")
    with pytest.raises(gate.GateError, match="gültiges Python"):
        gate.parse_revision(rev)


def test_op_calls_are_ordered_by_line(tmp_path):
    rev = write(tmp_path / "r.py", """
def upgrade():
    op.add_column('t', sa.Column('a', sa.Text(), nullable=True))
    op.create_index('ix_t_a', 't', ['a'])
""")
    info = gate.parse_revision(rev)
    assert [op.method for op in info.ops] == ["add_column", "create_index"]


def test_created_tables_tracked_within_revision(tmp_path):
    rev = write(tmp_path / "r.py", """
def upgrade():
    op.create_table('widgets')
    op.create_table("gadgets")
""")
    info = gate.parse_revision(rev)
    assert info.created_tables == {"widgets", "gadgets"}


# --- downgrade()-Leerfall-Erkennung ---------------------------------------------------

def test_downgrade_missing_function_counts_as_empty(tmp_path):
    rev = write(tmp_path / "r.py", "def upgrade():\n    pass\n")
    info = gate.parse_revision(rev)
    assert info.downgrade_empty is True
    assert info.one_way_reason is None


def test_downgrade_with_only_pass_counts_as_empty(tmp_path):
    rev = write(tmp_path / "r.py", "def upgrade():\n    pass\n\ndef downgrade():\n    pass\n")
    info = gate.parse_revision(rev)
    assert info.downgrade_empty is True
    assert info.one_way_reason is None


def test_downgrade_with_docstring_only_counts_as_empty(tmp_path):
    rev = write(tmp_path / "r.py", '''
def upgrade():
    pass

def downgrade():
    """Nichts zu tun."""
''')
    info = gate.parse_revision(rev)
    assert info.downgrade_empty is True


def test_downgrade_with_justified_not_implemented_is_not_empty(tmp_path):
    rev = write(tmp_path / "r.py", '''
def upgrade():
    pass

def downgrade():
    raise NotImplementedError("Datenverlust waere irreversibel, siehe ADR-12")
''')
    info = gate.parse_revision(rev)
    assert info.downgrade_empty is False
    assert info.one_way_reason == "Datenverlust waere irreversibel, siehe ADR-12"


def test_downgrade_with_bare_raise_not_implemented_no_reason_stays_empty(tmp_path):
    rev = write(tmp_path / "r.py", '''
def upgrade():
    pass

def downgrade():
    raise NotImplementedError
''')
    info = gate.parse_revision(rev)
    assert info.downgrade_empty is True
    assert info.one_way_reason is None


def test_downgrade_with_real_statements_is_not_empty(tmp_path):
    rev = write(tmp_path / "r.py", '''
def upgrade():
    op.add_column('t', sa.Column('a', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('t', 'a')
''')
    info = gate.parse_revision(rev)
    assert info.downgrade_empty is False
    assert info.one_way_reason is None


# --- Klassifikation je Operation -------------------------------------------------------

def op_of(source, index=0):
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "r.py"
        path.write_text(source, encoding="utf-8")
        info = gate.parse_revision(path)
        return info.ops[index], info.created_tables


def test_create_table_is_green():
    op, created = op_of("def upgrade():\n    op.create_table('widgets')\n")
    c = gate.classify_op(op, created)
    assert c.verdict == gate.GREEN


def test_add_column_nullable_true_is_green():
    op, created = op_of(
        "def upgrade():\n    op.add_column('t', sa.Column('a', sa.Text(), nullable=True))\n"
    )
    c = gate.classify_op(op, created)
    assert c.verdict == gate.GREEN


def test_add_column_not_null_without_default_on_existing_table_is_red():
    op, created = op_of(
        "def upgrade():\n    op.add_column('t', sa.Column('a', sa.Text(), nullable=False))\n"
    )
    c = gate.classify_op(op, created)
    assert c.verdict == gate.RED


def test_add_column_not_null_with_default_on_existing_table_is_yellow():
    op, created = op_of(
        "def upgrade():\n"
        "    op.add_column('t', sa.Column('a', sa.Text(), nullable=False, server_default='x'))\n"
    )
    c = gate.classify_op(op, created)
    assert c.verdict == gate.YELLOW
    assert c.auflagen


def test_add_column_not_null_without_default_on_new_table_is_green():
    src = (
        "def upgrade():\n"
        "    op.create_table('t')\n"
        "    op.add_column('t', sa.Column('a', sa.Text(), nullable=False))\n"
    )
    op, created = op_of(src, index=1)
    c = gate.classify_op(op, created)
    assert c.verdict == gate.GREEN


def test_create_index_concurrently_on_existing_table_is_green():
    op, created = op_of(
        "def upgrade():\n"
        "    op.create_index('ix_t_a', 't', ['a'], postgresql_concurrently=True)\n"
    )
    c = gate.classify_op(op, created)
    assert c.verdict == gate.GREEN


def test_create_index_without_concurrently_on_existing_table_is_red():
    op, created = op_of("def upgrade():\n    op.create_index('ix_t_a', 't', ['a'])\n")
    c = gate.classify_op(op, created)
    assert c.verdict == gate.RED


def test_create_index_without_concurrently_on_new_table_is_green():
    src = (
        "def upgrade():\n"
        "    op.create_table('t')\n"
        "    op.create_index('ix_t_a', 't', ['a'])\n"
    )
    op, created = op_of(src, index=1)
    c = gate.classify_op(op, created)
    assert c.verdict == gate.GREEN


def test_drop_index_is_yellow():
    op, created = op_of("def upgrade():\n    op.drop_index('ix_t_a', table_name='t')\n")
    c = gate.classify_op(op, created)
    assert c.verdict == gate.YELLOW


def test_drop_column_is_yellow_with_data_loss_auflage():
    op, created = op_of("def upgrade():\n    op.drop_column('t', 'a')\n")
    c = gate.classify_op(op, created)
    assert c.verdict == gate.YELLOW
    assert any("Datenverlust" in a for a in c.auflagen)


def test_create_foreign_key_on_existing_table_is_red():
    op, created = op_of(
        "def upgrade():\n"
        "    op.create_foreign_key('fk_t_u', 't', 'u', ['u_id'], ['id'])\n"
    )
    c = gate.classify_op(op, created)
    assert c.verdict == gate.RED


def test_create_foreign_key_on_new_table_is_green():
    src = (
        "def upgrade():\n"
        "    op.create_table('t')\n"
        "    op.create_foreign_key('fk_t_u', 't', 'u', ['u_id'], ['id'])\n"
    )
    op, created = op_of(src, index=1)
    c = gate.classify_op(op, created)
    assert c.verdict == gate.GREEN


def test_alter_column_type_change_is_red():
    op, created = op_of(
        "def upgrade():\n    op.alter_column('t', 'a', type_=sa.Text())\n"
    )
    c = gate.classify_op(op, created)
    assert c.verdict == gate.RED


def test_alter_column_relax_nullable_is_green():
    op, created = op_of("def upgrade():\n    op.alter_column('t', 'a', nullable=True)\n")
    c = gate.classify_op(op, created)
    assert c.verdict == gate.GREEN


def test_alter_column_set_not_null_on_existing_is_red():
    op, created = op_of("def upgrade():\n    op.alter_column('t', 'a', nullable=False)\n")
    c = gate.classify_op(op, created)
    assert c.verdict == gate.RED


def test_alter_column_rename_is_yellow():
    op, created = op_of(
        "def upgrade():\n    op.alter_column('t', 'a', new_column_name='b')\n"
    )
    c = gate.classify_op(op, created)
    assert c.verdict == gate.YELLOW


def test_rename_table_is_yellow():
    op, created = op_of("def upgrade():\n    op.rename_table('t', 'u')\n")
    c = gate.classify_op(op, created)
    assert c.verdict == gate.YELLOW


def test_bulk_insert_is_yellow():
    op, created = op_of("def upgrade():\n    op.bulk_insert(t, [{'a': 1}])\n")
    c = gate.classify_op(op, created)
    assert c.verdict == gate.YELLOW


def test_drop_table_is_red_regardless_of_size_hint():
    op, created = op_of("def upgrade():\n    op.drop_table('t')\n")
    c = gate.classify_op(op, created)
    assert c.verdict == gate.RED


def test_execute_raw_sql_is_unknown_never_green():
    op, created = op_of("def upgrade():\n    op.execute(\"UPDATE t SET a = 1\")\n")
    c = gate.classify_op(op, created)
    assert c.verdict == gate.UNKNOWN


def test_unknown_op_method_is_unknown():
    op, created = op_of("def upgrade():\n    op.some_future_method('t')\n")
    c = gate.classify_op(op, created)
    assert c.verdict == gate.UNKNOWN


# --- Revisions-Urteil: Kontrakt + Gesamtklasse ------------------------------------------

def revision_from(tmp_path, source):
    rev = write(tmp_path / "r.py", source)
    return gate.parse_revision(rev)


def test_verdict_pass_for_all_green(tmp_path):
    info = revision_from(tmp_path, '''
def upgrade():
    op.create_table('t')

def downgrade():
    op.drop_table('t')
''')
    verdict = gate.classify_revision(info)
    assert verdict.status == "pass"
    assert verdict.overall_class == gate.GREEN


def test_verdict_violation_when_upgrade_missing(tmp_path):
    info = revision_from(tmp_path, "def downgrade():\n    pass\n")
    verdict = gate.classify_revision(info)
    assert verdict.status == "violation"
    assert any("upgrade()" in v for v in verdict.violations)


def test_verdict_violation_when_downgrade_empty_without_justification(tmp_path):
    info = revision_from(tmp_path, "def upgrade():\n    op.create_table('t')\n\ndef downgrade():\n    pass\n")
    verdict = gate.classify_revision(info)
    assert verdict.status == "violation"
    assert any("downgrade()" in v for v in verdict.violations)


def test_verdict_passes_with_justified_one_way_downgrade(tmp_path):
    info = revision_from(tmp_path, '''
def upgrade():
    op.create_table('t')

def downgrade():
    raise NotImplementedError("Einbahn-Migration, siehe ADR-9")
''')
    verdict = gate.classify_revision(info)
    assert verdict.status == "pass"


def test_verdict_mixed_classes_highest_wins(tmp_path):
    info = revision_from(tmp_path, '''
def upgrade():
    op.create_table('t')
    op.drop_index('ix_u_a', table_name='u')
    op.drop_table('v')

def downgrade():
    raise NotImplementedError("irreversibel")
''')
    verdict = gate.classify_revision(info)
    assert verdict.overall_class == gate.RED


def test_verdict_red_without_multistep_marker_is_rejected(tmp_path):
    info = revision_from(tmp_path, '''
def upgrade():
    op.drop_table('t')

def downgrade():
    raise NotImplementedError("irreversibel")
''')
    verdict = gate.classify_revision(info)
    assert verdict.status == "violation"
    assert any("Mehrschritt-Plan" in v for v in verdict.violations)


def test_verdict_red_with_multistep_marker_passes(tmp_path):
    info = revision_from(tmp_path, '''
# Mehrschritt-Plan: Spalte nullable ergaenzen, Backfill in Batches, dann NOT NULL
def upgrade():
    op.alter_column('t', 'a', nullable=False)

def downgrade():
    op.alter_column('t', 'a', nullable=True)
''')
    verdict = gate.classify_revision(info)
    assert verdict.status == "pass"
    assert verdict.overall_class == gate.RED


def test_verdict_multistep_marker_too_short_is_still_rejected(tmp_path):
    info = revision_from(tmp_path, '''
# Mehrschritt-Plan: ok
def upgrade():
    op.drop_table('t')

def downgrade():
    raise NotImplementedError("irreversibel")
''')
    verdict = gate.classify_revision(info)
    assert verdict.status == "violation"


def test_verdict_execute_alone_is_review_required_not_pass(tmp_path):
    """Der zentrale Fall: op.execute() darf niemals stillschweigend als bestanden gelten."""
    info = revision_from(tmp_path, '''
def upgrade():
    op.execute("UPDATE t SET a = 1 WHERE a IS NULL")

def downgrade():
    op.execute("UPDATE t SET a = NULL")
''')
    verdict = gate.classify_revision(info)
    assert verdict.status == "review_required"
    assert len(verdict.unknown_ops) == 1


def test_verdict_execute_alongside_green_ops_still_review_required_not_pass(tmp_path):
    """Ein sonst gruenes Bild darf ein unbewertbares op.execute() nicht uebertoenen."""
    info = revision_from(tmp_path, '''
def upgrade():
    op.create_table('t')
    op.execute("COMMENT ON TABLE t IS 'x'")

def downgrade():
    op.drop_table('t')
''')
    verdict = gate.classify_revision(info)
    assert verdict.status == "review_required"
    assert verdict.overall_class == gate.GREEN
    assert len(verdict.unknown_ops) == 1


def test_verdict_unknown_op_method_is_also_review_required(tmp_path):
    info = revision_from(tmp_path, '''
def upgrade():
    op.some_future_method('t')

def downgrade():
    pass
''')
    verdict = gate.classify_revision(info)
    assert verdict.status in ("review_required", "violation")
    assert len(verdict.unknown_ops) == 1


def test_verdict_no_ops_at_all_is_pass(tmp_path):
    info = revision_from(tmp_path, '''
def upgrade():
    pass

def downgrade():
    pass
''')
    verdict = gate.classify_revision(info)
    # kein downgrade-Inhalt -> Verstoss, aber overall_class bleibt None (keine Ops)
    assert verdict.overall_class is None


# --- Haerte-Erkennung (R6) ---------------------------------------------------------------

def test_hardness_is_g2_without_any_settings_file(tmp_path):
    assert gate.detect_hook_installed(tmp_path) is False
    assert "G2" in gate.hardness_line(False)
    assert "meldet" in gate.hardness_line(False)


def test_hardness_is_g2_with_settings_file_but_no_hook(tmp_path):
    write(tmp_path / ".claude" / "settings.json", json.dumps({"hooks": {}}))
    assert gate.detect_hook_installed(tmp_path) is False


def test_hardness_is_g3_when_hook_present_in_settings_json(tmp_path):
    payload = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [
                    {"type": "command", "command": "python3 skills/sql-schema-architect/scripts/migration_gate.py --hook-check"}
                ]}
            ]
        }
    }
    write(tmp_path / ".claude" / "settings.json", json.dumps(payload))
    assert gate.detect_hook_installed(tmp_path) is True
    assert "G3" in gate.hardness_line(True)
    assert "blockiert" in gate.hardness_line(True)


def test_hardness_is_g3_when_hook_present_in_settings_local_json(tmp_path):
    payload = {"hooks": {"PreToolUse": [{"hooks": [
        {"command": "sql-schema-architect/scripts/migration_gate.py --hook-check"}
    ]}]}}
    write(tmp_path / ".claude" / "settings.local.json", json.dumps(payload))
    assert gate.detect_hook_installed(tmp_path) is True


# --- Report / CLI ------------------------------------------------------------------------

def test_build_report_carries_hardness_and_meta(tmp_path):
    info = revision_from(tmp_path, "def upgrade():\n    op.create_table('t')\n\ndef downgrade():\n    op.drop_table('t')\n")
    verdict = gate.classify_revision(info)
    report = gate.build_report(tmp_path, [(tmp_path / "r.py", verdict)])
    assert report["_meta"]["skill"] == "sql-schema-architect"
    assert report["hook_installed"] is False
    assert "G2" in report["hardness"]
    assert report["revisions"][0]["status"] == "pass"


def test_main_writes_report_to_cache(tmp_path, monkeypatch, capsys):
    rev_dir = tmp_path / "versions"
    write(rev_dir / "0001_widgets.py", "def upgrade():\n    op.create_table('t')\n\ndef downgrade():\n    op.drop_table('t')\n")
    monkeypatch.chdir(tmp_path)
    rc = gate.main([str(rev_dir)])
    assert rc == 0
    report = json.loads((tmp_path / ".skills" / "cache" / "migration-gate-report.json").read_text(encoding="utf-8"))
    assert report["revisions"][0]["status"] == "pass"
    out = capsys.readouterr().out
    assert "Härte:" in out


def test_main_returns_1_on_violation(tmp_path, monkeypatch):
    rev_dir = tmp_path / "versions"
    write(rev_dir / "0001.py", "def upgrade():\n    op.create_table('t')\n\ndef downgrade():\n    pass\n")
    monkeypatch.chdir(tmp_path)
    rc = gate.main([str(rev_dir)])
    assert rc == 1


def test_main_returns_2_on_review_required(tmp_path, monkeypatch):
    rev_dir = tmp_path / "versions"
    write(rev_dir / "0001.py", "def upgrade():\n    op.execute('UPDATE t SET a=1')\n\ndef downgrade():\n    op.execute('UPDATE t SET a=NULL')\n")
    monkeypatch.chdir(tmp_path)
    rc = gate.main([str(rev_dir)])
    assert rc == 2


def test_main_rejects_nonexistent_target(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = gate.main([str(tmp_path / "nope")])
    assert rc == 1
    assert "migration_gate:" in capsys.readouterr().err


def test_main_rejects_empty_directory(tmp_path, monkeypatch, capsys):
    empty = tmp_path / "versions"
    empty.mkdir()
    monkeypatch.chdir(tmp_path)
    rc = gate.main([str(empty)])
    assert rc == 1
    assert "keine Revisionsdateien" in capsys.readouterr().err


def test_main_json_mode_prints_json(tmp_path, monkeypatch, capsys):
    rev_dir = tmp_path / "versions"
    write(rev_dir / "0001.py", "def upgrade():\n    op.create_table('t')\n\ndef downgrade():\n    op.drop_table('t')\n")
    monkeypatch.chdir(tmp_path)
    rc = gate.main([str(rev_dir), "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["revisions"][0]["status"] == "pass"


# --- --hook-check ---------------------------------------------------------------------

def test_hook_check_ignores_non_bash_tool(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", _stdin(json.dumps({"tool_name": "Write", "tool_input": {}})))
    rc = gate.main(["--hook-check"])
    assert rc == 0


def test_hook_check_ignores_unrelated_bash_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", _stdin(json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})))
    rc = gate.main(["--hook-check"])
    assert rc == 0


def test_hook_check_blocks_alembic_upgrade_with_red_revision(tmp_path, monkeypatch):
    rev_dir = tmp_path / "alembic" / "versions"
    write(rev_dir / "0001.py", "def upgrade():\n    op.drop_table('t')\n\ndef downgrade():\n    raise NotImplementedError('x')\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", _stdin(json.dumps({"tool_name": "Bash", "tool_input": {"command": "alembic upgrade head"}})))
    rc = gate.main(["--hook-check"])
    assert rc == 2


def test_hook_check_allows_alembic_upgrade_with_clean_revisions(tmp_path, monkeypatch):
    rev_dir = tmp_path / "alembic" / "versions"
    write(rev_dir / "0001.py", "def upgrade():\n    op.create_table('t')\n\ndef downgrade():\n    op.drop_table('t')\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", _stdin(json.dumps({"tool_name": "Bash", "tool_input": {"command": "alembic upgrade head"}})))
    rc = gate.main(["--hook-check"])
    assert rc == 0


def test_hook_check_blocks_on_review_required_not_only_violation(tmp_path, monkeypatch):
    """Unbewertbares op.execute() darf den Hook nicht passieren lassen."""
    rev_dir = tmp_path / "alembic" / "versions"
    write(rev_dir / "0001.py", "def upgrade():\n    op.execute('UPDATE t SET a=1')\n\ndef downgrade():\n    op.execute('UPDATE t SET a=NULL')\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", _stdin(json.dumps({"tool_name": "Bash", "tool_input": {"command": "alembic upgrade head"}})))
    rc = gate.main(["--hook-check"])
    assert rc == 2


def test_hook_check_allows_when_no_versions_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", _stdin(json.dumps({"tool_name": "Bash", "tool_input": {"command": "alembic upgrade head"}})))
    rc = gate.main(["--hook-check"])
    assert rc == 0


def _stdin(text):
    import io
    return io.StringIO(text)
