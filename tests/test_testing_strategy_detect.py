import json
import subprocess

import pytest

from conftest import load_script

detect_stack = load_script("skills/testing-strategy/scripts/detect_stack.py")


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def init_git(repo):
    git(repo, "init", "--quiet", "--initial-branch=main")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "Test")


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "--quiet", "-m", message)


def write(repo, relpath, text):
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Ränder: leeres Verzeichnis, kein Git
# ---------------------------------------------------------------------------


def test_empty_directory_has_no_candidates_and_no_legacy_suspicion(tmp_path):
    result = detect_stack.classify(tmp_path)
    assert result["candidates"] == []
    assert result["primary"] is None
    assert result["ambiguous"] is False
    assert result["legacy"]["suspected"] is False
    assert result["git"]["available"] is False


def test_no_git_repo_notes_missing_history_signal(tmp_path):
    write(tmp_path, "a.py", "x = 1\n")
    result = detect_stack.classify(tmp_path)
    assert result["git"]["available"] is False
    assert any("Git" in reason for reason in result["legacy"]["reasons"])


# ---------------------------------------------------------------------------
# Chrome-Extension-Signal
# ---------------------------------------------------------------------------


def test_manifest_json_with_manifest_version_signals_extension(tmp_path):
    write(tmp_path, "manifest.json", json.dumps({"manifest_version": 3, "name": "x", "background": {}}))
    result = detect_stack.classify(tmp_path)
    assert result["primary"] == "chrome-extension"
    types = {c["type"] for c in result["candidates"]}
    assert types == {"chrome-extension"}


def test_manifest_json_without_manifest_version_key_is_not_a_signal(tmp_path):
    """PWA-Web-App-Manifeste heißen auch `manifest.json`, haben aber kein
    `manifest_version` — sonst würde jede PWA fälschlich als Extension gelten."""
    write(tmp_path, "manifest.json", json.dumps({"name": "x", "start_url": "/", "display": "standalone"}))
    result = detect_stack.classify(tmp_path)
    assert result["candidates"] == []


def test_malformed_manifest_json_is_skipped_not_crashed(tmp_path):
    write(tmp_path, "manifest.json", "{not valid json")
    result = detect_stack.classify(tmp_path)
    assert result["candidates"] == []


# ---------------------------------------------------------------------------
# REST-API-Signal
# ---------------------------------------------------------------------------


def test_openapi_file_signals_rest_api(tmp_path):
    write(tmp_path, "openapi.yaml", "openapi: 3.0.0\n")
    result = detect_stack.classify(tmp_path)
    assert result["primary"] == "rest-api"


def test_router_pattern_in_entry_file_signals_rest_api(tmp_path):
    write(tmp_path, "app.py", "@app.get('/health')\ndef health():\n    return {}\n")
    result = detect_stack.classify(tmp_path)
    assert result["primary"] == "rest-api"


def test_fastapi_dependency_in_pyproject_signals_rest_api(tmp_path):
    write(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    result = detect_stack.classify(tmp_path)
    assert result["primary"] == "rest-api"


def test_express_dependency_in_package_json_signals_rest_api(tmp_path):
    write(tmp_path, "package.json", json.dumps({"dependencies": {"express": "^4.0.0"}}))
    result = detect_stack.classify(tmp_path)
    assert result["primary"] == "rest-api"


# ---------------------------------------------------------------------------
# Frontend-SPA und CLI-Library
# ---------------------------------------------------------------------------


def test_react_dependency_signals_frontend_spa(tmp_path):
    write(tmp_path, "package.json", json.dumps({"dependencies": {"react": "^18.0.0"}}))
    result = detect_stack.classify(tmp_path)
    assert result["primary"] == "frontend-spa"


def test_bin_field_in_package_json_signals_cli_library(tmp_path):
    write(tmp_path, "package.json", json.dumps({"name": "x", "bin": {"x": "./cli.js"}}))
    result = detect_stack.classify(tmp_path)
    assert result["primary"] == "cli-library"


def test_project_scripts_section_in_pyproject_signals_cli_library(tmp_path):
    write(tmp_path, "pyproject.toml", "[project]\nname = 'x'\n\n[project.scripts]\nx = 'x:main'\n")
    result = detect_stack.classify(tmp_path)
    assert result["primary"] == "cli-library"


# ---------------------------------------------------------------------------
# Mehrdeutigkeit: Routing-Trap
# ---------------------------------------------------------------------------


def test_manifest_json_and_openapi_together_are_ambiguous(tmp_path):
    write(tmp_path, "manifest.json", json.dumps({"manifest_version": 3}))
    write(tmp_path, "openapi.yaml", "openapi: 3.0.0\n")
    result = detect_stack.classify(tmp_path)
    assert result["ambiguous"] is True
    assert result["primary"] is None
    types = {c["type"] for c in result["candidates"]}
    assert types == {"chrome-extension", "rest-api"}


def test_ambiguous_result_lists_both_candidates_with_signals(tmp_path):
    """Verdrahtungstest: Nicht nur die Scoring-Funktionen einzeln, sondern das
    Endergebnis muss beide Kandidaten mit ihren Signalen tragen — sonst kann
    die Skill nicht nachfragen, welcher Typ zutrifft."""
    write(tmp_path, "manifest.json", json.dumps({"manifest_version": 3}))
    write(tmp_path, "openapi.yaml", "openapi: 3.0.0\n")
    result = detect_stack.classify(tmp_path)
    by_type = {c["type"]: c for c in result["candidates"]}
    assert by_type["chrome-extension"]["signals"]
    assert by_type["rest-api"]["signals"]


# ---------------------------------------------------------------------------
# Monorepo mit mehreren Sprachen
# ---------------------------------------------------------------------------


def test_monorepo_detects_languages_in_subdirectories(tmp_path):
    write(tmp_path / "frontend", "package.json", json.dumps({"dependencies": {"react": "^18.0.0"}}))
    write(tmp_path / "backend", "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    result = detect_stack.classify(tmp_path)
    locations = {lang["location"] for lang in result["languages"]}
    assert "frontend/" in locations
    assert "backend/" in locations
    types = {c["type"] for c in result["candidates"]}
    assert "frontend-spa" in types
    assert "rest-api" in types


def test_ignored_directories_are_not_scanned(tmp_path):
    write(tmp_path / "node_modules" / "somelib", "package.json", json.dumps({"dependencies": {"react": "1.0.0"}}))
    result = detect_stack.classify(tmp_path)
    assert result["candidates"] == []


# ---------------------------------------------------------------------------
# Runner-Erkennung, inkl. Leerfall
# ---------------------------------------------------------------------------


def test_package_json_without_test_runner_has_null_runner(tmp_path):
    write(tmp_path, "package.json", json.dumps({"name": "x", "scripts": {"test": "echo \"Error: no test specified\" && exit 1"}}))
    result = detect_stack.classify(tmp_path)
    js_lang = next(lang for lang in result["languages"] if lang["location"] == ".")
    assert js_lang["runner"] is None


def test_package_json_with_vitest_devdependency_sets_runner(tmp_path):
    write(tmp_path, "package.json", json.dumps({"devDependencies": {"vitest": "^1.0.0"}}))
    result = detect_stack.classify(tmp_path)
    js_lang = next(lang for lang in result["languages"] if lang["location"] == ".")
    assert js_lang["runner"] == "vitest"


def test_tsconfig_marks_language_typescript(tmp_path):
    write(tmp_path, "package.json", json.dumps({}))
    write(tmp_path, "tsconfig.json", "{}")
    result = detect_stack.classify(tmp_path)
    js_lang = next(lang for lang in result["languages"] if lang["location"] == ".")
    assert js_lang["name"] == "typescript"


def test_pyproject_with_pytest_dependency_sets_runner(tmp_path):
    write(tmp_path, "pyproject.toml", "[project]\ndependencies = ['pytest']\n")
    result = detect_stack.classify(tmp_path)
    py_lang = next(lang for lang in result["languages"] if lang["location"] == ".")
    assert py_lang["runner"] == "pytest"


def test_requirements_txt_without_pyproject_is_read(tmp_path):
    write(tmp_path, "requirements.txt", "pytest\nflask\n")
    result = detect_stack.classify(tmp_path)
    py_lang = next(lang for lang in result["languages"] if lang["location"] == ".")
    assert py_lang["runner"] == "pytest"
    assert result["primary"] == "rest-api"


def test_pom_xml_signals_java_and_spring_as_rest_api(tmp_path):
    write(tmp_path, "pom.xml", "<project><dependencies><dependency>spring-boot-starter-web</dependency></dependencies></project>")
    result = detect_stack.classify(tmp_path)
    java_lang = next(lang for lang in result["languages"] if lang["name"] == "java")
    assert java_lang["location"] == "."
    assert result["primary"] == "rest-api"


# ---------------------------------------------------------------------------
# Legacy-Score
# ---------------------------------------------------------------------------


def test_legacy_suspected_via_no_tests_and_commit_count(tmp_path):
    init_git(tmp_path)
    for i in range(10):
        write(tmp_path, f"module_{i}.py", f"def f_{i}():\n    return {i}\n")
        commit_all(tmp_path, f"feat: modul {i}")
    result = detect_stack.classify(tmp_path)
    assert result["legacy"]["suspected"] is True
    assert result["legacy"]["score"] >= 3


def test_legacy_not_suspected_when_tests_exist(tmp_path):
    init_git(tmp_path)
    for i in range(10):
        write(tmp_path, f"module_{i}.py", f"def f_{i}():\n    return {i}\n")
        commit_all(tmp_path, f"feat: modul {i}")
    write(tmp_path, "tests/test_module_0.py", "def test_f_0():\n    assert True\n")
    commit_all(tmp_path, "test: modul 0 abgedeckt")
    result = detect_stack.classify(tmp_path)
    assert result["legacy"]["suspected"] is False
    assert result["tests_found"] is True


def test_legacy_not_suspected_for_small_fresh_repo(tmp_path):
    init_git(tmp_path)
    write(tmp_path, "a.py", "x = 1\n")
    commit_all(tmp_path, "feat: initial")
    result = detect_stack.classify(tmp_path)
    assert result["legacy"]["suspected"] is False


def test_test_file_variants_are_recognized(tmp_path):
    """Prüftabelle für die Test-Datei-Erkennung — verschiedene Sprachen und
    Konventionen, keine falschen Positiv-/Negativtreffer."""
    for relpath in (
        "tests/foo.py",
        "test_bar.py",
        "baz_test.py",
        "src/util.test.ts",
        "src/util.spec.js",
        "pkg/FooTest.java",
    ):
        assert detect_stack.TEST_FILE_RE.search(relpath), relpath
    for relpath in ("src/attest.py", "src/protest.js", "contests.py"):
        assert not detect_stack.TEST_FILE_RE.search(relpath), relpath


# ---------------------------------------------------------------------------
# Ausgabedatei und main()
# ---------------------------------------------------------------------------


def test_main_writes_cache_file_with_meta_header(tmp_path, monkeypatch):
    write(tmp_path, "manifest.json", json.dumps({"manifest_version": 3}))
    monkeypatch.chdir(tmp_path)
    rc = detect_stack.main(["--repo", "."])
    assert rc == 0
    written = json.loads((tmp_path / ".skills" / "cache" / "detect_stack.json").read_text(encoding="utf-8"))
    assert written["_meta"]["skill"] == "testing-strategy"
    assert written["_meta"]["schema"] == 1
    assert written["primary"] == "chrome-extension"


def test_main_rejects_missing_repo_path(tmp_path, capsys):
    rc = detect_stack.main(["--repo", str(tmp_path / "does-not-exist")])
    assert rc != 0
    assert "Klassifikation gescheitert" in capsys.readouterr().err


def test_classify_reclassifies_every_call_ignores_stale_cache(tmp_path):
    """R5: der Cache ist reine Ephemera. Ein alter, falscher Cache-Inhalt darf
    das Ergebnis des nächsten Aufrufs nicht beeinflussen."""
    cache = tmp_path / ".skills" / "cache" / "detect_stack.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"primary": "rest-api", "ambiguous": False, "candidates": []}), encoding="utf-8")
    write(tmp_path, "manifest.json", json.dumps({"manifest_version": 3}))
    result = detect_stack.classify(tmp_path)
    assert result["primary"] == "chrome-extension"
