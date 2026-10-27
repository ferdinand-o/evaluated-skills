# Recherche-Typen

Adaptiert (nicht wörtlich übernommen) aus dem Prozessgerüst von
[samber/cc-skills](https://github.com/samber/cc-skills), Skill `deep-research` (MIT-Lizenz),
gekürzt auf die Typ-Unterscheidung. Der Typ bestimmt Tiefe und Parallelisierung, nicht
die Register-/Tier-Pflicht — die gilt für alle vier Typen gleichermaßen.

## Quick Fact Check

Eine einzelne, eng gefasste Tatsachenfrage („Seit welcher Version heißt die Option
`--strict`?"). Register-Lookup zuerst, ein bis zwei Quellen genügen, keine Parallel-
Recherche nötig. Bleibt die Antwort mit einer Tier-1/2-Quelle belegbar, ist der Bericht
drei bis fünf Zeilen lang — Aufblähen ist hier der Hauptfehler.

## Vergleichende Recherche

Zwei oder mehr Optionen gegeneinander („Bibliothek A vs. B für X"). Pro Option
mindestens eine eigenständige Quellenkette, damit der Vergleich nicht an einer einzigen
(möglicherweise parteiischen) Quelle hängt. Anreizlage besonders prüfen: Herstellerdoku
ist Tier 1 für die eigenen Fakten, aber selten neutral im Vergleich zur Konkurrenz.

## Tiefenrecherche

Ein Thema mit mehreren Teilfragen, die sich gegenseitig bedingen (Ursache, Kontext,
Folgen). Läuft in mehreren Runden: erste Runde grob (Register + freie Suche), zweite
Runde vertieft die Lücken, die Runde eins offen gelassen hat. Konfidenz pro Teilfrage
wird einzeln getrackt, nicht als ein globaler Wert für das ganze Thema.

## Aktualitäts-Check / Delta-Recherche

Ein Thema, zu dem bereits eine Wissensdatei existiert. Kein Neuaufbau — siehe
`references/delta-mode.md`. Nur, was sich seit dem letzten Stand geändert hat oder neu
hinzugekommen ist, wird recherchiert; der Rest wird aus der Wissensdatei übernommen und
im Bericht als „Bekannt" ausgewiesen.

## Konfidenz-Tracking (gilt für alle Typen)

Jeder Claim trägt implizit eine Konfidenz durch sein Tier: Tier 1/2 = belastbar,
Tier 3 = vorläufig. Ein Claim, der beim Verifikations-Pass (`spotcheck.py`) nicht
standhält, verliert seine Konfidenz unabhängig vom ursprünglichen Tier — die Markierung
„VERWORFEN nach Spotcheck" sticht das Tier-Tag.

## Prose-first

Der Bericht ist Fließtext mit eingebetteten Claim-Tags, keine reine Tabelle und kein
Bullet-Friedhof. Aufzählungen dort, wo eine Liste wirklich eine Liste ist (mehrere
gleichrangige Optionen); sonst Prosa, die die Tags trägt, ohne von ihnen erschlagen zu
werden.
