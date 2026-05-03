import { describe, it, expect } from "vitest";
import { boundFromSliderChange } from "./screenerBounds";

describe("boundFromSliderChange", () => {
  it("returns null when both sides are at the track extreme", () => {
    expect(
      boundFromSliderChange({ min: null, max: null }, { trackMin: 0, trackMax: 100 }),
    ).toBeNull();
  });

  it("fills the min side with the track minimum when only max is set", () => {
    expect(
      boundFromSliderChange({ min: null, max: "0.5" }, { trackMin: 0, trackMax: 100 }),
    ).toEqual({ min: "0", max: "0.5" });
  });

  it("fills the max side with the track maximum when only min is set", () => {
    expect(
      boundFromSliderChange({ min: "0.1", max: null }, { trackMin: 0, trackMax: 100 }),
    ).toEqual({ min: "0.1", max: "100" });
  });

  it("returns both sides untouched when both are explicitly set", () => {
    expect(
      boundFromSliderChange({ min: "0.1", max: "0.5" }, { trackMin: 0, trackMax: 100 }),
    ).toEqual({ min: "0.1", max: "0.5" });
  });
});
