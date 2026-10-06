import { describe, it, expect } from "vitest";
import {
  unavailableExplanationKey,
  unavailableShortLabelKey,
} from "./trailingRatios";

describe("unavailableExplanationKey", () => {
  it("explains a window that does not fit, for every ratio", () => {
    for (const ratioKey of ["pe", "pfcf", "debtToEarnings", "debtToFcf"] as const) {
      expect(unavailableExplanationKey(ratioKey, "insufficient_history")).toBe(
        "fundamentals.unavailable.insufficient_history",
      );
    }
  });

  it("explains a negative average for the debt coverage ratios", () => {
    expect(unavailableExplanationKey("debtToEarnings", "negative_average")).toBe(
      "fundamentals.unavailable.negative_earnings",
    );
    expect(unavailableExplanationKey("debtToFcf", "negative_average")).toBe(
      "fundamentals.unavailable.negative_fcf",
    );
  });

  it("has nothing to say when there is no recorded reason", () => {
    expect(unavailableExplanationKey("debtToEarnings", null)).toBeNull();
  });
});

describe("unavailableShortLabelKey", () => {
  it("labels only a negative average", () => {
    expect(unavailableShortLabelKey("debtToEarnings", "negative_average")).toBe(
      "fundamentals.unavailable.negative_earnings_short",
    );
    expect(unavailableShortLabelKey("debtToFcf", "negative_average")).toBe(
      "fundamentals.unavailable.negative_fcf_short",
    );
  });

  it("leaves a window that does not fit as a dash", () => {
    expect(unavailableShortLabelKey("debtToEarnings", "insufficient_history")).toBeNull();
  });

  it("leaves a cell with no recorded reason as a dash", () => {
    expect(unavailableShortLabelKey("debtToFcf", null)).toBeNull();
  });
});
