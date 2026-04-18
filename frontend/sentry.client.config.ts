import * as Sentry from "@sentry/nextjs";

import { initSentry } from "./src/lib/sentry";

initSentry(Sentry, {
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "development",
  release: process.env.NEXT_PUBLIC_SENTRY_RELEASE,
  integrations: [Sentry.replayIntegration()],
});
