# cyclic-imports (Fixture)

Kleines Python-Paket unter `src/`. `src/domain/models/user.py` importiert
`get_session` aus `src/infra/db/session.py`, das umgekehrt `User` aus
`src/domain/models/user.py` importiert — ein Zyklus zwischen zwei Verzeichnissen,
die kein Reviewer beim schnellen Lesen von `src/api/routes.py` oder
`src/domain/services/order.py` zusammen sehen würde.

Erwartung: `architecture-map` findet den Zyklus über `extract_py.py` +
`analyze_graph.py`, nicht über eine Lese-Stichprobe.
