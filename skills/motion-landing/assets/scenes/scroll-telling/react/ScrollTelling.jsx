import { useEffect, useState } from "react";
import "./ScrollTelling.css";

const DEFAULT_PANELS = [
  {
    title: "Erst die Idee.",
    body: "Jedes Panel trägt einen Gedanken. Der Scroll-Fortschritt entscheidet, welcher gerade zu sehen ist — kein Timer.",
  },
  {
    title: "Dann die Form.",
    body: "Ohne unterstützten Browser oder ohne JavaScript bleiben alle drei Panels einfach untereinander lesbar.",
  },
  {
    title: "Am Ende die Wirkung.",
    body: "Der letzte Gedanke der Sequenz — danach geht die Seite normal weiter.",
  },
];

/**
 * scroll-telling — React-Adapter der Vanilla-Demo unter
 * assets/scenes/scroll-telling/vanilla/index.html. Dieselbe CSS-Technik
 * (animation-timeline: scroll(), Fallback per Feature-Detection). React
 * übernimmt hier nur, WANN die Detection läuft (useEffect beim Mount) und WIE
 * sie ihr Ergebnis hält (State statt Klasse auf <html>) — siehe
 * references/adapters.md.
 */
export default function ScrollTelling({ panels = DEFAULT_PANELS }) {
  const [supportsScrollDriven, setSupportsScrollDriven] = useState(false);

  useEffect(() => {
    if (window.CSS?.supports?.("animation-timeline: scroll()")) {
      setSupportsScrollDriven(true);
    }
  }, []);

  return (
    <section className="scroll-telling" data-supports-scroll-driven={supportsScrollDriven}>
      <div className="scroll-telling__viewport">
        {panels.map((panel, index) => (
          <article className="scroll-telling__panel" key={panel.title} data-index={index}>
            <h2>{panel.title}</h2>
            <p>{panel.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
