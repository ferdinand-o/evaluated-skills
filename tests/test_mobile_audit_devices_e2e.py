"""End-to-end durch einen echten Browser — der Erfolgspfad von Stufe 2.

`motion-landing/scripts/verify.py` hält im eigenen Docstring fest, dass sein
Erfolgspfad ungetestet blieb, weil die Toolchain in der Entwicklungsumgebung fehlte;
in zwei Testläufen lief dort ausschließlich der Degradationszweig. Diese Datei ist die
Gegenmaßnahme: Sobald Playwright vorhanden ist, fährt sie eine absichtlich kaputte und
eine saubere Seite durch die echte Matrix. Fehlt Playwright, wird übersprungen statt
Erfolg zu behaupten.
"""

import importlib.util

import pytest

from conftest import load_script

devices = load_script("skills/mobile-audit/scripts/audit_devices.py")
static = load_script("skills/mobile-audit/scripts/audit_static.py")

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None,
    reason="Playwright nicht installiert — Erfolgspfad nicht prüfbar, wird nicht behauptet",
)

BROKEN = """<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { margin: 0; font: 16px system-ui; }
  .wide { width: 700px; height: 40px; background: #ddd; }
  .bar { position: fixed; left: 0; right: 0; bottom: 0; padding: 6px; background: #123; }
  .bar button { font-size: 16px; }
  .tiny { width: 18px; height: 18px; padding: 0; }
</style>
<div class="wide">zu breit</div>
<input id="feld" placeholder="Login">
<button class="tiny" id="mini">x</button>
<div class="bar"><button id="submit">Anmelden</button></div>
"""

CLEAN = """<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { margin: 0; font: 16px system-ui; }
  button { min-width: 44px; min-height: 44px; font-size: 16px; }
</style>
<input id="feld" placeholder="Login">
<button id="submit">Anmelden</button>
"""


def page_url(tmp_path, html):
    path = tmp_path / "page.html"
    path.write_text(html, encoding="utf-8")
    return path.as_uri()


def test_broken_page_yields_the_expected_checks_through_a_real_browser(tmp_path):
    config = static.load_config(".")
    results = devices.run_matrix(page_url(tmp_path, BROKEN), config)

    assert [r["device"] for r in results] == [d["name"] for d in config["devices"]]
    by_device = {r["device"]: {f["check"] for f in r["findings"]} for r in results}

    # Das Notch-Profil ist das einzige mit Insets — nur dort kann safe-area anschlagen.
    assert "keyboard-overlay" in by_device["iphone-notch"]
    assert "tap-target-size" in by_device["iphone-notch"]
    assert "horizontal-overflow" in by_device["android-schmal"], "360px-Viewport, 700px-Element"

    keyboard = next(f for r in results for f in r["findings"] if f["check"] == "keyboard-overlay")
    assert keyboard["evidence"] == "modelliert"
    assert keyboard["selector"] == "button#submit"


def test_clean_page_produces_no_findings_through_a_real_browser(tmp_path):
    results = devices.run_matrix(page_url(tmp_path, CLEAN), static.load_config("."))
    assert [f for r in results for f in r["findings"]] == []


def test_wide_element_is_clean_on_the_tablet_profile(tmp_path):
    """Gegenprobe zur Matrix: 700px passen in 820px — dasselbe Dokument, anderes Urteil.
    Ohne diesen Test könnte die Matrix aus einem einzigen Profil bestehen."""
    results = devices.run_matrix(page_url(tmp_path, BROKEN), static.load_config("."))
    tablet = next(r for r in results if r["device"] == "tablet")
    assert "horizontal-overflow" not in {f["check"] for f in tablet["findings"]}
