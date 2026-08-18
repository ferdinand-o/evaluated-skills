# Schwierigkeit operationalisiert

Kein „leicht/mittel/schwer" aus dem Bauch. Drei Achsen, jede einzeln
eingeschätzt beim Erzeugen einer Aufgabe; das Label ist eine Ableitung, keine
eigene Entscheidung.

## Die drei Achsen

| Achse | Feld | Was gezählt wird |
| --- | --- | --- |
| Lösungsschritte | `steps` | Anzahl nötiger, nicht-trivialer Denk-/Rechenschritte bis zur Antwort. Ein Schritt = ein Punkt, an dem ein Anfänger falsch abbiegen kann. |
| Vorwissen | `prerequisites` | Liste benannter Konzepte, die die Aufgabe voraussetzt, ohne sie zu erklären. Länge der Liste zählt. |
| Transferdistanz | `transfer` | `"near"` — Aufgabe entspricht strukturell einem bereits gelernten Beispiel, nur Werte/Kontext geändert. `"far"` — die gelernte Idee muss auf einen neuen, nicht vorgeführten Kontext übertragen werden. |

## Ableitung des Labels

| `steps` | `len(prerequisites)` | `transfer` | Label |
| --- | --- | --- | --- |
| 1 | 0–1 | near | `leicht` |
| 2 | 0–2 | near | `leicht` |
| 2–3 | 2–3 | near | `mittel` |
| 1–2 | 0–2 | far | `mittel` |
| 3+ | jede | far | `schwer` |
| jede | 4+ | jede | `schwer` |

Trifft eine Aufgabe keine Zeile exakt (z. B. `steps=4, prerequisites=1,
transfer=near`), gilt die nächststrengere Zeile — im Zweifel höher einstufen,
nicht niedriger (dieselbe Vorsicht wie A4 in den Rulings: unklare Fälle werden
nicht klein geredet).

## „Eine Stufe schwerer"

Fordert der Lernende eine schwerere Variante an, ändert sich mindestens eine
Achse nachvollziehbar — nicht nur die Wortwahl im Stamm:

- **Steps erhöhen:** ein Zwischenschritt entfällt aus der Angabe und muss vom
  Lernenden selbst ergänzt werden.
- **Prerequisites erweitern:** ein zusätzliches, in der Aufgabe nicht
  erklärtes Konzept wird vorausgesetzt.
- **Transfer von `near` auf `far` heben:** derselbe Kern-Gedanke, aber in
  einem Kontext, der dem Lernbeispiel nicht mehr ähnelt.

Eine „schwerere" Aufgabe, die nur komplizierter klingt (längerer Stamm,
Fachjargon) ohne dass sich `steps`, `prerequisites` oder `transfer` ändern,
ist keine schwerere Aufgabe — nur eine schwerer zu lesende.
