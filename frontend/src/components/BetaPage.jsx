import { useState } from "react";
import PropTypes from "prop-types";
import BetaStamp from "./BetaStamp";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const ROLES = [
  "Entraîneur",
  "Analyste vidéo",
  "Analyste performance",
  "Staff",
  "Direction sportive",
  "Autre",
];

const VIDEO_TYPES = [
  "Match complet",
  "Première mi-temps",
  "Deuxième mi-temps",
  "Extrait",
  "Autre",
];

const OBJECTIVES = [
  "Analyse globale",
  "Organisation défensive",
  "Bloc / compacité",
  "Pressing",
  "Possession",
  "Transitions",
  "Séquences clés",
  "Autre",
];

export default function BetaPage({ onNavigate }) {
  const [formData, setFormData] = useState({
    name: "",
    club: "",
    role: "Entraîneur",
    email: "",
    phone: "",
    team_category: "",
    competition_level: "",
    opponent: "",
    video_type: "Match complet",
    video_url: "",
    analysis_objectives: ["Analyse globale"],
    message: "",
    video_authorization_confirmed: false,
    temporary_storage_consent: false,
    website: "", // Honeypot field
  });

  const [showDriveHelper, setShowDriveHelper] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [submissionSuccess, setSubmissionSuccess] = useState(null);

  const handleObjectiveToggle = (obj) => {
    setFormData((prev) => {
      const exists = prev.analysis_objectives.includes(obj);
      if (exists) {
        if (prev.analysis_objectives.length === 1) return prev; // Keep at least one
        return {
          ...prev,
          analysis_objectives: prev.analysis_objectives.filter((item) => item !== obj),
        };
      } else {
        return {
          ...prev,
          analysis_objectives: [...prev.analysis_objectives, obj],
        };
      }
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage("");

    // Basic frontend checks
    if (!formData.name.trim() || !formData.club.trim() || !formData.email.trim()) {
      setErrorMessage("Veuillez renseigner les champs obligatoires (nom, club, email).");
      return;
    }
    if (!formData.video_url.trim()) {
      setErrorMessage("Veuillez fournir le lien de partage vers votre vidéo.");
      return;
    }
    if (!formData.video_authorization_confirmed) {
      setErrorMessage("Vous devez confirmer être autorisé à transmettre cette vidéo.");
      return;
    }
    if (!formData.temporary_storage_consent) {
      setErrorMessage("Vous devez accepter la conservation temporaire pour analyse.");
      return;
    }

    setIsSubmitting(true);

    try {
      const payload = {
        name: formData.name.trim(),
        club: formData.club.trim(),
        role: formData.role,
        email: formData.email.trim(),
        phone: formData.phone.trim() || null,
        team_category: formData.team_category.trim(),
        competition_level: formData.competition_level.trim(),
        opponent: formData.opponent.trim() || null,
        video_type: formData.video_type,
        video_url: formData.video_url.trim(),
        analysis_objectives: formData.analysis_objectives,
        message: formData.message.trim() || null,
        video_authorization_confirmed: formData.video_authorization_confirmed,
        temporary_storage_consent: formData.temporary_storage_consent,
        honeypot: formData.website,
      };

      const res = await fetch(`${API_BASE}/api/beta-requests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(
          errorData.detail || "Impossible d'envoyer la demande pour le moment."
        );
      }

      const data = await res.json();
      setSubmissionSuccess(data);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setErrorMessage(err.message || "Impossible d'envoyer la demande pour le moment.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const scrollToForm = () => {
    const el = document.getElementById("beta-form");
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <div className="beta-page-container">
      {/* 1. HERO */}
      <section className="beta-hero" aria-labelledby="hero-title">
        <div className="beta-hero-inner">
          <div className="beta-hero-header">
            <span className="section-label">VISION-BALLING / BETA</span>
            <div className="beta-title-row">
              <h1 id="hero-title" className="beta-hero-title">
                FAITES ANALYSER VOTRE MATCH.
              </h1>
              <div className="beta-hero-stamp-slot">
                <BetaStamp size="small" />
              </div>
            </div>
            <p className="beta-hero-subtitle">
              Testez VISION-BALLING sur une vidéo réelle de votre équipe.
            </p>
          </div>

          <p className="beta-hero-body">
            La version BETA fonctionne actuellement sur invitation. Envoyez-nous un match
            ou une mi-temps : l&apos;analyse est réalisée par VISION-BALLING puis vérifiée
            avant de vous être transmise.
          </p>

          <div className="beta-hero-cta-slot">
            <button
              type="button"
              className="beta-cta-button"
              onClick={scrollToForm}
              aria-label="Accéder au formulaire de demande d'analyse BETA"
            >
              DEMANDER UNE ANALYSE ↓
            </button>
          </div>
        </div>
      </section>

      {/* 2. PROCESS (01 - 04) */}
      <section className="beta-process-section" aria-label="Processus d'analyse">
        <div className="beta-process-header">
          <span className="section-label">PROTOCOLE PILOTE</span>
          <h2 className="beta-section-title">Comment fonctionne la BETA</h2>
        </div>

        <div className="beta-process-grid">
          <div className="beta-step-item">
            <span className="beta-step-number">01</span>
            <h3 className="beta-step-title">ENVOYEZ VOTRE MATCH</h3>
            <p className="beta-step-text">
              Partagez un lien privé vers votre vidéo (Drive, Dropbox, WeTransfer).
            </p>
          </div>

          <div className="beta-step-item">
            <span className="beta-step-number">02</span>
            <h3 className="beta-step-title">VISION-BALLING L&apos;ANALYSE</h3>
            <p className="beta-step-text">
              Le pipeline analyse joueurs, ballon, structure collective et événements tactiques disponibles.
            </p>
          </div>

          <div className="beta-step-item">
            <span className="beta-step-number">03</span>
            <h3 className="beta-step-title">RECEVEZ LES RÉSULTATS</h3>
            <p className="beta-step-text">
              Vous recevez les résultats produits pour votre match (timeline, fiches d&apos;événements, rapport).
            </p>
          </div>

          <div className="beta-step-item">
            <span className="beta-step-number">04</span>
            <h3 className="beta-step-title">DONNEZ VOTRE RETOUR</h3>
            <p className="beta-step-text">
              Votre retour d&apos;analyste ou d&apos;entraîneur aide à construire la version finale destinée aux clubs.
            </p>
          </div>
        </div>
      </section>

      {/* 3. BETA EXPECTATION / HONESTY */}
      <section className="beta-honesty-section" aria-label="Cadre expérimental et engagements">
        <div className="beta-honesty-box">
          <div className="beta-honesty-meta">
            <span className="section-label" style={{ color: "var(--beta-red)" }}>
              VERSION BETA
            </span>
            <span className="beta-honesty-tag">PILOTE CONTRÔLÉ</span>
          </div>

          <p className="beta-honesty-lead">
            &ldquo;VISION-BALLING est actuellement en phase pilote. Chaque analyse est traitée individuellement et contrôlée avant livraison.&rdquo;
          </p>

          <ul className="beta-honesty-list">
            <li>
              <strong>Non-instantané :</strong> Les séquences sont traitées sur station de calcul dédiée avec vérification humaine de cohérence.
            </li>
            <li>
              <strong>Accès progressif :</strong> Les analyses sont attribuées par créneaux selon la capacité machine disponible.
            </li>
            <li>
              <strong>Qualité optique :</strong> La précision du tracking et de la calibration dépend de la hauteur de caméra et de la résolution fournie.
            </li>
            <li>
              <strong>Rigueur scientifique :</strong> Les indicateurs tactiques restent soumis aux protocoles et limites validés lors des benchmarks EXP-01 à EXP-26.
            </li>
          </ul>
        </div>
      </section>

      {/* 4. FORM SECTION */}
      <section className="beta-form-section" id="beta-form" aria-labelledby="form-heading">
        {submissionSuccess ? (
          <div className="beta-success-panel" role="alert">
            <div className="beta-success-meta">
              <span className="section-label">DEMANDE CONFIRMÉE</span>
              <span className="beta-request-id-badge">
                BETA REQUEST · {submissionSuccess.id}
              </span>
            </div>

            <h2 className="beta-success-title">DEMANDE REÇUE.</h2>

            <p className="beta-success-message">
              Votre demande BETA a bien été enregistrée. Nous vous contacterons à l&apos;adresse{" "}
              <strong>{formData.email}</strong> après vérification de la vidéo.
            </p>

            <div className="beta-success-actions">
              <button
                type="button"
                className="beta-cta-button"
                onClick={() => onNavigate("/")}
              >
                RETOUR À L&apos;ACCUEIL
              </button>
            </div>
          </div>
        ) : (
          <div className="beta-form-wrapper">
            <div className="beta-form-header">
              <span className="section-label">CANDIDATURE PILOTE</span>
              <h2 id="form-heading" className="beta-section-title">
                Demande d&apos;analyse match
              </h2>
              <p className="beta-form-desc">
                Remplissez les informations ci-dessous. Toutes les informations restent strictement confidentielles.
              </p>
            </div>

            {errorMessage && (
              <div className="beta-error-banner" role="alert" aria-live="polite">
                <span>{errorMessage}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} noValidate className="beta-grid-form">
              {/* Honeypot field (hidden from legitimate users) */}
              <div style={{ display: "none" }} aria-hidden="true">
                <label htmlFor="form-fax-field">Ne pas remplir</label>
                <input
                  id="form-fax-field"
                  type="text"
                  name="website"
                  tabIndex={-1}
                  autoComplete="off"
                  value={formData.website}
                  onChange={(e) => setFormData({ ...formData, website: e.target.value })}
                />
              </div>

              {/* Identity & Structure */}
              <div className="beta-form-row">
                <div className="beta-field-group">
                  <label htmlFor="field-name" className="beta-label">
                    Nom et prénom <span className="beta-required">*</span>
                  </label>
                  <input
                    id="field-name"
                    type="text"
                    required
                    className="beta-input"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="Arsène Wenger"
                  />
                </div>

                <div className="beta-field-group">
                  <label htmlFor="field-club" className="beta-label">
                    Club / structure <span className="beta-required">*</span>
                  </label>
                  <input
                    id="field-club"
                    type="text"
                    required
                    className="beta-input"
                    value={formData.club}
                    onChange={(e) => setFormData({ ...formData, club: e.target.value })}
                    placeholder="ex. FC Versailles, Centre de formation..."
                  />
                </div>
              </div>

              <div className="beta-form-row">
                <div className="beta-field-group">
                  <label htmlFor="field-role" className="beta-label">
                    Fonction <span className="beta-required">*</span>
                  </label>
                  <select
                    id="field-role"
                    required
                    className="beta-select"
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="beta-field-group">
                  <label htmlFor="field-email" className="beta-label">
                    Email professionnel <span className="beta-required">*</span>
                  </label>
                  <input
                    id="field-email"
                    type="email"
                    required
                    className="beta-input"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="staff@club.fr"
                  />
                </div>
              </div>

              <div className="beta-form-row">
                <div className="beta-field-group">
                  <label htmlFor="field-phone" className="beta-label">
                    Téléphone <span className="beta-optional">(optionnel)</span>
                  </label>
                  <input
                    id="field-phone"
                    type="tel"
                    className="beta-input"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    placeholder="+33 6 00 00 00 00"
                  />
                </div>

                <div className="beta-field-group">
                  <label htmlFor="field-category" className="beta-label">
                    Équipe / catégorie <span className="beta-required">*</span>
                  </label>
                  <input
                    id="field-category"
                    type="text"
                    required
                    className="beta-input"
                    value={formData.team_category}
                    onChange={(e) => setFormData({ ...formData, team_category: e.target.value })}
                    placeholder="ex. U19 Nationaux, Séniors R1..."
                  />
                </div>
              </div>

              <div className="beta-form-row">
                <div className="beta-field-group">
                  <label htmlFor="field-competition" className="beta-label">
                    Niveau de compétition <span className="beta-required">*</span>
                  </label>
                  <input
                    id="field-competition"
                    type="text"
                    required
                    className="beta-input"
                    value={formData.competition_level}
                    onChange={(e) => setFormData({ ...formData, competition_level: e.target.value })}
                    placeholder="ex. Régional 1, National 3, Professionnel..."
                  />
                </div>

                <div className="beta-field-group">
                  <label htmlFor="field-opponent" className="beta-label">
                    Adversaire <span className="beta-optional">(optionnel)</span>
                  </label>
                  <input
                    id="field-opponent"
                    type="text"
                    className="beta-input"
                    value={formData.opponent}
                    onChange={(e) => setFormData({ ...formData, opponent: e.target.value })}
                    placeholder="ex. FC Rouen"
                  />
                </div>
              </div>

              {/* Video details */}
              <div className="beta-form-row">
                <div className="beta-field-group">
                  <label htmlFor="field-video-type" className="beta-label">
                    Type de vidéo <span className="beta-required">*</span>
                  </label>
                  <select
                    id="field-video-type"
                    required
                    className="beta-select"
                    value={formData.video_type}
                    onChange={(e) => setFormData({ ...formData, video_type: e.target.value })}
                  >
                    {VIDEO_TYPES.map((vt) => (
                      <option key={vt} value={vt}>
                        {vt}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="beta-field-group">
                  <label htmlFor="field-video-url" className="beta-label">
                    LIEN PRIVÉ VERS LA VIDÉO <span className="beta-required">*</span>
                  </label>
                  <input
                    id="field-video-url"
                    type="url"
                    required
                    className="beta-input"
                    value={formData.video_url}
                    onChange={(e) => setFormData({ ...formData, video_url: e.target.value })}
                    placeholder="https://..."
                    aria-describedby="video-helper-desc"
                  />
                  <span id="video-helper-desc" className="beta-helper-note">
                    Google Drive, Dropbox, SwissTransfer, WeTransfer ou service équivalent.
                  </span>
                </div>
              </div>

              {/* Expandable Drive Helper */}
              <div className="beta-expandable-section">
                <button
                  type="button"
                  className="beta-expand-button"
                  onClick={() => setShowDriveHelper(!showDriveHelper)}
                  aria-expanded={showDriveHelper}
                >
                  <span>COMMENT PARTAGER MON MATCH ?</span>
                  <span className="mono">{showDriveHelper ? "[-]" : "[+]"}</span>
                </button>

                {showDriveHelper && (
                  <div className="beta-expand-content">
                    <p style={{ fontWeight: 600, marginBottom: "6px" }}>Google Drive :</p>
                    <ol style={{ paddingLeft: "18px", marginBottom: "12px", lineHeight: "1.6" }}>
                      <li>Importez votre vidéo dans votre propre Drive.</li>
                      <li>Ouvrez les paramètres de partage du fichier.</li>
                      <li>Choisissez &ldquo;Tous les utilisateurs disposant du lien&rdquo; (Lecteur) ou autorisez l&apos;accès au destinataire.</li>
                      <li>Copiez et collez le lien ci-dessus.</li>
                    </ol>
                    <p style={{ fontWeight: 600, marginBottom: "6px" }}>Dropbox / SwissTransfer / WeTransfer :</p>
                    <p style={{ lineHeight: "1.6" }}>
                      Générez un lien de téléchargement direct sans mot de passe ou prévoyez une durée de validité suffisante (7 jours recommandés).
                    </p>
                  </div>
                )}
              </div>

              {/* Objectives Multi-Select */}
              <div className="beta-field-group" style={{ marginTop: "12px" }}>
                <span className="beta-label">
                  Objectifs principaux d&apos;analyse <span className="beta-required">*</span>
                </span>
                <div className="beta-checkbox-grid">
                  {OBJECTIVES.map((obj) => {
                    const isChecked = formData.analysis_objectives.includes(obj);
                    return (
                      <label key={obj} className="beta-checkbox-label">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleObjectiveToggle(obj)}
                          className="beta-checkbox"
                        />
                        <span>{obj}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Optional Message */}
              <div className="beta-field-group" style={{ marginTop: "16px" }}>
                <label htmlFor="field-message" className="beta-label">
                  Message complémentaire <span className="beta-optional">(optionnel)</span>
                </label>
                <textarea
                  id="field-message"
                  rows={3}
                  className="beta-textarea"
                  value={formData.message}
                  onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                  placeholder="Points d'attention particuliers, minutes clés du match, consignes tactiques appliquées..."
                />
              </div>

              {/* Mandatory Consents */}
              <div className="beta-consents-group">
                <label className="beta-consent-label">
                  <input
                    type="checkbox"
                    required
                    checked={formData.video_authorization_confirmed}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        video_authorization_confirmed: e.target.checked,
                      })
                    }
                    className="beta-checkbox"
                  />
                  <span>
                    Je confirme disposer des droits et autorisations nécessaires pour transmettre cette vidéo à VISION-BALLING et demander son analyse, notamment lorsque des sportifs identifiables ou mineurs y apparaissent.{" "}
                    <button
                      type="button"
                      className="beta-inline-link"
                      onClick={() => onNavigate("/beta-terms")}
                    >
                      (Voir conditions BETA)
                    </button>{" "}
                    <span className="beta-required">*</span>
                  </span>
                </label>

                <label className="beta-consent-label">
                  <input
                    type="checkbox"
                    required
                    checked={formData.temporary_storage_consent}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        temporary_storage_consent: e.target.checked,
                      })
                    }
                    className="beta-checkbox"
                  />
                  <span>
                    J&apos;accepte que la vidéo et les résultats associés soient conservés temporairement afin de réaliser l&apos;analyse.{" "}
                    <button
                      type="button"
                      className="beta-inline-link"
                      onClick={() => onNavigate("/privacy")}
                    >
                      (Voir politique de confidentialité)
                    </button>{" "}
                    <span className="beta-required">*</span>
                  </span>
                </label>
              </div>

              {/* Submit CTA */}
              <div className="beta-form-actions">
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="beta-cta-button"
                  style={{ width: "100%", padding: "14px" }}
                >
                  {isSubmitting ? "ENVOI DE LA DEMANDE EN COURS..." : "SOUMETTRE MA DEMANDE D'ANALYSE →"}
                </button>
              </div>

              {/* Privacy statement below form */}
              <p className="beta-privacy-footer-note">
                Les vidéos reçues dans le cadre de la BETA ne sont pas rendues publiques, ne sont pas utilisées pour des démonstrations publiques, ni intégrées à des jeux de données d&apos;entraînement de modèles sans accord exprès. Elles sont utilisées uniquement pour réaliser l&apos;analyse demandée et sont supprimées selon la politique de conservation applicable.
              </p>
            </form>
          </div>
        )}
      </section>
    </div>
  );
}

BetaPage.propTypes = {
  onNavigate: PropTypes.func.isRequired,
};
