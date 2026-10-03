import PropTypes from "prop-types";

export default function LicensesPage({ onNavigate }) {
  const openSourceLibs = [
    { name: "React & React-DOM", license: "MIT License", copyright: "Meta Platforms, Inc." },
    { name: "Vite", license: "MIT License", copyright: "Evan You & Vite Contributors" },
    { name: "Three.js & @react-three/drei", license: "MIT License", copyright: "Ricardo Cabello (mrdoob) & Contributors" },
    { name: "Marked", license: "MIT License", copyright: "Christopher Jeffrey & Contributors" },
    { name: "DOMPurify", license: "Apache 2.0 / MPL 2.0", copyright: "Cure53" },
    { name: "FastAPI", license: "MIT License", copyright: "Sebastián Ramírez" },
    { name: "Pydantic", license: "MIT License", copyright: "Samuel Colvin & Pydantic Contributors" },
    { name: "SQLAlchemy", license: "MIT License", copyright: "Michael Bayer & SQLAlchemy Authors" },
    { name: "OpenCV Python", license: "Apache 2.0 License", copyright: "OpenCV Foundation" },
    { name: "PyTorch", license: "Modified BSD License", copyright: "Meta Platforms, Inc. & PyTorch Contributors" },
    { name: "ByteTrack / BoT-SORT", license: "MIT License", copyright: "Yifu Zhang, Nir Aharon & Contributors" },
    { name: "RF-DETR", license: "Apache 2.0 License", copyright: "Roboflow & DETR Contributors" },
  ];

  return (
    <div className="licenses-page-wrapper" style={{ maxWidth: "780px", margin: "0 auto", paddingBottom: "80px" }}>
      {/* Header */}
      <div style={{ marginBottom: "40px" }}>
        <span className="section-label">ATTRIBUTION LOGICIELLE & LICENCES</span>
        <h1 className="page-title">Licences logicielles & attributions</h1>
        <p className="page-subtitle">
          Reconnaissance des technologies open-source, des dépendances logicielles et des jeux de données de recherche intégrés à VISION-BALLING.
        </p>
      </div>

      <div className="licenses-content-blocks" style={{ display: "flex", flexDirection: "column", gap: "32px", lineHeight: "1.65" }}>
        {/* Proprietary note */}
        <section className="licenses-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            01. Propriété intellectuelle de VISION-BALLING
          </h2>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "18px", fontSize: "13px" }}>
            <p style={{ marginBottom: "6px" }}>
              Le nom commercial, le logo VISION-BALLING, le symbole de l&apos;œil, les chartes graphiques, ainsi que les méthodes et modèles d&apos;inférence tactique (protocoles EXP-01 à EXP-26) sont la propriété exclusive de leurs auteurs.
            </p>
            <p className="mono" style={{ fontSize: "12px", color: "var(--muted)" }}>
              Copyright © 2026 VISION-BALLING · Tous droits réservés.
            </p>
          </div>
        </section>

        {/* Datasets */}
        <section className="licenses-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            02. Données scientifiques de démonstration
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "8px" }}>
            <p>
              Les séquences vidéo de démonstration accessibles sur la plateforme (SNMOT-060, SNMOT-068, SNMOT-069) sont issues du benchmark scientifique <strong>SoccerNet</strong>.
            </p>
            <p style={{ fontSize: "13px", color: "var(--muted)" }}>
              Ces séquences sont intégrées conformément aux stipulations de la licence académique SoccerNet (utilisations à des fins de recherche, d&apos;évaluation et d&apos;illustration scientifique non commerciale).
            </p>
          </div>
        </section>

        {/* Libraries */}
        <section className="licenses-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            03. Bibliothèques logicielles open-source tierces
          </h2>
          <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden", background: "var(--surface)" }}>
            <div style={{ padding: "12px 16px", background: "var(--surface-soft)", fontWeight: "600", fontSize: "12px", display: "grid", gridTemplateColumns: "1fr 160px 180px", color: "var(--text)" }}>
              <span>COMPOSANT / BIBLIOTHÈQUE</span>
              <span>LICENCE</span>
              <span>AYANT DROIT</span>
            </div>
            {openSourceLibs.map((lib, idx) => (
              <div
                key={lib.name}
                style={{
                  padding: "12px 16px",
                  fontSize: "12.5px",
                  display: "grid",
                  gridTemplateColumns: "1fr 160px 180px",
                  borderTop: "1px solid var(--border-light)",
                  backgroundColor: idx % 2 === 0 ? "transparent" : "var(--bg-subtle)",
                }}
              >
                <span style={{ fontWeight: "500", color: "var(--text)" }}>{lib.name}</span>
                <span className="mono" style={{ color: "var(--muted)", fontSize: "11px" }}>{lib.license}</span>
                <span style={{ color: "var(--muted)", fontSize: "12px" }}>{lib.copyright}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div style={{ marginTop: "48px", paddingTop: "24px", borderTop: "1px solid var(--border-light)", display: "flex", gap: "16px" }}>
        <button
          type="button"
          className="beta-cta-button"
          onClick={() => onNavigate("/legal")}
        >
          MENTIONS LÉGALES
        </button>
        <button
          type="button"
          className="beta-secondary-button"
          onClick={() => onNavigate("/")}
        >
          ACCUEIL
        </button>
      </div>
    </div>
  );
}

LicensesPage.propTypes = {
  onNavigate: PropTypes.func.isRequired,
};
