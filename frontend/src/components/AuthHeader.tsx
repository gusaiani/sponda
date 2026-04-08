import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "../hooks/useAuth";
import { useTranslation, LanguageToggle } from "../i18n";
import { ShareDropdown } from "./ShareDropdown";
import "../styles/auth-header.css";

const AUTH_PAGES = ["/login", "/signup", "/forgot-password", "/reset-password"];

export function AuthHeader() {
  const { isAuthenticated, isSuperuser, isLoading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const { t, locale } = useTranslation();

  const isOnAuthPage = AUTH_PAGES.some((path) => pathname.startsWith(path));

  if (isLoading) {
    return (
      <div className="auth-header auth-header--loading">
        <ShareDropdown />
        <LanguageToggle />
        <span className="auth-header-link auth-header-signup">&nbsp;</span>
      </div>
    );
  }

  return (
    <div className="auth-header">
      <ShareDropdown />
      <LanguageToggle />
      {isAuthenticated ? (
        <>
          {isSuperuser && (
            <Link href={`/${locale}/admin-dashboard`} className="auth-header-link auth-header-admin">
              Admin
            </Link>
          )}
          <Link href={`/${locale}/account`} className="auth-header-link">
            {t("auth.my_account")}
          </Link>
        </>
      ) : isOnAuthPage ? (
        <button
          className="auth-header-link auth-header-close"
          onClick={() => router.push(`/${locale}`)}
          aria-label={t("common.close")}
        >
          ✕
        </button>
      ) : (
        <Link href={`/${locale}/login`} className="auth-header-link auth-header-signup">
          {t("auth.login")}
        </Link>
      )}
    </div>
  );
}
