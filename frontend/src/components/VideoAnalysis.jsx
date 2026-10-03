import { useEffect, useRef, useState } from "react";
import { marked } from "marked";
import "./VideoAnalysis.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const isPresent = (value) => value !== null && value !== undefined && value !== "";

const formatValue = (value, suffix = "") =>
  isPresent(value) ? `${value}${suffix}` : "—";

const resolveApiUrl = (url) => {
  if (!url) return null;
  return /^https?:\/\//i.test(url) ? url : `${API_BASE}${url}`;
};

const artifactMetadata = {
  annotated_video: { label: "Vidéo annotée", filename: "annotated.mp4", media_type: "video/mp4" },
  detections_json: { label: "Détections JSON", filename: "detections.json", media_type: "application/json" },
  preview_image: { label: "Aperçu image", filename: "preview.jpg", media_type: "image/jpeg" },
};

export default function VideoAnalysis() {
  const [file, setFile] = useState(null);
  const [job, setJob] = useState(null);
  const [result, setResult] = useState(null);
  const [artifacts, setArtifacts] = useState([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Chapter 8 Grounded Tactical Intelligence states
  const [activeTab, setActiveTab] = useState("overview"); // "overview" | "timeline" | "report" | "query"
  const [tacticalSummary, setTacticalSummary] = useState(null);
  const [tacticalTimeline, setTacticalTimeline] = useState([]);
  const [groundedReport, setGroundedReport] = useState("");
  const [selectedEventId, setSelectedEventId] = useState(null);
  const [queryInput, setQueryInput] = useState("");
  const [queryResponse, setQueryResponse] = useState(null);
  const [queryLoading, setQueryLoading] = useState(false);

  const timerRef = useRef(null);
  const videoRef = useRef(null);

  useEffect(() => () => window.clearTimeout(timerRef.current), []);

  const loadTacticalIntelligence = async (analysisId) => {
    try {
      const [sumRes, timeRes, repRes] = await Promise.all([
        fetch(`${API_BASE}/api/video-analysis/${analysisId}/summary`),
        fetch(`${API_BASE}/api/video-analysis/${analysisId}/timeline`),
        fetch(`${API_BASE}/api/video-analysis/${analysisId}/report`, { method: "POST" }),
      ]);

      if (sumRes.ok) setTacticalSummary(await sumRes.json());
      if (timeRes.ok) setTacticalTimeline(await timeRes.json());
      if (repRes.ok) {
        const repData = await repRes.json();
        setGroundedReport(repData.markdown_report || "");
      }
    } catch (e) {
      console.warn("Could not load full tactical intelligence:", e);
    }
  };

  const loadDemoSequence = (demoId = "SNMOT-068") => {
    setError("");
    setJob({
      analysis_id: demoId,
      status: "completed",
      progress_percent: 100,
      current_step: "completed (DEMO)",
    });
    setResult({
      status: "completed",
      analysis_id: demoId,
      video: { filename: `${demoId}_broadcast.mp4`, duration_seconds: 14.0, fps: 25.0, width: 1920, height: 1080 },
      frames_analyzed: 350,
      processing_duration_seconds: 18.2,
      average_processing_fps: 19.2,
      class_summary: { person_detections: 3820, ball_detections: 312 },
      pipeline: { detector_name: "RF-DETR", tracker_name: "PlayerBoTSORT+ReID", device: "cuda" },
    });
    loadTacticalIntelligence(demoId);
  };

  const poll = async (analysisId) => {
    try {
      const response = await fetch(`${API_BASE}/api/video-analysis/${analysisId}`);
      if (!response.ok) throw new Error("Impossible de consulter le job.");
      const payload = await response.json();
      setJob(payload);
      if (payload.status === "completed") {
        const [details, artifactResponse] = await Promise.all([
          fetch(`${API_BASE}/api/video-analysis/${analysisId}/detections`),
          fetch(`${API_BASE}/api/video-analysis/${analysisId}/artifacts`),
        ]);
        if (!details.ok) throw new Error("Les résultats de l’analyse sont indisponibles.");
        setResult(await details.json());
        if (!artifactResponse.ok) throw new Error("La liste des artefacts est indisponible.");
        const artifactPayload = await artifactResponse.json();
        setArtifacts(Array.isArray(artifactPayload.artifacts) ? artifactPayload.artifacts : []);
        setSubmitting(false);

        // Fetch EXP-26 grounded tactical intelligence
        await loadTacticalIntelligence(analysisId);
        return;
      }
      if (payload.status === "failed") {
        setError(payload.error?.message || "Le traitement a échoué.");
        setSubmitting(false);
        return;
      }
      timerRef.current = window.setTimeout(() => poll(analysisId), 1200);
    } catch (pollError) {
      setError(pollError.message);
      setSubmitting(false);
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!file || submitting) return;
    setError("");
    setResult(null);
    setArtifacts([]);
    setJob(null);
    setTacticalSummary(null);
    setTacticalTimeline([]);
    setGroundedReport("");
    setSubmitting(true);
    const body = new FormData();
    body.append("video", file);
    try {
      const response = await fetch(`${API_BASE}/api/video-analysis`, {
        method: "POST",
        body,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Upload refusé.");
      setJob({
        analysis_id: payload.analysis_id,
        status: payload.status,
        progress_percent: payload.reused ? 100 : 0,
        current_step: payload.reused ? "completed" : "queued",
      });
      await poll(payload.analysis_id);
    } catch (submitError) {
      setError(submitError.message);
      setSubmitting(false);
    }
  };

  const handleSeekEvent = (timestamp, eventId) => {
    setSelectedEventId(eventId);
    if (videoRef.current && Number.isFinite(timestamp)) {
      videoRef.current.currentTime = timestamp;
      videoRef.current.play?.().catch(() => {});
    }
  };

  const handleAskQuery = async (e) => {
    e.preventDefault();
    const currId = job?.analysis_id || result?.analysis_id;
    if (!currId || !queryInput.trim() || queryLoading) return;
    setQueryLoading(true);
    setQueryResponse(null);
    try {
      const res = await fetch(`${API_BASE}/api/video-analysis/${currId}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: queryInput, include_knowledge_base: true }),
      });
      if (!res.ok) throw new Error("Erreur lors de l'interrogation.");
      const data = await res.json();
      setQueryResponse(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setQueryLoading(false);
    }
  };

  const personCount = result?.class_summary?.person_detections;
  const ballCount = result?.class_summary?.ball_detections;
  const progressValue = isPresent(job?.progress_percent) && Number.isFinite(Number(job.progress_percent))
    ? Math.min(100, Math.max(0, Number(job.progress_percent)))
    : null;
  const resultArtifacts = Object.entries(result?.artifacts || {})
    .filter(([, url]) => isPresent(url))
    .map(([name, url]) => ({ name, url, media_type: artifactMetadata[name]?.media_type }));
  const exposedArtifacts = artifacts.length > 0 ? artifacts : resultArtifacts;
  const annotatedArtifact = exposedArtifacts.find((artifact) => artifact.name === "annotated_video");
  const annotatedVideoUrl = resolveApiUrl(annotatedArtifact?.url);

  return (
    <div className="video-analysis-grid">
      {/* Upload & Demo Column */}
      <div className="video-upload-card glass-panel">
        <span className="video-eyebrow">PIPELINE 0.9.0-RC1 • MULTIMODAL TACTICAL INTELLIGENCE</span>
        <h3>Analyse Vidéo Tactique</h3>
        <p>Importez un extrait ou chargez une séquence validée. Les évidences visuelles (blocs, pressions, transitions) sont directement ancrées et vérifiables.</p>

        <form onSubmit={submit}>
          <label className="video-file-drop">
            <input
              type="file"
              accept=".mp4,.mov,.mkv,.avi,.webm,video/*"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
            <strong>{file ? file.name : "Choisir une vidéo"}</strong>
            <span>{file ? `${(file.size / 1024 / 1024).toFixed(1)} Mo` : "MP4, MOV, MKV, AVI ou WebM"}</span>
          </label>
          <button className="video-submit" type="submit" disabled={!file || submitting}>
            {submitting ? "Analyse en cours…" : "Lancer l’analyse"}
          </button>
        </form>

        <div className="demo-selector-box">
          <span className="demo-label">JEU D’ESSAI DISPONIBLE (EXP-25 / EXP-26) :</span>
          <div className="demo-buttons">
            <button type="button" className="demo-btn" onClick={() => loadDemoSequence("SNMOT-068")}>
              Charger SNMOT-068 <span className="demo-badge">DEMO</span>
            </button>
            <button type="button" className="demo-btn" onClick={() => loadDemoSequence("SNMOT-069")}>
              Charger SNMOT-069 <span className="demo-badge">DEMO</span>
            </button>
          </div>
        </div>

        {error && <p className="video-error" role="alert">{error}</p>}
      </div>

      {/* Results & Tactical Intelligence Column */}
      <div className="video-result-card glass-panel" aria-live="polite">
        {!job && <div className="video-empty">Importez une vidéo ou chargez une séquence DEMO pour afficher l&apos;analyse.</div>}

        {job && (
          <>
            <div className="video-status-row">
              <div><span>STATUT</span><strong>{formatValue(result?.status ?? job.status)}</strong></div>
              <div><span>IDENTIFIANT</span><strong>{formatValue(result?.analysis_id ?? job.analysis_id)}</strong></div>
              <div><span>ÉTAPE</span><strong>{formatValue(job.current_step)}</strong></div>
              <div><span>PROGRESSION</span><strong>{formatValue(progressValue, " %")}</strong></div>
            </div>
            <div className="video-progress"><i style={{ width: `${progressValue ?? 0}%` }} /></div>
          </>
        )}

        {annotatedVideoUrl && (
          <video ref={videoRef} className="annotated-video" controls preload="metadata" src={annotatedVideoUrl}>
            Votre navigateur ne peut pas lire la vidéo annotée.
          </video>
        )}

        {/* Tab Navigation for Tactical Intelligence */}
        {job && (
          <div className="tactical-tabs">
            <button className={`tab-btn ${activeTab === "overview" ? "active" : ""}`} onClick={() => setActiveTab("overview")}>
              Agrégats & CV
            </button>
            <button className={`tab-btn ${activeTab === "timeline" ? "active" : ""}`} onClick={() => setActiveTab("timeline")}>
              Événements & Timeline ({tacticalTimeline.length})
            </button>
            <button className={`tab-btn ${activeTab === "report" ? "active" : ""}`} onClick={() => setActiveTab("report")}>
              Rapport Ancré (100%)
            </button>
            <button className={`tab-btn ${activeTab === "query" ? "active" : ""}`} onClick={() => setActiveTab("query")}>
              Grounded Q&A
            </button>
          </div>
        )}

        {/* TAB 1: OVERVIEW & CV STATS */}
        {activeTab === "overview" && result && (
          <>
            {tacticalSummary && (
              <div className="tactical-aggregates-box">
                <h4>Équipes & Primitives Tactiques Observées (EXP-25)</h4>
                <div className="team-cards-grid">
                  {Object.entries(tacticalSummary).map(([tKey, tData]) => (
                    <div key={tKey} className="team-card">
                      <span className="team-header">{tData.team_id || tKey}</span>
                      <div className="team-stats-grid">
                        <div><span>Possession</span><strong>{tData.secure_possession_pct?.toFixed(1) ?? "—"} %</strong></div>
                        <div><span>Hauteur bloc</span><strong>{tData.mean_defensive_line_height_m?.toFixed(1) ?? "—"} m</strong></div>
                        <div><span>Indice pression</span><strong>{tData.mean_pressure_index?.toFixed(3) ?? "—"}</strong></div>
                        <div><span>Compacité (surf.)</span><strong>{tData.mean_hull_area_m2?.toFixed(0) ?? "—"} m²</strong></div>
                      </div>
                      <span className="team-coverage">
                        Couverture: {tData.reliability?.coverage_pct?.toFixed(0) ?? 100}% • Confiance: {tData.reliability?.confidence_mean?.toFixed(2) ?? "0.55"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="video-summary">
              <div><strong>{formatValue(result.video?.duration_seconds, " s")}</strong><span>durée source</span></div>
              <div><strong>{formatValue(result.frames_analyzed)}</strong><span>frames analysées</span></div>
              <div><strong>{formatValue(personCount)}</strong><span>détections personnes</span></div>
              <div><strong>{formatValue(ballCount)}</strong><span>détections ballon</span></div>
              <div><strong>{formatValue(result.average_processing_fps)}</strong><span>FPS effectif CV</span></div>
              <div><strong>{formatValue(result.pipeline?.detector_name ?? "RF-DETR")}</strong><span>détecteur</span></div>
              <div><strong>{formatValue(result.pipeline?.tracker_name ?? "ByteTrack")}</strong><span>tracker</span></div>
              <div><strong>{formatValue(result.pipeline?.device ?? "cpu")}</strong><span>device</span></div>
            </div>
          </>
        )}

        {/* TAB 2: TIMELINE & EVENT CARDS */}
        {activeTab === "timeline" && (
          <div className="tactical-timeline-container">
            {tacticalTimeline.length === 0 ? (
              <p className="empty-notice">Aucun événement tactique indexé pour cette séquence.</p>
            ) : (
              tacticalTimeline.map((evt) => (
                <div
                  key={evt.event_id}
                  className={`event-card glass-panel ${selectedEventId === evt.event_id ? "selected" : ""}`}
                  onClick={() => handleSeekEvent(evt.start_timestamp, evt.event_id)}
                >
                  <div className="event-card-header">
                    <span className="event-family">{evt.event_family}</span>
                    <span className={`event-level level-${evt.semantic_level}`}>{evt.semantic_level}</span>
                    <span className={`event-quality q-${evt.quality_level}`}>{evt.quality_level}</span>
                    <span className="event-time">{evt.start_timestamp?.toFixed(2)}s – {evt.end_timestamp?.toFixed(2)}s</span>
                  </div>
                  <p className="event-summary">{evt.summary_text}</p>
                  <div className="event-footer">
                    <span className="event-citation">
                      [event:{evt.event_id} | t={evt.start_timestamp?.toFixed(2)}s | conf={evt.confidence?.toFixed(2)}]
                    </span>
                    {evt.conflict_flag && <span className="conflict-badge">⚠️ Signal contradictoire</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB 3: GROUNDED REPORT */}
        {activeTab === "report" && (
          <div className="tactical-report-container">
            {groundedReport ? (
              <div
                className="markdown-report-body"
                dangerouslySetInnerHTML={{ __html: marked.parse(groundedReport) }}
              />
            ) : (
              <p className="empty-notice">Génération du rapport en cours ou indisponible.</p>
            )}
          </div>
        )}

        {/* TAB 4: GROUNDED Q&A */}
        {activeTab === "query" && (
          <div className="grounded-qa-container">
            <form onSubmit={handleAskQuery} className="qa-form">
              <input
                type="text"
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value)}
                placeholder="Ex: Que se passe-t-il à 2.16 secondes ? ou Quelle équipe a le plus pressé ?"
                disabled={queryLoading}
              />
              <button type="submit" disabled={!queryInput.trim() || queryLoading}>
                {queryLoading ? "Recherche…" : "Interroger"}
              </button>
            </form>

            {queryResponse && (
              <div className="qa-response-box glass-panel">
                <div className="qa-meta">
                  <span className="qa-scope">SCOPE : {queryResponse.query_scope}</span>
                  <span className="qa-conf">Confiance : {queryResponse.confidence}</span>
                  {queryResponse.is_abstention && <span className="qa-abstain">ABSTENTION CONTRÔLÉE</span>}
                </div>
                <div
                  className="qa-answer-text"
                  dangerouslySetInnerHTML={{ __html: marked.parse(queryResponse.answer || "") }}
                />
                {queryResponse.evidence_citations?.length > 0 && (
                  <div className="qa-citations">
                    <strong>Preuves Vidéo Citées :</strong>
                    <ul>
                      {queryResponse.evidence_citations.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
