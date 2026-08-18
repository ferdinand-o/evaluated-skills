import { useEffect, useRef } from "react";
import "./CanvasMoment.css";

const PARTICLE_COUNT = 90; // an ein gedrosseltes Profil angepasst, nicht an die Entwicklungsmaschine

/**
 * canvas-moment — React-Adapter der Vanilla-Demo unter
 * assets/scenes/canvas-moment/vanilla/index.html. Derselbe
 * requestAnimationFrame-Loop, aber in useEffect mit useRef statt
 * Modul-Top-Level-Variablen, mit sauberem Cleanup (IntersectionObserver
 * trennen, rAF stoppen) — siehe references/adapters.md.
 */
export default function CanvasMoment({
  title = "Der eine Moment.",
  body = "Ein generatives Partikelfeld, reserviert für genau diese Szene. Läuft nur, während sie im Viewport ist, und respektiert reduzierte Bewegung als Standbild statt als Loop.",
}) {
  const sectionRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    const section = sectionRef.current;
    const canvas = canvasRef.current;
    if (!section || !canvas) return undefined;

    const ctx = canvas.getContext("2d");
    let particles = [];
    let rafId = null;
    const reducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

    function resize() {
      canvas.width = section.clientWidth;
      canvas.height = section.clientHeight;
    }

    function makeParticles() {
      particles = Array.from({ length: PARTICLE_COUNT }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: 1 + Math.random() * 2,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
      }));
    }

    function drawFrame(advance) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "rgba(110, 231, 183, 0.7)";
      particles.forEach((p) => {
        if (advance) {
          p.x += p.vx;
          p.y += p.vy;
          if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
          if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    function loop() {
      drawFrame(true);
      rafId = requestAnimationFrame(loop);
    }

    function start() {
      if (rafId !== null) return;
      if (reducedMotionQuery.matches) {
        // Pflicht-Gate: kein Loop, ein einzelnes Standbild statt Bewegung.
        drawFrame(false);
        return;
      }
      loop();
    }

    function stop() {
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
    }

    resize();
    makeParticles();

    const handleResize = () => {
      resize();
      makeParticles();
      drawFrame(false);
    };
    window.addEventListener("resize", handleResize);

    const observer = new IntersectionObserver(
      (entries) => entries.forEach((entry) => (entry.isIntersecting ? start() : stop())),
      { threshold: 0.1 },
    );
    observer.observe(section);

    const handleMotionChange = () => {
      stop();
      if (section.getBoundingClientRect().top < window.innerHeight) start();
    };
    reducedMotionQuery.addEventListener("change", handleMotionChange);

    return () => {
      stop();
      observer.disconnect();
      window.removeEventListener("resize", handleResize);
      reducedMotionQuery.removeEventListener("change", handleMotionChange);
    };
  }, []);

  return (
    <section className="canvas-moment" ref={sectionRef}>
      <canvas className="canvas-moment__canvas" ref={canvasRef} aria-hidden="true" />
      {/* Text bleibt unabhängig vom Canvas im DOM — "Inhalte sind ohne JS
          lesbar" gilt auch hier, das Canvas ist reine Verzierung. */}
      <div className="canvas-moment__caption">
        <h2>{title}</h2>
        <p>{body}</p>
      </div>
    </section>
  );
}
