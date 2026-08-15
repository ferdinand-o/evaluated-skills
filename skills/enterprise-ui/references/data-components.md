# Data components

Tables, forms, filtering, and navigation are where an enterprise surface earns its keep — this is the load-bearing 80% of daily product use, not the first-impression 20%. The patterns below are deliberately conventional: familiar beats clever here, because the user is scanning hundreds of rows or filling out the same form for the hundredth time, not admiring the interaction. Every example uses token-mapped utilities only (`bg-surface`, `text-fg`, `border`, `h-row`, …) — see `references/tokens.md` for the token architecture these build on.

## Data tables

**Alignment.** Text is left-aligned. Numbers are right-aligned with `tabular-nums` so digits line up on a fixed width and decimal points align down the column; use `--font-mono` for the numeric run (see `references/tokens.md#numbers--fonts`). Dates and IDs are monospaced wherever their values vary in digit count (order numbers, hashes, timestamps) — monospacing is what keeps a scanned column from jittering.

```tsx
<td className="px-3 py-2 text-right font-mono tabular-nums text-fg">
  {new Intl.NumberFormat("de-DE").format(value)}
</td>
```

**Sorting, filtering, pagination.**

| Row count | Approach |
|---|---|
| Roughly < 1,000 rows | Client-side sort/filter/paginate — the whole dataset is already in memory, so round-tripping to the server just adds latency. |
| Roughly ≥ 1,000 rows | Server-side — push sort/filter/page state into the request; don't ship the full table to the client to solve it there. |

Show the active sort as an indicator in the column header (arrow/chevron, not a separate control). Filters live in the toolbar above the table, not inside the table itself — see [Filtering & search](#filtering--search) for that pattern in full.

**Selection.** A checkbox column on the left, with a header checkbox that means "select all *on this page*" (label it that way, or offer an explicit "select all N matching filter" affordance if the dataset is paginated — silently selecting only the visible page while implying everything is a common source of destructive-bulk-action bugs). Once one or more rows are selected, a bulk-action bar appears — anchored to the toolbar or the bottom of the viewport — showing the count selected and the actions available on that selection. Don't leave bulk actions buried in a per-row menu once a multi-row selection exists; that's the point of having a selection state.

**Sticky positioning.** The header row is sticky by default — a header that scrolls away is a header the user has to scroll back to reread on every glance. On wide tables (many columns, horizontal scroll), the first column (usually the row's primary identifier) can optionally stick to the left edge so identity stays visible while the rest of the row scrolls under it.

**Virtualization.** Once a table can render roughly 100+ rows in the viewport, virtualize with `@tanstack/react-virtual` rather than mounting every row — an unvirtualized table of that size is a reliable way to tank interaction latency and layout-thrash on scroll. Below that threshold, virtualization is unnecessary complexity; don't reach for it pre-emptively on a table that will only ever show a couple dozen rows.

**Row actions.** Right-aligned, collapsed into a single `…` overflow menu (Radix Dropdown) rather than a row of icon buttons. A row of five icon buttons repeated down a hundred rows is visual noise and a mis-click hazard; a single trigger per row that opens the same menu keeps the row scannable and the destructive actions (delete, revoke) out of accidental reach.

**Column resize / visibility.** Optional, and only where the surface actually needs it (wide operational tables, power-user tooling) — reach for `@tanstack/react-table`'s column-sizing and visibility APIs rather than hand-rolling drag logic. Most tables don't need this; add it when users are actually asking to hide or resize columns, not by default.

## Forms

**Label placement.** Labels sit above the field (top-aligned), not to the side — top-aligned labels scan faster because the eye travels in one direction (down) instead of zig-zagging between a label column and a field column. Mark required fields, not optional ones; in most enterprise forms most fields are required, so marking the minority (optional) is less visual noise than marking the majority.

**Validation timing.** Validate on blur and on submit — **never on keystroke.** Keystroke-level validation shows an error while the user is still mid-word (e.g. flagging an email as invalid before they've typed the `@`), which reads as the UI complaining before it has grounds to. On-blur catches the mistake as soon as the user moves on from the field; on-submit is the final gate.

Errors render **below** the field they belong to, connected via `aria-describedby` so assistive tech announces the error when the field receives focus, and the field's border switches to the `--danger` token. The border tint is reinforcement, not the signal itself — the error text is what carries the meaning, since color alone is never a sufficient signal on its own.

**Error message content.** State what's wrong *and* how to fix it — "Enter a date in the future" tells the user what to do next; "Invalid date" tells them nothing they didn't already suspect. Every validation message should pass the test: *could a first-time user act on this without guessing?*

**Multi-step (wizard) forms.** Show progress (step N of M, or a stepper) so the user knows how much is left. Validate per step, not only at the final submit — surfacing five steps' worth of errors at once on the last screen is worse than catching each as it happens. Going back must never discard already-entered data; a "back" that wipes state is treated by users as data loss, not navigation.

**Saving.** Default to an explicit "Save changes" action — the user should know when their data is committed. Autosave is fine, but only paired with a clear, visible status ("Saved", "Saving…", "Unsaved changes") — silent autosave leaves the user unsure whether their edits survived. Keep `disabled` and `readOnly` distinct: `disabled` means *not interactable* (can't focus or submit its value — e.g. a field that doesn't apply given another field's value), `readOnly` means *readable but not editable* (still focusable/selectable/submittable — e.g. a system-generated ID shown for reference). Picking the wrong one breaks either keyboard access or the ability to copy the value.

**Spacing.** Vertical space between fields comes from `--field-gap` — not an ad hoc margin per form. This is one of the density-driven tokens (see `references/tokens.md#density-modes`), so a form automatically tightens under `data-density="compact"` without any per-component change.

## Filtering & search

The filter toolbar sits directly above the table (or list) it controls: search on the left, a filter trigger (opens a popover/panel of filter fields) next to it, and every currently active filter rendered as a removable chip so the current query is legible at a glance without opening the filter panel. A user should be able to tell what's filtering the view without a click.

**Saved views.** For filter combinations a user returns to repeatedly (my open tickets, this quarter's flagged transactions), let them save the current filter set as a named view rather than rebuilding it every session. Saved views turn a five-filter setup into a single click.

**Command palette.** For power-user tooling where fast keyboard-driven navigation matters, add a command palette (`⌘K` / `Ctrl+K`) built on `cmdk` for jumping between pages, records, and actions without leaving the keyboard. This is additive to, not a replacement for, the toolbar filters above — the palette is for *getting somewhere fast*, the toolbar is for *narrowing what's on screen*.

## Navigation

Persistent app-level navigation is either a **sidebar** or a **topbar** — pick one as the primary structure per product, don't run both as competing primary nav. Whichever is chosen, the active section must be unambiguous: apply `--accent-subtle` as the active item's background and `--accent-text` for its label/icon color, so the current location reads clearly against the neutral surrounding nav without relying on weight or an underline alone.

**Breadcrumbs** earn their place once the hierarchy goes more than two levels deep (e.g. Workspace → Project → Task → Subtask) — below that, a page title alone is enough, and breadcrumbs on a shallow hierarchy are just clutter repeating the sidebar.

**Master-detail** (a list on the left, the selected record's detail on the right, both visible at once) is the right pattern for edit-heavy workflows where a user is triaging or working through many records in sequence — it avoids a full-page navigation round-trip per record. Reach for a dedicated detail page instead when a record's detail view is heavy enough (many sections, its own sub-navigation) that splitting the viewport would cramp it.

## Sourcing primitives

Pull interactive primitives — dialog, dropdown, popover, tabs, and the table/form pieces referenced above — with `npx shadcn@latest add <component>`. **Never hand-write or hallucinate a primitive's markup from memory**; the CLI is the source of truth for the accessible interaction structure Radix provides underneath. After pulling a component, restyle it onto the token system: swap its default classes for token-mapped utilities (`bg-surface`, `border`, `text-fg`, etc.) and its default focus ring for the token-correct ring (see below) so the shipped component reads as this design system, not as shadcn's stock demo theme. Radix supplies the interaction and accessibility contract (focus trapping, keyboard nav, ARIA roles) for these primitives — that part stays as-is. **Never ship a primitive's stock visual identity** (default shadcn slate palette, default shadows) unrestyled; that is the single most common way a project ends up looking like every other shadcn tutorial instead of like this system.

When any of these primitives need a visible focus ring, use `ring-[var(--ring)]`. In this preset only `ringColor.DEFAULT` is set (no `ring` color key), so `ring-ring` is not a defined utility here — it emits nothing — while bare `ring`/`ring-2` fall back to Tailwind's stock blue; see the ring gotcha documented in `references/tokens.md#wiring-into-a-project`. For example, a Radix Dropdown trigger's focus-visible state:

```tsx
<button
  className="h-control rounded-md border bg-surface px-[var(--control-padding-x)] text-fg
             focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
>
  <MoreHorizontal className="size-4" />
</button>
```
