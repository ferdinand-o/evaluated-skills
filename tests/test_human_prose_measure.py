"""Tests für skills/human-prose/scripts/measure.py (Spec 19).

Die sechs Beispieltexte stammen wörtlich aus Abschnitt 9 des Entwurfs
docs/superpowers/specs/2026-09-15-menschlich-schreiben-v0.1.md. Erwartungswerte sind
dort nachgemessen (Plan 2026-09-15-human-prose, Task 1 und 2); wo eine Heuristik einen
Nachher-Text rot zählt, steht das als Kommentar am Test, nicht als aufgeweichte Regel.
"""

from conftest import load_script

m = load_script("skills/human-prose/scripts/measure.py")

B1_VORHER = (
    "In der heutigen Softwareentwicklung spielt Caching eine entscheidende Rolle. Es ist "
    "wichtig zu beachten, dass ein gut konfigurierter Cache nicht nur die Latenz reduziert, "
    "sondern auch die Last auf der Datenbank senkt, wodurch sich die Gesamtperformance des "
    "Systems deutlich verbessert. Darüber hinaus gibt es verschiedene Strategien, die je nach "
    "Anwendungsfall ausgewählt werden sollten. Zusammenfassend lässt sich sagen, dass Caching "
    "ein mächtiges Werkzeug ist."
)
B1_NACHHER = (
    "Ein Cache nimmt der Datenbank Arbeit ab. Bei uns fällt die Latenz von 400 auf 60 "
    "Millisekunden, und die Zahl der Queries sinkt um etwa zwei Drittel.\n\n"
    "Welche Strategie passt, hängt davon ab, wie oft sich die Daten ändern. Für Stammdaten "
    "reicht ein TTL von einer Stunde. Für Preise nicht."
)
B2_VORHER = (
    "When it comes to error handling, it is important to note that a robust strategy is "
    "pivotal for maintaining system reliability — ensuring that failures are caught early, "
    "logged appropriately, and surfaced to the right people."
)
B2_NACHHER = (
    "Error handling breaks in a predictable way: the failure happens in one place and shows "
    "up in another. Catch it where it happens. Log enough context that the next person can "
    "reconstruct the call, and route the alert to whoever can actually fix it."
)
B3_VORHER = (
    "Hallo zusammen, ich hoffe, es geht euch gut. Ich wollte mich kurz melden bezüglich des "
    "Deployments von gestern Abend. Leider ist es zu einigen unerwarteten Problemen gekommen, "
    "die dazu geführt haben, dass der Service für eine gewisse Zeit nicht verfügbar war. Wir "
    "arbeiten mit Hochdruck an einer Lösung. Ich hoffe, das hilft."
)
B3_NACHHER = (
    "Das Deployment gestern hat den Service von 21:40 bis 22:15 lahmgelegt. Ursache war eine "
    "Migration, die auf der Prod-Datenbank länger lief als im Test.\n\n"
    "Läuft wieder. Rollback-Plan steht für heute Abend, falls es nochmal kippt."
)
EXAMPLES = {
    "b1v": B1_VORHER, "b2v": B2_VORHER, "b3v": B3_VORHER,
    "b1n": B1_NACHHER, "b2n": B2_NACHHER, "b3n": B3_NACHHER,
}


# --- Task 1: Textmodell ---------------------------------------------------------------

def test_sentence_counts_of_the_six_examples():
    assert [len(m.sentences(EXAMPLES[k])) for k in ("b1v", "b2v", "b3v")] == [4, 1, 5]
    assert [len(m.sentences(EXAMPLES[k])) for k in ("b1n", "b2n", "b3n")] == [5, 3, 4]


def test_paragraph_counts_of_the_six_examples():
    assert [len(m.paragraphs(EXAMPLES[k])) for k in ("b1v", "b2v", "b3v")] == [1, 1, 1]
    assert [len(m.paragraphs(EXAMPLES[k])) for k in ("b1n", "b2n", "b3n")] == [2, 1, 2]


def test_word_counts_match_str_split():
    assert [len(m.words(EXAMPLES[k])) for k in ("b1v", "b2v", "b3v")] == [63, 36, 52]
    assert [len(m.words(EXAMPLES[k])) for k in ("b1n", "b2n", "b3n")] == [50, 44, 35]


def test_abbreviations_and_numbers_do_not_split_sentences():
    assert len(m.sentences("Wir nehmen z. B. Postgres. Das reicht.")) == 2
    assert len(m.sentences("Version 3.5 lief bzw. läuft um 21:40 Uhr. Danach nicht mehr.")) == 2
    assert len(m.sentences("See e.g. the log. Then i.e. restart.")) == 2


def test_strip_markup_removes_code_quotes_and_heading_marks():
    text = (
        "# Titel\n\nEin Satz mit `code` drin.\n\n```\nprint('x — y')\n```\n\n"
        "> Zitat — bleibt draußen.\n> Zweite Zeile.\n\nLetzter Satz."
    )
    stripped, method = m.strip_markup(text)
    assert "print" not in stripped and "Zitat" not in stripped and "#" not in stripped
    assert "`" not in stripped and "code" not in stripped
    assert method["quoted_lines_skipped"] == 2
    assert method["fenced_blocks_skipped"] == 1
    assert len(m.sentences(text)) == 2


def test_list_items_count_as_one_sentence_each():
    text = "Drei Punkte:\n\n- erstens\n- zweitens, ohne Punkt\n- drittens\n"
    sents = m.sentences(text)
    assert len(sents) == 4  # der Einleitungssatz plus drei Punkte
    assert len(m.paragraphs(text)) == 2


# --- Task 2: die vierzehn Prüfpunkte ---------------------------------------------------

def _check(text, rule, register="fach"):
    found = [c for c in m.check_all(text, register) if c.id == rule]
    assert len(found) == 1, rule
    return found[0]


def test_check_ids_in_spec_order():
    ids = [c.id for c in m.check_all(B1_NACHHER, "fach")]
    assert ids == ["R1.1", "R4.1/R4.2", "R4.3", "R2.1", "R2.2", "R3.5", "R5.1", "R5.2",
                   "R3.3", "R4.4", "R1.4", "R4.5", "R4.6", "R2.4"]
    assert [j["id"] for j in m.judgement()] == ["R3.1", "R5.3", "R5.4", "R2.3-2", "R5.2"]


def test_r11_characters():
    assert _check(B2_VORHER, "R1.1").status == "finding"      # ein Geviertstrich
    assert _check(B2_VORHER, "R1.1").value == 1
    for key in ("b1n", "b2n", "b3n"):
        assert _check(EXAMPLES[key], "R1.1").status == "pass", key
    assert _check("Ein Satz – mit Gedankenstrich; und Semikolon.", "R1.1").value == 2
    assert _check("Ein KI-Text mit Bindestrich und `a — b` im Code.", "R1.1").status == "pass"


def test_r41_r42_phrases_are_patterns_with_gaps():
    c = _check(B1_VORHER, "R4.1/R4.2")
    assert c.status == "finding" and c.value == 3, c.reason
    assert _check(B2_VORHER, "R4.1/R4.2").value == 4
    for key in ("b1n", "b2n", "b3n"):
        assert _check(EXAMPLES[key], "R4.1/R4.2").value == 0, key
    assert m.PHRASES_DE and m.PHRASES_EN


def test_r43_participle_tail_allows_comma_or_dash():
    assert _check(B1_VORHER, "R4.3").value == 1      # ", wodurch"
    assert _check(B2_VORHER, "R4.3").value == 1      # "— ensuring"
    assert _check(B1_VORHER, "R4.3").status == "pass"  # höchstens eines je 300 Wörter: eines ist erlaubt
    two = "Der Cache hilft, wodurch alles schneller wird. Er spart Zeit, was es ermöglicht, mehr zu tun."
    assert _check(two, "R4.3").status == "finding"


def test_r21_spread_windows_and_short_texts():
    assert _check(B1_VORHER, "R2.1").status == "finding"      # kein Satz mit höchstens sechs Wörtern
    assert "sechs" in _check(B1_VORHER, "R2.1").reason
    assert _check(B3_VORHER, "R2.1").status == "pass"
    assert _check(B2_VORHER, "R2.1").status == "unchecked"    # ein Satz
    assert _check(B2_NACHHER, "R2.1").status == "unchecked"   # drei Sätze
    assert _check(B1_NACHHER, "R2.1").status == "pass"
    # Beispiel 3 Nachher: kein Satz mit zwanzig Wörtern. Die Regel ist für Register
    # `kurz` zu streng — der Wert bleibt so im Test und im Report, nicht aufgeweicht.
    assert _check(B3_NACHHER, "R2.1", "kurz").status == "finding"
    assert "zwanzig" in _check(B3_NACHHER, "R2.1", "kurz").reason


def test_r22_connector_only_at_paragraph_start():
    for key, text in EXAMPLES.items():
        assert _check(text, "R2.2").status == "pass", key   # „Darüber hinaus" steht im Absatzinneren
    assert _check("Erster Absatz.\n\nDarüber hinaus gibt es mehr.", "R2.2").status == "finding"
    assert _check("Erster Absatz.\n\nMoreover, there is more.", "R2.2").status == "finding"


def test_r35_frame_phrases():
    assert _check(B1_VORHER, "R3.5").status == "finding"    # „Zusammenfassend lässt sich sagen"
    assert _check(B3_VORHER, "R3.5").status == "pass"       # „Ich hoffe, das hilft" ist R6, kein R3.5-Muster
    assert _check("In diesem Artikel zeigen wir X.\n\nX ist gut.", "R3.5").status == "finding"
    assert _check("X ist gut.\n\nFazit: X bleibt.", "R3.5").status == "finding"


def test_r51_concreteness_heuristic():
    assert _check(B1_VORHER, "R5.1").status == "finding"
    assert _check(B1_NACHHER, "R5.1").status == "pass"      # Ziffern, TTL
    # Beispiel 3 Nachher: zwei Absätze mit je zwei Sätzen — kein Behauptungsabsatz ab
    # drei Sätzen, also nichts zu prüfen. Ehrlicher als ein pass, das 21:40 gutschreibt.
    assert _check(B3_NACHHER, "R5.1").status == "unchecked"
    # Beispiel 2 Nachher: kein Ziffer, kein Pfad, kein Großwort — die Heuristik zählt den
    # guten Text rot. Bleibt so, der Report nennt es.
    assert _check(B2_NACHHER, "R5.1").status == "finding"
    assert _check("Wir nutzen PostgreSQL. Es läuft. Es bleibt so.", "R5.1").status == "pass"
    assert _check("Siehe `config.yml`. Dort steht es. Ganz unten.", "R5.1").status == "pass"


def test_r52_is_always_unchecked():
    for text in EXAMPLES.values():
        assert _check(text, "R5.2").status == "unchecked"


def test_r33_triads():
    three_of_four = (
        "Wir brauchen Zeit, Geld und Leute. Der Plan hat Anfang, Mitte und Ende. "
        "Es gibt Rot, Grün und Blau. Und dazu Nord, Süd, Ost und West."
    )
    c = _check(three_of_four, "R3.3")
    assert c.status == "finding" and c.value == 3
    assert _check(B2_VORHER, "R3.3").status == "pass"       # eine Aufzählung ist kein Muster
    assert _check("- a\n- b\n- c\n\nText.\n\n- d\n- e\n", "R3.3").value == 1


def test_r44_nominal_style():
    heavy = " ".join(["Die Durchführung der Prüfung und die Bewertung der Planung."] * 5 + ["Wort"] * 150)
    assert _check(heavy, "R4.4").status == "finding"
    assert _check(B1_VORHER, "R4.4").status == "pass"       # eines auf 63 Wörter: ein Treffer ist kein Muster
    assert _check(B1_VORHER, "R4.4").value == 1


def test_r14_parentheses_colons_exclamation():
    assert _check("Der Job (nachts) läuft (meistens) gut (sagt man).", "R1.4").status == "finding"
    assert _check(B2_NACHHER, "R1.4").status == "pass"      # ein Doppelpunkt auf 44 Wörter
    assert _check("Das ist toll! Wirklich!", "R1.4", "fach").status == "finding"
    assert _check("Das ist toll!", "R1.4", "kurz").status == "pass"
    listed = "Drei Dinge:\n\n- a\n- b\n- c\n"
    assert _check(listed, "R1.4").value["colons"] == 0     # Doppelpunkt vor Liste zählt nicht


def test_r45_passive_share():
    passive = "Der Text wurde geschrieben. Die Zahl wird geprüft. Alles wird gemacht. Es ist gut."
    assert _check(passive, "R4.5").status == "finding"
    assert _check(B1_NACHHER, "R4.5").status == "pass"
    assert _check("The report was written by the team. It is short.", "R4.5").status == "finding"


def test_r46_hedges():
    hedged = "Das könnte gehen. Möglicherweise nicht. Unter Umständen doch. Tendenziell ja. In der Regel nein."
    assert _check(hedged, "R4.6").status == "finding"
    assert _check(B1_NACHHER, "R4.6").status == "pass"


def test_r24_fragments():
    assert _check(B1_NACHHER, "R2.4").value == 1            # „Für Preise nicht."
    assert _check(B1_NACHHER, "R2.4").status == "pass"      # eines ist erlaubt
    many = "Nicht ideal. Kurz gesagt. Also nein. Und dann weiter im Text mit ganzen Sätzen, die reichen."
    assert _check(many, "R2.4", "fach").status == "finding"
    assert _check(many, "R2.4", "kurz").status == "pass"    # frei in der Kurzform


def test_every_check_names_an_estimated_limit():
    for c in m.check_all(B1_VORHER, "fach"):
        if c.status != "unchecked":
            assert c.limit is not None, c.id
            assert c.estimated is False or "geschätzt" in c.reason, c.id
