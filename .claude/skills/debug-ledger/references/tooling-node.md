# Tooling: Node / TypeScript

## node --inspect-brk

```bash
node --inspect-brk node_modules/.bin/vitest run tests/login.test.ts
```

Pausiert vor der ersten Zeile und wartet auf einen Inspector-Client
(`chrome://inspect`, VS Code, oder `node --inspect-brk` gefolgt von
`Ctrl+Click` auf die geloggte `devtools://...`-URL). Für einen laufenden
Prozess ohne Neustart: `kill -SIGUSR1 <pid>` aktiviert den Inspector nachträglich
auf demselben Port wie `--inspect`.

## Vitest-Debugging ohne Editor

```bash
vitest run tests/login.test.ts --reporter=verbose --no-coverage
```

`--reporter=verbose` zeigt jeden Testschritt statt nur des Fehlschlags — nützlich,
um die Grenze zu finden, an der ein asynchroner Ablauf abweicht, bevor man
überhaupt einen Breakpoint setzt. Für Timing-abhängige Fehler:

```bash
DEBUG=vitest:* vitest run tests/login.test.ts
```

## Stack-Traces bei unbehandelten Promise-Rejections

```bash
node --trace-warnings --unhandled-rejections=strict node_modules/.bin/vitest run
```

`--unhandled-rejections=strict` lässt den Prozess bei einer nicht abgefangenen
Rejection abstürzen statt sie stillschweigend zu verschlucken — der Stack-Trace
geht dann ins Evidenz-Log statt zu verschwinden.

## Degradation

Kein Node im PATH (`command not found`) → sichtbar melden und auf die
Python-Rezepte verweisen, falls der Stack gemischt ist, oder direkt beim Nutzer
nachfragen, welcher Stack tatsächlich läuft. Nie raten, welches Tooling passt.
