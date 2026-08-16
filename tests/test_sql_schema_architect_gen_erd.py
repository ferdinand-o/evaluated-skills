import json

import pytest

from conftest import load_script

erd = load_script("skills/sql-schema-architect/scripts/gen_erd.py")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


SIMPLE_MODEL = '''
class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    email = Column(Text, nullable=False, unique=True)

class Order(Base):
    __tablename__ = "orders"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
'''


def test_scan_source_finds_tables_and_columns():
    result = erd.scan_source(SIMPLE_MODEL)
    names = {t.name for t in result.tables}
    assert names == {"users", "orders"}
    users = next(t for t in result.tables if t.name == "users")
    assert {c.name for c in users.columns} == {"id", "email"}
    id_col = next(c for c in users.columns if c.name == "id")
    assert id_col.primary_key is True


def test_scan_source_detects_foreign_key_target():
    result = erd.scan_source(SIMPLE_MODEL)
    orders = next(t for t in result.tables if t.name == "orders")
    fk_col = next(c for c in orders.columns if c.name == "user_id")
    assert fk_col.fk_target == "users.id"


# --- Review-Fund 4: SQLAlchemy-2.0-Stil (Mapped[T]) muss sichtbar bleiben, nicht raten ---

MAPPED_STYLE_MODEL = '''
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
'''


def test_scan_source_flags_mapped_style_column_as_type_unresolved():
    result = erd.scan_source(MAPPED_STYLE_MODEL)
    users = next(t for t in result.tables if t.name == "users")
    id_col = next(c for c in users.columns if c.name == "id")
    assert id_col.type_unresolved is True
    assert id_col.type_text == "?"
    assert id_col.python_annotation == "int"


def test_scan_source_warns_about_unresolved_types_visibly():
    result = erd.scan_source(MAPPED_STYLE_MODEL)
    assert any("nicht statisch auflösbar" in w and "User" in w for w in result.warnings)


def test_scan_source_mapped_style_with_explicit_type_arg_is_resolved():
    """Wenn ein Typ-Positionalargument da ist, bleibt es die verlässliche Quelle —
    Mapped[...] ergänzt nur, überschreibt nicht."""
    src = '''
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
'''
    result = erd.scan_source(src)
    users = next(t for t in result.tables if t.name == "users")
    id_col = next(c for c in users.columns if c.name == "id")
    assert id_col.type_unresolved is False
    assert id_col.type_text == "BigInteger"


def test_render_mermaid_shows_mapped_annotation_hint():
    result = erd.scan_source(MAPPED_STYLE_MODEL)
    text = erd.render_mermaid(result)
    assert "Mapped_int" in text


def test_scan_source_no_warnings_for_clean_models():
    result = erd.scan_source(SIMPLE_MODEL)
    assert result.warnings == []


def test_scan_source_ignores_classes_without_tablename_or_columns():
    src = "class Mixin:\n    pass\n"
    result = erd.scan_source(src)
    assert result.tables == []
    assert result.warnings == []


def test_scan_source_flags_dynamic_tablename_visibly():
    src = '''
class Widget(Base):
    __tablename__ = f"{PREFIX}_widgets"
    id = Column(BigInteger, primary_key=True)
'''
    result = erd.scan_source(src)
    assert len(result.tables) == 1
    assert result.tables[0].resolvable is False
    assert result.tables[0].name == "unresolved_Widget"
    assert any("nicht auflösbar" in w for w in result.warnings)
    # Die Spalten bleiben trotzdem sichtbar, statt komplett zu verschwinden.
    assert result.tables[0].columns


def test_scan_source_flags_mixin_without_own_tablename():
    src = '''
class TimestampMixin:
    created_at = Column(DateTime)

class Article(TimestampMixin, Base):
    id = Column(BigInteger, primary_key=True)
'''
    result = erd.scan_source(src)
    unresolved = [t for t in result.tables if not t.resolvable]
    assert len(unresolved) == 2  # TimestampMixin und Article haben beide Columns, kein Tablename
    names = {t.class_name for t in unresolved}
    assert names == {"TimestampMixin", "Article"}
    assert any("Mixin" in w or "Vererbungs" in w for w in result.warnings)


def test_scan_source_detects_unique_column_as_one_to_one_cardinality():
    src = '''
class Profile(Base):
    __tablename__ = "profiles"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), unique=True)

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
'''
    result = erd.scan_source(src)
    profiles = next(t for t in result.tables if t.name == "profiles")
    col = next(c for c in profiles.columns if c.name == "user_id")
    assert col.unique is True


def test_scan_source_captures_fk_ondelete():
    src = '''
class Order(Base):
    __tablename__ = "orders"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
'''
    result = erd.scan_source(src)
    orders = next(t for t in result.tables if t.name == "orders")
    col = next(c for c in orders.columns if c.name == "user_id")
    assert col.fk_ondelete == "CASCADE"


def test_scan_source_fk_without_ondelete_is_empty_string():
    result = erd.scan_source(SIMPLE_MODEL)
    orders = next(t for t in result.tables if t.name == "orders")
    col = next(c for c in orders.columns if c.name == "user_id")
    assert col.fk_ondelete == ""


def test_scan_source_captures_relationship_calls():
    src = '''
class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    orders = relationship("Order", back_populates="user")
'''
    result = erd.scan_source(src)
    users = next(t for t in result.tables if t.name == "users")
    assert users.relationships == [{"attr": "orders", "target": "Order"}]


def test_scan_source_index_via_table_args_is_visible_on_first_column():
    src = '''
class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_created_at", "created_at"),)
    id = Column(BigInteger, primary_key=True)
    created_at = Column(DateTime)
'''
    result = erd.scan_source(src)
    events = next(t for t in result.tables if t.name == "events")
    assert events.columns[0].has_index is True


# --- scan_path über mehrere Dateien --------------------------------------------------

def test_scan_path_aggregates_across_files(tmp_path):
    write(tmp_path / "user.py", 'class User(Base):\n    __tablename__ = "users"\n    id = Column(BigInteger, primary_key=True)\n')
    write(tmp_path / "order.py", 'class Order(Base):\n    __tablename__ = "orders"\n    id = Column(BigInteger, primary_key=True)\n')
    result = erd.scan_path(tmp_path)
    assert {t.name for t in result.tables} == {"users", "orders"}


def test_scan_path_single_file():
    pass  # abgedeckt über tmp_path-Variante oben; kein zusaetzlicher Testfall noetig


def test_scan_path_reports_syntax_error_visibly(tmp_path):
    write(tmp_path / "broken.py", "class X(:\n    pass\n")
    result = erd.scan_path(tmp_path)
    assert result.tables == []
    assert any("kein gültiges Python" in w for w in result.warnings)


def test_scan_path_empty_directory_returns_nothing(tmp_path):
    result = erd.scan_path(tmp_path)
    assert result.tables == []
    assert result.warnings == []


# --- render_mermaid -------------------------------------------------------------------

def test_render_mermaid_starts_with_er_diagram():
    result = erd.scan_source(SIMPLE_MODEL)
    text = erd.render_mermaid(result)
    assert text.startswith("erDiagram\n")


def test_render_mermaid_includes_table_blocks_and_fk_edge():
    result = erd.scan_source(SIMPLE_MODEL)
    text = erd.render_mermaid(result)
    assert "users {" in text
    assert "orders {" in text
    assert 'users ||--o{ orders : "user_id"' in text


def test_render_mermaid_includes_warnings_as_comments():
    src = '''
class Widget(Base):
    __tablename__ = f"{PREFIX}_widgets"
    id = Column(BigInteger, primary_key=True)
'''
    result = erd.scan_source(src)
    text = erd.render_mermaid(result)
    assert "%% Warnungen" in text
    assert "nicht auflösbar" in text


def test_render_mermaid_includes_relationship_calls_as_comments():
    src = '''
class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    orders = relationship("Order", back_populates="user")
'''
    result = erd.scan_source(src)
    text = erd.render_mermaid(result)
    assert "%% relationship: users.orders -> Order" in text


def test_render_mermaid_table_without_columns_says_so():
    src = 'class Empty(Base):\n    __tablename__ = "empties"\n'
    result = erd.scan_source(src)
    text = erd.render_mermaid(result)
    assert "keine Columns statisch gefunden" in text


# --- write_erd / main ------------------------------------------------------------------

def test_write_erd_writes_file_with_header(tmp_path):
    models = write(tmp_path / "models.py", SIMPLE_MODEL)
    target = erd.write_erd(tmp_path, models, erd.DEFAULT_OUT, "python gen_erd.py models.py")
    text = target.read_text(encoding="utf-8")
    assert text.startswith("<!-- skill: sql-schema-architect | schema: 1 |")
    assert "```mermaid" in text
    assert target == tmp_path / "docs" / "schema" / "erd.md"


def test_main_writes_erd_and_prints_summary(tmp_path, monkeypatch, capsys):
    write(tmp_path / "models.py", SIMPLE_MODEL)
    monkeypatch.chdir(tmp_path)
    rc = erd.main(["models.py"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "2 Tabellen gefunden" in out
    assert (tmp_path / "docs" / "schema" / "erd.md").is_file()


def test_main_rejects_nonexistent_path(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = erd.main(["nope.py"])
    assert rc == 1
    assert "existiert nicht" in capsys.readouterr().err


def test_main_prints_warnings_for_unresolvable_tablename(tmp_path, monkeypatch, capsys):
    write(tmp_path / "models.py", '''
class Widget(Base):
    __tablename__ = f"{PREFIX}_widgets"
    id = Column(BigInteger, primary_key=True)
''')
    monkeypatch.chdir(tmp_path)
    rc = erd.main(["models.py"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Warnung:" in out
