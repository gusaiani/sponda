// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { DualRangeSlider } from "./DualRangeSlider";

afterEach(cleanup);

describe("DualRangeSlider", () => {
  it("renders two range inputs with the track bounds", () => {
    const { container } = render(
      <DualRangeSlider
        trackMin={0}
        trackMax={50}
        step={1}
        minValue={null}
        maxValue={null}
        onChange={() => {}}
      />,
    );
    const inputs = container.querySelectorAll("input[type='range']");
    expect(inputs).toHaveLength(2);
    for (const input of inputs) {
      expect(input.getAttribute("min")).toBe("0");
      expect(input.getAttribute("max")).toBe("50");
      expect(input.getAttribute("step")).toBe("1");
    }
  });

  it("shows handles at extremes when min/max values are null", () => {
    const { container } = render(
      <DualRangeSlider
        trackMin={0}
        trackMax={50}
        step={1}
        minValue={null}
        maxValue={null}
        onChange={() => {}}
      />,
    );
    const [minInput, maxInput] = container.querySelectorAll("input[type='range']");
    expect((minInput as HTMLInputElement).value).toBe("0");
    expect((maxInput as HTMLInputElement).value).toBe("50");
  });

  it("fires onChange with new min when the min handle moves up", () => {
    const onChange = vi.fn();
    const { container } = render(
      <DualRangeSlider
        trackMin={0}
        trackMax={50}
        step={1}
        minValue={null}
        maxValue={null}
        onChange={onChange}
      />,
    );
    const [minInput] = container.querySelectorAll("input[type='range']");
    fireEvent.change(minInput, { target: { value: "10" } });
    expect(onChange).toHaveBeenCalledWith({ min: "10", max: null });
  });

  it("clears the side that sits at its extreme after a change", () => {
    const onChange = vi.fn();
    const { container } = render(
      <DualRangeSlider
        trackMin={0}
        trackMax={50}
        step={1}
        minValue="10"
        maxValue={null}
        onChange={onChange}
      />,
    );
    const [minInput] = container.querySelectorAll("input[type='range']");
    // Move the min handle back to the extreme — should clear it.
    fireEvent.change(minInput, { target: { value: "0" } });
    expect(onChange).toHaveBeenCalledWith({ min: null, max: null });
  });

  it("prevents the min handle from crossing the max handle", () => {
    const onChange = vi.fn();
    const { container } = render(
      <DualRangeSlider
        trackMin={0}
        trackMax={50}
        step={1}
        minValue={null}
        maxValue="20"
        onChange={onChange}
      />,
    );
    const [minInput] = container.querySelectorAll("input[type='range']");
    fireEvent.change(minInput, { target: { value: "30" } });
    // Should clamp to the max handle's value (20).
    expect(onChange).toHaveBeenCalledWith({ min: "20", max: "20" });
  });

  it("prevents the max handle from going below the min handle", () => {
    const onChange = vi.fn();
    const { container } = render(
      <DualRangeSlider
        trackMin={0}
        trackMax={50}
        step={1}
        minValue="20"
        maxValue={null}
        onChange={onChange}
      />,
    );
    const [, maxInput] = container.querySelectorAll("input[type='range']");
    fireEvent.change(maxInput, { target: { value: "10" } });
    expect(onChange).toHaveBeenCalledWith({ min: "20", max: "20" });
  });

  it("uses provided format function for the value labels", () => {
    const { getByText } = render(
      <DualRangeSlider
        trackMin={0}
        trackMax={1_000_000_000_000}
        step={10_000_000_000}
        minValue={null}
        maxValue={null}
        format={(value) => `R$ ${value / 1e9}B`}
        onChange={() => {}}
      />,
    );
    expect(getByText("R$ 0B")).toBeTruthy();
    expect(getByText("R$ 1000B")).toBeTruthy();
  });
});
