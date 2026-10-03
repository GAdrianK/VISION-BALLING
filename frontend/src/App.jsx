import { useState, useEffect } from "react";
import MinimalHeader from "./components/MinimalHeader";
import LandingPage from "./components/LandingPage";
import AnalysisWorkspace from "./components/AnalysisWorkspace";
import DemoPage from "./components/DemoPage";
import ProjectPage from "./components/ProjectPage";
import ContactPage from "./components/ContactPage";

export default function App() {
  const [currentPath, setCurrentPath] = useState(() => {
    if (typeof window !== "undefined") {
      const p = window.location.pathname;
      return p && p !== "" ? p : "/";
    }
    return "/";
  });

  const [selectedDemoSeq, setSelectedDemoSeq] = useState("SNMOT-068");

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname || "/");
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = (path, demoId = null) => {
    if (demoId) {
      setSelectedDemoSeq(demoId);
    }
    if (window.location.pathname !== path) {
      window.history.pushState(null, "", path);
    }
    setCurrentPath(path);
    window.scrollTo({ top: 0, behavior: "instant" });
  };

  // If on root landing page, show full minimal logo page
  if (currentPath === "/") {
    return <LandingPage onEnter={() => navigate("/analyse")} />;
  }

  return (
    <div className="app-shell" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Top light minimal navigation */}
      <MinimalHeader currentPath={currentPath} onNavigate={navigate} />

      {/* Main analytical container */}
      <main className="main-shell" id="main-content">
        {currentPath === "/analyse" && (
          <AnalysisWorkspace
            initialSequenceId={selectedDemoSeq}
            onResetAnalysis={() => setSelectedDemoSeq(null)}
          />
        )}

        {currentPath === "/demo" && (
          <DemoPage
            onSelectDemo={(demoId) => {
              navigate("/analyse", demoId);
            }}
          />
        )}

        {currentPath === "/project" && <ProjectPage />}

        {currentPath === "/contact" && <ContactPage />}

        {currentPath !== "/analyse" &&
          currentPath !== "/demo" &&
          currentPath !== "/project" &&
          currentPath !== "/contact" && (
            <AnalysisWorkspace
              initialSequenceId={selectedDemoSeq}
              onResetAnalysis={() => setSelectedDemoSeq(null)}
            />
          )}
      </main>

      {/* Minimal technical footer */}
      <footer className="site-footer">
        <div>
          <span>VISION-BALLING · v0.9.0-rc1 · INTELLIGENCE TACTIQUE ANCRÉE</span>
        </div>
        <div style={{ display: "flex", gap: "20px" }}>
          <a
            href="https://github.com/GAdrianK/football-intelligence-rag"
            target="_blank"
            rel="noreferrer"
            style={{ textDecoration: "underline" }}
          >
            GITHUB
          </a>
          <span>2026 · TOUS DROITS RÉSERVÉS</span>
        </div>
      </footer>
    </div>
  );
}
