import { useState, FormEvent } from "react";
import "../styles/feedback.css";

const MATH_A = 3;
const MATH_B = 4;
const EXPECTED_ANSWER = MATH_A + MATH_B;

export function FeedbackButton() {
  const [isOpen, setIsOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [humanCheck, setHumanCheck] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    const answer = parseInt(humanCheck, 10);
    if (isNaN(answer) || answer !== EXPECTED_ANSWER) {
      setError("Resposta incorreta. Tente novamente.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch("/api/auth/feedback/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          message,
          human_check: answer,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        setError(data.error || "Erro ao enviar feedback");
        return;
      }

      setSuccess(true);
    } catch {
      setError("Erro de conexão. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  function handleClose() {
    setIsOpen(false);
    setSuccess(false);
    setError(null);
    setEmail("");
    setMessage("");
    setHumanCheck("");
  }

  return (
    <>
      <button
        className="feedback-trigger"
        onClick={() => setIsOpen(true)}
        aria-label="Enviar feedback"
      >
        Feedback
      </button>

      {isOpen && (
        <div className="feedback-overlay" onClick={handleClose}>
          <div className="feedback-panel" onClick={(event) => event.stopPropagation()}>
            <button className="feedback-close" onClick={handleClose} aria-label="Fechar">
              ×
            </button>

            {success ? (
              <div className="feedback-success">
                <h2 className="feedback-title">Obrigado!</h2>
                <p className="feedback-text">
                  Seu feedback foi enviado. Agradecemos sua contribuição.
                </p>
                <button className="auth-button" onClick={handleClose}>
                  Fechar
                </button>
              </div>
            ) : (
              <>
                <h2 className="feedback-title">Enviar Feedback</h2>
                <p className="feedback-text">
                  Sua opinião é importante para melhorarmos a Sponda.
                </p>
                <form className="auth-form" onSubmit={handleSubmit}>
                  <div>
                    <label className="auth-label" htmlFor="feedback-email">
                      Seu email
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
                      Mensagem
                    </label>
                    <textarea
                      id="feedback-message"
                      className="auth-textarea"
                      value={message}
                      onChange={(event) => setMessage(event.target.value)}
                      required
                      placeholder="O que você gostaria de compartilhar?"
                    />
                  </div>
                  <div>
                    <label className="auth-label" htmlFor="feedback-human">
                      Quanto é {MATH_A} + {MATH_B}?
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
                    {loading ? "Enviando…" : "Enviar"}
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
