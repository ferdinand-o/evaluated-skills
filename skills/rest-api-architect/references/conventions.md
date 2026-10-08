# Das Preset erklärt

Diese Datei erklärt `assets/conventions.json` — sie wiederholt die Werte nicht. Wer die
aktuellen Zahlen/Felder wissen will, liest die JSON-Datei (oder den Projekt-Override unter
`.skills/rest-api-architect/conventions.json`); wer das *Warum* wissen will, liest hier.

## Warum RFC 9457 (`problem+json`) statt eigenem Fehlerformat

Jedes selbst erfundene Fehlerformat ist eine weitere Sache, die jeder Client-Entwickler lernen
muss. RFC 9457 ist ein IETF-Standard, den generische HTTP-Tooling (Debugger, API-Gateways)
bereits kennt. Die Fehlercode-Registry (`errors.registry.codes`) ergänzt das um ein Feld, das
RFC 9457 selbst nicht vorschreibt: `code` — eine stabile, programmatisch auswertbare Kennung,
die sich nicht ändert, wenn `detail` (der menschenlesbare Text) umformuliert wird. Clients
sollten nie auf `detail` matchen.

## Warum Cursor- statt Offset-Paginierung

Offset-Paginierung (`?page=3&size=20`) bricht bei gleichzeitigen Schreibzugriffen: Einträge
verschieben sich zwischen zwei Requests, Seiten überspringen oder wiederholen Ergebnisse.
Cursor-Paginierung (`?cursor=...&limit=...`, Antwort trägt `next_cursor`) ist stabil gegenüber
Inserts/Deletes zwischen zwei Abrufen, weil der Cursor eine Position im Datensatz referenziert,
keinen Zähler.

## Warum Pfad-Versionierung mit Deprecation statt Bruch

Header-Versionierung (`Accept: application/vnd.api+json;version=2`) ist für Clients weniger
sichtbar als ein Pfadsegment — Debugging, Logs und Caching-Schichten sehen den Pfad, nicht
immer den Header. `/v1` im Pfad macht die Version an jeder Stelle sichtbar, an der die URL
auftaucht. Der Preis: Ein neues `/v2` ist teuer, deshalb ist die zweite Hälfte des Presets
wichtiger als die erste — Breaking Changes werden vermieden, nicht durch Versionssprünge
gelöst. Siehe `references/evolution.md` für den Deprecation-Pfad.

## Warum Idempotency-Key-Pflicht für unsichere POSTs

POST ist im HTTP-Modell nicht idempotent — ein wiederholter Request (Netzwerk-Timeout, Retry
durch einen Client) kann eine Ressource doppelt anlegen. Ein vom Client gesetzter
`Idempotency-Key`-Header lässt den Server einen wiederholten Request am Key erkennen und die
erste Antwort erneut ausliefern statt eine zweite Ressource anzulegen. GET/PUT/DELETE sind per
HTTP-Semantik bereits idempotent (oder sollen es sein) und brauchen den Header nicht.

## Warum snake_case, Plural, keine Verben in Pfaden

Konsistenz ist der eigentliche Wert, nicht die konkrete Wahl — ein Projekt, das durchgehend
camelCase nutzt, ist nicht falsch, nur anders als dieses Preset. snake_case ist hier Default,
weil es sprachneutral ist (kein Unterschied zwischen JSON-Feld und z. B. Python-Attributnamen).
Plural-Ressourcen (`/orders`, nicht `/order`) halten Kollektion und Einzelressource
(`/orders/{id}`) im selben Namensraum unterscheidbar durch Pfadtiefe, nicht durch Numerus.
Keine Verben in Pfaden folgt aus REST selbst: die Methode (GET/POST/...) trägt das Verb
bereits. Die Ausnahme sind echte Aktionen, die sich nicht als Ressourcen-Zustand modellieren
lassen (`POST /orders/{id}/cancel`) — siehe `references/resource-modeling.md` für die Grenze
zwischen Ressource und Aktion.

## Warum RFC 3339 UTC für Zeitstempel

RFC 3339 ist eine strikte, eindeutig parsbare Teilmenge von ISO 8601. UTC vermeidet
Zeitzonen-Mehrdeutigkeit in gespeicherten und übertragenen Werten; Darstellung in Lokalzeit ist
Sache des Clients, nicht der API.

## Fehlercode-Registry: zentral, nicht pro Domäne (R6)

Die Registry lebt in `conventions.json`, nicht in getrennten Domänen-Dateien. Eine Gliederung
vor dem ersten Bedarf ist eine Hierarchie ohne Inhalt. Ab `errors.registry.warn_threshold`
(Default 50) warnt die Skill, dass eine Gliederung fällig wäre — sie gliedert nicht selbst;
das ist eine Projektentscheidung, keine Skill-Entscheidung.
