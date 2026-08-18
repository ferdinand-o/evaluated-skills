# Quellenbindung: Referenzmarken-Konvention

Der Contract aus `SKILL.md` — keine Zahl und kein Chart ohne Quellenreferenz —
braucht eine konkrete, in beiden Medien gleich lesbare Mechanik. Das ist sie.

## Die Marke

Jede Zahl (Prozent, Betrag, Anzahl, Datum als Beleg für eine Behauptung) und
jeder Chart-Datenpunkt trägt **unmittelbar im Anschluss** eine Marke: eine Zahl
in eckigen Klammern.

- **Markdown** nutzt dafür die native Fußnotensyntax: `Die Rate lag bei 91 %[^1]`
  im Fließtext, am Dokumentende:
  ```
  [^1]: S. 23, Quartalsbericht — "Kundenbindungsrate erreichte 91 %"
  ```
- **HTML** nutzt einen verlinkten Anker: `Die Rate lag bei 91 % [<a href="#ref-1">1</a>]`,
  am Dokumentende in der Quellenliste:
  ```html
  <li id="ref-1">S. 23, Quartalsbericht — „Kundenbindungsrate erreichte 91 %"</li>
  ```

Gleiche visuelle Grammatik (Zahl in Klammern), zwei Mechaniken — passend zu
„gleiches Modell, zwei Renderer" aus `SKILL.md`.

**Eine Zahl ohne unmittelbar folgende Marke gehört nicht in den Output.** Auch
nicht als eigener, unmarkierter Absatz, auch nicht als Fußnote ohne
Klammer-Anschluss im Fließtext — die Marke sitzt direkt an der Zahl, nicht in
der Nähe.

## Locator je Input-Art

| Input-Art | Locator-Form | Beispiel |
| --- | --- | --- |
| Dokument/PDF/Artikel | Seite oder Abschnitt | `S. 23`, `§3.2` |
| Chat-/Arbeitsverlauf | Nachrichtennummer oder Zeitstempel | `Nachricht 19`, `14:32` |
| Code-/Projektstand | Commit-Hash (kurz) oder Datei:Zeile | `a1b2c3d`, `src/parser.py:42` |
| eigene Recherche (Zyklus 12) | Quelle/Link/Notiz-ID | `research/pricing.md#q3` |

Der Locator ist kein Kommentar zur Zahl, sondern die Fundstelle selbst — „laut
Dokument" ist kein Locator, `S. 23` ist einer.

## Konfidenz

Jeder Beleg im Inhaltsmodell trägt eine Konfidenz-Stufe, die in der Quellenliste
sichtbar wird, wenn sie unter „gesichert" liegt:

- **gesichert** — explizit im Material behauptet, keine Interpretation nötig.
- **abgeleitet** — aus mehreren Stellen zusammengesetzt oder eine naheliegende
  Folgerung; Marke trägt einen Zusatz: `[^2] (abgeleitet)`.
- **unsicher** — Material widerspricht sich oder ist mehrdeutig; Marke trägt
  `[^3] (unsicher — <Grund>)`. Eine unsichere Zahl fliegt nicht automatisch raus,
  aber sie wird nie stillschweigend wie eine gesicherte behandelt.

## Chat-Verlauf: übergeben, nicht erraten

Der Zugriff auf einen Chat-/Arbeitsverlauf ist umgebungsabhängig. Diese Skill
fordert ihn an (Dateipfad oder eingefügter Text) und arbeitet erst danach.
Sie rekonstruiert ihn nie aus der laufenden Session — eine geratene Historie
kann die falsche sein, ohne dass es auffällt, und das Destillat wäre dann über
das falsche Gespräch.
