import { describe, it, expect } from "vitest";
import { parseSseFrames } from "./useAssistantStream";

describe("parseSseFrames", () => {
  it("parses complete frames and holds back the incomplete tail", () => {
    const buffer = 
      'event: meta\ndata: {"ticker":"PETR4"}\n\n' +
      'event: token\ndata: "PETR4 "\n\n' +
      'event: token\ndata: "is che';
    
    const { frames, rest } = parseSseFrames(buffer);
    
    expect(frames).toEqual([
      { event: "meta", data: '{"ticker":"PETR4"}' },
      { event: "token", data: '"PETR4 "' },
    ]);
    expect(rest).toBe('event: token\ndata: "is che');
  })
});