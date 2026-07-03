# Accessibility floor

This file defines the **non-negotiable baseline** every enterprise-ui surface ships with — visible focus, full keyboard operability, AA contrast, labeled fields, native semantics, and respect for `prefers-reduced-motion`. It is **not** a substitute for full **BITV 2.0** or **EN 301 549** compliance, and it does not claim to be. The floor is the line below which a surface is broken for keyboard and assistive-tech users, full stop, on every project regardless of contract or jurisdiction; formal compliance is a separate, heavier commitment layered on top when a project's legal or contractual obligations require it — see [Escalating to full compliance](#escalating-to-full-compliance) for what that additional work looks like and when to reach for it.

Treat this file the same way `references/states.md` treats the six-state matrix: a literal pre-ship checklist, not aspirational guidance. `SKILL.md`'s doctrine line — "the accessibility floor is mandatory" — means every item below, on every surface, every time, with no "we'll add a11y in a follow-up" deferral.

## The floor

The baseline, in one scannable list. If any line here isn't true of a surface, it isn't done:

- **Visible focus everywhere.** Every focusable element — buttons, links, inputs, table rows, menu items — shows a visible `:focus-visible` ring using `--ring`. No element that can receive keyboard focus is allowed to render with no visible indicator of that fact. See [Focus](#focus).
- **Full keyboard operability.** Everything a mouse can do, a keyboard can also do — open a menu, sort a column, dismiss a dialog, reorder a list. No feature is mouse-only. See [Keyboard](#keyboard).
- **AA contrast, from tokens.** Every text/background pairing meets WCAG AA (≥ 4.5:1 body, ≥ 3:1 large text) — already true of the shipped semantic tokens in `assets/tokens.css` per `references/tokens.md#contrast`; re-verify only when a project introduces a *new* semantic value. See [Contrast & target size](#contrast--target-size).
- **Every field is labeled.** No input relies on a placeholder as its only label, and no icon-only control ships without an accessible name. See [Semantics](#semantics).
- **Native semantics first.** Reach for `<button>`, `<table>`, `<label>`, `<nav>` before reaching for a `<div>` plus a fistful of ARIA attributes trying to recreate what the native element already does for free. See [Semantics](#semantics).
- **Never color alone.** Status, direction, and validity are never conveyed by color as the only signal — pair color with text, an icon, or a sign (this already applies to `--up`/`--down` per `references/tokens.md#the-semantic-set`, and extends to every status/validation use of color). See [Contrast & target size](#contrast--target-size).
- **`prefers-reduced-motion` respected.** The global CSS safety net from `references/motion.md#prefers-reduced-motion` is wired up, and any JS-driven animation has its own reduced-motion check on top of it. This floor item is fully specified in `motion.md` — it is not repeated in depth here, only listed as a required line item.

## Focus

A visible focus indicator is the single most load-bearing item on the floor — it is how a keyboard or switch-device user tracks where they are on the screen at all, and its absence doesn't just degrade the experience, it makes the surface unusable for that user.

**Always `:focus-visible`, never bare `:focus`.** `:focus-visible` shows the ring for keyboard and other non-pointer input while suppressing it for a plain mouse click — matching what sighted mouse users expect (no ring flashing on every click) without removing the ring for the users who actually depend on it. Using bare `:focus` (or Tailwind's `focus:` variant) shows the ring on every interaction including mouse clicks, which reads as visual noise to pointer users and tends to get "fixed" by someone removing the ring outright — which then breaks keyboard access. Using `outline-none` with no `focus-visible:` replacement is the same failure by a different path.

**Always pin the ring color explicitly.** Per the gotcha documented in `references/tokens.md#wiring-into-a-project`, in this preset only `ringColor.DEFAULT` is set (no `ring` color key), so **`ring-ring` is not a defined utility here — it emits nothing**, whereas **bare `ring`/`ring-2` fall back to Tailwind's stock blue**, since Tailwind's ring plugin cannot bake a CSS variable into its default opacity math. Both compile clean, both look plausible in a quick glance, and both are wrong. Every focus ring in this system uses the arbitrary-value form:

```tsx
<button
  className="h-control rounded-md bg-accent px-[var(--control-padding-x)] text-fg-on-accent
             focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]
             focus-visible:ring-offset-2"
>
  Save changes
</button>
```

The pattern is always the same three utilities together: `focus-visible:outline-none` (removes the browser default so it doesn't double up with the ring), `focus-visible:ring-2 focus-visible:ring-[var(--ring)]` (the actual indicator, pinned to the token), and typically `focus-visible:ring-offset-2` so the ring has a visible gap from the element's own edge rather than sitting flush against it — offset matters most on filled/accent-colored controls, where a flush ring in a similar hue can visually merge into the control instead of standing apart from it.

**Focus trapping and return in dialogs.** When a dialog, sheet, or popover opens, focus must move *into* it (typically the first focusable element or a sensible default like the primary action), stay contained inside it while open (Tab/Shift+Tab cycle within the dialog rather than escaping to page content behind it), and return to the element that triggered it when it closes. Hand-rolling this trap-and-return logic is easy to get subtly wrong (focus escaping on a specific key combo, focus landing on `<body>` after close instead of back on the trigger) — **Radix's dialog/popover primitives already implement this correctly**, which is one more reason `references/data-components.md#sourcing-primitives` insists on pulling primitives via `npx shadcn@latest add <component>` rather than hand-writing the interaction shell. Restyle the visual layer; leave the focus-management behavior untouched.

## Keyboard

Every interaction on the floor must be reachable and operable without a mouse. Concretely:

- **No click-only handlers.** An `onClick` attached to a non-interactive element (a `<div>` or `<span>` styled to look clickable) is invisible to keyboard users — it doesn't receive focus and has no key handler, so a keyboard user cannot activate it at all. If a native `<button>` can wrap the interaction, use it; a native button already handles the click-vs-Enter-vs-Space activation contract and needs no extra key handling. Only reach for a manual `role="button"` plus `onKeyDown` handling Enter/Space on a non-button element as a last resort when no native element fits.
- **Composite widgets follow the arrow-key convention for their role**, not custom key bindings invented per component: a menu's items are reached with Up/Down, a tab list with Left/Right, a table's cells with all four arrows in grid-like navigation. This is exactly what Radix's menu, tabs, and select primitives already implement — another reason those primitives are sourced from `npx shadcn@latest add`, per `references/data-components.md#sourcing-primitives`, rather than hand-rolled. Don't invent a bespoke key scheme for a widget shape that already has an established one.
- **Escape closes the topmost transient surface** — a dropdown, popover, dialog, or command palette — without closing anything beneath it or navigating away from the page. This, too, is already correct out of the box in Radix's primitives.
- **Tab order follows visual/reading order.** A form or toolbar where Tab jumps around unpredictably (because of `tabIndex` values hand-tuned out of DOM order, or a CSS layout that visually reorders elements without also reordering the underlying markup) is disorienting for a keyboard user in a way a sighted mouse user would never even notice. Avoid positive `tabIndex` values entirely; let DOM order define tab order, and fix the DOM order if the visual order needs to differ from it.
- **No keyboard trap outside an intentional one.** The only place Tab should be unable to leave is a modal dialog while it's open (see [Focus](#focus)) — anywhere else, a user must always be able to Tab or Shift+Tab away from any element.

## Semantics

**Native HTML first, ARIA only to fill a genuine gap.** The first ARIA rule is that the best ARIA attribute is often the one you don't need, because the native element already carries the semantics, keyboard behavior, and assistive-tech announcement for free:

| Instead of | Use |
|---|---|
| `<div onClick>` styled as a button | `<button>` |
| `<div>` grid of cells for tabular data | `<table>` with `<thead>`/`<tbody>`/`<th scope="col">` |
| A styled `<span>` next to an `<input>` | `<label htmlFor="…">` wrapping or paired with the input |
| `<div role="navigation">` | `<nav>` |
| `<div>` stack of headings styled visually | Real `<h1>`–`<h6>` in a sequence that reflects actual hierarchy, not just font size |

ARIA earns its place only where no native element expresses the semantic — a custom combobox, a live-region announcement (see [Async](#async)), a `role="tab"`/`role="tabpanel"` pairing on elements a design constraint prevents from being native `<table>`-adjacent markup. Reaching for ARIA as the *first* tool rather than the fallback tends to produce a widget that *sounds* accessible (attributes are present) while still failing in practice, because ARIA only describes semantics — it grants none of the native keyboard behavior a real `<button>` or `<select>` comes with automatically.

**Every field has a real label**, connected via `<label htmlFor>` (or wrapping the input), not a placeholder standing in as the only label — a placeholder disappears the moment the user starts typing, and most assistive tech does not treat it as equivalent to a label in the first place. This is the same rule `references/data-components.md#forms` states for error-text wiring via `aria-describedby`; a label is the same contract one layer up, applying to the field's *name* rather than its *error*.

**Icon-only controls need an accessible name.** A row's `…` overflow trigger, a toolbar's icon buttons, a dismiss `×` — none of these have visible text, so without an explicit name a screen reader announces nothing useful (or just "button"). Supply one via visible-but-visually-hidden text or an `aria-label`:

```tsx
<button
  aria-label="Row actions"
  className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
>
  <MoreHorizontal className="size-4" />
</button>
```

**Heading hierarchy reflects actual structure**, not visual size choices — don't skip from an `<h1>` to an `<h3>` because the `<h2>` styling "looked too big" for the spot; restyle the `<h2>` instead of reaching for a different heading level to get a different font size. Screen reader users frequently navigate a page by jumping between headings, and a hierarchy that skips levels or uses them out of structural order breaks that navigation model even though it looks identical to a sighted user scanning visually.

## Contrast & target size

**Contrast** is inherited, not invented per component: use the semantic tokens as documented in `references/tokens.md#contrast`, which are already AA-compliant in both themes. The floor obligation here is narrow but firm — re-check contrast with an actual contrast checker any time a *new* semantic value enters the system (a new brand accent under multi-brand, a new status color), rather than eyeballing it as "looks about as dark as the others." Don't introduce a new `--bg-*`/`--text-*` pairing without running that check first.

**Color is reinforcement, never the only signal.** This applies everywhere the tokens carry meaning:

- `--up`/`--down` (financial deltas) pair with a `+`/`−` sign or a directional icon, never color alone — already called out in `references/tokens.md#the-semantic-set`.
- `--danger` on a form field's border reinforces an error, but the error *text* is what actually carries the meaning — per `references/data-components.md#forms`.
- A status badge (active/paused/failed) pairs its background color with a text label, not a bare colored dot with no accompanying word.

A colorblind user (or anyone on a low-quality/grayscale display) must be able to determine every one of these states from something other than hue.

**Target size.** Every interactive element meets at least the WCAG 2.2 AA minimum of 24×24px, and in practice this system's controls clear that comfortably by default: `--control-height` is 40px in the comfortable density and 32px under `[data-density="compact"]` (see `references/tokens.md#density-modes`) — both well above the 24px floor. The one place this needs a deliberate check is **icon-only controls that aren't full-height buttons** (a small `×` dismiss inside a chip, a compact-density row action) — pad the *hit area* out to at least 24×24px even if the visible icon glyph is smaller, rather than sizing the clickable region to exactly match the glyph's visual bounds. A visually small icon with a comfortably larger invisible hit area is the correct pattern; a hit area clipped to the icon's own pixels is not.

```tsx
{/* Hit area padded to clear 24px even though the icon glyph itself is 12px */}
<button aria-label="Remove filter" className="flex size-6 items-center justify-center rounded-full
           focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
  <X className="size-3" />
</button>
```

## Async

State that changes without a page navigation or an explicit user click on that exact spot — a toast appearing, a background save failing, a filtered result count updating — is invisible to a screen reader user unless something explicitly announces it. A sighted user notices the toast slide in or the count change because it's in their peripheral vision; a screen reader user gets nothing unless the update happens inside (or is announced via) an `aria-live` region.

**What needs a live region:**

- **Toasts** — any transient status message (per the toast/status conventions in `references/states.md#microcopy`) needs its container marked `aria-live="polite"` (or `role="status"`) so its appearance is announced without interrupting whatever the user is currently doing.
- **Async errors surfaced inline** — when a field or block's error state (per `references/states.md#error`) appears after an async check rather than on initial render, the region containing that error text should be `aria-live="polite"` so a screen reader user who has already tabbed past the field still hears that it failed.
- **Result/row counts that update from filtering** — "24 results" changing to "3 results" after a filter is applied (per `references/data-components.md#filtering--search`) is meaningful feedback a sighted user gets from re-reading the toolbar; announce the updated count so a screen reader user gets the same signal without needing to re-navigate to the count on every filter change.

```tsx
<div aria-live="polite" role="status" className="sr-only">
  {resultCount} results
</div>
```

**`polite` versus `assertive`.** Default to `aria-live="polite"` — it waits for the screen reader to finish whatever it's currently announcing before queuing the new message, which is correct for nearly everything above. Reserve `aria-live="assertive"` for something that genuinely needs to interrupt — a session-expiring warning, a destructive action's confirmation requirement — because `assertive` cuts off whatever the screen reader was mid-sentence on, and using it by default turns every minor update into an interruption.

**Don't over-announce.** A live region re-rendering on every keystroke of a search box floods the screen reader with noise faster than a sighted user could ever process the equivalent visual updates. Announce the *settled* result (after a debounce, or on blur/submit per the same validation-timing discipline `references/data-components.md#forms` applies to visual validation), not every intermediate character.

## Escalating to full compliance

Everything above is the floor: it is what keeps a surface from being broken for keyboard and screen-reader users, on every project, unconditionally. It is deliberately **not** a claim of full **BITV 2.0** or **EN 301 549** conformance — those are formal, audited standards with requirements this file does not attempt to cover (document/PDF accessibility, procurement-specific conformance statements, testing across a defined assistive-technology matrix, and WCAG success criteria well beyond what's listed here). Treat the floor as "correct by default, no extra process," and treat full compliance as an explicit, heavier commitment a project takes on when it's contractually or legally required — most commonly public-sector work in the EU (BITV 2.0 in Germany, EN 301 549 as the underlying harmonized standard) or any procurement process that names WCAG conformance as a requirement.

When a project needs to escalate past the floor, the concrete steps, roughly in the order a project should take them on:

1. **Automated linting in dev — `@axe-core/react`.** Wire `@axe-core/react` into the development build so accessibility violations (missing labels, contrast failures, invalid ARIA usage, etc.) surface as console warnings during normal development, not only when someone remembers to run a manual audit. This catches a wide, mechanical class of regressions for free but is explicitly a floor-raiser, not a full audit substitute — axe-core's own documentation is clear that automated tooling catches roughly a third of WCAG issues; the rest need human testing.
2. **Manual screen-reader testing — NVDA and VoiceOver.** Test the actual product with a real screen reader on both a Windows/NVDA and a macOS/VoiceOver pass, not just automated tooling — a great deal of what breaks the experience for a screen-reader user (confusing reading order, a live region that's too chatty, a custom widget whose ARIA state doesn't match its visual state) is invisible to `axe-core` and only surfaces when someone is actually listening to the page.
3. **A formal WCAG 2.2 AA audit.** Commission (internally or via a third-party accessibility auditor) a structured pass against every WCAG 2.2 AA success criterion, producing a documented conformance report — this is the artifact that BITV 2.0 / EN 301 549 procurement processes typically require, and it is a meaningfully different deliverable from "we ran axe-core and it's clean."
4. **A dedicated accessibility workstream, not a checklist bolted onto feature work.** Once formal compliance is a project requirement, accessibility needs its own tracked backlog, its own acceptance criteria per ticket, and someone accountable for it — treating it as an occasional cleanup pass on top of feature work is how compliance projects quietly regress between audits. This mirrors the same principle `references/states.md` states for the six-state matrix: an item that's "supposed to be handled" but isn't tracked as its own line item reliably gets skipped under deadline pressure.

None of this replaces the floor above — it's additive. A project doing a full BITV 2.0 audit still needs every item in [The floor](#the-floor) true first; the audit exists to verify compliance with a much larger surface of requirements, not to substitute for getting focus rings and keyboard operability right in the first place.
