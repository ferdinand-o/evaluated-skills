# Evolution: Deprecation statt Bruch

Der Kern des Contracts: Ändert sich etwas an einer bestehenden API-Zusicherung, bricht das
Consumer, die vielleicht kein Wort davon wissen. Der Fix ist Migration mit Frist, nie ein
stiller Bruch — egal wie klein die Änderung erscheint.

## Was als Breaking Change zählt (aus `conventions.json` `breaking_changes.definitions`)

- **Feld entfernt** — auch ein „ungenutztes" Feld. Du weißt nicht, wer es liest.
- **Feld umbenannt** — technisch entfernen + hinzufügen, für Consumer identisch zu „entfernt".
- **Pflichtfeld ergänzt** (Request) — bestehende Clients senden es nicht, ihr Request schlägt
  neu fehl.
- **Statuscode geändert** — ein Client, der auf `200` prüft, bricht bei `201`, selbst wenn
  beide „Erfolg" bedeuten.

**Nicht** breaking: ein neues optionales Response-Feld, ein neuer Endpunkt, eine neue optionale
Query-Parameter, eine Lockerung einer Validierung (die vorher 400 warf, jetzt akzeptiert).

## Der Deprecation-Pfad

1. **Neu hinzufügen, alt behalten.** Statt `user_name` in `full_name` umzubenennen: `full_name`
   ergänzen, `user_name` bleibt bestehen und liefert denselben Wert.
2. **Alt als deprecated markieren** — in der OpenAPI-Beschreibung des Felds (`"deprecated:
   Nutze full_name. Wird entfernt ab <Datum/Version>."`), nicht nur in einem Changelog, das
   Clients nicht lesen.
3. **Response-Header setzen** auf Operationen, die ein deprecated Feld enthalten:
   `Deprecation: true`, `Sunset: <Datum>`, `Link: <Migrationsguide>; rel="deprecation"` (die
   drei Header aus `conventions.json` `versioning.deprecation_headers`).
4. **Frist einhalten, dann erst entfernen.** Wie lang, ist projektabhängig (Anzahl bekannter
   Consumer, Release-Rhythmus) — die Skill legt keine Frist fest, sie verlangt nur, dass es
   eine gibt und sie in der Spec steht (`x-deviation`-Kommentar oder das `deprecated`-Feld
   selbst mit Datum).
5. **Erst nach Ablauf der Frist entfernen**, dann ist es kein Breaking Change mehr, sondern der
   angekündigte Abschluss einer Migration.

## Wann ein echtes `/v2` gerechtfertigt ist

Pfad-Versionierung existiert genau für den Fall, dass der Deprecation-Pfad nicht reicht — eine
grundlegende Umstrukturierung, die sich nicht additiv abbilden lässt (z. B. ein anderes
Paginierungsmodell für eine ganze Ressourcen-Familie). `/v2` ist teuer: alle Endpunkte der
Ressource brauchen eine Parallelfassung, bis auch `/v1` seine eigene Sunset-Frist durchlaufen
hat. Deshalb zuerst der additive Weg prüfen — die meisten vermeintlichen „v2-Kandidaten" sind
bei genauem Hinsehen ein einzelnes deprecated Feld.

## Wenn eine Abweichung vom Preset nötig ist

Nicht jede Abweichung ist ein Fehler — aber jede muss sichtbar sein. Eine begründete
Ausnahme steht als `x-deviation`-Eintrag direkt in der OpenAPI-Spec, an der Stelle, die
abweicht (Operation, Schema oder Feld), mit einer kurzen Begründung. Nie im Code allein, nie
stillschweigend: Der Punkt von `x-deviation` ist, dass die nächste Person, die die Spec liest,
die Abweichung sieht, ohne den Code durchsuchen zu müssen.
