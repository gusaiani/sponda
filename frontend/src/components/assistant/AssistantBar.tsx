"use client";

import { useState } from "react";
import { useTranslation, TranslationKey } from "../../i18n";
import { useAssistantStream } from "./useAssistantStream";
import "../../styles/assistant-bar.css";

interface AssistantBarProps {
  ticker: string;
  tab: string;
}

// Machine error code → localized user message. Config-level codes
// (assistant_not_configured) deliberately map to the neutral "unavailable"
// message so the raw cause never reaches end users — developers get that
// via DEV_ERROR_HINTS below. Unmapped codes fall back to the generic message.
const ERROR_MESSAGE_KEY_BY_CODE: Record<string, TranslationKey> = {
  upstream_timeout: "assistant.error.upstream_timeout",
  rate_limited: "assistant.error.rate_limited",
  internal: "assistant.error.internal",
  ASSISTANT_FORBIDDEN: "assistant.error.ASSISTANT_FORBIDDEN",
  assistant_limit: "assistant.error.assistant_limit",
  assistant_unavailable: "assistant.error.assistant_unavailable",
  assistant_not_configured: "assistant.error.assistant_unavailable",
  assistant_interrupted: "assistant.error.assistant_interrupted",
  network: "assistant.error.network",
};

// Developer-facing diagnostics, shown only outside production. English and
// untranslated on purpose — these are for whoever is running the app, not
// for end users. They name the real cause the user message hides.
const DEV_ERROR_HINTS: Record<string, string> = {
  assistant_not_configured:
    "OPENAI_API_KEY is not set on the backend — the assistant can't reach OpenAI.",
  assistant_unavailable:
    "The assistant backend returned an error status — is it running and is the route reachable?",
  assistant_interrupted:
    "The stream closed before a terminal frame — the backend likely failed mid-response.",
  network: "Couldn't reach the backend (fetch failed).",
};

/** Build the developer diagnostic line, prefixing the real HTTP status when
 * the error came from a non-OK response (so we never guess the number). */
function buildDeveloperHint(
  errorCode: string,
  httpStatus: number | null,
): string {
  const body = DEV_ERROR_HINTS[errorCode] ?? `Assistant error: ${errorCode}`;
  return httpStatus ? `HTTP ${httpStatus} · ${body}` : body;
}

const IS_DEVELOPMENT = process.env.NODE_ENV !== "production";

export function AssistantBar({ ticker, tab }: AssistantBarProps) {
  const { t, locale } = useTranslation();
  const { state, ask, abort } = useAssistantStream();
  const [question, setQuestion] = useState("");

  function handleSubmit() {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) return;

    ask({ ticker, tab, locale, question: trimmedQuestion });
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter submits; Shift+Enter keeps the default newline insertion.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }

  const errorMessageKey: TranslationKey =
    (state.errorCode && ERROR_MESSAGE_KEY_BY_CODE[state.errorCode]) ||
    "assistant.error.generic";

  const developerHint =
    IS_DEVELOPMENT && state.status === "error" && state.errorCode
      ? buildDeveloperHint(state.errorCode, state.httpStatus)
      : null;

  const isBusy = state.status === "submitting" || state.status === "streaming";

  const isOffTopic = state.status === "off_topic";

  return (
    <div className="assistant-bar">
      <div className="assistant-bar-panel">
        {(state.answer || state.status === "submitting") && (
          <div
            className={
              isOffTopic
                ? "assistant-bar-answer assistant-bar-answer--off-topic"
                : "assistant-bar-answer"
            }
            role="status"
          >
            {state.answer}
            {state.status === "submitting" && (
              <span className="assistant-bar-thinking" aria-hidden="true">
                <span className="assistant-bar-dot" />
                <span className="assistant-bar-dot" />
                <span className="assistant-bar-dot" />
              </span>
            )}
            {state.status === "streaming" && (
              <span className="assistant-bar-caret" aria-hidden="true" />
            )}
          </div>
        )}
        {state.status === "error" && (
          <div className="assistant-bar-error" role="alert">
            {t(errorMessageKey)}
          </div>
        )}
        {developerHint && (
          <div className="assistant-bar-dev-hint" role="note">
            {developerHint}
          </div>
        )}
        <div className="assistant-bar-row">
          <span className="assistant-bar-spark" aria-hidden="true">
            ✦
          </span>
          <textarea
            className="assistant-bar-input"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("assistant.placeholder")}
            rows={1}
          />
          <div className="assistant-bar-actions">
            {isBusy && (
              <button
                type="button"
                className="assistant-bar-stop"
                onClick={abort}
              >
                {t("assistant.stop")}
              </button>
            )}
            <button
              type="button"
              className="assistant-bar-send"
              onClick={handleSubmit}
              disabled={isBusy}
            >
              {t("assistant.send")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
