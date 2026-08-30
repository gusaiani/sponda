import { describe, it, expect } from "vitest";
import { buildOgImageResponse, OG_IMAGE_CACHE_CONTROL } from "./og-response";

const BYTES = Uint8Array.from([1, 2, 3, 4, 5]);

describe("buildOgImageResponse", () => {
  it("announces the byte count up front so a HEAD-first crawler can size the image", async () => {
    const response = buildOgImageResponse(BYTES, "image/png");
    expect(response.headers.get("content-length")).toBe("5");
    expect(new Uint8Array(await response.arrayBuffer())).toEqual(BYTES);
  });

  it("carries the MIME type it was given", () => {
    expect(buildOgImageResponse(BYTES, "image/jpeg").headers.get("content-type")).toBe("image/jpeg");
  });

  it("is public and long-lived at the edge, short in the browser", () => {
    const cacheControl = buildOgImageResponse(BYTES, "image/png").headers.get("cache-control");
    expect(cacheControl).toBe(OG_IMAGE_CACHE_CONTROL);
    expect(cacheControl).toContain("public");
    expect(cacheControl).toContain("s-maxage=86400");
  });

  it("offers no validators, so a crawler re-downloads instead of revalidating a stuck copy", () => {
    const response = buildOgImageResponse(BYTES, "image/jpeg");
    expect(response.headers.get("etag")).toBeNull();
    expect(response.headers.get("last-modified")).toBeNull();
    expect(response.headers.get("accept-ranges")).toBeNull();
  });
});
