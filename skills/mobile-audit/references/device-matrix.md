# Die Geräte-Matrix — und warum genau diese drei

Die Profile stehen in `assets/audit-config.json` und sind pro Projekt überschreibbar.
Drei Stück, nicht zehn: **Jedes Profil muss einen Check tragen, den kein anderes
auslöst.** Ein viertes Gerät, das nur „auch verbreitet" ist, verlängert die Laufzeit
und findet nichts Neues.

| Profil | Viewport | Trägt | Ohne dieses Profil |
| --- | --- | --- | --- |
| `android-schmal` | 360×800 | horizontales Overflow | Ein 400-px-Element fällt erst auf, wenn der Viewport schmaler ist. Auf 390 px bleibt es unentdeckt. |
| `iphone-notch` | 390×844, Insets 47/34 | Safe-Area | Das einzige Profil mit Insets. Ohne es ist der `safe-area`-Check blind — er hat schlicht nichts zu vergleichen. |
| `tablet` | 820×1180 | Breakpoint-Wechsel | Prüft die Gegenrichtung: Greift das Mehrspalten-Layout wieder? Ein Layout, das auf 820 px immer noch die Telefon-Ansicht zeigt, ist genauso kaputt wie eins, das auf 360 px die Desktop-Ansicht zeigt. |

Der `tap-target-size`-Check läuft auf allen drei, weil sich Trefferflächen zwischen
Breakpoints ändern — eine Icon-Reihe, die auf 390 px passt, kann auf 360 px unter den
Boden rutschen.

## Was gestrichen wurde

**Phablet (414×896).** Im Entwurf zu Spec 15 enthalten, dann gestrichen: Es liegt
zwischen `iphone-notch` und `tablet` und trägt keinen eigenen Check. Was es findet,
findet `android-schmal` früher oder `tablet` deutlicher.

**Landscape.** Bewusst offen (siehe Spec 15, Open questions). Querformat ändert die
Tastatur-Geometrie erheblich — K ist dort relativ zur Höhe viel größer —, und der
`keyboard_px`-Wert müsste je Orientierung getrennt geführt werden. Bis das entschieden
ist, prüft die Matrix nur Hochformat, und das steht so im Bericht statt still zu
bleiben.

## Die Werte, die kein Messwert sind

`keyboard_px` ist ein **Modell**, keine Messung. Der Spike zu Spec 15 hat gezeigt, dass
sich eine virtuelle Tastatur mit Chromium nicht emulieren lässt:
`Emulation.setDeviceMetricsOverride` schrumpft Layout und visuellen Viewport gemeinsam
(gemessen 844 → 500), sodass ein `position: fixed; bottom: 0` mitwandert und die
kaputte Seite heil aussieht; `Emulation.setVisibleSize` bleibt folgenlos. Deshalb wird
die verdeckte Zone gerechnet statt erzeugt, und Befunde aus diesem Check tragen
`modelliert` statt `gemessen`.

Die Werte (300 / 336 / 400 px) sind typische Höhen der Systemtastatur im Hochformat
inklusive Vorschlagsleiste. Wer eine App mit eigener Eingabeleiste hat, erhöht sie im
Projekt-Override — das ist eine Angabe über das eigene Produkt, keine über das Gerät.

`safe_area_top`/`safe_area_bottom` sind dagegen echte Gerätewerte (47 px Notch, 34 px
Home-Anzeige beim iPhone-Profil). Sie fließen als Vergleichsgrenze ein, nicht als
Emulation: Playwright rendert keine Notch, die Insets sind in der Testumgebung `0`.
Der Check misst also die Position des fixierten Elements gegen einen deklarierten
Grenzwert — auch das ist ein Modell, und auch das steht im Bericht.

## Warum CPU- und Netzdrosselung fehlen

Der Entwurf sah gedrosselte CPU und Netz vor. Beides gehört zu Performance-Budgets,
und die laufen bereits in `motion-landing/scripts/verify.py` (LCP/CLS/INP). Hier geht
es um Bedienbarkeit auf kleinen Touch-Geräten; eine zweite, schwächere
Performance-Messung neben einer bestehenden wäre doppelte Zuständigkeit — genau das
Familien-Problem, das Spec 15 vermeiden will.
