export interface SseFrame {
  event: string;
  data: string;
}

const FRAME_DELIMITER = "\n\n";

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