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

export const ASSISTANT_ASK_URL = "/api/assistant/ask";

const FRAME_DELIMITER = "\n\n";

const ASSISTANT_ERROR_CODE_BY_STATUS: Record<number, string> = {
  403: "ASSISTANT_FORBIDDEN",  // backend's superuser/tier gate rejected
  429: "assistant_limit",      // daily quota exhausted
};

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
}

export const INITIAL_ASSISTANT_STATE: AssistantState = {
  status: "idle",
  answer: "",
  classification: null,
  errorCode: null,
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

    const response = await fetch(
      ASSISTANT_ASK_URL,
      buildAskRequest(context, controller.signal),
    );

    const mappedErrorCode = ASSISTANT_ERROR_CODE_BY_STATUS[response.status];
    if (mappedErrorCode) {
      setState((prev) => ({ ...prev, status: "error", errorCode: mappedErrorCode }));
      return;
    }

    await readAssistantStream(response, setState);
  }, []);

  const abort = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  useEffect(() => {
    return () => controllerRef.current?.abort();
  }, []);

  return { state, ask, abort };
}