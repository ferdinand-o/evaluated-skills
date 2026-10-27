# Third-party notices

This repository is licensed under the [MIT License](LICENSE). Parts of it are
adapted or translated from the MIT-licensed projects below. Their copyright and
permission notices are reproduced here as the MIT License requires. Skill files
under `skills/` are mirrored to `.claude/skills/` by `scripts/sync_skills.py`; the
notices apply to those generated copies as well.

## obra/superpowers

<https://github.com/obra/superpowers> — MIT License

Adapted, or translated from English into German:

| File | What was taken |
| --- | --- |
| `skills/debug-ledger/SKILL.md` | the "iron law" (no fix proposal without a tested hypothesis) and the anti-rationalisation table, from `systematic-debugging` |
| `skills/debug-ledger/references/escalation.md` | the three-failed-fixes rule, from `systematic-debugging` |
| `skills/skill-forge/references/form-selection.md` | "Match the Form to the Failure", from `writing-skills` |
| `skills/impl-plan/references/reviewer-prompt.md` | the plan-reviewer prompt, from `writing-plans` |
| `skills/impl-plan/references/task-patterns.md` | the TDD five-step task pattern and two checklists, from `writing-plans` |
| `skills/subagent-dev/SKILL.md` | the plan header line format, from `writing-plans` |

Other mentions of superpowers in this repository (routing tables, the
`setup-user` gap analysis) only name its skills for comparison. No text is
taken from it there.

```
MIT License

Copyright (c) 2025 Jesse Vincent

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## samber/cc-skills (skill `deep-research`)

<https://github.com/samber/cc-skills> — MIT License

| File | What was taken |
| --- | --- |
| `skills/verified-research/SKILL.md` | process skeleton, confidence tracking and prose-first approach (adapted; the source registry, trust tiers, verification pass and delta mode are new) |
| `skills/verified-research/references/research-types.md` | the research-type distinction, shortened and rewritten |

```
MIT License

Copyright (c) 2026 Samuel Berthe

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Acknowledgement only

**anthropics/skills, `skill-creator`** (Apache License 2.0) — the trigger-eval
procedure described in `skills/skill-forge/references/evals.md` (about twenty
realistic queries, roughly half of them near-misses that must not trigger) follows
the idea of that skill. The text and the examples are our own and nothing is copied,
so no licence obligation applies. Credit is given because the idea is theirs.
