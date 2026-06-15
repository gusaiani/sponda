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

describe("ASSISTANT_ASK_URL", () => {
  it("targets Django's trailing-slash route", () => {
    // Django's route is `assistant/ask/` (APPEND_SLASH on). A slashless
    // POST can't be redirected (Django raises rather than 301 a POST body),
    // so it 500s before the view ever runs. The slash is mandatory. The URL
    // may carry a dev origin prefix (direct-to-Django), so match the suffix.
    expect(ASSISTANT_ASK_URL.endsWith("/api/assistant/ask/")).toBe(true);
  });
});

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

  const askContext: AssistantContext = {
    ticker: "PETR4",
    tab: "metrics",
    locale: "pt",
    question: "Is it cheap?",
  };

  it("reads the specific code from a 503 JSON body", async () => {
    // The backend short-circuits with 503 + {"code": ...} when no API key
    // is set; the specific code drives the developer hint in the UI.
    const response = new Response(
      JSON.stringify({ code: "assistant_not_configured" }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    );
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    const { result } = renderHook(() => useAssistantStream());
    await act(async () => {
      await result.current.ask(askContext);
    });

    expect(result.current.state.status).toBe("error");
    expect(result.current.state.errorCode).toBe("assistant_not_configured");
  });

  it("falls back to a generic unavailable code for a 503 with no body", async () => {
    const response = new Response(null, { status: 503 });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    const { result } = renderHook(() => useAssistantStream());
    await act(async () => {
      await result.current.ask(askContext);
    });

    expect(result.current.state.status).toBe("error");
    expect(result.current.state.errorCode).toBe("assistant_unavailable");
  });

  it("records the real HTTP status on a non-OK response", async () => {
    // The status drives the developer hint — it must reflect what the
    // backend actually returned (e.g. a 500), not a hardcoded guess.
    const response = new Response(null, { status: 500 });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    const { result } = renderHook(() => useAssistantStream());
    await act(async () => {
      await result.current.ask(askContext);
    });

    expect(result.current.state.status).toBe("error");
    expect(result.current.state.httpStatus).toBe(500);
  });

  it("flags a stream that ends with no terminal frame as interrupted", async () => {
    // 200 OK, but the body dies after meta + a token — no done/off_topic/
    // error. This is exactly what a backend that throws after committing
    // the 200 produces. Without detection the UI hangs on 'streaming'.
    const response = streamingResponse([
      'event: meta\ndata: {"classification":"on_topic"}\n\n',
      'event: token\ndata: "PETR4 "\n\n',
    ]);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    const { result } = renderHook(() => useAssistantStream());
    await act(async () => {
      await result.current.ask(askContext);
    });

    expect(result.current.state.status).toBe("error");
    expect(result.current.state.errorCode).toBe("assistant_interrupted");
    // The partial answer stays visible above the error message.
    expect(result.current.state.answer).toBe("PETR4 ");
  });

  it("flags an empty 200 body as interrupted", async () => {
    const response = streamingResponse([]);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    const { result } = renderHook(() => useAssistantStream());
    await act(async () => {
      await result.current.ask(askContext);
    });

    expect(result.current.state.status).toBe("error");
    expect(result.current.state.errorCode).toBe("assistant_interrupted");
  });

  it("maps a fetch failure to the network error code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    const { result } = renderHook(() => useAssistantStream());
    await act(async () => {
      await result.current.ask(askContext);
    });

    expect(result.current.state.status).toBe("error");
    expect(result.current.state.errorCode).toBe("network");
  });

  it("does not surface an error when the request is aborted", async () => {
    // Stop button / unmount aborts the fetch — that's deliberate, not a
    // failure, so the UI must not flash an error message.
    const abortError = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError));

    const { result } = renderHook(() => useAssistantStream());
    await act(async () => {
      await result.current.ask(askContext);
    });

    expect(result.current.state.status).not.toBe("error");
    expect(result.current.state.errorCode).toBeNull();
  });

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