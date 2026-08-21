# Spec 15: mobile-audit — Mobile-Handwerk als Referenz + Prüf-Skill

*Skill-Spezifikation · Zyklus 15 · Entscheidung: Mobile-Web/PWA, Referenz in der Familie + eigenständige Audit-Skill, zweistufiger Harness, PWA-Infrastruktur später · Abgeglichen mit Spec 00 und mit den Befunden der Testläufe vom 2026-08-20/21*

## Problem

Mobile ist der blinde Fleck der UI-Skill-Familie — und des gesamten Ökosystems: Kein bekannter Community-Skill kodiert das Mobile-Handwerk (Touch-Targets, Daumen-Zonen, `dvh/svh` statt kaputtem `100vh`, Safe-Areas, Virtual-Keyboard-Verhalten, hover-lose Interaktion, Container Queries, Tabellen-/Formular-Umbau für schmale Viewports). Der typische LLM-Fehler ist Desktop-first-und-dann-schrumpfen, und weil niemand mobil *prüft*, fällt es erst auf dem echten Gerät auf. Dabei ist genau der Prüf-Teil groß und mechanisierbar.

## Constraints

Geltungsbereich Mobile-Web (responsive Sites und Web-Apps im Browser); kein React Native. Keine PWA-Infrastruktur (Service Worker, Manifest, Push) — eigene Erweiterung später. Form: **zweiteilig** — (a) das Handwerk als geteilte Referenz `mobile.md` in den bestehenden Familien-Skills (enterprise-ui, motion-landing, ui-architect), damit es beim *Bauen* wirkt, ohne eine konkurrierende Bau-Skill zu schaffen; (b) eine eigenständige **mobile-audit**-Skill, die die Familie als Verifikationsschritt aufruft und die auch solo auf bestehende Seiten anwendbar ist. Portables Frontmatter.

**Grenzwerte sind Familienrecht, nicht Skill-Recht.** Der Tap-Target-Boden ist **24×24 px (WCAG 2.2 AA)** — identisch mit `enterprise-ui/references/a11y-floor.md`, dessen Controls bei 40 px (komfortabel) und 32 px (compact) liegen. Ein davon abweichender Boden würde jede regelkonform gebaute enterprise-ui-Tabelle als Verstoß melden; 44 px ist Apple-HIG-Empfehlung, kein Boden, und erscheint deshalb als *Hinweis* für primäre Aktionen, nie als Verstoß. Beide Werte stehen in `assets/audit-config.json` und sind pro Projekt überschreibbar.

**Der Harness ist zweistufig.** Playwright ist Tier 3 und in der Entwicklungsumgebung dieser Sammlung nicht installiert; `motion-landing/scripts/verify.py` dokumentiert im eigenen Docstring, dass sein Erfolgspfad deshalb ungetestet blieb, und in beiden Testläufen lief dort ausschließlich der Degradationszweig. motion-landing überlebt das, weil es auch ohne Harness eine Bau-Doktrin ist — mobile-audit wäre ohne Harness nichts. Deshalb: **Stufe 1 statisch (nur Stdlib, keine Browser-Abhängigkeit), Stufe 2 Geräte-Matrix.** Fehlt Playwright, liefert die Skill weiterhin echte Befunde und benennt die ausgelassene Stufe als „ungeprüft", statt als Ganzes zu degradieren.

## Approach

**Bauen lehrt die Referenz, beweisen tut der Harness.** Keine Trigger-Konkurrenz: mobile-audit triggert ausschließlich auf **Diagnose und Verifikation** („funktioniert das auf dem Handy?", „mobile kaputt", „prüf das mobil", „mobile Audit"). Bau- und Umbauaufträge — insbesondere **„responsive machen"** — gehören der Familie; sie ruft am Ende das Audit. Ein Bau-Trigger in dieser Skill wäre genau das Familien-Problem aus der Analyse, nur mit umgekehrtem Vorzeichen.

### Teil A — geteilte Referenz `mobile.md` (in die Familien-Skills)

Das Handwerk in einer Referenz, die enterprise-ui/motion-landing/ui-architect laden, sobald ein View auch mobil ausgeliefert wird (bei Web: immer):

- **Mobile-first-Reihenfolge:** Basis-Layout für ~360 px entwerfen, per Container Queries/`min-width` anreichern — nie umgekehrt schrumpfen.
- **Viewport-Wahrheiten:** `dvh/svh` statt `100vh`; Safe-Areas via `env(safe-area-inset-*)`; kein horizontales Overflow-Element ohne eigenen Scroll-Container; `<meta name="viewport">` ohne `user-scalable=no`/`maximum-scale=1` — Zoom-Sperren sind ein Zugänglichkeitsdefekt, kein Layout-Werkzeug.
- **Touch statt Hover:** Alles Hover-only bekommt einen Touch-Pfad (sichtbar, long-press oder explizit); Hit-Area ≥ 24×24 px, auch wenn die Glyphe kleiner ist; Daumen-Zone: primäre Aktionen in die untere Bildschirmhälfte, destruktive raus aus ihr.
- **Virtual Keyboard:** Formulare scrollen zum fokussierten Feld; nichts Fixiertes verdeckt Eingaben; `interactive-widget`/VisualViewport-Verhalten definiert; Eingabefelder ≥ 16 px, sonst zoomt iOS beim Fokus.
- **Umbau-Muster:** Tabellen → Karten-Stapel oder horizontaler Scroll-Container mit Schatten-Hinweis; Mehrspalten-Formulare → einspaltig; Sidebar-Navigation → Bottom-Nav oder Sheet.

**Verteilung:** je eine Kopie im `references/` der drei Familien-Skills, plus ein Test, der die Kopien auf Byte-Gleichheit prüft. Eine Referenz außerhalb des Bundles ist installiert tot — Lauf 1 hat das an `docs/artifact-header.md` gezeigt, auf das zwei Skills verwiesen und das in keinem installierten Bundle lag. Ein gemeinsames Plugin wäre neue Infrastruktur für eine Datei; der Drift-Test kostet zwanzig Zeilen und macht das Risiko zu einem roten Test.

### Teil B — Skill `mobile-audit`

```
mobile-audit/
├── SKILL.md                (Doktrin, Ablauf, Findings-Contract)
├── assets/
│   └── audit-config.json   (Grenzwerte und Geräteprofile, projektüberschreibbar)
├── references/
│   ├── fixes.md            (Befund → Standard-Fix-Rezept, verweist auf mobile.md)
│   └── device-matrix.md    (Geräteprofile und warum diese)
├── scripts/
│   ├── audit_static.py     (Stufe 1: Quelltext-Checks, nur Stdlib)
│   └── audit_devices.py    (Stufe 2: Playwright-Geräte-Matrix)
└── evals/evals.json
```

**Stufe 1 — `audit_static.py` (Tier 1, läuft immer).** Vier Checks brauchen keinen Browser und finden die häufigsten Defekte direkt im Quelltext: `100vh`-Verwendung im CSS, Schriftgröße < 16 px auf Eingabefeldern, Zoom-Sperre im Viewport-Meta, und Hover-Regeln ohne Touch-Äquivalent (siehe Verstoßdefinition unten). Preset-Auflösung relativ zum Skript, nicht zum aufrufenden Projekt — der Fehler aus `lint_schema.py:29` wird nicht wiederholt.

**Stufe 2 — `audit_devices.py` (Tier 3, degradiert sichtbar).** Fährt die Seite in der Geräte-Matrix (schmales Android ~360 px, iPhone-Klasse mit Notch-Profil, Tablet; Touch aktiv, CPU/Netz gedrosselt) und misst, was nur im Layout entsteht: horizontales Overflow (dokumentweit und pro Element), tatsächliche Hit-Area-Größen inklusive Padding und Überlappung, Safe-Area-Verletzungen fixierter Elemente. Pro Gerät Screenshots an definierten Scrollpositionen — Claude begutachtet sie zusätzlich visuell. Fehlt Playwright, meldet die Stufe „ungeprüft" mit Werkzeugliste, und Stufe 1 läuft trotzdem.

**Verstoßdefinition Hover.** JS-Listener sind aus der Seite heraus nicht enumerierbar — `getEventListeners` ist DevTools-Konsole, nicht Playwright. Der Check ist deshalb bewusst eng: Verstoß ist eine CSS-Regel, die unter `:hover` **Sichtbarkeit oder Position** ändert (`display`, `visibility`, `opacity`, `transform` auf einem sonst unsichtbaren Element) und für deren Selektor es keine `:focus-visible`/`[aria-expanded]`/`@media (hover: none)`-Entsprechung gibt. Reine Hover-*Stile* (Farbe, Schatten) sind kein Verstoß. JS-getriebene Hover-Menüs bleiben unerkannt — das steht als bekannte Grenze in `docs/known-limits.md`, statt durch eine Heuristik geraten zu werden.

**Keyboard-Check: Spike gelaufen, No-Go für Emulation, Go für Geometrie.**
Gemessen am 2026-08-21 mit Playwright/Chromium: Der emulierende Weg ist tot.
`Emulation.setDeviceMetricsOverride` mit kleinerer Höhe schrumpft Layout *und* visuellen
Viewport gemeinsam (844 → 500), sodass ein `position: fixed; bottom: 0` brav an den neuen
unteren Rand mitwandert (barTop 794 → 450) — eine kaputte Seite sähe damit heil aus.
`Emulation.setVisibleSize` wird ohne Fehler angenommen und tut nichts (beide Werte bleiben
844). Der Check wird deshalb **nicht emuliert, sondern modelliert**: Eine Tastatur verdeckt
die unteren K Pixel (K je Geräteprofil in `audit-config.json`, iPhone-Klasse 336). Elemente
im normalen Fluss sind unkritisch, weil der Browser das fokussierte Feld hineinscrollt;
gemeldet wird ein interaktives Element, das in einem `fixed`/`sticky` verankerten
**Vorfahren** liegt und dessen Unterkante unterhalb von `viewportHöhe − K` sitzt, sofern die
Seite überhaupt ein Eingabefeld hat. Der Aufstieg über die Vorfahren ist nicht optional: Ein
Button in einer fixierten Leiste hat selbst `position: static`, und ohne ihn findet der Check
genau den häufigsten Fall nicht — im Spike zuerst passiert. Verifiziert: Treffer im
Defektfall (`button#submit`, Unterkante 830 > 508), null Treffer, sobald die Leiste nicht
mehr fixiert ist. K ist ein deklariertes Modell, kein Messwert — der Befund heißt deshalb
`modelliert`, nicht `gemessen`. Was er nicht prüft: ob die Seite bei Fokus korrekt scrollt,
und div-basierte Bedienelemente ohne `role`; beides gehört in `docs/known-limits.md`.

**Findings-Contract (analog code-review/Spec 04).** Jeder Befund trägt Quelle (Datei:Zeile für Stufe 1, Gerät + Selektor für Stufe 2), Messwert vs. Grenzwert und ein konkretes Fix-Rezept aus `fixes.md`; deterministische Befunde sind als „gemessen", geometrisch modellierte als „modelliert" (Modellwert deklariert, siehe Keyboard-Check), visuelle als „begutachtet", ausgelassene Stufen als „ungeprüft" markiert. Kein Befund ohne Fundstelle. Der Bericht trägt die Artefakt-Kopfzeile nach Spec 00 §1.

**Gate-Stufe: G2.** Beide Skripte fällen ein maschinelles Urteil, der Aufruf bleibt freiwillig — die Skill sagt „meldet Verstoß", nie „blockiert" (Spec 00 §4). Ein G3-Hook ist hier nicht gerechtfertigt: Ein mobiler Layout-Fehler ist reversibel.

**Modi.** Selbst-Modus (eigene Views vor Lieferung) endet in angewandten Fixes plus Re-Audit; Fremd-Modus (bestehende Seite) endet im priorisierten Bericht. Im Selbst-Modus schreibt die Skill nur in Dateien, die der laufende Auftrag ohnehin anfasst — fremde Views werden gemeldet, nicht repariert.

**Anti-Rationalisierungs-Tabelle (Auszug):** „Sieht im schmalen Browserfenster gut aus" → Fenster-Schmalziehen emuliert weder Touch noch Keyboard noch Notch; Matrix läuft. „Hover-Menü hat doch jeder" → auf Touch existiert Hover nicht; Touch-Pfad oder Befund. „24 px sind bei uns halt 20" → dann als dokumentierte Abweichung in `audit-config.json`, nicht stillschweigend. „Playwright fehlt, also kann ich nichts sagen" → Stufe 1 läuft immer; „ungeprüft" gilt für Stufe 2, nicht für das Audit. „Das Audit mache ich am Ende einmal" → nach jedem größeren Layout-Schritt; Mobile-Fehler sind früh billig und spät teuer.

**Evals.** Fixtures zielen auf Stufe 1, damit die Eval-Suite in jeder Umgebung läuft — eine Suite, die nur auf fremder Hardware grün wird, prüft nichts: (1) `100vh`-Trap mit fixiertem Footer, `contract` — gemessen und gefixt? (2) Zoom-Sperre im Viewport-Meta, `contract` — gefunden und begründet? (3) Eingabefeld mit 14 px, `contract` — iOS-Zoom-Falle erkannt? (4) Hover-Dropdown ohne Touch-Pfad gegen einen reinen Hover-*Stil*, `contract` — genau einer der beiden gemeldet, der andere nicht? (5) Anti-Zeremonie nach Spec 00 §2, `contract`: bereits sauberer mobiler View — kurzer Grün-Bericht statt erfundener Befunde. (6) Degradation, `contract`: ohne Playwright meldet der Lauf Stufe-1-Befunde **und** Stufe 2 als „ungeprüft", nie Erfolg für die ganze Prüfung.

## Alternatives considered

Eigene Bau-Skill „mobile-ui" verworfen: Sie würde im Triggering mit enterprise-ui konkurrieren; die geteilte Referenz erreicht das Bauen ohne zweite Zuständigkeit. Nur-Harness ohne Referenzen verworfen: prüft gut, hebt aber die Erstqualität nicht. Einstufiger Playwright-Harness verworfen — siehe Constraints: eine Skill, deren einziger Wert an einer fehlenden Toolchain hängt, sagt zuverlässig „ungeprüft". 44 px als Boden verworfen, weil er die eigene Familie flächendeckend als verstoßend meldete (`a11y-floor.md:92`: 24×24, compact 32). Heuristische JS-Hover-Erkennung verworfen: nicht zuverlässig messbar, und ein Check, der rät, ist der Anfang der Fehlalarme, die `gate.py` gekostet haben. Gemeinsames Plugin für `mobile.md` verworfen: neue Infrastruktur für eine Datei, Kopie plus Drift-Test ist billiger. React-Native-Scope verworfen. PWA-Infrastruktur vertagt.

## Out of scope

React Native / native Apps, PWA-Infrastruktur (Service Worker, Manifest, Install, Push), App-Store-Themen, Geräte-Farm-Tests auf echter Hardware, Performance-Tiefenprofiling (Lighthouse-Budget läuft bereits in motion-landing), JS-getriebene Hover-Interaktionen (bekannte Grenze, siehe Verstoßdefinition).

## Open questions

Sind die drei Geräteprofile (schmal, Notch, Tablet) ausreichend, oder braucht es ein viertes für Landscape? Das Phablet ist gestrichen, weil es keinen eigenen Check trägt. Soll `audit-config.json` auch die Screenshot-Scrollpositionen führen oder bleiben die fest? Wie meldet Stufe 2 einen Befund, den Stufe 1 bereits gefunden hat — unterdrückt, oder mit beiden Fundstellen?

## Next steps

Keyboard-Spike ist gelaufen (Ergebnis oben). Dann `audit_static.py` mit den vier Quelltext-Checks plus Fixtures, damit die Eval-Suite von Beginn an lauffähig ist. Dann `mobile.md` schreiben und in enterprise-ui einhängen, mit Drift-Test über die drei Kopien. Dann `fixes.md` mit Befund→Rezept-Zuordnung. `audit_devices.py` zuletzt, mit dem Degradationszweig zuerst und dem Erfolgspfad als bewusst ungetestetem Teil, sauber im Docstring und in `docs/known-limits.md` benannt. Zum Schluss die Familien-Descriptions: Bauen ruft Audit, „responsive machen" bleibt bei der Familie.
