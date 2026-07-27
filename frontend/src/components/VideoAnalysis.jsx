import { useEffect, useRef, useState } from "react";
import "./VideoAnalysis.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function VideoAnalysis() {
  const [file, setFile] = useState(null);
  const [job, setJob] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => () => window.clearTimeout(timerRef.current), []);

  const poll = async (analysisId) => {
    try {
      const response = await fetch(`${API_BASE}/api/video-analysis/${analysisId}`);
      if (!response.ok) throw new Error("Impossible de consulter le job.");
      const payload = await response.json();
      setJob(payload);
      if (payload.status === "completed") {
        const details = await fetch(`${API_BASE}/api/video-analysis/${analysisId}/detections`);
        if (details.ok) setResult(await details.json());
        setSubmitting(false);
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
    setJob(null);
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

  const personCount = result?.class_summary?.person_detections ?? 0;
  const ballCount = result?.class_summary?.ball_detections ?? 0;
  const artifactUrl = result?.artifacts?.annotated_video
    ? `${API_BASE}${result.artifacts.annotated_video}`
    : null;

  return (
    <div className="video-analysis-grid">
      <form className="video-upload-card glass-panel" onSubmit={submit}>
        <span className="video-eyebrow">PIPELINE V0.2 • FOOTBALL BASELINE</span>
        <h3>Détection vidéo expérimentale</h3>
        <p>Importez un court extrait. Le détecteur configuré analyse les personnes et le ballon sans interpolation.</p>
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
        {error && <p className="video-error" role="alert">{error}</p>}
      </form>

      <div className="video-result-card glass-panel" aria-live="polite">
        {!job && <div className="video-empty">Les résultats apparaîtront ici.</div>}
        {job && (
          <>
            <div className="video-status-row">
              <div><span>STATUT</span><strong>{job.status}</strong></div>
              <div><span>ÉTAPE</span><strong>{job.current_step}</strong></div>
              <div><span>PROGRESSION</span><strong>{job.progress_percent || 0}%</strong></div>
            </div>
            <div className="video-progress"><i style={{ width: `${job.progress_percent || 0}%` }} /></div>
          </>
        )}
        {artifactUrl && (
          <video className="annotated-video" controls preload="metadata" src={artifactUrl}>
            Votre navigateur ne peut pas lire la vidéo annotée.
          </video>
        )}
        {result && (
          <>
            <div className="video-summary">
              <div><strong>{result.frames_analyzed}</strong><span>frames analysées</span></div>
              <div><strong>{personCount}</strong><span>personnes détectées</span></div>
              <div><strong>{ballCount}</strong><span>ballons détectés</span></div>
              <div><strong>{result.processing_duration_seconds}s</strong><span>traitement</span></div>
              <div><strong>{result.tracking_summary?.unique_person_tracks || 0}</strong><span>tracks personnes</span></div>
              <div><strong>{result.average_processing_fps || 0}</strong><span>FPS traitement</span></div>
              <div><strong>{result.pipeline?.detector_name || result.pipeline?.detector}</strong><span>détecteur</span></div>
              <div><strong>{result.pipeline?.tracker_name || "none"}</strong><span>tracker</span></div>
              <div><strong>{result.pipeline?.device || "unknown"}</strong><span>device</span></div>
              <div><strong>{result.pipeline?.video_backend || "opencv"}</strong><span>backend vidéo</span></div>
            </div>
            {result.warnings?.map((warning) => (
              <p className="video-warning" key={warning}>⚠ {warning}</p>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
