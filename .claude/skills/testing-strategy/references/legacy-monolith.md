# legacy-monolith — Sicherheitsnetz vor Refactoring

Geladen bei `legacy.suspected: true`, unabhängig vom erkannten `primary`-Typ.
Die Reihenfolge ist die ganze Doktrin dieses Adapters: **erst
Characterization-Tests, dann Refactoring — nie umgekehrt.** Ein Test, der
festschreibt, was der Code *tun sollte*, statt was er *tut*, ist in
unbekanntem Code eine Wette, keine Absicherung.

## Characterization-Tests (Golden-Master)

1. Den Code **unverändert** aufrufen, mit realistischen Eingaben.
2. Die tatsächliche Ausgabe erfassen — nicht die vermutete.
3. Diese Ausgabe als Erwartung einfrieren (Snapshot, Approval-Test, oder ein
   fest codiertes `assert`).
4. Erst danach ändern. Ein Fehlschlag zeigt jetzt: „Verhalten hat sich
   geändert" — nicht mehr und nicht weniger. Ob die Änderung gewollt war,
   entscheidet ein Mensch, nicht der Test.

**Der Unterschied zum naiven Unit-Test:** Ein naiver Test in Legacy-Code
schreibt zuerst auf, was der Autor *für richtig hält*, und lässt den Code
danach daran scheitern oder bestehen. Das prüft eine erfundene Spezifikation,
nicht das tatsächliche System — und verdeckt echtes Fehlverhalten, das seit
Jahren so funktioniert und von Aufrufern vorausgesetzt wird.

## Seams finden

Ein Seam ist eine Stelle, an der sich Verhalten ändern lässt, ohne den Code an
dieser Stelle zu editieren (Michael Feathers' Begriff). In Monolithen ohne
Tests sind das typischerweise:

- Ein globaler Singleton/Modul-Import, der sich durch einen Parameter ersetzen
  lässt (Dependency-Injection light, keine große Umstrukturierung).
- Eine Fassade um I/O (Datei, Netzwerk, DB), hinter der ein Test-Double
  einspringen kann, ohne die Aufrufer zu ändern.
- Ein Zeit- oder Zufallsquelle, die sich einfrieren lässt.

Ein Seam wird genutzt, um den Code **testbar** zu machen — nicht um ihn zu
verbessern. Das Verbessern kommt danach, mit Netz.

## Approval-Tests für große, unübersichtliche Ausgaben

Wenn die Ausgabe zu groß für eine einzelne Assertion ist (ein generierter
Report, ein komplexes Objekt), friert ein Approval-Test die gesamte Ausgabe
in einer Datei ein und diff't bei jedem Lauf dagegen. Ein Mensch prüft und
„genehmigt" Änderungen explizit (Datei überschreiben), statt dass ein Test
stillschweigend grün bleibt, weil niemand hinschaut.

## Java als Legacy-Vertreter

Java erscheint in `test-design.md` bewusst nicht — hier ist sein Platz, weil
Legacy-Monolithe in dieser Sammlung typischerweise Java sind (Spring-MVC-Apps
ohne Tests, Jahre gewachsen).

- **JUnit 5** (`@Test`, `@ParameterizedTest`) für Characterization-Tests.
- **ApprovalTests für Java** oder ein selbstgebauter Golden-Master-Vergleich
  (Ausgabe in eine Datei schreiben, gegen eine `.approved`-Referenzdatei
  diffen) für Approval-Tests.
- Seams in Java oft über Interfaces, die eine konkrete Klasse ersetzen — auch
  ohne vollen DI-Container, ein manuell durchgereichtes Interface reicht für
  den ersten Test.
- **Mockito** sparsam: Ein Mock pro externer Grenze (DB, HTTP-Client), nicht
  pro internem Kollaborator — sonst wird der Test zum Implementierungsdetail-Test
  aus `test-design.md`.

## Test-Plan-Feld „Ausgelassen:" bei Legacy

Bei Legacy-Code ist das Feld fast nie leer: Code-Pfade, die nicht in den
ersten Characterization-Durchgang passen (seltene Fehlerzweige, historisch
gewachsene Sonderfälle ohne erkennbaren Aufrufer), gehören explizit benannt —
nicht stillschweigend übersprungen.
