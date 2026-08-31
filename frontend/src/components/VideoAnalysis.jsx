import { useEffect, useRef, useState } from "react";
import "./VideoAnalysis.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const isPresent = (value) => value !== null && value !== undefined && value !== "";

const formatValue = (value, suffix = "") =>
  isPresent(value) ? `${value}${suffix}` : "—";

const formatCoverage = (value) => {
  if (!isPresent(value)) return "—";
  const numericValue = Number(value);
  return Number.isFinite(numericValue)
    ? `${(numericValue * 100).toFixed(1)} %`
    : `${value}`;
};

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
  const timerRef = useRef(null);

  useEffect(() => () => window.clearTimeout(timerRef.current), []);

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

  const personCount = result?.class_summary?.person_detections;
  const ballCount = result?.class_summary?.ball_detections;
  const tracking = result?.tracking_summary;
  const progressValue = isPresent(job?.progress_percent) && Number.isFinite(Number(job.progress_percent))
    ? Math.min(100, Math.max(0, Number(job.progress_percent)))
    : null;
  const resultArtifacts = Object.entries(result?.artifacts || {})
    .filter(([, url]) => isPresent(url))
    .map(([name, url]) => ({ name, url, media_type: artifactMetadata[name]?.media_type }));
  const exposedArtifacts = artifacts.length > 0 ? artifacts : resultArtifacts;
  const annotatedArtifact = exposedArtifacts.find((artifact) => artifact.name === "annotated_video");
  const annotatedVideoUrl = resolveApiUrl(annotatedArtifact?.url);
  const dimensions = isPresent(result?.video?.width) && isPresent(result?.video?.height)
    ? `${result.video.width} × ${result.video.height}`
    : "—";

  const downloadArtifact = async (artifact) => {
    try {
      const response = await fetch(resolveApiUrl(artifact.url));
      if (!response.ok) throw new Error("Téléchargement de l’artefact impossible.");
      const objectUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = artifactMetadata[artifact.name]?.filename || artifact.name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    } catch (downloadError) {
      setError(downloadError.message);
    }
  };

  return (
    <div className="video-analysis-grid">
      <form className="video-upload-card glass-panel" onSubmit={submit}>
        <span className="video-eyebrow">PIPELINE 0.2.0 • PROTOTYPE EXPÉRIMENTAL</span>
        <h3>Détection vidéo expérimentale</h3>
        <p>Importez un court extrait. Le résultat distingue les détections observées des prédictions temporelles éventuelles du ballon.</p>
        <p className="video-disclaimer">Le suivi du ballon n’est pas validé sur le protocole golden. Aucune métrique tactique V1 n’est calculée.</p>
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
              <div><span>STATUT</span><strong>{formatValue(result?.status ?? job.status)}</strong></div>
              <div><span>IDENTIFIANT</span><strong>{formatValue(result?.analysis_id ?? job.analysis_id)}</strong></div>
              <div><span>ÉTAPE</span><strong>{formatValue(job.current_step)}</strong></div>
              <div><span>PROGRESSION</span><strong>{formatValue(progressValue, " %")}</strong></div>
            </div>
            <div className="video-progress"><i style={{ width: `${progressValue ?? 0}%` }} /></div>
          </>
        )}
        {annotatedVideoUrl && (
          <video className="annotated-video" controls preload="metadata" src={annotatedVideoUrl}>
            Votre navigateur ne peut pas lire la vidéo annotée.
          </video>
        )}
        {result && (
          <>
            <div className="video-summary">
              <div><strong>{formatValue(result.video?.filename)}</strong><span>fichier</span></div>
              <div><strong>{formatValue(result.video?.duration_seconds, " s")}</strong><span>durée source</span></div>
              <div><strong>{dimensions}</strong><span>dimensions source</span></div>
              <div><strong>{formatValue(result.video?.fps)}</strong><span>FPS source</span></div>
              <div><strong>{formatValue(result.frames_analyzed)}</strong><span>frames analysées</span></div>
              <div><strong>{formatValue(personCount)}</strong><span>détections personnes</span></div>
              <div><strong>{formatValue(ballCount)}</strong><span>détections ballon observées</span></div>
              <div><strong>{formatValue(tracking?.observed_frames)}</strong><span>frames ballon observées</span></div>
              <div><strong>{formatValue(tracking?.predicted_frames)}</strong><span>frames ballon prédites</span></div>
              <div><strong>{formatValue(tracking?.missing_frames)}</strong><span>frames ballon manquantes</span></div>
              <div><strong>{formatCoverage(tracking?.observed_coverage)}</strong><span>couverture observée</span></div>
              <div><strong>{formatCoverage(tracking?.effective_coverage)}</strong><span>couverture effective</span></div>
              <div><strong>{formatValue(tracking?.longest_missing_gap)}</strong><span>plus longue absence (frames)</span></div>
              <div><strong>{formatValue(tracking?.reset_count)}</strong><span>réinitialisations tracker</span></div>
              <div><strong>{formatValue(result.processing_duration_seconds, " s")}</strong><span>temps de traitement</span></div>
              <div><strong>{formatValue(tracking?.unique_person_tracks)}</strong><span>tracks personnes expérimentaux</span></div>
              <div><strong>{formatValue(result.average_processing_fps)}</strong><span>FPS traitement</span></div>
              <div><strong>{formatValue(result.pipeline?.detector_name ?? result.pipeline?.detector)}</strong><span>détecteur</span></div>
              <div><strong>{formatValue(result.pipeline?.tracker_name)}</strong><span>tracker</span></div>
              <div><strong>{formatValue(result.pipeline?.device)}</strong><span>device</span></div>
              <div><strong>{formatValue(result.pipeline?.video_backend)}</strong><span>backend vidéo</span></div>
            </div>
            {exposedArtifacts.length > 0 && (
              <div className="video-artifacts">
                <span>ARTEFACTS EXPOSÉS</span>
                <div>
                  {exposedArtifacts.map((artifact) => (
                    <button type="button" key={artifact.name} onClick={() => downloadArtifact(artifact)}>
                      Télécharger {artifactMetadata[artifact.name]?.label || artifact.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <p className="video-disclaimer">Les frames prédites prolongent une trajectoire : elles ne sont pas des détections et leur confiance de détecteur est absente.</p>
            {result.warnings?.map((warning) => (
              <p className="video-warning" key={warning}>⚠ {warning}</p>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
