# Eskalation

Zwei getrennte Schwellen. Die erste schaltet das Ledger von Mini auf Voll um,
solange die Ursache noch offen ist. Die zweite gilt *innerhalb* des vollen
Prozesses und stellt die Architektur infrage, wenn der Fix selbst wiederholt
scheitert.

## Schwelle 1: Mini → Voll (`new_ledger.py --escalate`)

Eines der vier Signale reicht, keine Selbsteinschätzung „ist doch nicht so
schlimm":

1. **Zweiter fehlgeschlagener Fixversuch.** Der erste Versuch war ein
   begründeter Schuss — beim zweiten braucht es Evidenz, keine dritte Vermutung.
2. **Multi-Komponenten-Verdacht.** Der Bug könnte an einer Grenze zwischen
   zwei Layern liegen (CI → Build, API → Service → DB, Umgebungsvariable über
   mehrere Prozesse). Instrumentierung an den Grenzen ersetzt Raten.
3. **Kein zuverlässiges Repro.** Wenn das Symptom nicht bei jedem Lauf
   auftritt, ist das Mini-Ledger zu klein für das, was als Nächstes kommt
   (Evidenz über mehrere Läufe sammeln).
4. **Nutzer meldet „immer noch kaputt".** Der vorherige Fix hat nicht
   gehalten — das ist kein neuer Bug, sondern ein Indiz, dass die erste Ursache
   nicht die echte war.

## Schwelle 2: 3 Fixversuche → Architekturfrage

Adaptiert aus [obra/superpowers](https://github.com/obra/superpowers),
`skills/systematic-debugging/SKILL.md` — MIT License, Copyright (c) 2025 Jesse Vincent.

```
Fix Nr. 3 schlägt fehl → STOPP. Nicht Fix Nr. 4 versuchen.
```

Das Muster, das eine Architekturfrage statt eines vierten Fixes verlangt:

- Jeder Fix deckt an anderer Stelle neuen geteilten Zustand / neue Kopplung auf.
- Jeder Fix bräuchte „nur noch" einen größeren Umbau, um wirklich zu halten.
- Jeder Fix erzeugt ein neues Symptom, statt das alte zu beheben.

Das ist kein Zeichen für eine widerlegte Hypothese — das Ledger sammelt bis
hierhin drei Zeilen in der Hypothesen-Tabelle, alle mit Verdict, keine mit
„Bestätigt, Fix hält". Wenn das Muster passt: Root-Cause-Feld offen lassen,
stattdessen im Ledger vermerken, dass eine Architekturentscheidung ansteht, und
das mit dem Nutzer klären, bevor ein vierter Fix entsteht.

## Anti-Rationalisierung für diese Schwelle

| Gedanke | Realität |
| --- | --- |
| „Noch ein Versuch, dann passt es" | Genau der Gedanke nach Fix 2. Nach Fix 3 ist es ein Muster, kein Pech. |
| „Der Umbau ist zu groß, ich mach nur den kleinen Patch" | Der kleine Patch ist Fix 4 — derselbe Fehler, den die Schwelle verhindern soll. |
