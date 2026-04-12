"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "../../../../hooks/useAuth";
import { useTranslation } from "../../../../i18n";

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
  const [pages, setPages] = useState<TopPage[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated || !isSuperuser) {
      setIsLoading(false);
      return;
    }

    fetch("/api/auth/admin/top-pages/", { credentials: "include" })
      .then((response) => {
        if (!response.ok) throw new Error("Acesso negado");
        return response.json() as Promise<TopPagesResponse>;
      })
      .then((data) => setPages(data.pages))
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
          <Link href={`/${locale}`}>Voltar para a página inicial</Link>
        </p>
      </div>
    );
  }

  if (error || !pages) {
    return (
      <div className="admin-container">
        <h1 className="admin-title">Erro</h1>
        <p className="admin-text">{error || "Erro ao carregar dados"}</p>
      </div>
    );
  }

  return (
    <div className="admin-container">
      <Link href={`/${locale}/admin-dashboard`} className="admin-back-link">← Voltar ao painel</Link>
      <h1 className="admin-title">Páginas mais visitadas (30 dias)</h1>
      <p className="admin-text">Total: {pages.length.toLocaleString("pt-BR")} páginas</p>

      <table className="admin-table">
        <thead><tr><th>Página</th><th>Views</th></tr></thead>
        <tbody>
          {pages.map((page) => (
            <tr key={page.path}>
              <td className="admin-path-cell">{page.path || "/"}</td>
              <td>{page.view_count.toLocaleString("pt-BR")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
