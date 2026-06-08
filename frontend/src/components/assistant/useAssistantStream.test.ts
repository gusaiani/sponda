// @vitest-environment jsdom

import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { AssistantContext, AssistantState, buildAskRequest, parseSseFrames, applyFrame, readAssistantStream, ASSISTANT_ASK_URL, INITIAL_ASSISTANT_STATE, useAssistantStream } from "./useAssistantStream";

function streamingResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    }
  });
  return new Response(body);
};

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
  });

  it("off_topic frame puts the canned redirect text in answer and stops", () => {
    // The guardrail rejected the question — server streams one off_topic
    // frame whose data is the localized redirect string, then done.
    const redirect = applyFrame(INITIAL_ASSISTANT_STATE, {
      event: "off_topic",
      data: '"Só posso responder perguntas sobre esta empresa."',
    });

    expect(redirect.status).toBe("off_topic");
    expect(redirect.answer).toBe(
      "Só posso responder perguntas sobre esta empresa.",
    );
  });

  it("error frame records the machine-readable code", () => {
    // Upstream failed mid-stream; the code drives which localized error
    // message the component shows (rate_limited vs upstream_timeout, etc.).
    const failed = applyFrame(INITIAL_ASSISTANT_STATE, {
      event: "error",
      data: '{"code":"upstream_timeout"}',
    });

    expect(failed.status).toBe("error");
    expect(failed.errorCode).toBe("upstream_timeout");
  });
});

describe("readAssistantStream", () => {
  it("accumulates tokens across chunks boundaries and ends done", async () => {
    const response = streamingResponse([
      'event: meta\ndata: {"classification": "on_topic"}\n\n',
      'event: token\ndata: "PETR4 "\n\nevent: token\ndata: "is ',
      'cheap."\n\nevent: done\ndata: {}\n\n',
    ]);

    const snapshots: AssistantState[] = [];
    const finalState = await readAssistantStream(response, (state) => {
      snapshots.push(state);
    });

    expect(finalState.status).toBe("done");
    expect(finalState.answer).toBe("PETR4 is cheap.");
    // The UI must have seen the answer grow, not appear all at once.
    expect(snapshots.some((snapshot) => snapshot.answer === "PETR4 ")).toBe(true);
  });
});

describe("buildAskRequest", () => {
  it("builds a POST with credentials, csrf headers, and a JSON context body", () => {
    const context: AssistantContext = {
      ticker: "PETR4",
      tab: "metrics",
      locale: "pt",
      question: "Is PETR4 cheap?",
    };
    const controller = new AbortController();

    const request = buildAskRequest(context, controller.signal);

    expect(request.method).toBe("POST");
    // Session-cookie auth - the backend reads request.user from the cookie.
    expect(request.credentials).toBe("include");

    const headers = request.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers).toHaveProperty("X-CSRFToken");

    // Body must equal context
    expect(JSON.parse(request.body as string)).toEqual(context);

    expect(request.signal).toBe(controller.signal);
  })
});

describe("useAssistantStream hook", () => {
  // stubGlobal swaps window.fetch; undo it so other tests see the real one.
  afterEach(() => vi.unstubAllGlobals());

  it("streams an answer and ends in the done state", async () => {
    const response = streamingResponse([
      'event: meta\ndata: {"classification":"on_topic"}\n\n',
      'event: token\ndata: "PETR4 is cheap."\n\n',
      'event: done\ndata: {}\n\n',
    ]);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    const { result } = renderHook(() => useAssistantStream());

    await act(async () => {
      await result.current.ask({
        ticker: "PETR4",
        tab: "metrics",
        locale: "pt",
        question: "Is it cheap?",
      });
    });

    expect(result.current.state.status).toBe("done");
    expect(result.current.state.answer).toBe("PETR4 is cheap.");
  });

  it.each([
    [403, "ASSISTANT_FORBIDDEN"],
    [429, "assistant_limit"],
  ])("maps a %i response to an error state with code %s", async (httpStatus, expectedCode) => {
    const response = new Response(null, { status: httpStatus });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    const { result } = renderHook(() => useAssistantStream());

    await act(async () => {
      await result.current.ask({
        ticker: "PETR4",
        tab: "metrics",
        locale: "pt",
        question: "Is it cheap?",
      });
    });

    expect(result.current.state.status).toBe("error");
    expect(result.current.state.errorCode).toBe(expectedCode);
  })

  it("aborts the in-flight request when the component unmounts", async () => {
    const neverResolves = new Promise<Response>(() => {});
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(neverResolves));

    const abortSpy = vi.spyOn(AbortController.prototype, "abort");

    const { result, unmount } = renderHook(() => useAssistantStream());

    // Fire ask() but don't await, as it never settles
    act(() => {
      void result.current.ask({
        ticker: "PETR4",
        tab: "metrics",
        locale: "pt",
        question: "Is it cheap?",
      });
    });

    unmount();

    expect(abortSpy).toHaveBeenCalled();

    abortSpy.mockRestore();
  });
});