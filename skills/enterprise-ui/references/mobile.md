# Mobile craft

Shared reference. Byte-identical copies live in `enterprise-ui`, `ui-architect` and
`motion-landing`; `tests/test_mobile_reference_drift.py` fails if they diverge. Edit
one, run the test, copy to the other two.

Load this whenever a view will also be served to phones — for anything on the web,
that means always. The verification counterpart is the `mobile-audit` skill: this
file says how to build it, that skill proves whether you did.

---

## 1. Build narrow first, then add

Design the base layout for a ~360 px viewport, then *add* with `min-width` media
queries or container queries. Never build wide and shrink: shrinking produces layouts
where the mobile case is a pile of overrides fighting desktop rules, and every new
desktop rule silently re-breaks the phone.

Container queries beat media queries wherever a component can appear in more than one
slot — the component asks how much room *it* has, not how wide the window is.

## 2. Viewport truths

**`vh` lies on phones.** `100vh` measures the viewport *without* the browser chrome
that slides in and out while scrolling, so a `height: 100vh` hero is taller than what
you can see and its bottom edge — usually the primary action — sits under the toolbar.
Use `100svh` when nothing may be hidden, `100dvh` when the element should grow and
shrink with the chrome. For spacing and type, `vh` is almost never the right unit.

**Safe areas are not decoration.** On notched devices, anything anchored to a viewport
edge lands under the notch or the home indicator. Anchor with the insets, not against
them:

```css
.bottom-bar {
  padding-bottom: max(12px, env(safe-area-inset-bottom));
}
```

**Never let the page scroll sideways.** A single overwide element makes the whole
document pan, which breaks every fixed element and makes the layout feel broken even
where it isn't. Wide content — tables, code blocks, diagrams, chart canvases — gets
its own `overflow-x: auto` container, with a visual hint (edge shadow) that there is
more to the side.

**Never disable zoom.** `user-scalable=no` and `maximum-scale=1` remove the single most
important accessibility affordance mobile browsers have, and WCAG 1.4.4 requires
magnification to 200 %. The viewport meta you want is exactly this:

```html
<meta name="viewport" content="width=device-width, initial-scale=1">
```

If you were reaching for the zoom lock to stop iOS zooming into inputs, fix the cause
instead — see §4.

## 3. Touch has no hover

Hover does not exist on a touch device. A menu that only opens on `:hover` either
never opens, or opens on the first tap and closes on the second — while that same tap
also activates whatever is underneath.

Every hover-revealed thing needs one of three treatments:

```css
/* 1. Focus path — cheapest fix, covers keyboard and touch */
.menu:hover .submenu,
.menu:focus-within .submenu { display: block; }

/* 2. Explicit state — the only option that works for a real menu */
.menu[aria-expanded="true"] .submenu { display: block; }

/* 3. Hover as a bonus — for things that should be permanently visible on touch */
@media (hover: hover) {
  .card:hover .card__actions { opacity: 1; }
}
```

**Hit areas.** The floor is 24×24 px (WCAG 2.2 AA) — the same number
`a11y-floor.md` sets for this design system, not a separate mobile rule. Pad the *hit
area*, never the glyph: a 12 px icon with a 24 px invisible target is correct, an icon
whose clickable region matches its own pixels is not. For primary actions on a phone,
44×44 px is the comfortable size worth aiming for; it is a target, not a threshold.

**Thumb zone.** On a phone the bottom half of the screen is where the thumb rests.
Primary actions belong there. Destructive actions belong out of it — an accidental
"delete" is the price of putting it where the thumb already is.

## 4. The virtual keyboard eats the bottom of the screen

**Inputs below 16 px trigger iOS zoom.** Safari zooms into any focused field with a
font smaller than 16 px, and the zoom *stays* after the field is left — the page ends
up shifted and horizontally scrollable. If the field should look smaller, change
`padding`, `height` and line-height. Never the font size.

**Nothing fixed may sit where the keyboard will be.** The keyboard covers roughly the
bottom third. Elements in normal flow are fine — the browser scrolls the focused field
into view. Elements in a `fixed` or `sticky` ancestor are not: they stay exactly where
they are, which is how the classic defect happens, a submit bar pinned to the bottom
and invisible the moment someone types.

Either put the bar in normal flow, or move it with the visual viewport:

```js
visualViewport.addEventListener('resize', () => {
  bar.style.transform = `translateY(-${innerHeight - visualViewport.height}px)`;
});
```

Declare the behaviour you want while you are at it:
`<meta name="viewport" content="width=device-width, initial-scale=1, interactive-widget=resizes-content">`.

## 5. Rebuild patterns, don't squeeze

A layout that works narrow is usually a *different* layout, not the same one scaled.

| Wide | Narrow |
| --- | --- |
| Data table | Card stack (one card per row, label-value pairs), or the table in its own horizontal scroll container with the first column pinned |
| Multi-column form | One column. Always. Two fields side by side on a phone means two cramped fields |
| Sidebar navigation | Bottom navigation for ≤5 destinations, otherwise a sheet or drawer |
| Hover toolbar on a row | Permanently visible actions, or a `…` menu per row |
| Modal dialog | Full-screen sheet — a centered modal on a 360 px screen is a modal with no margins |

For tables specifically: decide per column what survives. A card stack that reproduces
all fourteen columns as label-value pairs is worse than the table it replaced.

---

## How this gets verified

`mobile-audit` measures most of the above: `100vh`, input font size, zoom lock and
hover-only rules from the source; overflow, hit areas, safe areas and the keyboard
geometry from a device matrix. What it cannot check — thumb-zone placement, whether a
card stack picked the right columns, whether a bottom nav has the right five
destinations — is on you.
