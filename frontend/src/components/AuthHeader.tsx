import { Link } from "@tanstack/react-router";
import { useAuth } from "../hooks/useAuth";
import "../styles/auth-header.css";

export function AuthHeader() {
  const { isAuthenticated, isSuperuser, isLoading } = useAuth();

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
      ) : (
        <Link to="/login" className="auth-header-link auth-header-signup">
          Entrar
        </Link>
      )}
    </div>
  );
}
