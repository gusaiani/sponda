import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { useAuth } from "../hooks/useAuth";
import "../styles/auth-header.css";

const AUTH_PAGES = ["/login", "/signup", "/forgot-password", "/reset-password"];

export function AuthHeader() {
  const { isAuthenticated, isSuperuser, isLoading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const isOnAuthPage = AUTH_PAGES.some((path) => location.pathname.startsWith(path));

  if (isLoading) return null;

  return (
    <div className="auth-header">
      {isAuthenticated ? (
        <>
          {isSuperuser && (
            <Link to="/admin-dashboard" className="auth-header-link auth-header-admin">
              Admin
            </Link>
          )}
          <Link to="/account" className="auth-header-link">
            Minha conta
          </Link>
        </>
      ) : isOnAuthPage ? (
        <button
          className="auth-header-link auth-header-close"
          onClick={() => navigate({ to: "/" })}
          aria-label="Fechar"
        >
          ✕
        </button>
      ) : (
        <Link to="/login" className="auth-header-link auth-header-signup">
          Entrar
        </Link>
      )}
    </div>
  );
}
