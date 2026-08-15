# Spec-Schema: Felder, Format, ein ausgefülltes Beispiel

Dieses Format ist kein Stilvorschlag — `scripts/export_stubs.py` parst es
mechanisch. Wer davon abweicht, bekommt beim Export eine Verweigerung statt
Stub-Dateien (siehe SKILL.md, Contract-Abschnitt).

## Pflichtfelder

| Feld | Überschrift | Pflicht | Was mechanisch geprüft wird |
| --- | --- | --- | --- |
| Problem | `## Problem` | ja | keine — reine Prosa, 2–3 Sätze |
| Non-Goals | `## Non-Goals` | ja | mindestens eine `- `-Zeile |
| Annahmen | `## Annahmen` | ja | keine — Konvention: jede Zeile beginnt mit `Annahme:` |
| Ansatz | `## Ansatz` | ja | keine — Prosa mit Bezug auf existierende Module/Pfade |
| Akzeptanzkriterien | `## Akzeptanzkriterien` | ja | jedes `### `-Kriterium braucht Given **und** When **und** Then |
| Offene Fragen | `## Offene Fragen` | ja | keine — Konvention: jede Zeile nennt einen Entscheider |

Nur **Non-Goals** und **Akzeptanzkriterien** sind mechanisch erzwungen — das
ist der Contract aus Spec 03: „Eine Spec ohne Non-Goals oder mit
Prosa-Kriterien ist unvollständig". Die übrigen Felder sind Doktrin, die
SKILL.md verlangt (G1), aber kein Skript prüft sie.

## Kopfzeile

Die erste nicht-leere Zeile jedes Spec-Entwurfs ist die Artefakt-Kopfzeile
aus `docs/artifact-header.md`:

```
<!-- skill: feature-spec | schema: 1 | generated: feature-spec Draft für "<Feature>" -->
```

## Feature-Titel

Direkt nach der Kopfzeile folgt `# Feature: <Name>`. `export_stubs.py` liest
diese Zeile für den Datei-Präfix der Stubs (`test_<feature>_<slug>.py`, alle
Bindestriche zu Unterstrichen normalisiert — Python-Modulnamen dürfen keine
Bindestriche enthalten). Fehlt die `# Feature:`-Zeile, versucht es die erste
`# `-Überschrift, danach den Dateinamen der Spec — beides ohne
Fehlermeldung, aber weniger lesbar. Explizit ist besser.

Der Dateiname des Entwurfs selbst folgt derselben Regel: `docs/specs/wip/
<feature>.md`, wobei `<feature>` der slugifizierte Feature-Titel ist (SKILL.md
Schritt 3) — nicht frei gewählt. Damit stimmt der Ablageort mit dem überein,
was `export_stubs.py` ohne `--feature`-Flag selbst aus der `# Feature:`-Zeile
herleiten würde.

## Non-Goals

Eine flache Liste. Mindestens eine Zeile — leer oder fehlend verweigert den
Export.

```markdown
## Non-Goals
- Kein plattformübergreifendes Settings-Sync — nur dieses Gerät.
- Keine Migration alter Formate.
```

## Akzeptanzkriterien

Jedes Kriterium ist ein `### `-Block mit einer flachen `- `-Liste direkt
darunter. Jede Zeile beginnt mit `Given`, `When`, `Then` oder `And`
(Groß-/Kleinschreibung egal), gefolgt von `:` oder Leerzeichen und dem Text.
`And` übernimmt die Kategorie der zuletzt genannten Zeile — nützlich für
mehrere Vorbedingungen oder mehrere Erwartungen.

```markdown
### Erinnerung wird verschickt
- Given eine Aufgabe hat ein Fälligkeitsdatum in 24 Stunden
- And der Nutzer hat Erinnerungen nicht deaktiviert
- When der geplante Erinnerungs-Job läuft
- Then verschickt der bestehende `EmailService` eine Erinnerungsmail
- And der Versand wird in `notifications_log` vermerkt
```

Was den Export verweigert:
- Der Block hat keine `- `-Liste (Fließtext statt Given/When/Then).
- Mindestens eine Zeile beginnt nicht mit Given/When/Then/And.
- `And` steht als erste Zeile eines Blocks (keine Kategorie zum Fortsetzen).
- Eine Kategorie fehlt ganz (z. B. kein `Then`).
- Zwei Kriterien erzeugen denselben Slug (aus dem Titel abgeleitet:
  klein geschrieben, Umlaute transliteriert, alles außer `a-z0-9` wird `-`).

Jede Verweigerung nennt die betroffene Zeilennummer — nicht nur „irgendwo
falsch", sondern die konkrete Stelle.

## Annahmen

Jede unabgesicherte Annahme steht als eigene Zeile, einzeln widersprechbar:

```markdown
## Annahmen
- Annahme: Erinnerungen laufen über den bestehenden `EmailService`, nicht
  über einen neuen Push-Kanal — widersprich, falls du Push willst.
- Annahme: „24 Stunden vorher" ist fix, nicht konfigurierbar pro Nutzer.
```

## Offene Fragen

```markdown
## Offene Fragen
- Soll eine bereits verschickte Erinnerung bei Terminverschiebung storniert
  werden? — Entscheider: du.
```

## Vollständiges Beispiel

```markdown
<!-- skill: feature-spec | schema: 1 | generated: feature-spec Draft für "Fälligkeits-Erinnerung" -->
# Feature: Fälligkeits-Erinnerung

## Problem
Aufgaben mit Fälligkeitsdatum werden verpasst, weil nichts an sie erinnert.
Nutzer merken es erst, wenn die Aufgabe schon überfällig ist.

## Non-Goals
- Kein plattformübergreifendes Settings-Sync — nur dieses Gerät.
- Keine SMS- oder Push-Kanäle, nur E-Mail über den bestehenden `EmailService`.

## Annahmen
- Annahme: Erinnerungen laufen über den bestehenden `EmailService`
  (`src/email.py`), nicht über einen neuen Kanal — widersprich, falls nein.
- Annahme: „24 Stunden vorher" ist fix, nicht konfigurierbar.

## Ansatz
Ein geplanter Job (analog zum bestehenden `src/scheduler.py`-Muster) prüft
stündlich fällige Aufgaben und verschickt bei Treffer eine E-Mail über
`EmailService.send()`. Versand wird in `notifications_log` vermerkt, damit
derselbe Job nicht zweimal an dieselbe Aufgabe erinnert.

## Akzeptanzkriterien

### Erinnerung wird verschickt
- Given eine Aufgabe hat ein Fälligkeitsdatum in 24 Stunden
- And der Nutzer hat Erinnerungen nicht deaktiviert
- When der geplante Erinnerungs-Job läuft
- Then verschickt `EmailService` eine Erinnerungsmail
- And der Versand wird in `notifications_log` vermerkt

### Keine doppelte Erinnerung
- Given eine Erinnerung wurde für diese Aufgabe bereits verschickt
- When der geplante Erinnerungs-Job erneut läuft
- Then verschickt `EmailService` keine zweite Mail für dieselbe Aufgabe

## Offene Fragen
- Soll eine verschickte Erinnerung bei Terminverschiebung storniert werden?
  — Entscheider: du.
```

Dieses Beispiel exportiert mit `export_stubs.py` sauber zwei Stub-Dateien:
`tests/test_faelligkeits_erinnerung_erinnerung_wird_verschickt.py` und
`tests/test_faelligkeits_erinnerung_keine_doppelte_erinnerung.py`.
