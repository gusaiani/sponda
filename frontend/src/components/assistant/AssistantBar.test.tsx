// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { AssistantBar } from "./AssistantBar";
import {
  INITIAL_ASSISTANT_STATE,
  useAssistantStream,
} from "./useAssistantStream";
import { useTranslation } from "@/i18n";

// useAssistantStream is tested on its own
// here we stub it
const ask = vi.fn();
const abort = vi.fn();
let mockState = INITIAL_ASSISTANT_STATE;

vi.mock("./useAssistantStream", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./useAssistantStream")>();
  return {
    ...actual,
    useAssistantStream: () => ({ state: mockState, ask, abort }),
  };
});

vi.mock("../../i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key, locale: "pt" }),
}));

afterEach(() => {
  cleanup();
  ask.mockReset();
  abort.mockReset();
  mockState = INITIAL_ASSISTANT_STATE;
});

describe("AssistantBar", () => {
  it("renders a question textbox and a send button", () => {
    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    expect(screen.getByRole("textbox")).toBeTruthy();
    expect(screen.getByRole("button", { name: "assistant.send" })).toBeTruthy();
  });

  it("calls ask with the context descriptor when the user submits", () => {
    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Is it cheap?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "assistant.send" }));

    expect(ask).toHaveBeenCalledWith({
      ticker: "PETR4",
      tab: "metrics",
      locale: "pt",
      question: "Is it cheap?",
    });
  });

  it("submits when the user presses Enter in the textbox", () => {
    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Is it cheap?" },
    });
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });

    expect(ask).toHaveBeenCalledWith({
      ticker: "PETR4",
      tab: "metrics",
      locale: "pt",
      question: "Is it cheap?",
    });
  });

  it("inserts a newline instead of submitting on Shift+Enter", () => {
    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Is it cheap?" },
    });
    fireEvent.keyDown(screen.getByRole("textbox"), {
      key: "Enter",
      shiftKey: true,
    });

    expect(ask).not.toHaveBeenCalled();
  });

  it("renders the streamed answer text", () => {
    mockState = {
      ...INITIAL_ASSISTANT_STATE,
      status: "streaming",
      answer: "PETR4 is cheap.",
    };

    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    expect(screen.getByText("PETR4 is cheap.")).toBeTruthy();
  });

  it("renders a localized error message keyed by errorCode", () => {
    mockState = {
      ...INITIAL_ASSISTANT_STATE,
      status: "error",
      errorCode: "rate_limited",
    };

    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    expect(screen.getByText("assistant.error.rate_limited")).toBeTruthy();
  });

  it("falls back to a generic error message for an unknown code", () => {
    mockState = {
      ...INITIAL_ASSISTANT_STATE,
      status: "error",
      errorCode: "something_new",
    };

    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    expect(screen.getByText("assistant.error.generic")).toBeTruthy();
  });

  it("shows the generic unavailable message to users on a config error", () => {
    // assistant_not_configured is a backend-misconfig code; users should
    // see a neutral "unavailable" message, not the raw cause.
    mockState = {
      ...INITIAL_ASSISTANT_STATE,
      status: "error",
      errorCode: "assistant_not_configured",
    };

    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    expect(
      screen.getByText("assistant.error.assistant_unavailable"),
    ).toBeTruthy();
  });

  it("renders a developer hint naming the cause outside production", () => {
    mockState = {
      ...INITIAL_ASSISTANT_STATE,
      status: "error",
      errorCode: "assistant_not_configured",
    };

    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    expect(screen.getByText(/OPENAI_API_KEY/)).toBeTruthy();
  });

  it("includes the real HTTP status in the developer hint", () => {
    mockState = {
      ...INITIAL_ASSISTANT_STATE,
      status: "error",
      errorCode: "assistant_unavailable",
      httpStatus: 500,
    };

    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    expect(screen.getByText(/HTTP 500/)).toBeTruthy();
  });

  it("does not render a developer hint when there is no error", () => {
    mockState = { ...INITIAL_ASSISTANT_STATE, status: "streaming" };

    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    expect(screen.queryByRole("note")).toBeNull();
  });

  it.each(["submitting", "streaming"] as const)(
    "disables the send button while the status is %",
    (busyStatus) => {
      mockState = { ...INITIAL_ASSISTANT_STATE, status: busyStatus };

      render(<AssistantBar ticker="PETR4" tab="metrics" />);

      const sendButton = screen.getByRole("button", { name: "assistant.send" });
      expect((sendButton as HTMLButtonElement).disabled).toBe(true);
    },
  );

  it("shows a stop button that calls abort while streaming", () => {
    mockState = { ...INITIAL_ASSISTANT_STATE, status: "streaming" };

    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    const stopButton = screen.getByRole("button", { name: "assistant.stop" });
    fireEvent.click(stopButton);

    expect(abort).toHaveBeenCalled();
  });
});
