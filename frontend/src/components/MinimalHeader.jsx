import BrandEye from "./BrandEye";

export default function MinimalHeader({ currentPath = "/analyse", onNavigate }) {
  const links = [
    { label: "ANALYSE", path: "/analyse" },
    { label: "DEMO", path: "/demo" },
    { label: "PROJET", path: "/project" },
    { label: "CONTACT", path: "/contact" },
  ];

  return (
    <header className="site-header" role="banner">
      <nav className="nav-links" aria-label="Navigation principale">
        {links.map((link) => {
          const isActive = currentPath === link.path;
          return (
            <a
              key={link.path}
              href={link.path}
              className={`nav-link ${isActive ? "active" : ""}`}
              aria-current={isActive ? "page" : undefined}
              onClick={(e) => {
                e.preventDefault();
                onNavigate(link.path);
              }}
            >
              {link.label}
            </a>
          );
        })}
      </nav>

      <div className="brand-slot">
        <BrandEye size={30} onClick={() => onNavigate("/")} />
      </div>
    </header>
  );
}
