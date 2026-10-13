# Form nach Fehlerart — welche Doktrin-Form gegen welches Versagen

Übersetzt aus `superpowers:writing-skills` („Match the Form to the Failure"), ergänzt
um die Fälle aus `docs/skill-building-pitfalls.md`. Der Kern: **Erst das Versagen
klassifizieren, dann die Form wählen.** Die Form, die eine Fehlerart wasserdicht macht,
geht bei einer anderen messbar nach hinten los.

## Die vier Formen

| Beobachtetes Versagen (Baseline ohne Skill) | Richtige Form | Falsche Form |
| --- | --- | --- |
| Kennt die Regel, bricht sie unter Druck („nur dieses eine Mal", „das ist hier anders") | **Verbot** plus Anti-Rationalisierungs-Tabelle plus rote Flaggen — jede Ausflucht wörtlich benannt | Weiche Empfehlung („bevorzuge …", „erwäge …") |
| Befolgt die Regel, aber die Ausgabe hat die falsche Form (aufgebläht, Urteil vergraben, Spec nacherzählt) | **Rezept oder Contract**: sagen, was die Ausgabe *ist* — ihre Teile, in dieser Reihenfolge | Verbotsliste („nicht nacherzählen", „nie erzählen") |
| Lässt ein Pflichtelement weg in etwas, das sie ohnehin erzeugt | **Pflichtslot**: ein Feld oder eine Sektion im Template, das ausgefüllt werden muss — `## Was nicht gemessen wurde`, `_meta`, die Diskriminator-Notiz in `notes` | Prosa-Erinnerung neben dem Template |
| Das Verhalten soll von einer Bedingung abhängen | **Konditional an einem beobachtbaren Prädikat** („wenn `evals_due: true`, dann Evals"; „wenn `assets/hooks/` existiert, darf es ‚blockiert' heißen") | Unbedingte Regel plus Ausnahmeklauseln |

**Warum Verbote bei Formfehlern schaden:** Unter einem konkurrierenden Anreiz
(„mach die Prompt vollständig") verhandelt ein Agent mit „tu nicht X". In
Wortlaut-Tests gegeneinander erzeugte der Verbots-Arm deutlich *mehr* des unerwünschten
Inhalts als der Rezept-Arm — und tendenziell mehr als die Kontrolle ganz ohne Anleitung.
Ein Rezept lässt nichts zu verhandeln: Die Ausgabe hat die genannte Form, oder sie hat
sie nicht.

**Zwei Regeln für jede Form:**

- **Keine Nuance-Klauseln.** „Nicht X, außer es ist wichtig" öffnet die Verhandlung
  wieder. Eine einzige angehängte Nuance-Klausel hat in denselben Tests ein stabiles
  Rezept in ein verrauschtes verwandelt. Eine echte Ausnahme ist ein eigenes
  Konditional an einem beobachtbaren Prädikat.
- **Ausnahmeklauseln begrenzen nicht.** „Das Limit gilt nicht für Codeblöcke"
  unterdrückt trotzdem Codeblöcke. Muss ein Teil der Ausgabe ausgenommen sein, muss die
  Regel so gebaut werden, dass sie ihn gar nicht erreichen kann.

## Die Fälle aus dieser Sammlung

Jeder ist real aufgetreten; die Form, die geholfen hat, steht dabei.

| Fall | Versagen | Form, die trug |
| --- | --- | --- |
| Der Artefakt-Header wurde gebrochen, weil ein Beispiel zwei Abschnitte unter der Regel ihr widersprach | Pflichtelement, vom Beispiel überstimmt | Pflichtslot: die Kopfzeile ist die erste Zeile des Templates, nicht ein Satz daneben. **Beispiele schlagen Vorschriften** — jedes Beispiel gegen die Regel prüfen, unter der es steht |
| Ein `verify` meldete PASS ohne seine Eingabe; ein Drift-Check sagte „kein Drift", weil er nichts vergleichen konnte | Mechanismus meldet Erfolg, ohne geprüft zu haben | Konditional im Code, nicht in der Doktrin: `unchecked` ist ein eigener Status, `allowlist_checked: false` steht im Artefakt. Die Frage lautet immer: **Wo meldet etwas Erfolg, ohne geprüft zu haben?** |
| Eine verschärfte SKILL.md hielt gemessen nicht; erst der Mechanismus half | Regel unter Druck gebrochen, Appell wirkungslos | Wo etwas mechanisch prüfbar ist, gehört kein Appell hin — G2-Skript statt G1-Satz. Verbot plus Tabelle bleibt für das, was kein Skript sehen kann |
| Die Abgrenzungsklausel schloss den eigenen Pflichtfall mit aus (Anti-Zeremonie-Fall; ein Verbot, das legitime eigene Fragen mitverbot) | Konditional falsch geschnitten | Trigger positiv nennen, Abgrenzung als eigene Klausel dahinter — nie eine Abgrenzung, die das Kernszenario berührt |
| Ein Contract versprach „gilt nur bei valider Begründung als kaputt", der Mechanismus markierte jede Fehlwahl gleich | Contract hält mehr, als das Gate leistet | Contract auf das zurückziehen, was geleistet wird; die Gate-Sprache aus Spec 00 §4 ist genau diese Rückführung |
| Zusammengesetzte Judge-Claims wurden bejaht, sobald der Judge eine Bedingung erfüllt sah | Pflichtelement verschluckt in einer Kette | Ein Claim, eine Bedingung; alles mechanisch Prüfbare ganz aus dem Judge heraus (`references/evals.md`) |

## Für die Anti-Rationalisierungs-Tabelle einer Skill

Sie gehört nur zur ersten Zeile der Vierertabelle — Regel bekannt, unter Druck gebrochen.
Jede Zeile nennt den Gedanken wörtlich, wie er im Kopf entsteht („Vier Agents wirken
produktiver", „Ein Satz braucht keinen Lint"), und daneben die Realität in einem Satz
mit Beleg. Keine Tabelle für Formfehler: Dort hilft das Rezept, und die Tabelle würde
nur die Verhandlung eröffnen, die das Rezept gerade beendet hat.
