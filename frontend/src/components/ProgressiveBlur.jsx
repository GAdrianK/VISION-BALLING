import React from "react";

export function ProgressiveBlur({
  className = "",
  backgroundColor = "#000000",
  position = "bottom",
  height = "150px",
  blurAmount = "4px",
}) {
  const isTop = position === "top";

  return (
    <div
      className={`pointer-events-none absolute left-0 w-full select-none ${className.includes("z-") ? "" : "z-40"} ${className}`}
      style={{
        [isTop ? "top" : "bottom"]: 0,
        height,
        background: isTop
          ? `linear-gradient(to top, transparent, ${backgroundColor})`
          : `linear-gradient(to bottom, transparent, ${backgroundColor})`,
        maskImage: isTop
          ? `linear-gradient(to bottom, ${backgroundColor} 50%, transparent)`
          : `linear-gradient(to top, ${backgroundColor} 50%, transparent)`,
        WebkitBackdropFilter: `blur(${blurAmount})`,
        backdropFilter: `blur(${blurAmount})`,
        WebkitUserSelect: "none",
        userSelect: "none",
      }}
    />
  );
}
