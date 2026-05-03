// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { MultiSelectFilter } from "./MultiSelectFilter";

afterEach(cleanup);

const OPTIONS = ["Energy", "Health Services", "Technology"];

const TRANSLATIONS: Record<string, string> = {
  Technology: "Tecnologia",
  "Health Services": "Saúde",
  Energy: "Energia",
};

const labelFor = (option: string) => TRANSLATIONS[option] ?? option;

const defaultProps = {
  options: OPTIONS,
  labelFor,
  locale: "pt",
  allLabel: "All sectors",
  multiLabel: "Sector",
};

function getTrigger(container: HTMLElement) {
  return container.querySelector(
    ".screener-multiselect-trigger",
  ) as HTMLButtonElement;
}

function openPopover(container: HTMLElement) {
  fireEvent.click(getTrigger(container));
}

function getCheckbox(container: HTMLElement, value: string) {
  return container.querySelector(
    `input[type='checkbox'][value='${value}']`,
  ) as HTMLInputElement;
}

describe("MultiSelectFilter", () => {
  it("renders the trigger with the 'all' label when nothing is selected", () => {
    const { container } = render(
      <MultiSelectFilter {...defaultProps} selected={[]} onChange={() => {}} />,
    );
    expect(getTrigger(container).textContent).toContain("All sectors");
  });

  it("shows the translated single-option label when exactly one is selected", () => {
    const { container } = render(
      <MultiSelectFilter
        {...defaultProps}
        selected={["Technology"]}
        onChange={() => {}}
      />,
    );
    expect(getTrigger(container).textContent).toContain("Tecnologia");
  });

  it("shows '{multiLabel} (count)' when multiple options are selected", () => {
    const { container } = render(
      <MultiSelectFilter
        {...defaultProps}
        selected={["Technology", "Health Services"]}
        onChange={() => {}}
      />,
    );
    expect(getTrigger(container).textContent).toBe("Sector (2)");
  });

  it("opens a popover with one checkbox per option when the trigger is clicked", () => {
    const { container } = render(
      <MultiSelectFilter {...defaultProps} selected={[]} onChange={() => {}} />,
    );
    openPopover(container);
    const checkboxes = container.querySelectorAll(
      ".screener-multiselect-popover input[type='checkbox']",
    );
    expect(checkboxes).toHaveLength(OPTIONS.length);
  });

  it("renders option labels via labelFor", () => {
    const { container } = render(
      <MultiSelectFilter {...defaultProps} selected={[]} onChange={() => {}} />,
    );
    openPopover(container);
    const popover = container.querySelector(".screener-multiselect-popover")!;
    expect(popover.textContent).toContain("Tecnologia");
    expect(popover.textContent).toContain("Saúde");
    expect(popover.textContent).toContain("Energia");
  });

  it("checks the boxes for currently-selected options", () => {
    const { container } = render(
      <MultiSelectFilter
        {...defaultProps}
        selected={["Technology"]}
        onChange={() => {}}
      />,
    );
    openPopover(container);
    expect(getCheckbox(container, "Technology").checked).toBe(true);
    expect(getCheckbox(container, "Health Services").checked).toBe(false);
  });

  it("calls onChange with the option added when an unchecked box is toggled", () => {
    const handleChange = vi.fn();
    const { container } = render(
      <MultiSelectFilter
        {...defaultProps}
        selected={["Technology"]}
        onChange={handleChange}
      />,
    );
    openPopover(container);
    fireEvent.click(getCheckbox(container, "Health Services"));
    expect(handleChange).toHaveBeenCalledWith(["Technology", "Health Services"]);
  });

  it("calls onChange with the option removed when a checked box is toggled off", () => {
    const handleChange = vi.fn();
    const { container } = render(
      <MultiSelectFilter
        {...defaultProps}
        selected={["Technology", "Health Services"]}
        onChange={handleChange}
      />,
    );
    openPopover(container);
    fireEvent.click(getCheckbox(container, "Technology"));
    expect(handleChange).toHaveBeenCalledWith(["Health Services"]);
  });

  it("falls back to the raw value when labelFor returns the input unchanged", () => {
    const { container } = render(
      <MultiSelectFilter
        {...defaultProps}
        options={["Mystery"]}
        selected={["Mystery"]}
        onChange={() => {}}
      />,
    );
    expect(getTrigger(container).textContent).toContain("Mystery");
  });

  it("closes the popover when the user presses Escape", () => {
    const { container } = render(
      <MultiSelectFilter {...defaultProps} selected={[]} onChange={() => {}} />,
    );
    openPopover(container);
    expect(
      container.querySelector(".screener-multiselect-popover"),
    ).not.toBeNull();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(container.querySelector(".screener-multiselect-popover")).toBeNull();
  });
});
