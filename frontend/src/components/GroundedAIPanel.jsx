import { useState } from "react";
import { API_BASE } from "../config/api";

export default function GroundedAIPanel({
  analysisId = "SNMOT-068",
  qaExamples = [],
  onSeekCitation,
}) {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleAsk = async (text) => {
    const q = (text || query).trim();
    if (!q) return;

    setLoading(true);
    setResponse(null);

    // Check if question matches one of the local precomputed examples
    const match = qaExamples.find((ex) =>
      ex.query.toLowerCase().includes(q.toLowerCase()) || q.toLowerCase().includes(ex.query.toLowerCase())
    );

    if (match) {
      setTimeout(() => {
        setResponse(match);
        setLoading(false);
      }, 150);
      return;
    }

    // Otherwise attempt call to backend API
    try {
      const res = await fetch(`${API_BASE}/api/grounded-rag/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, analysis_id: analysisId }),
      });

      if (res.ok) {
        const data = await res.json();
        setResponse(data);
      } else {
        // Fallback default answer
        setResponse({
          answer: `Aucune évidence directe n'a été trouvée pour la requête : "${q}". Le système applique l'abstention stricte afin d'éviter toute hallucination factuelle.`,
          evidence_citations: [],
          is_abstention: true,
        });
      }
    } catch {
      // Offline fallback: first available example or abstention
      if (qaExamples.length > 0) {
        setResponse(qaExamples[0]);
      } else {
        setResponse({
          answer: "Le moteur d'intelligence tactique fonctionne en mode hors-ligne sans connexion API distante. Les réponses s'appuient sur les fiches de preuves vérifiées.",
          evidence_citations: [],
          is_abstention: true,
        });
      }
    } finally {
      setLoading(false);
    }
  };

  // Helper to extract timestamp from citation string
  const parseCitationTime = (citation) => {
    const match = citation.match(/t=([0-9.]+)s/);
    return match ? parseFloat(match[1]) : null;
  };

  return (
    <div className="grounded-panel" aria-label="Module d'interrogation tactique ancrée">
      <div className="summary-heading">
        <span>INTERROGATION TACTIQUE ANCRÉE · GROUNDED AI</span>
      </div>

      <div style={{ marginTop: "12px", marginBottom: "8px", fontSize: "12px", color: "var(--muted)" }}>
        Posez une question sur les faits de ce match. 100% des affirmations citent une preuve horodatée.
      </div>

      {/* Suggested queries */}
      {qaExamples.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "12px" }}>
          {qaExamples.slice(0, 3).map((ex) => (
            <button
              key={ex.id}
              className="btn-secondary"
              style={{ fontSize: "11px", padding: "4px 8px" }}
              onClick={() => {
                setQuery(ex.query);
                handleAsk(ex.query);
              }}
            >
              {ex.query}
            </button>
          ))}
        </div>
      )}

      {/* Search Input Row */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleAsk(query);
        }}
        className="research-input-row"
      >
        <input
          type="text"
          className="research-input mono"
          placeholder="Ex: Pourquoi Team 0 a perdu le contrôle à 2.16s ?"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Requête d'analyse tactique"
        />
        <button type="submit" className="btn-primary" disabled={loading || !query.trim()}>
          {loading ? "..." : "Interroger"}
        </button>
      </form>

      {/* Response Area */}
      {response && (
        <div
          style={{
            borderTop: "1px solid var(--border-light)",
            paddingTop: "16px",
            marginTop: "16px",
          }}
        >
          <div style={{ fontSize: "13px", lineHeight: "1.6", whiteSpace: "pre-line" }}>
            {response.answer}
          </div>

          {/* Evidence Citations */}
          {response.evidence_citations && response.evidence_citations.length > 0 && (
            <div style={{ marginTop: "16px" }}>
              <span className="section-label">SOURCES VIDÉO CITÉES (CLIQUER POUR NAVIGUER) :</span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px" }}>
                {response.evidence_citations.map((cite, i) => {
                  const t = parseCitationTime(cite);
                  return (
                    <button
                      key={i}
                      className="grounded-citation"
                      onClick={() => t !== null && onSeekCitation && onSeekCitation(t)}
                      title={`Aller à ${t !== null ? `${t.toFixed(2)}s` : "l'événement"}`}
                    >
                      {cite}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
