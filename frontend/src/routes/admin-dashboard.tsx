import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useAuth } from "../hooks/useAuth";
import "../styles/admin.css";

interface UserStats {
  email: string;
  date_joined: string;
  last_login: string | null;
  allow_contact: boolean;
  is_superuser: boolean;
  page_views: Record<string, number>;
  lookups: Record<string, number>;
  favorites_count: number;
  saved_comparisons_count: number;
}

interface PeriodViewStats {
  total_views: number;
  unique_visitors: number;
  authenticated_views?: number;
  anonymous_views?: number;
}

interface TopPage {
  path: string;
  view_count: number;
}

interface TopTicker {
  ticker: string;
  lookup_count: number;
}

interface DashboardData {
  users: UserStats[];
  page_views: Record<string, PeriodViewStats>;
  top_pages: TopPage[];
  top_tickers: Record<string, TopTicker[]>;
  signup_stats: Record<string, number>;
  favorites_count: number;
  saved_comparisons_count: number;
}

const PERIOD_LABELS: Record<string, string> = {
  day: "24h",
  week: "7 dias",
  month: "30 dias",
  year: "1 ano",
  all_time: "Total",
  total: "Total",
};

function formatDate(dateString: string | null): string {
  if (!dateString) return "—";
  const date = new Date(dateString);
  return date.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AdminDashboardPage() {
  const { isAuthenticated, isSuperuser, isLoading: authLoading } = useAuth();
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated || !isSuperuser) {
      setIsLoading(false);
      return;
    }

    fetch("/api/auth/admin/dashboard/", { credentials: "include" })
      .then((response) => {
        if (!response.ok) throw new Error("Acesso negado");
        return response.json();
      })
      .then((data) => setDashboardData(data))
      .catch((fetchError) => setError(fetchError.message))
      .finally(() => setIsLoading(false));
  }, [isAuthenticated, isSuperuser, authLoading]);

  if (authLoading || isLoading) {
    return (
      <div className="admin-container">
        <p className="admin-loading">Carregando…</p>
      </div>
    );
  }

  if (!isAuthenticated || !isSuperuser) {
    return (
      <div className="admin-container">
        <h1 className="admin-title">Acesso restrito</h1>
        <p className="admin-text">Esta página é exclusiva para administradores.</p>
        <p className="admin-link">
          <Link to="/">Voltar para a página inicial</Link>
        </p>
      </div>
    );
  }

  if (error || !dashboardData) {
    return (
      <div className="admin-container">
        <h1 className="admin-title">Erro</h1>
        <p className="admin-text">{error || "Erro ao carregar dados"}</p>
      </div>
    );
  }

  return (
    <div className="admin-container">
      <Link to="/" className="admin-back-link">← Voltar</Link>
      <h1 className="admin-title">Painel de Administração</h1>

      {/* Overview cards */}
      <div className="admin-overview-grid">
        <OverviewCard
          label="Usuários"
          value={dashboardData.signup_stats.total}
        />
        <OverviewCard
          label="Favoritos"
          value={dashboardData.favorites_count}
        />
        <OverviewCard
          label="Comparações salvas"
          value={dashboardData.saved_comparisons_count}
        />
        <OverviewCard
          label="Views (24h)"
          value={dashboardData.page_views.day?.total_views ?? 0}
        />
        <OverviewCard
          label="Únicos (24h)"
          value={dashboardData.page_views.day?.unique_visitors ?? 0}
        />
        <OverviewCard
          label="Novos usuários (7d)"
          value={dashboardData.signup_stats.week}
        />
      </div>

      {/* Page view stats */}
      <h2 className="admin-section-title">Visualizações de Página</h2>
      <table className="admin-table">
        <thead>
          <tr>
            <th>Período</th>
            <th>Total</th>
            <th>Únicos</th>
            <th>Autenticados</th>
            <th>Anônimos</th>
          </tr>
        </thead>
        <tbody>
          {["day", "week", "month", "year", "all_time"].map((period) => {
            const stats = dashboardData.page_views[period];
            if (!stats) return null;
            return (
              <tr key={period}>
                <td>{PERIOD_LABELS[period]}</td>
                <td>{stats.total_views.toLocaleString("pt-BR")}</td>
                <td>{stats.unique_visitors.toLocaleString("pt-BR")}</td>
                <td>{stats.authenticated_views?.toLocaleString("pt-BR") ?? "—"}</td>
                <td>{stats.anonymous_views?.toLocaleString("pt-BR") ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Top pages (last 30 days) */}
      <h2 className="admin-section-title">Páginas mais visitadas (30 dias)</h2>
      <table className="admin-table">
        <thead>
          <tr>
            <th>Página</th>
            <th>Views</th>
          </tr>
        </thead>
        <tbody>
          {dashboardData.top_pages.map((page) => (
            <tr key={page.path}>
              <td className="admin-path-cell">{page.path || "/"}</td>
              <td>{page.view_count.toLocaleString("pt-BR")}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Top tickers */}
      <h2 className="admin-section-title">Tickers mais buscados</h2>
      <div className="admin-tickers-grid">
        {["day", "week", "month"].map((period) => {
          const tickers = dashboardData.top_tickers[period] || [];
          return (
            <div key={period}>
              <h3 className="admin-subsection-title">{PERIOD_LABELS[period]}</h3>
              {tickers.length === 0 ? (
                <p className="admin-text">Nenhum</p>
              ) : (
                <table className="admin-table admin-table-compact">
                  <tbody>
                    {tickers.map((ticker) => (
                      <tr key={ticker.ticker}>
                        <td>{ticker.ticker}</td>
                        <td>{ticker.lookup_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          );
        })}
      </div>

      {/* Signups over time */}
      <h2 className="admin-section-title">Cadastros</h2>
      <table className="admin-table">
        <thead>
          <tr>
            <th>Período</th>
            <th>Novos</th>
          </tr>
        </thead>
        <tbody>
          {["day", "week", "month", "year", "total"].map((period) => (
            <tr key={period}>
              <td>{PERIOD_LABELS[period]}</td>
              <td>{dashboardData.signup_stats[period]}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Users table */}
      <h2 className="admin-section-title">
        Usuários ({dashboardData.users.length})
      </h2>
      <div className="admin-table-scroll">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Cadastro</th>
              <th>Último login</th>
              <th>Contato</th>
              <th>Views 24h</th>
              <th>Views 7d</th>
              <th>Views 30d</th>
              <th>Lookups 7d</th>
              <th>Fav</th>
              <th>Comp</th>
            </tr>
          </thead>
          <tbody>
            {dashboardData.users.map((user) => (
              <tr key={user.email}>
                <td className="admin-email-cell">
                  {user.email}
                  {user.is_superuser && <span className="admin-badge">admin</span>}
                </td>
                <td>{formatDate(user.date_joined)}</td>
                <td>{formatDate(user.last_login)}</td>
                <td>{user.allow_contact ? "✓" : "—"}</td>
                <td>{user.page_views.day}</td>
                <td>{user.page_views.week}</td>
                <td>{user.page_views.month}</td>
                <td>{user.lookups.week}</td>
                <td>{user.favorites_count}</td>
                <td>{user.saved_comparisons_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function OverviewCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="admin-overview-card">
      <span className="admin-overview-value">{value.toLocaleString("pt-BR")}</span>
      <span className="admin-overview-label">{label}</span>
    </div>
  );
}
