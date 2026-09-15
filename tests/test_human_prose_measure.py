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
