import PropTypes from "prop-types";

export default function BetaTermsPage({ onNavigate }) {
  return (
    <div className="terms-page-wrapper" style={{ maxWidth: "780px", margin: "0 auto", paddingBottom: "80px" }}>
      {/* Header */}
      <div style={{ marginBottom: "40px" }}>
        <span className="section-label">CONDITIONS DU PROGRAMME PILOTE</span>
        <h1 className="page-title">Conditions Générales d&apos;Utilisation · Programme BETA</h1>
        <p className="page-subtitle">
          Cadre d&apos;accès expérimental et engagements réciproques pour les clubs, entraîneurs et analystes participant au programme pilote VISION-BALLING.
        </p>
      </div>

      <div className="terms-content-blocks" style={{ display: "flex", flexDirection: "column", gap: "32px", lineHeight: "1.65" }}>
        {/* 1. Statut expérimental et gratuité */}
        <section className="terms-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            01. Statut expérimental & gratuité du programme pilote
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "8px" }}>
            <p>
              Le programme pilote VISION-BALLING constitue une phase d&apos;expérimentation technique et de recherche appliquée ouverte à titre <strong>gratuit</strong> aux staffs techniques, analystes vidéo et clubs de football.
            </p>
            <p>
              Ce programme n&apos;a pas valeur de contrat de service commercial définitif (SaaS) ni de prestation tarifée. Il vise à évaluer la robustesse des modèles de vision par ordinateur sur des séquences réelles de match et à recueillir les retours d&apos;expérience des utilisateurs.
            </p>
          </div>
        </section>

        {/* 2. Traitement humain et délais indicatifs */}
        <section className="terms-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            02. Traitement assisté & absence de garantie de délai
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "8px" }}>
            <p>
              L&apos;analyse des vidéos dans le cadre de la BETA n&apos;est pas un traitement automatisé instantané. Chaque séquence est téléchargée, prétraitée, exécutée sur nos stations de calcul GPU locales et auditée par nos ingénieurs avant transmission des livrables.
            </p>
            <p>
              En conséquence, aucun délai fixe de restitution n&apos;est garanti. Le temps de livraison dépend de la durée de la vidéo transmise, de la file d&apos;attente des calculs GPU et de la disponibilité des stations de recherche.
            </p>
          </div>
        </section>

        {/* 3. Dépendance à la qualité optique et limites scientifiques */}
        <section className="terms-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            03. Qualité optique & limites scientifiques documentées
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "8px" }}>
            <p>
              L&apos;exactitude des métriques produites (trajectoires des joueurs, vitesse de fermeture, compacité de bloc, indice de pressing, transitions) est directement tributaire des conditions de tournage de la vidéo :
            </p>
            <ul style={{ paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "4px", fontSize: "13px" }}>
              <li>Une élévation suffisante de la caméra par rapport au terrain est indispensable à une calibration homographique précise.</li>
              <li>Les séquences en caméra basse (niveau main courante) ou présentant de fortes occultations entraînent des incertitudes géométriques documentées.</li>
              <li>Les indicateurs tactiques synthétisés demeurent des outils d&apos;aide à la décision et ne sauraient se substituer au jugement critique du staff technique.</li>
            </ul>
          </div>
        </section>

        {/* 4. Responsabilité de l'utilisateur sur les droits vidéo */}
        <section className="terms-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            04. Responsabilité de l&apos;utilisateur & droits sur la vidéo
          </h2>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "18px", fontSize: "13px" }}>
            <p style={{ fontWeight: "600", marginBottom: "8px", color: "var(--text)" }}>
              Déclaration et garantie de l&apos;utilisateur :
            </p>
            <p style={{ marginBottom: "8px", lineHeight: "1.55" }}>
              En soumettant une vidéo via le formulaire de candidature BETA, vous déclarez et garantissez disposer de l&apos;ensemble des droits, habilitations et autorisations nécessaires pour transmettre la vidéo à VISION-BALLING et en solliciter l&apos;analyse tactique.
            </p>
            <p style={{ lineHeight: "1.55" }}>
              Cette garantie s&apos;applique tout particulièrement au droit à l&apos;image des sportifs identifiables, des membres du staff et des personnes mineures apparaissant sur les enregistrements.
            </p>
          </div>
        </section>

        {/* 5. Confidentialité et non-réutilisation */}
        <section className="terms-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            05. Traitement confidentiel & absence de réutilisation publique
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "8px" }}>
            <p>
              VISION-BALLING s&apos;engage à traiter l&apos;ensemble des vidéos et données transmises dans la plus stricte confidentialité :
            </p>
            <ul style={{ paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "4px", fontSize: "13px" }}>
              <li>Les vidéos reçues ne sont jamais diffusées publiquement ni accessibles à d&apos;autres utilisateurs.</li>
              <li>Aucune séquence n&apos;est intégrée dans les démonstrations publiques de l&apos;instrument sans votre autorisation écrite explicite.</li>
              <li>Aucune séquence n&apos;est utilisée pour l&apos;entraînement de modèles ou le marketing sans accord préalable convenu.</li>
            </ul>
          </div>
        </section>

        {/* 6. Droit de refus et résiliation */}
        <section className="terms-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            06. Sélection des dossiers, refus et clôture
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "8px" }}>
            <p>
              En raison de la capacité matérielle limitée des stations de calcul et de la nature humaine du contrôle qualité, l&apos;accès au programme pilote n&apos;est pas garanti. VISION-BALLING se réserve le droit de différer ou de refuser toute demande d&apos;analyse :
            </p>
            <ul style={{ paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "4px", fontSize: "13px" }}>
              <li>Si la qualité optique ou la hauteur de captation rend l&apos;analyse biométrique/tactique impossible.</li>
              <li>Si les quotas de calcul disponibles pour la période sont saturés.</li>
              <li>Si les vérifications de légitimité de la demande ou de sécurité des liens échouent.</li>
            </ul>
            <p style={{ marginTop: "6px" }}>
              L&apos;utilisateur ou VISION-BALLING peut mettre fin à sa participation au programme pilote à tout moment, sur simple notification par courriel.
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
          SOUMETTRE UN MATCH EN BETA
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

BetaTermsPage.propTypes = {
  onNavigate: PropTypes.func.isRequired,
};
