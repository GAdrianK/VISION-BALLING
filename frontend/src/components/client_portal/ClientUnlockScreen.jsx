import { useState, useEffect, useRef } from "react";
import { API_BASE_URL } from "../../config/api";

export default function ClientUnlockScreen({ analysisId, onUnlocked }) {
  const [tokenInput, setTokenInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // Store capability token strictly in-memory (never in localStorage / sessionStorage)
  const capabilityRef = useRef(null);

  useEffect(() => {
    // 1. Inspect URL hash fragment for #access=<capability>
    if (typeof window !== "undefined" && window.location.hash) {
      const hash = window.location.hash.substring(1); // remove '#'
      const params = new URLSearchParams(hash);
      const accessValue = params.get("access");

      if (accessValue && accessValue.trim()) {
        const cleanToken = accessValue.trim();
        capabilityRef.current = cleanToken;
        setTokenInput(cleanToken);

        // 2. IMMEDIATELY scrub fragment from address bar (RFC 3986 client-side sanitize)
        window.history.replaceState(null, document.title, window.location.pathname);
      }
    }
  }, []);

  const handleUnlock = async (e) => {
    if (e) e.preventDefault();
    const tokenToExchange = capabilityRef.current || tokenInput.trim();

    if (!tokenToExchange) {
      setErrorMessage("Veuillez fournir le jeton d'accès privé ou utiliser le lien reçu par courriel.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/video-analysis/${analysisId}/access/exchange`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ capability_token: tokenToExchange }),
        credentials: "include", // Set __Host-vb_session cookie
      });

      if (!response.ok) {
        if (response.status === 403 || response.status === 401) {
          throw new Error("Lien ou jeton d'accès invalide, expiré ou révoqué.");
        } else if (response.status === 404) {
          throw new Error("Cette analyse n'existe pas ou n'est plus accessible.");
        } else {
          throw new Error(`Erreur d'accès (${response.status}). Veuillez réessayer ultérieurement.`);
        }
      }

      const data = await response.json();
      // Purge token from memory reference after successful session exchange
      capabilityRef.current = null;
      setTokenInput("");

      if (onUnlocked) {
        onUnlocked(data);
      }
    } catch (err) {
      setErrorMessage(err.message || "Impossible de déverrouiller l'analyse.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="unlock-container"
      style={{
        maxWidth: "560px",
        margin: "80px auto",
        padding: "40px",
        background: "#FFFFFF",
        border: "1px solid #E5E5E0",
        borderRadius: "2px",
        fontFamily: "'Inter', -apple-system, sans-serif",
      }}
    >
      <div style={{ marginBottom: "24px", borderBottom: "1px solid #EAEAEA", paddingBottom: "16px" }}>
        <div
          style={{
            fontFamily: "monospace",
            fontSize: "11px",
            letterSpacing: "0.08em",
            color: "#666666",
            textTransform: "uppercase",
            marginBottom: "8px",
          }}
        >
          VISION-BALLING · ESPACE D&apos;ANALYSE PRIVÉ
        </div>
        <h1
          style={{
            fontSize: "18px",
            fontWeight: "600",
            letterSpacing: "-0.01em",
            color: "#111111",
            margin: "0 0 8px 0",
          }}
        >
          Déverrouillage de votre match
        </h1>
        <div style={{ fontSize: "13px", color: "#555555" }}>
          Réf. analyse : <code style={{ fontFamily: "monospace", color: "#111" }}>{analysisId}</code>
        </div>
      </div>

      <p style={{ fontSize: "13px", lineHeight: "1.6", color: "#444444", marginBottom: "24px" }}>
        Cette analyse tactique est strictement confidentielle. L&apos;accès s&apos;effectue via une capacité
        sécurisée éphémère sans mot de passe durable.
      </p>

      {errorMessage && (
        <div
          style={{
            padding: "12px 14px",
            marginBottom: "20px",
            background: "#FFF5F5",
            border: "1px solid #FFCCCC",
            borderRadius: "2px",
            fontSize: "13px",
            color: "#990000",
          }}
        >
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleUnlock}>
        {!capabilityRef.current && (
          <div style={{ marginBottom: "20px" }}>
            <label
              htmlFor="tokenInput"
              style={{
                display: "block",
                fontSize: "12px",
                fontWeight: "500",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: "6px",
                color: "#444",
              }}
            >
              Jeton de capacité d&apos;accès
            </label>
            <input
              id="tokenInput"
              type="text"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="Collez votre jeton ou utilisez votre lien direct"
              style={{
                width: "100%",
                padding: "10px 12px",
                fontSize: "13px",
                fontFamily: "monospace",
                border: "1px solid #D4D4CE",
                borderRadius: "2px",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            width: "100%",
            padding: "12px 20px",
            background: "#111111",
            color: "#FFFFFF",
            fontSize: "13px",
            fontWeight: "500",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
            border: "none",
            borderRadius: "2px",
            cursor: loading ? "wait" : "pointer",
            transition: "opacity 0.2s ease",
          }}
        >
          {loading ? "Vérification de l'accès..." : "Accéder à l'analyse du match →"}
        </button>
      </form>

      <div
        style={{
          marginTop: "32px",
          paddingTop: "16px",
          borderTop: "1px solid #F0F0EE",
          fontSize: "11px",
          color: "#888888",
          lineHeight: "1.5",
        }}
      >
        🔒 Session éphémère signée par cookie <code>__Host-</code>. Aucune trace de clé n&apos;est persistée
        sur votre terminal.
      </div>
    </div>
  );
}
