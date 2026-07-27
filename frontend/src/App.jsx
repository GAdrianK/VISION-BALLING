import React, { useState, useEffect, useRef } from "react";
import Lenis from "lenis";
import { marked } from "marked";
import StadiumScene from "./components/StadiumScene";
import VideoAnalysis from "./components/VideoAnalysis";

const prompts = [
  "Qui est le meilleur buteur de la saison 2024/2025 ?",
  "Trouve un joueur similaire à Bradley Barcola",
  "Compare les milieux de Ligue 1 de 2025/2026",
];

const modes = ["Coach", "Analyste", "Supporter"];

const metrics = [
  { value: "7.8", unit: "PPDA", label: "Intensité du pressing", delta: "−1.4", tone: "lime" },
  { value: "0.91", unit: "xT", label: "Menace attendue", delta: "+24%", tone: "cyan" },
  { value: "12.4", unit: "m", label: "Compacité du bloc", delta: "Optimal", tone: "violet" },
  { value: "94.6", unit: "%", label: "Confiance du modèle", delta: "+2.1", tone: "orange" },
];

const capabilities = [
  {
    index: "01",
    title: "Questionnez le match",
    copy: "Posez une question en langage naturel. Le moteur comprend les phases, les zones et le contexte tactique.",
    tag: "NLP + RAG",
  },
  {
    index: "02",
    title: "Croisez les signaux",
    copy: "Documents, événements et métriques sont rapprochés pour produire une lecture fiable, sourcée et exploitable.",
    tag: "DATA FUSION",
  },
  {
    index: "03",
    title: "Décidez plus vite",
    copy: "Les données brutes deviennent des recommandations claires pour le staff, l'analyste ou le supporter.",
    tag: "LIVE INSIGHT",
  },
];

function ArrowUpRight() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" width="16" height="16">
      <path d="M5 15 15 5M7 5h8v8" stroke="currentColor" strokeWidth="1.7" fill="none" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" width="16" height="16">
      <path d="m17 3-7.4 14-1.5-6.1L3 7.8 17 3Z" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="m8.1 10.9 4.1-3.3" stroke="currentColor" strokeWidth="1.5" fill="none" />
    </svg>
  );
}

function BrainMark() {
  return (
    <span className="brain-mark" aria-hidden="true">
      <span />
      <span />
      <span />
      <span />
    </span>
  );
}

function RadarChart({ chartData }) {
  if (!chartData || !chartData.metrics || !chartData.players || chartData.players.length === 0) {
    return null;
  }

  const metrics = chartData.metrics;
  const players = chartData.players;
  const numMetrics = metrics.length;

  const METRIC_LABELS = {
    goals: "Buts",
    xg: "Expected Goals (xG)",
    xa: "Expected Assists (xA)",
    key_passes: "Passes Clés",
    dribbles_prog: "Dribbles Prog.",
    pressions_def: "Pressions Déf.",
  };

  const COLORS = [
    { fill: "rgba(255, 255, 255, 0.05)", stroke: "#ffffff", shadow: "rgba(255, 255, 255, 0.5)" }, // Blanc Néon (Cible)
    { fill: "rgba(199, 255, 61, 0.05)", stroke: "#c7ff3d", shadow: "rgba(199, 255, 61, 0.5)" }, // Lime Néon (Clone 1)
    { fill: "rgba(91, 231, 216, 0.05)", stroke: "#5be7d8", shadow: "rgba(91, 231, 216, 0.5)" }, // Cyan Néon (Clone 2)
    { fill: "rgba(170, 140, 255, 0.05)", stroke: "#aa8cff", shadow: "rgba(170, 140, 255, 0.5)" }  // Violet Néon
  ];

  // Calculate max values for normalization
  const maxValues = metrics.map((_, i) => {
    const vals = players.map(p => p.data[i] || 0);
    const max = Math.max(...vals);
    return max > 0 ? max : 1.0;
  });

  const CX = 135;
  const CY = 135;
  const R = 75;
  const angleStep = (Math.PI * 2) / numMetrics;

  // Concentric levels
  const levels = [0.25, 0.5, 0.75, 1.0];
  const gridPolygons = levels.map((level, levelIdx) => {
    const points = [];
    for (let i = 0; i < numMetrics; i++) {
      const angle = -Math.PI / 2 + i * angleStep;
      const x = CX + R * level * Math.cos(angle);
      const y = CY + R * level * Math.sin(angle);
      points.push(`${x},${y}`);
    }
    return (
      <polygon
        key={`level-${levelIdx}`}
        points={points.join(" ")}
        fill="none"
        stroke="rgba(255, 255, 255, 0.06)"
        strokeWidth="1"
        strokeDasharray="3,3"
      />
    );
  });

  // Spokes
  const spokes = [];
  for (let i = 0; i < numMetrics; i++) {
    const angle = -Math.PI / 2 + i * angleStep;
    const x = CX + R * Math.cos(angle);
    const y = CY + R * Math.sin(angle);
    spokes.push(
      <line
        key={`spoke-${i}`}
        x1={CX}
        y1={CY}
        x2={x}
        y2={y}
        stroke="rgba(255, 255, 255, 0.06)"
        strokeWidth="1"
      />
    );
  }

  // Player polygons and points
  const playerPolys = [];
  const playerPoints = [];

  players.forEach((player, pIdx) => {
    const color = COLORS[pIdx % COLORS.length];
    const points = [];
    player.data.forEach((val, i) => {
      const angle = -Math.PI / 2 + i * angleStep;
      const normVal = (val || 0) / maxValues[i];
      const x = CX + R * normVal * Math.cos(angle);
      const y = CY + R * normVal * Math.sin(angle);
      points.push(`${x},${y}`);

      playerPoints.push(
        <circle
          key={`pt-${pIdx}-${i}`}
          cx={x}
          cy={y}
          r="3"
          fill={color.stroke}
          style={{ filter: `drop-shadow(0 0 3px ${color.shadow})` }}
        />
      );
    });

    playerPolys.push(
      <polygon
        key={`poly-${pIdx}`}
        points={points.join(" ")}
        fill={color.fill}
        stroke={color.stroke}
        strokeWidth="2.5"
        style={{ filter: `url(#glow-${pIdx})` }}
      />
    );
  });

  // Labels
  const labels = [];
  for (let i = 0; i < numMetrics; i++) {
    const angle = -Math.PI / 2 + i * angleStep;
    const labelRadius = R + 14;
    const x = CX + labelRadius * Math.cos(angle);
    const y = CY + labelRadius * Math.sin(angle);
    const labelText = METRIC_LABELS[metrics[i]] || metrics[i];

    let textAnchor = "middle";
    if (Math.abs(Math.cos(angle)) > 0.1) {
      textAnchor = Math.cos(angle) > 0 ? "start" : "end";
    }
    let dy = "0.35em";
    if (Math.sin(angle) < -0.9) dy = "-0.1em";
    if (Math.sin(angle) > 0.9) dy = "1.0em";

    labels.push(
      <text
        key={`lbl-${i}`}
        x={x}
        y={y}
        fill="#8c9688"
        fontSize="8"
        fontWeight="600"
        textAnchor={textAnchor}
        dy={dy}
        style={{ fontFamily: "var(--font-geist-mono)" }}
      >
        {labelText}
      </text>
    );
  }

  // Extract similarity match percent
  let matchPercent = null;
  players.forEach((p) => {
    const match = p.name.match(/Match:\s*([0-9.]+)\s*%/i) || p.name.match(/([0-9.]+)\s*%/);
    if (match) {
      matchPercent = parseFloat(match[1]);
    }
  });

  return (
    <div className="radar-chart-container">
      <div className="radar-layout">
        <svg width="270" height="270" viewBox="0 0 270 270" style={{ overflow: "visible" }}>
          <defs>
            {players.map((_, pIdx) => {
              const color = COLORS[pIdx % COLORS.length];
              return (
                <filter id={`glow-${pIdx}`} key={`filter-${pIdx}`} x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="2" result="blur" />
                  <feComponentTransfer in="blur" result="boost">
                    <feFuncA type="linear" slope="1.4" />
                  </feComponentTransfer>
                  <feMerge>
                    <feMergeNode in="boost" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              );
            })}
          </defs>
          <g>{gridPolygons}{spokes}</g>
          <g>{playerPolys}{playerPoints}</g>
          <g>{labels}</g>
        </svg>

        {matchPercent !== null && (
          <div className="dna-match-card">
            <span className="dna-title">DNA MATCH</span>
            <div className="dna-circle-wrapper">
              <svg width="100" height="100" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="38" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="5" />
                <circle
                  cx="50"
                  cy="50"
                  r="38"
                  fill="none"
                  stroke="url(#dna-grad)"
                  strokeWidth="5"
                  strokeDasharray={2 * Math.PI * 38}
                  strokeDashoffset={(2 * Math.PI * 38) * (1 - matchPercent / 100)}
                  strokeLinecap="round"
                  transform="rotate(-90 50 50)"
                  style={{ transition: "stroke-dashoffset 1s ease-out", filter: "drop-shadow(0 0 5px var(--cyan))" }}
                />
                <defs>
                  <linearGradient id="dna-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="var(--cyan)" />
                    <stop offset="100%" stopColor="var(--lime)" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="dna-circle-text">
                <strong style={{ fontSize: "15px" }}>{matchPercent.toFixed(1)}%</strong>
                <span style={{ fontSize: "7px" }}>SIMILARITÉ</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="chart-legend">
        {players.map((player, pIdx) => {
          const color = COLORS[pIdx % COLORS.length];
          return (
            <div className="legend-item" key={player.name}>
              <span className="legend-color" style={{ backgroundColor: color.stroke, boxShadow: `0 0 8px ${color.shadow}` }} />
              <span>{player.name}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function App() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mode, setMode] = useState("Analyste");
  const [season, setSeason] = useState("season_2025_2026_summary");
  const [activeTab, setActiveTab] = useState("map");
  const [chartData, setChartData] = useState(null);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [copied, setCopied] = useState(false);
  const [clock, setClock] = useState("LIVE");
  const [fps, setFps] = useState(144);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      meta: "IA FOOT • RAG LOCAL",
      text: "Prêt. Interrogez le match, une phase de jeu ou votre base de connaissances tactiques.",
      isHtml: false,
    },
  ]);
  const messageListRef = useRef(null);

  // Initialize Lenis scroll engine
  useEffect(() => {
    const mobileUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    const smallScreen = window.innerWidth < 768;
    const isMobileDevice = mobileUA || smallScreen;

    let lenis = null;
    let rafId;
    const container = document.getElementById("edra-root-canvas");

    if (!isMobileDevice && container) {
      lenis = new Lenis({
        wrapper: container,
        duration: 1.2,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        smoothWheel: true,
        wheelMultiplier: 1.0,
        touchMultiplier: 1.5,
      });

      const raf = (time) => {
        lenis?.raf(time);
        rafId = requestAnimationFrame(raf);
      };
      rafId = requestAnimationFrame(raf);
    }

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      if (lenis) lenis.destroy();
    };
  }, []);

  // Real-time FPS counter
  useEffect(() => {
    let last = performance.now();
    let count = 0;
    let rafId;
    const loop = () => {
      count++;
      const now = performance.now();
      if (now - last >= 1000) {
        setFps(Math.round(count * 1000 / (now - last)));
        count = 0;
        last = now;
      }
      rafId = requestAnimationFrame(loop);
    };
    rafId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafId);
  }, []);

  // Update clock
  useEffect(() => {
    const update = () => setClock(new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    update();
    const id = window.setInterval(update, 1000);
    return () => window.clearInterval(id);
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    const list = messageListRef.current;
    if (list) list.scrollTo({ top: list.scrollHeight, behavior: "smooth" });
  }, [messages, thinking]);

  const submitPrompt = async (value) => {
    const query = value.trim();
    if (!query || thinking) return;
    setInput("");

    // Add user message
    setMessages((current) => [...current, { role: "user", meta: `MODE ${mode.toUpperCase()}`, text: query }]);
    setThinking(true);

    // Prepare assistant message slot
    setMessages((current) => [
      ...current,
      {
        role: "assistant",
        meta: `ANALYSE EN COURS`,
        text: "",
        isHtml: false,
      },
    ]);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: query, season: season }),
      });

      if (!response.ok) {
        throw new Error(`Erreur serveur: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let fullText = "";

      while (true) {
        const { value: chunkVal, done } = await reader.read();
        if (done) break;

        const chunkText = decoder.decode(chunkVal, { stream: true });
        fullText += chunkText;

        // Clean display text (remove the JSON block)
        let displayText = fullText;
        const jsonMarkerIndex = fullText.indexOf("```json");
        if (jsonMarkerIndex !== -1) {
          displayText = fullText.substring(0, jsonMarkerIndex).trim();
        }

        // Render markdown in real-time
        const html = marked.parse(displayText);

        // Update last message
        setMessages((current) => {
          const updated = [...current];
          if (updated.length > 0) {
            updated[updated.length - 1] = {
              role: "assistant",
              meta: `ANALYSE COMPLETE • RAG LOCAL`,
              text: html,
              rawText: displayText, // Keep raw text for copy
              isHtml: true,
            };
          }
          return updated;
        });
      }

      // Check if there is a JSON block for the radar chart
      const jsonMarkerIndex = fullText.indexOf("```json");
      if (jsonMarkerIndex !== -1) {
        const jsonEndIndex = fullText.indexOf("```", jsonMarkerIndex + 7);
        if (jsonEndIndex !== -1) {
          const jsonStr = fullText.substring(jsonMarkerIndex + 7, jsonEndIndex).trim();
          try {
            const parsedChart = JSON.parse(jsonStr);
            setChartData(parsedChart);
            setActiveTab("radar"); // Auto-switch to radar tab to wOw the user!
          } catch (e) {
            console.error("Erreur lecture JSON du graphique:", e);
          }
        }
      }
    } catch (err) {
      console.error(err);
      setMessages((current) => {
        const updated = [...current];
        if (updated.length > 0) {
          updated[updated.length - 1] = {
            role: "assistant",
            meta: "ERREUR BACKEND",
            text: `Désolé, impossible de contacter le serveur tactique local (vérifiez que le backend FastAPI tourne sur le port 8000). Détail : ${err.message}`,
            isHtml: false,
          };
        }
        return updated;
      });
    } finally {
      setThinking(false);
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    submitPrompt(input);
  };

  const copyLatest = async () => {
    const latest = [...messages].reverse().find((message) => message.role === "assistant");
    if (!latest) return;
    const textToCopy = latest.rawText || latest.text;
    await navigator.clipboard?.writeText(textToCopy);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div id="edra-root-canvas">
      <main className="site-shell">
        {/* Background 3D GLSL Shaders */}
        <StadiumScene />

        {/* Ambient grids & noise over shader background */}
        <div className="stadium-scene" aria-hidden="true">
          <div className="stadium-grid" />
          <div className="noise" />
        </div>

        <header className="topbar">
          <a className="brand" href="#top" aria-label="IA Foot — accueil" onClick={(e) => {
            e.preventDefault();
            document.getElementById("edra-root-canvas")?.scrollTo({ top: 0, behavior: "smooth" });
          }}>
            <BrainMark />
            <span>IA FOOT</span>
            <em>ALPHA</em>
          </a>

          <nav className={mobileOpen ? "nav-links is-open" : "nav-links"} aria-label="Navigation principale">
            <a href="#assistant" onClick={(e) => {
              e.preventDefault();
              setMobileOpen(false);
              document.getElementById("assistant")?.scrollIntoView({ behavior: "smooth" });
            }}>Assistant</a>
            <a href="#intelligence" onClick={(e) => {
              e.preventDefault();
              setMobileOpen(false);
              document.getElementById("intelligence")?.scrollIntoView({ behavior: "smooth" });
            }}>Intelligence</a>
            <a href="#methode" onClick={(e) => {
              e.preventDefault();
              setMobileOpen(false);
              document.getElementById("methode")?.scrollIntoView({ behavior: "smooth" });
            }}>Méthode</a>
          </nav>

          <div className="header-actions">
            <div className="live-pill"><i /> RAG LOCAL &nbsp;·&nbsp; {fps} FPS</div>
            <a className="header-cta" href="#assistant" onClick={(e) => {
              e.preventDefault();
              document.getElementById("assistant")?.scrollIntoView({ behavior: "smooth" });
            }}>Lancer l’analyse <ArrowUpRight /></a>
            <button
              className={mobileOpen ? "menu-button is-open" : "menu-button"}
              type="button"
              aria-label="Ouvrir le menu"
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen((value) => !value)}
            ><span /><span /></button>
          </div>
        </header>

        <section className="hero" id="top">
          <div className="hero-copy">
            <div className="hero-kicker reveal-one"><i /> Football intelligence system <span>v0.9</span></div>
            <h1 className="reveal-two">Le match parle.<br /><span>Nous le décodons.</span></h1>
            <p className="hero-description reveal-three">
              Un assistant IA tactique qui transforme vos données, rapports et événements de match en décisions de jeu instantanées.
            </p>
            <div className="hero-actions reveal-four">
              <a className="primary-button" href="#assistant" onClick={(e) => {
                e.preventDefault();
                document.getElementById("assistant")?.scrollIntoView({ behavior: "smooth" });
              }}>Tester l’assistant <ArrowUpRight /></a>
              <a className="text-button" href="#intelligence" onClick={(e) => {
                e.preventDefault();
                document.getElementById("intelligence")?.scrollIntoView({ behavior: "smooth" });
              }}><span className="play">▶</span> Voir comment ça fonctionne</a>
            </div>
            <div className="trust-row reveal-four">
              <div><strong>49</strong><span>documents indexés</span></div>
              <div><strong>12ms</strong><span>temps de recherche</span></div>
              <div><strong>100%</strong><span>traitement local</span></div>
            </div>
          </div>

          <div className="hero-visual reveal-three">
            <div className="orbital-ring ring-one" />
            <div className="orbital-ring ring-two" />
            <div className="visual-label label-top"><span>01</span> Retrieval engine</div>
            <div className="visual-label label-bottom"><span>02</span> Tactical reasoning</div>
            <div className="intelligence-orb">
              <div className="orb-core"><BrainMark /></div>
              <div className="orb-glow" />
            </div>
            <div className="floating-data data-a"><span>xT FLOW</span><strong>0.91</strong><i>+24%</i></div>
            <div className="floating-data data-b"><span>CONFIDENCE</span><strong>94.6%</strong><i>VERIFIED</i></div>
          </div>

          <div className="scroll-cue"><span>Scroll to decode</span><i /></div>
        </section>

        <section className="assistant-section section-wrap" id="assistant">
          <div className="section-heading">
            <div>
              <span className="section-index">01 / ASSISTANT</span>
              <h2>De la question<br />à <em>l’avantage.</em></h2>
            </div>
            <p>Une interface conçue pour aller droit au signal. Pas de tableaux illisibles : une réponse claire, contextualisée et sourcée.</p>
          </div>

          <div className="assistant-console glass-panel">
            <div className="console-topbar">
              <div className="console-title"><BrainMark /><span>IA FOOT / MATCH ROOM</span></div>
              <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                <select 
                  value={season} 
                  onChange={(e) => setSeason(e.target.value)} 
                  className="season-select"
                  aria-label="Choisir la saison"
                >
                  <option value="season_2025_2026_summary">Saison 2025/2026</option>
                  <option value="season_2024_2025_summary">Saison 2024/2025</option>
                </select>
                <div className="mode-switch" aria-label="Choisir le mode d’analyse">
                  {modes.map((item) => (
                    <button key={item} type="button" onClick={() => setMode(item)} className={mode === item ? "active" : ""}>{item}</button>
                  ))}
                </div>
              </div>
              <div className="console-status"><i /> EN LIGNE <span>{clock}</span></div>
            </div>

            <div className="console-grid">
              <div className="chat-panel">
                <div className="chat-head">
                  <div><span>SESSION ACTIVE</span><strong>Analyse tactique #024</strong></div>
                  <button type="button" onClick={copyLatest}>{copied ? "Copié ✓" : "Copier l’analyse"}</button>
                </div>
                <div className="message-list" aria-live="polite" ref={messageListRef}>
                  {messages.map((message, index) => (
                    <article className={`message ${message.role}`} key={`${message.role}-${index}`}>
                      <div className="avatar">{message.role === "assistant" ? <BrainMark /> : "User"}</div>
                      <div>
                        <span>{message.meta}</span>
                        {message.isHtml ? (
                          <div className="message-content-html" dangerouslySetInnerHTML={{ __html: message.text }} />
                        ) : (
                          <p>{message.text}</p>
                        )}
                      </div>
                    </article>
                  ))}
                  {thinking && (
                    <article className="message assistant thinking">
                      <div className="avatar"><BrainMark /></div>
                      <div><span>ANALYSE EN COURS</span><p><i /><i /><i /></p></div>
                    </article>
                  )}
                </div>
                <div className="prompt-chips">
                  {prompts.map((prompt) => <button type="button" key={prompt} onClick={() => submitPrompt(prompt)}>{prompt}</button>)}
                </div>
                <form className="prompt-bar" onSubmit={handleSubmit}>
                  <span className="prompt-spark"><BrainMark /></span>
                  <input
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    placeholder="Interrogez le match, les données ou vos documents…"
                    aria-label="Votre question tactique"
                  />
                  <span className="key-hint">↵</span>
                  <button type="submit" aria-label="Envoyer la question" disabled={thinking || !input.trim()}><SendIcon /></button>
                </form>
                <p className="console-note">Les réponses sont générées à partir de votre base de données et connaissances locales.</p>
              </div>

              <div className="pitch-shell">
                <div className="pitch-toolbar">
                  <div className="pitch-tabs">
                    <button 
                      type="button" 
                      onClick={() => setActiveTab("map")} 
                      className={activeTab === "map" ? "active" : ""}
                    >
                      MAP TACTIQUE
                    </button>
                    <button 
                      type="button" 
                      onClick={() => setActiveTab("radar")} 
                      disabled={!chartData}
                      className={activeTab === "radar" ? "active" : ""}
                      style={{ opacity: !chartData ? 0.35 : 1 }}
                    >
                      RADAR DNA
                    </button>
                  </div>
                  {activeTab === "map" ? (
                    <div className="legend"><i /> Possession haute</div>
                  ) : (
                    <div className="legend"><i style={{ backgroundColor: "var(--cyan)", boxShadow: "0 0 8px var(--cyan)" }} /> Comparatif IA</div>
                  )}
                </div>

                {activeTab === "map" ? (
                  <div className="pitch" aria-label="Carte tactique du match">
                    <div className="pitch-line center-line" />
                    <div className="center-circle" />
                    <div className="box box-left" />
                    <div className="box box-right" />
                    <div className="goal goal-left" />
                    <div className="goal goal-right" />
                    <div className="heat heat-a" />
                    <div className="heat heat-b" />
                    <div className="run-line run-one" />
                    <div className="run-line run-two" />
                    {["p1", "p2", "p3", "p4", "p5", "p6"].map((player) => (
                      <span className={`player ${player}`} key={player}><i /></span>
                    ))}
                  </div>
                ) : (
                  <RadarChart chartData={chartData} />
                )}

                <div className="pitch-bottom">
                  {activeTab === "map" ? (
                    <>
                      <div><span>Phase détectée</span><strong>Pressing haut</strong></div>
                      <div><span>Fenêtre</span><strong>60’—75’</strong></div>
                      <div><span>Confiance</span><strong>94.6%</strong></div>
                    </>
                  ) : (
                    <>
                      <div><span>Moteur</span><strong>SQL + LLM</strong></div>
                      <div><span>Saison</span><strong>{season.replace("season_", "").replace("_summary", "").replace("_", "/")}</strong></div>
                      <div><span>Métrique clé</span><strong>ADN Tactique</strong></div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="video-section section-wrap" id="video-analysis">
          <div className="section-heading compact">
            <div>
              <span className="section-index">02 / VIDÉO</span>
              <h2>De la vidéo brute<br />aux <em>premiers signaux.</em></h2>
            </div>
            <p>Ingestion, validation, détection générique, vidéo annotée et JSON horodaté.</p>
          </div>
          <VideoAnalysis />
        </section>

        <section className="intelligence-section section-wrap" id="intelligence">
          <div className="section-heading compact">
            <div>
              <span className="section-index">03 / INTELLIGENCE</span>
              <h2>Voir ce que les autres<br /><em>ne voient pas.</em></h2>
            </div>
            <div className="section-badge"><i /> LIVE MATCH MODEL</div>
          </div>

          <div className="metric-grid">
            {metrics.map((metric, index) => (
              <article className={`metric-card glass-panel tone-${metric.tone}`} key={metric.label}>
                <div className="metric-top"><span>0{index + 1}</span><i /></div>
                <p>{metric.label}</p>
                <strong>{metric.value}<small>{metric.unit}</small></strong>
                <div className="metric-bottom"><span>{metric.delta}</span><div className="sparkline"><i /><i /><i /><i /><i /><i /></div></div>
              </article>
            ))}
          </div>

          <div className="insight-banner glass-panel">
            <div className="insight-visual"><span>60’</span><i /><i /><i /><i /><i /></div>
            <div className="insight-copy">
              <span>INSIGHT DÉTECTÉ • MINUTE 60</span>
              <h3>Le pressing adverse ouvre une fenêtre de <em>14 mètres</em> dans le demi-espace gauche.</h3>
              <p>Signal croisé sur 4 sources tactiques — confiance élevée.</p>
            </div>
            <a href="#assistant" className="icon-button" aria-label="Analyser cet insight" onClick={(e) => {
              e.preventDefault();
              document.getElementById("assistant")?.scrollIntoView({ behavior: "smooth" });
            }}><ArrowUpRight /></a>
          </div>
        </section>

        <section className="method-section section-wrap" id="methode">
          <div className="section-heading compact">
            <div>
              <span className="section-index">04 / MÉTHODE</span>
              <h2>Une chaîne de décision.<br /><em>Pas une boîte noire.</em></h2>
            </div>
            <p>Chaque réponse conserve une logique simple : comprendre, vérifier, expliquer.</p>
          </div>

          <div className="capability-grid">
            {capabilities.map((item) => (
              <article className="capability-card" key={item.index}>
                <span className="capability-index">{item.index}</span>
                <div className="capability-icon"><BrainMark /></div>
                <h3>{item.title}</h3>
                <p>{item.copy}</p>
                <span className="capability-tag">{item.tag}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="closing-section section-wrap">
          <div className="closing-glow" />
          <span className="section-index">READY FOR KICK-OFF</span>
          <h2>Votre lecture du jeu<br />commence <em>maintenant.</em></h2>
          <p>Interrogez vos données. Comprenez le match. Prenez l’avantage.</p>
          <a className="primary-button large" href="#assistant" onClick={(e) => {
            e.preventDefault();
            document.getElementById("assistant")?.scrollIntoView({ behavior: "smooth" });
          }}>Lancer une analyse <ArrowUpRight /></a>
        </section>

        <footer className="footer section-wrap">
          <a className="brand" href="#top" onClick={(e) => {
            e.preventDefault();
            document.getElementById("edra-root-canvas")?.scrollTo({ top: 0, behavior: "smooth" });
          }}><BrainMark /><span>IA FOOT</span><em>ALPHA</em></a>
          <p>Intelligence tactique augmentée.</p>
          <div><span>RAG ENGINE ONLINE</span><span>© 2026</span></div>
        </footer>
      </main>
    </div>
  );
}
