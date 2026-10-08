---
name: gate-demo
description: Use when a commit message needs the ticket id in front. Not for writing the commit itself (use handoff).
---

# gate-demo

## Ablauf

1. Ticket-ID aus dem Branch-Namen lesen.
2. Vor die Commit-Message setzen.

## Contract

- Jede Commit-Message beginnt mit der Ticket-ID.
- Der Lint blockiert den Commit, wenn sie fehlt.

## Abgrenzung

- **handoff** — Sitzungsende, nicht Commit.
