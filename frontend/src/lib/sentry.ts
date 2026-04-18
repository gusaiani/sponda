/**
 * Shared Sentry initializer for the three Next.js runtimes
 * (client, server, edge). Each runtime's sentry.*.config.ts calls this
 * with the matching @sentry/nextjs module.
 *
 * No-op when `dsn` is falsy so dev and test environments stay quiet
 * unless NEXT_PUBLIC_SENTRY_DSN is set.
 */

export interface SentrySDKLike {
  init: (options: Record<string, unknown>) => unknown;
}

export interface InitSentryOptions {
  dsn: string | undefined;
  environment: string;
  release: string | undefined;
  tracesSampleRate?: number;
  replaysSessionSampleRate?: number;
  replaysOnErrorSampleRate?: number;
  integrations?: unknown[];
}

export function initSentry(sdk: SentrySDKLike, options: InitSentryOptions): boolean {
  if (!options.dsn) {
    return false;
  }

  sdk.init({
    dsn: options.dsn,
    environment: options.environment,
    release: options.release,
    tracesSampleRate: options.tracesSampleRate ?? 1.0,
    replaysSessionSampleRate: options.replaysSessionSampleRate ?? 0.1,
    replaysOnErrorSampleRate: options.replaysOnErrorSampleRate ?? 1.0,
    sendDefaultPii: false,
    integrations: options.integrations,
  });

  return true;
}
