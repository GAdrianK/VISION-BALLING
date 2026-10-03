import PropTypes from "prop-types";

export default function CookiesPage({ onNavigate }) {
  return (
    <div className="cookies-page-wrapper" style={{ maxWidth: "780px", margin: "0 auto", paddingBottom: "80px" }}>
      {/* Header */}
      <div style={{ marginBottom: "40px" }}>
        <span className="section-label">TRANSPARENCE & TRACEURS</span>
        <h1 className="page-title">Gestion des traceurs et cookies</h1>
        <p className="page-subtitle">
          Politique relative aux cookies, au stockage local et au respect de la vie privée des utilisateurs sur VISION-BALLING (délibération CNIL n° 2020-091 et article 82 de la loi Informatique et Libertés).
        </p>
      </div>

      <div className="cookies-content-blocks" style={{ display: "flex", flexDirection: "column", gap: "32px", lineHeight: "1.65" }}>
        {/* Résumé de l'audit */}
        <section className="cookies-section">
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "20px" }}>
            <span className="section-label" style={{ color: "var(--text)" }}>AUDIT TECHNIQUE DU SITE</span>
            <h2 style={{ fontSize: "16px", fontWeight: "600", marginTop: "4px", marginBottom: "8px", color: "var(--text)" }}>
              Zéro cookie publicitaire · Zéro outil d&apos;analyse tiers
            </h2>
            <p style={{ fontSize: "13.5px", color: "var(--text)", lineHeight: "1.6" }}>
              Le site <strong>VISION-BALLING n&apos;utilise aucun cookie publicitaire, aucun traceur de reciblage, aucun pixel marketing (Facebook, Google Ads, TikTok, etc.) et aucun service de mesure d&apos;audience tiers</strong> (type Google Analytics).
            </p>
          </div>
        </section>

        {/* Mécanismes de stockage utilisés */}
        <section className="cookies-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            01. Mécanismes de stockage strictement nécessaires
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "10px" }}>
            <p>
              Pour assurer le fonctionnement technique rigoureux et la sécurité des accès, le site recourt exclusivement au mécanisme technique suivant :
            </p>
            <div style={{ border: "1px solid var(--border-light)", borderRadius: "var(--radius)", overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", background: "var(--surface-soft)", fontWeight: "600", fontSize: "13px", display: "grid", gridTemplateColumns: "140px 140px 1fr" }}>
                <span>NOM</span>
                <span>TYPE & DURÉE</span>
                <span>FINALITÉ STRICTEMENT FONCTIONNELLE</span>
              </div>
              <div style={{ padding: "14px 16px", background: "var(--surface)", fontSize: "12.5px", display: "grid", gridTemplateColumns: "140px 140px 1fr", borderTop: "1px solid var(--border-light)" }}>
                <span className="mono">vb_analysis_tokens</span>
                <span>sessionStorage (fermeture de l&apos;onglet)</span>
                <span>
                  Conservation temporaire du jeton d&apos;autorisation de session utilisateur pour l&apos;accès sécurisé aux artefacts vidéo de son analyse active (modèle de sécurité par capacité). Ne transite par aucun serveur tiers.
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Absence de bandeau de consentement */}
        <section className="cookies-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            02. Pourquoi aucun bandeau intrusif n&apos;est affiché ?
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "8px" }}>
            <p>
              Conformément aux recommandations officielles de la CNIL et à la directive européenne ePrivacy :
            </p>
            <blockquote style={{ borderLeft: "2px solid var(--text)", paddingLeft: "14px", margin: "8px 0", color: "var(--muted)", fontStyle: "italic" }}>
              Les traceurs strictement nécessaires à la fourniture d&apos;un service de communication en ligne expressément demandé par l&apos;utilisateur ou ayant pour finalité exclusive de permettre ou faciliter une communication par voie électronique sont exemptés de l&apos;obligation de recueil préalable du consentement.
            </blockquote>
            <p>
              En l&apos;absence totale de traceurs optionnels ou publicitaires sur VISION-BALLING, afficher un bandeau de cookies constituerait une fausse conformité et une gêne inutile pour l&apos;utilisateur.
            </p>
          </div>
        </section>

        {/* Ressources externes */}
        <section className="cookies-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            03. Polices typographiques et ressources statiques
          </h2>
          <p style={{ fontSize: "13.5px", color: "var(--text)" }}>
            Les typographies du site (Inter et Geist Mono) sont chargées via des feuilles de style optimisées. Aucune donnée d&apos;identification personnelle n&apos;est transmise ni croisée avec des profils publicitaires lors du chargement de ces polices.
          </p>
        </section>
      </div>

      <div style={{ marginTop: "48px", paddingTop: "24px", borderTop: "1px solid var(--border-light)", display: "flex", gap: "16px" }}>
        <button
          type="button"
          className="beta-cta-button"
          onClick={() => onNavigate("/privacy")}
        >
          POLITIQUE DE CONFIDENTIALITÉ
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

CookiesPage.propTypes = {
  onNavigate: PropTypes.func.isRequired,
};
