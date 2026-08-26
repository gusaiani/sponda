/**
 * The seven translation dictionaries, and a translator that does not need
 * React.
 *
 * `useTranslation` is a client hook, so anything rendered on the server
 * (Open Graph cards, the markdown twin of every page) could not reach the
 * translations through it. This module holds the lookup itself; the hook is
 * a thin wrapper that binds it to the language context.
 */
import { pt } from "./locales/pt";
import { en } from "./locales/en";
import { es } from "./locales/es";
import { zh } from "./locales/zh";
import { fr } from "./locales/fr";
import { de } from "./locales/de";
import { it } from "./locales/it";
import type { Locale, TranslationKey, TranslationDictionary } from "./types";

export const DICTIONARIES: Record<Locale, TranslationDictionary> = { pt, en, es, zh, fr, de, it };

export type Translator = (
  key: TranslationKey,
  params?: Record<string, string | number>,
) => string;

/** Look up one key in one locale, interpolating `{param}` placeholders. */
export function translate(
  dictionary: TranslationDictionary,
  key: TranslationKey,
  params?: Record<string, string | number>,
): string {
  let value = dictionary[key];
  if (params) {
    for (const [paramKey, paramValue] of Object.entries(params)) {
      value = value.replace(new RegExp(`\\{${paramKey}\\}`, "g"), String(paramValue));
    }
  }
  return value;
}

/** A `t()` bound to one locale, for use outside React. */
export function translatorFor(locale: Locale): Translator {
  const dictionary = DICTIONARIES[locale];
  return (key, params) => translate(dictionary, key, params);
}
