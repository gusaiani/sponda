import * as Sentry from "@sentry/nextjs";

import { initSentry } from "./src/lib/sentry";

initSentry(Sentry, {
  dsn: process.env.SENTRY_DSN_NEXTJS ?? process.env.SENTRY_DSN,
  environment: process.env.SENTRY_ENVIRONMENT ?? "development",
  release: process.env.SENTRY_RELEASE,
});
