# frontend-spa — Component-/E2E-Schnitt

Geladen bei `primary: "frontend-spa"`. Die Kernfrage ist immer: Component-Test
oder E2E-Test — nicht ob, sondern wo die Grenze verläuft.

## Testing-Library-Disziplin

Testing Library (React/Vue/Svelte-Varianten) erzwingt eine Regel durch ihre
API: Man findet Elemente so, wie ein Nutzer sie fände — über sichtbaren Text,
Label, Rolle (`getByRole`, `getByLabelText`) — nicht über CSS-Klassen oder
Komponentenstruktur (`container.querySelector(".btn-primary")`).

- **`getByRole` vor `getByTestId` vor `querySelector`.** In dieser
  Reihenfolge. `data-testid` ist ein Fallback für Fälle ohne zugängliche
  Rolle, kein Standardweg.
- **`userEvent` statt `fireEvent`** für Interaktionen — es simuliert die volle
  Ereigniskette eines echten Klicks/einer echten Eingabe, nicht nur ein
  einzelnes DOM-Event.
- **Nie interne State-/Prop-Werte direkt prüfen.** Wenn ein Test
  `wrapper.instance().state.isOpen` braucht, testet er die Implementierung,
  nicht was der Nutzer sieht. Sichtbarkeit/Text/Rolle sind die Assertion.
- **Async-UI mit `findBy*`/`waitFor` abwarten**, nie mit `setTimeout` im Test.

## Component- vs. E2E-Schnitt

| Kriterium | Component-Test | E2E-Test |
| --- | --- | --- |
| Kosten | niedrig, läuft in Node/JSDOM oder Browser-Component-Runner | hoch, echter Browser, echte Navigation |
| Deckt | eine Komponente inkl. Interaktion, isoliert von Routing/Netzwerk | den vollen Nutzerfluss über mehrere Seiten/Komponenten |
| Netzwerk | gemockt (MSW o. ä.) | real oder gegen eine Testumgebung |
| Wann nötig | Standardfall für Formulare, Widgets, Zustandslogik einer Komponente | Kernflüsse, die mehrere Komponenten/Routen verbinden (Login → Dashboard, Checkout) |

**Faustregel:** Ein Fehler, der sich in einer Komponente isoliert reproduzieren
lässt, gehört in einen Component-Test — billiger, schneller, genauere
Fehlerlokalisierung. E2E ist für Flüsse reserviert, die sich nicht sinnvoll
isolieren lassen (Navigation, Auth-Redirects, Zusammenspiel mehrerer Routen).
Ein E2E-Test pro Component-Fall ist teure Redundanz, kein zusätzlicher
Regressions-Fang.

## Netzwerk mocken, nicht Komponenten

Mock Service Worker (MSW) fängt Requests auf Netzwerkebene ab — die Komponente
ruft `fetch`/den echten HTTP-Client unverändert auf, nur die Antwort ist
kontrolliert. Das vermeidet, dass ein Test bricht, weil sich ein interner
API-Client-Wrapper geändert hat, obwohl das Netzwerkverhalten gleich blieb.

## Test-Plan-Schichten für frontend-spa

1. **Component-Tests** für Formulare, Widgets, Zustandslogik — der
   Normalfall, mit MSW-gemocktem Netzwerk.
2. **E2E-Tests** für die zwei bis vier Kernflüsse, die mehrere Routen
   verbinden — bewusst wenige, teuer genug, dass „mehr ist besser" hier gegen
   die Doktrin verstößt.
3. Reine Darstellungskomponenten ohne Logik (ein `<Badge color="red" />`)
   gehören typischerweise ins Feld `Ausgelassen:` — visuelle Regression ist
   ein anderes Werkzeug (out of scope dieser Skill), kein fehlender Unit-Test.
