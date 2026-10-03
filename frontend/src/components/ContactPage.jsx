import { useState } from "react";

export default function ContactPage() {
  const [formData, setFormData] = useState({ name: "", email: "", message: "" });
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.email || !formData.message) return;
    setSubmitted(true);
  };

  return (
    <div className="contact-page-wrapper" style={{ maxWidth: "680px", margin: "0 auto", paddingBottom: "64px" }}>
      {/* Header */}
      <div style={{ marginBottom: "48px" }}>
        <span className="section-label">CONTACT & RECHERCHE</span>
        <h1 className="page-title">Échange & partenariats</h1>
        <p className="page-subtitle">
          Pour toute question relative aux protocoles expérimentaux, aux benchmarks de vision par ordinateur ou aux partenariats académiques et clubs.
        </p>
      </div>

      {/* External Direct Links */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "24px",
          paddingBottom: "32px",
          marginBottom: "40px",
          borderBottom: "1px solid var(--border-light)",
        }}
        className="mono"
      >
        <div>
          <span style={{ fontSize: "11px", color: "var(--muted)", display: "block" }}>DÉPÔT DU CODE</span>
          <a
            href="https://github.com/GAdrianK/football-intelligence-rag"
            target="_blank"
            rel="noreferrer"
            style={{ fontSize: "13px", textDecoration: "underline", color: "var(--text)" }}
          >
            github.com/GAdrianK/football-intelligence-rag
          </a>
        </div>

        <div>
          <span style={{ fontSize: "11px", color: "var(--muted)", display: "block" }}>COURRIEL DIRECT</span>
          <a
            href="mailto:contact@vision-balling.ai"
            style={{ fontSize: "13px", textDecoration: "underline", color: "var(--text)" }}
          >
            contact@vision-balling.ai
          </a>
        </div>
      </div>

      {/* Minimal Underline Form */}
      {submitted ? (
        <div style={{ padding: "32px 0", borderTop: "1px solid var(--border-light)" }}>
          <h3 style={{ fontSize: "18px", fontWeight: 500, marginBottom: "8px" }}>Message transmis</h3>
          <p style={{ color: "var(--muted)", fontSize: "13px" }}>
            Merci pour votre prise de contact. Nous reviendrons vers vous dans les plus brefs délais.
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: "28px" }}>
          <div>
            <label htmlFor="contact-name" className="mono" style={{ fontSize: "11px", color: "var(--muted)", display: "block", marginBottom: "6px" }}>
              NOM OU ORGANISATION
            </label>
            <input
              id="contact-name"
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              style={{
                width: "100%",
                padding: "8px 0",
                border: "none",
                borderBottom: "1px solid var(--text)",
                borderRadius: 0,
                fontSize: "14px",
                backgroundColor: "transparent",
              }}
              placeholder="Ex: Club, Université ou Analyste Indépendant"
            />
          </div>

          <div>
            <label htmlFor="contact-email" className="mono" style={{ fontSize: "11px", color: "var(--muted)", display: "block", marginBottom: "6px" }}>
              ADRESSE COURRIEL
            </label>
            <input
              id="contact-email"
              type="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              style={{
                width: "100%",
                padding: "8px 0",
                border: "none",
                borderBottom: "1px solid var(--text)",
                borderRadius: 0,
                fontSize: "14px",
                backgroundColor: "transparent",
              }}
              placeholder="nom@domaine.com"
            />
          </div>

          <div>
            <label htmlFor="contact-message" className="mono" style={{ fontSize: "11px", color: "var(--muted)", display: "block", marginBottom: "6px" }}>
              OBJET DE LA DEMANDE
            </label>
            <textarea
              id="contact-message"
              required
              rows={4}
              value={formData.message}
              onChange={(e) => setFormData({ ...formData, message: e.target.value })}
              style={{
                width: "100%",
                padding: "8px 0",
                border: "none",
                borderBottom: "1px solid var(--text)",
                borderRadius: 0,
                fontSize: "14px",
                backgroundColor: "transparent",
                resize: "vertical",
              }}
              placeholder="Détaillez votre question ou projet d'analyse..."
            />
          </div>

          <div style={{ marginTop: "12px" }}>
            <button type="submit" className="btn-primary">
              ENVOYER LE MESSAGE
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
