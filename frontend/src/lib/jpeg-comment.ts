/**
 * Stamp a JPEG with a COM (comment) segment.
 *
 * Social networks key their image caches by URL, but some also fingerprint
 * the bytes. When a card has to move to a fresh URL because a network's
 * cache entry for the old one is stuck, byte-identical content risks being
 * deduplicated straight back onto the stuck entry. A comment segment changes
 * the bytes without touching a single pixel.
 */

const START_OF_IMAGE = 0xd8;
const APP0 = 0xe0;
const COMMENT = 0xfe;
const START_OF_SCAN = 0xda;
const MARKER_PREFIX = 0xff;
const MARKER_LENGTH = 2;
const SEGMENT_LENGTH_FIELD = 2;

interface JpegSegment {
  marker: number;
  bytes: Uint8Array;
}

function assertJpeg(bytes: Uint8Array): void {
  if (bytes.length < MARKER_LENGTH || bytes[0] !== MARKER_PREFIX || bytes[1] !== START_OF_IMAGE) {
    throw new Error("Not a JPEG: missing SOI marker");
  }
}

/** Split the header into marker segments; the scan (and everything after it) is returned whole. */
function splitSegments(bytes: Uint8Array): { segments: JpegSegment[]; scan: Uint8Array } {
  const segments: JpegSegment[] = [];
  let offset = MARKER_LENGTH;
  while (offset + MARKER_LENGTH <= bytes.length && bytes[offset] === MARKER_PREFIX) {
    const marker = bytes[offset + 1];
    if (marker === START_OF_SCAN) break;
    const length = (bytes[offset + 2] << 8) | bytes[offset + 3];
    const end = offset + MARKER_LENGTH + length;
    segments.push({ marker, bytes: bytes.slice(offset, end) });
    offset = end;
  }
  return { segments, scan: bytes.slice(offset) };
}

function buildCommentSegment(comment: string): Uint8Array {
  const text = new TextEncoder().encode(comment);
  const length = SEGMENT_LENGTH_FIELD + text.length;
  const segment = new Uint8Array(MARKER_LENGTH + length);
  segment[0] = MARKER_PREFIX;
  segment[1] = COMMENT;
  segment[2] = length >> 8;
  segment[3] = length & 0xff;
  segment.set(text, MARKER_LENGTH + SEGMENT_LENGTH_FIELD);
  return segment;
}

function concat(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

/**
 * Return a copy of `bytes` whose only COM segment carries `comment`,
 * placed right after APP0 (or first, if there is no APP0). Existing
 * comments are dropped. Pixels are untouched.
 */
export function withJpegComment(bytes: Uint8Array, comment: string): Uint8Array {
  assertJpeg(bytes);
  const { segments, scan } = splitSegments(bytes);
  const kept = segments.filter((segment) => segment.marker !== COMMENT);
  const app0Index = kept.findIndex((segment) => segment.marker === APP0);
  const insertAt = app0Index === -1 ? 0 : app0Index + 1;
  kept.splice(insertAt, 0, { marker: COMMENT, bytes: buildCommentSegment(comment) });
  return concat([bytes.slice(0, MARKER_LENGTH), ...kept.map((segment) => segment.bytes), scan]);
}

/** Every COM segment's text, in file order. */
export function readJpegComments(bytes: Uint8Array): string[] {
  assertJpeg(bytes);
  const { segments } = splitSegments(bytes);
  return segments
    .filter((segment) => segment.marker === COMMENT)
    .map((segment) => new TextDecoder().decode(segment.bytes.slice(MARKER_LENGTH + SEGMENT_LENGTH_FIELD)));
}
