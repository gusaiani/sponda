import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

import { SeoArticle } from "./SeoArticle";

describe("SeoArticle", () => {
  it("renders the article title as the home page's only h1", () => {
    // The home page had no h1 at all: the visible header is a favorites
    // prompt, so the article title is the page's real headline.
    const html = renderToString(<SeoArticle locale="en" />);

    expect(html.match(/<h1/g)).toHaveLength(1);
    expect(html).toContain("<h1 class=\"homepage-explainer-title\">Inflation-adjusted fundamental analysis for value investors</h1>");
  });

  it("keeps section headings below the h1", () => {
    const html = renderToString(<SeoArticle locale="en" />);
    expect(html).not.toContain("<h2");
    expect(html).toContain("<h3>");
  });
});
