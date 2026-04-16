import { describe, it, expect } from "vitest";
import { buildAlertsListUrl } from "./useAlerts";

describe("buildAlertsListUrl", () => {
  it("returns the bare endpoint when no ticker is given", () => {
    expect(buildAlertsListUrl()).toBe("/api/auth/alerts/");
  });

  it("appends a normalized (upper-case) ticker query param", () => {
    expect(buildAlertsListUrl("petr4")).toBe("/api/auth/alerts/?ticker=PETR4");
  });

  it("URL-encodes unusual characters defensively", () => {
    expect(buildAlertsListUrl("a&b")).toBe("/api/auth/alerts/?ticker=A%26B");
  });
});
