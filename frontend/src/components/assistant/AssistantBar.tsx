"use client";

import { useState } from "react";
import { useTranslation, TranslationKey } from "../../i18n";
import { useAssistantStream } from "./useAssistantStream";
import "../../styles/assistant-bar.css";

interface AssistantBarProps {
  ticker: string;
  tab: string;
}

const KNOWN_ERROR_CODES = new Set([
  "upstream_timeout",
  "rate_limited",
  "internal",
  "ASSISTANT_FORBIDDEN",
  "assistant_limit",
]);

export function AssistantBar({ ticker, tab }: AssistantBarProps) {
  const { t, locale } = useTranslation();
  const { state, ask, abort } = useAssistantStream();
  const [question, setQuestion] = useState("");

  function handleSubmit() {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) return;

    ask({ ticker, tab, locale, question: trimmedQuestion });
  }

  const errorMessageKey: TranslationKey =
    state.errorCode && KNOWN_ERROR_CODES.has(state.errorCode)
      ? (`assistant.error.${state.errorCode}` as TranslationKey)
      : "assistant.error.generic";

  const isBusy = state.status === "submitting" || state.status === "streaming";

  return (
    <div className="assistant-bar">
      {state.answer && (
        <div className="assistant-bar-answer" role="status">
          {state.answer}
        </div>
      )}
      {state.status === "error" && (
        <div className="assistant-bar-error" role="alert">
          {t(errorMessageKey)}
        </div>
      )}
      <textarea
        className="assistant-bar-input"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        placeholder={t("assistant.placeholder")}
      />
      <button
        type="button"
        className="assistant-bar-send"
        onClick={handleSubmit}
        disabled={isBusy}
      >
        {t("assistant.send")}
      </button>
      {isBusy && (
        <button type="button" className="assistant-bar-stop" onClick={abort}>
          {t("assistant.stop")}
        </button>
      )}
    </div>
  );
}
