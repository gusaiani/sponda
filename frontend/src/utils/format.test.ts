import { describe, it, expect } from "vitest";
import { ptLabel, br, formatLargeNumber, formatQuarterLabel } from "./format";

describe("ptLabel", () => {
  it("converts PE10 to P/L10", () => {
    expect(ptLabel("PE10")).toBe("P/L10");
  });

  it("converts PE5 to P/L5", () => {
    expect(ptLabel("PE5")).toBe("P/L5");
  });

  it("converts PFCF10 to P/FCL10", () => {
    expect(ptLabel("PFCF10")).toBe("P/FCL10");
  });

  it("converts PFCF7 to P/FCL7", () => {
    expect(ptLabel("PFCF7")).toBe("P/FCL7");
  });

  it("leaves other strings unchanged", () => {
    expect(ptLabel("CAGR")).toBe("CAGR");
  });
});

describe("br", () => {
  it("formats with Brazilian locale using comma as decimal separator", () => {
    expect(br(1234.56, 2)).toContain(",");
  });

  it("respects the digits parameter for decimal places", () => {
    expect(br(1.5, 0)).toBe("2");
    expect(br(1.5, 2)).toBe("1,50");
    expect(br(3.14159, 3)).toBe("3,142");
  });

  it("replaces hyphen-minus with n-dash for negative numbers", () => {
    const result = br(-5, 0);
    expect(result).not.toContain("-");
    expect(result).toContain("\u2013");
    expect(result).toBe("\u20135");
  });

  it("handles zero", () => {
    expect(br(0, 0)).toBe("0");
    expect(br(0, 2)).toBe("0,00");
  });
});

describe("formatLargeNumber", () => {
  it("formats billions with B suffix", () => {
    const result = formatLargeNumber(2_500_000_000);
    expect(result).toMatch(/^R\$ .+B$/);
    expect(result).toContain("2,50");
  });

  it("formats millions with M suffix", () => {
    const result = formatLargeNumber(350_000_000);
    expect(result).toMatch(/^R\$ .+M$/);
    expect(result).toContain("350,00");
  });

  it("formats thousands with K suffix", () => {
    const result = formatLargeNumber(42_000);
    expect(result).toMatch(/^R\$ .+K$/);
    expect(result).toContain("42,0");
  });

  it("formats small numbers without suffix", () => {
    const result = formatLargeNumber(500);
    expect(result).toBe("R$ 500");
  });

  it("handles negative values in billions", () => {
    const result = formatLargeNumber(-1_000_000_000);
    expect(result).toMatch(/^R\$ .+B$/);
    expect(result).toContain("\u2013");
  });

  it("handles negative values in millions", () => {
    const result = formatLargeNumber(-50_000_000);
    expect(result).toMatch(/^R\$ .+M$/);
    expect(result).toContain("\u2013");
  });

  it("always prefixes with R$", () => {
    expect(formatLargeNumber(0)).toMatch(/^R\$ /);
    expect(formatLargeNumber(999)).toMatch(/^R\$ /);
    expect(formatLargeNumber(1_000_000)).toMatch(/^R\$ /);
    expect(formatLargeNumber(1_000_000_000)).toMatch(/^R\$ /);
  });
});

describe("formatQuarterLabel", () => {
  it("returns 1T2024 for 2024-03-31", () => {
    expect(formatQuarterLabel("2024-03-31")).toBe("1T2024");
  });

  it("returns 2T2024 for 2024-06-30", () => {
    expect(formatQuarterLabel("2024-06-30")).toBe("2T2024");
  });

  it("returns 3T2024 for 2024-09-30", () => {
    expect(formatQuarterLabel("2024-09-30")).toBe("3T2024");
  });

  it("returns 4T2024 for 2024-12-31", () => {
    expect(formatQuarterLabel("2024-12-31")).toBe("4T2024");
  });

  it("returns 1T2023 for 2023-01-15", () => {
    expect(formatQuarterLabel("2023-01-15")).toBe("1T2023");
  });
});
