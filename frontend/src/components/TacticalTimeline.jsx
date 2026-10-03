export default function TacticalTimeline({
  durationSeconds = 14.0,
  events = [],
  currentTime = 0,
  selectedEventId = null,
  onSeek,
}) {
  const duration = Math.max(durationSeconds, 1.0);

  const formatTime = (seconds) => {
    const s = Math.max(0, Number(seconds) || 0);
    const m = Math.floor(s / 60);
    const rem = (s % 60).toFixed(1);
    return `${m.toString().padStart(2, "0")}:${rem.padStart(4, "0")}`;
  };

  const getEventFamilyLabel = (family) => {
    switch (family) {
      case "POSSESSION_CHANGE":
        return "PERTE / GAIN";
      case "PRESSURE_EPISODE":
        return "PRESSION ↑";
      case "POST_LOSS_ENGAGEMENT":
        return "CONTRE-PRESSING";
      case "BALL_TRANSFER":
        return "PASSE";
      default:
        return "ÉVÉNEMENT";
    }
  };

  return (
    <div className="timeline-card" aria-label="Chronologie des événements tactiques">
      <div className="summary-heading">
        <span>INSTRUMENTATION TEMPORELLE · MATCH TIMELINE</span>
      </div>

      <div className="timeline-axis-container">
        {/* Playhead progress */}
        <div
          style={{
            position: "absolute",
            top: 14,
            left: `${Math.min(100, Math.max(0, (currentTime / duration) * 100))}%`,
            width: "1px",
            height: "22px",
            backgroundColor: "var(--accent)",
            zIndex: 10,
            pointerEvents: "none",
          }}
          title={`Position courante: ${currentTime.toFixed(2)}s`}
        />

        {/* Base horizontal axis */}
        <div className="timeline-axis-line">
          {events.map((ev) => {
            const time = ev.start_timestamp ?? ev.timestamp_seconds ?? 0;
            const pct = Math.min(100, Math.max(0, (time / duration) * 100));
            const isSelected = selectedEventId === ev.event_id;

            return (
              <div
                key={ev.event_id || `${time}-${ev.event_family}`}
                className={`timeline-event-marker ${isSelected ? "selected" : ""}`}
                style={{ left: `${pct}%` }}
                onClick={() => onSeek && onSeek(time, ev.event_id)}
                title={`${formatTime(time)} — ${ev.event_family} (${ev.subject_team})`}
                role="button"
                tabIndex={0}
                aria-label={`Aller à ${formatTime(time)} : ${ev.event_family}`}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSeek && onSeek(time, ev.event_id);
                  }
                }}
              >
                <div className="timeline-dot" />
                <span className="timeline-event-label">
                  {formatTime(time)} {getEventFamilyLabel(ev.event_family)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "28px" }} className="mono">
        <span style={{ fontSize: "11px", color: "var(--muted)" }}>00:00.0</span>
        <span style={{ fontSize: "11px", color: "var(--muted)" }}>{formatTime(duration)}</span>
      </div>
    </div>
  );
}
