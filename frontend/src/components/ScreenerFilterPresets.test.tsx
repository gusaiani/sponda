// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { SaveFilterPresetModal } from "./ScreenerFilterPresets";

vi.mock("../i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key, locale: "pt" }),
}));

afterEach(cleanup);

function renderModal(props: Partial<React.ComponentProps<typeof SaveFilterPresetModal>> = {}) {
  const onSave = vi.fn();
  const onCancel = vi.fn();
  const utils = render(
    <SaveFilterPresetModal onSave={onSave} onCancel={onCancel} {...props} />,
  );
  const input = utils.container.querySelector("input") as HTMLInputElement;
  return { ...utils, input, onSave, onCancel };
}

describe("SaveFilterPresetModal", () => {
  it("starts empty when no default name is given", () => {
    const { input } = renderModal();

    expect(input.value).toBe("");
  });

  it("seeds the field from defaultName", () => {
    const { input } = renderModal({ defaultName: "Cheap Brazilians" });

    expect(input.value).toBe("Cheap Brazilians");
  });

  it("takes the new default on a fresh mount, which is how reopening works", () => {
    // The screener renders this behind `showSavePresetModal &&`, so closing
    // unmounts it and reopening builds a new one. That is what makes the
    // initial useState value sufficient.
    const first = renderModal({ defaultName: "First" });
    expect(first.input.value).toBe("First");
    cleanup();

    const second = renderModal({ defaultName: "Second" });
    expect(second.input.value).toBe("Second");
  });

  it("keeps what the user typed", () => {
    const { input } = renderModal({ defaultName: "Preset" });

    fireEvent.change(input, { target: { value: "My own name" } });

    expect(input.value).toBe("My own name");
  });

  it("submits the trimmed name", () => {
    const { input, onSave, container } = renderModal();

    fireEvent.change(input, { target: { value: "  spaced  " } });
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);

    expect(onSave).toHaveBeenCalledWith("spaced");
  });

  it("refuses to submit a blank name", () => {
    const { input, onSave, container } = renderModal();

    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);

    expect(onSave).not.toHaveBeenCalled();
  });
});
