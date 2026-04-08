"use client";

import { useState, useRef, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTranslation } from "./useTranslation";
import { translateTabSlug } from "../utils/tabs";
import type { Locale } from "./types";

const LANGUAGE_OPTIONS: { locale: Locale; flag: string; label: string }[] = [
  { locale: "pt", flag: "🇧🇷", label: "PT" },
  { locale: "en", flag: "🇺🇸", label: "EN" },
  { locale: "es", flag: "🇪🇸", label: "ES" },
  { locale: "zh", flag: "🇨🇳", label: "ZH" },
  { locale: "fr", flag: "🇫🇷", label: "FR" },
  { locale: "de", flag: "🇩🇪", label: "DE" },
  { locale: "it", flag: "🇮🇹", label: "IT" },
];

export function LanguageToggle() {
  const { locale, setLocale } = useTranslation();
  const router = useRouter();
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentOption = LANGUAGE_OPTIONS.find((option) => option.locale === locale)!;

  function handleSelect(selected: Locale) {
    setLocale(selected);
    setIsOpen(false);

    // Navigate to the equivalent URL in the new locale
    const segments = pathname.split("/").filter(Boolean);
    const LOCALES = new Set(["pt", "en", "es", "zh", "fr", "de", "it"]);
    if (segments.length > 0 && LOCALES.has(segments[0])) {
      segments[0] = selected;
      // Translate tab slug if present (3rd segment: /{locale}/{ticker}/{tab})
      if (segments.length === 3) {
        segments[2] = translateTabSlug(segments[2], selected);
      }
    } else {
      segments.unshift(selected);
    }
    router.push("/" + segments.join("/"));
  }

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="language-dropdown" ref={dropdownRef}>
      <button
        className="language-dropdown-trigger"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Change language"
        aria-expanded={isOpen}
      >
        <span className="language-dropdown-flag">{currentOption.flag}</span>
        <span className="language-dropdown-label">{currentOption.label}</span>
      </button>
      {isOpen && (
        <ul className="language-dropdown-menu">
          {LANGUAGE_OPTIONS.map((option) => (
            <li key={option.locale}>
              <button
                className={`language-dropdown-option${option.locale === locale ? " active" : ""}`}
                onClick={() => handleSelect(option.locale)}
              >
                <span className="language-dropdown-flag">{option.flag}</span>
                <span className="language-dropdown-label">{option.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
