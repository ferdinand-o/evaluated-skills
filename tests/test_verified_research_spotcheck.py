import json
import math

from conftest import load_script

spotcheck = load_script("skills/verified-research/scripts/spotcheck.py")


def report_text(*lines: str) -> str:
    return "# Bericht\n\n" + "\n".join(lines) + "\n"


# --- parse_claims -----------------------------------------------------------

def test_parse_claims_reads_tier_and_source():
    text = report_text("- Die API heißt v2. [Tier 1, Quelle: sources/primary.md]")
    claims = spotcheck.parse_claims(text)
    assert len(claims) == 1
    c = claims[0]
    assert c.text == "Die API heißt v2."
    assert c.tier == 1
    assert c.source == "sources/primary.md"
    assert c.critical is False


def test_parse_claims_reads_critical_flag():
    text = report_text("- Marktanteil 42 %. [Tier 3, kritisch, Quelle: sources/blog.md]")
    claims = spotcheck.parse_claims(text)
    assert claims[0].critical is True


def test_parse_claims_ignores_non_matching_lines():
    text = report_text(
        "Das ist ein normaler Absatz ohne Tag.",
        "- Ein Claim mit Tag. [Tier 2, Quelle: sources/x.md]",
        "- Eine Aufzählung ohne Tag.",
    )
    claims = spotcheck.parse_claims(text)
    assert len(claims) == 1
    assert claims[0].text == "Ein Claim mit Tag."


def test_parse_claims_returns_empty_list_without_matches():
    assert spotcheck.parse_claims("Nur Prosa, keine Claims.\n") == []


def test_parse_claims_handles_multiple_claims_with_line_numbers():
    text = report_text(
        "- Erster Claim. [Tier 1, Quelle: a.md]",
        "- Zweiter Claim. [Tier 2, kritisch, Quelle: b.md]",
    )
    claims = spotcheck.parse_claims(text)
    assert [c.text for c in claims] == ["Erster Claim.", "Zweiter Claim."]
    assert claims[0].line_no < claims[1].line_no


# --- select_sample -----------------------------------------------------------

def _claim(text, tier=1, critical=False, source="s.md"):
    return spotcheck.Claim(text=text, tier=tier, critical=critical, source=source, line_no=1)


def test_select_sample_empty_claims_returns_empty():
    assert spotcheck.select_sample([]) == []


def test_select_sample_includes_all_critical_claims():
    claims = [_claim(f"kritisch-{i}", critical=True) for i in range(5)]
    sample = spotcheck.select_sample(claims)
    assert set(c.text for c in sample) == {c.text for c in claims}


def test_select_sample_minimum_rule_covers_two_noncritical_claims():
    """Der R9-Grenzfall: "ein Drittel, abgerundet" ergibt für ein oder zwei
    unkritische Claims 0 (nicht für drei — 3 * (1/3) rundet in IEEE-754-double
    exakt auf 1.0). Ohne Minimum würde bei zwei unkritischen Claims nichts geprüft."""
    assert math.floor(2 * spotcheck.SPOTCHECK_REST_QUOTA) == 0  # dokumentiert die Falle
    claims = [_claim(f"rest-{i}") for i in range(2)]
    sample = spotcheck.select_sample(claims)
    assert len(sample) >= spotcheck.SPOTCHECK_MIN_SAMPLE
    assert sample[0] in claims


def test_select_sample_exact_three_noncritical_is_not_the_edge_case():
    """Gegenprobe zur obigen Falle: Bei genau drei Claims rundet 3 * (1/3) exakt auf
    1.0, die Quote liefert also schon ohne Minimum-Regel einen Treffer."""
    assert math.floor(3 * spotcheck.SPOTCHECK_REST_QUOTA) == 1
    claims = [_claim(f"rest-{i}") for i in range(3)]
    sample = spotcheck.select_sample(claims)
    assert len(sample) == 1


def test_select_sample_takes_a_third_of_larger_rest():
    claims = [_claim(f"rest-{i}") for i in range(9)]
    sample = spotcheck.select_sample(claims)
    assert len(sample) == 3


def test_select_sample_combines_critical_and_rest_quota():
    critical = [_claim(f"krit-{i}", critical=True) for i in range(2)]
    rest = [_claim(f"rest-{i}") for i in range(9)]
    sample = spotcheck.select_sample(critical + rest)
    sample_texts = {c.text for c in sample}
    assert all(c.text in sample_texts for c in critical)
    assert len(sample) == 2 + 3


def test_select_sample_is_deterministic_for_fixed_seed():
    claims = [_claim(f"rest-{i}") for i in range(12)]
    sample_a = spotcheck.select_sample(claims, seed=42)
    sample_b = spotcheck.select_sample(claims, seed=42)
    assert [c.text for c in sample_a] == [c.text for c in sample_b]


def test_select_sample_different_seed_can_differ():
    claims = [_claim(f"rest-{i}") for i in range(12)]
    sample_a = spotcheck.select_sample(claims, seed=1)
    sample_b = spotcheck.select_sample(claims, seed=2)
    assert [c.text for c in sample_a] != [c.text for c in sample_b]


# --- CLI (main) ---------------------------------------------------------

def test_cli_missing_report_returns_exit_2(tmp_path, capsys):
    exit_code = spotcheck.main(["--report", "nope.md", "--repo", str(tmp_path)])
    assert exit_code == 2
    assert "nicht gefunden" in capsys.readouterr().err


def test_cli_no_claims_returns_exit_3(tmp_path, capsys):
    report = tmp_path / "report.md"
    report.write_text("Nur Prosa.\n", encoding="utf-8")
    exit_code = spotcheck.main(["--report", "report.md", "--repo", str(tmp_path)])
    assert exit_code == 3
    assert "Keine Claims" in capsys.readouterr().err


def test_cli_writes_sample_json_and_prints_summary(tmp_path, capsys):
    report = tmp_path / "report.md"
    report.write_text(report_text(
        "- Marktanteil 42 %. [Tier 3, kritisch, Quelle: sources/blog.md]",
        "- Nebenfakt A. [Tier 1, Quelle: sources/a.md]",
        "- Nebenfakt B. [Tier 1, Quelle: sources/b.md]",
        "- Nebenfakt C. [Tier 1, Quelle: sources/c.md]",
    ), encoding="utf-8")

    exit_code = spotcheck.main(["--report", "report.md", "--repo", str(tmp_path)])
    assert exit_code == 0

    out_path = tmp_path / ".skills" / "cache" / "verified-research-spotcheck.json"
    assert out_path.is_file()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["_meta"]["skill"] == "verified-research"
    assert payload["claims_total"] == 4
    assert payload["critical_total"] == 1
    sample_texts = {e["text"] for e in payload["sample"]}
    assert "Marktanteil 42 %." in sample_texts  # kritisch ist immer dabei

    out = capsys.readouterr().out
    assert "Claims gefunden" in out
    assert "Öffne sources/blog.md" in out
