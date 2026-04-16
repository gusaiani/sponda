import { RefObject, useEffect } from "react";

interface Options {
  ref: RefObject<Element | null>;
  onVisible: () => void;
  enabled: boolean;
}

/**
 * Fire `onVisible` whenever the element behind `ref` scrolls into view.
 * When `enabled` is false the observer is not created at all, which lets the
 * caller pause listening once there are no more pages to load.
 */
export function useInfiniteScrollTrigger({ ref, onVisible, enabled }: Options): void {
  useEffect(() => {
    if (!enabled) return;
    const element = ref.current;
    if (!element) return;

    // Fire a bit before the sentinel reaches the viewport so users never see
    // a hard stop while the next page is loading.
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            onVisible();
          }
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(element);

    return () => observer.disconnect();
  }, [enabled, onVisible, ref]);
}
