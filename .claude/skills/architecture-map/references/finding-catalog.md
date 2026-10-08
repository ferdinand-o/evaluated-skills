# Befund-Katalog

Jeder Befund stammt aus `analyze_graph.py` — das LLM darf einordnen (real problematisch
vs. bewusste Ausnahme, mit Begründung) und ergänzen, aber ergänzte Befunde tragen die
Markierung „Beobachtung (nicht graph-belegt)". Nie umgekehrt: ein Befund, den das Skript
nicht gemeldet hat, wird nie als Fakt behauptet.

## Zyklus

**Erkennungsregel:** `find_cycles()` — starke Zusammenhangskomponente mit >= 2 Knoten,
oder eine Selbstkante. Deterministisch (Tarjan), nichts Interpretatives.

**Schweregrad-Leitfaden:** Nicht jeder Zyklus ist ein Notfall. Ein Zyklus zwischen zwei
eng verwandten Modulen derselben Verantwortlichkeit (z. B. `models.py` <-> `validators.py`
in einem kleinen Package) ist oft eine bewusste Design-Entscheidung — dokumentiere sie
als solche, verschweige sie nicht. Ein Zyklus, der zwei Schichten verbindet, die laut
`layers.json` getrennt sein sollen (`domain` <-> `infrastructure`), ist strukturell
riskant: Änderungen an einer Seite können die andere unvorhersehbar brechen, und keine
der beiden Seiten ist unabhängig testbar. Ein Zyklus außerhalb jeder plausiblen
Lese-Stichprobe (weit auseinanderliegende Verzeichnisse) ist der Fall, den Spec 10s
erster Eval verlangt zu finden — er wäre beim bloßen Lesen nie aufgefallen.

## Fan-in-/Fan-out-Ausreißer ("God-Class"/"God-Module")

**Erkennungsregel:** `find_outliers()` — Fan-in oder Fan-out über der konfigurierten
(oder Default-) Schwelle aus `layers.json["thresholds"]`.

**Schweregrad-Leitfaden:** Hoher Fan-in (viele Module importieren dieses eine) ist oft
gesund — eine gemeinsame Utility- oder Domänen-Schicht soll importiert werden. Hoher
Fan-out (dieses eine Modul importiert sehr viel) ist eher ein Zeichen für zu viel
Verantwortung an einer Stelle — der klassische "God-Module"-Verdacht. Beides braucht
Kontext aus dem Pfad/Namen, den das Skript nicht hat: eine Einschätzung, keine
automatische Regel.

## Schichtverletzung

**Erkennungsregel:** `find_layer_violations()` — eine Kante von einer inneren zu einer
äußeren Schicht laut `layers.json["order"]` (Details und Richtungskonvention: Docstring
in `analyze_graph.py`). `None` (nicht `[]`) heißt: keine `layers.json` vorhanden, also
ungeprüft — das gehört so in die Narration, nicht als "keine Verletzungen gefunden".

**Schweregrad-Leitfaden:** Eine einzelne Verletzung an einer klar benannten Stelle
(z. B. ein Adapter, der bewusst beide Seiten kennt) ist oft eine dokumentierte
Ausnahme. Mehrere Verletzungen über verschiedene Module hinweg deuten auf eine Schicht-
Grenze, die in der Praxis nicht mehr gilt — dann ist entweder der Code oder die
`layers.json` falsch, und das gehört explizit benannt.

## Totes Modul

**Erkennungsregel:** `find_dead_modules()` — Fan-in 0 und kein Treffer gegen die
Entry-Pattern-Liste (`__main__`, `main`, `cli`, `app`, `index` als exakter letzter
Namensteil, keine Substring-Prüfung).

**Schweregrad-Leitfaden:** Kandidat für "kann weg", aber kein Beweis — dynamische
Importe (Plugins, `importlib.import_module` mit Variablen-Pfad, DI-Container),
Einstiegspunkte außerhalb der Entry-Pattern-Liste (z. B. ein per Setuptools-Entry-Point
registriertes Skript) und reine Test-Fixtures erzeugen echte Fan-in-0-Module, die
trotzdem gebraucht werden. Immer als Kandidat formulieren, nie als "wird nicht
verwendet".
