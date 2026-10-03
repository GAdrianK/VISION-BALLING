import PropTypes from "prop-types";

export default function PrivacyPage({ onNavigate }) {
  return (
    <div className="privacy-page-wrapper" style={{ maxWidth: "780px", margin: "0 auto", paddingBottom: "80px" }}>
      {/* Header */}
      <div style={{ marginBottom: "40px" }}>
        <span className="section-label">PROTECTION DES DONNÉES PERSONNELLES & RGPD</span>
        <h1 className="page-title">Politique de confidentialité</h1>
        <p className="page-subtitle">
          Règles relatives à la collecte, au traitement et à la conservation des données dans le cadre de l&apos;application publique et du programme pilote VISION-BALLING (Règlement Général sur la Protection des Données - RGPD n° 2016/679 et Loi Informatique et Libertés).
        </p>
      </div>

      <div className="privacy-content-blocks" style={{ display: "flex", flexDirection: "column", gap: "32px", lineHeight: "1.65" }}>
        {/* 1. Responsable du traitement */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            01. Responsable du traitement
          </h2>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "18px", fontSize: "13px" }}>
            <p style={{ marginBottom: "6px" }}>
              Le responsable du traitement des données à caractère personnel collectées sur ce site est :
            </p>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "4px" }}>
              <li><strong>Entité / Nom :</strong> [LEGAL_NAME]</li>
              <li><strong>Adresse professionnelle :</strong> [PROFESSIONAL_ADDRESS]</li>
              <li><strong>Courriel de contact DPO / Protection des données :</strong> [EMAIL]</li>
            </ul>
          </div>
        </section>

        {/* 2. Données collectées */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            02. Données collectées
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "8px" }}>
            <p>
              Dans le cadre de l&apos;utilisation du site et du formulaire de candidature BETA, nous collectons les catégories de données suivantes :
            </p>
            <ul style={{ paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "4px", fontSize: "13px" }}>
              <li><strong>Données d&apos;identification :</strong> nom, prénom, club ou structure représentée, fonction occupée au sein du staff.</li>
              <li><strong>Données de contact :</strong> adresse électronique professionnelle, numéro de téléphone (optionnel).</li>
              <li><strong>Données relatives au match :</strong> catégorie d&apos;équipe, niveau de compétition, adversaire (optionnel), objectifs tactiques recherchés, message d&apos;accompagnement.</li>
              <li><strong>Données techniques de captation :</strong> lien privé vers la vidéo de match (Google Drive, Dropbox, SwissTransfer, WeTransfer, etc.).</li>
              <li><strong>Données techniques de connexion :</strong> adresse IP du demandeur (utilisée exclusivement pour la limitation de débit anti-abus), horodatage de soumission, jeton technique de session locale (sessionStorage).</li>
            </ul>
          </div>
        </section>

        {/* 3. Finalités du traitement */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            03. Finalités du traitement
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "8px" }}>
            <p>Les données collectées répondent aux finalités explicites suivantes :</p>
            <ol style={{ paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "4px", fontSize: "13px" }}>
              <li>Enregistrement et instruction des candidatures au programme pilote BETA VISION-BALLING.</li>
              <li>Téléchargement temporaire et analyse tactique des séquences de match par les algorithmes de vision par ordinateur.</li>
              <li>Contrôle qualité humain des métriques tactiques et livraison des rapports aux staffs demandeurs.</li>
              <li>Communication et recueil des retours d&apos;expérience des utilisateurs pilotes.</li>
              <li>Sécurité du système, prévention des attaques par déni de service et protection contre les soumissions automatisées par robots (honeypot, limitation de débit).</li>
            </ol>
          </div>
        </section>

        {/* 4. Bases légales */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            04. Bases légales du traitement
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "8px" }}>
            <ul style={{ paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "6px", fontSize: "13px" }}>
              <li><strong>Exécution de mesures précontractuelles et contractuelles (Art. 6-1-b du RGPD) :</strong> le traitement des coordonnées et des informations de match est nécessaire à l&apos;exécution du service d&apos;analyse pilote demandé.</li>
              <li><strong>Consentement exprès (Art. 6-1-a du RGPD) :</strong> la transmission de la vidéo et la conservation temporaire sont subordonnées à la validation active des cases à cocher obligatoires du formulaire.</li>
              <li><strong>Intérêt légitime (Art. 6-1-f du RGPD) :</strong> la journalisation technique et le filtrage anti-abus (IP, limitation de débit) répondent à notre intérêt légitime d&apos;assurer l&apos;intégrité et la disponibilité du service.</li>
            </ul>
          </div>
        </section>

        {/* 5. Données obligatoires vs facultatives */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            05. Données obligatoires et facultatives
          </h2>
          <p style={{ fontSize: "13.5px", color: "var(--text)" }}>
            Les champs assortis d&apos;un astérisque rouge (<span style={{ color: "var(--beta-red)" }}>*</span>) dans le formulaire sont strictement obligatoires pour permettre l&apos;instruction technique de votre demande. À défaut de renseignement, l&apos;analyse ne pourra être planifiée ni exécutée. Les autres champs (téléphone, adversaire, message complémentaire) sont purement facultatifs.
          </p>
        </section>

        {/* 6. Destinataires des données */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            06. Destinataires des données
          </h2>
          <p style={{ fontSize: "13.5px", color: "var(--text)" }}>
            Les données sont destinées exclusivement aux membres habilités de l&apos;équipe technique et scientifique de VISION-BALLING. Vos données ne font l&apos;objet d&apos;aucune cession, vente, échange ou location à des tiers à des fins commerciales ou publicitaires.
          </p>
        </section>

        {/* 7. Hébergement et sous-traitants */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            07. Hébergement & distinction des infrastructures
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "10px" }}>
            <p>
              Pour une transparence rigoureuse, nous distinguons clairement deux environnements d&apos;infrastructure :
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "16px" }}>
                <strong style={{ display: "block", fontSize: "13px", marginBottom: "6px" }}>Infrastructure Web & API</strong>
                <p style={{ fontSize: "12.5px", color: "var(--muted)" }}>
                  Le site web, le formulaire et l&apos;API de réception des candidatures sont hébergés sur les serveurs de [HOST_NAME] situés au sein de l&apos;Union Européenne.
                </p>
              </div>
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "16px" }}>
                <strong style={{ display: "block", fontSize: "13px", marginBottom: "6px" }}>Inférence GPU & Traitement Vidéo</strong>
                <p style={{ fontSize: "12.5px", color: "var(--muted)" }}>
                  L&apos;exécution des modèles de vision par ordinateur (tracking, détection, calibration) s&apos;effectue sur station de calcul locale sécurisée sous contrôle direct de l&apos;opérateur. Les vidéos ne sont jamais transmises à des tiers d&apos;inférence en cloud public.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* 8. Transferts hors Union Européenne */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            08. Transferts hors Union Européenne
          </h2>
          <p style={{ fontSize: "13.5px", color: "var(--text)" }}>
            Aucun transfert de données à caractère personnel vers un pays situé hors de l&apos;Espace Économique Européen (EEE) n&apos;est réalisé de notre initiative. Lorsque vous choisissez de partager une vidéo via un service tiers situé hors EEE (ex. Google Drive, Dropbox), ce transfert est régi par les conditions d&apos;utilisation et les clauses contractuelles types dudit prestataire.
          </p>
        </section>

        {/* 9. Durées de conservation */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            09. Durées de conservation
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "8px" }}>
            <p>Conformément au principe de minimisation, les données sont conservées selon des durées définies et vérifiables :</p>
            <ul style={{ paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "6px", fontSize: "13px" }}>
              <li><strong>Dossier de candidature BETA :</strong> conservé pendant la durée du programme pilote, puis purgé au maximum 180 jours après clôture de l&apos;évaluation.</li>
              <li><strong>Fichiers vidéo bruts de match :</strong> conservés uniquement le temps nécessaire au traitement et au contrôle qualité (durée configurable jusqu&apos;à 14 jours maximum après livraison du rapport), puis définitivement supprimés de l&apos;espace de calcul actif.</li>
              <li><strong>Rapports et métriques agrégées anonymisées :</strong> conservés pendant 30 jours pour consultation par le staff demandeur, avant archivage ou suppression selon accord.</li>
              <li><strong>Journaux de sécurité (logs de connexion) :</strong> conservés pour une durée maximale de 12 mois conformément aux obligations légales de l&apos;article L34-1 du CPCE.</li>
            </ul>
          </div>
        </section>

        {/* 10. Traitement vidéo & engagements de non-réutilisation */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            10. Traitement vidéo & engagement formel de non-réutilisation
          </h2>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "18px", fontSize: "13px" }}>
            <p style={{ fontWeight: "600", marginBottom: "8px", color: "var(--text)" }}>
              Engagements stricts relatifs aux vidéos fournies par les clubs et analystes :
            </p>
            <ul style={{ paddingLeft: "18px", display: "flex", flexDirection: "column", gap: "6px", color: "var(--text)" }}>
              <li><strong>Aucune publication publique :</strong> vos matchs et extraits ne sont jamais mis en ligne, diffusés publiquement ou exposés à d&apos;autres utilisateurs.</li>
              <li><strong>Aucune intégration de démonstration :</strong> aucune séquence issue de vos fichiers ne sert de démonstration publique sans votre accord exprès écrit.</li>
              <li><strong>Aucun entraînement de modèle non consenti :</strong> vos captations ne sont pas intégrées à nos jeux de données d&apos;entraînement de détection sans convention spécifique.</li>
              <li><strong>Aucun usage marketing :</strong> les données vidéo ne font l&apos;objet d&apos;aucune exploitation promotionnelle.</li>
            </ul>
          </div>
        </section>

        {/* 11. Droits des personnes & exercice */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            11. Vos droits et modalités d&apos;exercice
          </h2>
          <div style={{ fontSize: "13.5px", color: "var(--text)", display: "flex", flexDirection: "column", gap: "10px" }}>
            <p>
              Conformément à la réglementation RGPD, vous disposez des droits suivants sur vos données :
            </p>
            <ul style={{ paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "4px", fontSize: "13px" }}>
              <li><strong>Droit d&apos;accès :</strong> obtenir confirmation du traitement de vos données et en recevoir une copie.</li>
              <li><strong>Droit de rectification :</strong> corriger vos coordonnées inexactes ou incomplètes.</li>
              <li><strong>Droit à l&apos;effacement (&ldquo;droit à l&apos;oubli&rdquo;) :</strong> exiger la suppression immédiate de vos données de contact et des fichiers associés.</li>
              <li><strong>Droit à la limitation du traitement :</strong> restreindre le traitement dans les conditions prévues par l&apos;article 18 du RGPD.</li>
              <li><strong>Droit à la portabilité :</strong> recevoir les données fournies dans un format structuré et lisible par machine.</li>
              <li><strong>Droit d&apos;opposition :</strong> vous opposer à tout moment au traitement pour des motifs légitimes.</li>
            </ul>
            <p style={{ marginTop: "6px" }}>
              Pour exercer l&apos;un de ces droits, adressez simplement votre demande par courriel à :{" "}
              <a href="mailto:[EMAIL]" style={{ textDecoration: "underline", fontWeight: "600" }}>
                [EMAIL]
              </a>. Nous vous répondrons dans un délai maximal de 30 jours.
            </p>
          </div>
        </section>

        {/* 12. Réclamation auprès de la CNIL */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            12. Réclamation auprès de l&apos;autorité de contrôle (CNIL)
          </h2>
          <p style={{ fontSize: "13.5px", color: "var(--text)" }}>
            Si vous estimez, après nous avoir contactés, que vos droits Informatique et Libertés ne sont pas respectés, vous avez la possibilité d&apos;introduire une réclamation auprès de la <strong>Commission Nationale de l&apos;Informatique et des Libertés (CNIL)</strong> : en ligne sur le site <a href="https://www.cnil.fr" target="_blank" rel="noreferrer" style={{ textDecoration: "underline" }}>cnil.fr</a> ou par voie postale (3 Place de Fontenoy - TSA 80715 - 75334 Paris Cedex 07).
          </p>
        </section>

        {/* 13. Sécurité */}
        <section className="privacy-section">
          <h2 style={{ fontSize: "15px", fontWeight: "600", marginBottom: "12px", color: "var(--text)" }}>
            13. Sécurité technique et organisationnelle
          </h2>
          <p style={{ fontSize: "13.5px", color: "var(--text)" }}>
            VISION-BALLING applique des mesures de sécurité strictes fondées sur le principe de moindre privilège et de fermeture par défaut (*fail-closed*) : chiffrement des flux de transmission en HTTPS (TLS 1.3), masquage automatique des paramètres de jeton d&apos;accès dans les journaux d&apos;audit, protection anti-rejeu et filtrage anti-bruteforce, stockage persistant sécurisé des candidatures et séparation étanche entre services d&apos;ingestion web et calcul GPU.
          </p>
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

PrivacyPage.propTypes = {
  onNavigate: PropTypes.func.isRequired,
};
