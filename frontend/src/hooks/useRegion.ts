import { useState, useEffect } from "react";
import { type Region, detectRegion } from "../utils/region";

/**
 * Detects the user's region from their browser timezone.
 * Returns "brazil" during SSR and before hydration to match the server default.
 */
export function useRegion(): Region {
  const [region, setRegion] = useState<Region>("brazil");

  useEffect(() => {
    setRegion(detectRegion());
  }, []);

  return region;
}
