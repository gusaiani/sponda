// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, fireEvent, screen } from "@testing-library/react";
import { useState } from "react";
import { LocalizedDateInput } from "./LocalizedDateInput";
import { LanguageContext } from "../i18n";
import type { Locale } from "../i18n";

afterEach(cleanup);

function Harness({ locale, initial = "", min, onChange }: {
  locale: Locale;
  initial?: string;
  min?: string;
  onChange?: (value: string) => void;
}) {
  const [value, setValue] = useState(initial);
  return (
    <LanguageContext.Provider value={{ locale, setLocale: () => {} }}>
      <LocalizedDateInput
        value={value}
        min={min}
        className="field"
        onChange={(next) => {
          setValue(next);
          onChange?.(next);
        }}
      />
      <output data-testid="value">{value}</output>
    </LanguageContext.Provider>
  );
}

function textField(): HTMLInputElement {
  return document.querySelector("input.field") as HTMLInputElement;
}

describe("LocalizedDateInput", () => {
  it.each([
    ["pt", "dd/mm/aaaa"],
    ["en", "mm/dd/yyyy"],
    ["es", "dd/mm/aaaa"],
    ["fr", "jj/mm/aaaa"],
    ["de", "TT.MM.JJJJ"],
    ["it", "gg/mm/aaaa"],
    ["zh", "年/月/日"],
  ] as const)("shows the %s placeholder %s", (locale, placeholder) => {
    render(<Harness locale={locale} />);

    expect(textField().placeholder).toBe(placeholder);
  });

  it("formats typed digits and reports the ISO date", () => {
    const onChange = vi.fn();
    render(<Harness locale="pt" onChange={onChange} />);

    fireEvent.change(textField(), { target: { value: "18122026" } });

    expect(textField().value).toBe("18/12/2026");
    expect(onChange).toHaveBeenLastCalledWith("2026-12-18");
  });

  it("keeps a partial entry on screen and reports no date yet", () => {
    const onChange = vi.fn();
    render(<Harness locale="pt" onChange={onChange} />);

    fireEvent.change(textField(), { target: { value: "181" } });

    expect(textField().value).toBe("18/1");
    expect(onChange).toHaveBeenLastCalledWith("");
  });

  it("reads month first in English", () => {
    render(<Harness locale="en" />);

    fireEvent.change(textField(), { target: { value: "12182026" } });

    expect(screen.getByTestId("value").textContent).toBe("2026-12-18");
  });

  it("rejects a date before the minimum and flags the field", () => {
    const onChange = vi.fn();
    render(<Harness locale="pt" min="2026-11-18" onChange={onChange} />);

    fireEvent.change(textField(), { target: { value: "01/01/2026" } });

    expect(onChange).toHaveBeenLastCalledWith("");
    expect(textField().getAttribute("aria-invalid")).toBe("true");
  });

  it("flags a date that does not exist", () => {
    render(<Harness locale="pt" />);

    fireEvent.change(textField(), { target: { value: "31/02/2027" } });

    expect(textField().getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByTestId("value").textContent).toBe("");
  });

  it("shows an existing value in the active locale's format", () => {
    render(<Harness locale="pt" initial="2027-01-10" />);

    expect(textField().value).toBe("10/01/2027");
  });

  it("clears the text when the value is reset from outside", () => {
    function ResettableHarness() {
      const [value, setValue] = useState("");
      return (
        <LanguageContext.Provider value={{ locale: "pt", setLocale: () => {} }}>
          <LocalizedDateInput value={value} onChange={setValue} className="field" />
          <button type="button" onClick={() => setValue("")}>reset</button>
        </LanguageContext.Provider>
      );
    }
    render(<ResettableHarness />);

    fireEvent.change(textField(), { target: { value: "10012027" } });
    fireEvent.click(screen.getByText("reset"));

    expect(textField().value).toBe("");
  });

  it("opens the browser's calendar from the calendar button", () => {
    render(<Harness locale="pt" />);
    const picker = document.querySelector('input[type="date"]') as HTMLInputElement;
    const showPicker = vi.fn();
    Object.defineProperty(picker, "showPicker", { value: showPicker });

    fireEvent.click(screen.getByRole("button", { name: "Abrir calendário" }));

    expect(showPicker).toHaveBeenCalled();
  });

  it("takes a date chosen in the calendar", () => {
    render(<Harness locale="pt" />);
    const picker = document.querySelector('input[type="date"]') as HTMLInputElement;

    fireEvent.change(picker, { target: { value: "2027-03-05" } });

    expect(screen.getByTestId("value").textContent).toBe("2027-03-05");
    expect(textField().value).toBe("05/03/2027");
  });

  it("keeps the browser's calendar out of the tab order and away from screen readers", () => {
    render(<Harness locale="pt" />);
    const picker = document.querySelector('input[type="date"]') as HTMLInputElement;

    expect(picker.tabIndex).toBe(-1);
    expect(picker.getAttribute("aria-hidden")).toBe("true");
  });
});
