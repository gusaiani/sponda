import { describe, it, expect } from "vitest";
import { parseSseFrames, applyFrame, INITIAL_ASSISTANT_STATE } from "./useAssistantStream";

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

describe("applyFrame", () => {
  it ("folds meta → token → token → done into accumulated answer text", () => {
    const afterMeta = applyFrame(INITIAL_ASSISTANT_STATE, {
      event: "meta",
      data: '{"classification":"on_topic", "model": "gpt-4o"}',
    });
    expect(afterMeta.status).toBe("streaming");
    expect(afterMeta.classification).toBe("on_topic");

    const afterFirstToken = applyFrame(afterMeta, {
      event: "token",
      data: '"PETR4 "',
    });
    const afterSecondToken = applyFrame(afterFirstToken, {
      event: "token",
      data: '"is cheap."',
    });
    expect(afterSecondToken.answer).toBe("PETR4 is cheap.");

    const afterDone = applyFrame(afterSecondToken, {
      event: "done",
      data: '{"input_tokens":42, "output_tokens":7}'
    });
    
    expect(afterDone.status).toBe("done");
    expect(afterDone.answer).toBe("PETR4 is cheap.");
  })
})