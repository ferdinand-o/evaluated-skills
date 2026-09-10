# Reviewer-Prompt für einen fertigen Skill-Bau

Der Reviewer ist ein Subagent mit frischem Kontext; er bekommt Spec, Plan, den
Skill-Ordner und die `lint.json` — nie die Konversation. Dispatch **nach** dem Lint,
nicht statt dessen: Der Lint prüft dreizehn Regeln mechanisch, der Reviewer prüft die
sechs Ermessenspunkte aus `checklist.md` und misst nach, was der Bauende behauptet.
Kalibrierung und Format sind die aus `impl-plan/references/reviewer-prompt.md`; die
Kategorien sind die des Skill-Baus.

```
Subagent (general-purpose, frischer Kontext):
  description: "Skill-Bau reviewen"
  prompt: |
    Du reviewst den fertigen Bau einer Skill darauf, ob er seine Spec einlöst und ob
    das, was er über sich sagt, stimmt. Lies alles selbst; glaube keiner
    Zusammenfassung.

    **Spec:** <SPEC_PFAD>
    **Plan:** <PLAN_PFAD>
    **Skill-Ordner:** <SKILL_PFAD>  (SKILL.md, references/, assets/, scripts/)
    **Evals:** evals/<name>/evals.json, evals/fixtures/<…>/
    **Lint:** <LINT_JSON_PFAD oder „nicht gelaufen — Skill gilt als ungeprüft">
    **Report:** docs/superpowers/reports/<name>-report.md, Abschnitt in docs/known-limits.md

    ## Was zu prüfen ist

    | Kategorie | Worauf achten |
    | --- | --- |
    | Spec-Abgleich | Jede Zusage der Spec (Contract, Eval-Tabelle, Abgrenzung, Tier) hat eine Stelle im Bau; nichts wurde gebaut, was die Spec ausschließt |
    | Diskriminator je Eval | Könnte das Basismodell ohne die Skill dieselbe Assertion bestehen? `notes` muss das beantworten — prüf die Antwort, nicht ihr Vorhandensein. Falsch-Rot: reißt ein doktrintreuer Lauf eine Assertion? |
    | Gate-Ehrlichkeit | Jeder Satz im Contract, der „verlangt", „meldet" oder „blockiert" sagt: Welcher Mechanismus steht dahinter? Wo meldet etwas Erfolg, ohne geprüft zu haben (`all([])`, `pass` statt `unchecked`, übersprungene Gates)? |
    | Beispiele gegen Regeln | Jedes Beispiel in SKILL.md, References und Template gegen die Regel prüfen, unter der es steht |
    | Schnittstellen | Jede Datei, die ein Nachbar liest oder schreibt: Pfad und Form in beiden Skills gleich? Nennen die Nachbarn zurück? |
    | Zahlen | Jede Zahl im Report und in known-limits nachmessen (Tests, Zeilen, Befunde, Evals). Eine Zahl, die nicht stimmt, ist ein Befund |
    | Lint-Lücken | Wo sagt `lint.json` `unchecked` oder `hint` — und hat der Bauende das gesehen, oder als grün gelesen? |

    ## Kalibrierung

    **Melde nur, was beim Einsatz zu einem echten Problem führt, eine Spec-Zusage bricht
    oder eine falsche Zahl ist.** Stil, Wortwahl und „wäre schön" sind keine Befunde.
    Jeder Befund braucht einen Beleg, den du selbst geprüft hast (Datei:Zeile, eigener
    Lauf). Was du nicht verifizieren konntest, kennzeichne als solches statt es als
    Befund zu führen.

    ## Ausgabeformat

    ## Review <name>

    **Status:** Freigegeben | Befunde

    **Befunde:**
    - [hoch|mittel|niedrig] Datei:Zeile — Befund — Beleg — Warum es beim Einsatz zählt

    **Nachgemessen:** je Zahl aus Report/known-limits: stimmt | falsch (dein Wert)

    **Verifiziert (ohne Befund):** kurze Liste

    **Empfehlungen (beratend, blockieren die Freigabe nicht):** höchstens fünf

    Nichts ändern, nur berichten. Kein Commit, kein Push.
```

**Danach:** Befunde in einer Fix-Runde beheben, jede Fix-Runde endet mit dem Lint
(`--base` auf den Stand vor der Runde). Die tragenden Befunde des Reviewers selbst
nachmessen, bevor sie weitergegeben werden — ein Reviewer mit frischem Kontext
irrt sich anders als der Bauende, nicht seltener. Ein zweiter Review-Durchlauf nur,
wenn ein Befund den Zuschnitt geändert hat; zwei Runden waren bei Spec 16 nötig,
beide fanden Echtes.

Was der Reviewer **nicht** ersetzt: den Lint (Form ist mechanisch), den zweiten
Eval-Lauf (ein Ergebnis ist eine Stichprobe) und den Repo-Test (der läuft ohne Zutun).
