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

interface LearningModeContextValue {
  enabled: boolean;
  available: boolean;
  setEnabled: (enabled: boolean) => void;
}

export const LearningModeContext = createContext<LearningModeContextValue>({
  enabled: false,
  available: false,
  setEnabled: () => {},
});

interface LearningModeProviderProps {
  children: ReactNode;
}

export function LearningModeProvider({ children }: LearningModeProviderProps) {
  const { user } = useAuth();
  const available = !!user?.is_superuser;
  const serverEnabled = user?.learning_mode_enabled ?? false;
  const [enabled, setEnabledState] = useState(false);

  // When auth resolves, sync the local state to the server-side preference.
  // For non-superusers `available` is false, so `enabled` stays false.
  useEffect(() => {
    if (available) {
      setEnabledState(serverEnabled);
    } else {
      setEnabledState(false);
    }
  }, [available, serverEnabled]);

  const setEnabled = useCallback(
    (next: boolean) => {
      if (!available) return;
      setEnabledState(next);
      fetch("/api/auth/preferences/", {
        method: "PATCH",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ learning_mode_enabled: next }),
      }).catch(() => {});
    },
    [available],
  );

  return (
    <LearningModeContext.Provider value={{ enabled, available, setEnabled }}>
      {children}
    </LearningModeContext.Provider>
  );
}

export function useLearningMode(): LearningModeContextValue {
  return useContext(LearningModeContext);
}
