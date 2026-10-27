# Documentation index

Most documents here are in German. This page says what each one is for, so you know
which to read and which are records.

## Conventions — read these

| Document | Purpose |
| --- | --- |
| [`artifact-header.md`](artifact-header.md) | the header line every generated artifact carries, and the rule for consumers |
| [`skill-building-pitfalls.md`](skill-building-pitfalls.md) | failure classes found while building skills |
| [`known-limits.md`](known-limits.md) | known limits of the eval harness and of individual evals |

The specifications themselves live in [`../specs/`](../specs/); Spec 00 is the shared
foundation.

## Working records — reference only

`docs/superpowers/` holds the records of how each skill was built. They are kept
because they back the claims in the specs and reports, not because you need them to
use the skills.

| Folder | Contents |
| --- | --- |
| `superpowers/plans/` | implementation plans, one per skill or change |
| `superpowers/reports/` | build report per skill: what was measured and what was not |
| `superpowers/specs/`, `superpowers/validation/` | design and baseline of the first skill (`cad-parts`), built before the spec process |

The folder name is part of the contract: `impl-plan` writes plans to
`docs/superpowers/plans/`, and `skill-forge` and its lint read the reports from
`docs/superpowers/reports/`. Moving the folder means changing those skills.

## Assessments

| Document | Purpose |
| --- | --- |
| [`assessment-brainstorming.md`](assessment-brainstorming.md) | assessment: is an own successor to `superpowers:brainstorming` worth building? |
| [`assessment-writing-skills-writing-plans.md`](assessment-writing-skills-writing-plans.md) | assessment: own successors to `superpowers:writing-plans` and `superpowers:writing-skills` |
