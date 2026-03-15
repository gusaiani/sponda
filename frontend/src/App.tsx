import { Outlet } from "@tanstack/react-router";
import "./styles/global.css";

export function App() {
  return (
    <div className="app-container">
      <main className="app-main">
        <Outlet />
      </main>
      <footer className="app-footer">
        <a href="https://poe.ma" className="app-footer-logo-link">
          <img src="/poema-logo.jpg" alt="Poema" className="app-footer-logo" />
        </a>
        <p className="app-footer-text">
          Uma ferramenta da{" "}
          <a href="https://poe.ma" className="app-footer-link">
            Poema Parceria de Investimentos
          </a>
        </p>
        <a href="https://poe.ma" className="app-footer-link app-footer-performance">
          Retorno acumulado da Poema: 355,64% vs Ibovespa: 167,55% (jan/2017–dez/2025).
          <br />
          Resultados passados não garantem resultados futuros.
        </a>
        <a href="https://poe.ma" className="app-footer-link app-footer-cta">
          Procuramos parceiros com visão de longo prazo.
        </a>
      </footer>
    </div>
  );
}
