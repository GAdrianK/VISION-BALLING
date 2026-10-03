import PropTypes from "prop-types";

export default function LegalPage({ onNavigate }) {
  return (
    <div className="legal-page-wrapper" style={{ maxWidth: "780px", margin: "0 auto", paddingBottom: "80px" }}>
      {/* Header */}
      <div style={{ marginBottom: "40px" }}>
        <span className="section-label">CADRE JURIDIQUE & INFORMATIONS ÉDITORIALES</span>
        <h1 className="page-title">Mentions légales</h1>
        <p className="page-subtitle">
          Informations réglementaires relatives à l&apos;éditeur et à l&apos;hébergement du site VISION-BALLING (loi n° 2004-575 du 21 juin 2004 pour la confiance dans l&apos;économie numérique - LCEN).
        </p>
      </div>

      <div className="legal-content-blocks" style={{ display: "flex", flexDirection: "column", gap: "32px", lineHeight: "1.65" }}>
        {/* Éditeur du site */}
        <section className="legal-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            01. Éditeur du site
          </h2>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "20px" }}>
            <p style={{ marginBottom: "8px", fontSize: "13.5px" }}>
              Le site <strong>VISION-BALLING</strong> est édité par :
            </p>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "6px", fontSize: "13px", color: "var(--text)" }}>
              <li><strong>Nom légal / Raison sociale :</strong> [LEGAL_NAME]</li>
              <li><strong>Nom commercial :</strong> [BUSINESS_NAME]</li>
              <li><strong>Forme juridique :</strong> [LEGAL_STATUS]</li>
              <li><strong>Adresse professionnelle :</strong> [PROFESSIONAL_ADDRESS]</li>
              <li><strong>Courriel :</strong> [EMAIL]</li>
              <li><strong>Téléphone :</strong> [PHONE]</li>
              <li><strong>Numéro SIREN :</strong> [SIREN]</li>
              <li><strong>Numéro SIRET :</strong> [SIRET]</li>
              <li><strong>Immatriculation RNE :</strong> [RNE]</li>
              <li><strong>Registre du Commerce et des Sociétés :</strong> [RCS_IF_APPLICABLE]</li>
              <li><strong>Numéro de TVA intracommunautaire :</strong> [VAT_NUMBER_IF_APPLICABLE]</li>
            </ul>
          </div>
        </section>

        {/* Directeur de la publication */}
        <section className="legal-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            02. Directeur de la publication
          </h2>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "20px" }}>
            <p style={{ fontSize: "13.5px", color: "var(--text)" }}>
              <strong>Directeur de la publication :</strong> [NAME]
            </p>
          </div>
        </section>

        {/* Hébergeur */}
        <section className="legal-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            03. Hébergement du site
          </h2>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "20px" }}>
            <p style={{ marginBottom: "8px", fontSize: "13.5px" }}>
              Le site et ses API d&apos;ingestion publique sont hébergés par :
            </p>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "6px", fontSize: "13px", color: "var(--text)" }}>
              <li><strong>Hébergeur :</strong> [HOST_NAME]</li>
              <li><strong>Raison sociale :</strong> [HOST_LEGAL_ENTITY]</li>
              <li><strong>Adresse de l&apos;hébergeur :</strong> [HOST_ADDRESS]</li>
              <li><strong>Téléphone de l&apos;hébergeur :</strong> [HOST_PHONE]</li>
              <li><strong>Site web :</strong> [HOST_URL]</li>
            </ul>
            <p style={{ marginTop: "12px", fontSize: "12px", color: "var(--muted)" }}>
              Note d&apos;infrastructure : L&apos;exécution des modèles de vision par ordinateur sur les séquences vidéo de match (inférence GPU) est réalisée sur station de calcul locale et ne transite par aucun service d&apos;inférence mutualisé public.
            </p>
          </div>
        </section>

        {/* Propriété intellectuelle */}
        <section className="legal-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            04. Propriété intellectuelle
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "10px" }}>
            <p>
              L&apos;ensemble de l&apos;architecture logicielle, de l&apos;identité visuelle, des algorithmes d&apos;inférence tactique (protocoles EXP-01 à EXP-26), des graphismes, interfaces et marques VISION-BALLING sont protégés par le Code de la propriété intellectuelle et les traités internationaux applicables.
            </p>
            <p>
              Toute reproduction, représentation, modification, publication ou adaptation totale ou partielle de ces éléments, quel que soit le moyen ou le procédé utilisé, est formellement interdite sans l&apos;autorisation écrite préalable de l&apos;éditeur.
            </p>
          </div>
        </section>

        {/* Contenus tiers et attributions */}
        <section className="legal-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            05. Contenus tiers & attributions
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "10px" }}>
            <p>
              Les séquences de démonstration intégrées à l&apos;instrument proviennent du jeu de données scientifique ouvert <strong>SoccerNet</strong> (séquences de recherche académique SNMOT-060, SNMOT-068, SNMOT-069) et sont exploitées conformément aux termes de leurs licences de recherche respectives.
            </p>
            <p>
              Pour consulter la liste complète des bibliothèques logicielles open-source intégrées (React, Vite, Three.js, OpenCV, PyTorch, ByteTrack, BoT-SORT, RF-DETR), référez-vous à notre page dédiée aux{" "}
              <button
                type="button"
                className="beta-inline-link"
                onClick={() => onNavigate("/licenses")}
                style={{ fontWeight: "500" }}
              >
                Licences et Attributions
              </button>.
            </p>
          </div>
        </section>
      </div>

      <div style={{ marginTop: "48px", paddingTop: "24px", borderTop: "1px solid var(--border-light)", display: "flex", gap: "16px" }}>
        <button
          type="button"
          className="beta-cta-button"
          onClick={() => onNavigate("/beta")}
        >
          CANDIDATURE BETA
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

LegalPage.propTypes = {
  onNavigate: PropTypes.func.isRequired,
};
