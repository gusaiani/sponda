import Link from "next/link";

/**
 * Render a plain Spond body with $TICKER, @handle and bare URL tokens
 * linkified. The body is at most 500 chars and arrives as plain text, so a
 * single regex pass with split-and-stitch is fast enough — no DOM-walking,
 * no DOMPurify.
 *
 * URLs open in a new tab with rel="noopener noreferrer". @handle and
 * $TICKER stay as in-app Next.js links.
 */

const TOKEN_PATTERN = /(https?:\/\/[^\s]+|@[a-z0-9_]{3,24}\b|\$[A-Z]{1,5}\d{0,2}\b)/g;

const TRAILING_PUNCTUATION = ".,;:!?'\"]}";
const TOKEN_LINK_STYLE = { color: "#1b347e", fontWeight: 600 } as const;

/**
 * Split sentence punctuation that the greedy URL match swallowed back off
 * the end of the URL. A closing paren counts as punctuation only when it is
 * unbalanced (no matching "(" inside the URL), so balanced links such as
 * Wikipedia URLs keep their parens.
 */
function splitTrailingPunctuation(raw: string): [url: string, trailing: string] {
  let end = raw.length;
  while (end > 0) {
    const char = raw[end - 1];
    if (TRAILING_PUNCTUATION.includes(char)) {
      end -= 1;
      continue;
    }
    if (char === ")") {
      const slice = raw.slice(0, end);
      const openCount = (slice.match(/\(/g) ?? []).length;
      const closeCount = (slice.match(/\)/g) ?? []).length;
      if (closeCount > openCount) {
        end -= 1;
        continue;
      }
    }
    break;
  }
  return [raw.slice(0, end), raw.slice(end)];
}

export function renderSpondBody(body: string, locale: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  TOKEN_PATTERN.lastIndex = 0;
  while ((match = TOKEN_PATTERN.exec(body)) !== null) {
    if (match.index > lastIndex) {
      parts.push(body.slice(lastIndex, match.index));
    }
    const token = match[0];

    if (token.startsWith("http")) {
      const [url, trailing] = splitTrailingPunctuation(token);
      parts.push(
        <a
          key={`u-${key++}`}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          style={TOKEN_LINK_STYLE}
        >
          {url}
        </a>,
      );
      if (trailing) parts.push(trailing);
    } else if (token.startsWith("@")) {
      const handle = token.slice(1);
      parts.push(
        <Link key={`m-${key++}`} href={`/${locale}/user/${handle}`} style={TOKEN_LINK_STYLE}>
          {token}
        </Link>,
      );
    } else if (token.startsWith("$")) {
      const symbol = token.slice(1);
      parts.push(
        <Link key={`t-${key++}`} href={`/${locale}/${symbol}`} style={TOKEN_LINK_STYLE}>
          {token}
        </Link>,
      );
    }
    lastIndex = TOKEN_PATTERN.lastIndex;
  }
  if (lastIndex < body.length) parts.push(body.slice(lastIndex));
  return parts;
}
