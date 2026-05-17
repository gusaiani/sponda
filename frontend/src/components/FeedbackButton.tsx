"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { useTranslation } from "../i18n";
import "../styles/feedback.css";

const MATH_A = 3;
const MATH_B = 4;
const EXPECTED_ANSWER = MATH_A + MATH_B;
const POE_URL_TEXT = "www.poe.ma";
const POE_URL_HREF = "https://www.poe.ma";


function linkifyPoe(text: string): ReactNode {
  const index = text.indexOf(POE_URL_TEXT);
  if (index === -1) return text;
  return (
    <>
      {text.slice(0, index)}
      <a href={POE_URL_HREF} target="_blank" rel="noopener noreferrer" className="feedback-link">
        {POE_URL_TEXT}
      </a>
      {text.slice(index + POE_URL_TEXT.length)}
    </>
  );
}


interface FeedbackContextValue {
  open: () => void;
}

const FeedbackContext = createContext<FeedbackContextValue | null>(null);


/**
 * Hook used by anywhere in the app that wants to open the feedback modal
 * (the LeftNav button, a header link, etc.). The provider must be mounted
 * higher up in the tree.
 */
export function useFeedback(): FeedbackContextValue {
  const value = useContext(FeedbackContext);
  if (!value) return { open: () => {} };
  return value;
}


/**
 * Provider that owns the open/close state and renders the modal once.
 * Mount near the layout root so any descendant can call ``open()``.
 *
 * The standalone floating FeedbackButton was retired when the LeftNav
 * absorbed the feedback affordance — there is no default trigger
 * anymore, only the modal and the imperative ``open()``.
 */
export function FeedbackProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [humanCheck, setHumanCheck] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const open = useCallback(() => setIsOpen(true), []);

  function close() {
    setIsOpen(false);
    setSuccess(false);
    setError(null);
    setEmail("");
    setMessage("");
    setHumanCheck("");
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    const answer = parseInt(humanCheck, 10);
    if (isNaN(answer) || answer !== EXPECTED_ANSWER) {
      setError(t("feedback.wrong_answer"));
      return;
    }

    setLoading(true);

    try {
      const response = await fetch("/api/auth/feedback/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, message, human_check: answer }),
      });

      if (!response.ok) {
        const data = await response.json();
        setError(data.error || t("feedback.send_error"));
        return;
      }

      setSuccess(true);
    } catch {
      setError(t("feedback.send_error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <FeedbackContext.Provider value={{ open }}>
      {children}
      {isOpen && (
        <div className="feedback-overlay" onClick={close}>
          <div className="feedback-panel" onClick={(event) => event.stopPropagation()}>
            <button className="feedback-close" onClick={close} aria-label={t("common.close")}>
              ×
            </button>

            {success ? (
              <div className="feedback-success">
                <h2 className="feedback-title">{t("feedback.thanks")}</h2>
                <p className="feedback-text">{t("feedback.thanks_text")}</p>
                <button className="auth-button" onClick={close}>
                  {t("common.close")}
                </button>
              </div>
            ) : (
              <>
                <h2 className="feedback-title">{t("feedback.title")}</h2>
                <p className="feedback-text">{linkifyPoe(t("feedback.subtitle"))}</p>
                <form className="auth-form" onSubmit={handleSubmit}>
                  <div>
                    <label className="auth-label" htmlFor="feedback-email">
                      {t("feedback.email_label")}
                    </label>
                    <input
                      id="feedback-email"
                      type="email"
                      className="auth-input"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <label className="auth-label" htmlFor="feedback-message">
                      {t("feedback.message_label")}
                    </label>
                    <textarea
                      id="feedback-message"
                      className="auth-textarea"
                      value={message}
                      onChange={(event) => setMessage(event.target.value)}
                      required
                      placeholder={t("feedback.message_placeholder")}
                    />
                  </div>
                  <div>
                    <label className="auth-label" htmlFor="feedback-human">
                      {t("feedback.math_question")} {MATH_A} + {MATH_B}?
                    </label>
                    <input
                      id="feedback-human"
                      type="number"
                      className="auth-input"
                      value={humanCheck}
                      onChange={(event) => setHumanCheck(event.target.value)}
                      required
                      style={{ maxWidth: "100px" }}
                    />
                  </div>
                  {error && <p className="auth-error">{error}</p>}
                  <button type="submit" className="auth-button" disabled={loading}>
                    {loading ? t("feedback.sending") : t("feedback.send")}
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      )}
    </FeedbackContext.Provider>
  );
}
