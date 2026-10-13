# rest-api — Contracts vor Implementierungsdetails

Geladen bei `primary: "rest-api"`. Doktrin: Eine REST-API testen heißt zuerst,
ihren **Contract** prüfen — was Aufrufer sehen und sich darauf verlassen —
und erst danach interne Implementierungsdetails, wenn überhaupt.

## Contract-Tests

Ein Contract-Test prüft die Schnittstelle, nicht die Logik dahinter: Status-Codes,
Response-Shape, Header, Fehlerformat. Er bleibt grün, solange der Contract
eingehalten wird, egal wie die Implementierung intern umgebaut wird — das ist
der Regressions-Fang-pro-Wartungskosten-Vorteil gegenüber Implementierungstests.

- **Provider-seitig:** Die eigene API gegen ihre eigene Spezifikation prüfen
  (siehe Schema-Validierung unten).
- **Consumer-driven** (wenn es mehrere Teams/Services gibt): Der Aufrufer
  definiert, was er tatsächlich nutzt; der Provider prüft dagegen. Verhindert
  Breaking Changes an Feldern, die niemand mehr liest, ohne unnötig konservativ
  bei Feldern zu sein, die kein Consumer kennt.

## Schema-Validierung gegen OpenAPI

Wenn `openapi.yaml`/`swagger.yaml` existiert (das Signal, das `detect_stack.py`
für `rest-api` nutzt), ist es die Quelle der Wahrheit für Contract-Tests:

1. Echte Response gegen das im Schema definierte Response-Objekt validieren
   (Python: `jsonschema`/`openapi-core`; TypeScript: `ajv` gegen das aus der
   Spec exportierte JSON-Schema).
2. Ein Contract-Test pro Endpunkt und Statuscode, der in der Spec vorkommt —
   nicht nur der Happy Path. Ein `404`, der in der Spec steht, aber nie
   getestet wird, ist eine Lücke im Contract-Netz.
3. Driftet Implementierung und Spec auseinander, ist das ein Befund, kein
   Testfehler, der stillschweigend angepasst wird — die Spec ist der Vertrag,
   nicht ein Nebenprodukt der Implementierung.

Fehlt die Spec-Datei trotzdem `primary: "rest-api"` (z. B. nur über
Router-Muster erkannt), gehört „keine Schema-Validierung möglich, keine
OpenAPI-Spec gefunden" explizit ins Feld `Ausgelassen:` — kein stilles
Weglassen.

## Testcontainers statt Mocks für echte Abhängigkeiten

Eine REST-API, die gegen eine Datenbank oder einen Message-Broker spricht,
gewinnt durch echte, isolierte Instanzen mehr Regressions-Fang als durch
gemockte Repositories:

- **Python:** `testcontainers-python` startet die reale DB/den realen Broker
  in Docker, pro Testlauf isoliert.
- **TypeScript:** `testcontainers` (Node-Bindings) — gleiches Prinzip.
- Ein gemocktes Repository beweist, dass der Code die Mock-API korrekt
  aufruft — nicht, dass eine echte Query funktioniert (falsches SQL, falscher
  Index, Transaktionsverhalten). Diese Klasse von Fehlern entgeht
  Implementierungstests systematisch.
- Testcontainer-Tests sind langsamer — das ist der bewusste Tradeoff, nicht
  ein Grund, sie wegzulassen. Wenn Laufzeit zum Problem wird, gehört das ins
  Feld `Ausgelassen:` mit Begründung, nicht ins stille Streichen der Schicht.

## Schichten für den Test-Plan-Block

1. **Contract-Tests** gegen die Spec (oder gegen das dokumentierte Verhalten,
   wenn keine Spec existiert — dann als Auslassung vermerkt).
2. **Integrationstests mit echten Abhängigkeiten** (Testcontainers) für
   Pfade, die eine DB/einen Broker berühren.
3. **Unit-Tests** für Logik, die sich ohne HTTP-Layer isolieren lässt
   (Validierung, Business-Regeln) — dünn gehalten, der Contract-Test deckt
   den Rest.
