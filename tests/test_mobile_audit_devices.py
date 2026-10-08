"""Stufe 2 von mobile-audit: Bewertung der Geräte-Messwerte (Spec 15).

Die Bewertung ist von der Playwright-Ansteuerung getrennt und bekommt hier
synthetische Messdaten — genau die Trennung, die `motion-landing/scripts/verify.py`
im Docstring beschreibt, damit die Logik ohne Browser prüfbar bleibt. Der
Erfolgspfad durch den echten Browser wird zusätzlich end-to-end geprüft (siehe
test_mobile_audit_devices_e2e.py), was bei verify.py nie geschah.
"""

import json

import pytest

from conftest import load_script

devices = load_script("skills/mobile-audit/scripts/audit_devices.py")
static = load_script("skills/mobile-audit/scripts/audit_static.py")

PROFILE = {"name": "iphone-notch", "width": 390, "height": 844, "device_scale_factor": 3,
           "safe_area_top": 47, "safe_area_bottom": 34, "keyboard_px": 336, "why": "Test"}


def config():
    return static.load_config(".")


def measurement(**overrides):
    """Rohdaten, wie sie ein `page.evaluate`-Aufruf liefert — hier per Hand gebaut."""
    data = {
        "viewport": {"width": 390, "height": 844},
        "document_scroll_width": 390,
        "has_input": False,
        "elements": [],
        "overflowing": [],
    }
    data.update(overrides)
    return data


def element(selector="button#a", top=100, bottom=140, left=10, right=100,
            fixed_ancestor=None, visible=True, disabled=False):
    return {"selector": selector, "top": top, "bottom": bottom, "left": left, "right": right,
            "width": right - left, "height": bottom - top,
            "fixed_ancestor": fixed_ancestor, "visible": visible, "disabled": disabled}


def names(findings):
    return sorted({f["check"] for f in findings})


# --- Degradation -----------------------------------------------------------------
#
# Der wichtigste Test der Stufe: Ohne Toolchain darf nie Erfolg gemeldet werden
# (Spec 00 §4). motion-landing hat genau hier seinen einzigen real geprüften Zweig.


def test_report_without_toolchain_is_ungeprueft_never_green():
    report = devices.build_report(status=devices.ToolchainStatus(False, ("playwright fehlt",)),
                                  results=[])
    assert report["stage_2"]["status"] == "ungeprüft"
    assert "playwright" in " ".join(report["stage_2"]["missing_tools"]).lower()
    assert report["stage_2"].get("devices") == []


def test_report_with_results_marks_evidence_per_finding():
    findings = devices.evaluate(measurement(document_scroll_width=460), config(), PROFILE)
    report = devices.build_report(status=devices.ToolchainStatus(True, ()),
                                  results=[{"device": PROFILE["name"], "findings": findings}])
    assert report["stage_2"]["status"] == "geprüft"
    assert all(f["evidence"] in ("gemessen", "modelliert") for f in findings)


# --- horizontales Overflow -------------------------------------------------------


def test_document_wider_than_viewport_is_a_finding():
    findings = devices.evaluate(measurement(document_scroll_width=460), config(), PROFILE)
    hit = next(f for f in findings if f["check"] == "horizontal-overflow")
    assert hit["measured"] == "460px" and hit["threshold"] == "390px"
    assert hit["evidence"] == "gemessen"


def test_document_exactly_at_viewport_width_is_clean():
    assert "horizontal-overflow" not in names(devices.evaluate(measurement(), config(), PROFILE))


# --- Tap-Targets -----------------------------------------------------------------


def test_hit_area_below_the_family_floor_is_a_finding():
    small = element(selector="button#x", top=10, bottom=30, left=10, right=30)  # 20x20
    hit = next(f for f in devices.evaluate(measurement(elements=[small]), config(), PROFILE)
               if f["check"] == "tap-target-size")
    assert hit["measured"] == "20×20px" and hit["threshold"] == "24×24px"


def test_hit_area_at_the_floor_is_clean_and_the_44px_hint_is_not_a_violation():
    ok = element(top=10, bottom=34, left=10, right=34)  # exakt 24x24
    findings = devices.evaluate(measurement(elements=[ok]), config(), PROFILE)
    violations = [f for f in findings if f["check"] == "tap-target-size"]
    assert violations == [], "24x24 ist der Boden — kein Verstoß"


def test_invisible_and_disabled_elements_are_not_measured():
    hidden = element(selector="button#h", top=0, bottom=0, left=0, right=0, visible=False)
    off = element(selector="button#d", top=10, bottom=20, left=10, right=20, disabled=True)
    findings = devices.evaluate(measurement(elements=[hidden, off]), config(), PROFILE)
    assert "tap-target-size" not in names(findings), "unsichtbare/deaktivierte Elemente sind kein Befund"


# --- Safe-Area -------------------------------------------------------------------


def test_fixed_element_under_the_notch_is_a_finding():
    top_bar = element(selector="header.bar", top=0, bottom=40, left=0, right=390,
                      fixed_ancestor="fixed")
    hit = next(f for f in devices.evaluate(measurement(elements=[top_bar]), config(), PROFILE)
               if f["check"] == "safe-area")
    assert "47" in hit["threshold"]


def test_fixed_element_clear_of_the_insets_is_clean():
    bar = element(selector="header.bar", top=60, bottom=100, left=0, right=390,
                  fixed_ancestor="fixed")
    assert "safe-area" not in names(devices.evaluate(measurement(elements=[bar]), config(), PROFILE))


def test_element_in_normal_flow_under_the_notch_is_not_a_safe_area_finding():
    """Nur Fixiertes hängt in der Notch fest — normaler Fluss scrollt weg."""
    flowing = element(selector="h1", top=0, bottom=40, left=0, right=390, fixed_ancestor=None)
    assert "safe-area" not in names(devices.evaluate(measurement(elements=[flowing]), config(), PROFILE))


# --- Keyboard-Geometrie (modelliert) ---------------------------------------------
#
# Ergebnis des Spikes: nicht emulierbar, deshalb modelliert. Die Tastatur verdeckt
# die unteren K Pixel; gemeldet wird nur, was dort fixiert festhängt.


def test_fixed_submit_below_the_keyboard_line_is_a_finding():
    submit = element(selector="button#submit", top=806, bottom=830, left=10, right=380,
                     fixed_ancestor="fixed")
    findings = devices.evaluate(measurement(has_input=True, elements=[submit]), config(), PROFILE)
    hit = next(f for f in findings if f["check"] == "keyboard-overlay")
    assert hit["evidence"] == "modelliert", "K ist ein Modell, kein Messwert"
    assert "508" in hit["threshold"], "844 - 336 = 508"


def test_same_element_without_an_input_on_the_page_is_not_a_finding():
    """Ohne Eingabefeld erscheint keine Tastatur — dann verdeckt auch nichts."""
    submit = element(selector="button#submit", top=806, bottom=830, left=10, right=380,
                     fixed_ancestor="fixed")
    findings = devices.evaluate(measurement(has_input=False, elements=[submit]), config(), PROFILE)
    assert "keyboard-overlay" not in names(findings)


def test_element_in_normal_flow_below_the_keyboard_line_is_not_a_finding():
    """Der Browser scrollt das fokussierte Feld hinein — nur Fixiertes bleibt liegen."""
    submit = element(selector="button#submit", top=806, bottom=830, left=10, right=380,
                     fixed_ancestor=None)
    findings = devices.evaluate(measurement(has_input=True, elements=[submit]), config(), PROFILE)
    assert "keyboard-overlay" not in names(findings)


# --- Fundstellen -----------------------------------------------------------------


def test_every_finding_carries_device_and_selector():
    submit = element(selector="button#submit", top=806, bottom=830, left=10, right=380,
                     fixed_ancestor="fixed")
    findings = devices.evaluate(measurement(has_input=True, document_scroll_width=460,
                                            elements=[submit]), config(), PROFILE)
    assert findings, "Testdaten sollen Befunde erzeugen"
    for finding in findings:
        assert finding["device"] == "iphone-notch"
        assert finding["selector"], f"{finding['check']} ohne Selektor"
        assert finding["fix"], f"{finding['check']} ohne Rezept"
