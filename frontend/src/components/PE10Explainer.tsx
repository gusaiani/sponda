import { useState } from "react";
import { useTranslation } from "../i18n";
import "../styles/card.css";

export function PE10Explainer() {
  const { t } = useTranslation();
  const [pe10Open, setPE10Open] = useState(false);
  const [pfcf10Open, setPFCF10Open] = useState(false);

  return (
    <div className="pe10-explainer-wrapper">
      {/* PE10 */}
      <button
        className="pe10-explainer-toggle"
        onClick={() => setPE10Open(!pe10Open)}
      >
        {pe10Open ? t("explainer.hide") : t("explainer.what_is_pe10")}
        <span className={`pe10-explainer-chevron ${pe10Open ? "pe10-explainer-chevron-open" : ""}`}>
          &#9662;
        </span>
      </button>

      {pe10Open && (
        <div className="pe10-explainer">
          <p>{t("explainer.pe10_text_1")}</p>
          <p>{t("explainer.pe10_text_2")}</p>
          <p>{t("explainer.pe10_text_3")}</p>
        </div>
      )}

      {/* PFCF10 */}
      <button
        className="pe10-explainer-toggle"
        onClick={() => setPFCF10Open(!pfcf10Open)}
      >
        {pfcf10Open ? t("explainer.hide") : t("explainer.what_is_pfcf10")}
        <span className={`pe10-explainer-chevron ${pfcf10Open ? "pe10-explainer-chevron-open" : ""}`}>
          &#9662;
        </span>
      </button>

      {pfcf10Open && (
        <div className="pe10-explainer">
          <p>{t("explainer.pfcf10_text_1")}</p>
          <p>{t("explainer.pfcf10_text_2")}</p>
          <p><strong>{t("explainer.pfcf10_fcf_vs_earnings")}</strong> {t("explainer.pfcf10_text_3")}</p>
          <p>{t("explainer.pfcf10_text_4")}</p>
        </div>
      )}
    </div>
  );
}
