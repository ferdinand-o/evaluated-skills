import json

import pytest

from conftest import load_script

registry = load_script("skills/verified-research/scripts/registry.py")

ASSETS_PATH = "skills/verified-research/assets/registry.json"


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    return d


@pytest.fixture
def home(tmp_path):
    d = tmp_path / "home"
    d.mkdir()
    return d


def _sample_data():
    return {
        "domains": {
            "software-tech": [
                {"pattern": "docs.python.org", "name": "Python-Doku", "tier": 1, "notiz": "Primärquelle, offizielle Doku."},
                {"pattern": "example-blog.example", "name": "Beispiel-Blog", "tier": 3, "notiz": "Sekundärquelle ohne Track Record."},
            ]
        },
        "allgemein": [
            {"pattern": "de.wikipedia.org", "name": "Wikipedia DE", "tier": 3, "notiz": "Kein Beleg selbst, Sekundärquelle."},
        ],
    }


# --- resolve_base_dir ---------------------------------------------------

def test_resolve_base_dir_uses_home_when_no_project_dir(repo, home):
    base, is_project_local = registry.resolve_base_dir(repo, home)
    assert base == home / ".skills" / "verified-research"
    assert is_project_local is False


def test_resolve_base_dir_prefers_project_dir_when_it_exists(repo, home):
    project_dir = repo / ".skills" / "verified-research"
    project_dir.mkdir(parents=True)
    base, is_project_local = registry.resolve_base_dir(repo, home)
    assert base == project_dir
    assert is_project_local is True


def test_resolve_base_dir_project_override_needs_no_registry_file_yet(repo, home):
    """Verzeichnis-Ebene statt Datei-Ebene (Abweichung von Spec 00 §1, siehe Plan):
    Ein leeres .skills/verified-research/-Verzeichnis reicht, damit eine ganz neue
    research/<thema>.md projektlokal statt im Home-Verzeichnis landet."""
    (repo / ".skills" / "verified-research").mkdir(parents=True)
    base, is_project_local = registry.resolve_base_dir(repo, home)
    assert is_project_local is True
    assert not (base / "research" / "irgendwas.md").exists()


# --- ensure_registry / load / save --------------------------------------

def test_ensure_registry_bootstraps_from_assets(repo, home, capsys):
    path, created = registry.ensure_registry(repo, ASSETS_PATH, home)
    assert created is True
    assert path == home / ".skills" / "verified-research" / "registry.json"
    assert path.is_file()
    out = capsys.readouterr().out
    assert str(path) in out
    data = registry.load_registry(path)
    assert "domains" in data


def test_ensure_registry_does_not_overwrite_existing(repo, home):
    path, _ = registry.ensure_registry(repo, ASSETS_PATH, home)
    registry.save_registry(path, {"domains": {}, "allgemein": [], "marker": "unverändert"})
    path2, created2 = registry.ensure_registry(repo, ASSETS_PATH, home)
    assert path2 == path
    assert created2 is False
    assert registry.load_registry(path)["marker"] == "unverändert"


def test_load_registry_missing_file_raises(tmp_path):
    with pytest.raises(registry.RegistryError, match="nicht gefunden"):
        registry.load_registry(tmp_path / "nope.json")


def test_load_registry_invalid_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{nicht json", encoding="utf-8")
    with pytest.raises(registry.RegistryError, match="kein gültiges JSON"):
        registry.load_registry(bad)


def test_save_and_reload_roundtrip(tmp_path):
    path = tmp_path / "sub" / "registry.json"
    data = _sample_data()
    registry.save_registry(path, data)
    reloaded = registry.load_registry(path)
    assert reloaded == data


# --- lookup ---------------------------------------------------------------

def test_lookup_finds_matching_pattern():
    data = _sample_data()
    hit = registry.lookup(data, "https://docs.python.org/3/library/json.html")
    assert hit["name"] == "Python-Doku"
    assert hit["tier"] == 1
    assert hit["domain"] == "software-tech"


def test_lookup_returns_none_without_match():
    data = _sample_data()
    assert registry.lookup(data, "https://unknown-outlet.example/artikel") is None


def test_lookup_prefers_longest_pattern_on_multiple_hits():
    data = {
        "domains": {"software-tech": [
            {"pattern": "example.com", "name": "Kurz", "tier": 3, "notiz": "Sekundärquelle, kein Track Record."},
            {"pattern": "docs.example.com", "name": "Lang", "tier": 1, "notiz": "Primärquelle, offizielle Doku."},
        ]},
        "allgemein": [],
    }
    hit = registry.lookup(data, "https://docs.example.com/guide")
    assert hit["name"] == "Lang"


def test_lookup_checks_allgemein_section_too():
    data = _sample_data()
    hit = registry.lookup(data, "https://de.wikipedia.org/wiki/Test")
    assert hit["domain"] == "allgemein"


# --- lookup: Host-/Pfad-Grenzen (Regression, ehemals reiner Teilstring-Vergleich) ----

def _prefix_registry(pattern="ir.", name="IR-Seiten", tier=1):
    return {
        "domains": {"wirtschaft-statistik": [
            {"pattern": pattern, "name": name, "tier": tier, "notiz": "Primärquelle, Anreizlage beachten."},
        ]},
        "allgemein": [],
    }


def test_lookup_prefix_pattern_does_not_match_inside_word():
    """Der vom Reviewer gemeldete Fall: 'ir.' als Teilstring von 'elixir.example.com'
    darf keine Investor-Relations-Seite ergeben — die Buchstabenfolge kommt zufällig
    vor, niemand hat diese Domain bewertet."""
    data = _prefix_registry()
    assert registry.lookup(data, "https://elixir.example.com/docs") is None


def test_lookup_prefix_pattern_does_not_match_inside_second_word():
    data = _prefix_registry()
    assert registry.lookup(data, "https://kefir.example.blog/rezept") is None


def test_lookup_prefix_pattern_matches_at_string_start():
    data = _prefix_registry()
    hit = registry.lookup(data, "ir.example.com")
    assert hit is not None
    assert hit["name"] == "IR-Seiten"


def test_lookup_prefix_pattern_matches_after_scheme():
    data = _prefix_registry()
    hit = registry.lookup(data, "https://ir.example.com/reports")
    assert hit is not None


def test_lookup_prefix_pattern_matches_as_subdomain_after_dot():
    data = _prefix_registry()
    hit = registry.lookup(data, "www.ir.example.com")
    assert hit is not None


def test_lookup_suffix_hyphen_pattern_still_matches_inside_label():
    """'-vergleich.de' soll bewusst mitten in einem Label ziehen (Suffix-Wildcard für
    Vergleichsportale) — das Trennzeichen '-' ist Teil des Musters, keine zusätzliche
    Randprüfung nötig."""
    data = {"domains": {}, "allgemein": [
        {"pattern": "-vergleich.de", "name": "Vergleichsportale", "tier": 3, "notiz": "Anreizlage Affiliate, kein Track Record."},
    ]}
    assert registry.lookup(data, "https://www.auto-vergleich.de/produkt") is not None


def test_lookup_full_domain_pattern_does_not_match_as_substring_of_longer_host():
    """Ein zweiter, realer Fall aus der Register-Durchsicht: 'arxiv.org' darf nicht in
    'chemarxiv.org' (ChemRxiv, ein eigenständiger, anderer Preprint-Server) zünden."""
    data = {"domains": {"wissenschaft": [
        {"pattern": "arxiv.org", "name": "arXiv (Preprints)", "tier": 1, "notiz": "Primärquelle für die Autoren-Aussage."},
    ]}, "allgemein": []}
    assert registry.lookup(data, "https://chemarxiv.org/engage/chemrxiv/article") is None
    assert registry.lookup(data, "https://arxiv.org/abs/1234.5678") is not None


def test_lookup_file_path_pattern_still_matches_exact_source(tmp_path):
    """Fixture-Pfadmuster (keine Domains) bleiben von der Grenzprüfung unberührt,
    solange der Fundort an einer echten Pfadgrenze ('/', '.', Anfang/Ende) liegt."""
    data = {"domains": {"software-tech": [
        {"pattern": "internal-tool-docs.example", "name": "Interne Doku", "tier": 1, "notiz": "Primärquelle, Projektteam."},
    ]}, "allgemein": []}
    hit = registry.lookup(data, "sources/internal-tool-docs.example.md")
    assert hit is not None
    assert hit["name"] == "Interne Doku"


# --- add_entry --------------------------------------------------------------

def test_add_entry_appends_valid_entry():
    data = _sample_data()
    entry = registry.add_entry(
        data, domain="software-tech", pattern="neue-quelle.example",
        name="Neue Quelle", tier=2,
        notiz="Etablierte Fachredaktion mit redaktionellen Standards und Track Record.",
    )
    assert entry["pattern"] == "neue-quelle.example"
    assert entry in data["domains"]["software-tech"]


def test_add_entry_appends_to_allgemein():
    data = _sample_data()
    registry.add_entry(
        data, domain="allgemein", pattern="neuer-blog.example",
        name="Neuer Blog", tier=3,
        notiz="Anreizlage unklar, kein etablierter Track Record.",
    )
    assert any(e["pattern"] == "neuer-blog.example" for e in data["allgemein"])


def test_add_entry_rejects_invalid_tier():
    data = _sample_data()
    with pytest.raises(registry.RegistryError, match="tier"):
        registry.add_entry(
            data, domain="software-tech", pattern="x", name="X", tier=4,
            notiz="Primärquelle mit langem Track Record und Interessenkonflikt-Prüfung.",
        )


def test_add_entry_rejects_short_notiz():
    data = _sample_data()
    with pytest.raises(registry.RegistryError, match="notiz"):
        registry.add_entry(
            data, domain="software-tech", pattern="x", name="X", tier=1, notiz="ok",
        )


def test_add_entry_rejects_notiz_without_rubric_keyword():
    data = _sample_data()
    with pytest.raises(registry.RegistryError, match="Rubrik-Kriterium"):
        registry.add_entry(
            data, domain="software-tech", pattern="x", name="X", tier=1,
            notiz="Wirkt seriös und macht einen guten Eindruck insgesamt.",
        )


def test_add_entry_rejects_duplicate_pattern():
    data = _sample_data()
    with pytest.raises(registry.RegistryError, match="existiert bereits"):
        registry.add_entry(
            data, domain="software-tech", pattern="docs.python.org", name="Dup", tier=1,
            notiz="Primärquelle, offizielle Dokumentation, hoher Track Record.",
        )


def test_add_entry_duplicate_check_is_case_insensitive():
    data = _sample_data()
    with pytest.raises(registry.RegistryError, match="existiert bereits"):
        registry.add_entry(
            data, domain="software-tech", pattern="DOCS.PYTHON.ORG", name="Dup", tier=1,
            notiz="Primärquelle, offizielle Dokumentation, hoher Track Record.",
        )


# --- topics -----------------------------------------------------------------

def test_count_topics_zero_when_dir_missing(tmp_path):
    assert registry.count_topics(tmp_path / "nope") == 0


def test_count_topics_counts_markdown_files(tmp_path):
    research = tmp_path / "research"
    research.mkdir()
    (research / "a.md").write_text("x", encoding="utf-8")
    (research / "b.md").write_text("x", encoding="utf-8")
    (research / "c.txt").write_text("x", encoding="utf-8")
    assert registry.count_topics(research) == 2


def test_topic_warning_none_below_threshold(tmp_path):
    research = tmp_path / "research"
    research.mkdir()
    for i in range(5):
        (research / f"thema-{i}.md").write_text("x", encoding="utf-8")
    assert registry.topic_warning(research) is None


def test_topic_warning_fires_at_threshold(tmp_path):
    research = tmp_path / "research"
    research.mkdir()
    for i in range(registry.TOPIC_WARNING_THRESHOLD):
        (research / f"thema-{i}.md").write_text("x", encoding="utf-8")
    warning = registry.topic_warning(research)
    assert warning is not None
    assert str(registry.TOPIC_WARNING_THRESHOLD) in warning


# --- CLI (main) ---------------------------------------------------------

def test_cli_lookup_hit_prints_json_and_exits_zero(repo, home, capsys, monkeypatch):
    monkeypatch.setattr(registry.Path, "home", staticmethod(lambda: home))
    exit_code = registry.main(["--repo", str(repo), "--assets", ASSETS_PATH, "lookup", "docs.python.org"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Python-Dokumentation" in out


def test_cli_lookup_miss_exits_one(repo, home, capsys, monkeypatch):
    monkeypatch.setattr(registry.Path, "home", staticmethod(lambda: home))
    exit_code = registry.main(["--repo", str(repo), "--assets", ASSETS_PATH, "lookup", "unknown-outlet.example"])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "Kein Registertreffer" in out


def test_cli_add_persists_entry_to_disk(repo, home, monkeypatch):
    monkeypatch.setattr(registry.Path, "home", staticmethod(lambda: home))
    exit_code = registry.main([
        "--repo", str(repo), "--assets", ASSETS_PATH, "add",
        "--domain", "allgemein", "--pattern", "neu.example", "--name", "Neu",
        "--tier", "2", "--notiz", "Etablierte Redaktion mit redaktionellen Standards und Track Record.",
    ])
    assert exit_code == 0
    path = home / ".skills" / "verified-research" / "registry.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert any(e["pattern"] == "neu.example" for e in data["allgemein"])


def test_cli_add_writes_to_project_dir_when_it_already_exists(repo, home, monkeypatch):
    monkeypatch.setattr(registry.Path, "home", staticmethod(lambda: home))
    (repo / ".skills" / "verified-research").mkdir(parents=True)
    exit_code = registry.main([
        "--repo", str(repo), "--assets", ASSETS_PATH, "add",
        "--domain", "allgemein", "--pattern", "neu.example", "--name", "Neu",
        "--tier", "2", "--notiz", "Etablierte Redaktion mit redaktionellen Standards und Track Record.",
    ])
    assert exit_code == 0
    project_path = repo / ".skills" / "verified-research" / "registry.json"
    assert project_path.is_file()
    home_path = home / ".skills" / "verified-research" / "registry.json"
    assert not home_path.exists()


def test_cli_add_invalid_notiz_returns_error_exit_code(repo, home, monkeypatch):
    monkeypatch.setattr(registry.Path, "home", staticmethod(lambda: home))
    exit_code = registry.main([
        "--repo", str(repo), "--assets", ASSETS_PATH, "add",
        "--domain", "allgemein", "--pattern", "neu.example", "--name", "Neu",
        "--tier", "2", "--notiz", "zu kurz",
    ])
    assert exit_code == 2


def test_cli_topics_reports_count(repo, home, monkeypatch, capsys):
    monkeypatch.setattr(registry.Path, "home", staticmethod(lambda: home))
    exit_code = registry.main(["--repo", str(repo), "--assets", ASSETS_PATH, "topics"])
    assert exit_code == 0
    assert "0 Themen-Dateien" in capsys.readouterr().out
