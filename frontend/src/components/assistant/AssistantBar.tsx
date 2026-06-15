"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslation, TranslationKey } from "../../i18n";
import { useAssistantStream, type AssistantState } from "./useAssistantStream";
import { useAssistantWindow } from "./AssistantWindowContext";
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

/** One exchange in the thread: the user's question, then the assistant's
 * answer (or thinking dots / streaming caret), plus any error + dev hint. */
function AssistantBarTurn({ turn }: { turn: AssistantState }) {
  const { t } = useTranslation();

  // Off-topic redirects classify as off_topic/jailbreak but still end on a
  // `done` frame — gate on the classification, not the status, so the muted
  // redirect styling sticks after completion.
  const isOffTopic =
    turn.classification != null && turn.classification !== "on_topic";

  const errorMessageKey: TranslationKey =
    (turn.errorCode && ERROR_MESSAGE_KEY_BY_CODE[turn.errorCode]) ||
    "assistant.error.generic";

  const developerHint =
    IS_DEVELOPMENT && turn.status === "error" && turn.errorCode
      ? buildDeveloperHint(turn.errorCode, turn.httpStatus)
      : null;

  return (
    <div className="assistant-bar-turn">
      {turn.question && (
        <p className="assistant-bar-question">{turn.question}</p>
      )}
      {(turn.answer || turn.status === "submitting") && (
        <div
          className={
            isOffTopic
              ? "assistant-bar-answer assistant-bar-answer--off-topic"
              : "assistant-bar-answer"
          }
          role="status"
        >
          {turn.answer}
          {turn.status === "submitting" && (
            <span className="assistant-bar-thinking" aria-hidden="true">
              <span className="assistant-bar-dot" />
              <span className="assistant-bar-dot" />
              <span className="assistant-bar-dot" />
            </span>
          )}
          {turn.status === "streaming" && (
            <span className="assistant-bar-caret" aria-hidden="true" />
          )}
        </div>
      )}
      {turn.status === "error" && (
        <div className="assistant-bar-error" role="alert">
          {t(errorMessageKey)}
        </div>
      )}
      {developerHint && (
        <div className="assistant-bar-dev-hint" role="note">
          {developerHint}
        </div>
      )}
    </div>
  );
}

export function AssistantBar({ ticker, tab }: AssistantBarProps) {
  const { t, locale } = useTranslation();
  const { state, conversation, ask, abort } = useAssistantStream();
  const years = useAssistantWindow();
  // `draft` is the in-progress textarea text; the *submitted* question lives on
  // each turn's state and is rendered above that turn's answer.
  const [draft, setDraft] = useState("");
  const [isOpen, setIsOpen] = useState(true);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  function handleSubmit() {
    const trimmedQuestion = draft.trim();
    if (!trimmedQuestion) return;

    ask({ ticker, tab, locale, question: trimmedQuestion, years });
    // Clear the box and keep focus so the user can fire a follow-up
    // immediately — the submitted question reappears in the thread.
    setDraft("");
    inputRef.current?.focus();
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter submits; Shift+Enter keeps the default newline insertion.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }

  // Keep the latest turn / streaming tokens in view as the thread grows.
  useEffect(() => {
    const thread = threadRef.current;
    if (thread) {
      thread.scrollTop = thread.scrollHeight;
    }
  }, [conversation]);

  const isBusy = state.status === "submitting" || state.status === "streaming";

  // Collapsed: a small launcher to bring the assistant back. The component
  // stays mounted, so the conversation thread survives a close/reopen.
  if (!isOpen) {
    return (
      <div className="assistant-bar">
        <button
          type="button"
          className="assistant-bar-launcher"
          onClick={() => setIsOpen(true)}
          aria-label={t("assistant.open")}
        >
          ✦
        </button>
      </div>
    );
  }

  return (
    <div className="assistant-bar">
      <div className="assistant-bar-panel">
        <div className="assistant-bar-header">
          <button
            type="button"
            className="assistant-bar-close"
            onClick={() => setIsOpen(false)}
            aria-label={t("assistant.close")}
          >
            ✕
          </button>
        </div>
        {conversation.length > 0 && (
          <div className="assistant-bar-thread" ref={threadRef}>
            {conversation.map((turn, index) => (
              <AssistantBarTurn key={index} turn={turn} />
            ))}
          </div>
        )}
        <div className="assistant-bar-row">
          <span className="assistant-bar-spark" aria-hidden="true">
            ✦
          </span>
          <textarea
            ref={inputRef}
            className="assistant-bar-input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
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
