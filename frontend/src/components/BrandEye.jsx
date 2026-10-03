export default function BrandEye({ size = 30, className = "", onClick = null }) {
  return (
    <a
      href="/"
      className={`brand-eye-link ${className}`}
      onClick={(e) => {
        if (onClick) {
          e.preventDefault();
          onClick();
        }
      }}
      aria-label="VISION-BALLING Accueil"
    >
      <img
        src="/brand/vision-balling-eye.png"
        alt="Symbole VISION-BALLING"
        className="brand-eye-img"
        style={{ width: `${size}px`, height: "auto" }}
        width="483"
        height="309"
        loading="eager"
      />
    </a>
  );
}
