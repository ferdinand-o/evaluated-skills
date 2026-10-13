"""Strukturprüfung der explain-evals.json. Läuft keine Evals — kein Agentenlauf,
keine claude-CLI-Aufrufe.

Für eine Tier-0-Skill ist das der **einzige** mechanische Regressionsschutz, den
es überhaupt geben kann: Es gibt keinen Anwendungscode, den Unit-Tests prüfen
könnten. Die Tests hier fangen deshalb den einen Fehler, der die Skill
lautlos entwerten würde — dass jemand den Wortlaut eines der drei Tokens in der
Doktrin ändert, ohne die Evals mitzuziehen. Danach wären alle Evals weiter grün
und prüften nichts mehr.
"""

import re
from pathlib import Path

from evalkit.schema import load_evals

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALS_PATH = REPO_ROOT / "evals" / "explain" / "evals.json"
SKILL_DIR = REPO_ROOT / "skills" / "explain"

# Die drei wörtlichen Tokens aus SKILL.md. Sie sind zugleich das einzige Merkmal,
# an dem ein Eval die Skill von einer guten Antwort ohne Skill unterscheiden kann.
TOKENS = ("Unverified:", "Source:", "Next:")


def _assertion_patterns(evals) -> list[str]:
    patterns = []
    for ev in evals:
        for assertion in list(ev.must) + list(ev.must_not):
            if assertion.type == "output_matches":
                patterns.append(assertion.pattern)
    return patterns


def test_evals_file_loads_without_schema_error():
    assert len(load_evals(EVALS_PATH)) == 8


def test_anti_ceremony_eval_exists():
    """Spec 00 §2 Pflicht: mindestens ein Anti-Zeremonie-Eval."""
    evals = load_evals(EVALS_PATH)
    assert any("anti-ceremony" in ev.id for ev in evals)


def test_anti_ceremony_eval_hangs_on_a_skill_owned_token():
    """Der Pflicht-Eval darf nicht allein auf generischer Kürze beruhen.

    Kürze könnte das Basismodell ohne die Skill auch — und `docs/known-limits.md`
    verlangt, dass Assertions an Artefakten hängen, die *nur* die getestete Skill
    erzeugt. Für eine dateilose Skill ist das die Abwesenheit von `Next:` bei `low`.
    """
    evals = load_evals(EVALS_PATH)
    anti = next(ev for ev in evals if "anti-ceremony" in ev.id)
    negated = [a.pattern for a in anti.must_not if a.type == "output_matches"]
    assert any("Next:" in p for p in negated)


def test_every_token_is_asserted_somewhere():
    """Jeder der drei Tokens wird von mindestens einem Eval mechanisch geprüft.

    Fällt einer heraus, ist er ab da nur noch Doktrin ohne Messung.
    """
    patterns = _assertion_patterns(load_evals(EVALS_PATH))
    for token in TOKENS:
        assert any(token in p for p in patterns), f"kein Eval prüft {token!r}"


def test_asserted_tokens_match_the_doctrine_verbatim():
    """Die Verdrahtung: Was die Evals prüfen, muss in der Doktrin so dastehen.

    Das ist der Test, der eine stille Umbenennung fängt. Ein reiner Test der
    evals.json gegen sich selbst wäre Dekoration — er bliebe grün, während
    SKILL.md längst ein anderes Wort mandatiert.
    """
    doctrine = "\n".join(
        p.read_text(encoding="utf-8")
        for p in [SKILL_DIR / "SKILL.md", *sorted((SKILL_DIR / "references").glob("*.md"))]
    )
    for token in TOKENS:
        assert token in doctrine, f"{token!r} steht in keiner Doktrin-Datei mehr"


def test_no_contract_eval_relies_on_a_judge():
    """Spec 00 §2: contract-Evals sind mechanisch. Das Schema erzwingt es bereits —
    dieser Test hält es fest, damit eine Schema-Lockerung hier auffällt."""
    for ev in load_evals(EVALS_PATH):
        if ev.eval_class == "contract":
            assert all(a.type != "judge" for a in list(ev.must) + list(ev.must_not))


def test_every_eval_has_at_most_one_judge_claim():
    """Zusammengesetzte Judge-Claims sind im Repo nachweislich unzuverlässig
    (docs/known-limits.md, Abschnitt „Judge"). Ein Claim pro Eval."""
    for ev in load_evals(EVALS_PATH):
        judges = [a for a in list(ev.must) + list(ev.must_not) if a.type == "judge"]
        assert len(judges) <= 1, f"{ev.id} hat {len(judges)} Judge-Claims"


def test_every_eval_answers_the_discriminator_question():
    """Jeder Eval begründet in `notes`, warum ihn das Basismodell ohne die Skill
    nicht bestünde — die Regel aus docs/known-limits.md gegen Falsch-Grün."""
    for ev in load_evals(EVALS_PATH):
        assert re.search(r"(?i)diskriminator|basismodell", ev.notes or ""), ev.id
