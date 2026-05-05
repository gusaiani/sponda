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
    rerender: () => {
      act(() => {
        root.render(
          <LearningModeProvider>
            <Reader />
          </LearningModeProvider>,
        );
      });
    },
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
}

describe("LearningModeProvider", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let rendered: ReturnType<typeof renderProvider> | null = null;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    document.cookie = "csrftoken=test-csrf";
    mockUseAuth.mockReset();
  });

  afterEach(() => {
    rendered?.unmount();
    rendered = null;
    vi.unstubAllGlobals();
  });

  it("is unavailable for non-authenticated users", () => {
    mockUseAuth.mockReturnValue({ user: null });
    rendered = renderProvider();
    expect(rendered.context().available).toBe(false);
    expect(rendered.context().enabled).toBe(false);
  });

  it("is unavailable for non-superuser authenticated users", () => {
    mockUseAuth.mockReturnValue({
      user: { is_superuser: false, learning_mode_enabled: true },
    });
    rendered = renderProvider();
    expect(rendered.context().available).toBe(false);
    expect(rendered.context().enabled).toBe(false);
  });

  it("is available for superusers and reflects server preference", () => {
    mockUseAuth.mockReturnValue({
      user: { is_superuser: true, learning_mode_enabled: true },
    });
    rendered = renderProvider();
    expect(rendered.context().available).toBe(true);
    expect(rendered.context().enabled).toBe(true);
  });

  it("setEnabled persists to /api/auth/preferences/ for superusers", async () => {
    mockUseAuth.mockReturnValue({
      user: { is_superuser: true, learning_mode_enabled: false },
    });
    rendered = renderProvider();
    await act(async () => {
      rendered!.context().setEnabled(true);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/preferences/");
    expect(init.method).toBe("PATCH");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body as string)).toEqual({ learning_mode_enabled: true });
    expect(rendered.context().enabled).toBe(true);
  });

  it("setEnabled is a no-op for non-superusers", async () => {
    mockUseAuth.mockReturnValue({
      user: { is_superuser: false, learning_mode_enabled: false },
    });
    rendered = renderProvider();
    await act(async () => {
      rendered!.context().setEnabled(true);
    });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(rendered.context().enabled).toBe(false);
  });

  it("ignores backend errors but keeps optimistic state", async () => {
    fetchMock.mockResolvedValueOnce(new Response("{}", { status: 500 }));
    mockUseAuth.mockReturnValue({
      user: { is_superuser: true, learning_mode_enabled: false },
    });
    rendered = renderProvider();
    await act(async () => {
      rendered!.context().setEnabled(true);
    });
    expect(rendered.context().enabled).toBe(true);
  });
});
