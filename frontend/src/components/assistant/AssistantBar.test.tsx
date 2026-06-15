// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { AssistantBar } from "./AssistantBar";
import {
  INITIAL_ASSISTANT_STATE,
  useAssistantStream,
  type AssistantState,
} from "./useAssistantStream";
import {
  AssistantWindowProvider,
  useSetAssistantWindow,
} from "./AssistantWindowContext";
import { useEffect } from "react";
import { useTranslation } from "@/i18n";

// useAssistantStream is tested on its own
// here we stub it
const ask = vi.fn();
const abort = vi.fn();
let mockState = INITIAL_ASSISTANT_STATE;
// When a test sets only mockState, derive a 1-turn thread from it so the
// single-turn assertions keep working. Tests exercising the multi-turn thread
// set mockConversation directly.
let mockConversation: AssistantState[] | null = null;

vi.mock("./useAssistantStream", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./useAssistantStream")>();
  return {
    ...actual,
    useAssistantStream: () => ({
      state: mockState,
      conversation:
        mockConversation ?? (mockState.status === "idle" ? [] : [mockState]),
      ask,
      abort,
    }),
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
  mockConversation = null;
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
      years: null,
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
      years: null,
    });
  });

  it("sends the PRAZO window from context when one is set", () => {
    function WindowSetter({ years }: { years: number }) {
      const setYears = useSetAssistantWindow();
      useEffect(() => setYears(years), [setYears, years]);
      return null;
    }

    render(
      <AssistantWindowProvider>
        <WindowSetter years={7} />
        <AssistantBar ticker="PETR4" tab="metrics" />
      </AssistantWindowProvider>,
    );

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Is it cheap?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "assistant.send" }));

    expect(ask).toHaveBeenCalledWith({
      ticker: "PETR4",
      tab: "metrics",
      locale: "pt",
      question: "Is it cheap?",
      years: 7,
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

  it("closes the panel to a launcher, then reopens it", () => {
    render(<AssistantBar ticker="PETR4" tab="metrics" />);
    // Open by default.
    expect(screen.getByRole("textbox")).toBeTruthy();

    // Close hides the panel.
    fireEvent.click(screen.getByRole("button", { name: "assistant.close" }));
    expect(screen.queryByRole("textbox")).toBeNull();

    // A launcher remains to reopen it.
    fireEvent.click(screen.getByRole("button", { name: "assistant.open" }));
    expect(screen.getByRole("textbox")).toBeTruthy();
  });

  it("keeps the conversation thread after closing and reopening", () => {
    mockConversation = [
      {
        ...INITIAL_ASSISTANT_STATE,
        status: "done",
        question: "Is it cheap?",
        answer: "On PE10, yes.",
      },
    ];

    render(<AssistantBar ticker="PETR4" tab="metrics" />);
    fireEvent.click(screen.getByRole("button", { name: "assistant.close" }));
    fireEvent.click(screen.getByRole("button", { name: "assistant.open" }));

    // The thread is owned by the hook, so it survives a close/reopen.
    expect(screen.getByText("Is it cheap?")).toBeTruthy();
    expect(screen.getByText("On PE10, yes.")).toBeTruthy();
  });

  it("renders every exchange in the conversation thread", () => {
    mockConversation = [
      {
        ...INITIAL_ASSISTANT_STATE,
        status: "done",
        question: "Is it cheap?",
        answer: "On PE10, yes.",
      },
      {
        ...INITIAL_ASSISTANT_STATE,
        status: "streaming",
        question: "And on PFCF10?",
        answer: "Also cheap.",
      },
    ];

    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    expect(screen.getByText("Is it cheap?")).toBeTruthy();
    expect(screen.getByText("On PE10, yes.")).toBeTruthy();
    expect(screen.getByText("And on PFCF10?")).toBeTruthy();
    expect(screen.getByText("Also cheap.")).toBeTruthy();
  });

  it("renders the submitted question above the answer", () => {
    mockState = {
      ...INITIAL_ASSISTANT_STATE,
      status: "streaming",
      question: "Is it cheap?",
      answer: "PETR4 is cheap.",
    };

    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    expect(screen.getByText("Is it cheap?")).toBeTruthy();
    expect(screen.getByText("PETR4 is cheap.")).toBeTruthy();
  });

  it("clears the textarea after submitting", () => {
    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textbox, { target: { value: "Is it cheap?" } });
    fireEvent.click(screen.getByRole("button", { name: "assistant.send" }));

    expect(textbox.value).toBe("");
  });

  it("refocuses the textarea after submitting for quick follow-ups", () => {
    render(<AssistantBar ticker="PETR4" tab="metrics" />);

    const textbox = screen.getByRole("textbox");
    fireEvent.change(textbox, { target: { value: "Is it cheap?" } });
    fireEvent.click(screen.getByRole("button", { name: "assistant.send" }));

    expect(document.activeElement).toBe(textbox);
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
