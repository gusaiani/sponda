import { useTranslation } from "../i18n";

interface SignupVerificationContentProps {
  onContinue: () => void;
  continueLabel?: string;
}

export function SignupVerificationContent({
  onContinue,
  continueLabel,
}: SignupVerificationContentProps) {
  const { t, locale } = useTranslation();

  const sentCopy = {
    pt: "Email de verificação enviado. Confira sua caixa de entrada.",
    en: "Verification email sent. Check your inbox.",
    es: "Email de verificación enviado. Revisa tu bandeja de entrada.",
    fr: "Email de vérification envoyé. Consultez votre boîte de réception.",
    de: "Bestätigungs-E-Mail gesendet. Prüfen Sie Ihren Posteingang.",
    it: "Email di verifica inviata. Controlla la tua casella di posta.",
    zh: "验证邮件已发送。请检查您的收件箱。",
  }[locale];

  return (
    <div className="auth-signup-success">
      <h1 className="auth-title">{t("verify.pending_title")}</h1>
      <p className="auth-success-text">{sentCopy}</p>
      <button type="button" className="auth-button" onClick={onContinue}>
        {continueLabel ?? t("common.close")}
      </button>
    </div>
  );
}
