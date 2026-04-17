import { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import {
  useSavedScreenerFilters,
  type SavedScreenerFilterEntry,
} from "../hooks/useSavedScreenerFilters";
import { useTranslation } from "../i18n";
import type { ScreenerFilters } from "../hooks/useScreener";
import "../styles/screener-filter-presets.css";

interface Props {
  currentBounds: ScreenerFilters["bounds"];
  currentSort: string;
  onApplyPreset: (preset: SavedScreenerFilterEntry) => void;
  /** Called when the "Save filters" button is clicked. The caller decides
   * how to collect the name (inline prompt, modal, etc.) so the preset
   * strip stays purely about listing + applying presets. */
  onRequestSave: () => void;
}

export function ScreenerFilterPresets({
  currentBounds,
  currentSort,
  onApplyPreset,
  onRequestSave,
}: Props) {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { filters, deleteFilter } = useSavedScreenerFilters();

  if (!isAuthenticated) return null;

  const hasActiveFilters =
    Object.keys(currentBounds).length > 0 || currentSort !== "-market_cap";

  if (filters.length === 0 && !hasActiveFilters) return null;

  function boundsMatch(a: ScreenerFilters["bounds"], b: ScreenerFilters["bounds"]) {
    const keysA = Object.keys(a);
    const keysB = Object.keys(b);
    if (keysA.length !== keysB.length) return false;
    for (const key of keysA) {
      const entryA = a[key as keyof ScreenerFilters["bounds"]];
      const entryB = b[key as keyof ScreenerFilters["bounds"]];
      if (!entryA || !entryB) return false;
      if ((entryA.min ?? null) !== (entryB.min ?? null)) return false;
      if ((entryA.max ?? null) !== (entryB.max ?? null)) return false;
    }
    return true;
  }

  const activePresetId = filters.find(
    (preset) => preset.sort === currentSort && boundsMatch(preset.bounds, currentBounds),
  )?.id ?? null;

  return (
    <div className="screener-presets">
      <span className="screener-presets-label">{t("screener.presets_label")}</span>
      <div className="screener-presets-list">
        {filters.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={`screener-preset-chip${activePresetId === preset.id ? " screener-preset-chip-active" : ""}`}
            onClick={() => onApplyPreset(preset)}
          >
            <span className="screener-preset-name">{preset.name}</span>
            <span
              className="screener-preset-delete"
              role="button"
              aria-label={t("common.delete")}
              onClick={(event) => {
                event.stopPropagation();
                if (confirm(`${t("screener.confirm_delete_preset")} "${preset.name}"?`)) {
                  deleteFilter.mutate(preset.id);
                }
              }}
            >
              ×
            </span>
          </button>
        ))}
        {hasActiveFilters && (
          <button
            type="button"
            className="screener-preset-save"
            onClick={onRequestSave}
          >
            + {t("screener.save_filters")}
          </button>
        )}
      </div>
    </div>
  );
}

/** Lightweight modal prompting the user for a name. Lifted out so the
 * screener page doesn't have to reinvent another modal/form stack. */
interface SaveModalProps {
  defaultName?: string;
  onSave: (name: string) => void;
  onCancel: () => void;
}

export function SaveFilterPresetModal({ defaultName = "", onSave, onCancel }: SaveModalProps) {
  const { t } = useTranslation();
  const [name, setName] = useState(defaultName);

  useEffect(() => {
    setName(defaultName);
  }, [defaultName]);

  return (
    <div className="compare-save-overlay" onClick={onCancel}>
      <div className="compare-save-modal" onClick={(event) => event.stopPropagation()}>
        <h3 className="compare-save-modal-title">{t("screener.save_filters")}</h3>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const trimmed = name.trim();
            if (!trimmed) return;
            onSave(trimmed);
          }}
        >
          <input
            type="text"
            className="auth-input"
            placeholder={t("screener.filter_preset_name")}
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoFocus
          />
          <div className="compare-save-modal-actions">
            <button type="submit" className="auth-button" disabled={!name.trim()}>
              {t("common.save")}
            </button>
            <button
              type="button"
              className="auth-button-secondary"
              onClick={onCancel}
            >
              {t("common.cancel")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
