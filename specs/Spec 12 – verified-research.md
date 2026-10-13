# Spec 12: verified\-research — Recherche mit Quellenregister und Trust\-Tiers

Skill\-Spezifikation · Zyklus 12/14 · Entscheidung: Fork von deep\-research (MIT), Register mit 4 Domänen \+ Truth\-Bewertung, Delta\-Modus in v1 · Abgeglichen mit Spec 00

## Problem

Selbst die beste existierende Recherche\-Skill (samber/deep\-research) überlässt die Quellen*wahl* dem Modell — und damit dem Suchmaschinen\-Ranking: SEO\-Spam und Aggregatoren gewinnen, Primärquellen werden übersprungen, sobald ein Blog sie zusammenfasst, Qualitätsstandards variieren pro Lauf, und es gibt kein Gedächtnis über frühere Recherchen zum selben Thema. Bessere Recherche entsteht nicht durch mehr Suchen, sondern durch bessere, reproduzierbare Quellen.

## Constraints

Fork/Adaption von samber/deep\-research (MIT, mit Attribution): Prozessgerüst, Recherche\-Typen, Konfidenz\-Tracking und Prose\-first\-Doktrin bleiben; Register, Tiers, Truth\-Bewertung und Delta\-Modus kommen hinzu. Initiale Register\-Domänen: Software/Tech, Recht/Steuern DE\-EU, Wissenschaft/Papers, Wirtschaft/Statistik — plus ein allgemeines Quellenverzeichnis mit Truth\-Bewertung für domänenübergreifende Quellen (Nachrichtenmedien, Blogs, Aggregatoren). Delta\-Modus mit Themen\-Wissensdatei ab v1. Portables Frontmatter.

## Approach

**Das Register vor der Suche, das Tier vor dem Claim, das Delta vor der Wiederholung.**

**Skill\-Struktur:**

```
verified-research/
├── SKILL.md                 (Doktrin, Ablauf, Tier-Regeln, Contract; adaptierter Kern)
├── references/
│   ├── rating-rubric.md     (Truth-Bewertung: Kriterien, Einstufungs-Leitfaden)
│   ├── research-types.md    (aus deep-research übernommen, gekürzt)
│   └── delta-mode.md        (Wissensdatei-Schema, Differenz-Recherche)
├── assets/
│   └── registry.yaml        (das Quellenregister — siehe unten)
├── scripts/                 (beide Tier 2: PyYAML)
│   ├── registry.py          (Lookup, Tier-Auskunft, neue Bewertungen eintragen)
│   └── spotcheck.py         (Stichproben ziehen: Claim → Quelle → Verifikationsauftrag; G2)
└── evals/evals.json
```

**Das Register (`~/.skills/verified-research/registry.yaml`, mit optionalem Projekt\-Override — Spec 00 §1 für nicht projektgebundene Artefakte):** Pro Domäne kuratierte Einträge (URL\-Muster, Name, Tier, Notiz) — Software/Tech: offizielle Docs, RFCs/Standards (IETF/W3C/WHATWG), Changelogs, GitHub\-Releases; Recht/Steuern DE\-EU: gesetze\-im\-internet, EUR\-Lex, BMF\-Schreiben; Wissenschaft: arXiv, PubMed, Semantic Scholar, DOI\-Auflösung — Original\-Paper vor Sekundärbericht; Wirtschaft/Statistik: Destatis, Eurostat, Bundesbank/EZB, IR\-Seiten. Dazu die **allgemeine Sektion**\: bekannte Medien/Portale mit Truth\-Bewertung und Begründungs\-Notiz. **Tiers:** 1 \= Primärquelle (Gesetz, Standard, Original\-Paper, offizielle Doku, Originaldaten); 2 \= etablierte Fachquelle mit redaktionellem Standard; 3 \= alles Übrige aus freier Suche. Das Register ist nutzergepflegt und *wächst durch Gebrauch*\: Trifft die Recherche eine unbekannte Quelle, bewertet sie sie nach `rating-rubric.md` (Primär\-/Sekundärstatus, redaktionelle Standards, Anreizlage/Interessenkonflikte, Track Record, Aktualität) und trägt sie per `registry.py` mit Begründung ein — Bewertung geschieht einmal, nicht bei jedem Lauf neu.

**Ablauf (adaptiert):** Scope wie gehabt (Interview nur bei vagen Aufträgen) → **Register\-Phase zuerst und verpflichtend**\: passende Tier\-1/2\-Quellen der Domäne werden direkt angesteuert (Site\-Search, bekannte Pfade), bevor freie Suche startet → freie Suche ergänzt, alle Treffer werden getiert (Register\-Lookup oder Neubewertung) → Synthese mit deep\-researchs Konfidenz\-Regeln, verschärft: **Kritische Claims brauchen mindestens eine Tier\-1/2\-Quelle**; nur Tier\-3 belegt → explizit „nur Sekundärquellen gefunden" statt stiller Hochstufung. Aggregator\-Zitate werden zur Primärquelle durchverfolgt (wer zitiert, ist nicht die Quelle).

**Verifikations\-Pass:** `spotcheck.py` zieht nach der Synthese eine Stichprobe der Claims (kritische immer, Rest zufällig); ein Subagent öffnet die genannte Quelle und prüft: Steht das da wirklich, in diesem Kontext, mit diesem Zahlenwert? Abweichungen degradieren den Claim sichtbar (Konfidenz runter oder raus) — das schließt die Lücke zwischen „zitiert" und „belegt".

**Delta\-Modus:** Pro Thema eine Wissensdatei (`~/.skills/verified-research/research/<thema>.md`, im Projektfall repo\-lokal überschreibbar): destillierte Findings mit Quelle, Tier, Datum, Konfidenz. Folgeläufe lesen sie zuerst und recherchieren nur die Differenz (Neues seit Datum X, geänderte Sachlage, offene Fragen von damals); der Bericht weist Bekanntes und Neues getrennt aus. Contract: Jeder Lauf endet mit Update der Wissensdatei — Recherche ohne Gedächtnis\-Update ist unvollständig.

**Anti\-Rationalisierungs\-Tabelle (Auszug):** „Der Blog fasst das Paper gut zusammen" → Paper öffnen; der Blog ist Tier 3. „Steht in drei Artikeln, also stimmt es" → drei Abschriften derselben Pressemitteilung sind eine Quelle. „Die Quelle kenne ich nicht, wirkt aber seriös" → Rubrik anwenden, eintragen, dann verwenden. „Delta sparen wir uns, ich recherchiere frisch" → frisch heißt: bezahlt dasselbe zweimal und verliert den Vergleich.

**Evals:** (1) Frage, deren Top\-Suchtreffer ein SEO\-Aggregator mit veralteter Zahl ist, während die Primärquelle aktuell ist — gewinnt die Primärquelle? (2) Kritischer Claim, der nur in Tier\-3 belegbar ist — wird das ausgewiesen statt hochgestuft? (3) Zweiter Lauf zum selben Thema nach simuliertem Neuigkeiten\-Stand — recherchiert die Skill nur das Delta und weist es getrennt aus? (4) spotcheck\-Trap: ein Claim mit subtil falscher Zahl gegenüber der Quelle — fängt ihn die Stichprobe? (5) Unbekannte Quelle — entsteht ein begründeter Register\-Eintrag nach Rubrik?

## Alternatives considered

Eigenständige Neuentwicklung verworfen: deep\-researchs Prozessreife (Typen, Parallel\-Recherche, Konfidenz, Prose\-Doktrin) ist erprobt; die Innovation liegt im Quellen\-Layer, nicht im Prozess. Delta\-Modus auf v2 verschieben verworfen (Nutzerentscheidung — er ist der zweite große Hebel). Automatische Web\-weite Truth\-Scores (externe Rating\-APIs) verworfen: intransparent und nicht nutzerkontrolliert; die eigene Rubrik mit Begründungs\-Notizen bleibt nachvollziehbar. Festes Quellen\-Whitelisting (nur Register, keine freie Suche) verworfen: zu starr für neue Themen — die Pflicht\-Reihenfolge Register→frei erreicht das Ziel ohne Blindheit.

## Out of scope

Paywalled\-Quellen\-Zugriff, automatisches Monitoring/Alerts zu Themen (wäre eine geplante Aufgabe über dieser Skill), Zitationsformat\-Verwaltung (BibTeX o. Ä.), Berichts\-Design (visual\-summary/Spec 11 übernimmt das Rendering auf Wunsch).

## Open questions

Stichproben\-Quote von spotcheck.py (kritische 100 % \+ wie viel Rest?)? Wissensdatei\-Format: eine Datei pro Thema vs. Themenbaum bei großen Gebieten?

## Next steps

registry.yaml mit den vier Domänen\-Sektionen und \~30 Kern\-Einträgen befüllen; rating\-rubric.md schreiben; registry.py (Lookup/Eintrag) und spotcheck.py implementieren; deep\-research forken, Register\-Phase und Tier\-Contract in den Kern einbauen (mit Attribution); Eval 1 (SEO\-Trap) und 4 (spotcheck\-Trap) zuerst fahren.
