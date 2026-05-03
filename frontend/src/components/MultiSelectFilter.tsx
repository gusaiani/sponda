"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

interface MultiSelectFilterProps {
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
  /** Translates a raw option (e.g. an ISO country code or a backend
   * sector name) into its human-readable form for the active locale. */
  labelFor: (option: string) => string;
  /** Locale used to sort the popover entries by their localized label. */
  locale: string;
  /** Trigger text when nothing is selected (e.g. "All sectors"). */
  allLabel: string;
  /** Trigger prefix when more than one option is selected — rendered as
   * "{multiLabel} ({count})", e.g. "Sector (3)". */
  multiLabel: string;
}

interface PopoverPosition {
  top: number;
  left: number;
}

export function MultiSelectFilter({
  options,
  selected,
  onChange,
  labelFor,
  locale,
  allLabel,
  multiLabel,
}: MultiSelectFilterProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const [popoverPosition, setPopoverPosition] = useState<PopoverPosition | null>(null);

  /** Sort options by their localized label so the popover reads naturally
   * in the active language rather than mixing languages mid-list. */
  const sortedOptions = useMemo(() => {
    return [...options].sort((a, b) =>
      labelFor(a).localeCompare(labelFor(b), locale),
    );
  }, [options, locale, labelFor]);

  /** The trigger sits inside the inline-filters strip, which clips
   * overflow to enforce a single-line layout. An absolutely-positioned
   * popover would inherit that clipping, so we anchor a fixed-positioned
   * popover to the trigger's viewport rect instead. */
  const recomputePopoverPosition = useCallback(() => {
    const node = triggerRef.current;
    if (!node) return;
    const rect = node.getBoundingClientRect();
    setPopoverPosition({ top: rect.bottom + 6, left: rect.left });
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    recomputePopoverPosition();
  }, [open, recomputePopoverPosition]);

  useEffect(() => {
    if (!open) return;
    window.addEventListener("scroll", recomputePopoverPosition, true);
    window.addEventListener("resize", recomputePopoverPosition);
    return () => {
      window.removeEventListener("scroll", recomputePopoverPosition, true);
      window.removeEventListener("resize", recomputePopoverPosition);
    };
  }, [open, recomputePopoverPosition]);

  useEffect(() => {
    if (!open) return;
    function handlePointer(event: MouseEvent) {
      const target = event.target as Node;
      if (triggerRef.current?.contains(target)) return;
      if (popoverRef.current?.contains(target)) return;
      setOpen(false);
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  let triggerLabel: string;
  if (selected.length === 0) {
    triggerLabel = allLabel;
  } else if (selected.length === 1) {
    triggerLabel = labelFor(selected[0]);
  } else {
    triggerLabel = `${multiLabel} (${selected.length})`;
  }

  function toggleOption(option: string) {
    if (selected.includes(option)) {
      onChange(selected.filter((value) => value !== option));
    } else {
      onChange([...selected, option]);
    }
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="screener-multiselect-trigger"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        {triggerLabel}
      </button>
      {open && popoverPosition && (
        <div
          ref={popoverRef}
          className="screener-multiselect-popover"
          role="dialog"
          style={{ top: popoverPosition.top, left: popoverPosition.left }}
        >
          {sortedOptions.map((option) => (
            <label key={option} className="screener-multiselect-option">
              <input
                type="checkbox"
                value={option}
                checked={selected.includes(option)}
                onChange={() => toggleOption(option)}
              />
              <span>{labelFor(option)}</span>
            </label>
          ))}
        </div>
      )}
    </>
  );
}
