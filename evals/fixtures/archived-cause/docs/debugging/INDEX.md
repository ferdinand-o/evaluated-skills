<!-- skill: debug-ledger | schema: 1 | generated: python skills/debug-ledger/scripts/new_ledger.py --resolve docs/debugging/2026-07-01-login-haengt.md --cause "cache_key() kuerzt den Nutzernamen auf 8 Zeichen; zwei Nutzer mit gleichem Praefix kollidieren und blockieren sich gegenseitig" -->

# Debugging-Archiv

Eine Zeile pro gelöstem Fall: Symptom → Ursache. Wird nie automatisch
umgegliedert oder geprunt (siehe SKILL.md).

- Login hängt beim Start für manche Nutzer → cache_key() kürzt den Nutzernamen auf 8 Zeichen; zwei Nutzer mit gleichem Präfix kollidieren und blockieren sich gegenseitig ([2026-07-01-login-haengt.md](docs/debugging/2026-07-01-login-haengt.md))
