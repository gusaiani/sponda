import { describe, it, expect } from "vitest";
import { readJpegComments } from "../../../../lib/jpeg-comment";

const JPEG_START_OF_IMAGE = [0xff, 0xd8];

async function get(card: string): Promise<Response> {
  const { GET } = await import("./route");
  return GET(new Request(`https://sponda.capital/og/site/${card}`), {
    params: Promise.resolve({ card }),
  });
}

describe("GET /og/site/<artwork>.jpg", () => {
  it("serves the English artwork as a JPEG with its length announced", async () => {
    const response = await get("en.jpg");
    const bytes = new Uint8Array(await response.arrayBuffer());
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("image/jpeg");
    expect(response.headers.get("content-length")).toBe(String(bytes.byteLength));
    expect(Array.from(bytes.slice(0, 2))).toEqual(JPEG_START_OF_IMAGE);
  });

  it("serves distinct Portuguese artwork", async () => {
    const english = new Uint8Array(await (await get("en.jpg")).arrayBuffer());
    const portuguese = new Uint8Array(await (await get("pt.jpg")).arrayBuffer());
    expect(Buffer.from(english).equals(Buffer.from(portuguese))).toBe(false);
  });

  it("stamps the bytes so they cannot be content-deduplicated onto an older URL", async () => {
    const bytes = new Uint8Array(await (await get("en.jpg")).arrayBuffer());
    expect(readJpegComments(bytes)).toEqual(["Sponda OG site card en /og/site"]);
  });

  it("sends no validators, only a public cache policy", async () => {
    const response = await get("en.jpg");
    expect(response.headers.get("etag")).toBeNull();
    expect(response.headers.get("last-modified")).toBeNull();
    expect(response.headers.get("accept-ranges")).toBeNull();
    expect(response.headers.get("cache-control")).toContain("public");
  });

  it("404s for anything that is not one of the two artworks", async () => {
    expect((await get("es.jpg")).status).toBe(404);
    expect((await get("en.png")).status).toBe(404);
    expect((await get("sponda-og-en-v2.jpg")).status).toBe(404);
  });
});
