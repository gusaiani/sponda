// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDragGhost } from "./useDragGhost";

/** Query all ghost elements (fixed-position, pointer-events:none) appended by the hook. */
function getGhosts(): HTMLElement[] {
  return Array.from(document.body.children).filter((child) => {
    const style = (child as HTMLElement).style;
    return style.position === "fixed" && style.pointerEvents === "none";
  }) as HTMLElement[];
}

function createMockElement(
  tagName: string = "DIV",
  rect: Partial<DOMRect> = {},
): HTMLElement {
  const element = document.createElement(tagName);
  element.textContent = "Test content";
  document.body.appendChild(element);

  const defaultRect: DOMRect = {
    x: 100,
    y: 200,
    width: 300,
    height: 150,
    top: 200,
    right: 400,
    bottom: 350,
    left: 100,
    toJSON: () => ({}),
    ...rect,
  };
  vi.spyOn(element, "getBoundingClientRect").mockReturnValue(defaultRect);

  return element;
}

function createMockDragEvent(
  clientX: number = 150,
  clientY: number = 250,
): React.DragEvent {
  const dataTransfer = {
    setDragImage: vi.fn(),
    effectAllowed: "uninitialized" as string,
    dropEffect: "none" as string,
    setData: vi.fn(),
    getData: vi.fn(),
    clearData: vi.fn(),
    types: [] as string[],
    items: {} as DataTransferItemList,
    files: {} as FileList,
  };

  return {
    clientX,
    clientY,
    dataTransfer,
  } as unknown as React.DragEvent;
}

describe("useDragGhost", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("startGhost appends a ghost element to document.body", () => {
    const { result } = renderHook(() => useDragGhost());
    const element = createMockElement();
    const event = createMockDragEvent();

    expect(getGhosts()).toHaveLength(0);

    act(() => {
      result.current.startGhost(element, event);
    });

    expect(getGhosts()).toHaveLength(1);
  });

  it("ghost is positioned at the source element's location", () => {
    const { result } = renderHook(() => useDragGhost());
    const element = createMockElement("DIV", { left: 100, top: 200 });
    const event = createMockDragEvent();

    act(() => {
      result.current.startGhost(element, event);
    });

    const ghost = getGhosts()[0];
    expect(ghost.style.left).toBe("100px");
    expect(ghost.style.top).toBe("200px");
  });

  it("ghost has fixed positioning and is non-interactive", () => {
    const { result } = renderHook(() => useDragGhost());
    const element = createMockElement();
    const event = createMockDragEvent();

    act(() => {
      result.current.startGhost(element, event);
    });

    const ghost = getGhosts()[0];
    expect(ghost.style.position).toBe("fixed");
    expect(ghost.style.pointerEvents).toBe("none");
    expect(ghost.style.zIndex).toBe("10000");
  });

  it("ghost matches source element dimensions", () => {
    const { result } = renderHook(() => useDragGhost());
    const element = createMockElement("DIV", { width: 300, height: 150 });
    const event = createMockDragEvent();

    act(() => {
      result.current.startGhost(element, event);
    });

    const ghost = getGhosts()[0];
    expect(ghost.style.width).toBe("300px");
    expect(ghost.style.height).toBe("150px");
  });

  it("ghost has visual lift effect (rotation, scale, shadow)", () => {
    const { result } = renderHook(() => useDragGhost());
    const element = createMockElement();
    const event = createMockDragEvent();

    act(() => {
      result.current.startGhost(element, event);
    });

    const ghost = getGhosts()[0];
    expect(ghost.style.transform).toBe("rotate(1.5deg) scale(1.03)");
    expect(ghost.style.boxShadow).toContain("rgba(0,0,0,0.18)");
    expect(ghost.style.opacity).toBe("0.92");
  });

  it("hides the browser default drag image with an offscreen DOM element", () => {
    const { result } = renderHook(() => useDragGhost());
    const element = createMockElement();
    const event = createMockDragEvent();

    act(() => {
      result.current.startGhost(element, event);
    });

    expect(event.dataTransfer.setDragImage).toHaveBeenCalledOnce();
    const [dragImage] = (event.dataTransfer.setDragImage as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(dragImage).toBeInstanceOf(HTMLDivElement);
    expect(dragImage.style.width).toBe("1px");
    expect(dragImage.style.height).toBe("1px");
  });

  it("wraps table rows in table > tbody structure for correct rendering", () => {
    const { result } = renderHook(() => useDragGhost());

    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.textContent = "Cell";
    tr.appendChild(td);
    document.body.appendChild(tr);

    vi.spyOn(tr, "getBoundingClientRect").mockReturnValue({
      x: 0, y: 0, width: 500, height: 40,
      top: 0, right: 500, bottom: 40, left: 0,
      toJSON: () => ({}),
    });

    const event = createMockDragEvent(10, 10);

    act(() => {
      result.current.startGhost(tr, event);
    });

    const ghost = getGhosts()[0];
    // Ghost wrapper is a div containing table > tbody > tr
    expect(ghost.tagName).toBe("DIV");
    const table = ghost.querySelector("table");
    expect(table).not.toBeNull();
    const tbody = table!.querySelector("tbody");
    expect(tbody).not.toBeNull();
    const clonedRow = tbody!.querySelector("tr");
    expect(clonedRow).not.toBeNull();
    expect(clonedRow!.querySelector("td")!.textContent).toBe("Cell");
  });

  it("does not wrap non-table elements in table structure", () => {
    const { result } = renderHook(() => useDragGhost());
    const element = createMockElement("DIV");
    const event = createMockDragEvent();

    act(() => {
      result.current.startGhost(element, event);
    });

    const ghost = getGhosts()[0];
    expect(ghost.tagName).toBe("DIV");
    expect(ghost.querySelector("table")).toBeNull();
  });

  it("removes drag-state classes from the ghost clone", () => {
    const { result } = renderHook(() => useDragGhost());
    const element = createMockElement();
    element.classList.add(
      "homepage-grid-item--dragging",
      "homepage-grid-item--drag-over",
      "compare-row-dragging",
      "compare-row-drag-over",
    );
    const event = createMockDragEvent();

    act(() => {
      result.current.startGhost(element, event);
    });

    const ghost = getGhosts()[0];
    expect(ghost.classList.contains("homepage-grid-item--dragging")).toBe(false);
    expect(ghost.classList.contains("homepage-grid-item--drag-over")).toBe(false);
    expect(ghost.classList.contains("compare-row-dragging")).toBe(false);
    expect(ghost.classList.contains("compare-row-drag-over")).toBe(false);
  });

  it("stopGhost removes the ghost from the DOM", () => {
    const { result } = renderHook(() => useDragGhost());
    const element = createMockElement();
    const event = createMockDragEvent();

    act(() => {
      result.current.startGhost(element, event);
    });

    expect(getGhosts()).toHaveLength(1);

    act(() => {
      result.current.stopGhost();
    });

    expect(getGhosts()).toHaveLength(0);
  });

  it("stopGhost is safe to call without an active ghost", () => {
    const { result } = renderHook(() => useDragGhost());

    // Should not throw
    act(() => {
      result.current.stopGhost();
    });
  });

  it("starting a new ghost removes the previous one", () => {
    const { result } = renderHook(() => useDragGhost());
    const element1 = createMockElement();
    const element2 = createMockElement();

    act(() => {
      result.current.startGhost(element1, createMockDragEvent());
    });

    expect(getGhosts()).toHaveLength(1);

    act(() => {
      result.current.startGhost(element2, createMockDragEvent());
    });

    // Previous ghost removed, new ghost added — still exactly 1
    expect(getGhosts()).toHaveLength(1);
  });

  it("ghost follows the cursor via document dragover events", () => {
    const { result } = renderHook(() => useDragGhost());
    const element = createMockElement("DIV", {
      left: 100, top: 200, width: 300, height: 150,
    });
    // Mouse starts at (150, 250) — offset from element is (50, 50)
    const event = createMockDragEvent(150, 250);

    act(() => {
      result.current.startGhost(element, event);
    });

    const ghost = getGhosts()[0];

    // Simulate document dragover at new position
    act(() => {
      const dragOverEvent = new MouseEvent("dragover", {
        clientX: 400,
        clientY: 500,
      });
      document.dispatchEvent(dragOverEvent);
    });

    // Ghost should be at (400-50, 500-50) = (350, 450)
    expect(ghost.style.left).toBe("350px");
    expect(ghost.style.top).toBe("450px");
  });

  it("ghost ignores dragover events with (0,0) coordinates", () => {
    const { result } = renderHook(() => useDragGhost());
    const element = createMockElement("DIV", { left: 100, top: 200 });
    const event = createMockDragEvent(150, 250);

    act(() => {
      result.current.startGhost(element, event);
    });

    const ghost = getGhosts()[0];
    const initialLeft = ghost.style.left;
    const initialTop = ghost.style.top;

    // Simulate a (0,0) dragover (browser artifact at drag end)
    act(() => {
      const dragOverEvent = new MouseEvent("dragover", {
        clientX: 0,
        clientY: 0,
      });
      document.dispatchEvent(dragOverEvent);
    });

    // Position should not change
    expect(ghost.style.left).toBe(initialLeft);
    expect(ghost.style.top).toBe(initialTop);
  });

  it("stops tracking dragover after stopGhost is called", () => {
    const { result } = renderHook(() => useDragGhost());
    const element = createMockElement("DIV", { left: 100, top: 200 });
    const event = createMockDragEvent(150, 250);

    act(() => {
      result.current.startGhost(element, event);
    });

    act(() => {
      result.current.stopGhost();
    });

    // Ghost is removed, dragover should not throw
    act(() => {
      const dragOverEvent = new MouseEvent("dragover", {
        clientX: 999,
        clientY: 999,
      });
      document.dispatchEvent(dragOverEvent);
    });

    // No ghost in the DOM
    expect(document.body.querySelectorAll("[style*='position: fixed']").length).toBe(0);
  });

  it("cleans up ghost element on unmount", () => {
    const { result, unmount } = renderHook(() => useDragGhost());
    const element = createMockElement();
    const event = createMockDragEvent();

    act(() => {
      result.current.startGhost(element, event);
    });

    expect(getGhosts()).toHaveLength(1);

    unmount();

    expect(getGhosts()).toHaveLength(0);
  });
});
