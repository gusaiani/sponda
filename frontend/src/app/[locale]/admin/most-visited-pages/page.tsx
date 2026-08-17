"use client";

import { useQuery } from "@tanstack/react-query";

import Link from "next/link";
import { useAuth } from "../../../../hooks/useAuth";
import { useTranslation } from "../../../../i18n";
import { formatNumber } from "../../../../utils/format";

interface TopPage {
  path: string;
  view_count: number;
}

interface TopPagesResponse {
  pages: TopPage[];
}

export default function MostVisitedPagesPage() {
  const { isAuthenticated, isSuperuser, isLoading: authLoading } = useAuth();
  const { locale } = useTranslation();
  // react-query rather than fetch-in-an-effect: loading, error and data stop
  // being three pieces of state kept in sync by hand, and `enabled` expresses
  // "only admins fetch this" without an early return that has to remember to
  // clear the loading flag.
  const {
    data: pages = null,
    isLoading,
    error,
  } = useQuery<TopPage[]>({
    queryKey: ["admin-top-pages"],
    queryFn: async () => {
      const response = await fetch("/api/auth/admin/top-pages/", { credentials: "include" });
      if (!response.ok) throw new Error("Acesso negado");
      const data = (await response.json()) as TopPagesResponse;
      return data.pages;
    },
    enabled: !authLoading && isAuthenticated && isSuperuser,
  });

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
          <Link href={`/${locale}`}>Voltar para a página inicial</Link>
        </p>
      </div>
    );
  }

  if (error || !pages) {
    return (
      <div className="admin-container">
        <h1 className="admin-title">Erro</h1>
        <p className="admin-text">{error?.message || "Erro ao carregar dados"}</p>
      </div>
    );
  }

  return (
    <div className="admin-container">
      <Link href={`/${locale}/admin-dashboard`} className="admin-back-link">← Voltar ao painel</Link>
      <h1 className="admin-title">Páginas mais visitadas (30 dias)</h1>
      <p className="admin-text">Total: {formatNumber(pages.length, 0, locale)} páginas</p>

      <table className="admin-table">
        <thead><tr><th>Página</th><th>Views</th></tr></thead>
        <tbody>
          {pages.map((page) => (
            <tr key={page.path}>
              <td className="admin-path-cell">{page.path || "/"}</td>
              <td>{formatNumber(page.view_count, 0, locale)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
