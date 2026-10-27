# Contributing

**Issues are welcome. Pull requests are not accepted.**

## Why no pull requests

This collection is built spec-first by one maintainer: every skill follows a written
spec, is measured by evals, and has generated copies under `.claude/skills/`. Reviewing
outside changes against that process costs more than it returns, so pull requests are
closed without review. That is not a judgement on their quality.

You are free to fork the repository and change it under the terms of the
[MIT License](LICENSE).

## What helps in an issue

- A skill that fires when it should not, or does not fire when it should (include the
  prompt you used).
- A skill that gives wrong or contradictory instructions.
- A failing eval or test on a clean checkout (include the command and its output).
- An idea for a new skill or a change to an existing one. Say what goes wrong today
  without it.

For bugs, please include the plugin and skill name, the commit or marketplace version,
your Claude Code version, and the steps to reproduce. English or German is fine.

I read issues when I have time and cannot promise an answer or a fix.

## Security

If you find something that could harm users of these skills or scripts, do not post
details in a public issue. Use GitHub's private vulnerability reporting on this
repository if it is enabled; otherwise open an issue that only asks for a contact
channel.
