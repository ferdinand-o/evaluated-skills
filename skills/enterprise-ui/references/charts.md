# Charts & data-viz

A chart in this system is an instrument, not an illustration — it exists so a user can read a value, compare two series, or spot a trend faster than a table would let them. Every choice below follows from that: pick the chart type the question demands, color it from tokens so meaning survives dark mode and colorblindness, strip anything that doesn't carry information, and ship the same loading/empty/error states any other data view ships. This file builds on the token architecture in `references/tokens.md` and defers to `references/states.md` for the general state model — the state matrix there already lists "Chart" as a surface type; this file only adds the chart-specific detail.

## Choose the chart

Pick the chart type by **the question being asked**, not by which one looks the most impressive on a dashboard. A chart chosen for its visual weight instead of its fit is a decoration wearing a data costume — it takes just as long to build as the right chart and answers the user's question worse.

| Question | Chart | Notes |
|---|---|---|
| How did this change over time? | **Line** or **area** | Line for one or a few series; area to emphasize volume/magnitude under the line. Don't stack more than 3–4 lines on one chart — beyond that, split into small multiples. |
| How do these categories compare? | **Bar** (horizontal or vertical) | The default for comparison. Horizontal bars read better once labels get long or the category count grows past what fits on a vertical axis. |
| How is this value distributed? | **Histogram** | Bucket a continuous variable to show its shape (skew, outliers, modality) — a line chart cannot answer a distribution question. |
| Is there a relationship between two variables? | **Scatter** | One point per observation, two numeric axes. Add a trend line only if the relationship is the point being made, not as decoration. |
| What share of the whole does each part have? | **Bar** first; **donut** only sparingly | A sorted bar chart almost always communicates share faster than a pie or donut, especially past 3–4 categories where slice angles become hard to compare by eye. Reach for a donut only for a single, well-known "part of a whole" metric (e.g. storage used) where the total-in-the-center readout is itself useful — never for more than 4–5 categories, and never as a substitute for a bar chart just because it looks more finished. |

Two rules sit above the table:

- **No decorative charts.** If a number would communicate the point on its own — a single KPI, a single percentage — don't wrap it in a gauge, a speedometer, or a 3D-tilted bar just to fill space on a dashboard. A big, well-formatted number *is* the chart in that case.
- **When in doubt, prefer the plainer chart.** A line chart and a bar chart cover the large majority of enterprise data-viz needs. Reach for scatter, histogram, or a donut only when the question genuinely requires it, not because the dashboard already has three line charts and a fourth would look repetitive.

## Color

Chart color comes from the same token layers as everything else in this system — a chart with its own hardcoded hex palette is exactly the kind of drift `references/tokens.md` exists to prevent, and it's also the part of a chart most likely to silently break in dark mode if it isn't token-driven.

- **Categorical series** (comparing distinct, unordered categories — e.g. one line per region) — derive a small qualitative palette from the primitive ramps in `assets/tokens.css` (the accent blues, plus the green/red/amber primitives) rather than inventing new hues. Keep a categorical palette to the number of series a user can actually hold in working memory at once — beyond 6–8 colors, direct-labeling or small multiples (see [Restraint](#restraint)) communicate better than adding another color no one can reliably tell apart from its neighbors.
- **Sequential scales** (a single quantity going from low to high — e.g. a heatmap of activity intensity) — a one-hue ramp with increasing saturation/lightness, derived from a single primitive ramp (e.g. the blue primitives from light to dark) rather than a rainbow gradient. A rainbow sequential scale implies categorical boundaries that aren't there and is also one of the worst-performing palette choices for colorblind readers.
- **Diverging scales** (a quantity with a meaningful midpoint — e.g. performance vs. a benchmark, positive/negative variance) — two hues meeting at a neutral midpoint, built from the `--up`/`--down` direction pair described below plus a neutral (`--bg-muted` or a gray primitive) at zero.
- **Directional / finance color** — use the semantic tokens `--up` and `--down` (Tailwind: `text-up`, `text-down`, or as chart series colors via the same CSS variables) for anything with a positive/negative or gain/loss meaning: price change, P&L, variance vs. target. These are already chosen to be **colorblind-safe as a pair**, but that safety only holds if color is never the *only* signal carrying the meaning — see the rule immediately below.
- **Meaning must never rely on color alone.** This is the single most important rule on this page, and it's a WCAG requirement, not a style preference: a user with a color-vision deficiency (roughly 1 in 12 men) must still be able to read up vs. down, or "this bar means something different from that bar," without perceiving color at all. Concretely, always pair a directional or categorical color with at least one of:
  - A **sign** (`+2.4%` / `−1.1%`), not just a colored number.
  - An **arrow or icon** (▲/▼, or an up/down chevron) next to the value or the series.
  - **Position** (a diverging bar that visibly extends left vs. right of a zero baseline, independent of its fill color).
  - A **pattern or line style** (dashed vs. solid, or a texture) when two overlapping series need to stay distinguishable in grayscale.

No magic hex codes in a chart's *usage* — component and chart-config code reads token variables (`var(--up)`, `var(--accent)`, a Tailwind `text-up`/`bg-accent` utility, or a palette array built from `getComputedStyle`/CSS custom properties at the theme layer). The one place a literal color value is legitimate is a **definition site** — a palette-builder or theme file that assigns primitive values to named slots once, the same way `references/tokens.md#multi-brand` assigns literal hex to `--accent` for one brand. The distinction is: define colors once, in one place, as tokens; never re-declare them inline in a chart component.

## Restraint

A chart earns trust by getting out of the way of the data, not by looking busy. Everything on this list either removes something or replaces a heavier element with a lighter one:

- **No chartjunk.** No decorative icons floating in the plot area, no background images, no drop shadows on bars or lines, no gradient fills standing in for a flat, legible one. If an element doesn't help someone read a value, remove it.
- **No 3D.** A 3D bar or pie chart distorts the exact comparison a chart exists to make — perspective makes far bars look smaller than they are and slice angles harder to judge — for a purely cosmetic gain. Always render 2D.
- **Minimal gridlines.** Enough gridlines to let the eye anchor a value to an axis, not a full grid at every tick. Prefer light, low-contrast gridlines on the primary axis only (usually the y-axis for a bar/line chart), and omit them entirely on axes where exact readout matters less than the shape of the trend.
- **Dezent axes.** Axis lines and tick labels use `--text-muted` or `--text-subtle`, not `--text-strong` — the axis is a supporting frame for the data, not itself the thing being read. Keep tick label count low enough to avoid crowding (thin out labels rather than shrinking font size to fit more of them).
- **Direct-labeling over a legend, where it fits.** Labeling a line at its endpoint, or a bar at its tip, lets the eye read the value and its meaning in one look instead of two — glance at the mark, then glance away to a separate legend box to decode its color, then glance back. Reach for direct labels whenever there's room (2–4 series is the common case); fall back to a legend once too many series make endpoint labels collide, and keep the legend itself compact and close to the plot rather than floating far away from what it explains.

## Axes & numbers

Numbers on a chart follow the same discipline as numbers in a table (`references/data-components.md`) and the same font/format rules in `references/tokens.md#numbers--fonts`:

- **`tabular-nums` on every numeric label** — axis ticks, data labels, tooltip values — via `--font-mono` with `font-variant-numeric: tabular-nums`, so a tooltip or axis that updates on hover doesn't visibly reflow as digit widths change.
- **Units live on the axis title, not on every tick.** Label the axis "Revenue (€)" or "Latency (ms)" once, and let the tick values themselves be bare numbers — repeating a unit suffix on every single tick is visual noise that direct-labeling and axis titles already make unnecessary.
- **Shorten large numbers.** Render large axis values and data labels as `1.2K` / `3.4M` / `1.1B` rather than spelling out every digit — a dense y-axis of `1,000,000` / `2,000,000` / `3,000,000` costs far more horizontal space than the values need and is harder to scan than `1M` / `2M` / `3M`.
- **Locale-format everything.** Use `Intl.NumberFormat` rather than manual string manipulation for both the compact form above and any full-precision tooltip value, so decimal separators and grouping match the user's locale automatically. German locale (`de-DE`) uses a comma as the decimal separator and a period/space as the grouping separator — the opposite of `en-US` — which is exactly the kind of detail manual formatting gets wrong:

```ts
const fmt = new Intl.NumberFormat("de-DE", { notation: "compact", maximumFractionDigits: 1 });
fmt.format(1234567); // "1,2 Mio."
```

## Chart states

A chart is a data view like any other, and it ships the same loading/empty/error discipline `references/states.md` requires everywhere else — a chart that only renders once data has successfully arrived is exactly the "happy path only" mistake that file opens by calling out. `references/states.md#the-state-matrix` already lists "Chart" as a surface row; this section is the chart-specific detail behind that row.

- **Loading — skeleton in chart shape, not a spinner.** Render a lightweight placeholder that echoes the real chart's geometry (a few muted bars at varying heights for a bar chart, a soft wavy line shape for a line/area chart) using `bg-subtle`/`animate-pulse`, matching the same skeleton-vs-spinner rule as everywhere else in this system: skeletons are for content-shaped waits, spinners are for actions. A generic centered spinner over blank chart space tells the user nothing about what kind of chart is about to appear.
- **Empty — say why nothing is showing, and be exact about which "empty" it is.** "No data for this range" (a real, deliberate scope with nothing in it — e.g. a date range before the account existed) is a different situation from "No data matches these filters" (loosen the filter to see something), and both are different from an axis that renders because every value is genuinely `0`. **No-data must never be rendered identically to zero data** — a flat line at `0` and a missing series look the same on an unlabeled axis, but they mean opposite things (nothing happened to measure vs. we have nothing to show). Render the empty state as an explicit message replacing the plot area, not as a chart quietly drawing a zero baseline.
- **Error — inline, scoped to the chart, with retry.** A failed chart fetch gets the same inline-error treatment as any other block-scoped failure in `references/states.md#error`: a short message plus a **Retry** action, contained to the chart's own area — one broken chart on a dashboard must not blank the rest of the dashboard (see `references/states.md#partial--optimistic`).
- **Accessibility fallback — never chart-only.** A chart's visual encoding is not, by itself, an accessible representation of its data. Every chart ships two things beyond the visual plot: a concise `aria-label` (or `aria-describedby`) summarizing what the chart shows (e.g. "Line chart of monthly revenue, January to June, trending up"), **and** a visually-hidden data table (`sr-only`/`visually-hidden` class, not `display: none`, so assistive tech still reaches it) containing the same series as real `<table>` markup a screen reader can navigate cell by cell. Never make the chart's underlying data reachable *only* through hovering a pixel with a mouse.

```tsx
<figure aria-label="Line chart of monthly revenue, January to June, trending up">
  <LineChart data={revenueSeries} /* …visual chart, colors from tokens… */ />
  <table className="sr-only">
    <caption>Monthly revenue</caption>
    <thead><tr><th>Month</th><th>Revenue</th></tr></thead>
    <tbody>
      {revenueSeries.map((point) => (
        <tr key={point.month}><td>{point.month}</td><td>{point.value}</td></tr>
      ))}
    </tbody>
  </table>
</figure>
```

## Library

For this stack (React + TypeScript + Tailwind), reach for one of these depending on how standard the chart is:

- **Tremor** — Tailwind-native chart and dashboard-block components; the fastest path when the chart is a standard type (line, bar, area, donut) and the surface is otherwise built with Tailwind utilities already. Good default for most dashboard widgets in this skill.
- **Recharts** — a more flexible, composable React charting library when a chart needs configuration Tremor doesn't expose (custom tooltips, layered series, non-standard axis behavior) but still doesn't need a fully bespoke visual.
- **visx** — a low-level set of primitives (from Airbnb) for building a chart from scratch when the visualization is genuinely custom — a bespoke financial instrument view, an unusual layout no off-the-shelf chart library models. Reach for visx only when Tremor and Recharts have both been ruled out; it costs far more implementation time in exchange for full control.

**Whichever library is chosen, restyle its colors, fonts, and spacing onto this system's tokens before shipping** — every library above ships its own default palette and its own default sans font, and neither matches this skill's tokens out of the box. Treat a chart library's defaults the same way `SKILL.md`'s rationalization table treats a shadcn or MUI default: a starting primitive, not a finished look. Concretely: pass series colors as `var(--accent)` / `var(--up)` / `var(--down)` / a token-derived categorical palette (see [Color](#color)) rather than the library's built-in palette, and set the chart's font to `var(--font-sans)` (labels, legend, tooltip text) and `var(--font-mono)` with `tabular-nums` for any rendered numeric value (see [Axes & numbers](#axes--numbers)).

## Finance specifics

This system is built for data-dense B2B and financial surfaces, so a few chart patterns show up often enough to call out on their own:

- **Sparklines in table rows.** A tiny, axis-free line or area chart inside a table cell — showing a trend at a glance next to the row's other numeric columns (e.g. a 30-day price trend next to today's price). Keep a sparkline label-free and axis-free by design (its only job is shape, not exact readout); if a user needs exact values, that's what hovering for a tooltip or opening the full detail chart is for. Color a sparkline with `--up`/`--down` when it's showing a directional series, following the same colorblind-safe pairing rule from [Color](#color) — an up-colored sparkline sitting next to a `+2.4%` figure in the adjacent column already satisfies "don't rely on color alone," since the sign is right there in the row.
- **OHLC / candlestick charts.** For price series, color each candle's body with `--up`/`--down` depending on whether the period closed above or below its open — this is the one chart type in this system where color *is* the primary encoding, which is exactly why it must always be read alongside the candle's own shape (a hollow/filled or wick-length convention) and an accompanying price axis, never color in isolation on an otherwise unlabeled strip.
- **Reference lines.** A thin, muted horizontal (or vertical) line marking a fixed comparison point — the previous close, a target/benchmark value, a threshold — drawn in `--border-strong` or `--text-subtle` so it reads as a reference, not as another data series competing for attention. Label a reference line directly at its edge (e.g. "Prev. close 142.10") rather than adding it to the legend.
- **Brush / zoom for long time series.** Once a series spans enough points that the full range makes short-term movement illegible (months of daily prices, years of daily volume), pair the main chart with a brush control — a compressed overview strip below the chart with a draggable selection window — so a user can zoom into a range without losing the context of where that range sits in the whole series. Prefer this over forcing a user to pre-select a date range from a separate control before seeing anything.
