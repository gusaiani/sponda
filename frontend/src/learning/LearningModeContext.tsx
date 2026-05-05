"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "../hooks/useAuth";
import { csrfHeaders } from "../utils/csrf";

const STORAGE_KEY = "sponda-learning-mode";

interface LearningModeContextValue {
  /** Currently on for this visitor. */
  enabled: boolean;
  /** Always true: Learning Mode is available to every user. Kept on the
   *  context so call sites can stay forward-compatible if we ever gate
   *  it again (e.g. behind a paid tier). */
  available: boolean;
  setEnabled: (enabled: boolean) => void;
}

export const LearningModeContext = createContext<LearningModeContextValue>({
  enabled: false,
  available: true,
  setEnabled: () => {},
});

function readLocalStorageFlag(): boolean {
  // Default to ON when no preference is stored — Learning Mode ships
  // turned on; the flag only flips to false once a user has explicitly
  // disabled it (which we then persist as "0").
  if (typeof window === "undefined") return true;
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    if (value === null) return true;
    return value === "1";
  } catch {
    return true;
  }
}

function writeLocalStorageFlag(value: boolean) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
  } catch {
    /* private browsing / quota — silently ignore */
  }
}

interface LearningModeProviderProps {
  children: ReactNode;
}

export function LearningModeProvider({ children }: LearningModeProviderProps) {
  const { user, isAuthenticated } = useAuth();
  const [enabled, setEnabledState] = useState(false);

  // Resolve the initial value once auth resolves. Authenticated users:
  // server-side preference. Guests: localStorage.
  useEffect(() => {
    if (isAuthenticated) {
      setEnabledState(user?.learning_mode_enabled ?? false);
    } else {
      setEnabledState(readLocalStorageFlag());
    }
  }, [isAuthenticated, user?.learning_mode_enabled]);

  const setEnabled = useCallback(
    (next: boolean) => {
      setEnabledState(next);
      writeLocalStorageFlag(next);
      if (!isAuthenticated) return;
      fetch("/api/auth/preferences/", {
        method: "PATCH",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ learning_mode_enabled: next }),
      }).catch(() => {});
    },
    [isAuthenticated],
  );

  return (
    <LearningModeContext.Provider value={{ enabled, available: true, setEnabled }}>
      {children}
    </LearningModeContext.Provider>
  );
}

export function useLearningMode(): LearningModeContextValue {
  return useContext(LearningModeContext);
}
