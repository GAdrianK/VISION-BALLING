import { useState } from "react";

export default function EvidenceCards({ events = [], selectedEventId = null, onSelectEvent }) {
  const [filter, setFilter] = useState("ALL");

  const formatTimestamp = (sec) => {
    if (sec === null || sec === undefined) return "00:00.0";
    const m = Math.floor(sec / 60);
    const s = (sec % 60).toFixed(2);
    return `${m.toString().padStart(2, "0")}:${s.padStart(5, "0")}`;
  };

  const getSemanticTag = (level) => {
    if (!level) return "FACT";
    if (level.includes("LEVEL_1") || level.includes("FACT")) return "FACT";
    if (level.includes("LEVEL_2") || level.includes("STRUCTURAL")) return "STRUCTURAL";
    if (level.includes("LEVEL_3") || level.includes("CANDIDATE")) return "CANDIDATE";
    return "FACT";
  };

  const filteredEvents = events.filter((ev) => {
    if (filter === "ALL") return true;
    if (filter === "POSSESSION" && (ev.event_family?.includes("POSSESSION") || ev.event_family?.includes("BALL"))) return true;
    if (filter === "PRESSURE" && ev.event_family?.includes("PRESSURE")) return true;
    if (filter === "TRANSITION" && (ev.event_family?.includes("ENGAGEMENT") || ev.event_family?.includes("TRANSITION"))) return true;
    return false;
  });

  return (
    <div className="evidence-panel-wrapper" style={{ marginTop: "24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <span className="section-label">FICHES DE PREUVES STRUCTURÉES ({filteredEvents.length})</span>
        <div style={{ display: "flex", gap: "6px" }}>
          {["ALL", "POSSESSION", "PRESSURE", "TRANSITION"].map((f) => (
            <button
              key={f}
              className={`btn-secondary ${filter === f ? "active" : ""}`}
              style={{
                fontSize: "11px",
                padding: "4px 8px",
                borderColor: filter === f ? "var(--text)" : "var(--border)",
                fontWeight: filter === f ? 600 : 400,
              }}
              onClick={() => setFilter(f)}
            >
              {f === "ALL" ? "TOUS" : f}
            </button>
          ))}
        </div>
      </div>

      <div className="events-table">
        {filteredEvents.length === 0 && (
          <div style={{ padding: "32px", textAlign: "center", color: "var(--muted)", fontSize: "13px" }}>
            Aucun événement dans cette catégorie.
          </div>
        )}

        {filteredEvents.map((ev) => {
          const isSelected = selectedEventId === ev.event_id;
          const tag = getSemanticTag(ev.semantic_level);
          const timeStr = formatTimestamp(ev.start_timestamp ?? ev.timestamp_seconds);
          const conf = Number(ev.confidence || 0).toFixed(2);
          const quality = ev.quality_level || "HIGH";
          const pDelta = ev.supporting_metrics?.mean_pressure_index
            ? `P: ${Number(ev.supporting_metrics.mean_pressure_index).toFixed(2)}`
            : "";

          return (
            <div
              key={ev.event_id || `${timeStr}-${ev.event_family}`}
              className={`event-row ${isSelected ? "selected" : ""}`}
              onClick={() => onSelectEvent && onSelectEvent(ev.start_timestamp ?? ev.timestamp_seconds, ev.event_id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelectEvent && onSelectEvent(ev.start_timestamp ?? ev.timestamp_seconds, ev.event_id);
                }
              }}
            >
              <div className="event-time">{timeStr}</div>

              <div className="event-type">
                {ev.event_family?.replace(/_/g, " ") || "ACTION"}
              </div>

              <div className="mono" style={{ fontSize: "11px", color: "var(--muted)" }}>
                {ev.subject_team || "—"} {ev.opponent_team ? `→ ${ev.opponent_team}` : ""}
              </div>

              <div className="event-details" style={{ fontSize: "12px", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {ev.summary_text || `Événement ${ev.event_family} à ${timeStr}`}
              </div>

              <div className="event-metrics" style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "2px" }}>
                <span className="event-semantic-tag">{tag}</span>
                <span className="mono" style={{ fontSize: "10px", color: "var(--muted)" }}>
                  Conf: {conf} · {quality} {pDelta ? `· ${pDelta}` : ""}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
