import { useEffect, useState } from "react";
import "./StickyPin.css";

const DEFAULT_STEPS = [
  {
    title: "Schritt eins",
    body: "Das Element rechts bleibt stehen, während dieser Text vorbeiscrollt — reines CSS position: sticky, kein JavaScript für das Pinning.",
  },
  {
    title: "Schritt zwei",
    body: "Ohne unterstützten Browser oder JavaScript bleibt jeder Schritt einfach direkt sichtbar.",
  },
  {
    title: "Schritt drei",
    body: "Sobald der Container endet, löst sich das Pinning wieder — die Höhe stand von Anfang an fest, kein Layout-Sprung beim Loslassen.",
  },
];

/**
 * sticky-pin — React-Adapter der Vanilla-Demo unter
 * assets/scenes/sticky-pin/vanilla/index.html. Das Pinning selbst
 * (position: sticky) ist reines CSS und identisch in beiden Welten; React
 * übernimmt nur, wann die Feature-Detection für die begleitende
 * Opacity-Choreografie läuft (siehe references/adapters.md).
 */
export default function StickyPin({ steps = DEFAULT_STEPS, pinnedLabel = "Gepinntes Element" }) {
  const [supportsScrollDriven, setSupportsScrollDriven] = useState(false);

  useEffect(() => {
    if (window.CSS?.supports?.("animation-timeline: view()")) {
      setSupportsScrollDriven(true);
    }
  }, []);

  return (
    <section className="sticky-pin" data-supports-scroll-driven={supportsScrollDriven}>
      <div className="sticky-pin__grid">
        <div className="sticky-pin__pinned" aria-hidden="true">
          {pinnedLabel}
        </div>
        <div className="sticky-pin__commentary">
          {steps.map((step) => (
            <div className="sticky-pin__step" key={step.title}>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
