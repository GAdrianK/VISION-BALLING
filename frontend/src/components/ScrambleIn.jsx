import React, { useState, useEffect, useRef } from "react";

const GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+~|}{[]:;?><";

export function ScrambleIn({ text, scrollProgress, delay = 0, className = "", trigger = true }) {
  const [displayText, setDisplayText] = useState(() => 
    text.split("").map(c => c === " " ? " " : "\u00A0").join("")
  );
  const [opacity, setOpacity] = useState(1);
  const phaseRef = useRef("idle");
  const progressRef = useRef(0);
  const animationFrameId = useRef(null);
  const lastTimeRef = useRef(0);
  const startTimeoutRef = useRef(null);

  const scrollActive = scrollProgress > 0.015;

  useEffect(() => {
    if (startTimeoutRef.current) clearTimeout(startTimeoutRef.current);

    if (!trigger) return;

    if (scrollActive) {
      if (phaseRef.current === "idle") {
        phaseRef.current = "hidden";
        setDisplayText(text.split("").map(c => c === " " ? " " : "\u00A0").join(""));
        setOpacity(0);
      } else if (phaseRef.current === "revealed" || phaseRef.current === "scrambling-in") {
        startAnimation("scrambling-out");
      }
    } else {
      if (phaseRef.current === "idle" || phaseRef.current === "hidden" || phaseRef.current === "scrambling-out") {
        const activeDelay = phaseRef.current === "idle" ? delay : 0;
        startTimeoutRef.current = setTimeout(() => {
          startAnimation("scrambling-in");
        }, activeDelay);
      }
    }

    return () => {
      if (startTimeoutRef.current) clearTimeout(startTimeoutRef.current);
      if (animationFrameId.current) cancelAnimationFrame(animationFrameId.current);
    };
  }, [scrollActive, delay, trigger]);

  const startAnimation = (targetPhase) => {
    if (animationFrameId.current) cancelAnimationFrame(animationFrameId.current);
    phaseRef.current = targetPhase;
    progressRef.current = 0;
    lastTimeRef.current = performance.now();
    animate();
  };

  const animate = () => {
    const now = performance.now();
    const delta = now - lastTimeRef.current;
    lastTimeRef.current = now;

    const duration = phaseRef.current === "scrambling-in" ? 900 : 700;
    progressRef.current = Math.min(1, progressRef.current + delta / duration);

    const t = progressRef.current;

    if (phaseRef.current === "scrambling-in") {
      setOpacity(1);
      const updated = text
        .split("")
        .map((char, index) => {
          if (char === " ") return " ";
          const charThreshold = index / text.length;
          
          if (t >= charThreshold + 0.15) {
            return char;
          } else if (t >= charThreshold - 0.1) {
            return GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
          } else {
            return "\u00A0";
          }
        })
        .join("");

      setDisplayText(updated);

      if (t >= 1) {
        phaseRef.current = "revealed";
        setDisplayText(text);
        return;
      }
    } else if (phaseRef.current === "scrambling-out") {
      const updated = text
        .split("")
        .map((char, index) => {
          if (char === " ") return " ";
          const charThreshold = index / text.length;

          if (t >= charThreshold + 0.2) {
            return "\u00A0";
          } else if (t >= charThreshold - 0.05) {
            return GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
          } else {
            return char;
          }
        })
        .join("");

      setDisplayText(updated);
      setOpacity(Math.max(0, 1 - t * 1.5));

      if (t >= 1) {
        phaseRef.current = "hidden";
        setDisplayText(text.split("").map(c => c === " " ? " " : "\u00A0").join(""));
        setOpacity(0);
        return;
      }
    }

    animationFrameId.current = requestAnimationFrame(animate);
  };

  return (
    <span 
      className={className} 
      style={{ 
        opacity, 
        transition: "opacity 0.1s linear",
        display: "inline-block",
      }}
    >
      {displayText}
    </span>
  );
}
