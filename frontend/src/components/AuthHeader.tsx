"use client";

import { NotificationBell } from "./NotificationBell";
import { AccountButton } from "./AccountButton";
import "../styles/auth-header.css";
import "../styles/account-button.css";

/**
 * Right-hand cluster of the top header: notification bell + unified
 * account button.
 *
 * Was previously a much larger component containing inline links to
 * Visits / Alerts / Admin / Blog and a separate hamburger menu for
 * mobile. Those items have moved to the LeftNav in `LeftNav.tsx`,
 * which the hamburger in the layout shell now toggles.
 */
export function AuthHeader() {
  return (
    <div className="auth-header">
      <NotificationBell />
      <AccountButton />
    </div>
  );
}
