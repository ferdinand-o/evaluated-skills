---
name: feature-spec
description: Use when starting a new feature and a codebase already exists — scans the repo and existing decisions first, then drafts a complete spec with explicit `Annahme:` lines instead of interviewing. Triggers include "neues Feature", "bau mir X", "schreib eine Spec für …". Not for bugfixes or failing tests (use systematic-debugging) and not for breaking the finished spec into work packages (use superpowers:writing-plans).
---

# feature-spec — Draft-first Featurebeschreibung

**Scannen ist der erste Schritt, nicht Fragen.** Du legst einen vollständigen
Entwurf vor, bevor du den Nutzer etwas fragst — Ungesichertes markierst du,
statt es abzufragen.

## Die eiserne Regel

```
KEIN INTERVIEW, BEVOR DIE CODEBASE GESCANNT UND EIN ENTWURF STEHT.
```

Fragen sind die Ausnahme (siehe Fallback in Schritt 2), nicht der Einstieg.

## Ablauf

1. **Scannen.** Betroffene Module, vorhandene Muster, `docs/decisions.md`
   (Kopfzeile prüfen — Spec 00 §1 Konsumenten-Regel; fehlt sie oder passt das
   Schema nicht, scannst du trotzdem weiter und sagst, dass die Datei
   übersprungen wurde). Ein Widerspruch zwischen der Anfrage und einer
   entschiedenen Zeile gehört in den Entwurf, nicht ins Schweigen.
2. **Fallback prüfen.** Wären mehr als drei *zentrale* Annahmen nötig
   (Kernentscheidungen, die den Ansatz tragen — nicht Details), stell zuerst
   zwei bis drei entscheidende Fragen. Sonst weiter zu Schritt 3. Interview
   ist die Ausnahme, nicht der Weg.
3. **Entwurf schreiben** nach `assets/spec-template.md`, Feldregeln in
   `references/spec-schema.md`, nach `docs/specs/wip/<feature>.md`. Kündige
   die Erstanlage an (Spec 00 Bootstrap-Regel) und trag die Artefakt-
   Kopfzeile ein.
4. **Vorlegen.** Der Nutzer reagiert auf den Entwurf — widerspricht
   Annahmen, beantwortet offene Fragen. Kein „ist das ok?" ohne Inhalt.
5. **Stubs exportieren**, sobald der Entwurf steht:
   ```bash
   python skills/feature-spec/scripts/export_stubs.py docs/specs/wip/<feature>.md
   ```
   Verweigert der Export (Prosa-Kriterien, fehlende Non-Goals,
   Slug-Kollision), meldet er jede betroffene Zeile — das ist der Contract,
   kein Absturz. Trag den Grund dem Nutzer vor und korrigiere den Entwurf,
   statt ihn zu übergehen.
6. **Ernten.** Grundsatzentscheidungen aus dem fertigen Entwurf (Kriterien in
   `references/decisions-guide.md`) als Zeile nach `docs/decisions.md`
   anhängen — Feature-Details nicht. Hat die Datei danach ≥30 Einträge, sag
   das im Output dazu; gliedere nicht automatisch um.
7. **Spec ist wegwerfbar.** Sie lebt in `docs/specs/wip/`, bis implementiert
   ist; danach darf sie gelöscht werden. Was bleibt: die Stubs im Testbaum
   und die geernteten Zeilen in `docs/decisions.md`.

## Contract

- **Pflichtfelder** (siehe `references/spec-schema.md`): Problem, Non-Goals
  (mindestens ein „bauen wir nicht"), Annahmen (einzeln als `Annahme:`-Zeile,
  nie gebündelt), Ansatz mit Bezug auf existierende Module, Akzeptanz-
  kriterien ausschließlich als Given/When/Then, offene Fragen mit
  Entscheider.
- `export_stubs.py` ist ein **G2**-Gate (Spec 00 §4): Es fällt ein
  mechanisches Urteil über die Given/When/Then-Form und die Non-Goals-
  Pflicht — der Aufruf bleibt Teil deines Workflows, kein Hook erzwingt ihn.
  Es **meldet Verstoß**, es blockiert nicht.
- Verweigert der Export, schreibt er **keine** Stub-Datei — auch nicht für
  Kriterien, die sauber geparst hätten. Ein halber Export sieht aus wie ein
  voller und ist deshalb schlimmer als keiner.
- Re-Export überschreibt eine Stub-Datei nur, solange sie noch `# spec-stub:
  <slug>` als Kopfzeile **und** `@pytest.mark.skip("stub: noch nicht
  implementiert")` trägt. Fehlt einer der beiden Marker, bleibt die Datei
  unangetastet — der Export meldet sie als „übersprungen (bereits
  implementiert)".
- Jede `Annahme:`-Zeile bleibt einzeln widersprechbar — keine Sammel-Annahme,
  die mehrere Entscheidungen bündelt.
- `docs/decisions.md` bleibt flach. Ab 30 Einträgen nennst du das im
  Output — du gliederst nicht selbst um, das ist eine bewusste Handlung des
  Nutzers (G1, Selbstauskunft, kein Skript zählt das).

## Anti-Rationalisierungs-Tabelle

| Gedanke | Realität |
| --- | --- |
| „Der Nutzer weiß, was er will — Fragen sparen" | Unmarkierte Annahmen sind versteckte Fragen. Markieren, nicht raten. |
| „Non-Goals ergeben sich schon aus dem Ansatz" | Ohne explizites Nicht-Ziel wächst der Scope beim Implementieren. |
| „Kriterien als Checkliste reicht" | Was `export_stubs.py` nicht parsen kann, ist kein Kriterium. |
| „Der Entwurf ist offensichtlich vollständig" | Ohne markierte Annahmen ist „vollständig" ein ungeerdeter Anspruch. |
| „docs/decisions.md ist eh unübersichtlich, ich räum das kurz auf" | Umgliedern ist eine bewusste Handlung des Nutzers, keine Nebenwirkung deines Laufs. |
| „Die Spec ist wegwerfbar, also spar ich mir die Kopfzeile" | Wegwerfbar heißt kurzlebig, nicht ungekennzeichnet. |
| „Der Export meckert nur wegen Formatierung — ich schreib die Stubs selbst" | Dann bewacht nichts mehr den Contract. Korrigiere den Entwurf, umgeh nicht das Skript. |

## Abgrenzung

- **systematic-debugging** *(Spec 01, geplant)* — Bug, Testfehler. Hier
  greift diese Skill nicht.
- **superpowers:writing-plans** — Zerlegung der fertigen Spec in
  Arbeitspakete. Diese Skill endet bei Spec plus Stubs, sie zerlegt nicht.
- Ohne existierende Codebase (leeres Repo, neues Projekt) ist Draft-first
  ungeerdet — dort ist ein Interview-Muster überlegen, nicht diese Skill.
- Diese Skill braucht keinen mechanischen Codebase-Scanner: „Scannen" heißt
  hier Lesen mit den Standardwerkzeugen, kein eigenes Skript.
