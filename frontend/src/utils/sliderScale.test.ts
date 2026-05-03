import { describe, it, expect } from "vitest";
import {
  CURRENT_RATIO_SCALE,
  LEVERAGE_SCALE,
  formatCurrentRatioValue,
  formatLeverageValue,
} from "./sliderScale";

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

describe("CURRENT_RATIO_SCALE", () => {
  it("maps the track endpoints to 0 and 20", () => {
    expect(CURRENT_RATIO_SCALE.toValue(0)).toBe(0);
    expect(CURRENT_RATIO_SCALE.toValue(1)).toBe(20);
  });

  it("clamps positions outside [0, 1]", () => {
    expect(CURRENT_RATIO_SCALE.toValue(-0.2)).toBe(0);
    expect(CURRENT_RATIO_SCALE.toValue(1.4)).toBe(20);
  });

  it("gives the 0..3 band 60% of the track", () => {
    expect(CURRENT_RATIO_SCALE.toValue(0.6)).toBeCloseTo(3, 6);
    expect(CURRENT_RATIO_SCALE.toPosition(3)).toBeCloseTo(0.6, 6);
  });

  it("places the value 1 at one third of the low band", () => {
    expect(CURRENT_RATIO_SCALE.toValue(0.2)).toBeCloseTo(1, 6);
    expect(CURRENT_RATIO_SCALE.toPosition(1)).toBeCloseTo(0.2, 6);
  });

  it("log-compresses the 3..20 tail across the upper 40%", () => {
    expect(CURRENT_RATIO_SCALE.toValue(CURRENT_RATIO_SCALE.toPosition(10))).toBeCloseTo(
      10,
      6,
    );
    const halfwayUpper = 0.6 + 0.2;
    const expectedAtHalfway = 3 * Math.pow(20 / 3, 0.5);
    expect(CURRENT_RATIO_SCALE.toValue(halfwayUpper)).toBeCloseTo(expectedAtHalfway, 6);
  });

  it("is a true inverse round-trip for representative values", () => {
    for (const value of [0, 0.05, 0.5, 1, 1.5, 3, 5, 10, 20]) {
      expect(
        CURRENT_RATIO_SCALE.toValue(CURRENT_RATIO_SCALE.toPosition(value)),
      ).toBeCloseTo(value, 6);
    }
  });

  describe("snap", () => {
    it("snaps to 0.05 increments below 1", () => {
      expect(CURRENT_RATIO_SCALE.snap(0.07)).toBeCloseTo(0.05, 6);
      expect(CURRENT_RATIO_SCALE.snap(0.08)).toBeCloseTo(0.1, 6);
    });

    it("snaps to 0.1 increments between 1 and 5", () => {
      expect(CURRENT_RATIO_SCALE.snap(2.34)).toBeCloseTo(2.3, 6);
      expect(CURRENT_RATIO_SCALE.snap(4.97)).toBeCloseTo(5, 6);
    });

    it("snaps to 0.5 increments between 5 and 10", () => {
      expect(CURRENT_RATIO_SCALE.snap(6.3)).toBe(6.5);
      expect(CURRENT_RATIO_SCALE.snap(9.1)).toBe(9);
    });

    it("snaps to whole numbers at 10 and above", () => {
      expect(CURRENT_RATIO_SCALE.snap(11.4)).toBe(11);
      expect(CURRENT_RATIO_SCALE.snap(17.6)).toBe(18);
    });

    it("clamps to the [0, 20] range", () => {
      expect(CURRENT_RATIO_SCALE.snap(-0.3)).toBe(0);
      expect(CURRENT_RATIO_SCALE.snap(25)).toBe(20);
    });
  });
});

describe("formatCurrentRatioValue", () => {
  it("uses two decimals below 1", () => {
    expect(formatCurrentRatioValue(0.05, "en")).toBe("0.05");
    expect(formatCurrentRatioValue(0.5, "en")).toBe("0.50");
  });

  it("uses one decimal between 1 and 10", () => {
    expect(formatCurrentRatioValue(2.5, "en")).toBe("2.5");
    expect(formatCurrentRatioValue(9.5, "en")).toBe("9.5");
  });

  it("uses integer formatting at 10 and above", () => {
    expect(formatCurrentRatioValue(10, "en")).toBe("10");
    expect(formatCurrentRatioValue(20, "en")).toBe("20");
  });

  it("respects locale-specific decimal separators", () => {
    expect(formatCurrentRatioValue(0.5, "pt")).toBe("0,50");
    expect(formatCurrentRatioValue(2.5, "pt")).toBe("2,5");
  });
});
