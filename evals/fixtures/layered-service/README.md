# layered-service (Fixture)

Kleiner Drei-Schichten-Service: `domain/`, `application/`, `infrastructure/`, plus
`main.py` als Einstiegspunkt.

- `domain/broken.py` importiert aus `infrastructure/db.py` — eine Verletzung der in
  `.skills/architecture-map/layers.json` festgelegten Dependency Rule (innere Schicht
  darf keine äußere importieren).
- `infrastructure/unused_helper.py` hat keinen Fan-in und trifft kein Entry-Pattern —
  Kandidat für ein totes Modul.
- `main.py` hat ebenfalls keinen Fan-in, matcht aber das Entry-Pattern `main` und darf
  deshalb nicht als tot gemeldet werden.

Erwartung: `architecture-map` liefert drei getrennte Diagramm-Abschnitte (kein
Monster-Diagramm für diesen kleinen Fall — Anti-Zeremonie), benennt die
Schichtverletzung und das tote Modul.
