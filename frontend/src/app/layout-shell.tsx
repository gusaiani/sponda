"use client";

import { AuthHeader } from "../components/AuthHeader";
import { FeedbackButton } from "../components/FeedbackButton";
import { usePageTracking } from "../hooks/usePageTracking";
import { POEMA_PERFORMANCE_LINE, POEMA_DISCLAIMER, POEMA_CTA } from "../utils/branding";

export function LayoutShell({ children }: { children: React.ReactNode }) {
  usePageTracking();

  return (
    <div className="app-container">
      <AuthHeader />
      <FeedbackButton />
      <main className="app-main">
        {children}
      </main>
      <footer className="app-footer">
        <a href="https://poe.ma" target="_blank" rel="noopener noreferrer" className="app-footer-logo-link">
          <img src="/poema-logo.jpg" alt="Poema" className="app-footer-logo" />
        </a>
        <p className="app-footer-text">
          Uma ferramenta da{" "}
          <a href="https://poe.ma" target="_blank" rel="noopener noreferrer" className="app-footer-link">
            Poema Parceria de Investimentos
          </a>
        </p>
        <a href="https://poe.ma" target="_blank" rel="noopener noreferrer" className="app-footer-link app-footer-performance">
          {POEMA_PERFORMANCE_LINE}
          <br />
          {POEMA_DISCLAIMER}
        </a>
        <a href="https://poe.ma" target="_blank" rel="noopener noreferrer" className="app-footer-link app-footer-cta">
          {POEMA_CTA}
        </a>
      </footer>
    </div>
  );
}
