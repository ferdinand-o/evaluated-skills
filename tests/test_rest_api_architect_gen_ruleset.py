import json

from conftest import load_script

gen_ruleset = load_script("skills/rest-api-architect/scripts/gen_ruleset.py")

FULL_CONVENTIONS = {
    "errors": {
        "media_type": "application/problem+json",
        "required_fields": ["type", "title", "status", "detail", "code"],
    },
    "pagination": {
        "request_params": ["cursor", "limit"],
        "response_fields": ["next_cursor"],
    },
    "versioning": {"prefix_pattern": "^/v[0-9]+/"},
    "idempotency": {"header": "Idempotency-Key"},
    "naming": {"field_case": "snake_case"},
    "timestamps": {"format": "rfc3339"},
}


# --- Pfadauflösung -----------------------------------------------------


def test_resolve_conventions_path_prefers_explicit(tmp_path):
    explicit = tmp_path / "custom.json"
    explicit.write_text("{}", encoding="utf-8")
    result = gen_ruleset.resolve_conventions_path(explicit, tmp_path / "skill", tmp_path / "project")
    assert result == explicit


def test_resolve_conventions_path_prefers_project_override(tmp_path):
    skill_dir = tmp_path / "skill"
    project_root = tmp_path / "project"
    (skill_dir / "assets").mkdir(parents=True)
    (skill_dir / "assets" / "conventions.json").write_text("{}", encoding="utf-8")
    override_dir = project_root / ".skills" / "rest-api-architect"
    override_dir.mkdir(parents=True)
    override = override_dir / "conventions.json"
    override.write_text("{}", encoding="utf-8")

    result = gen_ruleset.resolve_conventions_path(None, skill_dir, project_root)
    assert result == override


def test_resolve_conventions_path_falls_back_to_skill_default(tmp_path):
    skill_dir = tmp_path / "skill"
    project_root = tmp_path / "project"
    (skill_dir / "assets").mkdir(parents=True)
    default = skill_dir / "assets" / "conventions.json"
    default.write_text("{}", encoding="utf-8")

    result = gen_ruleset.resolve_conventions_path(None, skill_dir, project_root)
    assert result == default


def test_resolve_output_path_defaults_next_to_conventions(tmp_path):
    conventions_path = tmp_path / ".skills" / "rest-api-architect" / "conventions.json"
    result = gen_ruleset.resolve_output_path(None, conventions_path)
    assert result == conventions_path.parent / "spectral-ruleset.json"


def test_resolve_output_path_prefers_explicit(tmp_path):
    explicit = tmp_path / "out.json"
    result = gen_ruleset.resolve_output_path(explicit, tmp_path / "conventions.json")
    assert result == explicit


# --- Rule-Generierung ----------------------------------------------------


def test_build_rules_covers_every_preset_dimension():
    rules = gen_ruleset.build_rules(FULL_CONVENTIONS)
    assert "error-response-is-problem-json" in rules
    assert "error-schema-has-required-fields" in rules
    assert "pagination-request-params-present" in rules
    assert "pagination-response-has-next-cursor" in rules
    assert "path-is-versioned" in rules
    assert "unsafe-post-requires-idempotency-key" in rules
    assert "field-names-are-snake-case" in rules
    assert "timestamp-fields-use-date-time-format" in rules


def test_build_rules_omits_rule_for_absent_dimension():
    conventions = {k: v for k, v in FULL_CONVENTIONS.items() if k != "idempotency"}
    rules = gen_ruleset.build_rules(conventions)
    assert "unsafe-post-requires-idempotency-key" not in rules


def test_build_rules_error_message_references_preset_media_type():
    rules = gen_ruleset.build_rules(FULL_CONVENTIONS)
    assert "application/problem+json" in rules["error-response-is-problem-json"]["message"]


def test_build_rules_versioning_uses_configured_pattern():
    custom = dict(FULL_CONVENTIONS)
    custom["versioning"] = {"prefix_pattern": "^/api/v[0-9]+/"}
    rules = gen_ruleset.build_rules(custom)
    then = rules["path-is-versioned"]["then"]
    assert then["functionOptions"]["match"] == "^/api/v[0-9]+/"


def test_build_rules_snake_case_reacts_to_field_case_override():
    custom = dict(FULL_CONVENTIONS)
    custom["naming"] = {"field_case": "camelCase"}
    rules = gen_ruleset.build_rules(custom)
    assert "field-names-are-snake-case" not in rules


def test_build_ruleset_has_rules_key_only():
    ruleset = gen_ruleset.build_ruleset(FULL_CONVENTIONS)
    assert set(ruleset) == {"rules"}
    assert ruleset["rules"] == gen_ruleset.build_rules(FULL_CONVENTIONS)


# --- main() ---------------------------------------------------------------


def test_main_writes_ruleset_with_meta_header(tmp_path, monkeypatch):
    conventions_path = tmp_path / "conventions.json"
    conventions_path.write_text(json.dumps(FULL_CONVENTIONS), encoding="utf-8")
    out_path = tmp_path / "spectral-ruleset.json"

    rc = gen_ruleset.main(["--conventions", str(conventions_path), "--out", str(out_path)])
    assert rc == 0

    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["_meta"]["skill"] == "rest-api-architect"
    assert written["_meta"]["schema"] == gen_ruleset.SCHEMA_VERSION
    assert "gen_ruleset.py" in written["_meta"]["generated"]
    assert "rules" in written
    assert "path-is-versioned" in written["rules"]


def test_main_rejects_missing_conventions_file(tmp_path):
    rc = gen_ruleset.main(["--conventions", str(tmp_path / "nope.json"), "--out", str(tmp_path / "out.json")])
    assert rc == 1


def test_main_rejects_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    rc = gen_ruleset.main(["--conventions", str(bad), "--out", str(tmp_path / "out.json")])
    assert rc == 1
