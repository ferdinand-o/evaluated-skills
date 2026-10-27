# cc-skills

A collection of Claude skills, shipped as four Claude Code plugins. Every skill comes
with a written specification and an eval suite, and has to prove in a baseline run
that it adds something over the bare model.

> **Language.** The skills, specs and docs are written in German, and skill
> descriptions trigger on German phrases ("neues Feature", "Bug", "Übergabe", …). The
> README, `CONTRIBUTING.md` and the notices are in English. Issues in English or German
> are both fine.

## Repository layout

| Folder | Contents |
| --- | --- |
| `skills/` | the skills (one folder each, with a `SKILL.md`) |
| `specs/` | specifications; Spec 00 is the shared foundation |
| `evals/` | eval definitions and fixtures |
| `evals-templates/` | template measurements outside the eval contract (run with `--evals-dir evals-templates`) |
| `evalkit/` | the shared eval harness |
| `docs/` | conventions, plans, reports (see [`docs/README.md`](docs/README.md)) |
| `.claude/skills/` | generated project copies for working on this repo, never edit by hand |
| `scripts/` | repo tooling, including `sync_skills.py` for the project copies |

## Install as plugins

The repo is a Claude Code marketplace (`.claude-plugin/marketplace.json`) with four
plugins. All use the repo root as source and load only the skills in their `skills`
list; once installed, skills are namespaced by plugin, e.g. `cc-dev:handoff`. From
Claude Code 2.1.275 on, one line per plugin adds marketplace and plugin together:

- `/plugin install cc-dev --marketplace ferdinand-o/cc-skills` — development, always
  on: architecture-map, debug-ledger, dev-report, feature-spec, handoff,
  rest-api-architect, review-context, sql-schema-architect, subagent-dev, test-first,
  testing-strategy, work-plan.
- `/plugin install cc-setup --marketplace ferdinand-o/cc-skills` — Claude Code setup,
  **CLI only**: setup-repo and setup-user, available only as `/cc-setup:setup-repo`
  and `/cc-setup:setup-user`. Both carry `disable-model-invocation`, which claude.ai
  (web) does not know; on the web, add only `cc-dev`, `cc-ui` and `cc-knowledge`.
- `/plugin install cc-ui --marketplace ferdinand-o/cc-skills` — UI, **off by default**
  (`defaultEnabled: false`): enterprise-ui, mobile-audit, motion-landing,
  ui-architect. Enable it per frontend repo in that repo's `.claude/settings.json` with
  `"enabledPlugins": {"cc-ui@cc-skills": true}`; the project setting wins over the
  `false` that the installation writes to the user settings.
- `/plugin install cc-knowledge --marketplace ferdinand-o/cc-skills` — knowledge,
  always on: exercise-forge, explain, human-prose, learning-coach, verified-research,
  visual-summary.

With older versions, first run `/plugin marketplace add ferdinand-o/cc-skills`, then
`/plugin install cc-dev@cc-skills` and so on. New commits arrive with
`/plugin marketplace update cc-skills`, followed by `/reload-plugins`.

**Migrating from the old `cc-skills` plugin.** Until Spec 20 the whole collection was
one plugin, `cc-skills@cc-skills`. The manifest lists it under `renames` as removed
(`"cc-skills": null`), so `/plugin marketplace update cc-skills` drops it. Then install
the new plugins:

```
/plugin marketplace update cc-skills
/plugin install cc-dev@cc-skills
/plugin install cc-setup@cc-skills
/plugin install cc-ui@cc-skills
/plugin install cc-knowledge@cc-skills
```

**In no plugin** are three skills, each with its reason in `.claude-plugin/excluded.json`:

- impl-plan and skill-forge apply only to specs and skills of this collection. They
  exist only as project copies under `.claude/skills/` and load when Claude Code runs
  in this repo.
- cad-parts is excluded because it needs an `stl-cad-server` MCP server.

**Project copies.** `.claude/skills/` holds ten skills for working on this repo:
impl-plan, skill-forge and eight from `cc-dev` (all except rest-api-architect and
sql-schema-architect). The original is always `skills/<name>/`;
`scripts/sync_skills.py` mirrors the skills in its `PROJECT_SKILLS` table, and
`python3 scripts/sync_skills.py --check` reports every copy that has drifted. The
committed `.claude/settings.json` turns `cc-dev@cc-skills` off inside this repo so the
eight skills do not appear twice.

`tests/test_marketplace.py` keeps manifest, `excluded.json` and copies in sync with
`skills/`: a new skill is listed in exactly one `skills` list or, with a reason, in
`.claude-plugin/excluded.json`, otherwise the test fails; skill-forge's lint rule
`plugin-membership` checks the same mapping. The test also checks the skills of the web
plugins against claude.ai's upload rules (frontmatter keys, `<`/`>` and length of the
description, exactly one `SKILL.md` per folder).

## Running the evals

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                                  # harness unit tests
.venv/bin/python run_evals.py --class contract    # cheap contract evals
.venv/bin/python run_evals.py --skill handoff     # everything for one skill
.venv/bin/python run_evals.py --skill handoff --without-skill   # baseline: same evals, nothing installed
```

Exit codes: `0` all green, `1` at least one eval failed, `2` harness error. With
`--without-skill` it is the other way round: `1` as soon as one eval passes without the
skill (it measures nothing the skill contributes), `0` if all fail. A run in which the
agent did not see the skill (with skill) or saw it anyway (without skill) is `2`, not
a result.

## Routing

Which skill for which occasion — the central matrix from Spec 00 §5. Every description
also carries a delimitation clause against its two strongest competitors.

| Occasion | Responsible | Not |
| --- | --- | --- |
| new feature, codebase exists | feature-spec | brainstorming (your own profile skill, not superpowers: no codebase link), work-plan (the *how* afterwards) |
| bug, failing test | debug-ledger | feature-spec |
| test plan, repo-type question | testing-strategy | test-first (the cycle *during* implementation), feature-spec (produces the test stubs, testing-strategy implements from them) |
| implement new behaviour, regression test after diagnosis | test-first | testing-strategy (which tests are missing), debug-ledger (diagnosis first), superpowers:test-driven-development (doctrine without evidence) |
| review a diff | `/code-review` (built in) | a dedicated review skill — see Spec 04, scope left open |
| security | `/security-review`, trailofbits | all skills of this collection |
| UI: style and tokens | ui-architect | enterprise-ui (product UI), motion-landing (motion) |
| UI: product surfaces, tables, forms | enterprise-ui | ui-architect (marketing/brand) |
| landing-page motion | motion-landing | ui-architect (style/tokens), enterprise-ui |
| broken on mobile, "does it work on a phone?" | mobile-audit | enterprise-ui / ui-architect / motion-landing — they *build* mobile with `references/mobile.md`, mobile-audit only checks |
| ad-hoc "summarise this" | visual-summary | dev-report (periodic), handoff (end of session) |
| explain a concept or topic (no code) | explain | learning-coach (session with retrieval), visual-summary (condenses what exists), architecture-map (codebase) |
| implementation plan for a spec | impl-plan | work-plan (other repos), brainstorming (your own profile skill, not superpowers: the spec comes first), subagent-dev (splits and dispatches the finished plan) |
| plan for work in any repo (spec, finding, task) | work-plan | impl-plan (specs of this collection), built-in plan mode (plan only in the conversation), subagent-dev (splits and dispatches the finished plan) |
| build or change a skill | skill-forge | skill-creator (outside this collection, its own eval schema), superpowers:writing-skills (discipline skills with pressure scenarios), impl-plan (the plan only) |
| write or rework a text that must not sound like a model | human-prose | setup-writing-style (builds the voice profile, in the user profile), visual-summary (condenses, does not change style), explain (explains, with its own answer contract) |
| end of session, handover | handoff | visual-summary, dev-report |
| set up or check your own Claude Code user scope | setup-user | `/statusline` (status line on request), setup-repo (repo, cloud, CI), handoff (saves the state) |
| set up or check a repo for Claude Code | setup-repo | setup-user (personal user scope), testing-strategy (which tests are missing), `/init` (CLAUDE.md without evidence) |

## Conventions

- [Artifact header and consumer rule](docs/artifact-header.md)
- [Spec 00 — artifact contract, evals, tiers and routing](specs/Spec%2000%20%E2%80%93%20skill-foundation.md)
- [Known limits of the eval harness](docs/known-limits.md)

## License and contributions

[MIT](LICENSE). Parts are adapted from other MIT-licensed projects; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Issues are welcome, pull requests are
not accepted — see [CONTRIBUTING.md](CONTRIBUTING.md).
