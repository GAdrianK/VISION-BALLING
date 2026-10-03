import { useEffect, useState, useCallback } from "react";

export default function LandingPage({ onEnter }) {
  const [fading, setFading] = useState(false);

  const handleEnter = useCallback(() => {
    if (fading) return;
    setFading(true);
    setTimeout(() => {
      onEnter();
    }, 200);
  }, [fading, onEnter]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
        e.preventDefault();
        handleEnter();
      }
    };

    const handleWheel = (e) => {
      if (Math.abs(e.deltaY) > 20) {
        handleEnter();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("wheel", handleWheel, { passive: true });

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("wheel", handleWheel);
    };
  }, [handleEnter]);

  return (
    <main
      className="landing-shell"
      style={{
        opacity: fading ? 0 : 1,
        transition: "opacity 200ms ease",
      }}
      onClick={handleEnter}
      role="button"
      tabIndex={0}
      aria-label="Entrer dans l'application VISION-BALLING"
    >
      <div className="landing-logo-container">
        <img
          src="/brand/vision-balling-logo.png"
          alt="VISION-BALLING"
          className="landing-logo-img"
          width="1124"
          height="789"
          loading="eager"
        />
      </div>

      <div className="landing-enter-cta">
        <span>ENTER</span>
      </div>
    </main>
  );
}
