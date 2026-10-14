# Prüfpunkte — TypeScript und JavaScript

Gilt für Repos mit TypeScript oder JavaScript. Konformität, nicht Fehlersuche; geprüft
wird nur der Diff des Ziels. Format je Zeile: `- **<id>** — <Prüfpunkt> Quelle: <Quelle>`.

## Prüfpunkte

- **ts-test-for-export** — Ein neuer `export` (Funktion, Klasse, Komponente) wird von mindestens einem Test im Diff oder im Repo aufgerufen. Quelle: Spec 22, Abschnitt „Review" (Beispiel „neue öffentliche Funktion hat einen Test").
- **ts-dependency-in-manifest** — Ein neuer Import eines Pakets steht in `package.json`, Laufzeitcode unter `dependencies`, Werkzeuge und Tests unter `devDependencies`. Quelle: npm-Doku zu `package.json`, Abschnitte „dependencies" und „devDependencies", https://docs.npmjs.com/cli/v10/configuring-npm/package-json
- **ts-lockfile-with-manifest** — Ändern sich Abhängigkeiten in `package.json`, ändert sich das Lockfile des Repos im selben Diff (`package-lock.json`, `pnpm-lock.yaml` oder `yarn.lock`). Quelle: npm-Doku zu `package-lock.json`, https://docs.npmjs.com/cli/v10/configuring-npm/package-lock-json
