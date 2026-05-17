import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders } from "../utils/csrf";
import { clearPersistedAuthState } from "../utils/clearPersistedAuthState";
import {
  getEmailVerificationPromptVisible,
  setEmailVerificationPromptVisible,
} from "../utils/emailVerificationPrompt";

export interface AuthUser {
  email: string;
  is_superuser: boolean;
  email_verified: boolean;
  date_joined: string;
  allow_contact: boolean;
  /** Server-side preference for Learning Mode. Only present when the
   *  current user is a superuser (the feature is gated to superusers
   *  while methodology v1 stabilizes). */
  learning_mode_enabled?: boolean;
  // Social profile fields. handle is null for users created before the
  // social rollout backfill ran or who explicitly cleared it.
  handle: string | null;
  display_name: string;
  bio: string;
  is_private: boolean;
}

async function fetchMe(): Promise<AuthUser | null> {
  const response = await fetch("/api/auth/me/", {
    credentials: "include",
  });
  if (!response.ok) return null;
  return response.json();
}

export function useAuth() {
  const queryClient = useQueryClient();
  const [showEmailVerificationPrompt, setShowEmailVerificationPrompt] = useState(false);

  // refetchOnMount: "always" is load-bearing. The persisted React Query cache
  // (PersistQueryClientProvider in providers.tsx) may rehydrate ["auth-user"]
  // with a stale value — most importantly, with the `null` we wrote during a
  // previous anonymous visit. With staleTime > 0 and the default refetch
  // policy, that null would pin `isAuthenticated=false` across hard navs
  // (e.g. the login → SPA flow ends in window.location.href = "/${locale}"),
  // so a logged-in user would still see the unauthenticated UI on the next
  // page mount until the staleness window elapsed. Forcing a mount-time
  // refetch keeps the auth view of the world honest while still letting
  // staleTime suppress background refetches on focus/reconnect.
  const { data: user, isLoading } = useQuery({
    queryKey: ["auth-user"],
    queryFn: fetchMe,
    staleTime: 5 * 60 * 1000,
    refetchOnMount: "always",
    retry: false,
  });

  useEffect(() => {
    function syncPromptState() {
      setShowEmailVerificationPrompt(getEmailVerificationPromptVisible());
    }

    syncPromptState();
    window.addEventListener("storage", syncPromptState);
    window.addEventListener("sponda-email-verification-prompt-change", syncPromptState);

    return () => {
      window.removeEventListener("storage", syncPromptState);
      window.removeEventListener("sponda-email-verification-prompt-change", syncPromptState);
    };
  }, []);

  useEffect(() => {
    if (!isLoading && (!user || user.email_verified)) {
      setEmailVerificationPromptVisible(false);
    }
  }, [isLoading, user]);

  async function logout() {
    try {
      await fetch("/api/auth/logout/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfHeaders()["X-CSRFToken"] },
        credentials: "include",
      });
    } catch {
      // Network errors must not strand the user in a half-logged-out
      // state: server-side session is destroyed by Django on the next
      // request anyway. Press on with the client-side cleanup.
    }
    setEmailVerificationPromptVisible(false);
    if (typeof window !== "undefined") {
      clearPersistedAuthState({
        queryClient,
        storage: window.localStorage,
        navigator: window.location,
      });
    }
  }

  async function refreshUser() {
    await queryClient.invalidateQueries({ queryKey: ["auth-user"] });
  }

  return {
    user: user ?? null,
    isAuthenticated: !!user,
    isSuperuser: user?.is_superuser ?? false,
    showEmailVerificationPrompt,
    isLoading,
    logout,
    refreshUser,
  };
}
