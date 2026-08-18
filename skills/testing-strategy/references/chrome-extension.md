# chrome-extension — der tiefste Adapter

Geladen bei `primary: "chrome-extension"`. Vier Schichten, vom billigsten zum
teuersten. Keine Schicht ersetzt eine andere — sie fangen unterschiedliche
Fehlerklassen.

> **Wichtiger Hinweis zur Playwright-Fixture unten:** Sie ist vollständig
> ausgeschrieben, aber in dieser Umgebung **nicht real ausgeführt worden** —
> Playwright ist hier nicht installiert und wird hier nicht installiert.
> Nirgends in diesem Dokument bedeutet eine Formulierung, dass die Fixture
> „getestet" oder „erprobt" ist. Wer sie zum ersten Mal einsetzt, sollte mit
> einem einzigen trivialen Message-Handler beginnen, bevor echte Routen
> darauf aufbauen. Siehe `docs/known-limits.md`, Abschnitt testing-strategy.

## Schicht 1: Unit mit gemocktem `chrome.*`

Kein Browser nötig. `chrome.runtime`, `chrome.storage` etc. existieren im
Testprozess nicht — sie werden durch ein minimales Objekt ersetzt, das nur
die genutzten Methoden bereitstellt.

```ts
// background.test.ts (vitest)
import { describe, it, expect, vi, beforeEach } from "vitest";
import { handleMessage } from "./background";

function fakeChrome() {
  const listeners: Array<(msg: any, sender: any, sendResponse: any) => void> = [];
  return {
    runtime: {
      onMessage: { addListener: (fn: any) => listeners.push(fn) },
      sendMessage: vi.fn(),
      __trigger: (msg: any, sendResponse = vi.fn()) =>
        listeners.forEach((fn) => fn(msg, {}, sendResponse)),
    },
    storage: {
      local: {
        get: vi.fn().mockResolvedValue({}),
        set: vi.fn().mockResolvedValue(undefined),
      },
    },
  };
}

beforeEach(() => {
  (globalThis as any).chrome = fakeChrome();
});

describe("HANDLE_SYNC", () => {
  it("antwortet mit dem gespeicherten Zustand", async () => {
    const sendResponse = vi.fn();
    (globalThis as any).chrome.runtime.__trigger({ type: "HANDLE_SYNC" }, sendResponse);
    await Promise.resolve(); // Message-Handler ist async
    expect(sendResponse).toHaveBeenCalledWith(expect.objectContaining({ ok: true }));
  });
});
```

Diese Schicht ist billig und deckt Logikfehler — nicht Browser-/MV3-spezifisches
Verhalten wie Service-Worker-Lifecycle.

## Schicht 2: Integration via Playwright Persistent Context

`--load-extension` funktioniert nur mit einem **persistenten** Kontext (kein
`browser.newContext()`), und nur in Chromium, headful oder mit
`--headless=new`. Das ist der teuerste, aber realistischste Layer.

```ts
// e2e/fixtures.ts — Persistent-Context-Fixture mit geladener Extension.
// UNGETESTET in diesem Repo — siehe Warnung oben.
import { test as base, chromium, type BrowserContext } from "@playwright/test";
import path from "node:path";

const EXTENSION_PATH = path.resolve(__dirname, "../dist");

export const test = base.extend<{
  context: BrowserContext;
  extensionId: string;
}>({
  // eslint-disable-next-line no-empty-pattern
  context: async ({}, use) => {
    const context = await chromium.launchPersistentContext("", {
      headless: false, // MV3-Service-Worker starten in vielen Chromium-Versionen
                        // im klassischen Headless-Modus nicht zuverlässig —
                        // "--headless=new" ist der Fallback, wenn ein Display fehlt.
      args: [
        `--disable-extensions-except=${EXTENSION_PATH}`,
        `--load-extension=${EXTENSION_PATH}`,
      ],
    });
    await use(context);
    await context.close();
  },

  extensionId: async ({ context }, use) => {
    // MV3: der Service Worker registriert sich beim Start der Extension.
    let [worker] = context.serviceWorkers();
    if (!worker) {
      worker = await context.waitForEvent("serviceworker", { timeout: 10_000 });
    }
    const extensionId = worker.url().split("/")[2];
    await use(extensionId);
  },
});

export const expect = test.expect;
```

```ts
// e2e/popup.spec.ts — Beispielnutzung. UNGETESTET, siehe Warnung oben.
import { test, expect } from "./fixtures";

test("Popup zeigt den gespeicherten Zustand", async ({ context, extensionId }) => {
  const page = await context.newPage();
  await page.goto(`chrome-extension://${extensionId}/popup.html`);
  await expect(page.getByTestId("status")).toBeVisible();
});
```

## Schicht 3: SW-Termination-Chaostest — das Kernrisiko

MV3-Service-Worker werden vom Browser nach Inaktivität beendet und bei
Bedarf neu gestartet. Zustand, der nur im Arbeitsspeicher des Workers lebt
(nicht in `chrome.storage`), ist nach einem Neustart weg — ein Message-Handler,
der das nicht einplant, verliert still Daten oder antwortet falsch. Das ist
der Fehler, den kein anderer Layer fängt: Schicht 1 mockt `chrome.*` und sieht
keinen echten Neustart; Schicht 2 prüft normales Verhalten, aber typischerweise
ohne den Worker gezielt zu beenden.

```ts
// e2e/sw-termination.spec.ts — Muster für den Chaostest. UNGETESTET, siehe Warnung oben.
import { test, expect } from "./fixtures";

test("HANDLE_SYNC überlebt einen erzwungenen SW-Neustart", async ({ context, extensionId }) => {
  const page = await context.newPage();
  await page.goto(`chrome-extension://${extensionId}/popup.html`);

  // 1. Zustand erzeugen, der den Neustart überleben soll.
  await page.evaluate(() =>
    chrome.runtime.sendMessage({ type: "HANDLE_SYNC", payload: { key: "a" } })
  );

  // 2. Service Worker gezielt beenden. Playwrights CDP-Anbindung erlaubt das
  //    über die Chrome-DevTools-Protocol-Session des Workers; alternativ über
  //    chrome://serviceworker-internals im UI, hier über CDP für Determinismus.
  const worker = context.serviceWorkers().find((w) => w.url().includes(extensionId));
  const client = await context.newCDPSession(page);
  await client.send("ServiceWorker.stopWorker", {
    versionId: /* aus ServiceWorker.enable-Events ermitteln */ "",
  });
  // Alternative, falls die Zielversion nicht bekannt ist: Chrome über Idle
  // erzwingen (`chrome://inspect/#service-workers` manuell, oder länger
  // warten als die Idle-Timeout-Schwelle in einem gezielten Testlauf).

  // 3. Ein Event auslösen, das den Worker neu startet.
  await page.reload();

  // 4. State-Rehydrierung prüfen: Kam der vor dem Neustart geschriebene
  //    Zustand aus chrome.storage zurück, oder ist er verloren?
  const rehydrated = await page.evaluate(
    () => new Promise((resolve) => chrome.runtime.sendMessage({ type: "GET_STATE" }, resolve))
  );
  expect(rehydrated).toMatchObject({ key: "a" });
});
```

**Konvention:** Jede neue oder geänderte Message-Route bekommt ihren eigenen
Termination-Test nach diesem Muster — kein Sammeltest für alle Routen. Der
Test-Plan-Block nennt die Schicht explizit als `SW-Termination` mit dem
Route-Namen (siehe SKILL.md-Contract).

## Schicht 4: Content-Script-Tests gegen Fixture-Seiten

Content-Scripts laufen im Kontext einer fremden Seite. Live-Websites ändern
ihr DOM ohne Vorwarnung — ein Test, der gegen `https://example.com` läuft,
bricht irgendwann aus Gründen, die nichts mit der Extension zu tun haben.

- Eine **eingefrorene Fixture-Seite** (statisches HTML im Repo, z. B.
  `e2e/fixtures/pages/product-page.html`) bildet die relevanten DOM-Strukturen
  nach, gegen die das Content-Script tatsächlich matcht (Selektoren,
  `data-`-Attribute).
- `page.goto('file://' + path.resolve(...))` oder ein lokaler Static-Server
  lädt die Fixture-Seite, das Content-Script injiziert sich über
  `--load-extension` wie in Schicht 2.
- Ändert sich die Ziel-Website real, wird die Fixture-Seite bewusst
  aktualisiert — ein sichtbarer Commit, kein stiller Drift.

## Promotion-Hinweis

Dieser Adapter ist bereits nahe an der ~300-Zeilen-Schwelle aus der
SKILL.md-Promotion-Regel — vor allem, sobald ein echtes CDP-Hilfsskript für
Schicht 3 dazukommt (die `versionId`-Ermittlung oben ist noch keine
Referenzimplementierung, nur ein Muster). Wird daraus ein eigenes
`scripts/`-Verzeichnis, wird `chrome-extension.md` zur Geschwister-Skill
befördert.
