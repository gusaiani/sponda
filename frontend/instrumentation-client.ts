import * as Sentry from "@sentry/nextjs";

import { initSentry } from "./src/lib/sentry";

// Routes worth keeping at 100% sampling because they drive the bulk of
// real-user value: the home page (`/`, locale-prefixed) and the company
// detail pages (`/[locale]/[ticker]`). Everything else samples at the
// default 0.2 set in initSentry.
const HIGH_PRIORITY_ROUTE_PATTERN =
  /^\/(en|pt|es|zh|fr|de|it)?(\/?$|\/(?!api\b)[a-z0-9-]+\/?$)/i;

initSentry(Sentry, {
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "development",
  release: process.env.NEXT_PUBLIC_SENTRY_RELEASE,
  integrations: [
    Sentry.browserTracingIntegration({
      // Capture INP (Interaction to Next Paint), which replaced FID as
      // the responsiveness Core Web Vital in March 2024.
      enableInp: true,
      // Long Animation Frame attribution surfaces the JS that blocked
      // the main thread, complementing INP.
      enableLongAnimationFrame: true,
    }),
    Sentry.replayIntegration(),
  ],
  // Stitch frontend transactions to backend spans by propagating
  // sentry-trace + baggage headers on these origins.
  tracePropagationTargets: [
    "localhost",
    /^https:\/\/(www\.)?sponda\.capital/,
    /^https:\/\/sponda\.poe\.ma/,
  ],
  tracesSampler: (samplingContext) => {
    const transactionContext = samplingContext.transactionContext as
      | { name?: string; op?: string }
      | undefined;
    const name = transactionContext?.name ?? "";
    if (HIGH_PRIORITY_ROUTE_PATTERN.test(name)) {
      return 1.0;
    }
    return 0.2;
  },
});

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
