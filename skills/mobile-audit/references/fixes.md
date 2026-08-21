# Befund → Rezept

Jeder Befund aus `audit_static.py` und `audit_devices.py` verweist auf einen
Abschnitt hier. Ein Befund ohne Rezept ist eine Beschwerde, kein Audit.

Die Rezepte sind knapp gehalten: Das *Warum* des Handwerks steht in `mobile.md` in
den Familien-Skills (enterprise-ui, ui-architect, motion-landing), hier steht nur
der Handgriff.

---

## viewport-units

**Befund:** `100vh` (oder eine andere `vh`-Länge) in einer Höhenangabe.

**Warum es bricht:** `vh` rechnet mit dem *größten* Viewport — also ohne die
Browserleiste, die auf iOS und Android beim Scrollen ein- und ausfährt. Ein
`height: 100vh`-Element ist deshalb im Ausgangszustand höher als der sichtbare
Bereich; der untere Rand liegt unter der Leiste. Bei einem Vollbild-Hero fällt das
als abgeschnittener Call-to-Action auf, bei einem Sheet als unerreichbarer Button.

**Rezept:**

```css
/* vorher */  .hero  { height: 100vh; }
/* nachher */ .hero  { height: 100svh; }   /* kleinster Viewport: nichts wird verdeckt */
/* oder */    .sheet { height: 100dvh; }   /* dynamisch: wächst und schrumpft mit der Leiste */
```

`svh` ist die sichere Wahl, wenn nichts verdeckt sein darf. `dvh` ist die richtige
Wahl, wenn das Element beim Scrollen mitwachsen soll — es löst allerdings
Layout-Sprünge aus, wenn die Leiste ein- und ausfährt. Für Abstände und
Schriftgrößen ist `vh` selten die richtige Einheit; dort meist besser `rem`, `%`
oder Container Queries.

**Ausnahme:** `min-height: 100vh` auf einem Element, das ohnehin scrollt und dessen
unterer Rand nichts Bedienbares enthält, ist unkritisch — dann als Abweichung
begründen statt stumm zu lassen.

---

## input-font-size

**Befund:** Eine CSS-Regel setzt für `input`, `select` oder `textarea` eine
Schriftgröße unter 16 px.

**Warum es bricht:** Safari auf iOS zoomt beim Fokus automatisch in Eingabefelder
mit weniger als 16 px hinein. Der Zoom bleibt nach dem Verlassen des Feldes bestehen
— die Seite ist verschoben, horizontal scrollbar, und der Nutzer muss von Hand
herauszoomen. Es gibt keinen Weg, das abzuschalten, außer der Schriftgröße selbst
(`user-scalable=no` wäre einer, siehe `zoom-lock` — und ist der schlimmere Fehler).

**Rezept:**

```css
/* vorher */  .search input { font-size: 13px; }
/* nachher */ .search input { font-size: 16px; }
```

Soll das Feld optisch kleiner wirken, ist das eine Frage von `padding`, `height` und
Zeilenhöhe — nicht der Schriftgröße. Ein 16-px-Text in einem kompakten Feld sieht
kompakt aus; ein 13-px-Text in einem kompakten Feld sieht kaputt aus, sobald jemand
hineintippt.

---

## zoom-lock

**Befund:** `user-scalable=no` oder `maximum-scale=1` im Viewport-Meta.

**Warum es bricht:** Es nimmt Menschen die Vergrößerung weg — die wichtigste
Zugänglichkeitsfunktion, die mobile Browser haben. Betroffen ist nicht nur, wer
schlecht sieht: Jeder, der eine kleine Beschriftung, eine Fehlermeldung oder eine
Tabellenzelle genauer ansehen will, ist darauf angewiesen. WCAG 1.4.4 verlangt
Vergrößerung bis 200 %.

**Rezept:**

```html
<!-- vorher -->
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<!-- nachher -->
<meta name="viewport" content="width=device-width, initial-scale=1">
```

Die Sperre steht fast immer aus einem von zwei Gründen da: Entweder soll der
iOS-Zoom auf Eingabefelder unterdrückt werden — dafür gibt es `input-font-size`,
das den Grund beseitigt statt das Symptom. Oder das Layout bricht beim Zoomen, was
kein Zoom-Problem ist, sondern ein Layout-Problem (meist feste Pixelbreiten statt
`max-width`/`%`).

---

## hover-only

**Befund:** Eine CSS-Regel macht unter `:hover` etwas sichtbar oder verschiebt es,
und für dasselbe Ziel gibt es keine Focus-Entsprechung und keine
`@media (hover: hover)`-Kapselung.

**Warum es bricht:** Auf einem Touch-Gerät gibt es kein Hover. Was nur bei Hover
erscheint, existiert dort schlicht nicht — oder erscheint beim ersten Tap und
verschwindet beim zweiten, was schlimmer ist, weil der Tap zusätzlich dem Link
darunter gilt.

**Rezept — eine der drei Varianten:**

```css
/* 1. Focus-Pfad ergänzen: Tastatur und Touch bekommen denselben Zustand */
.nav__item:hover  .nav__flyout,
.nav__item:focus-within .nav__flyout { display: block; }

/* 2. Zustand explizit machen: ein Tap schaltet um, per Attribut gesteuert */
.nav__item[aria-expanded="true"] .nav__flyout { display: block; }

/* 3. Hover als Zugabe kapseln: nur dort, wo es Hover wirklich gibt */
@media (hover: hover) {
  .card:hover .card__actions { opacity: 1; }
}
```

Variante 2 ist die einzige, die für ein echtes Menü taugt — sie braucht etwas
JavaScript, macht den Zustand aber für Screenreader lesbar. Variante 3 ist richtig
für Zugaben, die auf Touch verzichtbar sind (eine Aktionsleiste, die dort ohnehin
dauerhaft sichtbar sein sollte). Variante 1 ist der billigste Fix und für
einfache Flyouts ausreichend.

**Bekannte Grenze:** JS-getriebene Hover-Menüs (`mouseenter`-Listener ohne
CSS-`:hover`) findet der Check nicht — Listener sind weder im Quelltext zuverlässig
erkennbar noch aus der laufenden Seite enumerierbar. Wer ein solches Menü hat, prüft
es von Hand: einmal mit dem Finger bedienen.

---

## Stufe 2 (Geräte-Matrix)

`horizontal-overflow`, `tap-target-size` und `safe-area` entstehen erst im Layout
und brauchen `audit_devices.py`. Ihre Rezepte kommen mit dem Skript — bis dahin
meldet Stufe 2 `ungeprüft`, und dieser Abschnitt bleibt bewusst leer statt
Rezepte für Befunde zu versprechen, die noch niemand gemessen hat.
