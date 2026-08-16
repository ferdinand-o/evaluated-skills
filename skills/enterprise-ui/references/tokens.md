# Design tokens

Tokens are the **only** source of color, spacing, radius, and motion in an enterprise-ui surface. If a value isn't a token, it's a bug — magic hex codes, one-off `px` paddings, and inline `border-radius` are exactly how visual drift and inconsistent "one component looks slightly different" bugs creep back in. Every rule below exists to keep that from happening.

The canonical values live in `assets/tokens.css`; the Tailwind mappings live in `assets/tailwind.preset.ts`. This file explains the *architecture* — read it once per project, then work from the source files.

## Token layers

Tokens are organized in three layers, each one narrower than the last:

1. **Primitive** — raw values with no meaning attached. `--gray-600`, `--blue-600`. Never used directly in component markup.
2. **Semantic** — meaning-carrying names that point at a primitive. `--bg-surface`, `--text-muted`, `--accent`. This is the layer components are built from.
3. **Component** *(optional)* — a token scoped to one component when a semantic name alone isn't specific enough, e.g. a hypothetical `--table-row-hover: var(--bg-subtle)`. Use sparingly; most components need nothing beyond the semantic layer. `tokens.css` currently defines only primitives and semantics — add component tokens locally if a specific component genuinely needs a name of its own.

**The rule:** components reference **only the semantic layer**, never primitives directly. `bg-[var(--gray-100)]` in a component is a bug — it breaks theming (dark mode, density, multi-brand all work by re-pointing the semantic layer) and it breaks the one thing tokens are for: one edit in `tokens.css` should be able to re-theme every consumer.

```
Primitive  --gray-100  --blue-600  --green-600  …
                │           │            │
                ▼           ▼            ▼
Semantic   --bg-subtle  --accent   --success
                │
                ▼
Component  --table-row-hover: var(--bg-subtle)   (optional, per-component)
```

## The semantic set

Every semantic token currently defined in `assets/tokens.css`, grouped by purpose. Exact values (hex, `rgba`, `px`) live in that file — don't duplicate them here or they will drift out of sync.

| Group | Tokens | Tailwind utility |
|---|---|---|
| Backgrounds | `--bg-canvas`, `--bg-surface`, `--bg-subtle`, `--bg-muted`, `--bg-inverse` | `bg-canvas`, `bg-surface`, `bg-subtle`, `bg-muted`, `bg-inverse` |
| Text | `--text-strong`, `--text-default`, `--text-muted`, `--text-subtle`, `--text-inverse`, `--text-on-accent` | `text-fg-strong`, `text-fg`, `text-fg-muted`, `text-fg-subtle`, `text-fg-inverse`, `text-fg-on-accent` |
| Border | `--border-subtle`, `--border-default`, `--border-strong` | `border-subtle`, `border` (DEFAULT), `border-strong` |
| Accent | `--accent`, `--accent-hover`, `--accent-subtle`, `--accent-text` | `bg-accent` / `text-accent`, `bg-accent-hover`, `bg-accent-subtle`, `text-accent-text` |
| Status | `--success` / `--success-subtle`, `--danger` / `--danger-subtle`, `--warning` / `--warning-subtle` | `bg-success`, `bg-success-subtle`, `bg-danger`, `bg-danger-subtle`, `bg-warning`, `bg-warning-subtle` |
| Finance directional | `--up`, `--down` | `text-up`, `text-down` |
| Focus | `--ring` | no *reliable* direct utility — see the gotcha in [Wiring into a project](#wiring-into-a-project) |

Note on naming: the primitive/CSS-variable name uses `bg-`/`text-`/`border-` prefixes (`--bg-surface`, `--text-muted`), but the Tailwind preset exposes text colors under the `fg` key (`colors.fg.muted`), so the utility is `text-fg-muted`, not `text-text-muted`. When in doubt, check `assets/tailwind.preset.ts` rather than guessing from the CSS variable name.

Colorblind-safe reminder: `--up`/`--down` carry directional meaning by convention (finance deltas), but color must never be the *only* signal — pair them with a `+`/`−` sign or an icon, not color alone.

Opacity-modifier gotcha: Tailwind color opacity modifiers (`bg-accent/50`, `text-fg-muted/70`, …) are not supported on these token colors, since every one of them resolves to a full `var()` color value rather than an RGB triplet Tailwind can blend an alpha channel into — reach for a dedicated subtle/muted token instead of an opacity modifier.

## Light & dark

Theme switching is driven by an attribute on `<html>`, not a class-based override of individual components:

```html
<html data-theme="dark">
```

`.dark` is also supported as a selector (for shadcn/ui compatibility, since many of its primitives ship keyed to that class), so either `data-theme="dark"` or the `dark` class will activate the dark theme.

**Only the semantic layer is overridden.** `[data-theme="dark"], .dark { --bg-surface: var(--gray-900); … }` re-points semantic names at different primitives (or, for a few subtle-background/shadow cases, different literal values); the primitive ramp itself (`--gray-100`, `--blue-600`, …) never changes. This is why component code must never read primitives directly — a component that does `bg-[var(--gray-50)]` will render identically in light and dark mode, which is the bug this architecture exists to prevent.

## Density modes

Density controls the *sizing* tokens, not color. `[data-density="compact"]` overrides:

- `--control-height`
- `--row-height`
- `--control-padding-x`
- `--field-gap`
- `--font-size-body` / `--font-size-sm`

**Comfortable is the default** (no attribute needed). Compact is opt-in via:

```html
<html data-density="compact">
```

Reach for compact when the surface is dense data work for power users who benefit from seeing more rows/fields per screen at the cost of a tighter target size — think trading blotters, bulk-edit admin tables, ops consoles. Don't default new surfaces to compact; comfortable is right for anything a user isn't in all day.

Apply the type tokens the same way as any other density token — reference the variable, don't hardcode a size: body copy uses `text-[length:var(--font-size-body)]`, secondary/caption text uses `text-[length:var(--font-size-sm)]`, so both shrink automatically under `data-density="compact"` with no per-component change.

## Multi-brand

A multi-brand deployment (white-label, per-tenant theming) overrides the semantic layer per brand — in practice this is almost always just the accent group, since that's what carries brand identity:

```css
[data-brand="acme"] {
  --accent: #1d4ed8;
  --accent-hover: #1e40af;
  --accent-subtle: #dbeafe;
  --accent-text: #1e40af;
}
```

Primitives and spacing/sizing tokens stay stable across brands — a brand switch should never change layout density or the neutral gray ramp, only the accent identity layered on top. If a brand needs more than the accent group re-themed, that's a signal to double check the request isn't actually asking for a different product, not just a different brand skin.

## Scales

Beyond color, three scalar systems exist:

- **Radius** — `--radius-xs` through `--radius-xl`, plus `--radius-full` for pills/avatars. Utilities: `rounded-xs` … `rounded-xl` (full is available as Tailwind's built-in `rounded-full`).
- **Shadow** — `--shadow-xs` through `--shadow-lg`. Deliberately subtle — these are for elevation cues (dropdowns, popovers, modals), not decoration. If a shadow looks like a soft glow or a marketing-site "floating card," it's the wrong choice for this skill; see `SKILL.md`'s rationalization table.
- **Motion** — `--duration-fast/base/slow` and `--ease-standard/emphasized/out`, mapped to `duration-fast/base/slow` and `ease-standard/emphasized` (the preset does not expose an `ease-out` utility; reach for `ease-[var(--ease-out)]` if a transition specifically needs it). See `references/motion.md` for which duration/easing pairs to use where.
- **Type roles** — display / heading / body / label roles built on `--font-sans`, plus **mono for numbers** (`--font-mono`) — see below.

## Numbers & fonts

All numeric and tabular data — table cells, KPI figures, financial amounts, IDs — uses `--font-mono` with `font-variant-numeric: tabular-nums`, so digits align on a fixed width and columns of numbers don't visually jitter as values change:

```css
.metric {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
```

`--font-sans` (`"Inter", "Geist", ui-sans-serif, system-ui, sans-serif`) is the UI typeface for everything else. As `SKILL.md` notes under "A note on fonts": unlike expressive marketing work, a quiet, highly legible UI sans is *correct* for enterprise product UI — it's a deliberate legibility choice, not a default to avoid replacing. Personality here comes from the token system and layout discipline, not from swapping the typeface.

## Contrast

Every text/background pair in the default palette meets **WCAG AA**: ≥ 4.5:1 for body text, ≥ 3:1 for large text (≥ 24px, or ≥ 19px bold). This is already satisfied by the shipped semantic values in both light and dark themes.

Whenever a project introduces a **new** semantic value — a new brand accent (see [Multi-brand](#multi-brand)), a new status color, a custom `--bg-*`/`--text-*` pairing — re-check contrast before shipping it. Don't assume a new accent is fine because it "looks about as dark as the old one." Use a contrast checker against every background it's likely to sit on (`--bg-surface`, `--bg-subtle`, `--bg-inverse`), not just the one you tested first.

## Wiring into a project

Three steps, in order:

1. **Import `assets/tokens.css` globally** — once, at the app's CSS entry point, before any component styles.
2. **Add `assets/tailwind.preset.ts` as a preset** in `tailwind.config.ts`:

   ```ts
   import preset from "./enterprise-ui/assets/tailwind.preset";

   export default {
     presets: [preset],
     content: ["./src/**/*.{ts,tsx}"],
   };
   ```

3. **Set `data-theme` / `data-density` on `<html>`** (see [Light & dark](#light--dark) and [Density modes](#density-modes)) — typically driven by a theme provider that reads user/tenant preference and writes the attribute, rather than hardcoding it.

With that wired up, every component is built from token-mapped utilities only:

```tsx
// Button styled purely via token-mapped utilities (no magic values)
<button className="h-control rounded-md bg-accent px-[var(--control-padding-x)] text-fg-on-accent
                   shadow-xs transition-colors duration-base ease-standard hover:bg-accent-hover
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
  Save changes
</button>
```

**Gotcha worth knowing:** the preset sets only `ringColor.DEFAULT` to `var(--ring)` — there is no `ring` color key defined — so **`ring-ring` is not a defined utility here and emits nothing**, while **bare `ring`/`ring-2`** resolve the width utility but Tailwind v3's ring plugin cannot bake a CSS variable into its default ring-opacity calculation, so they **fall back to Tailwind's stock blue** instead of the token. Both compile without error and neither one visibly signals the mistake. Always pin the color explicitly with the arbitrary-value form shown above (`ring-[var(--ring)]`) wherever a focus ring is applied. The rest of the utilities in this example (`h-control`, `bg-accent`, `text-fg-on-accent`, `shadow-xs`, `duration-base`, `ease-standard`, `hover:bg-accent-hover`) resolve correctly with no such caveat.
