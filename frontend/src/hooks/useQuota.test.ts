import { describe, it, expect } from "vitest";
import { shouldShowQuotaAlert, type QuotaResult } from "./useQuota";

function quota(p: Partial<QuotaResult>): QuotaResult {
  return {
    limit: 20,
    used: 0,
    remaining: 20,
    authenticated: false,
    email_verified: false,
    scope: "anonymous",
    ...p,
  };
}

describe("shouldShowQuotaAlert", () => {
  it("hidden while lookups remain", () => {
    expect(shouldShowQuotaAlert(quota({ remaining: 5 }))).toBe(false);
  });

  it("shown exactly when the cap is exhausted", () => {
    expect(shouldShowQuotaAlert(quota({ remaining: 0 }))).toBe(true);
  });

  it("hidden for unlimited (verified) users — remaining is null", () => {
    expect(
      shouldShowQuotaAlert(
        quota({ limit: null, remaining: null, scope: "verified" }),
      ),
    ).toBe(false);
  });

  it("hidden when data is absent", () => {
    expect(shouldShowQuotaAlert(undefined)).toBe(false);
  });
});
