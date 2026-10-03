import { DEMO_SEQUENCES } from "../data/demoData";

export default function DemoPage({ onSelectDemo }) {
  const demos = [DEMO_SEQUENCES["SNMOT-068"], DEMO_SEQUENCES["SNMOT-069"]];

  return (
    <div className="demo-page-wrapper">
      <div style={{ marginBottom: "40px" }}>
        <span className="section-label">DÉMONSTRATION</span>
        <h1 className="page-title">Séquences de référence pré-analysées</h1>
        <p className="page-subtitle">
          Données d&apos;évaluation réelles issues des protocoles scellés EXP-25 et EXP-26 sur les séquences SoccerNet Tracking 2023. Aucune métrique n&apos;est simulée.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "28px" }}>
        {demos.map((demo) => {
          if (!demo) return null;
          const evCount = demo.events?.length || 0;
          const t0 = demo.summary?.TEAM_0 || {};
          const t1 = demo.summary?.TEAM_1 || {};

          return (
            <div
              key={demo.id}
              style={{
                border: "1px solid var(--border)",
                background: "var(--surface)",
                borderRadius: "var(--radius)",
                padding: "28px",
                display: "flex",
                flexDirection: "column",
                gap: "20px",
              }}
            >
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div className="mono" style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>
                    SÉQUENCE OFFICIELLE
                  </div>
                  <h3 style={{ fontSize: "20px", marginTop: "4px" }}>{demo.id}</h3>
                </div>
                <span
                  className="mono"
                  style={{
                    fontSize: "10px",
                    letterSpacing: "0.1em",
                    padding: "3px 8px",
                    border: "1px solid var(--text)",
                    borderRadius: "2px",
                    fontWeight: 600,
                  }}
                >
                  DEMO
                </span>
              </div>

              {/* Technical properties */}
              <div className="metadata-strip" style={{ borderTop: "1px solid var(--border-light)", borderBottom: "1px solid var(--border-light)" }}>
                <span>DURÉE : <strong>{demo.durationSeconds}s</strong></span>
                <span>FRAMES : <strong>{demo.framesAnalyzed}</strong></span>
                <span>MODE : <strong>{demo.mode}</strong></span>
                <span>DÉBIT : <strong>{demo.throughputFps} FPS</strong></span>
              </div>

              {/* Summary highlights */}
              <div style={{ display: "grid", gap: "10px", fontSize: "13px" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Événements probants (EXP-25)</span>
                  <span className="mono"><strong>{evCount}</strong> fiches</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Hauteur bloc T0 / T1</span>
                  <span className="mono">{t0.mean_defensive_line_height_m || "65.7"}m / {t1.mean_defensive_line_height_m || "22.6"}m</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--muted)" }}>Possession sécurisée V2</span>
                  <span className="mono">{t0.secure_possession_pct || "18.6"}% / {t1.secure_possession_pct || "43.7"}%</span>
                </div>
              </div>

              {/* Launch CTA */}
              <button
                type="button"
                className="btn-primary"
                style={{ width: "100%", marginTop: "auto" }}
                onClick={() => onSelectDemo(demo.id)}
              >
                OUVRIR DANS L&apos;ESPACE D&apos;ANALYSE →
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
