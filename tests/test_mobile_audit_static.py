"""Stufe 1 von mobile-audit: die vier Quelltext-Checks ohne Browser (Spec 15).

Die Fixtures hier sind absichtlich winzige Schnipsel statt ganzer Seiten — geprüft
wird die Erkennung, nicht Realismus (Spec 00 §2).
"""

import json

import pytest

from conftest import load_script

audit = load_script("skills/mobile-audit/scripts/audit_static.py")


def write(root, relpath, text):
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def names(findings):
    return sorted(f["check"] for f in findings)


# --- Preset-Auflösung ------------------------------------------------------------
#
# Der Fehler aus lint_schema.py:29 (repo-relativer Default-Pfad, der nur im
# cc-skills-Repo selbst existiert) wird hier nicht wiederholt: Das Preset liegt
# neben dem Skript und muss aus jedem beliebigen Projektverzeichnis laden.


def test_config_loads_from_the_skill_dir_not_the_project(tmp_path):
    config = audit.load_config(tmp_path)
    assert config["tap_target_min_px"] == 24, "Boden muss der Familienwert sein (Spec 15)"
    assert config["input_font_min_px"] == 16


def test_project_override_beats_the_shipped_preset(tmp_path):
    write(tmp_path, ".skills/mobile-audit/audit-config.json", json.dumps({"input_font_min_px": 14}))
    assert audit.load_config(tmp_path)["input_font_min_px"] == 14
    assert audit.load_config(tmp_path)["tap_target_min_px"] == 24, "nicht überschriebene Werte bleiben"


# --- Check: 100vh ----------------------------------------------------------------


def test_finds_100vh_in_css(tmp_path):
    write(tmp_path, "app.css", ".hero { height: 100vh; }\n")
    findings = audit.run_static(tmp_path, audit.load_config(tmp_path))
    assert "viewport-units" in names(findings)
    hit = next(f for f in findings if f["check"] == "viewport-units")
    assert hit["file"] == "app.css" and hit["line"] == 1
    assert "dvh" in hit["fix"]


def test_dvh_and_svh_are_not_flagged(tmp_path):
    write(tmp_path, "app.css", ".hero { height: 100dvh; }\n.sheet { max-height: 100svh; }\n")
    assert "viewport-units" not in names(audit.run_static(tmp_path, audit.load_config(tmp_path)))


# --- Check: Eingabefeld-Schriftgröße ---------------------------------------------


def test_finds_input_font_size_below_the_ios_zoom_threshold(tmp_path):
    write(tmp_path, "form.css", "input, select { font-size: 14px; }\n")
    hit = next(f for f in audit.run_static(tmp_path, audit.load_config(tmp_path))
               if f["check"] == "input-font-size")
    assert hit["measured"] == "14px" and hit["threshold"] == "16px"


def test_input_font_size_at_the_threshold_is_clean(tmp_path):
    write(tmp_path, "form.css", "input { font-size: 16px; }\n")
    assert "input-font-size" not in names(audit.run_static(tmp_path, audit.load_config(tmp_path)))


def test_font_size_on_a_non_input_selector_is_not_our_business(tmp_path):
    write(tmp_path, "type.css", ".caption { font-size: 12px; }\n")
    assert "input-font-size" not in names(audit.run_static(tmp_path, audit.load_config(tmp_path)))


# --- Check: Zoom-Sperre ----------------------------------------------------------


@pytest.mark.parametrize("content", ["width=device-width, user-scalable=no",
                                     "width=device-width, maximum-scale=1",
                                     "width=device-width,maximum-scale=1.0"])
def test_finds_zoom_lock_in_viewport_meta(tmp_path, content):
    write(tmp_path, "index.html", f'<meta name="viewport" content="{content}">\n')
    assert "zoom-lock" in names(audit.run_static(tmp_path, audit.load_config(tmp_path)))


def test_plain_viewport_meta_is_clean(tmp_path):
    write(tmp_path, "index.html", '<meta name="viewport" content="width=device-width, initial-scale=1">\n')
    assert "zoom-lock" not in names(audit.run_static(tmp_path, audit.load_config(tmp_path)))


def test_maximum_scale_above_one_is_not_a_zoom_lock(tmp_path):
    write(tmp_path, "index.html", '<meta name="viewport" content="width=device-width, maximum-scale=5">\n')
    assert "zoom-lock" not in names(audit.run_static(tmp_path, audit.load_config(tmp_path)))


# --- Check: Hover ohne Touch-Pfad ------------------------------------------------
#
# Die enge Verstoßdefinition aus Spec 15: Verstoß ist nur, was unter :hover
# Sichtbarkeit oder Position ändert und keine Focus-/hover:none-Entsprechung hat.
# Ein reiner Hover-Stil ist ausdrücklich kein Verstoß — sonst wird der Check zur
# Fehlalarm-Maschine, die gate.py gekostet hat.


def test_finds_hover_only_dropdown(tmp_path):
    write(tmp_path, "nav.css", ".menu:hover .submenu { display: block; }\n")
    hit = next(f for f in audit.run_static(tmp_path, audit.load_config(tmp_path))
               if f["check"] == "hover-only")
    assert hit["line"] == 1


def test_pure_hover_style_is_not_a_finding(tmp_path):
    write(tmp_path, "button.css", ".btn:hover { background: #eee; box-shadow: 0 1px 2px #0002; }\n")
    assert "hover-only" not in names(audit.run_static(tmp_path, audit.load_config(tmp_path)))


def test_hover_with_a_focus_equivalent_is_not_a_finding(tmp_path):
    write(tmp_path, "nav.css",
          ".menu:hover .submenu { display: block; }\n"
          ".menu:focus-within .submenu { display: block; }\n")
    assert "hover-only" not in names(audit.run_static(tmp_path, audit.load_config(tmp_path)))


def test_hover_guarded_by_hover_media_query_is_not_a_finding(tmp_path):
    write(tmp_path, "nav.css",
          "@media (hover: hover) {\n  .menu:hover .submenu { display: block; }\n}\n")
    assert "hover-only" not in names(audit.run_static(tmp_path, audit.load_config(tmp_path)))


# --- Bericht ---------------------------------------------------------------------


def test_report_carries_the_artifact_header_and_never_claims_stage_two(tmp_path):
    write(tmp_path, "app.css", ".hero { height: 100vh; }\n")
    report = audit.build_report(tmp_path, audit.run_static(tmp_path, audit.load_config(tmp_path)))
    assert report["_meta"]["skill"] == "mobile-audit"
    assert report["stage_2"]["status"] == "ungeprüft", "Stufe 1 darf nie für Stufe 2 sprechen"
    assert all(f["evidence"] == "gemessen" for f in report["findings"])


def test_clean_project_reports_green_without_inventing_findings(tmp_path):
    write(tmp_path, "app.css", ".hero { height: 100dvh; }\ninput { font-size: 16px; }\n")
    write(tmp_path, "index.html", '<meta name="viewport" content="width=device-width, initial-scale=1">\n')
    report = audit.build_report(tmp_path, audit.run_static(tmp_path, audit.load_config(tmp_path)))
    assert report["findings"] == []
    assert report["stage_1"]["status"] == "sauber"


def test_hover_finding_points_at_the_offending_rule_not_the_previous_one(tmp_path):
    """Regression: Der Selektor-Teil des Regex beginnt hinter der vorigen `}` und damit
    noch auf deren Zeile — der Befund zeigte auf die Zeile darüber. Bei einem Contract,
    dessen Kern 'kein Befund ohne Fundstelle' ist, ist das kein Schönheitsfehler."""
    write(tmp_path, "nav.css",
          ".btn:hover { background: #eee; }\n"
          ".nav:hover .flyout { display: block; }\n")
    hit = next(f for f in audit.run_static(tmp_path, audit.load_config(tmp_path))
               if f["check"] == "hover-only")
    assert hit["line"] == 2, f"zeigt auf Zeile {hit['line']} statt auf die Regel in Zeile 2"
