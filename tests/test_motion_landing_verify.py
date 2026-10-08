"""Tests für skills/motion-landing/scripts/verify.py.

Playwright und Lighthouse sind in dieser Umgebung nicht installiert und
dürfen nicht installiert werden (siehe docs/known-limits.md). Getestet wird
deshalb nur, was ohne Browser und ohne Node-Toolchain läuft: Szenen-Grenzen,
Budget-Auswertung aus einem eingelesenen Lighthouse-JSON, Toolchain-Erkennung
und der Degradationszweig von main() — real, nicht gemockt, weil diese
Umgebung die Toolchain tatsächlich nicht hat. Der Erfolgspfad (echter
Playwright-/Lighthouse-Lauf) bleibt ungetestet.
"""

import json

import pytest

from conftest import load_script

verify = load_script("skills/motion-landing/scripts/verify.py")


# ---------------------------------------------------------------------------
# Scene / SceneBoundary / Storyboard-Contract
# ---------------------------------------------------------------------------

def scene(name, height_px=100, highlight=False, scene_type="hero-reveal"):
    return verify.Scene(name=name, type=scene_type, height_px=height_px, highlight=highlight)


def test_validate_single_highlight_accepts_exactly_one():
    verify.validate_single_highlight([scene("a"), scene("b", highlight=True), scene("c")])


def test_validate_single_highlight_rejects_zero():
    with pytest.raises(verify.SceneError, match="genau einen Höhepunkt"):
        verify.validate_single_highlight([scene("a"), scene("b")])


def test_validate_single_highlight_rejects_more_than_one():
    with pytest.raises(verify.SceneError, match="genau einen Höhepunkt"):
        verify.validate_single_highlight([scene("a", highlight=True), scene("b", highlight=True)])


def test_validate_single_highlight_rejects_empty_list():
    with pytest.raises(verify.SceneError, match="leer"):
        verify.validate_single_highlight([])


def test_compute_scene_boundaries_pixel_and_percent():
    scenes = [scene("intro", height_px=100), scene("höhepunkt", height_px=300, highlight=True), scene("outro", height_px=100)]
    boundaries = verify.compute_scene_boundaries(scenes)
    assert [b.name for b in boundaries] == ["intro", "höhepunkt", "outro"]
    assert boundaries[0].start_px == 0
    assert boundaries[0].end_px == 100
    assert boundaries[1].start_px == 100
    assert boundaries[1].end_px == 400
    assert boundaries[2].end_px == 500
    # Prozente summieren sich über die letzte Grenze auf 100
    assert boundaries[-1].end_pct == 100.0
    assert boundaries[0].start_pct == 0.0


def test_compute_scene_boundaries_rejects_non_positive_height():
    with pytest.raises(verify.SceneError, match="height_px"):
        verify.compute_scene_boundaries([scene("a", height_px=0, highlight=True)])


def test_compute_scene_boundaries_requires_storyboard_contract():
    """Ohne genau einen Höhepunkt darf gar nicht erst gerechnet werden."""
    with pytest.raises(verify.SceneError, match="Höhepunkt"):
        verify.compute_scene_boundaries([scene("a"), scene("b")])


def test_load_scenes_parses_valid_json(tmp_path):
    path = tmp_path / "scenes.json"
    path.write_text(json.dumps({"scenes": [
        {"name": "intro", "type": "hero-reveal", "height_px": 200, "highlight": False},
        {"name": "moment", "type": "canvas-moment", "height_px": 400, "highlight": True},
    ]}), encoding="utf-8")
    scenes = verify.load_scenes(path)
    assert len(scenes) == 2
    assert scenes[1].highlight is True
    assert scenes[1].type == "canvas-moment"


def test_load_scenes_rejects_missing_scenes_key(tmp_path):
    path = tmp_path / "scenes.json"
    path.write_text(json.dumps({"nope": []}), encoding="utf-8")
    with pytest.raises(verify.SceneError, match="scenes"):
        verify.load_scenes(path)


def test_load_scenes_rejects_non_positive_height(tmp_path):
    path = tmp_path / "scenes.json"
    path.write_text(json.dumps({"scenes": [{"name": "a", "type": "hero-reveal", "height_px": -5}]}), encoding="utf-8")
    with pytest.raises(verify.SceneError, match="height_px"):
        verify.load_scenes(path)


def test_load_scenes_rejects_missing_name(tmp_path):
    path = tmp_path / "scenes.json"
    path.write_text(json.dumps({"scenes": [{"type": "hero-reveal", "height_px": 5}]}), encoding="utf-8")
    with pytest.raises(verify.SceneError, match="name"):
        verify.load_scenes(path)


# ---------------------------------------------------------------------------
# Toolchain-Erkennung
# ---------------------------------------------------------------------------

def test_detect_toolchain_all_present():
    status = verify.detect_toolchain(find_spec=lambda name: object(), which=lambda name: "/usr/bin/" + name)
    assert status.playwright_available is True
    assert status.node_available is True
    assert status.lighthouse_available is True
    assert status.fully_available is True
    assert status.details == ()


def test_detect_toolchain_all_missing():
    status = verify.detect_toolchain(find_spec=lambda name: None, which=lambda name: None)
    assert status.fully_available is False
    assert any("playwright" in d for d in status.details)
    assert any("node" in d for d in status.details)
    assert any("lighthouse" in d for d in status.details)


def test_detect_toolchain_partial_missing_lighthouse_only():
    status = verify.detect_toolchain(
        find_spec=lambda name: object(),
        which=lambda name: "/usr/bin/node" if name == "node" else None,
    )
    assert status.playwright_available is True
    assert status.node_available is True
    assert status.lighthouse_available is False
    assert status.fully_available is False
    assert status.details == ("lighthouse (CLI) fehlt",)


def test_detect_toolchain_runs_for_real_in_this_environment():
    """Diese Umgebung hat wirklich kein Playwright/Lighthouse — kein Mock nötig,
    das ist der real geprüfte Fall aus dem Auftrag."""
    status = verify.detect_toolchain()
    assert status.fully_available is False


# ---------------------------------------------------------------------------
# Budget-Auswertung aus einem eingelesenen Lighthouse-JSON
# ---------------------------------------------------------------------------

def lighthouse_result(lcp=None, cls=None, inp=None, tbt=None):
    audits = {}
    if lcp is not None:
        audits["largest-contentful-paint"] = {"numericValue": lcp}
    if cls is not None:
        audits["cumulative-layout-shift"] = {"numericValue": cls}
    if inp is not None:
        audits["interaction-to-next-paint"] = {"numericValue": inp}
    if tbt is not None:
        audits["total-blocking-time"] = {"numericValue": tbt}
    return {"audits": audits}


def test_evaluate_budgets_all_pass():
    report = verify.evaluate_budgets(lighthouse_result(lcp=1800, cls=0.02, inp=120))
    assert report.all_pass is True
    by_metric = {c.metric: c for c in report.checks}
    assert by_metric["LCP"].status == "pass"
    assert by_metric["CLS"].status == "pass"
    assert by_metric["INP"].status == "pass"


def test_evaluate_budgets_lcp_over_budget_fails():
    report = verify.evaluate_budgets(lighthouse_result(lcp=3200, cls=0.02, inp=120))
    by_metric = {c.metric: c for c in report.checks}
    assert by_metric["LCP"].status == "fail"
    assert report.all_pass is False


def test_evaluate_budgets_cls_over_budget_fails():
    report = verify.evaluate_budgets(lighthouse_result(lcp=1800, cls=0.25, inp=120))
    by_metric = {c.metric: c for c in report.checks}
    assert by_metric["CLS"].status == "fail"


def test_evaluate_budgets_missing_audit_is_missing_not_silently_pass():
    report = verify.evaluate_budgets(lighthouse_result(lcp=1800, cls=0.02))
    by_metric = {c.metric: c for c in report.checks}
    assert by_metric["INP"].status == "missing"
    assert report.all_pass is False


def test_evaluate_budgets_inp_falls_back_to_tbt_with_note():
    report = verify.evaluate_budgets(lighthouse_result(lcp=1800, cls=0.02, tbt=150))
    by_metric = {c.metric: c for c in report.checks}
    assert by_metric["INP"].value == 150
    assert by_metric["INP"].status == "pass"
    assert "Näherungswert" in by_metric["INP"].note


def test_evaluate_budgets_empty_result_all_missing():
    report = verify.evaluate_budgets({})
    assert all(c.status == "missing" for c in report.checks)
    assert report.all_pass is False


# ---------------------------------------------------------------------------
# Degradations-Meldung
# ---------------------------------------------------------------------------

def test_degradation_report_names_missing_tools():
    status = verify.detect_toolchain(find_spec=lambda name: None, which=lambda name: None)
    report = verify.degradation_report(status)
    assert report["status"] == "ungeprüft"
    assert "Playwright" in report["message"] and "Lighthouse" in report["message"]
    assert "nicht verfügbar" in report["message"]


def test_degradation_report_checklist_covers_all_budget_items_not_silently_skipped():
    status = verify.detect_toolchain(find_spec=lambda name: None, which=lambda name: None)
    report = verify.degradation_report(status)
    checklist = report["budgets_checklist"]
    metrics = {item["metric"] for item in checklist}
    assert {"LCP < 2.5s", "CLS < 0.1", "INP < 200ms"} <= metrics
    # Sechs Contract-Punkte aus SKILL.md, nicht nur die drei Zahlen-Budgets
    assert len(checklist) == 6
    assert all(item["status"] == "ungeprüft (Werkzeug fehlt)" for item in checklist)


def test_degradation_report_partial_toolchain_lists_only_the_actually_missing_tool():
    """Die feste Phrase 'Playwright/Lighthouse nicht verfügbar' nennt beide Namen
    immer — was sich unterscheidet, ist `missing_tools`: nur das wirklich
    fehlende Werkzeug landet dort, nicht Playwright, das hier verfügbar ist."""
    status = verify.detect_toolchain(
        find_spec=lambda name: object(),
        which=lambda name: "/usr/bin/node" if name == "node" else None,
    )
    report = verify.degradation_report(status)
    assert report["missing_tools"] == ["lighthouse (CLI) fehlt"]
    assert not any("playwright" in tool.lower() for tool in report["missing_tools"])


# ---------------------------------------------------------------------------
# main() — CLI
# ---------------------------------------------------------------------------

def write_scenes(tmp_path, scenes):
    path = tmp_path / "scenes.json"
    path.write_text(json.dumps({"scenes": scenes}), encoding="utf-8")
    return path


VALID_SCENES = [
    {"name": "intro", "type": "hero-reveal", "height_px": 400, "highlight": False},
    {"name": "moment", "type": "canvas-moment", "height_px": 800, "highlight": True},
]


def test_main_degrades_visibly_when_toolchain_is_missing(tmp_path):
    """Real geprüft: diese Umgebung hat kein Playwright/Lighthouse. main() muss
    das sichtbar melden — Exit 2, Report mit status 'ungeprüft', nichts wird
    stillschweigend übersprungen. Das ist der Kern von Eval 4."""
    scenes_path = write_scenes(tmp_path, VALID_SCENES)
    out_dir = tmp_path / "out"
    rc = verify.main(["--scenes", str(scenes_path), "--out", str(out_dir)])
    assert rc == 2

    report = json.loads((out_dir / "verify-report.json").read_text(encoding="utf-8"))
    assert report["status"] == "ungeprüft"
    assert "Playwright" in report["message"]
    assert "Lighthouse" in report["message"]
    assert "nicht verfügbar" in report["message"]
    assert len(report["budgets_checklist"]) == 6
    assert all(item["status"] == "ungeprüft (Werkzeug fehlt)" for item in report["budgets_checklist"])
    assert report["_meta"]["skill"] == "motion-landing"
    assert report["_meta"]["schema"] == 1


def test_main_rejects_storyboard_without_exactly_one_highlight(tmp_path, capsys):
    scenes_path = write_scenes(tmp_path, [
        {"name": "a", "type": "hero-reveal", "height_px": 100, "highlight": False},
        {"name": "b", "type": "hero-reveal", "height_px": 100, "highlight": False},
    ])
    out_dir = tmp_path / "out"
    rc = verify.main(["--scenes", str(scenes_path), "--out", str(out_dir)])
    assert rc == 3
    assert not (out_dir / "verify-report.json").exists()
    captured = capsys.readouterr()
    assert "Höhepunkt" in captured.err


def test_main_rejects_invalid_scenes_json(tmp_path):
    scenes_path = tmp_path / "scenes.json"
    scenes_path.write_text("{}", encoding="utf-8")
    out_dir = tmp_path / "out"
    rc = verify.main(["--scenes", str(scenes_path), "--out", str(out_dir)])
    assert rc == 3
    assert not (out_dir / "verify-report.json").exists()


def test_main_success_path_writes_pass_report_when_toolchain_and_budgets_are_fine(tmp_path, monkeypatch):
    """Der Erfolgspfad selbst (echter Playwright-/Lighthouse-Lauf) ist hier
    nicht verifizierbar — Playwright/Lighthouse fehlen in dieser Umgebung. Was
    dieser Test wirklich prüft: dass main() bei voller Toolchain die
    Report-Zusammenstellung und Exit-Codes korrekt aus den (gemockten)
    Rückgaben von run_playwright_capture/run_lighthouse ableitet — die
    Playwright-/Lighthouse-Aufrufe selbst sind hier durch Doubles ersetzt."""
    monkeypatch.setattr(verify, "detect_toolchain", lambda: verify.ToolchainStatus(True, True, True, ()))
    monkeypatch.setattr(
        verify, "run_playwright_capture",
        lambda url, scenes, out_dir, *, video, reduced_motion: {"screenshots": [], "video": None, "reduced_motion": reduced_motion},
    )
    monkeypatch.setattr(
        verify, "run_lighthouse",
        lambda url, out_path: {"audits": {
            "largest-contentful-paint": {"numericValue": 1800},
            "cumulative-layout-shift": {"numericValue": 0.02},
            "interaction-to-next-paint": {"numericValue": 120},
        }},
    )

    scenes_path = write_scenes(tmp_path, VALID_SCENES)
    out_dir = tmp_path / "out"
    rc = verify.main(["--scenes", str(scenes_path), "--url", "http://localhost:8000", "--out", str(out_dir)])
    assert rc == 0

    report = json.loads((out_dir / "verify-report.json").read_text(encoding="utf-8"))
    assert report["status"] == "geprüft"
    assert report["all_budgets_pass"] is True


def test_main_success_path_fails_when_a_budget_is_violated(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "detect_toolchain", lambda: verify.ToolchainStatus(True, True, True, ()))
    monkeypatch.setattr(
        verify, "run_playwright_capture",
        lambda url, scenes, out_dir, *, video, reduced_motion: {"screenshots": [], "video": None, "reduced_motion": reduced_motion},
    )
    monkeypatch.setattr(
        verify, "run_lighthouse",
        lambda url, out_path: {"audits": {
            "largest-contentful-paint": {"numericValue": 4000},
            "cumulative-layout-shift": {"numericValue": 0.02},
            "interaction-to-next-paint": {"numericValue": 120},
        }},
    )

    scenes_path = write_scenes(tmp_path, VALID_SCENES)
    out_dir = tmp_path / "out"
    rc = verify.main(["--scenes", str(scenes_path), "--url", "http://localhost:8000", "--out", str(out_dir)])
    assert rc == 1
    report = json.loads((out_dir / "verify-report.json").read_text(encoding="utf-8"))
    assert report["all_budgets_pass"] is False


def test_main_success_path_without_url_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "detect_toolchain", lambda: verify.ToolchainStatus(True, True, True, ()))
    scenes_path = write_scenes(tmp_path, VALID_SCENES)
    out_dir = tmp_path / "out"
    rc = verify.main(["--scenes", str(scenes_path), "--out", str(out_dir)])
    assert rc == 1
    assert not (out_dir / "verify-report.json").exists()
