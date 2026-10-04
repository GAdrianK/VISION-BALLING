import { useState, useEffect, useRef, useCallback } from "react";
import { API_BASE_URL } from "../../config/api";

export default function ClientVideoPlayer({ analysisId, initialStreamUrl, onTimeUpdate }) {
  const videoRef = useRef(null);
  const [streamUrl, setStreamUrl] = useState(initialStreamUrl || "");
  const [loading, setLoading] = useState(!initialStreamUrl);
  const [playbackError, setPlaybackError] = useState(null);

  const fetchStreamUrl = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/video-analysis/${analysisId}/video-stream-url`, {
        credentials: "include",
      });
      if (!resp.ok) {
        if (resp.status === 401 || resp.status === 403) {
          throw new Error("Session expirée. Veuillez rafraîchir la page.");
        }
        throw new Error(`Flux vidéo indisponible (${resp.status}).`);
      }
      const data = await resp.json();
      return data.stream_url;
    } catch (err) {
      console.warn("Failed to retrieve presigned video stream URL:", err);
      return null;
    }
  }, [analysisId]);

  // Initial load if initialStreamUrl not supplied
  useEffect(() => {
    if (!initialStreamUrl) {
      fetchStreamUrl().then((url) => {
        if (url) {
          setStreamUrl(url);
          setLoading(false);
        } else {
          setPlaybackError("Vidéo indisponible ou accès révoqué.");
          setLoading(false);
        }
      });
    } else {
      setStreamUrl(initialStreamUrl);
      setLoading(false);
    }
  }, [initialStreamUrl, fetchStreamUrl]);

  // Proactive periodic renewal of signed URL (every 4 minutes = 240,000ms)
  // Preserves currentTime and playback state seamlessly
  useEffect(() => {
    const renewalInterval = setInterval(async () => {
      const newUrl = await fetchStreamUrl();
      if (newUrl && newUrl !== streamUrl) {
        const video = videoRef.current;
        if (video) {
          const currentTime = video.currentTime;
          const wasPlaying = !video.paused;

          const handleCanPlay = () => {
            video.currentTime = currentTime;
            if (wasPlaying) {
              video.play().catch(() => {});
            }
            video.removeEventListener("canplay", handleCanPlay);
          };

          video.addEventListener("canplay", handleCanPlay);
          setStreamUrl(newUrl);
        } else {
          setStreamUrl(newUrl);
        }
      }
    }, 240000); // 4 minutes

    return () => clearInterval(renewalInterval);
  }, [streamUrl, fetchStreamUrl]);

  const handleVideoError = async () => {
    // Attempt one automatic retry with refreshed URL
    const freshUrl = await fetchStreamUrl();
    if (freshUrl && freshUrl !== streamUrl) {
      setStreamUrl(freshUrl);
      setPlaybackError(null);
    } else {
      setPlaybackError(
        "Impossible de lire le flux vidéo. La vidéo a peut-être dépassé sa période de rétention (14 jours) ou votre accès a expiré."
      );
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current && onTimeUpdate) {
      onTimeUpdate(videoRef.current.currentTime);
    }
  };

  return (
    <div
      className="client-video-container"
      style={{
        background: "#0E0E0E",
        borderRadius: "2px",
        overflow: "hidden",
        position: "relative",
        border: "1px solid #222222",
      }}
    >
      {loading ? (
        <div
          style={{
            height: "440px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#888888",
            fontSize: "13px",
            fontFamily: "monospace",
          }}
        >
          Préparation du flux vidéo sécurisé...
        </div>
      ) : playbackError ? (
        <div
          style={{
            height: "440px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "24px",
            color: "#DDDDDD",
            textAlign: "center",
            background: "#161616",
          }}
        >
          <div style={{ fontSize: "24px", marginBottom: "12px" }}>⚠️</div>
          <div style={{ fontSize: "14px", fontWeight: "600", marginBottom: "8px", color: "#FFFFFF" }}>
            Flux vidéo non disponible
          </div>
          <p style={{ fontSize: "12px", color: "#999999", maxWidth: "420px", lineHeight: "1.6", margin: "0 0 16px 0" }}>
            {playbackError}
          </p>
          <button
            onClick={async () => {
              setLoading(true);
              setPlaybackError(null);
              const url = await fetchStreamUrl();
              if (url) {
                setStreamUrl(url);
              } else {
                setPlaybackError("Le flux vidéo n'a pas pu être rechargé.");
              }
              setLoading(false);
            }}
            style={{
              padding: "8px 16px",
              background: "#2A2A2A",
              color: "#FFFFFF",
              border: "1px solid #444",
              borderRadius: "2px",
              fontSize: "12px",
              cursor: "pointer",
            }}
          >
            Réessayer la connexion
          </button>
        </div>
      ) : (
        <video
          ref={videoRef}
          src={streamUrl}
          controls
          playsInline
          preload="metadata"
          onError={handleVideoError}
          onTimeUpdate={handleTimeUpdate}
          style={{
            width: "100%",
            maxHeight: "580px",
            display: "block",
            background: "#000000",
          }}
        />
      )}
    </div>
  );
}
