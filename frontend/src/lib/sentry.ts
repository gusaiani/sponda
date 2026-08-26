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
  tracesSampler?: (samplingContext: Record<string, unknown>) => number | boolean;
  tracePropagationTargets?: (string | RegExp)[];
  replaysSessionSampleRate?: number;
  replaysOnErrorSampleRate?: number;
  integrations?: unknown[];
  /** Overrides the third-party noise defaults when provided. */
  ignoreErrors?: (string | RegExp)[];
}

// Default down from 1.0: traces are linear in cost and the home-page
// fanout used to send 60+ spans per visit. 0.2 keeps a representative
// sample without burning quota; routes that need more (e.g. /) can
// override per-transaction via `tracesSampler`.
const DEFAULT_TRACES_SAMPLE_RATE = 0.2;

// Errors thrown by code we do not ship and cannot fix. Each of these was
// sitting unresolved in the Sentry inbox, crowding out real defects:
// a wallet extension that fails when no wallet is installed, an iOS
// in-app webview reaching for a handler only Safari defines, and
// extension bootstraps (Deno-based ones announce themselves with
// `ext:core/` or an `<extension:bootstrap>` frame).
const THIRD_PARTY_NOISE_PATTERNS: (string | RegExp)[] = [
  "Failed to connect to MetaMask",
  "window.webkit.messageHandlers",
  "window.ethereum",
  /\bext:core\//,
  /<[a-z0-9-]+:bootstrap>/i,
  /^(chrome|moz|safari)-extension:\/\//i,
];

export function initSentry(sdk: SentrySDKLike, options: InitSentryOptions): boolean {
  if (!options.dsn) {
    return false;
  }

  const initOptions: Record<string, unknown> = {
    dsn: options.dsn,
    environment: options.environment,
    release: options.release,
    replaysSessionSampleRate: options.replaysSessionSampleRate ?? 0.1,
    replaysOnErrorSampleRate: options.replaysOnErrorSampleRate ?? 1.0,
    sendDefaultPii: false,
    integrations: options.integrations,
    ignoreErrors: options.ignoreErrors ?? THIRD_PARTY_NOISE_PATTERNS,
  };

  if (options.tracesSampler) {
    initOptions.tracesSampler = options.tracesSampler;
  } else {
    initOptions.tracesSampleRate = options.tracesSampleRate ?? DEFAULT_TRACES_SAMPLE_RATE;
  }

  if (options.tracePropagationTargets) {
    initOptions.tracePropagationTargets = options.tracePropagationTargets;
  }

  sdk.init(initOptions);
  return true;
}
