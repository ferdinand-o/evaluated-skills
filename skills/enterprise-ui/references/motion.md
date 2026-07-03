# Motion

Motion in an enterprise product surface has one job: make state changes legible. It confirms that a click registered, shows where a panel came from, or softens a value that just changed — it is not there to feel "designed." The moment motion starts drawing attention to itself instead of to the content it's revealing, it has become decoration, and this skill's doctrine on decoration (see `SKILL.md`'s rationalization table) applies to motion exactly as it applies to gradients and shadows: restraint is the premium signal, not the flourish.

That restraint has a concrete consequence: every duration and curve in this system comes from the motion tokens, never from a one-off `150ms` or a hand-picked `cubic-bezier(...)` typed into a component. This file explains which tokens exist, what's worth animating versus what isn't, how motion contributes to (or undermines) perceived performance, and the one rule that is not negotiable — respecting `prefers-reduced-motion`.

## Motion tokens

`assets/tokens.css` defines two small scales — durations and easings — and nothing else. There is no motion primitive layer the way color has one; these values are already semantic.

| Token | Value | Tailwind utility | Use for |
|---|---|---|---|
| `--duration-fast` | 120ms | `duration-fast` | Micro-feedback: hover, press, checkbox/switch toggle |
| `--duration-base` | 180ms | `duration-base` | **Default.** Most transitions: color/background changes, simple show/hide |
| `--duration-slow` | 240ms | `duration-slow` | Larger surface area moving: panel slide-in, modal/dialog entrance, accordion expand |
| `--ease-standard` | `cubic-bezier(.2,0,0,1)` | `ease-standard` | **Default curve.** Symmetric-feeling, quick-out-quick-in — correct for the majority of UI transitions |
| `--ease-emphasized` | `cubic-bezier(.3,0,0,1)` | `ease-emphasized` | A transition that should read as slightly more deliberate — a dialog opening, a destructive action's confirm state |
| `--ease-out` | `cubic-bezier(0,0,0,1)` | *(none — see gotcha below)* | An element decelerating firmly into its final position — fast start, no overshoot, settles rather than snaps (e.g. a dropped-in row coming to rest) |

**Default pairing, when in doubt:** `duration-base` + `ease-standard`. Reach for `fast` only when the animated property is a direct, immediate reaction to input (hover/press); reach for `slow` or `emphasized` only when a larger amount of screen real estate is moving at once. Most components never need anything past the default pair.

**Gotcha:** `--ease-out` is defined in `tokens.css` but, unlike `--ease-standard` and `--ease-emphasized`, it is **not** mapped to a Tailwind utility in `assets/tailwind.preset.ts` — there is no `ease-out` class wired to the token (Tailwind's own built-in `ease-out` utility is a different, unrelated curve, so using it "by accident" silently pulls in the wrong easing rather than erroring). If a transition genuinely needs `--ease-out`, use the arbitrary-value form:

```html
<div class="transition-transform duration-base ease-[var(--ease-out)]">
```

No component should ever contain a literal `ms` value or a hand-typed `cubic-bezier(...)` — if none of the three durations or two mapped easings fit, that's a signal to reconsider the animation, not a license to invent a new one inline.

## What to animate

Motion earns its place when it clarifies **what changed and where things went**. In practice, that means:

- **State transitions** — hover, press/active, open/close, selected/unselected. These are the bread-and-butter cases `duration-fast`/`duration-base` + `ease-standard` exist for.
- **Disclosure** — accordion expand/collapse, popover/dropdown/tooltip appearance, dialog/sheet entrance and exit. The animation traces where the revealed content came from (usually a short translate + fade from the trigger's direction), which is what makes disclosure feel spatially coherent instead of items just blinking into existence.
- **Focus changes** — a focus ring or highlight moving between elements (e.g. keyboard navigation through a table or menu) can transition its position/opacity so the eye can track it, rather than snapping with no transitional cue.
- **Optimistic updates** — the brief moment an optimistically-applied change settles (a row's background flashing to `--success-subtle` and fading back to `--bg-surface` after a save confirms) gives quiet confirmation without a toast for every action. See [Perceived performance](#perceived-performance) and `references/states.md#partial--optimistic` for the underlying pattern this motion is confirming.

**Do not animate:**

- **Decorative loops** — anything that animates on a timer with no user action or state change behind it (idle pulsing icons, looping background shapes). If nothing happened, nothing should be moving.
- **Parallax** — scroll-linked depth effects belong to marketing/landing work (`frontend-design`/`ui-architect`), not a task surface where the user is trying to read a table while scrolling it.
- **Attention-seeking wiggles** — shake/bounce/wobble to "draw the eye" to a badge, count, or notification. This reads as anxious rather than confident, and enterprise users specifically find repeated unsolicited motion in a tool they use for hours a day fatiguing, not delightful.
- **Layout jumps** — content shifting position because something above or beside it changed size abruptly (an accordion snapping open without an animated height, a toast pushing page content down with no transition). This isn't really "no animation" so much as *unintentional*, jarring motion — either animate the size change smoothly or reserve the space up front so nothing has to jump.

If an animation doesn't correspond to a state that just changed, it doesn't belong on a product surface built on this skill's doctrine of optimizing for the user's task over the first impression.

## Perceived performance

Motion's biggest practical contribution on a data-dense surface isn't charm — it's making the interface *feel* fast independent of how fast the network actually is. Three tools do almost all of that work:

- **Optimistic UI** — apply the user's action to the screen immediately and reconcile with the server after, rather than waiting on a round-trip before showing anything changed. This is the single highest-leverage perceived-performance technique available and it's a state-management pattern, not a motion one — see `references/states.md#partial--optimistic` for the rollback contract that has to come with it. Motion's role here is small and specific: a short transition on the value/row that changed, so the update reads as "this just happened" rather than "this was always like this."
- **Skeletons over spinners for content-shaped waits** — a skeleton that mirrors the real layout lets the user start orienting to *where* content will land before it arrives, which measurably reads as faster than a centered spinner even at an identical actual load time. This is a `references/states.md#loading` pattern; the only motion involved is the skeleton's own subtle pulse (`animate-pulse`), never anything elaborate.
- **Staggering, used sparingly** — a small, fixed stagger (each item animating a beat after the previous). There is no token for per-item stagger intervals — they aren't transition durations — so keep this a small ad-hoc value, well under `--duration-fast`. This can make a short list of new items feel considered rather than dumped on screen. Keep this for **small lists only** — a handful of newly-added rows, a dropdown's few menu items. Staggering a 50-row table load turns a fast render into a *visibly slow* one, which is the opposite of the effect this technique exists to produce; large lists render as a single skeleton-to-content swap, no stagger.

The target across all three is specific: motion should make the interface feel **quick**, not feel **animated**. If a user could describe what they just saw as "everything moved," the balance has tipped from confirmation into spectacle — pull duration and distance back until the change is felt more than seen.

## prefers-reduced-motion

**This is a hard requirement, not a nice-to-have.** Vestibular disorders, migraines, and motion sensitivity are triggered by exactly the kind of transform/opacity animation this system otherwise encourages, and `prefers-reduced-motion: reduce` is the browser-level, user-controlled signal that a person has told their OS they need animation minimized. Ignoring it isn't a minor a11y gap — it makes the product physically uncomfortable or unusable for the users who set that preference, which is why this sits under the same "accessibility floor is mandatory" line in `SKILL.md` as visible focus and AA contrast, not under "nice polish if there's time."

The contract: when `reduce` is set, transitions and animations collapse to effectively instant (or, where a transition genuinely helps communicate a change even at near-zero duration, drop to a simple opacity crossfade instead of a transform/movement). Nothing should *translate, scale, or rotate* under `reduce` — swap to opacity-only or nothing at all.

The baseline CSS-only safety net, applied globally once (this is one of the few places in this system a literal value is correct — it's a deliberate global override, not a per-component token substitute):

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

This is a blunt instrument by design — it guarantees no element on the page can violate the preference, even ones a future component author forgets to handle individually. Ship it once, globally, alongside `tokens.css`, and it silently covers every Tailwind `transition-*`/`animate-*` utility in this system without touching component code.

For animation driven from React/JS rather than CSS transitions — most commonly `framer-motion` — the equivalent is respecting the library's own reduced-motion hook rather than relying solely on the CSS net, because JS-driven animation (spring physics, orchestrated multi-element sequences) isn't always expressible as a CSS `transition-duration` override:

```tsx
import { useReducedMotion, motion } from "framer-motion";

function Panel({ children }: { children: React.ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: reduce ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduce ? 0 : 0.18, ease: [0.2, 0, 0, 1] }}
    >
      {children}
    </motion.div>
  );
}
```

The pattern generalizes beyond `framer-motion`: whatever animation approach a project uses, it must have some code path that checks the reduced-motion preference and either skips the transform entirely or reduces it to a near-instant opacity change — the CSS media query above is the floor everyone gets for free, and JS-orchestrated animation needs its own explicit check on top of it.

(Note: `0.18` and `[0.2, 0, 0, 1]` above are `--duration-base`/`--ease-standard` restated as plain numbers, not new magic values — `framer-motion`'s `transition` prop animates via JS/WAAPI and can't consume a CSS custom property directly. Keep the numbers in sync with `tokens.css` by hand, or wrap them in a small shared constants module rather than repeating the literal in every component.)
