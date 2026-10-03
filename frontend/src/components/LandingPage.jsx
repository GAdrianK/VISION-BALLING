import { useEffect, useState, useCallback } from "react";
import PropTypes from "prop-types";
import BetaStamp from "./BetaStamp";

export default function LandingPage({ onEnter, onBeta }) {
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

        <div
          className="landing-beta-stamp-slot"
          onClick={(e) => {
            e.stopPropagation();
            if (onBeta) onBeta();
          }}
        >
          <BetaStamp
            size="large"
            showHint={false}
            onClick={(e) => {
              e.stopPropagation();
              if (onBeta) onBeta();
            }}
          />
        </div>
      </div>

      <div className="landing-enter-cta">
        <span>ENTER</span>
      </div>
    </main>
  );
}

LandingPage.propTypes = {
  onEnter: PropTypes.func.isRequired,
  onBeta: PropTypes.func,
};
