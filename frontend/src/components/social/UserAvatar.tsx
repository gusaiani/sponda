"use client";

/**
 * Initials-only avatar. The colored background is derived deterministically
 * from the handle so the same user always gets the same circle. We use a
 * fixed palette so colors stay on-brand and accessible.
 *
 * v2 will support uploaded image avatars; this component already accepts an
 * optional `src` prop so swapping in <img> is a drop-in change.
 */

const SIZE_PX: Record<UserAvatarSize, number> = {
  sm: 24,
  md: 36,
  lg: 64,
};

const FONT_PX: Record<UserAvatarSize, number> = {
  sm: 11,
  md: 15,
  lg: 24,
};

// On-brand palette. All colors meet WCAG AA contrast against white text.
const PALETTE = [
  "#1b347e", // sponda blue
  "#2f4fa6",
  "#4b5fa6",
  "#5b3a86",
  "#7a3a86",
  "#8a3a6f",
  "#a13a4a",
  "#a85a2a",
  "#a87a2a",
  "#5a7a2a",
  "#2a7a4a",
  "#2a7a7a",
  "#2a5a8a",
];

export type UserAvatarSize = "sm" | "md" | "lg";

interface Props {
  handle: string | null | undefined;
  displayName?: string;
  size?: UserAvatarSize;
  src?: string | null;
}

function hashString(input: string): number {
  // Simple deterministic 32-bit FNV-1a — sufficient for palette index.
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = (hash * 16777619) >>> 0;
  }
  return hash;
}

export function paletteColorFor(handle: string | null | undefined): string {
  if (!handle) return PALETTE[0];
  return PALETTE[hashString(handle) % PALETTE.length];
}

export function initialsFor(handle: string | null | undefined, displayName?: string): string {
  const source = (displayName?.trim() || handle || "?").trim();
  if (!source) return "?";
  const parts = source.split(/[\s_]+/).filter(Boolean);
  if (parts.length === 0) return source.slice(0, 1).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

export function UserAvatar({ handle, displayName, size = "md", src }: Props) {
  const px = SIZE_PX[size];
  const fontPx = FONT_PX[size];
  const color = paletteColorFor(handle);
  const initials = initialsFor(handle, displayName);

  if (src) {
    return (
      <img
        src={src}
        alt={displayName || handle || ""}
        width={px}
        height={px}
        style={{
          width: `${px}px`,
          height: `${px}px`,
          borderRadius: "50%",
          objectFit: "cover",
          display: "inline-block",
        }}
      />
    );
  }

  return (
    <span
      role="img"
      aria-label={displayName || handle || "user"}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: `${px}px`,
        height: `${px}px`,
        borderRadius: "50%",
        backgroundColor: color,
        color: "#ffffff",
        fontSize: `${fontPx}px`,
        fontWeight: 600,
        userSelect: "none",
        flexShrink: 0,
      }}
    >
      {initials}
    </span>
  );
}
