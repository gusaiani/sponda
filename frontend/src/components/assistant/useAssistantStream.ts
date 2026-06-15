import { useCallback, useEffect, useRef, useState } from "react";
import { csrfHeaders } from "../../utils/csrf";

export interface SseFrame {
  event: string;
  data: string;
}

export interface AssistantContext {
  ticker: string;
  tab: string;
  locale: string;
  question: string;
}

// The assistant streams Server-Sent Events. In development the browser posts
// directly to Django (cross-origin, credentialed): Next's dev server can't
// proxy a streaming text/event-stream to a browser's incremental reader
// without breaking the chunked framing. In production the request is
// same-origin and nginx routes /api/assistant/ask straight to Django (the
// SSE bypass). Trailing slash is required — Django's route is `assistant/ask/`
// with APPEND_SLASH, so a slashless POST 500s before the view runs.
const ASSISTANT_ASK_PATH = "/api/assistant/ask/";
const ASSISTANT_DEV_API_ORIGIN =
  process.env.NEXT_PUBLIC_DEV_API_ORIGIN || "http://localhost:8710";
export const ASSISTANT_ASK_URL =
  process.env.NODE_ENV === "production"
    ? ASSISTANT_ASK_PATH
    : `${ASSISTANT_DEV_API_ORIGIN}${ASSISTANT_ASK_PATH}`;

const FRAME_DELIMITER = "\n\n";

const ASSISTANT_ERROR_CODE_BY_STATUS: Record<number, string> = {
  403: "ASSISTANT_FORBIDDEN",  // backend's superuser/tier gate rejected
  429: "assistant_limit",      // daily quota exhausted
  503: "assistant_unavailable", // service down / not configured
};

// Any non-OK status without a more specific mapping or body code lands here.
const FALLBACK_HTTP_ERROR_CODE = "assistant_unavailable";

// A healthy stream always ends on one of these. Anything else means the
// connection dropped mid-answer.
const TERMINAL_STATUSES: ReadonlySet<AssistantState["status"]> = new Set([
  "done",
  "off_topic",
  "error",
]);

/** Pull the most specific error code out of a non-OK response. A JSON body
 * like {"code":"assistant_not_configured"} wins — it lets the UI show a
 * developer-specific hint — otherwise fall back to a status-based code. */
async function resolveHttpErrorCode(response: Response): Promise<string> {
  try {
    const body = (await response.clone().json()) as { code?: unknown };
    if (typeof body.code === "string" && body.code) {
      return body.code;
    }
  } catch {
    // Empty or non-JSON body (e.g. a bare 403/429) — use the status map.
  }
  return ASSISTANT_ERROR_CODE_BY_STATUS[response.status] ?? FALLBACK_HTTP_ERROR_CODE;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function parseSseFrames(buffer: string): {
  frames: SseFrame[];
  rest: string;
} {
  const segments = buffer.split(FRAME_DELIMITER);
  const rest = segments.pop() ?? "";

  const frames: SseFrame[] = [];
  for (const segment of segments) {
    let event = "";
    let data = "";
    for (const line of segment.split("\n")) {
      if (line.startsWith("event: ")) {
        event = line.slice("event: ".length);
      } else if (line.startsWith("data: ")) {
        data = line.slice("data: ".length);
      }
    }
    frames.push({ event, data });

  }
 
  return { frames, rest };
}

export interface AssistantState {
  status:
    | "idle"
    | "submitting"
    | "streaming"
    | "done"
    | "off_topic"
    | "error";
  answer: string;
  classification: string | null;
  errorCode: string | null;
  // The HTTP status of a non-OK response, when the error came from one.
  // null for stream-level errors (interrupted, network, mid-stream frames).
  httpStatus: number | null;
}

export const INITIAL_ASSISTANT_STATE: AssistantState = {
  status: "idle",
  answer: "",
  classification: null,
  errorCode: null,
  httpStatus: null,
};

/** Fold one SSE frame into the running state. Pure: same inputs → same
 * output, no side effects, input state untouched. Unknown events pass
 * through unchanged so a future frame type can't crash an old client. */
export function applyFrame(
  state: AssistantState,
  frame: SseFrame,
): AssistantState {
  switch (frame.event) {
    case "meta": {
      const meta = JSON.parse(frame.data) as { classification: string };
      return { ...state, status: "streaming", classification: meta.classification};
    }
    case "token":
      const text = JSON.parse(frame.data) as string;
      return { ...state, answer: state.answer + text };
    case "off_topic": {
        const redirectText = JSON.parse(frame.data) as string;
        return { ...state, status: "off_topic", answer: redirectText };
      }
      case "done": {
        return { ...state, status: "done"};
      }
      case "error": {
        const errorPayload = JSON.parse(frame.data) as { code: string };
        return { ...state, status: "error", errorCode: errorPayload.code };
      }
      default:
        return state;
  }
}

export async function readAssistantStream(
  response: Response,
  onState: (state: AssistantState) => void,
): Promise<AssistantState> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();

  let buffer = "";
  let state: AssistantState = INITIAL_ASSISTANT_STATE;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    // stream: true lets a multi-byte char span two chunks without mojibake.
    buffer += decoder.decode(value, { stream: true });

    const { frames, rest } = parseSseFrames(buffer);
    buffer = rest;

    for (const frame of frames) {
      state = applyFrame(state, frame);
      onState(state);
    }
  }

  return state;
}

export function buildAskRequest(
  context: AssistantContext,
  signal: AbortSignal,
): RequestInit {
  return {
    method: "POST",
    credentials: "include",
    headers: csrfHeaders(),
    body: JSON.stringify(context),
    signal,
  }
}

export function useAssistantStream() {
  const [state, setState] = useState<AssistantState>(INITIAL_ASSISTANT_STATE);
  const controllerRef = useRef<AbortController | null>(null);

  const ask = useCallback(async (context: AssistantContext) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setState({...INITIAL_ASSISTANT_STATE, status: "submitting"});

    try {
      const response = await fetch(
        ASSISTANT_ASK_URL,
        buildAskRequest(context, controller.signal),
      );

      if (!response.ok) {
        const errorCode = await resolveHttpErrorCode(response);
        setState((prev) => ({
          ...prev,
          status: "error",
          errorCode,
          httpStatus: response.status,
        }));
        return;
      }

      const finalState = await readAssistantStream(response, setState);

      // A well-behaved stream ends on done / off_topic / error. Anything
      // else means the connection dropped mid-answer (e.g. the backend
      // threw after committing a 200) — surface it instead of hanging,
      // keeping whatever partial answer already streamed in.
      if (!TERMINAL_STATUSES.has(finalState.status)) {
        setState({
          ...finalState,
          status: "error",
          errorCode: "assistant_interrupted",
        });
      }
    } catch (error) {
      // An abort is deliberate (Stop button or unmount), not a failure.
      if (isAbortError(error)) {
        return;
      }
      setState((prev) => ({ ...prev, status: "error", errorCode: "network" }));
    }
  }, []);

  const abort = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  useEffect(() => {
    return () => controllerRef.current?.abort();
  }, []);

  return { state, ask, abort };
}