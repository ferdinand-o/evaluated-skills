# Reviewer-Prompt für eine Spec vor dem Plan

Der Reviewer ist ein Subagent mit frischem Kontext; er bekommt die Spec, Spec 00, die in
der Abgrenzung genannten Nachbar-Skills und den Harness — nie die Konversation, in der
die Spec entstand. Dispatch **vor** `impl-plan`: Was hier gefunden wird, kostet eine
Überarbeitung; was erst der Bau findet, kostet eine Fix-Runde. Die drei bisher so
geprüften Specs (15, 16, 17) brauchten je 119 bis 217 Diff-Zeilen — überwiegend
Behauptungen über das Repo, die niemand geöffnet hatte, und Evals, die der Harness so
nicht fahren kann. Der Selbst-Review von `brainstorming` fängt beides nicht: Derselbe
Kontext, der die Zahl erfunden hat, liest sie wohlwollend.

```
Subagent (general-purpose, frischer Kontext):
  description: "Spec reviewen"
  prompt: |
    Du reviewst eine Spec, bevor daraus ein Plan wird. Deine Aufgabe ist nicht, sie
    umzuschreiben oder zu loben, sondern jede tragende Behauptung nachzumessen und
    die Evals auf Fahrbarkeit zu prüfen. Lies alles selbst; glaube keiner Zusammenfassung.

    **Spec:** <SPEC_PFAD>
    **Grundlage:** specs/Spec 00 – skill-foundation.md (§2 Eval-Vertrag, §3 Tiers, §4 Gate-Sprache, §5 Routing)
    **Nachbarn:** skills/<name>/SKILL.md jeder in der Abgrenzung genannten Skill, dazu ihr Abschnitt in docs/known-limits.md
    **Harness:** evalkit/schema.py (welche Assertion-Typen es gibt), evalkit/workspace.py (was `prepare()` in einen Eval-Workspace kopiert — nur Skill-Ordner und Fixture)
    **Vorbild:** die Commit-Bodies d6d456e und f1b2b6d zeigen, wie Funde und Ablehnungen protokolliert werden

    ## Was zu prüfen ist

    | Kategorie | Worauf achten |
    | --- | --- |
    | Fakten über das Repo | Jede Aussage über eine Datei, eine Zahl, einen Nachbarn, eine Harness-Fähigkeit: öffnen, zählen, laufen lassen. „Die id-Spalte gibt es ab Spec 11" ist eine Messung, keine Meinung — miss sie |
    | Zitate | Jedes Zitat aus einer Nachbar-SKILL.md, aus Spec 00 oder aus einer Fremd-Skill wörtlich vergleichen; ein sinngemäß wiedergegebener Satz in Anführungszeichen ist ein Befund |
    | Zahlen ohne Quelle | Jede Zahl, die weder aus einer Messung noch aus einer Nutzerangabe stammt, ist erfunden — Befund, auch wenn sie plausibel ist |
    | Evals fahrbar | Je Eval ein Prompt (kein Vergleich zweier Läufe); jeder Assertion-Typ existiert in `evalkit`; das Artefakt, an das die Assertion bindet, entsteht im Workspace — Skripte anderer Skills sind dort nicht vorhanden; kein Eval verlangt, was die Eiserne Regel verbietet; die Diskriminator-Frage ist je Eval beantwortet, nicht nur gestellt; ein Eval trägt das Präfix `anti-ceremony-` |
    | Spec-00-Konsistenz | Tier gegen den tatsächlichen Skriptaufruf (eine Eiserne Regel mit Skript ist nie Tier 0); G1/G2/G3 gegen den Mechanismus (ein pytest-Test ist G2, nur ein Hook ist G3, „blockiert" nur mit `assets/hooks/`); Ablage nach §1; Abgrenzung gegen zwei genannte Konkurrenten, die ihrerseits existieren |
    | Innere Widersprüche | Anti-Rationalisierungs-Tabelle gegen Open questions, Contract gegen Eval-Tabelle, Aufrufsyntax gegen Zielsystem, Constraints gegen Approach |
    | Stille Entscheidungen | Was als entschieden dasteht, ohne dass jemand es entschieden hat — gehört als `Annahme:`-Zeile oder in Open questions, nicht in den Approach |
    | Schnittstellen | Jede Datei, die ein Nachbar liest oder schreibt: Pfad und Form in beiden Specs gleich? Nennt der Nachbar diese Skill zurück, oder muss er es nach dem Bau? |

    ## Kalibrierung

    **Blockierend** ist, was den Plan oder einen Eval strukturell falsch machen würde
    (ein Eval, der nie grün werden kann; ein Tier, das nicht stimmt; eine Zahl, auf der
    der Zuschnitt steht). **Wichtig** ist, was die Argumentation schwächt, ohne den
    Zuschnitt zu ändern. Stil und Wortwahl sind keine Befunde. Jeder Befund braucht
    einen Beleg, den du selbst geprüft hast (Kommando und Messwert, oder Datei:Zeile).
    Was du nicht messen konntest, kennzeichne als solches statt es als Befund zu führen.

    ## Ausgabeformat

    ## Review <Spec>

    **Blockierend:** je Punkt: Befund — Beleg (Kommando + Messwert) — was im Plan
    daran hinge
    **Wichtig:** dito, kürzer
    **Nachgemessen und bestätigt:** Liste der geprüften Zahlen und Zitate, Kurzform
    **Nicht geprüft:** was du nicht messen konntest und warum
    **Gesamturteil:** zwei Sätze

    Nichts ändern, nur berichten. Kein Commit, kein Push.
```

**Danach:** Die tragenden Befunde selbst nachmessen, bevor sie eingearbeitet werden — ein
Reviewer mit frischem Kontext irrt sich anders als der Schreibende, nicht seltener; bei
Spec 16 stimmten alle fünf strukturellen Behauptungen des Reviewers, bei Spec 15 wurde
ein Fund begründet abgelehnt. Dann die Spec überarbeiten, in der Kopfzeile
„Überarbeitet nach unabhängigem Review" ergänzen und im Commit-Body festhalten, was
blockierend war, was behoben wurde und was mit welchem Grund abgelehnt wurde. Der
Vermerk ist der Token, an dem später ein Lint erkennt, dass der Schritt stattfand.

Ein zweiter Durchlauf nur, wenn ein Befund den Zuschnitt geändert hat. Eine Spec, die
um eine Entscheidung wächst (ein Satz aus Open questions wird Festlegung), braucht
keinen neuen Review — das ist der Anti-Zeremonie-Fall; die Eval-Tabelle ist die
Ausnahme, jede Änderung dort ist reviewpflichtig.
