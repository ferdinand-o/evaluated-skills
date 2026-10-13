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

## horizontal-overflow

**Befund:** Das Dokument ist breiter als der sichtbare Viewport; der genannte Selektor
ist das erste Element, das über den Rand ragt.

**Warum es bricht:** Ein einziges überbreites Element lässt die ganze Seite seitwärts
schwingen. Fixierte Leisten verlieren dabei ihre Ausrichtung, Text wird beim Zurückwischen
abgeschnitten, und die Seite fühlt sich kaputt an — auch dort, wo sie es nicht ist.

**Rezept:** Nicht das Element schmaler machen, sondern ihm einen eigenen Scroll-Bereich
geben. Breiter Inhalt darf breit sein; nur der Seitenkörper darf nicht mitscrollen.

```css
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.table-wrap table { min-width: 640px; }   /* darf breit bleiben */
```

Häufige Ursachen, bevor du den Container baust: feste `width` in px statt `max-width`,
ein `100vw` (rechnet die Scrollbar mit), lange Zeichenketten ohne
`overflow-wrap: anywhere`, negative Margins in einem Grid.

**Achtung:** `overflow-x: hidden` auf `body` versteckt den Befund, statt ihn zu beheben —
der Inhalt ist dann unerreichbar statt nur unbequem.

---

## tap-target-size

**Befund:** Die gemessene Trefferfläche eines Bedienelements liegt unter 24×24 px.

**Warum es bricht:** 24×24 px ist der Boden aus WCAG 2.2 AA. Darunter trifft ein Daumen
zuverlässig daneben — besonders bei Elementen, die dicht nebeneinander liegen, wo ein
Fehlgriff nicht nur nichts tut, sondern das Falsche.

**Rezept:** Die *Trefferfläche* wächst, nicht die Glyphe. Ein 12-px-Icon mit 24-px-Ziel
ist richtig; ein Ziel, das exakt die Icon-Pixel umschließt, ist es nicht.

```css
.icon-btn {
  min-width: 24px; min-height: 24px;      /* Boden */
  display: inline-grid; place-items: center;
  padding: 6px;                            /* vergroessert das Ziel, nicht das Icon */
}
/* Reicht der Platz im Layout nicht, das Ziel unsichtbar vergroessern: */
.icon-btn { position: relative; }
.icon-btn::after { content: ""; position: absolute; inset: -8px; }
```

Für primäre Aktionen auf dem Telefon sind 44×44 px die bequeme Größe — ein Ziel, kein
Grenzwert. Der Audit meldet sie nicht als Verstoß.

**Weicht euer System bewusst ab?** Dann in `.skills/mobile-audit/audit-config.json`
überschreiben, mit Begründung im Projekt — nicht stillschweigend unterschreiten.

---

## safe-area

**Befund:** Ein fixiertes Bedienelement ragt in die Notch-Zone oder in den Bereich der
Home-Anzeige.

**Warum es bricht:** Auf Geräten mit Aussparung ist der Viewport nicht der nutzbare
Bereich. Was am Rand klebt, liegt teilweise unter der Kamera-Insel oder unter dem
Home-Strich — und dort nimmt das System die Berührung entgegen, nicht deine Schaltfläche.

**Rezept:** Mit den Insets rechnen statt gegen sie. `max()` sorgt dafür, dass auch Geräte
ohne Aussparung einen vernünftigen Abstand behalten.

```css
.bottom-bar {
  position: fixed; inset-inline: 0; bottom: 0;
  padding-bottom: max(12px, env(safe-area-inset-bottom));
}
.top-bar { padding-top: max(8px, env(safe-area-inset-top)); }
```

Voraussetzung ist `viewport-fit=cover` im Viewport-Meta — ohne das sind die `env()`-Werte
immer `0` und die Regel wirkt, als sei sie nicht da.

**Zur Einordnung:** Der Audit rendert keine echte Notch; er vergleicht die Position gegen
die deklarierten Insets des Geräteprofils. Der Befund ist damit so gut wie das Profil —
siehe `device-matrix.md`.

---

## keyboard-overlay

**Befund:** Ein fixiertes Bedienelement liegt in dem Bereich, den die Bildschirmtastatur
verdeckt, und die Seite hat mindestens ein Eingabefeld.

**Warum es bricht:** Die Tastatur nimmt etwa das untere Drittel. Elemente im normalen
Fluss sind unkritisch — der Browser scrollt das fokussierte Feld hinein. Fixierte bleiben
liegen. Der Klassiker ist die angepinnte „Absenden"-Leiste, die genau in dem Moment
verschwindet, in dem jemand zu tippen beginnt.

**Rezept — eine der beiden Varianten:**

```js
// 1. Die Leiste mit dem sichtbaren Viewport mitfuehren
const bar = document.querySelector('.submit-bar');
visualViewport.addEventListener('resize', () => {
  bar.style.transform = `translateY(-${innerHeight - visualViewport.height}px)`;
});
```

```html
<!-- 2. Dem Browser sagen, dass er das Layout verkleinern soll -->
<meta name="viewport" content="width=device-width, initial-scale=1, interactive-widget=resizes-content">
```

Variante 2 ist die einfachere und reicht oft; sie wirkt allerdings nur dort, wo die
Engine sie unterstützt. Wenn beides ausscheidet, gehört die Leiste in den normalen Fluss —
ein Button am Formularende, den der Browser mitscrollt, ist besser als einer, der zum
falschen Zeitpunkt unsichtbar wird.

**Zur Einordnung:** Dieser Befund ist `modelliert`, nicht `gemessen`. Eine virtuelle
Tastatur lässt sich mit Chromium nicht emulieren (siehe `device-matrix.md`), deshalb
rechnet der Audit mit einer deklarierten Tastaturhöhe je Profil. Was er nicht sieht: ob
deine Seite beim Fokus korrekt scrollt. Das prüfst du mit dem Finger.

---

## Was Stufe 2 nicht prüft

Daumen-Zonen, ob ein Karten-Stapel die richtigen Spalten behalten hat, ob eine Bottom-Nav
die richtigen fünf Ziele führt — das sind Entwurfsfragen, keine Messwerte. Sie stehen in
`mobile.md` und bleiben deine Aufgabe.
