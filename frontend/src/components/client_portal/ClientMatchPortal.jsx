import { useState, useEffect, useCallback } from "react";
import { API_BASE_URL } from "../../config/api";
import ClientUnlockScreen from "./ClientUnlockScreen";
import ClientVideoPlayer from "./ClientVideoPlayer";
import HonestMetricsPanel from "./HonestMetricsPanel";

export default function ClientMatchPortal({ analysisId }) {
  const [sessionData, setSessionData] = useState(null);
  const [job, setJob] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [summary, setSummary] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("video"); // "video" | "metrics" | "assistant" | "report"

  // Assistant Chat State
  const [chatQuery, setChatQuery] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatAnswers, setChatAnswers] = useState([]);

  // Check if session cookie already works on mount
  useEffect(() => {
    let isMounted = true;
    fetch(`${API_BASE_URL}/api/video-analysis/${analysisId}`, {
      credentials: "include",
    })
      .then((res) => {
        if (res.ok) {
          return res.json();
        }
        return null;
      })
      .then((data) => {
        if (isMounted && data) {
          setJob(data);
          setSessionData({ active: true });
        }
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, [analysisId]);

  const loadMatchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Load job
      const jobRes = await fetch(`${API_BASE_URL}/api/video-analysis/${analysisId}`, {
        credentials: "include",
      });
      if (!jobRes.ok) {
        throw new Error("Impossible de charger les métadonnées de l'analyse.");
      }
      const jobData = await jobRes.json();
      setJob(jobData);

      // 2. Load timeline
      try {
        const tlRes = await fetch(`${API_BASE_URL}/api/video-analysis/${analysisId}/timeline`, {
          credentials: "include",
        });
        if (tlRes.ok) {
          const tlData = await tlRes.json();
          setTimeline(Array.isArray(tlData) ? tlData : []);
        }
      } catch {
        setTimeline([]);
      }

      // 3. Load summary
      try {
        const sumRes = await fetch(`${API_BASE_URL}/api/video-analysis/${analysisId}/summary`, {
          credentials: "include",
        });
        if (sumRes.ok) {
          const sumData = await sumRes.json();
          setSummary(sumData);
        }
      } catch {
        setSummary(null);
      }

      // 4. Load report
      try {
        const repRes = await fetch(`${API_BASE_URL}/api/video-analysis/${analysisId}/report`, {
          credentials: "include",
        });
        if (repRes.ok) {
          const repData = await repRes.json();
          setReport(repData);
        }
      } catch {
        setReport(null);
      }
    } catch (err) {
      setError(err.message || "Erreur de chargement des données.");
    } finally {
      setLoading(false);
    }
  }, [analysisId]);

  const handleUnlocked = (data) => {
    setSessionData(data);
    loadMatchData();
  };

  const handleSendChat = async (e) => {
    if (e) e.preventDefault();
    const q = chatQuery.trim();
    if (!q || chatLoading) return;

    setChatLoading(true);
    const newEntry = { query: q, loading: true, answer: null };
    setChatAnswers((prev) => [newEntry, ...prev]);
    setChatQuery("");

    try {
      const headers = {
        "Content-Type": "application/json",
      };
      if (sessionData?.csrf_token) {
        headers["X-CSRF-Token"] = sessionData.csrf_token;
      }

      const res = await fetch(`${API_BASE_URL}/api/video-analysis/${analysisId}/query`, {
        method: "POST",
        headers,
        credentials: "include",
        body: JSON.stringify({
          query: q,
          max_evidence_events: 8,
          include_knowledge_base: true,
        }),
      });

      if (!res.ok) {
        throw new Error(`Erreur assistant (${res.status})`);
      }

      const answerData = await res.json();
      setChatAnswers((prev) => [
        { query: q, loading: false, answer: answerData },
        ...prev.slice(1),
      ]);
    } catch (err) {
      setChatAnswers((prev) => [
        {
          query: q,
          loading: false,
          answer: {
            answer: `Erreur : ${err.message}. Le système s'abstient pour préserver la rigueur factuelle.`,
            is_abstention: true,
            limitations: ["Échec de communication avec le résolveur de preuves."],
          },
        },
        ...prev.slice(1),
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  if (!sessionData) {
    return <ClientUnlockScreen analysisId={analysisId} onUnlocked={handleUnlocked} />;
  }

  if (loading && !job) {
    return (
      <div style={{ maxWidth: "1100px", margin: "60px auto", padding: "20px", textAlign: "center", color: "#666" }}>
        Chargement de l&apos;espace d&apos;analyse...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ maxWidth: "600px", margin: "60px auto", padding: "24px", background: "#FFF5F5", border: "1px solid #FFCCCC", color: "#990000" }}>
        <h3>Accès indisponible</h3>
        <p>{error}</p>
        <button
          onClick={() => {
            setSessionData(null);
          }}
          style={{ padding: "8px 16px", background: "#111", color: "#fff", border: "none", cursor: "pointer" }}
        >
          Déverrouiller à nouveau
        </button>
      </div>
    );
  }

  return (
    <div
      className="client-match-portal"
      style={{
        maxWidth: "1280px",
        margin: "0 auto",
        padding: "32px 24px 60px 24px",
        fontFamily: "'Inter', -apple-system, sans-serif",
      }}
    >
      {/* Top Match Header */}
      <div
        style={{
          borderBottom: "1px solid #E5E5E0",
          paddingBottom: "16px",
          marginBottom: "24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
        }}
      >
        <div>
          <div
            style={{
              fontFamily: "monospace",
              fontSize: "11px",
              letterSpacing: "0.08em",
              color: "#666666",
              textTransform: "uppercase",
              marginBottom: "6px",
            }}
          >
            ESPACE PRIVÉ CERTIFIÉ · {job?.match_id || analysisId}
          </div>
          <h1
            style={{
              fontSize: "22px",
              fontWeight: "600",
              letterSpacing: "-0.02em",
              margin: 0,
              color: "#111111",
            }}
          >
            Analyse Tactique & Évidences de Match
          </h1>
        </div>

        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <span
            style={{
              display: "inline-block",
              padding: "4px 8px",
              background: "#E8F5E9",
              color: "#2E7D32",
              fontSize: "11px",
              fontFamily: "monospace",
              borderRadius: "2px",
            }}
          >
            ● SESSION ACTIVE
          </span>
          <span style={{ fontSize: "12px", color: "#888", fontFamily: "monospace" }}>
            Réf: {analysisId}
          </span>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          borderBottom: "1px solid #E5E5E0",
          marginBottom: "24px",
        }}
      >
        {[
          { id: "video", label: "Vidéo & Chronologie" },
          { id: "metrics", label: "Métriques Physiques" },
          { id: "assistant", label: "Assistant Tactique Ancré" },
          { id: "report", label: "Rapport Tactique" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "10px 18px",
              fontSize: "13px",
              fontWeight: activeTab === tab.id ? "600" : "400",
              color: activeTab === tab.id ? "#111111" : "#666666",
              background: activeTab === tab.id ? "#FFFFFF" : "transparent",
              border: "1px solid",
              borderColor: activeTab === tab.id ? "#E5E5E0 #E5E5E0 #FFFFFF #E5E5E0" : "transparent",
              marginBottom: activeTab === tab.id ? "-1px" : "0",
              borderRadius: "2px 2px 0 0",
              cursor: "pointer",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB 1: Video & Timeline */}
      {activeTab === "video" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: "24px" }}>
          <div>
            <ClientVideoPlayer analysisId={analysisId} />
            <div style={{ marginTop: "16px" }}>
              <HonestMetricsPanel job={job} summary={summary} />
            </div>
          </div>

          <div
            style={{
              background: "#FFFFFF",
              border: "1px solid #E5E5E0",
              borderRadius: "2px",
              padding: "20px",
              maxHeight: "720px",
              overflowY: "auto",
            }}
          >
            <div
              style={{
                fontFamily: "monospace",
                fontSize: "11px",
                letterSpacing: "0.06em",
                color: "#666666",
                textTransform: "uppercase",
                marginBottom: "12px",
                borderBottom: "1px solid #EAEAEA",
                paddingBottom: "8px",
              }}
            >
              Chronologie des Événements ({timeline.length})
            </div>

            {timeline.length === 0 ? (
              <div style={{ fontSize: "12px", color: "#888", fontStyle: "italic" }}>
                Aucun événement ordonné disponible.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {timeline.map((evt, idx) => (
                  <div
                    key={evt.event_id || idx}
                    style={{
                      padding: "10px 12px",
                      background: "#FAFAF8",
                      border: "1px solid #EAEAEA",
                      borderRadius: "2px",
                      fontSize: "12px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                      <span style={{ fontFamily: "monospace", fontWeight: "600", color: "#111" }}>
                        {evt.start_timestamp != null ? `${Number(evt.start_timestamp).toFixed(1)}s` : ""}
                        {evt.end_timestamp != null && evt.end_timestamp !== evt.start_timestamp
                          ? ` – ${Number(evt.end_timestamp).toFixed(1)}s`
                          : ""}
                      </span>
                      <span
                        style={{
                          fontSize: "10px",
                          fontFamily: "monospace",
                          color: "#666",
                          background: "#EBEBEB",
                          padding: "2px 6px",
                          borderRadius: "2px",
                        }}
                      >
                        {evt.event_family || "ÉVÉNEMENT"}
                      </span>
                    </div>
                    <div style={{ color: "#333", lineHeight: "1.4" }}>
                      {evt.summary_text || evt.description || "Événement tactique mesuré"}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Honest Metrics */}
      {activeTab === "metrics" && (
        <div>
          <HonestMetricsPanel job={job} summary={summary} />
        </div>
      )}

      {/* TAB 3: Grounded Tactical Assistant */}
      {activeTab === "assistant" && (
        <div style={{ maxWidth: "880px", margin: "0 auto" }}>
          <div
            style={{
              padding: "16px",
              background: "#F7F7F5",
              border: "1px solid #E5E5E0",
              borderRadius: "2px",
              marginBottom: "24px",
              fontSize: "13px",
              color: "#333",
              lineHeight: "1.6",
            }}
          >
            <strong>Assistant Tactique Ancré (Chapter 9) :</strong> Posez vos questions sur la rencontre.
            Le modèle est <strong>strictement contraint</strong> aux observations physiques mesurées dans votre match.
            Il s&apos;abstient formellement de spéculer sur le score, les statistiques non mesurées (xG) ou des identités de joueurs absentes.
          </div>

          <form onSubmit={handleSendChat} style={{ display: "flex", gap: "10px", marginBottom: "24px" }}>
            <input
              type="text"
              value={chatQuery}
              onChange={(e) => setChatQuery(e.target.value)}
              placeholder="Ex: Comment s'est organisée la pression défensive lors des transitions ?"
              disabled={chatLoading}
              style={{
                flex: 1,
                padding: "12px 16px",
                fontSize: "13px",
                border: "1px solid #D4D4CE",
                borderRadius: "2px",
                outline: "none",
              }}
            />
            <button
              type="submit"
              disabled={chatLoading || !chatQuery.trim()}
              style={{
                padding: "12px 24px",
                background: "#111",
                color: "#fff",
                border: "none",
                borderRadius: "2px",
                fontSize: "13px",
                fontWeight: "500",
                cursor: chatLoading ? "wait" : "pointer",
              }}
            >
              {chatLoading ? "Analyse..." : "Interroger →"}
            </button>
          </form>

          {/* Chat Stream */}
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {chatAnswers.map((entry, idx) => (
              <div
                key={idx}
                style={{
                  background: "#FFFFFF",
                  border: "1px solid #E5E5E0",
                  borderRadius: "2px",
                  padding: "20px 24px",
                }}
              >
                <div style={{ fontSize: "13px", fontWeight: "600", color: "#111", marginBottom: "12px" }}>
                  Q : {entry.query}
                </div>

                {entry.loading ? (
                  <div style={{ color: "#888", fontSize: "13px", fontStyle: "italic" }}>
                    Interrogation des évidences tactiques validées...
                  </div>
                ) : (
                  <div>
                    {/* Render the 4 Structured Blocks */}
                    {entry.answer?.observations_du_match?.length > 0 && (
                      <div style={{ marginBottom: "16px" }}>
                        <div style={{ fontSize: "12px", fontWeight: "600", color: "#111", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
                          1. Observations du match (faits mesurés)
                        </div>
                        <ul style={{ margin: "0 0 10px 0", paddingLeft: "20px", fontSize: "13px", color: "#333", lineHeight: "1.5" }}>
                          {entry.answer.observations_du_match.map((obs, oIdx) => (
                            <li key={oIdx}>{obs}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {entry.answer?.interpretations_tactiques?.length > 0 && (
                      <div style={{ marginBottom: "16px" }}>
                        <div style={{ fontSize: "12px", fontWeight: "600", color: "#111", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
                          2. Interprétations tactiques (inférences & candidats)
                        </div>
                        <ul style={{ margin: "0 0 10px 0", paddingLeft: "20px", fontSize: "13px", color: "#444", lineHeight: "1.5" }}>
                          {entry.answer.interpretations_tactiques.map((intp, iIdx) => (
                            <li key={iIdx}>{intp}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {entry.answer?.connaissances_generales?.length > 0 && (
                      <div style={{ marginBottom: "16px" }}>
                        <div style={{ fontSize: "12px", fontWeight: "600", color: "#666", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
                          3. Connaissances générales (théorie du football)
                        </div>
                        <ul style={{ margin: "0 0 10px 0", paddingLeft: "20px", fontSize: "12px", color: "#666", lineHeight: "1.5" }}>
                          {entry.answer.connaissances_generales.map((cg, cIdx) => (
                            <li key={cIdx}>{cg}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Fallback to full markdown text if blocks are empty */}
                    {!entry.answer?.observations_du_match?.length && (
                      <div style={{ fontSize: "13px", lineHeight: "1.6", color: "#222", whiteSpace: "pre-wrap", marginBottom: "12px" }}>
                        {entry.answer?.answer}
                      </div>
                    )}

                    {/* Section 4: Limites */}
                    {entry.answer?.limitations?.length > 0 && (
                      <div style={{ borderTop: "1px solid #F0F0EE", paddingTop: "10px", marginTop: "12px", fontSize: "11px", color: "#888" }}>
                        <strong>Limites & Abstentions :</strong> {entry.answer.limitations.join(" · ")}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: Tactical Report */}
      {activeTab === "report" && (
        <div
          style={{
            maxWidth: "880px",
            margin: "0 auto",
            background: "#FFFFFF",
            border: "1px solid #E5E5E0",
            padding: "40px",
            borderRadius: "2px",
          }}
        >
          {report?.markdown_report ? (
            <div style={{ whiteSpace: "pre-wrap", fontSize: "13px", lineHeight: "1.7", color: "#222" }}>
              {report.markdown_report}
            </div>
          ) : (
            <div style={{ color: "#888", fontStyle: "italic", textAlign: "center" }}>
              Rapport d&apos;analyse non disponible pour ce match.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
