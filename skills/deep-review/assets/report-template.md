<!-- skill: deep-review | schema: 1 | generated: Hauptagent nach assets/report-template.md | run: <lauf> | range: <range aus plan.json> | profile: <profil> | focus: <fokus> | tool: <werkzeug> -->
# deep-review <range aus plan.json>
<!-- Ausfüllen: range wörtlich aus plan.json, beim Wurzel-Commit nur die SHA von ZIEL. tool wie bei record: /code-review, /security-review, Review ohne /code-review oder Review ohne /security-review. Je Fund eine Zeile - `datei:zeile` — Zusammenfassung, bei line null - `datei` — Zusammenfassung; ohne Funde entfällt die Zeile. Je Paket eine Tabellenzeile, bei packets [] keine. -->
<!-- Gegenstellen: Zahl aus counterparts; ein Paket nur aus Dateien ohne Sammler bekommt – (nicht gesammelt: Sprache), Fokus quality – (nicht gesammelt: Fokus quality). Hinweise: je Eintrag von notes Paket, kind und Dateien. Hinweise, Übernommen und Nicht geprüft sind je eine Zeile, sonst keine. Bei split: false gilt eine Grenze von REPORT_BASE_LINES (20) Zeilen plus einer je Fund, die Kopfzeile nicht gezählt, diese Kommentare gezählt. -->

Funde: <N>
- `<datei>:<zeile>` — <Zusammenfassung>

| Paket | Dateien | Zeilen | Gegenstellen | Funde |
| --- | --- | --- | --- | --- |
| <p1> | <Zahl> | <geänderte Zeilen> | <Zahl oder – (nicht gesammelt: Sprache)> | <Zahl> |

- Hinweise: <notes je Paket oder keine>
- Übernommen (--since): <n> Dateien aus <Läufe>, <m> Funde
- Nicht geprüft: <Grund> (<n>), … — Dateien in plan.json not_reviewed
- Abdeckung: <a>/<b> — <vollständig|unvollständig>

Dass je Paket ein Review lief, ist Auskunft des Hauptagenten, kein Beleg; belegt ist nur, was `audit` an angenommenen Ergebnissen zählt.
`--max-findings all` hebt nur die Kappung der Funde je Review auf und belegt nicht, dass kein Fehler übrig blieb. Es bleibt danach als Wahl des Nutzers gesetzt, und `/code-review` ohne Stufe nimmt die zuletzt getippte Stufe; deep-review setzt nichts zurück, zurück geht es mit `/code-review --max-findings default`.
