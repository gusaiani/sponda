import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "../hooks/useAuth";
import "../styles/auth-header.css";

const AUTH_PAGES = ["/login", "/signup", "/forgot-password", "/reset-password"];

export function AuthHeader() {
  const { isAuthenticated, isSuperuser, isLoading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const isOnAuthPage = AUTH_PAGES.some((path) => pathname.startsWith(path));

  if (isLoading) return null;

  return (
    <div className="auth-header">
      {isAuthenticated ? (
        <>
          {isSuperuser && (
            <Link href="/admin-dashboard" className="auth-header-link auth-header-admin">
              Admin
            </Link>
          )}
          <Link href="/account" className="auth-header-link">
            Minha conta
          </Link>
        </>
      ) : isOnAuthPage ? (
        <button
          className="auth-header-link auth-header-close"
          onClick={() => router.push("/")}
          aria-label="Fechar"
        >
          ✕
        </button>
      ) : (
        <Link href="/login" className="auth-header-link auth-header-signup">
          Entrar
        </Link>
      )}
    </div>
  );
}
