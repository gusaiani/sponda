import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Creates a DOM-cloned ghost element that follows the cursor during HTML5 drag operations.
 * Hides the browser's default drag image and renders a styled floating clone instead.
 */
export function useDragGhost() {
  const ghostRef = useRef<HTMLElement | null>(null);
  const offsetRef = useRef({ x: 0, y: 0 });
  const [active, setActive] = useState(false);

  const startGhost = useCallback((element: HTMLElement, event: React.DragEvent) => {
    ghostRef.current?.remove();

    const rect = element.getBoundingClientRect();
    const isTableRow = element.tagName === "TR";

    // Table rows need a wrapping table structure to render correctly outside the DOM
    let ghost: HTMLElement;
    if (isTableRow) {
      const wrapper = document.createElement("div");
      const table = document.createElement("table");
      const tbody = document.createElement("tbody");
      const clonedRow = element.cloneNode(true) as HTMLElement;
      tbody.appendChild(clonedRow);
      table.appendChild(tbody);
      table.style.borderCollapse = "collapse";
      table.style.width = `${rect.width}px`;
      wrapper.appendChild(table);
      ghost = wrapper;
    } else {
      ghost = element.cloneNode(true) as HTMLElement;
    }

    Object.assign(ghost.style, {
      position: "fixed",
      pointerEvents: "none",
      zIndex: "10000",
      width: `${rect.width}px`,
      height: `${rect.height}px`,
      opacity: "0.92",
      transform: "rotate(1.5deg) scale(1.03)",
      boxShadow: "0 16px 40px rgba(0,0,0,0.18), 0 2px 8px rgba(0,0,0,0.08)",
      transition: "transform 0.12s ease",
      borderRadius: "8px",
      left: `${rect.left}px`,
      top: `${rect.top}px`,
      background: "#ffffff",
      overflow: "hidden",
    });

    // Remove any drag-state classes from the clone
    ghost.classList.remove(
      "homepage-grid-item--dragging",
      "homepage-grid-item--drag-over",
      "compare-row-dragging",
      "compare-row-drag-over",
    );

    document.body.appendChild(ghost);
    ghostRef.current = ghost;

    offsetRef.current = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };

    // Hide the browser's default drag image with an offscreen transparent element.
    // The element must be in the DOM or some browsers show a fallback icon (globe).
    const emptyDragImage = document.createElement("div");
    Object.assign(emptyDragImage.style, {
      position: "absolute",
      top: "-9999px",
      left: "-9999px",
      width: "1px",
      height: "1px",
      opacity: "0.01",
    });
    document.body.appendChild(emptyDragImage);
    event.dataTransfer.setDragImage(emptyDragImage, 0, 0);
    // Clean up after the browser captures the drag image (next frame)
    requestAnimationFrame(() => emptyDragImage.remove());

    setActive(true);
  }, []);

  const stopGhost = useCallback(() => {
    ghostRef.current?.remove();
    ghostRef.current = null;
    setActive(false);
  }, []);

  // Track cursor position via document-level dragover and move the ghost
  useEffect(() => {
    if (!active) return;

    function handleDragOver(event: DragEvent) {
      // Some browsers send (0,0) at drag end — ignore those
      if (ghostRef.current && event.clientX !== 0 && event.clientY !== 0) {
        ghostRef.current.style.left = `${event.clientX - offsetRef.current.x}px`;
        ghostRef.current.style.top = `${event.clientY - offsetRef.current.y}px`;
      }
    }

    document.addEventListener("dragover", handleDragOver);
    return () => document.removeEventListener("dragover", handleDragOver);
  }, [active]);

  // Safety cleanup on unmount
  useEffect(() => {
    return () => {
      ghostRef.current?.remove();
    };
  }, []);

  return { startGhost, stopGhost };
}
