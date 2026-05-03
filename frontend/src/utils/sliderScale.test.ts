import { describe, it, expect } from "vitest";
import { LEVERAGE_SCALE, formatLeverageValue } from "./sliderScale";

describe("LEVERAGE_SCALE", () => {
  it("maps the track endpoints to 0 and 100", () => {
    expect(LEVERAGE_SCALE.toValue(0)).toBe(0);
    expect(LEVERAGE_SCALE.toValue(1)).toBe(100);
  });

  it("clamps positions outside [0, 1]", () => {
    expect(LEVERAGE_SCALE.toValue(-0.2)).toBe(0);
    expect(LEVERAGE_SCALE.toValue(1.4)).toBe(100);
  });

  it("gives the 0..1 band 55% of the track", () => {
    expect(LEVERAGE_SCALE.toValue(0.55)).toBeCloseTo(1, 6);
    expect(LEVERAGE_SCALE.toPosition(1)).toBeCloseTo(0.55, 6);
  });

  it("places the value 0.5 at the midpoint of the low band", () => {
    expect(LEVERAGE_SCALE.toValue(0.275)).toBeCloseTo(0.5, 6);
    expect(LEVERAGE_SCALE.toPosition(0.5)).toBeCloseTo(0.275, 6);
  });

  it("log-compresses the 1..100 tail across the upper 45%", () => {
    // log10(10) = 1 → halfway through the upper band → position 0.55 + 0.225.
    expect(LEVERAGE_SCALE.toValue(0.775)).toBeCloseTo(10, 6);
    expect(LEVERAGE_SCALE.toPosition(10)).toBeCloseTo(0.775, 6);
  });

  it("is a true inverse round-trip for representative values", () => {
    for (const value of [0, 0.05, 0.5, 1, 2.5, 10, 25, 100]) {
      expect(LEVERAGE_SCALE.toValue(LEVERAGE_SCALE.toPosition(value))).toBeCloseTo(
        value,
        6,
      );
    }
  });

  describe("snap", () => {
    it("snaps to 0.05 increments below 1", () => {
      expect(LEVERAGE_SCALE.snap(0.07)).toBeCloseTo(0.05, 6);
      expect(LEVERAGE_SCALE.snap(0.08)).toBeCloseTo(0.1, 6);
      expect(LEVERAGE_SCALE.snap(0.55)).toBeCloseTo(0.55, 6);
    });

    it("snaps to 0.5 increments between 1 and 20", () => {
      expect(LEVERAGE_SCALE.snap(2.3)).toBe(2.5);
      expect(LEVERAGE_SCALE.snap(7.1)).toBe(7);
      expect(LEVERAGE_SCALE.snap(19.4)).toBe(19.5);
    });

    it("snaps to 5 increments above 20", () => {
      expect(LEVERAGE_SCALE.snap(22)).toBe(20);
      expect(LEVERAGE_SCALE.snap(47)).toBe(45);
      expect(LEVERAGE_SCALE.snap(98)).toBe(100);
    });

    it("clamps to the [0, 100] range", () => {
      expect(LEVERAGE_SCALE.snap(-0.3)).toBe(0);
      expect(LEVERAGE_SCALE.snap(150)).toBe(100);
    });
  });
});

describe("formatLeverageValue", () => {
  it("uses two decimals below 1", () => {
    expect(formatLeverageValue(0.05, "en")).toBe("0.05");
    expect(formatLeverageValue(0.5, "en")).toBe("0.50");
  });

  it("uses one decimal between 1 and 10", () => {
    expect(formatLeverageValue(2.5, "en")).toBe("2.5");
    expect(formatLeverageValue(9.5, "en")).toBe("9.5");
  });

  it("uses integer formatting at 10 and above", () => {
    expect(formatLeverageValue(10, "en")).toBe("10");
    expect(formatLeverageValue(45, "en")).toBe("45");
    expect(formatLeverageValue(100, "en")).toBe("100");
  });

  it("respects locale-specific decimal separators", () => {
    expect(formatLeverageValue(0.5, "pt")).toBe("0,50");
    expect(formatLeverageValue(2.5, "pt")).toBe("2,5");
  });
});
