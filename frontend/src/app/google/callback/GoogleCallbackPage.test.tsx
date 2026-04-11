// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { GoogleCallbackContent } from "./GoogleCallbackContent";

const mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
}));

let lastFetchUrl: string | undefined;
let lastFetchBody: Record<string, string> | undefined;
let fetchResponse: { ok: boolean; json: () => Promise<Record<string, string>> };

beforeEach(() => {
  lastFetchUrl = undefined;
  lastFetchBody = undefined;
  fetchResponse = { ok: true, json: async () => ({}) };

  vi.stubGlobal("fetch", async (url: string, options: RequestInit) => {
    lastFetchUrl = url;
    lastFetchBody = JSON.parse(options.body as string);
    return fetchResponse;
  });

  // Reset search params
  for (const key of [...mockSearchParams.keys()]) {
    mockSearchParams.delete(key);
  }
});

afterEach(cleanup);

describe("GoogleCallbackContent", () => {
  it("sends a locale-free redirect_uri to the backend", async () => {
    mockSearchParams.set("code", "test-auth-code");
    mockSearchParams.set("state", "pt");

    render(<GoogleCallbackContent />);

    // Wait for the fetch to be called
    await vi.waitFor(() => {
      expect(lastFetchUrl).toBe("/api/auth/google/");
    });

    expect(lastFetchBody?.redirect_uri).toBe("http://localhost:3000/google/callback");
    expect(lastFetchBody?.code).toBe("test-auth-code");
  });

  it("uses the same redirect_uri regardless of which locale is in state", async () => {
    mockSearchParams.set("code", "test-auth-code");
    mockSearchParams.set("state", "zh");

    render(<GoogleCallbackContent />);

    await vi.waitFor(() => {
      expect(lastFetchUrl).toBe("/api/auth/google/");
    });

    // redirect_uri must NOT contain the locale
    expect(lastFetchBody?.redirect_uri).toBe("http://localhost:3000/google/callback");
  });

  it("shows error when no authorization code is present", () => {
    // No code param set
    render(<GoogleCallbackContent />);

    expect(screen.getByText(/authorization/i)).toBeTruthy();
  });

  it("redirects to the locale from state param on success", async () => {
    mockSearchParams.set("code", "test-auth-code");
    mockSearchParams.set("state", "fr");

    const locationAssign = vi.fn();
    Object.defineProperty(window, "location", {
      value: { ...window.location, href: "", origin: "http://localhost:3000", assign: locationAssign },
      writable: true,
    });

    render(<GoogleCallbackContent />);

    await vi.waitFor(() => {
      expect(window.location.href).toBe("/fr");
    });
  });

  it("falls back to English when state param is missing", async () => {
    mockSearchParams.set("code", "test-auth-code");
    // No state param

    Object.defineProperty(window, "location", {
      value: { ...window.location, href: "", origin: "http://localhost:3000" },
      writable: true,
    });

    render(<GoogleCallbackContent />);

    await vi.waitFor(() => {
      expect(window.location.href).toBe("/en");
    });
  });
});
