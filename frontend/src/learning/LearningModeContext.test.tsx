// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import * as React from "react";
import { act, useContext } from "react";
import { createRoot } from "react-dom/client";
import { LearningModeContext, LearningModeProvider } from "./LearningModeContext";

const mockUseAuth = vi.fn();

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

type ContextValue = React.ContextType<typeof LearningModeContext>;

function renderProvider() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  let captured!: ContextValue;
  function Reader() {
    captured = useContext(LearningModeContext);
    return null;
  }
  act(() => {
    root.render(
      <LearningModeProvider>
        <Reader />
      </LearningModeProvider>,
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

describe("LearningModeProvider", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let store: Map<string, string>;
  let rendered: ReturnType<typeof renderProvider> | null = null;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    store = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, value),
      removeItem: (key: string) => store.delete(key),
      clear: () => store.clear(),
      length: 0,
      key: () => null,
    });
    document.cookie = "csrftoken=test-csrf";
    mockUseAuth.mockReset();
  });

  afterEach(() => {
    rendered?.unmount();
    rendered = null;
    vi.unstubAllGlobals();
  });

  it("is always available", () => {
    mockUseAuth.mockReturnValue({ user: null, isAuthenticated: false });
    rendered = renderProvider();
    expect(rendered.context().available).toBe(true);
  });

  it("guest defaults to enabled when localStorage is empty", () => {
    mockUseAuth.mockReturnValue({ user: null, isAuthenticated: false });
    rendered = renderProvider();
    expect(rendered.context().enabled).toBe(true);
  });

  it("guest honors an explicit opt-out stored in localStorage", () => {
    store.set("sponda-learning-mode", "0");
    mockUseAuth.mockReturnValue({ user: null, isAuthenticated: false });
    rendered = renderProvider();
    expect(rendered.context().enabled).toBe(false);
  });

  it("authenticated user reflects the server preference", () => {
    mockUseAuth.mockReturnValue({
      user: { is_superuser: false, learning_mode_enabled: true },
      isAuthenticated: true,
    });
    rendered = renderProvider();
    expect(rendered.context().enabled).toBe(true);
  });

  it("setEnabled persists to /api/auth/preferences/ when authenticated", async () => {
    mockUseAuth.mockReturnValue({
      user: { is_superuser: false, learning_mode_enabled: false },
      isAuthenticated: true,
    });
    rendered = renderProvider();
    await act(async () => {
      rendered!.context().setEnabled(true);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/preferences/");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ learning_mode_enabled: true });
    expect(rendered.context().enabled).toBe(true);
  });

  it("setEnabled writes localStorage for guests and skips the network", async () => {
    mockUseAuth.mockReturnValue({ user: null, isAuthenticated: false });
    rendered = renderProvider();
    await act(async () => {
      rendered!.context().setEnabled(true);
    });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(store.get("sponda-learning-mode")).toBe("1");
    expect(rendered.context().enabled).toBe(true);
  });

  it("ignores backend errors but keeps optimistic state", async () => {
    fetchMock.mockResolvedValueOnce(new Response("{}", { status: 500 }));
    mockUseAuth.mockReturnValue({
      user: { is_superuser: false, learning_mode_enabled: false },
      isAuthenticated: true,
    });
    rendered = renderProvider();
    await act(async () => {
      rendered!.context().setEnabled(true);
    });
    expect(rendered.context().enabled).toBe(true);
  });
});
