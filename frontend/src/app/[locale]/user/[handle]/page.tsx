"use client";

import { use } from "react";
import { notFound } from "next/navigation";
import { useTranslation } from "../../../../i18n";
import { useAuth } from "../../../../hooks/useAuth";
import { useProfile } from "../../../../hooks/useProfile";
import { useToggleFollow } from "../../../../hooks/useFollow";
import { UserAvatar } from "../../../../components/social/UserAvatar";
import { SpondCard } from "../../../../components/social/SpondCard";

interface Props {
  params: Promise<{ locale: string; handle: string }>;
}

export default function UserProfilePage({ params }: Props) {
  const { handle } = use(params);
  const { t } = useTranslation();
  const { user: viewer } = useAuth();
  const profileQuery = useProfile(handle);
  const toggleFollow = useToggleFollow();

  if (profileQuery.isLoading) {
    return (
      <div style={{ maxWidth: "640px", margin: "32px auto", padding: "0 16px", color: "#666" }}>
        {t("common.loading")}
      </div>
    );
  }

  const profile = profileQuery.data;
  if (!profile) {
    notFound();
  }

  const isMe = viewer?.handle === profile.user.handle;
  const followState = profile.viewer_is_following;

  let followLabel = t("social.profile.follow");
  if (followState === "accepted") followLabel = t("social.profile.following_button");
  else if (followState === "pending") followLabel = t("social.profile.requested");

  function handleFollowClick() {
    toggleFollow.mutate({
      handle,
      follow: !followState,
    });
  }

  return (
    <>
      {/* Crawlers stay out of social pages until moderation matures. */}
      <meta name="robots" content="noindex,follow" />

      <div style={{ maxWidth: "640px", margin: "32px auto", padding: "0 16px" }}>
        <header style={{ display: "flex", alignItems: "flex-start", gap: "16px", marginBottom: "20px" }}>
          <UserAvatar handle={profile.user.handle} displayName={profile.user.display_name} size="lg" />
          <div style={{ flex: 1 }}>
            <h1 style={{ margin: 0, fontSize: "22px" }}>
              {profile.user.display_name || profile.user.handle}
            </h1>
            <div style={{ color: "#666" }}>
              @{profile.user.handle}
              {profile.user.is_private && (
                <span style={{ marginLeft: "8px", padding: "2px 8px", borderRadius: "999px", background: "#eef1ff", fontSize: "12px", color: "#1b347e" }}>
                  {t("social.profile.private_account")}
                </span>
              )}
            </div>
            {profile.user.bio && (
              <p style={{ marginTop: "8px", marginBottom: "8px" }}>{profile.user.bio}</p>
            )}
            <div style={{ display: "flex", gap: "16px", color: "#555", fontSize: "14px" }}>
              <span><b>{profile.follower_count}</b> {t("social.profile.followers")}</span>
              <span><b>{profile.following_count}</b> {t("social.profile.following")}</span>
            </div>
          </div>
          {!isMe && viewer && (
            <button
              type="button"
              onClick={handleFollowClick}
              disabled={toggleFollow.isPending}
              style={{
                padding: "6px 14px",
                border: "1px solid #1b347e",
                borderRadius: "999px",
                background: followState === "accepted" ? "#fff" : "#1b347e",
                color: followState === "accepted" ? "#1b347e" : "#fff",
                cursor: "pointer",
                fontWeight: 600,
              }}
            >
              {followLabel}
            </button>
          )}
        </header>

        {profile.sponds.length === 0 ? (
          <div style={{ padding: "16px", color: "#666" }}>
            {t("social.feed.empty_profile")}
          </div>
        ) : (
          profile.sponds.map((spond) => <SpondCard key={spond.id} spond={spond} />)
        )}
      </div>
    </>
  );
}
