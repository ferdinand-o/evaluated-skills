# Reviewer-Prompt für einen fertigen Plan

Aus `superpowers:writing-plans` übersetzt und um die Pflichtinhalte dieser Sammlung
ergänzt. Der Reviewer ist ein Subagent mit frischem Kontext; er bekommt Plan und Spec,
nie die Konversation. Dispatch **nach** dem Lint, nicht statt dessen — der Reviewer
prüft Zuschnitt und Vollständigkeit, der Lint prüft Form.

```
Subagent (general-purpose):
  description: "Plan reviewen"
  prompt: |
    Du reviewst einen Implementierungsplan darauf, ob er vollständig ist und ob ein
    Builder ihn ausführen kann, ohne stecken zu bleiben.

    **Plan:** <PLAN_PFAD>
    **Spec:** <SPEC_PFAD>
    **Lint-Ergebnis:** <LINT_JSON_PFAD oder „nicht gelaufen — Plan gilt als ungeprüft">

    ## Was zu prüfen ist

    | Kategorie | Worauf achten |
    | --- | --- |
    | Vollständigkeit | Platzhalter, unvollständige Tasks, Steps ohne beobachtbares Ergebnis |
    | Spec-Abgleich | Jede Eval-ID der Spec-Tabelle hat einen Task; kein Task baut, was die Spec ausschließt |
    | Zuschnitt | Klare Grenzen; ein Reviewer könnte eine Task ablehnen und die Nachbar-Task annehmen |
    | Pflichtinhalte | `### Task N: Evals`, `Nachbarn`, `known-limits`, `Report` vorhanden — oder der Sammel-Task `Pflicht` im Anti-Zeremonie-Fall |
    | Reihenfolge | Bei einer Tier-0-Skill steht der Eval-Task vor dem SKILL.md-Task |
    | Baubarkeit | Kann ein Builder, der nur seine eigene Task sieht, sie ausführen? Kennt er jedes Symbol in `Consumes:` aus einem `Produces:`? |

    ## Kalibrierung

    **Melde nur, was beim Bau zu einem echten Problem führt.** Ein Builder, der das
    Falsche baut oder stecken bleibt, ist ein Befund. Wortwahl, Stil und „wäre schön"
    sind keine.

    Gib den Plan frei, außer es gibt ernste Lücken: fehlende Spec-Anforderungen,
    widersprüchliche Steps, Platzhalter, oder Tasks, die so vage sind, dass man sie
    nicht ausführen kann.

    ## Ausgabeformat

    ## Plan-Review

    **Status:** Freigegeben | Befunde

    **Befunde (falls vorhanden):**
    - [Task X, Step Y]: [konkreter Befund] — [warum das den Bau betrifft]

    **Empfehlungen (beratend, blockieren die Freigabe nicht):**
    - [Vorschlag]
```

**Der Reviewer liefert:** Status, Befunde, Empfehlungen. Befunde werden im Plan
behoben, danach erneut `lint`; ein zweiter Review-Durchlauf nur, wenn ein Befund den
Zuschnitt geändert hat.

Was der Reviewer **nicht** ersetzt: den Lint (Form ist mechanisch, nicht
Ermessenssache) und den Repo-Test (der läuft ohne Zutun). Der Reviewer sieht, was
beide nicht sehen — ob die Tasks das Richtige bauen und ob man sie bauen kann.
