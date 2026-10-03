export default function ProjectPage() {
  const chapters = [
    {
      index: "01",
      title: "PERCEPTION VIDÉO & DÉTECTION",
      metric: "RF-DETR Small @ 960px · mAP50 = 0.865 (H250)",
      body: "Évaluation comparative des détecteurs sur le dataset spécialisé H250. RF-DETR surpasse YOLO11s (0.842) sur les petits objets (ballon, joueurs distants). YOLO11n à 640px est conservé pour le mode accéléré.",
    },
    {
      index: "02",
      title: "SUIVI MULTI-OBJETS & RE-IDENTIFICATION",
      metric: "BoT-SORT + PRTReID · IDF1 = 75.8 % · Économie calcul : -68 %",
      body: "Association multi-objets combinant la cinématique Kalman et les embeddings d'apparence 256-D extraits par BPB-ReID HRNet-32. Le gating conditionnel réserve l'inférence ReID aux situations d'ambiguïté spatiale.",
    },
    {
      index: "03",
      title: "CALIBRATION DU TERRAIN & MÉTRIQUE 2D",
      metric: "PnLCalib · Erreur reprojection : 3.2 px · Lissage temporel : -54 % variance",
      body: "Estimation de la matrice d'homographie planaire reliant les pixels caméra au repère métrique du terrain (105 m × 68 m). Filtrage récursif temporel de la matrice H pour éliminer les micro-saccades.",
    },
    {
      index: "04",
      title: "INTELLIGENCE TACTIQUE SPATIO-TEMPORELLE",
      metric: "Possession V2 : +21 % F1 · PressureIndex continu ∈ [0, 1]",
      body: "Calcul de la hauteur de bloc défensif, de la compacité surfacique (m²), de la pression continue vectorielle et des transitions de contre-pressing. Modélisation causale dans un graphe d'événements spatio-temporel.",
    },
    {
      index: "05",
      title: "RAG MULTIMODAL ANCRÉ & RAPPORT DE MATCH",
      metric: "Affirmations étayées : 100 % · Hallucination sur le match : 0 % (76/76 cas)",
      body: "Les événements vidéo structurés constituent l'unique source de vérité factuelle sur le match. La base documentaire générale intervient exclusivement pour expliciter le sens tactique des observations observées.",
    },
  ];

  return (
    <div className="project-page-wrapper" style={{ maxWidth: "860px", margin: "0 auto" }}>
      {/* Editorial Header */}
      <div style={{ marginBottom: "48px" }}>
        <span className="section-label">DOSSIER TECHNIQUE & SCIENTIFIQUE</span>
        <h1 className="page-title">Architecture du système & résultats d&apos;expérimentation</h1>
        <p className="page-subtitle">
          Unification des chapitres 1 à 8 et des 26 expériences gelées (EXP-01 à EXP-26) en une plateforme computationnelle d&apos;analyse tactique vérifiable.
        </p>
      </div>

      {/* Pipeline Diagram */}
      <div
        style={{
          border: "1px solid var(--border)",
          background: "var(--surface)",
          borderRadius: "var(--radius)",
          padding: "24px 28px",
          marginBottom: "48px",
        }}
      >
        <div className="summary-heading" style={{ marginBottom: "16px" }}>
          <span>CHAÎNE CAUSALE DE TRAITEMENT (PIPELINE)</span>
        </div>
        <div
          className="mono"
          style={{
            fontSize: "12px",
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "8px",
            color: "var(--text)",
          }}
        >
          <span>VIDÉO BRUTE</span>
          <span style={{ color: "var(--muted)" }}>→</span>
          <span>DÉTECTION (RF-DETR)</span>
          <span style={{ color: "var(--muted)" }}>→</span>
          <span>TRACKING (BoT-SORT + ReID)</span>
          <span style={{ color: "var(--muted)" }}>→</span>
          <span>CALIBRATION 2D (PnLCalib)</span>
          <span style={{ color: "var(--muted)" }}>→</span>
          <span>PREUVES TACTIQUES (EXP-25)</span>
          <span style={{ color: "var(--muted)" }}>→</span>
          <span>RAG MULTIMODAL ANCRÉ (EXP-26)</span>
        </div>
      </div>

      {/* Vertical Narrative Sections */}
      <div style={{ display: "grid", gap: "40px", marginBottom: "56px" }}>
        {chapters.map((ch) => (
          <section key={ch.index} style={{ borderBottom: "1px solid var(--border-light)", paddingBottom: "32px" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: "16px", marginBottom: "8px" }}>
              <span className="mono" style={{ fontSize: "12px", color: "var(--muted)" }}>{ch.index}</span>
              <h2 style={{ fontSize: "18px", fontWeight: 500 }}>{ch.title}</h2>
            </div>

            <div className="mono" style={{ fontSize: "12px", color: "var(--accent)", marginBottom: "12px", fontWeight: 500 }}>
              {ch.metric}
            </div>

            <p style={{ color: "var(--text)", fontSize: "14px", lineHeight: "1.65" }}>
              {ch.body}
            </p>
          </section>
        ))}
      </div>

      {/* Honest Limitations & Negative Results Callout */}
      <div
        style={{
          border: "1px solid var(--border)",
          background: "var(--surface)",
          borderRadius: "var(--radius)",
          padding: "32px",
        }}
      >
        <span className="section-label">DISCIPLINE ÉPISTÉMIQUE & RÉSULTATS NÉGATIFS ASSUMÉS</span>
        <h3 style={{ fontSize: "18px", marginTop: "6px", marginBottom: "16px" }}>Limites physiques et hypothèses réfutées</h3>

        <ul style={{ paddingLeft: "18px", display: "grid", gap: "10px", fontSize: "13px", lineHeight: "1.6", color: "var(--text)" }}>
          <li>
            <strong>Formations catégoriques réfutées (EXP-21) :</strong> L&apos;inférence de compositions nominales rigides (4-3-3, 4-4-2) échoue sur vidéo broadcast (Macro F1 = 0.00 %) en raison de la troncation du champ de vision (FOV) et des déformations asymétriques fluides. Seules les grandeurs continues (distances inter-lignes, centroïdes) sont validées.
          </li>
          <li>
            <strong>Pression discrète réfutée (EXP-23) :</strong> Les classes arbitraires (FORTE, FAIBLE) introduisant des effets de bord discontinus, seul l&apos;indice continu vectoriel PressureIndex est retenu.
          </li>
          <li>
            <strong>Débit temps réel strict (25 FPS) non atteint :</strong> Le pipeline complet opère à ~11.4 FPS en mode QUALITY et ~24.2 FPS en mode LOW_LATENCY sur machine standard.
          </li>
          <li>
            <strong>Hypothèse de planarité du ballon (Z=0) :</strong> Les trajectoires aériennes (dégagements, centres) subissent une erreur de parallaxe lors de la projection 2D au sol.
          </li>
          <li>
            <strong>Licence PnLCalib (GPL-2.0) :</strong> Strictement isolée dans un sous-processus hermétique pour préserver la licence permissive libre du reste du projet.
          </li>
        </ul>
      </div>
    </div>
  );
}
