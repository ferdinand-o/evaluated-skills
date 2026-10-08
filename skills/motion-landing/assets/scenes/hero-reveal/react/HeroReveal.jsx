import "./HeroReveal.css";

/**
 * hero-reveal — React-Adapter der Vanilla-Demo unter
 * assets/scenes/hero-reveal/vanilla/index.html. Gleiche Mechanik (CSS
 * @keyframes mit animation-delay, nur transform/opacity, reduced-motion als
 * Pflicht-Gate im Stylesheet) — React ändert nichts an der Animationstechnik,
 * nur an der Komponentenstruktur (siehe references/adapters.md).
 */
export default function HeroReveal({
  title = "Ein Werkzeug, das mitdenkt.",
  subtitle = "Hero-Reveal orchestriert drei Elemente beim Laden — nacheinander, mit kurzem Versatz, nie alle gleichzeitig.",
  ctaLabel = "Jetzt starten",
  ctaHref = "#",
}) {
  return (
    <section className="hero-reveal">
      <h1 className="hero-reveal__title">{title}</h1>
      <p className="hero-reveal__subtitle">{subtitle}</p>
      <a className="hero-reveal__cta" href={ctaHref}>
        {ctaLabel}
      </a>
    </section>
  );
}
