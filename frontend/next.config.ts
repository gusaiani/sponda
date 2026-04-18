import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const FRONTEND_ROOT = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
  // Pin Turbopack's workspace root to the frontend package so relative CSS
  // imports (e.g. `@import "../styles/global.css"`) resolve against
  // frontend/src/ instead of the outer /web/ repo root. Next 16 auto-detects
  // the root from the nearest lockfile and an empty outer package-lock.json
  // would otherwise win.
  turbopack: {
    root: FRONTEND_ROOT,
  },
  images: {
    remotePatterns: [
      { hostname: "financialmodelingprep.com" },
      { hostname: "icons.brapi.dev" },
    ],
  },
  env: {
    NEXT_PUBLIC_GOOGLE_CLIENT_ID:
      process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ||
      "61540815310-n311ho945gmd0d0q0kcasr6msckk8m1t.apps.googleusercontent.com",
  },
};

export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  silent: !process.env.CI,
  widenClientFileUpload: true,
  disableLogger: true,
  telemetry: false,
});
