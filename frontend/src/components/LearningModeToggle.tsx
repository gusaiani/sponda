"use client";

import { useTranslation } from "../i18n";
import { useLearningMode } from "../learning";
import "../styles/learning-mode-toggle.css";

export function LearningModeToggle() {
  const { enabled, available, setEnabled } = useLearningMode();
  const { t } = useTranslation();

  if (!available) return null;

  return (
    <button
      type="button"
      className={`learning-mode-toggle${enabled ? " learning-mode-toggle--on" : ""}`}
      aria-pressed={enabled}
      aria-label={t("learning.toggle.aria_label" as never)}
      title={t("learning.toggle.title" as never)}
      onClick={() => setEnabled(!enabled)}
    >
      <span className="learning-mode-toggle-dots" aria-hidden="true">
        <span className="learning-mode-toggle-dot learning-mode-toggle-dot--1" />
        <span className="learning-mode-toggle-dot learning-mode-toggle-dot--3" />
        <span className="learning-mode-toggle-dot learning-mode-toggle-dot--5" />
      </span>
      <span className="learning-mode-toggle-label">{t("learning.toggle.label" as never)}</span>
    </button>
  );
}
