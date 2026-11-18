/**
 * Carries a visitor back to where they were after a login that leaves the
 * page (Google OAuth), and lets that page resume the action that asked for
 * the login. Both values live in sessionStorage, which survives the round
 * trip to Google within the same tab and never leaves the browser.
 */

const RETURN_PATH_STORAGE_KEY = "sponda.postLoginReturn";
const PENDING_ACTION_STORAGE_KEY = "sponda.pendingAuthAction";

/** A login abandoned for longer than this should not fire an action later. */
export const PENDING_ACTION_LIFETIME_MILLISECONDS = 15 * 60 * 1000;

export interface PendingAuthAction {
  kind: "mark-visited";
  ticker: string;
}

interface StoredReturnPath {
  path: string;
  savedAt: number;
}

interface StoredPendingAction extends PendingAuthAction {
  savedAt: number;
}

function readJson<T>(key: string): T | null {
  try {
    const raw = window.sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage blocked (private mode, disabled site data): the login still
    // works, it just lands on the locale home as before.
  }
}

function remove(key: string): void {
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // Nothing to clean up when storage is unavailable.
  }
}

/** Only a path on this origin: "/x", never "//host" or "/\host". */
function isSameOriginPath(path: unknown): path is string {
  return (
    typeof path === "string" &&
    path.startsWith("/") &&
    !path.startsWith("//") &&
    !path.startsWith("/\\")
  );
}

function normalizeAction(action: PendingAuthAction): PendingAuthAction {
  return { kind: action.kind, ticker: action.ticker.toUpperCase() };
}

export function rememberPostLoginReturn(path: string, pendingAction?: PendingAuthAction): void {
  const savedAt = Date.now();
  writeJson(RETURN_PATH_STORAGE_KEY, { path, savedAt } satisfies StoredReturnPath);
  if (pendingAction) {
    writeJson(PENDING_ACTION_STORAGE_KEY, { ...normalizeAction(pendingAction), savedAt });
  } else {
    remove(PENDING_ACTION_STORAGE_KEY);
  }
}

/** The page to land on after login, read once. Null when none is safe. */
export function consumePostLoginReturnPath(): string | null {
  const stored = readJson<StoredReturnPath>(RETURN_PATH_STORAGE_KEY);
  remove(RETURN_PATH_STORAGE_KEY);
  return isSameOriginPath(stored?.path) ? stored.path : null;
}

/**
 * True, once, when the given action was waiting on a login. An action meant
 * for another company is left in place for that company's page.
 */
export function consumePendingAuthAction(action: PendingAuthAction): boolean {
  const stored = readJson<StoredPendingAction>(PENDING_ACTION_STORAGE_KEY);
  if (!stored) return false;

  const isExpired = Date.now() - stored.savedAt > PENDING_ACTION_LIFETIME_MILLISECONDS;
  if (isExpired) {
    remove(PENDING_ACTION_STORAGE_KEY);
    return false;
  }

  const wanted = normalizeAction(action);
  if (stored.kind !== wanted.kind || stored.ticker !== wanted.ticker) return false;

  remove(PENDING_ACTION_STORAGE_KEY);
  return true;
}
