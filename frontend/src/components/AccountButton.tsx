"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useTranslation } from "../i18n";
import { useAuth } from "../hooks/useAuth";
import { UserAvatar } from "./social/UserAvatar";
import { ProfileEditModal } from "./social/ProfileEditModal";

/**
 * Single account control in the top header. Replaces the previous pair
 * of "Minha conta" link + "@handle" pill — those concepts are now one
 * affordance. Signed-out users see a "Sign in" link; signed-in users
 * see their avatar + handle, which opens a dropdown with profile,
 * settings, and sign-out actions.
 */
export function AccountButton() {
  const { t, locale } = useTranslation();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [editingProfile, setEditingProfile] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function clickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", clickOutside);
    return () => document.removeEventListener("mousedown", clickOutside);
  }, [open]);

  if (isLoading) {
    return <div className="account-button-placeholder" aria-hidden />;
  }

  if (!isAuthenticated || !user) {
    return (
      <Link href={`/${locale}/login`} className="account-button account-button--login">
        {t("nav.account_login")}
      </Link>
    );
  }

  return (
    <div className="account-button-wrapper" ref={ref}>
      {editingProfile && (
        <ProfileEditModal open={true} onClose={() => setEditingProfile(false)} />
      )}
      <button
        type="button"
        className="account-button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label={t("nav.account_menu_label")}
        aria-expanded={open}
      >
        <UserAvatar handle={user.handle} displayName={user.display_name} size="sm" />
        {user.handle && (
          <span className="account-button-handle">@{user.handle}</span>
        )}
      </button>
      {open && (
        <div className="account-button-menu" role="menu">
          <div className="account-button-menu-header">
            <UserAvatar handle={user.handle} displayName={user.display_name} size="md" />
            <div className="account-button-menu-identity">
              <strong>{user.display_name || user.handle || user.email}</strong>
              {user.handle && <span>@{user.handle}</span>}
            </div>
          </div>
          {user.handle && (
            <Link
              href={`/${locale}/user/${user.handle}`}
              className="account-button-menu-item"
              onClick={() => setOpen(false)}
              role="menuitem"
            >
              {t("social.profile.my_profile")}
            </Link>
          )}
          <button
            type="button"
            className="account-button-menu-item"
            onClick={() => {
              setOpen(false);
              setEditingProfile(true);
            }}
            role="menuitem"
          >
            {t("social.profile.edit_title")}
          </button>
          <Link
            href={`/${locale}/account`}
            className="account-button-menu-item"
            onClick={() => setOpen(false)}
            role="menuitem"
          >
            {t("nav.account_settings")}
          </Link>
          <button
            type="button"
            className="account-button-menu-item account-button-menu-item--danger"
            onClick={() => {
              setOpen(false);
              logout();
            }}
            role="menuitem"
          >
            {t("nav.account_sign_out")}
          </button>
        </div>
      )}
    </div>
  );
}
