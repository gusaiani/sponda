import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { fetchSharedList, type SharedListData } from "../hooks/useSavedLists";
import "../styles/auth.css";

export function SharedListPage() {
  const [listData, setListData] = useState<SharedListData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Extract token from URL path: /shared/<token>
  const pathSegments = window.location.pathname.split("/");
  const shareToken = pathSegments[pathSegments.length - 1] || "";

  useEffect(() => {
    if (!shareToken) {
      setError("Link inválido");
      setIsLoading(false);
      return;
    }

    fetchSharedList(shareToken)
      .then((data) => setListData(data))
      .catch(() => setError("Lista não encontrada"))
      .finally(() => setIsLoading(false));
  }, [shareToken]);

  if (isLoading) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <p className="auth-success-text">Carregando…</p>
        </div>
      </div>
    );
  }

  if (error || !listData) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <Link to="/" className="auth-logo-link">
            <span className="auth-logo">SPONDA</span>
          </Link>
          <h1 className="auth-title">Lista não encontrada</h1>
          <p className="auth-success-text">
            Este link pode ter expirado ou ser inválido.
          </p>
          <p className="auth-link">
            <Link to="/">Ir para a página inicial</Link>
          </p>
        </div>
      </div>
    );
  }

  const firstTicker = listData.tickers[0];
  const remainingTickers = listData.tickers.slice(1);
  const compareUrl = `/${firstTicker}/comparar`;

  return (
    <div className="auth-container" style={{ maxWidth: "32rem" }}>
      <div className="auth-card">
        <Link to="/" className="auth-logo-link">
          <span className="auth-logo">SPONDA</span>
        </Link>
        <h1 className="auth-title">Lista compartilhada</h1>

        <div style={{ marginBottom: "1.5rem" }}>
          <p className="auth-success-text" style={{ marginBottom: "0.5rem" }}>
            <strong>{listData.shared_by}</strong> compartilhou uma
            lista com você:
          </p>
          <p className="auth-success-text" style={{ fontSize: "1rem", color: "var(--color-ink)" }}>
            "{listData.name}"
          </p>
          <p className="auth-success-text">
            {listData.tickers.length} empresas · {listData.years} {listData.years === 1 ? "ano" : "anos"} de análise
          </p>
          <p className="auth-success-text" style={{ fontSize: "0.7rem" }}>
            Empresas: {listData.tickers.join(", ")}
          </p>
        </div>

        <Link
          to={compareUrl}
          search={{ extras: remainingTickers.join(","), years: String(listData.years) }}
          className="auth-button"
          style={{ display: "block", textAlign: "center", textDecoration: "none" }}
        >
          Ver lista
        </Link>

        <p className="auth-link">
          <Link to="/">Ir para a página inicial</Link>
        </p>
      </div>
    </div>
  );
}
