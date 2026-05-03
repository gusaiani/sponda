// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import { DualRangeSlider, SLIDER_SCALE_RESOLUTION } from "./DualRangeSlider";
import { LEVERAGE_SCALE } from "../utils/sliderScale";

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

  describe("with a non-linear scale", () => {
    it("drives the underlying inputs in normalized position space", () => {
      const { container } = render(
        <DualRangeSlider
          trackMin={0}
          trackMax={100}
          step={0.05}
          scale={LEVERAGE_SCALE}
          minValue={null}
          maxValue={null}
          onChange={() => {}}
        />,
      );
      const inputs = container.querySelectorAll("input[type='range']");
      for (const input of inputs) {
        expect(input.getAttribute("min")).toBe("0");
        expect(input.getAttribute("max")).toBe(String(SLIDER_SCALE_RESOLUTION));
        expect(input.getAttribute("step")).toBe("1");
      }
      const [minInput, maxInput] = inputs;
      expect((minInput as HTMLInputElement).value).toBe("0");
      expect((maxInput as HTMLInputElement).value).toBe(
        String(SLIDER_SCALE_RESOLUTION),
      );
    });

    it("places handles at the scaled position for the current value", () => {
      const { container } = render(
        <DualRangeSlider
          trackMin={0}
          trackMax={100}
          step={0.05}
          scale={LEVERAGE_SCALE}
          minValue="1"
          maxValue={null}
          onChange={() => {}}
        />,
      );
      const [minInput] = container.querySelectorAll("input[type='range']");
      // value 1 sits at the boundary between bands → position 0.55.
      expect((minInput as HTMLInputElement).value).toBe(
        String(Math.round(0.55 * SLIDER_SCALE_RESOLUTION)),
      );
    });

    it("converts handle motion through the scale before storing the value", () => {
      const onChange = vi.fn();
      const { container } = render(
        <DualRangeSlider
          trackMin={0}
          trackMax={100}
          step={0.05}
          scale={LEVERAGE_SCALE}
          minValue={null}
          maxValue={null}
          onChange={onChange}
        />,
      );
      const [minInput] = container.querySelectorAll("input[type='range']");
      // Position 0.55 of the track → value 1 after snapping.
      fireEvent.change(minInput, {
        target: { value: String(Math.round(0.55 * SLIDER_SCALE_RESOLUTION)) },
      });
      expect(onChange).toHaveBeenCalledWith({ min: "1", max: null });
    });

    it("snaps high-band values to the nearest 5 increment", () => {
      const onChange = vi.fn();
      const { container } = render(
        <DualRangeSlider
          trackMin={0}
          trackMax={100}
          step={0.05}
          scale={LEVERAGE_SCALE}
          minValue={null}
          maxValue={null}
          onChange={onChange}
        />,
      );
      const [, maxInput] = container.querySelectorAll("input[type='range']");
      // Position for value 47 → ~0.927; after snap should land on 45.
      const position = LEVERAGE_SCALE.toPosition(47);
      fireEvent.change(maxInput, {
        target: { value: String(Math.round(position * SLIDER_SCALE_RESOLUTION)) },
      });
      expect(onChange).toHaveBeenCalledWith({ min: null, max: "45" });
    });
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
