import { useQuota } from "../hooks/useQuota";
import { useTranslation } from "../i18n";
import "../styles/auth.css";

export function QuotaAlert() {
  const { t, locale } = useTranslation();
  const { data } = useQuota();

  if (!data || data.remaining > 0) return null;

  return (
    <div className="quota-alert">
      <p className="quota-alert-text">
        {t("quota.limit_reached")} {data.limit} {locale === "pt" ? "consultas diárias" : "daily queries"}.{" "}
        <a href={`/${locale}/signup`} className="quota-alert-link">
          {t("quota.create_account")}
        </a>{" "}
        {t("quota.to_continue")}
      </p>
    </div>
  );
}
