import { useState, useEffect } from "react";
import MinimalHeader from "./components/MinimalHeader";
import LandingPage from "./components/LandingPage";
import AnalysisWorkspace from "./components/AnalysisWorkspace";
import DemoPage from "./components/DemoPage";
import ProjectPage from "./components/ProjectPage";
import ContactPage from "./components/ContactPage";
import BetaPage from "./components/BetaPage";
import PrivacyPage from "./components/PrivacyPage";
import LegalPage from "./components/LegalPage";
import BetaTermsPage from "./components/BetaTermsPage";
import CookiesPage from "./components/CookiesPage";
import LicensesPage from "./components/LicensesPage";

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
    return (
      <LandingPage
        onEnter={() => navigate("/analyse")}
        onBeta={() => navigate("/beta")}
      />
    );
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

        {currentPath === "/beta" && <BetaPage onNavigate={navigate} />}

        {currentPath === "/legal" && <LegalPage onNavigate={navigate} />}

        {currentPath === "/privacy" && <PrivacyPage onNavigate={navigate} />}

        {currentPath === "/cookies" && <CookiesPage onNavigate={navigate} />}

        {currentPath === "/beta-terms" && <BetaTermsPage onNavigate={navigate} />}

        {currentPath === "/licenses" && <LicensesPage onNavigate={navigate} />}

        {currentPath === "/contact" && <ContactPage />}

        {currentPath !== "/analyse" &&
          currentPath !== "/demo" &&
          currentPath !== "/project" &&
          currentPath !== "/beta" &&
          currentPath !== "/legal" &&
          currentPath !== "/privacy" &&
          currentPath !== "/cookies" &&
          currentPath !== "/beta-terms" &&
          currentPath !== "/licenses" &&
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
          <span>VISION-BALLING · v0.9.0-rc2 · INSTRUMENT D&apos;ANALYSE TACTIQUE</span>
        </div>
        <nav className="footer-links" aria-label="Informations légales et conformité">
          <a
            href="/legal"
            onClick={(e) => {
              e.preventDefault();
              navigate("/legal");
            }}
            className="footer-link"
          >
            MENTIONS LÉGALES
          </a>
          <a
            href="/privacy"
            onClick={(e) => {
              e.preventDefault();
              navigate("/privacy");
            }}
            className="footer-link"
          >
            CONFIDENTIALITÉ
          </a>
          <a
            href="/cookies"
            onClick={(e) => {
              e.preventDefault();
              navigate("/cookies");
            }}
            className="footer-link"
          >
            COOKIES
          </a>
          <a
            href="/beta-terms"
            onClick={(e) => {
              e.preventDefault();
              navigate("/beta-terms");
            }}
            className="footer-link"
          >
            CONDITIONS BETA
          </a>
          <a
            href="/licenses"
            onClick={(e) => {
              e.preventDefault();
              navigate("/licenses");
            }}
            className="footer-link"
          >
            LICENCES
          </a>
          <a
            href="https://github.com/GAdrianK/football-intelligence-rag"
            target="_blank"
            rel="noreferrer"
            className="footer-link"
          >
            GITHUB
          </a>
        </nav>
      </footer>
    </div>
  );
}
