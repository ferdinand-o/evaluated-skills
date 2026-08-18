import json

from conftest import load_script

gate = load_script("skills/rest-api-architect/scripts/gate.py")


FULL_CONVENTIONS = {
    "errors": {"media_type": "application/problem+json"},
    "pagination": {"request_params": ["cursor", "limit"], "response_fields": ["next_cursor"]},
    "versioning": {"prefix_pattern": "^/v[0-9]+/"},
    "idempotency": {"header": "Idempotency-Key"},
    "naming": {"field_case": "snake_case", "no_verbs_in_paths": True, "verb_exceptions": ["search"]},
    "timestamps": {"format": "rfc3339"},
}

COMPLIANT_TEXT = """
"/v1/orders":
  "post":
    "parameters":
      - "name": "Idempotency-Key"
"components":
  "schemas":
    "Order":
      "properties":
        "created_at":
          "format": "date-time"
"errors": "application/problem+json"
"cursor": true
"limit": true
"next_cursor": true
"""


# --- Toolchain-Erkennung (R3: das ist hier der einzig verifizierbare Zweig) ------


def _which_factory(available):
    def which(name):
        return f"/usr/bin/{name}" if name in available else None
    return which


def test_detect_toolchain_all_missing():
    status = gate.detect_toolchain(which=_which_factory(set()))
    assert status["spectral_usable"] is False
    assert status["oasdiff_usable"] is False


def test_detect_toolchain_spectral_via_npx_and_node():
    status = gate.detect_toolchain(which=_which_factory({"node", "npx"}))
    assert status["spectral_usable"] is True


def test_detect_toolchain_spectral_direct_binary_without_node():
    status = gate.detect_toolchain(which=_which_factory({"spectral"}))
    assert status["spectral_usable"] is True


def test_detect_toolchain_npx_without_node_is_not_usable():
    status = gate.detect_toolchain(which=_which_factory({"npx"}))
    assert status["spectral_usable"] is False


def test_detect_toolchain_oasdiff_standalone():
    status = gate.detect_toolchain(which=_which_factory({"oasdiff"}))
    assert status["oasdiff_usable"] is True


def test_describe_toolchain_gap_both_missing_is_the_exact_required_phrase():
    status = gate.detect_toolchain(which=_which_factory(set()))
    assert gate.describe_toolchain_gap(status) == "ungeprüft (Spectral/oasdiff nicht verfügbar)"


def test_describe_toolchain_gap_only_spectral_missing():
    status = gate.detect_toolchain(which=_which_factory({"oasdiff"}))
    assert gate.describe_toolchain_gap(status) == "ungeprüft (Spectral nicht verfügbar)"


def test_describe_toolchain_gap_only_oasdiff_missing():
    status = gate.detect_toolchain(which=_which_factory({"node", "npx"}))
    assert gate.describe_toolchain_gap(status) == "ungeprüft (oasdiff nicht verfügbar)"


def test_describe_toolchain_gap_none_missing_is_none():
    status = gate.detect_toolchain(which=_which_factory({"node", "npx", "oasdiff"}))
    assert gate.describe_toolchain_gap(status) is None


# --- Konventions-Checkliste (läuft immer, unabhängig von der Toolchain) ----------


def test_checklist_all_pass_on_compliant_text():
    checks = gate.run_checklist(COMPLIANT_TEXT, FULL_CONVENTIONS)
    assert checks
    assert all(c["passed"] for c in checks)


def test_checklist_fails_missing_problem_json():
    text = COMPLIANT_TEXT.replace("application/problem+json", "")
    checks = {c["name"]: c for c in gate.run_checklist(text, FULL_CONVENTIONS)}
    assert checks["errors.media_type"]["passed"] is False


def test_checklist_fails_camel_case_field():
    text = COMPLIANT_TEXT + '\n"createdAt": "x"\n'
    checks = {c["name"]: c for c in gate.run_checklist(text, FULL_CONVENTIONS)}
    assert checks["naming.field_case"]["passed"] is False


def test_checklist_flags_verb_in_path():
    text = COMPLIANT_TEXT + '\n"/v1/orders/get": {}\n'
    checks = {c["name"]: c for c in gate.run_checklist(text, FULL_CONVENTIONS)}
    assert checks["naming.no_verbs_in_paths"]["passed"] is False


def test_checklist_verb_exception_is_not_flagged():
    text = COMPLIANT_TEXT + '\n"/v1/orders/search": {}\n'
    checks = {c["name"]: c for c in gate.run_checklist(text, FULL_CONVENTIONS)}
    assert checks["naming.no_verbs_in_paths"]["passed"] is True


def test_checklist_never_silently_skips_a_dimension():
    checks = gate.run_checklist(COMPLIANT_TEXT, FULL_CONVENTIONS)
    names = {c["name"] for c in checks}
    assert names == {
        "errors.media_type", "pagination.request_params", "pagination.response_fields",
        "versioning.prefix_pattern", "idempotency.header", "naming.field_case",
        "naming.no_verbs_in_paths", "timestamps.format",
    }


# --- Erfolgspfad: nur mit gemocktem subprocess getestet, nie mit echtem Werkzeug --


def _run_returning(stdout, returncode=0):
    def run(cmd, **kwargs):
        class Completed:
            pass
        completed = Completed()
        completed.stdout = stdout
        completed.stderr = ""
        completed.returncode = returncode
        return completed
    return run


def test_run_lint_degrades_when_spectral_unavailable():
    status = gate.detect_toolchain(which=_which_factory(set()))
    result = gate.run_lint("api/openapi.yaml", "ruleset.json", status, run=_run_returning("[]"))
    assert result["degraded"] is True
    assert result["ok"] is None
    assert result["message"] == "ungeprüft (Spectral nicht verfügbar)"


def test_run_lint_parses_mocked_spectral_error_output():
    status = gate.detect_toolchain(which=_which_factory({"node", "npx"}))
    stdout = json.dumps([{"code": "path-is-versioned", "message": "kaputt", "severity": 0}])
    result = gate.run_lint("api/openapi.yaml", "ruleset.json", status, run=_run_returning(stdout))
    assert result["degraded"] is False
    assert result["ok"] is False
    assert result["findings"][0]["severity"] == "error"


def test_run_lint_parses_mocked_spectral_warn_only_output_as_ok():
    status = gate.detect_toolchain(which=_which_factory({"node", "npx"}))
    stdout = json.dumps([{"code": "field-names-are-snake-case", "message": "hm", "severity": 1}])
    result = gate.run_lint("api/openapi.yaml", "ruleset.json", status, run=_run_returning(stdout))
    assert result["ok"] is True
    assert result["findings"][0]["severity"] == "warn"


def test_run_lint_handles_subprocess_failure_to_start():
    status = gate.detect_toolchain(which=_which_factory({"node", "npx"}))

    def broken_run(cmd, **kwargs):
        raise OSError("nicht gefunden")

    result = gate.run_lint("api/openapi.yaml", "ruleset.json", status, run=broken_run)
    assert result["ok"] is False
    assert "fehlgeschlagen" in result["message"]


def test_run_breaking_change_check_no_previous_is_not_a_failure():
    status = gate.detect_toolchain(which=_which_factory({"oasdiff"}))
    result = gate.run_breaking_change_check(None, "api/openapi.yaml", status, run=_run_returning("[]"))
    assert result["ok"] is None
    assert result["degraded"] is False
    assert "kein Vorgänger" in result["message"]


def test_run_breaking_change_check_degrades_when_oasdiff_unavailable(tmp_path):
    previous = tmp_path / "prev.yaml"
    previous.write_text("x", encoding="utf-8")
    status = gate.detect_toolchain(which=_which_factory(set()))
    result = gate.run_breaking_change_check(previous, tmp_path / "cur.yaml", status, run=_run_returning("[]"))
    assert result["degraded"] is True
    assert result["message"] == "ungeprüft (oasdiff nicht verfügbar)"


def test_run_breaking_change_check_parses_mocked_oasdiff_findings(tmp_path):
    previous = tmp_path / "prev.yaml"
    previous.write_text("x", encoding="utf-8")
    status = gate.detect_toolchain(which=_which_factory({"oasdiff"}))
    stdout = json.dumps([{"id": "response-required-property-removed", "text": "Feld entfernt", "level": "error"}])
    result = gate.run_breaking_change_check(previous, tmp_path / "cur.yaml", status, run=_run_returning(stdout))
    assert result["ok"] is False
    assert result["findings"][0]["text"] == "Feld entfernt"


# --- Gesamt-Report ----------------------------------------------------------------


def test_build_gate_report_degraded_toolchain_but_clean_checklist_is_ok(tmp_path):
    openapi = tmp_path / "openapi.yaml"
    openapi.write_text(COMPLIANT_TEXT, encoding="utf-8")
    report = gate.build_gate_report(
        openapi, tmp_path / "ruleset.json", FULL_CONVENTIONS, previous_path=None,
        which=_which_factory(set()), run=_run_returning("[]"),
    )
    assert report["checklist_ok"] is True
    assert report["overall_ok"] is True
    assert report["lint"]["degraded"] is True


def test_build_gate_report_checklist_violation_fails_regardless_of_toolchain(tmp_path):
    openapi = tmp_path / "openapi.yaml"
    openapi.write_text(COMPLIANT_TEXT.replace("application/problem+json", ""), encoding="utf-8")
    report = gate.build_gate_report(
        openapi, tmp_path / "ruleset.json", FULL_CONVENTIONS, previous_path=None,
        which=_which_factory(set()), run=_run_returning("[]"),
    )
    assert report["checklist_ok"] is False
    assert report["overall_ok"] is False


def test_format_report_contains_degradation_line_verbatim(tmp_path):
    openapi = tmp_path / "openapi.yaml"
    openapi.write_text(COMPLIANT_TEXT, encoding="utf-8")
    report = gate.build_gate_report(
        openapi, tmp_path / "ruleset.json", FULL_CONVENTIONS, previous_path=None,
        which=_which_factory(set()), run=_run_returning("[]"),
    )
    text = gate.format_report(report)
    assert "ungeprüft (Spectral/oasdiff nicht verfügbar)" in text
    for check in report["checklist"]:
        assert check["name"] in text


# --- main() -------------------------------------------------------------------


def test_main_exit_zero_when_degraded_but_checklist_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate.shutil, "which", _which_factory(set()))
    openapi = tmp_path / "openapi.yaml"
    openapi.write_text(COMPLIANT_TEXT, encoding="utf-8")
    conventions = tmp_path / "conventions.json"
    conventions.write_text(json.dumps(FULL_CONVENTIONS), encoding="utf-8")

    rc = gate.main(["--openapi", str(openapi), "--conventions", str(conventions), "--ruleset", str(tmp_path / "r.json")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ungeprüft (Spectral/oasdiff nicht verfügbar)" in out


def test_main_exit_nonzero_on_checklist_violation(tmp_path, monkeypatch):
    monkeypatch.setattr(gate.shutil, "which", _which_factory(set()))
    openapi = tmp_path / "openapi.yaml"
    openapi.write_text(COMPLIANT_TEXT.replace("application/problem+json", ""), encoding="utf-8")
    conventions = tmp_path / "conventions.json"
    conventions.write_text(json.dumps(FULL_CONVENTIONS), encoding="utf-8")

    rc = gate.main(["--openapi", str(openapi), "--conventions", str(conventions), "--ruleset", str(tmp_path / "r.json")])
    assert rc == 1


def test_main_rejects_missing_openapi_file(tmp_path):
    conventions = tmp_path / "conventions.json"
    conventions.write_text(json.dumps(FULL_CONVENTIONS), encoding="utf-8")
    rc = gate.main(["--openapi", str(tmp_path / "nope.yaml"), "--conventions", str(conventions), "--ruleset", str(tmp_path / "r.json")])
    assert rc == 2
