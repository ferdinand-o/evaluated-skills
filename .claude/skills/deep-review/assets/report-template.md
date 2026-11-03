<!-- skill: deep-review | schema: 1 | generated: Hauptagent nach assets/report-template.md | run: <lauf> | range: <range aus plan.json> | profile: <profil> | focus: <fokus> | tool: <werkzeug> -->
# deep-review <range aus plan.json>
<!-- Ausfüllen: range wörtlich aus plan.json, beim Wurzel-Commit nur die SHA von ZIEL. tool wie in results/<id>.json unter _meta.tool gespeichert, etwa /code-review (record speichert code-review so), /security-review, Review ohne /code-review oder Review ohne /security-review. Je Fund eine Zeile - `datei:zeile` — Zusammenfassung, bei line null - `datei` — Zusammenfassung; ohne Funde entfällt die Zeile. Je Paket eine Tabellenzeile, bei packets [] keine. -->
<!-- Gegenstellen: Zahl aus counterparts; ein Paket nur aus Dateien ohne Sammler bekommt wörtlich Gegenstellen nicht gesammelt (Sprache), Fokus quality Gegenstellen nicht gesammelt (Fokus quality). Nicht geprüft: zuerst jeder Grund, der Quellcode betrifft (Quelldatei mit Nicht-UTF-8-Pfad — nicht reviewt), mit seinen Dateien in Klammern, wie sie in plan.json not_reviewed stehen; Doku, Bilder, Delphi-Projekte und Ressourcen, Testdateien und Nicht-UTF-8-Pfade ohne Quellcode nur mit ihrer Zahl. -->
<!-- Hinweise, Übernommen und Nicht geprüft stehen immer da, je genau eine Zeile; ohne Inhalt steht dort keine. Hinweise: je Eintrag von notes Paket und kind, Dateien in Klammern, Einträge mit ; getrennt; audit prüft, dass jedes Paar aus Paket und kind dasteht. Übernommen: n = Dateien mit reused_from in file_keys, m = ihre findings plus outside-Elemente; audit prüft beide Zahlen. Bei split: false gilt eine Grenze von REPORT_BASE_LINES (20) Zeilen plus einer je Fund; die Kopfzeile und Zeilen nur aus einem HTML-Kommentar zählen nicht. -->

Funde: <N>
- `<datei>:<zeile>` — <Zusammenfassung>

| Paket | Dateien | Zeilen | Gegenstellen | Funde |
| --- | --- | --- | --- | --- |
| <p1> | <Zahl> | <geänderte Zeilen> | <Zahl oder Gegenstellen nicht gesammelt (Sprache)> | <Zahl> |

- Hinweise: <paket> <kind> (<dateien>); … oder keine
- Übernommen (--since): <n> Dateien aus <Läufe>, <m> Funde oder keine
- Nicht geprüft: <Grund einer Quelldatei> (<datei>, …), <übriger Grund> (<n>), … — Dateien in plan.json not_reviewed
- Abdeckung: <a>/<b> — <vollständig|unvollständig>

Dass je Paket ein Review lief, ist Auskunft des Hauptagenten, kein Beleg; belegt ist nur, was `audit` an angenommenen Ergebnissen zählt.
`--max-findings all` hebt nur die Kappung der Funde je Review auf und belegt nicht, dass kein Fehler übrig blieb. Es bleibt danach als Wahl des Nutzers gesetzt, und `/code-review` ohne Stufe nimmt die zuletzt getippte Stufe; deep-review setzt nichts zurück, zurück geht es mit `/code-review --max-findings default`.
