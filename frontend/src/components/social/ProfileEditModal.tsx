"use client";

import { useState } from "react";
import { useTranslation } from "../../i18n";
import { useAuth } from "../../hooks/useAuth";
import { useUpdateProfile } from "../../hooks/useProfile";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function ProfileEditModal({ open, onClose }: Props) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const updateProfile = useUpdateProfile();

  const [handle, setHandle] = useState(user?.handle ?? "");
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [bio, setBio] = useState(user?.bio ?? "");
  const [isPrivate, setIsPrivate] = useState(user?.is_private ?? false);
  const [error, setError] = useState<string | null>(null);

  if (!open || !user) return null;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const payload: Record<string, unknown> = {};
    if (user && handle !== user.handle) payload.handle = handle.trim();
    if (user && displayName !== user.display_name) payload.display_name = displayName;
    if (user && bio !== user.bio) payload.bio = bio;
    if (user && isPrivate !== user.is_private) payload.is_private = isPrivate;
    if (Object.keys(payload).length === 0) {
      onClose();
      return;
    }
    try {
      await updateProfile.mutateAsync(payload);
      onClose();
    } catch (e) {
      const detail = (e as Error & { detail?: { handle?: string; code?: string } }).detail;
      if (detail?.code === "HANDLE_CHANGE_TOO_SOON") {
        setError(t("social.errors.handle_change_too_soon"));
      } else if (detail?.handle) {
        setError(detail.handle.includes("taken")
          ? t("social.errors.handle_taken")
          : t("social.errors.invalid_handle"));
      } else {
        setError(t("social.errors.invalid_handle"));
      }
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="profile-edit-title"
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "16px",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          background: "#fff", borderRadius: "12px", padding: "24px",
          maxWidth: "480px", width: "100%", maxHeight: "90vh", overflowY: "auto",
        }}
      >
        <h2 id="profile-edit-title" style={{ margin: "0 0 16px", fontSize: "20px" }}>
          {t("social.profile.edit_title")}
        </h2>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "16px" }}>
            <label htmlFor="profile-handle" style={{ display: "block", fontWeight: 600, marginBottom: "4px" }}>
              {t("social.profile.handle")}
            </label>
            <input
              id="profile-handle"
              type="text"
              value={handle}
              onChange={(e) => setHandle(e.target.value.toLowerCase())}
              maxLength={24}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #ccc", borderRadius: "6px" }}
            />
            <p style={{ margin: "4px 0 0", color: "#666", fontSize: "13px" }}>
              {t("social.profile.handle_help")}
            </p>
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label htmlFor="profile-name" style={{ display: "block", fontWeight: 600, marginBottom: "4px" }}>
              {t("social.profile.display_name")}
            </label>
            <input
              id="profile-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              maxLength={64}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #ccc", borderRadius: "6px" }}
            />
            <p style={{ margin: "4px 0 0", color: "#666", fontSize: "13px" }}>
              {t("social.profile.display_name_help")}
            </p>
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label htmlFor="profile-bio" style={{ display: "block", fontWeight: 600, marginBottom: "4px" }}>
              {t("social.profile.bio")}
            </label>
            <textarea
              id="profile-bio"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              maxLength={160}
              rows={3}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #ccc", borderRadius: "6px", resize: "vertical" }}
            />
            <p style={{ margin: "4px 0 0", color: "#666", fontSize: "13px" }}>
              {t("social.profile.bio_help")}
            </p>
          </div>

          <div style={{ marginBottom: "16px", display: "flex", gap: "10px", alignItems: "flex-start" }}>
            <input
              id="profile-private"
              type="checkbox"
              checked={isPrivate}
              onChange={(e) => setIsPrivate(e.target.checked)}
              style={{ marginTop: "2px" }}
            />
            <label htmlFor="profile-private" style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>{t("social.profile.is_private")}</div>
              <div style={{ color: "#666", fontSize: "13px" }}>
                {t("social.profile.is_private_help")}
              </div>
            </label>
          </div>

          {error && (
            <div style={{ marginBottom: "12px", padding: "8px 12px", background: "#fee", color: "#a00", borderRadius: "6px" }}>
              {error}
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
            <button
              type="button"
              onClick={onClose}
              style={{ padding: "8px 16px", border: "1px solid #ccc", borderRadius: "6px", background: "#fff", cursor: "pointer" }}
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={updateProfile.isPending}
              style={{
                padding: "8px 16px", border: "none", borderRadius: "6px",
                background: "#1b347e", color: "#fff", fontWeight: 600,
                cursor: updateProfile.isPending ? "wait" : "pointer",
              }}
            >
              {t("social.profile.save")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
