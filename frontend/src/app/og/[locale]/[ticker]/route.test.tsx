import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const FAKE_PNG = Uint8Array.from([0x89, 0x50, 0x4e, 0x47, 0, 1, 2, 3]);

vi.mock("next/og", () => ({
  ImageResponse: class extends Response {
    constructor() {
      super(FAKE_PNG, { headers: { "Content-Type": "image/png" } });
    }
  },
}));

async function get(locale: string, ticker: string): Promise<Response> {
  const { GET } = await import("./route");
  return GET(new Request(`https://sponda.capital/og/${locale}/${ticker}`), {
    params: Promise.resolve({ locale, ticker }),
  });
}

describe("GET /og/<locale>/<TICKER>.png", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 200 })));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("announces the byte count so a HEAD-first crawler can size the card", async () => {
    const response = await get("pt", "VULC3.png");
    const bytes = new Uint8Array(await response.arrayBuffer());
    expect(response.status).toBe(200);
    expect(bytes).toEqual(FAKE_PNG);
    expect(response.headers.get("content-length")).toBe(String(FAKE_PNG.byteLength));
    expect(response.headers.get("content-type")).toBe("image/png");
  });

  it("keeps the public, edge-cached policy", async () => {
    const response = await get("pt", "VULC3.png");
    expect(response.headers.get("cache-control")).toContain("public");
    expect(response.headers.get("cache-control")).toContain("s-maxage=86400");
  });

  it("404s an unknown locale and a non-card filename", async () => {
    expect((await get("xx", "VULC3.png")).status).toBe(404);
    expect((await get("pt", "VULC3")).status).toBe(404);
  });
});
