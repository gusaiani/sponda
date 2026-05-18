// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { renderSpondBody } from "./renderSpondBody";

afterEach(cleanup);

function renderBodyInto(body: string, locale = "pt") {
  return render(<div data-testid="body">{renderSpondBody(body, locale)}</div>);
}

describe("renderSpondBody — URL linkification", () => {
  it("turns a plain https URL into an anchor opening in a new tab", () => {
    renderBodyInto("Veja https://poe.ma para detalhes");
    const link = screen.getByRole("link", { name: "https://poe.ma" });
    expect(link).toHaveAttribute("href", "https://poe.ma");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("linkifies http URLs as well", () => {
    renderBodyInto("old http://example.com link");
    expect(screen.getByRole("link", { name: "http://example.com" })).toHaveAttribute(
      "href",
      "http://example.com",
    );
  });

  it("does not swallow a closing paren when the URL is wrapped in ()", () => {
    renderBodyInto("A Allied faz parte da carteira (https://poe.ma), e tem números");
    const link = screen.getByRole("link", { name: "https://poe.ma" });
    expect(link).toHaveAttribute("href", "https://poe.ma");
    expect(screen.getByTestId("body").textContent).toContain("(https://poe.ma),");
  });

  it("strips a trailing sentence period from the link target", () => {
    renderBodyInto("Fonte: https://poe.ma.");
    const link = screen.getByRole("link", { name: "https://poe.ma" });
    expect(link).toHaveAttribute("href", "https://poe.ma");
    expect(screen.getByTestId("body").textContent).toContain("https://poe.ma.");
  });

  it("preserves query strings inside the URL", () => {
    const url =
      "https://www.rad.cvm.gov.br/ENET/frmExibirArquivoIPEExterno.aspx?NumeroProtocoloEntrega=1375544";
    renderBodyInto(`Veja na CVM: ${url}`);
    expect(screen.getByRole("link", { name: url })).toHaveAttribute("href", url);
  });

  it("still linkifies @handle and $TICKER tokens", () => {
    renderBodyInto("oi @gustavo confira $ALLD3", "pt");
    expect(screen.getByRole("link", { name: "@gustavo" })).toHaveAttribute(
      "href",
      "/pt/user/gustavo",
    );
    expect(screen.getByRole("link", { name: "$ALLD3" })).toHaveAttribute("href", "/pt/ALLD3");
  });

  it("handles a body that mixes a URL, a mention and a ticker", () => {
    renderBodyInto("@gustavo veja https://poe.ma sobre $PETR4", "en");
    expect(screen.getByRole("link", { name: "@gustavo" })).toHaveAttribute(
      "href",
      "/en/user/gustavo",
    );
    expect(screen.getByRole("link", { name: "https://poe.ma" })).toHaveAttribute(
      "href",
      "https://poe.ma",
    );
    expect(screen.getByRole("link", { name: "$PETR4" })).toHaveAttribute("href", "/en/PETR4");
  });

  it("renders plain text untouched when there are no tokens", () => {
    renderBodyInto("apenas texto simples sem links");
    expect(screen.getByTestId("body").textContent).toBe("apenas texto simples sem links");
    expect(screen.queryByRole("link")).toBeNull();
  });
});
