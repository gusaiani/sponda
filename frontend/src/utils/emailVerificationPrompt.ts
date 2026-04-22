"use client";

const STORAGE_KEY = "sponda-email-verification-prompt-visible";
const EVENT_NAME = "sponda-email-verification-prompt-change";

function emitChange() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(EVENT_NAME));
}

export function getEmailVerificationPromptVisible(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(STORAGE_KEY) === "true";
}

export function setEmailVerificationPromptVisible(visible: boolean) {
  if (typeof window === "undefined") return;

  if (visible) {
    window.localStorage.setItem(STORAGE_KEY, "true");
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }

  emitChange();
}

export async function buildApiError(response: Response, fallbackMessage: string): Promise<Error> {
  const bodyText = await response.text().catch(() => "");
  let message = fallbackMessage;

  try {
    const parsed = bodyText ? JSON.parse(bodyText) : null;
    if (parsed?.verification_required) {
      setEmailVerificationPromptVisible(true);
    }

    if (parsed?.error) {
      message = String(parsed.error);
    } else if (parsed?.detail) {
      message = String(parsed.detail);
    } else if (bodyText) {
      message = bodyText.slice(0, 200);
    }
  } catch {
    if (bodyText) {
      message = bodyText.slice(0, 200);
    }
  }

  return new Error(message);
}
