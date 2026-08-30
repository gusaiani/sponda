import { describe, it, expect } from "vitest";
import { withJpegComment, readJpegComments } from "./jpeg-comment";

const SOI = [0xff, 0xd8];
const APP0 = [0xff, 0xe0, 0x00, 0x04, 0x4a, 0x46];
const EXISTING_COMMENT = [0xff, 0xfe, 0x00, 0x05, 0x6f, 0x6c, 0x64];
const QUANTIZATION_TABLE = [0xff, 0xdb, 0x00, 0x03, 0x01];
const START_OF_SCAN = [0xff, 0xda, 0x00, 0x02, 0x00, 0x11, 0x22];

function jpeg(...segments: number[][]): Uint8Array {
  return Uint8Array.from(segments.flat());
}

describe("withJpegComment", () => {
  it("inserts a COM segment right after APP0 when the file has none", () => {
    const source = jpeg(SOI, APP0, QUANTIZATION_TABLE, START_OF_SCAN);
    const stamped = withJpegComment(source, "hi");
    expect(readJpegComments(stamped)).toEqual(["hi"]);
    expect(Array.from(stamped.slice(0, 8))).toEqual([...SOI, ...APP0]);
    expect(Array.from(stamped.slice(-START_OF_SCAN.length))).toEqual(START_OF_SCAN);
  });

  it("replaces an existing COM segment instead of stacking a second one", () => {
    const source = jpeg(SOI, APP0, EXISTING_COMMENT, QUANTIZATION_TABLE, START_OF_SCAN);
    const stamped = withJpegComment(source, "new");
    expect(readJpegComments(stamped)).toEqual(["new"]);
  });

  it("changes the bytes, which is the whole point of stamping", () => {
    const source = jpeg(SOI, APP0, EXISTING_COMMENT, QUANTIZATION_TABLE, START_OF_SCAN);
    expect(Buffer.from(withJpegComment(source, "a")).equals(Buffer.from(withJpegComment(source, "b")))).toBe(false);
  });

  it("leaves the entropy-coded scan untouched", () => {
    const source = jpeg(SOI, APP0, QUANTIZATION_TABLE, START_OF_SCAN);
    const stamped = withJpegComment(source, "x");
    expect(Array.from(stamped.slice(-START_OF_SCAN.length))).toEqual(START_OF_SCAN);
  });

  it("rejects bytes that are not a JPEG", () => {
    expect(() => withJpegComment(Uint8Array.from([0x89, 0x50, 0x4e, 0x47]), "x")).toThrow(/JPEG/);
  });
});
