# Spec 02: dev\-report — Fakten\-first Entwicklungs\-Reports

Skill\-Spezifikation · Zyklus 2/14 · Entscheidung: Option A \+ Context\-Harvest aus B · Abgeglichen mit Spec 00

## Problem

Report\-Skills (internal\-comms u. a.) lassen Claude aus dem Kontextfenster schreiben: Was gerade im Gedächtnis ist, wird Report. Nichts erzwingt, dass Aussagen aus Commits oder Artefakten stammen; Zahlen sind unbelegt, Wochenreports blähen ruhige Wochen auf, und Management\-Texte schwanken zufällig zwischen zu technisch und zu vage. Der Report ist eine Rekonstruktion statt eines Renderings vorhandener Fakten.

## Constraints

Datenquelle ist ausschließlich lokales Git (keine gh\-/API\-Abhängigkeit — die Skill muss offline und in jedem Repo funktionieren). Drei Anlässe: Wochen\-/Statusreport, Feature\-/PR\-Abschluss, Release Notes. Drei Zielgruppen: Ich/Projektlog, Team/Technik, Vorgesetzte. Reports auf Deutsch (Templates zweisprachig vorbereitet). Die Skill liefert immer einen *Entwurf* zur Freigabe, nie einen automatisch versendeten Report. Portables Frontmatter.

## Approach

Zwei strikt getrennte Phasen: **Sammeln ist ein Skript, Schreiben ist ein Rendering.** Claude darf in den Report nur schreiben, was in `facts.json` steht oder explizit als Einschätzung markiert ist.

**Skill\-Struktur:**

```
dev-report/
├── SKILL.md               (Doktrin, Modus-/Audience-Wahl, Contract)
├── references/
│   ├── audience-guide.md  (Ich/Team/Vorgesetzte: Ton, Tiefe, Tabus)
│   └── harvest.md         (welche Repo-Artefakte wie geerntet werden)
├── assets/
│   ├── template-weekly.md
│   ├── template-feature.md
│   └── template-release.md
├── scripts/
│   └── collect.py         (Tier 1; Git-Fakten → .skills/cache/facts.json)
└── evals/evals.json
```

**`collect.py`** nimmt Modus und Zeitfenster/Ref\-Bereich (`--since`, `--range v1.2..HEAD`, `--branch feature/x`) und erzeugt `.skills/cache/facts.json` (Ephemera nach Spec 00, gitignored): Commits (Hash, Message, Dateien, Insertions/Deletions), berührte Module (aggregiert per Pfadpräfix), Branch\-/Tag\-Ereignisse, Merge\-Punkte, auffällige Muster (Revert\-Commits, Fix\-auf\-Fix\-Ketten — ehrliche Signale für „das war zäh").

**Context Harvest:** Nach dem Git\-Sammeln prüft die Skill definierte Repo\-Artefakte und erntet sie als zweite Faktenquelle, *falls vorhanden* — nie vorausgesetzt: `docs/debugging/INDEX.md` (gelöste Bugs samt Ursache — das *Warum* hinter Fix\-Commits), `docs/specs/wip/` (Spec 03: geplantes vs. Geliefertes), `docs/decisions.md`, `CHANGELOG.md`, Handoff\-Dateien. Jede Ernte wird in facts.json mit Quellpfad *und gelesener Schema\-Version* abgelegt — bei unbekannter Version wird die Quelle sichtbar übersprungen statt geraten (Konsumenten\-Regel, Spec 00 §1). So verzinsen sich die Artefakte der anderen Skills (Spec 01 ff.) im Report.

**Rendering:** Template nach Modus, Ton nach Zielgruppe. Audience\-Regeln als harte Doktrin: *Vorgesetzte* — Outcomes, Risiken, nächste Schritte; keine Dateinamen, keine Commit\-Hashes im Fließtext, Belege als Fußnoten; *Team* — Entscheidungen, offene Punkte, relevante Diffs verlinkt; *Ich/Projektlog* — kompakt, ehrlich, inklusive Sackgassen. Contract: Jede faktische Aussage trägt eine Referenz auf einen facts.json\-Eintrag (Commit, Tag, Artefakt); Sätze ohne Referenz müssen als „Einschätzung:" markiert sein. Ruhige Perioden werden als solche benannt („2 Commits, Fokus lag auf X") — Aufblähen ist der definierte Hauptfehler.

**Anti\-Rationalisierungs\-Tabelle (Auszug):** „Ich erinnere mich, was diese Woche war" → Erinnerung ist keine Quelle; collect.py zuerst. „Die Zahl macht es überzeugender" → Zahlen ohne facts.json\-Referenz fliegen raus. „Für den Chef schönreden" → Risiken benennen ist der Wert des Reports; Revert\-Ketten erscheinen als Lessons Learned, nicht gar nicht.

**Evals:** (1) Ruhige Woche mit 3 Commits — bleibt der Report ehrlich kurz? (2) Woche mit Revert\-Kette — taucht sie auf (Ich/Team) bzw. wird sie korrekt zu „Risiko/Erkenntnis" abstrahiert (Vorgesetzte)? (3) Release\-Notes\-Modus mit gemischten Commit\-Messages — werden interne Refactorings korrekt aus der Kundensicht gefiltert? (4) Aussage ohne Beleg im Entwurf provoziert — schlägt der Contract an?

## Alternatives considered

Journal\-first als Kern (Report \= reines Rendering eines gepflegten Entwicklungsjournals) ist die sauberste Theorie, setzt aber Pflege\-Disziplin voraus — der Harvest\-Schritt holt 80 % davon ohne die Abhängigkeit. Die ambitionierte Variante mit Claim\-Checker\-Skript und Trend\-Metriken wurde vertagt: Metriken (Velocity, Churn) laden zum Zahlen\-Theater ein; der Referenz\-Contract im Text reicht zunächst. gh\-/CI\-Integration bewusst ausgeklammert (Constraint), als optionales Modul nachrüstbar. Vollautomatische geplante Reports ohne Review verworfen: Richtung Vorgesetzte ist ein ungeprüfter KI\-Report ein Vertrauensrisiko.

## Out of scope

GitHub\-/CI\-Datenquellen (PRs, Issues, Pipeline\-Status), Trend\-Metriken über Reports hinweg, automatischer Versand (E\-Mail/Slack), Zeiterfassungs\-Integration.

## Open questions

Soll der Feature\-Modus zusätzlich das Diff selbst lesen (Code\-Verständnis statt nur Metadaten) — genauer, aber teurer? Mehrsprachigkeit: deutsche Templates zuerst, englische als Option — oder umgekehrt fürs Teilen?

## Next steps

`collect.py` implementieren (Modi, Zeitfenster, Muster\-Erkennung für Reverts/Fix\-Ketten); drei Templates schreiben; audience\-guide.md mit den Tabu\-Regeln formulieren; Harvest\-Konventionen mit Spec 01 (Ledger\-INDEX) abstimmen; die vier Evals bauen und den Aufbläh\-Fall zuerst testen.
