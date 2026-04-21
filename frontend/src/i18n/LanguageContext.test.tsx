/** @vitest-environment jsdom */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { useContext } from "react";
import { LanguageContext, LanguageProvider } from "./LanguageContext";

type LanguageContextValue = React.ContextType<typeof LanguageContext>;

function renderProvider(initialLocale: "pt" | "en" | "fr" | "de" | "it" | "es" | "zh" = "en") {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  let captured!: LanguageContextValue;
  function Reader() {
    captured = useContext(LanguageContext);
    return null;
  }
  act(() => {
    root.render(
      <LanguageProvider initialLocale={initialLocale}>
        <Reader />
      </LanguageProvider>,
    );
  });
  return {
    context: () => captured,
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
}

describe("LanguageProvider", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let rendered: ReturnType<typeof renderProvider> | null = null;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const store = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, value),
      removeItem: (key: string) => store.delete(key),
      clear: () => store.clear(),
      length: 0,
      key: () => null,
    });
    document.cookie = "sponda-lang=; path=/; max-age=0";
  });

  afterEach(() => {
    rendered?.unmount();
    rendered = null;
    vi.unstubAllGlobals();
  });

  it("setLocale persists to backend via PATCH /api/auth/language/", async () => {
    rendered = renderProvider("en");
    await act(async () => {
      rendered!.context().setLocale("fr");
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/language/");
    expect(init.method).toBe("PATCH");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body as string)).toEqual({ language: "fr" });
  });

  it("setLocale writes sponda-lang cookie", async () => {
    rendered = renderProvider("en");
    await act(async () => {
      rendered!.context().setLocale("it");
    });
    expect(document.cookie).toContain("sponda-lang=it");
  });

  it("ignores backend errors (anonymous visitor)", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 401 }));
    rendered = renderProvider("en");
    await act(async () => {
      rendered!.context().setLocale("de");
    });
    expect(rendered.context().locale).toBe("de");
  });
});
