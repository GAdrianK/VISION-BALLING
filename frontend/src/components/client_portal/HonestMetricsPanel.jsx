export default function HonestMetricsPanel({ job, summary }) {
  const duration =
    job?.pipeline?.video_duration_seconds != null
      ? `${Number(job.pipeline.video_duration_seconds).toFixed(1)} s`
      : summary?.duration_seconds != null
      ? `${Number(summary.duration_seconds).toFixed(1)} s`
      : "Non mesuré";

  const fps =
    job?.pipeline?.average_processing_fps != null && job.pipeline.average_processing_fps > 0
      ? `${Number(job.pipeline.average_processing_fps).toFixed(1)} FPS`
      : "25.0 FPS (nominal)";

  const teams = summary ? Object.keys(summary).filter((k) => k !== "duration_seconds").sort() : [];

  return (
    <div
      className="honest-metrics-panel"
      style={{
        background: "#FFFFFF",
        border: "1px solid #E5E5E0",
        borderRadius: "2px",
        padding: "20px 24px",
        fontFamily: "'Inter', -apple-system, sans-serif",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid #EAEAEA",
          paddingBottom: "12px",
          marginBottom: "16px",
        }}
      >
        <span
          style={{
            fontFamily: "monospace",
            fontSize: "11px",
            letterSpacing: "0.06em",
            color: "#666666",
            textTransform: "uppercase",
          }}
        >
          Métriques Physiques Mesurées
        </span>
        <div style={{ display: "flex", gap: "16px", fontSize: "12px", fontFamily: "monospace" }}>
          <span>
            Durée : <strong>{duration}</strong>
          </span>
          <span>
            Cadence : <strong>{fps}</strong>
          </span>
        </div>
      </div>

      {teams.length === 0 ? (
        <div style={{ fontSize: "12px", color: "#888888", fontStyle: "italic", padding: "12px 0" }}>
          Agrégats collectifs en cours de consolidation ou données indisponibles.
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${teams.length}, 1fr)`, gap: "20px" }}>
          {teams.map((teamKey) => {
            const t = summary[teamKey];
            const teamId = t.team_id != null ? `Équipe ${t.team_id}` : teamKey;
            const possession = t.secure_possession_pct != null ? `${Number(t.secure_possession_pct).toFixed(1)}%` : "N/D";
            const blockHeight = t.mean_defensive_line_height_m != null ? `${Number(t.mean_defensive_line_height_m).toFixed(1)} m` : "N/D";
            const blockDepth = t.mean_team_depth_m != null ? `${Number(t.mean_team_depth_m).toFixed(1)} m` : "N/D";
            const pressure = t.mean_pressure_index != null ? Number(t.mean_pressure_index).toFixed(3) : "N/D";
            const pressureEpisodes = t.high_quality_pressure_episode_count != null ? t.high_quality_pressure_episode_count : "0";

            return (
              <div
                key={teamKey}
                style={{
                  background: "#FAFAF8",
                  border: "1px solid #ECECE8",
                  padding: "16px",
                  borderRadius: "2px",
                }}
              >
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: "600",
                    letterSpacing: "-0.01em",
                    color: "#111111",
                    marginBottom: "12px",
                    borderBottom: "1px solid #E0E0DC",
                    paddingBottom: "6px",
                  }}
                >
                  {teamId}
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#666" }}>Possession sécurisée</span>
                    <strong style={{ fontFamily: "monospace", color: "#111" }}>{possession}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#666" }}>Hauteur moyenne du bloc</span>
                    <strong style={{ fontFamily: "monospace", color: "#111" }}>{blockHeight}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#666" }}>Profondeur moyenne du bloc</span>
                    <strong style={{ fontFamily: "monospace", color: "#111" }}>{blockDepth}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#666" }}>Pression défensive moyenne</span>
                    <strong style={{ fontFamily: "monospace", color: "#111" }}>{pressure}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#666" }}>Épisodes de pressing intense</span>
                    <strong style={{ fontFamily: "monospace", color: "#111" }}>{pressureEpisodes}</strong>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div
        style={{
          marginTop: "16px",
          paddingTop: "12px",
          borderTop: "1px solid #F0F0EE",
          display: "flex",
          justifyContent: "space-between",
          fontSize: "11px",
          color: "#888888",
        }}
      >
        <span>Origine : Traitement GPU local (RTX 4060) · Ontologie EXP-01 / EXP-26</span>
        <span>Score & xG : Exclus (hors périmètre de mesure physique)</span>
      </div>
    </div>
  );
}
