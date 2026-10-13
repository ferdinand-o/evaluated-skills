"""Verdrahtungstest: dev-report/scripts/collect.py erwartet docs/debugging/INDEX.md
als Harvest-Quelle mit Kopfzeile schema 1 (siehe HARVEST_SOURCES in collect.py).
Reine Unit-Tests je Skript hätten eine Formatabweichung zwischen beiden nicht
gefangen — genau die Fehlerklasse, die brief-common.md als "Ungetestete
Verdrahtung" nennt."""

from conftest import load_script

new_ledger = load_script("skills/debug-ledger/scripts/new_ledger.py")
collect = load_script("skills/dev-report/scripts/collect.py")


def test_dev_report_harvest_reads_debug_ledger_index(tmp_path):
    target = new_ledger.action_new(
        tmp_path, symptom="Login hängt", repro="pytest", expected="ok", observed="hängt",
        slug="login", date_str="2026-08-16",
    )
    rel = target.relative_to(tmp_path).as_posix()
    new_ledger.action_resolve(tmp_path, rel, "Cache-Key kollidiert zwischen zwei Nutzern")

    entries = {e["path"]: e for e in collect.harvest(tmp_path)}
    entry = entries["docs/debugging/INDEX.md"]
    assert entry["status"] == "read"
    assert "Cache-Key kollidiert" in entry["excerpt"]


def test_dev_report_harvest_sees_bootstrap_index_before_resolve(tmp_path):
    """Auch ein noch leeres, gerade erst gebootstrapptes INDEX.md ist lesbar,
    nicht nur eines mit Einträgen."""
    new_ledger.action_new(
        tmp_path, symptom="Bug", repro="cmd", expected="a", observed="b",
        slug="bug", date_str="2026-08-16",
    )
    entries = {e["path"]: e for e in collect.harvest(tmp_path)}
    assert entries["docs/debugging/INDEX.md"]["status"] == "read"
