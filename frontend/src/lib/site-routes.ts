/**
 * The non-ticker route names that can follow a locale prefix.
 *
 * `/{locale}/{segment}` is a company page unless `segment` is one of these.
 * Both the middleware's ticker-case normalization and the markdown router
 * need that distinction, and getting it wrong is expensive: adding a route
 * here late is what once had `/pt/user/x` uppercased to `/pt/USER/x`.
 */
export const KNOWN_LOCALE_ROUTES: ReadonlySet<string> = new Set([
  "screener", "shared", "login", "signup", "forgot-password",
  "reset-password", "verify-email", "account", "admin-dashboard",
  "admin", "listas", "alertas", "notificacoes", "visitas",
  // Social routes. Without these the middleware uppercases /pt/user
  // to /pt/USER (treating it as a ticker symbol), which then 404s.
  "user", "spond",
  // How to read Sponda from a program.
  "for-ai",
]);

/**
 * The subset of those routes that has a markdown twin.
 *
 * Everything else in `KNOWN_LOCALE_ROUTES` is an auth, account or social
 * page. They are already `Disallow`ed in robots.txt and there is nothing in
 * them worth serving to a reader who wants plain text.
 */
export const MARKDOWN_LOCALE_ROUTES: ReadonlySet<string> = new Set(["screener", "for-ai"]);

/** Canonical origin every absolute URL on the site is built from. */
export const SITE_BASE_URL = "https://sponda.capital";
