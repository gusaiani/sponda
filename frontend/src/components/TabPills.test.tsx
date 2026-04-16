// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { TabPills } from "./TabPills";

afterEach(cleanup);

vi.mock("../i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const labels: Record<string, string> = {
        "tabs.metrics": "Indicadores",
        "tabs.fundamentals": "Fundamentos",
        "tabs.compare": "Comparar",
        "tabs.charts": "Gráficos",
      };
      return labels[key] ?? key;
    },
    locale: "pt",
  }),
}));

describe("TabPills", () => {
  it("renders all four tabs as anchor links so cmd-click opens in a new tab", () => {
    const { container } = render(<TabPills ticker="PETR4" activeTab="metrics" />);
    const links = container.querySelectorAll("a.tab-pill");
    expect(links).toHaveLength(4);
    for (const link of links) {
      expect(link.tagName).toBe("A");
      expect(link.getAttribute("href")).toMatch(/^\/pt\/PETR4/);
    }
  });

  it("uses locale-aware paths for each tab", () => {
    const { getByText } = render(<TabPills ticker="PETR4" activeTab="metrics" />);
    expect(getByText("Indicadores").getAttribute("href")).toBe("/pt/PETR4");
    expect(getByText("Fundamentos").getAttribute("href")).toBe("/pt/PETR4/fundamentos");
    expect(getByText("Comparar").getAttribute("href")).toBe("/pt/PETR4/comparar");
    expect(getByText("Gráficos").getAttribute("href")).toBe("/pt/PETR4/graficos");
  });

  it("marks the active tab with tab-pill-active", () => {
    const { getByText } = render(<TabPills ticker="PETR4" activeTab="compare" />);
    expect(getByText("Comparar").className).toContain("tab-pill-active");
    expect(getByText("Indicadores").className).not.toContain("tab-pill-active");
  });

  it("fires onPrefetch when hovering the fundamentals or charts tab", () => {
    const onPrefetch = vi.fn();
    const { getByText } = render(
      <TabPills ticker="PETR4" activeTab="metrics" onPrefetch={onPrefetch} />,
    );
    fireEvent.mouseEnter(getByText("Fundamentos"));
    fireEvent.mouseEnter(getByText("Gráficos"));
    expect(onPrefetch).toHaveBeenCalledWith("fundamentals");
    expect(onPrefetch).toHaveBeenCalledWith("charts");
    expect(onPrefetch).toHaveBeenCalledTimes(2);
  });

  it("does not fire onPrefetch for metrics or compare", () => {
    const onPrefetch = vi.fn();
    const { getByText } = render(
      <TabPills ticker="PETR4" activeTab="metrics" onPrefetch={onPrefetch} />,
    );
    fireEvent.mouseEnter(getByText("Indicadores"));
    fireEvent.mouseEnter(getByText("Comparar"));
    expect(onPrefetch).not.toHaveBeenCalled();
  });
});
