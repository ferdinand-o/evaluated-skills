# States & microcopy

A data view that only renders its happy path is unfinished, not "done for now." Every table, form, chart, and dashboard widget in this system ships loading, empty, error, and permission states as part of the same unit of work — not as a follow-up ticket. This file is the checklist for which states exist, what each one looks like, and the exact words to put in them. It builds on the tokens in `references/tokens.md` and the table/form patterns in `references/data-components.md`; `references/charts.md` defers to this file for its own chart-specific states.

## The state matrix

Every data view — a table, a form, a detail page, a dashboard widget, a chart — needs to answer the same six questions before it ships:

- **Loading** — is the data still arriving?
- **Empty** — is there genuinely nothing to show, and if so, which of the three empty reasons (first-run, no-results, filtered-empty — see [Empty](#empty)) applies?
- **Error** — did the request fail, and is that failure scoped to one field/block (inline) or the whole view (page-level)?
- **Partial / optimistic** — did *some* of the view load while another part failed or is still in flight?
- **No-permission** — can the current user even see this data?
- **Offline / stale** — is what's on screen still current, or served from a cache the app can no longer refresh?

Treat this as a literal pre-ship checklist per surface, the same way the Pre-Flight block in `SKILL.md` treats tokens and density as non-negotiable inputs. A surface that has an answer for five of the six and shrugs at the sixth ships an unfinished state, not a finished one with a known gap.

Not every surface needs every state at the same intensity — a static settings page with no fetch has no loading state, and a form the user always has access to has no no-permission state — but the absence has to be a deliberate call, not an oversight. The table below is the reference for how the six states typically show up per surface type; use it as a starting checklist, not a ceiling.

| Surface | Loading | Empty | Error | Partial/optimistic | No-permission | Offline/stale |
|---|---|---|---|---|---|---|
| **Table** | Skeleton rows matching column layout | First-run / no-results / filtered-empty (see below) | Page-level banner if the whole fetch failed; inline row-level flag for a single failed mutation | Row-level optimistic update with rollback on failure | Replace table with a no-access message, not an empty table | "Last updated" timestamp + stale badge if the refetch fails |
| **Form** | Skeleton fields while initial values load | Rare — a form is usually empty by design, not an empty *state* | Inline, under the field it belongs to (see `data-components.md#forms`) | Optimistic save with visible "Saving…" → "Saved" status and rollback on rejection | Disable the form and say why, don't silently 404 | Warn before submit if the session might be stale (e.g. edited a record that has since changed) |
| **Detail page** | Skeleton mirroring the page's section layout | N/A — a detail page implies the record exists | Page-level if the record fails to load; inline per section if only one section's data failed | Each section loads and errors independently — one broken section doesn't blank the page | Show "You don't have access to this record" instead of a 404 look-alike | Stale badge on the whole page if it was hydrated from cache |
| **Dashboard widget** | Per-widget skeleton, not a full-page spinner | "No data for this range/filter" inside the one widget | Isolated to the widget — a broken chart doesn't take down the dashboard (see [Partial / optimistic](#partial--optimistic)) | Widgets refresh independently; one slow widget doesn't block the rest | Omit the widget or show a locked/no-access placeholder, per product convention | Per-widget "Last updated" if refresh intervals differ across widgets |
| **Chart** | Skeleton in chart shape (see `charts.md#chart-states`) | "No data for this range" ≠ "all values are zero" | Inline error with retry, scoped to the chart | N/A in most cases — a chart either has its series or it doesn't | Same as widget: omit or lock, don't render an empty axis | Stale badge if the underlying series is cached |

## Loading

Two loading primitives, used for two different kinds of wait — mixing them up is one of the most common state-layer regressions:

- **Skeleton** — for any *content-shaped* wait: a table about to show rows, a card about to show a KPI, a chart about to show a series. The skeleton mirrors the real layout (same row height, same column widths, same card structure) so the transition from skeleton to content doesn't cause a layout jump, and so the user can already tell *what kind* of content is coming.
- **Spinner** — for *actions*, not content: a button mid-submit, a save-in-progress indicator. A spinner tells the user "something you triggered is working"; it has no opinion about layout because it doesn't replace a content region.

Reaching for a spinner where a table or card should be is the single most common way this state gets shortchanged — a centered spinner over blank white space tells the user nothing about what's about to appear and reads as unfinished the moment real content pops in underneath it.

A row skeleton, sized off the same `h-row` used by the real table rows so nothing jumps when content arrives:

```tsx
<div className="h-row animate-pulse rounded-md bg-subtle" />
```

For a full skeleton table, stack one of these per expected row and keep column proportions roughly matched to the real columns (a wide "name" skeleton next to a narrow "status" skeleton reads as a table before any data has loaded). For a button-busy spinner, keep the button's own dimensions fixed while swapping its label for a spinner icon — a button that resizes when it starts loading causes the same layout-jump problem skeletons exist to avoid.

## Empty

"Empty" is not one state — it's three, and each has different causes, different next actions, and therefore different copy. Collapsing them into a single generic "No data" message is a common shortcut that leaves the user unsure whether they're looking at a broken filter, a genuinely blank workspace, or a brand-new account. Each case gets its own copy and **exactly one** primary action — a list of three "helpful" links a genuinely stuck user has to read through defeats the point of an empty state.

- **First-run** — the user (or workspace) is new; the resource has never had any records. Explain the *value* of what would go here, then give a single primary action to create the first one. This is a teaching moment, not an error.
- **No-results** — the underlying collection is genuinely empty even with no filters applied (e.g. a "closed tickets" view for a team that hasn't closed any yet). Neutral, factual, no CTA pushed — there's nothing wrong, there's just nothing there yet.
- **Filtered-empty** — records exist, but the current filter/search combination matches none of them. This is the one case where the fix is obvious and mechanical: clear or loosen the filter. Always offer "Clear filters" as the primary action here — sending a filtered-empty user to a generic "create new" CTA when their actual problem is an overly narrow filter is a frequent misfire.

## Error

Split by scope, not by cause — the user experience question is "how much of the screen do I lose," not "was it a 500 or a timeout":

- **Inline** — one field or one block failed; the rest of the view is still usable. A single table cell, one dashboard widget, one form field's async validation. Contain the error to that region.
- **Page-level** — the entire view depends on data that failed to load; there is nothing else useful to show underneath. Reserve this for when the whole page really is unusable, not as a default for any failure.

Both scopes follow the same content rule: **state what happened and what to do next.** "Something went wrong" tells the user nothing they didn't already know from the fact that the screen is showing an error. "Couldn't load transactions. Retry" tells them what failed and gives them a next step. Always pair the message with a recovery action — Retry for a transient failure, a link back for a dead end — never leave an error as a dead-end statement with no way forward.

Never surface a raw stack trace, a raw HTTP status code, or an unformatted server error string to the user — those are for logs and error-tracking tools, not the UI. If the underlying cause is genuinely useful for a support conversation, put it behind a "Copy error details" affordance rather than in the primary message.

## Partial / optimistic

Two related but distinct patterns for handling a view that's only *partly* in a known-good state:

- **Optimistic UI** — apply the user's action to the screen immediately (mark the row updated, close the dialog, show the new value) rather than waiting for the server round-trip to confirm it. If the request then fails, roll the UI back to its prior state and surface the error — don't leave the optimistic change on screen next to a failure message, since that's a direct contradiction the user has to resolve themselves.
- **Isolated partial failure** — on a view built from multiple independent data sources (a dashboard of widgets, a detail page of sections), one section's fetch failing must not block or blank the rest. Each region owns its own loading/error state, scoped as described in [Error](#error). A dashboard where one broken KPI widget takes the entire page down with it is treating independent data as if it were one atomic unit, when it isn't.

Both patterns exist for the same reason: minimize how much of the interface a single failure is allowed to take down. The single most correct check to run for this state is "if this one call fails, what else on screen becomes unusable?" — the answer should be "nothing, or as little as possible."

## No-permission

A user missing the rights to see or act on something needs to be told that plainly — not shown a blank page that looks like a bug, not shown a 404 that implies the resource doesn't exist, and never shown a control that's disabled with no explanation attached. Say directly that access is missing, and say who to ask for it (a role, a workspace admin, a specific contact path) — "you don't have access" without a next step just relocates the dead end instead of removing it.

Never ship a disabled button, hidden-but-referenced action, or grayed-out row with no accompanying text explaining why it's inert. A user who can't tell *why* a button won't respond assumes it's broken, not that they lack permission — that's a support ticket the copy could have prevented.

## Offline / stale

Data on screen that the app can no longer verify as current — because the network dropped, a background refresh failed, or the view is being served from a cache — needs to say so, not silently keep displaying numbers as if they were live. Two concrete signals:

- **A visible "Last updated" timestamp**, so the user can judge staleness for themselves rather than having to guess whether what they're looking at is seconds or hours old.
- **A reconnect/stale indicator** when the app detects it's offline or a refresh has failed — a small persistent badge, not a disruptive full-screen takeover, since the data is still usable, just possibly outdated.

This matters most on anything time-sensitive (prices, statuses, queue counts) where an unmarked stale value is actively misleading rather than just slightly outdated — silence here reads as "this is current" by default, so the absence of a stale indicator is itself a claim.

## Microcopy

The words in every state above come from **the voice of the interface, not a person** — there's no "I" or "we," no first-person apology, no personality performance. The voice is consistent, direct, and describes what's happening and what the user can do about it.

- **Active verbs, sentence case.** "Save changes," not "Changes Will Be Saved" or "Saving Of Changes." Title case on buttons and headings is a common default-theme habit; sentence case throughout is quieter and reads faster.
- **Buttons name the action, not a generic verb.** "Save changes," "Publish," "Delete workspace" — not "Submit," "OK," or "Confirm." A button called "Submit" doesn't tell the user what submitting *does*; a button called "Save changes" does.
- **Stay consistent through the flow.** If the button says "Publish," the resulting toast says "Published" — not "Success!" or "Done." A mismatch between the action's name and its confirmation (button: "Publish", toast: "Changes saved") makes the user re-verify that the thing they clicked is the thing that happened.
- **Name settings by what the user controls, not by the system underneath.** A toggle that controls whether the user gets pinged is labeled "Notifications," not "Webhook config" or "Event subscription" — the underlying implementation is not the user's problem, and exposing it as the label makes a simple control read like an engineering settings page.
- **Errors don't apologize and don't hedge.** No "Oops!", no "Sorry about that," no "Something might have gone wrong." State the fact and the fix: what failed, what to do next. An apology adds words without adding information; vagueness ("there was an issue") withholds the one thing the user actually needs.

Concrete strings, one pass per state discussed above:

| State | Example copy |
|---|---|
| Loading (skeleton) | *(no text — the skeleton itself is the signal; avoid a redundant "Loading…" label next to it)* |
| Loading (button-busy) | Button label swaps to "Saving…" while `disabled`; returns to "Save changes" after |
| Empty — first-run | "Create your first project to start tracking work." Primary action: **Create project** |
| Empty — no-results | "No closed tickets yet." *(no CTA)* |
| Empty — filtered-empty | "No results for these filters." Primary action: **Clear filters** |
| Error — inline | "Couldn't save this field. Retry" |
| Error — page-level | "Couldn't load transactions. Retry" |
| Partial (optimistic rollback) | "Couldn't update status — reverted to Open. Retry" |
| Partial (isolated widget failure) | "Couldn't load this chart. Retry" *(rest of the dashboard stays interactive)* |
| No-permission | "You don't have access to billing. Ask a workspace admin for the Billing role." |
| Offline / stale | "Last updated 12 minutes ago — reconnecting…" |
| Button → toast consistency | Button: **Publish** → Toast: "Published" *(not "Success!")* |
