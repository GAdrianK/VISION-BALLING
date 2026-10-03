import PropTypes from "prop-types";

export default function BetaStamp({
  size = "large",
  variant = "classic",
  className = "",
  onClick = null,
  showHint = false,
}) {
  const isInteractive = Boolean(onClick);

  const handleKeyDown = (e) => {
    if (isInteractive && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      onClick(e);
    }
  };

  const sizeClass =
    size === "hero"
      ? "beta-stamp-hero"
      : size === "small"
      ? "beta-stamp-small"
      : "beta-stamp-large";

  return (
    <div
      className={`beta-stamp-wrapper ${sizeClass} ${
        isInteractive ? "beta-stamp-interactive" : ""
      } ${className}`}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      role={isInteractive ? "button" : "img"}
      tabIndex={isInteractive ? 0 : undefined}
      aria-label="Tester VISION-BALLING BETA"
    >
      <div className="beta-stamp-frame">
        <svg
          viewBox="0 0 136 46"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="beta-stamp-svg"
          aria-hidden="true"
        >
          {/* Subtle distressed / textured filter for real ink rubber-stamp feel */}
          <defs>
            <filter id="stamp-ink-distress" x="-5%" y="-5%" width="110%" height="110%">
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.04"
                numOctaves="2"
                result="noise"
              />
              <feDisplacementMap
                in="SourceGraphic"
                in2="noise"
                scale="1.2"
                xChannelSelector="R"
                yChannelSelector="G"
              />
            </filter>
          </defs>

          {variant === "broken" ? (
            /* Variant B — Subtle broken lines suggesting the stamp plate */
            <g stroke="currentColor" strokeWidth="2" opacity="0.88">
              {/* Corner ticks */}
              <path d="M 3 14 L 3 3 L 18 3" />
              <path d="M 118 3 L 133 3 L 133 14" />
              <path d="M 3 32 L 3 43 L 18 43" />
              <path d="M 118 43 L 133 43 L 133 32" />
              {/* Minimal center indicators */}
              <line x1="62" y1="3" x2="74" y2="3" strokeDasharray="3 3" />
              <line x1="62" y1="43" x2="74" y2="43" strokeDasharray="3 3" />
            </g>
          ) : (
            /* Variant A — Classic rectangular double border rubber stamp */
            <>
              {/* Outer thick border with authentic stamp imperfection */}
              <rect
                x="2"
                y="2"
                width="132"
                height="42"
                rx="2"
                stroke="currentColor"
                strokeWidth="2.75"
                filter="url(#stamp-ink-distress)"
              />

              {/* Inner thin border with slight print gaps */}
              <rect
                x="6"
                y="6"
                width="124"
                height="34"
                rx="1"
                stroke="currentColor"
                strokeWidth="1"
                strokeDasharray="40 2 24 1.5 50 2"
                opacity="0.9"
              />
            </>
          )}

          {/* Stamp Typography: uppercase condensed/mono bold */}
          <text
            x="50%"
            y="54%"
            textAnchor="middle"
            dominantBaseline="middle"
            fill="currentColor"
            style={{
              fontFamily: "var(--font-mono), 'JetBrains Mono', 'Fira Code', monospace",
              fontWeight: 900,
            }}
            fontSize="23"
            letterSpacing="0.22em"
          >
            BETA
          </text>
        </svg>
      </div>

      {showHint && <span className="beta-stamp-subhint">TESTER LA BETA →</span>}
    </div>
  );
}

BetaStamp.propTypes = {
  size: PropTypes.oneOf(["small", "large", "hero"]),
  variant: PropTypes.oneOf(["classic", "broken"]),
  className: PropTypes.string,
  onClick: PropTypes.func,
  showHint: PropTypes.bool,
};
