import PropTypes from "prop-types";

export default function PrivacyPage({ onNavigate }) {
  return (
    <div className="privacy-page-wrapper" style={{ maxWidth: "740px", margin: "0 auto", paddingBottom: "64px" }}>
      {/* Header */}
      <div style={{ marginBottom: "40px" }}>
        <span className="section-label">CONFIDENTIALITÉ & DONNÉES</span>
        <h1 className="page-title">Politique de confidentialité · Programme Pilote BETA</h1>
        <p className="page-subtitle">
          Engagements de sécurité, de traitement et de conservation des vidéos d&apos;équipes et des métriques tactiques.
        </p>
      </div>

      <div className="privacy-content-blocks" style={{ display: "flex", flexDirection: "column", gap: "28px", lineHeight: "1.65" }}>
        <div className="privacy-block">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "8px", color: "var(--text)" }}>
            01. Propriété et stricte confidentialité des vidéos
          </h2>
          <p style={{ color: "var(--text)", fontSize: "13.5px" }}>
            Les vidéos transmises via lien privé (Google Drive, Dropbox, SwissTransfer, WeTransfer ou équivalent) demeurent la propriété exclusive de votre club, staff ou structure. VISION-BALLING ne revendique aucun droit d&apos;exploitation sur vos captations. Vos vidéos ne sont jamais rendues publiques, partagées avec d&apos;autres clubs ou utilisées à des fins de communication externe sans accord exprès écrit.
          </p>
        </div>

        <div className="privacy-block">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "8px", color: "var(--text)" }}>
            02. Traitement local & souverain sur GPU
          </h2>
          <p style={{ color: "var(--text)", fontSize: "13.5px" }}>
            L&apos;inférence des modèles de détection (RF-DETR), de suivi (ByteTrack / BoT-SORT) et d&apos;extraction métrique (homographie et géométrie de terrain) s&apos;exécute en local sur nos stations de calcul sécurisées. Les flux et artefacts intermédiaires ne transitent pas par des services tiers d&apos;inférence mutualisés.
          </p>
        </div>

        <div className="privacy-block">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "8px", color: "var(--text)" }}>
            03. Conservation temporaire et purge
          </h2>
          <p style={{ color: "var(--text)", fontSize: "13.5px" }}>
            Les vidéos brutes téléchargées pour l&apos;analyse sont conservées uniquement pendant la durée nécessaire à l&apos;exécution du pipeline et au contrôle qualité des résultats par l&apos;équipe technique. Une fois les livrables transmis au demandeur, les fichiers vidéo volumineux sont supprimés de l&apos;espace de travail actif.
          </p>
        </div>

        <div className="privacy-block">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "8px", color: "var(--text)" }}>
            04. Données de contact & absence de démarchage
          </h2>
          <p style={{ color: "var(--text)", fontSize: "13.5px" }}>
            Les coordonnées fournies dans le formulaire (nom, club, fonction, courriel, téléphone) servent exclusivement à vous contacter au sujet de votre analyse, vous transmettre le rapport tactique et recueillir votre retour d&apos;expérience sur l&apos;instrument. Aucun démarchage commercial non sollicité n&apos;est effectué et vos informations ne sont jamais cédées à des tiers.
          </p>
        </div>

        <div className="privacy-block">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "8px", color: "var(--text)" }}>
            05. Exercice de vos droits
          </h2>
          <p style={{ color: "var(--text)", fontSize: "13.5px" }}>
            Vous pouvez à tout moment demander l&apos;effacement immédiat de vos données et des rapports associés en contactant l&apos;équipe à l&apos;adresse suivante :{" "}
            <a href="mailto:contact@vision-balling.ai" style={{ textDecoration: "underline", fontWeight: "500" }}>
              contact@vision-balling.ai
            </a>.
          </p>
        </div>
      </div>

      <div style={{ marginTop: "48px", paddingTop: "24px", borderTop: "1px solid var(--border-light)", display: "flex", gap: "16px" }}>
        <button
          type="button"
          className="beta-cta-button"
          onClick={() => onNavigate("/beta")}
        >
          ← RETOUR À LA CANDIDATURE BETA
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

PrivacyPage.propTypes = {
  onNavigate: PropTypes.func.isRequired,
};
