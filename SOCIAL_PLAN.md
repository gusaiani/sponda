# Plan: Make Sponda Social

## Context

Sponda today is a single-player tool: users research companies, save lists, set alerts, schedule revisits. There is no way to *speak* on the platform, no way to discover what other investors think, and no social graph. With 32 production users this is the right moment to introduce the social layer — small enough that we can ship a functional MVP without sharding feeds, ranking algorithms, abuse pipelines, or caching tiers, but with a data model that won't paint us into a corner at 3,200 or 32,000 users.

Goal: introduce **Sponds** (user-authored posts, 500 chars), a **follow graph** with optional **private accounts**, and **mute/block** primitives, integrated into the home page (general feed + composer) and into each company page (per-ticker composer + per-ticker thread). Replies and likes ship in v1. `@mention` and `$TICKER` linkification with composer autocomplete ship in v1. Avatars do **not** ship in v1 — initials-only fallback. Public Sponds are visible to anonymous readers but `noindex` for search engines until moderation matures.

Naming: the noun is **Spond** in every locale (invariant, like "tweet"). The verb conjugates per locale via the existing i18n dictionary — `social.verb.infinitive`, `social.verb.past`, `social.verb.imperative`, etc. Examples: pt `Spondar / Spondou`, en `to Spond / Sponded`, it `Spondare`, es `Spondar`, fr `Sponder`, de `Sponden`, zh `发布 Spond`.

## Resolved decisions (from user)

1. **Char limit**: 500 — enforced at serializer level, surfaced as live counter in composer.
2. **v1 engagement primitives**: replies + likes (no reposts).
3. **Visibility**: public-to-the-world for default accounts (anonymous read OK); per-user opt-in **private** flag (`User.is_private`) where Sponds are visible only to approved followers and follows are gated by approval.
4. **Identity**: `@handle` + `display_name`, **no avatar uploads** — `<UserAvatar />` renders a colored circle with initials. `avatar` ImageField deferred to v2.
5. **Follow workflow for private accounts**: `Follow.state` = `pending | accepted`. Pending follow creates a `follow_requested` notification; recipient accepts/rejects. Accept transitions to `accepted` and emits a `followed` notification to the requester.
6. **SEO**: `noindex` on `/user/<handle>` and `/spond/<id>` (meta tag + `robots.txt`). Anonymous browsing works; crawlers stay out.
7. **Profile URL**: `/user/<handle>` (user picked this variant — `/user/` namespace, never collides with tickers, locales, or future routes).
8. **Mentions/tags**: `@handle` and `$TICKER` linkified in cards + autocomplete dropdowns in composer in v1.

## Existing infrastructure we will reuse

- `accounts.User` (extends `AbstractUser`, identified by `email`) — we add profile fields directly here.
- `accounts.UserOperation` — already exists for write rate-limiting; we extend its scope set to include social verbs and use it as the source of truth for audit, alongside DRF throttles for enforcement.
- `quotes.Ticker` (PK = `symbol`) — natural FK target for ticker-tagged Sponds and `$TICKER` resolution.
- `accounts.AlertNotification` — pattern we generalize into a unified `Notification` model that absorbs alerts in a follow-up migration.
- DRF session auth + `CsrfExemptSessionAuthentication`, `/api/...` URL prefix.
- Frontend: React Query for all server state, Tailwind 4, custom i18n with 7 locales, vitest colocated tests, plain `useState` forms, existing `AuthHeader` mount point.
- `User.email_verified` — required to compose, reply, like, follow.

## Data model (backend, new app: `social`)

New Django app `backend/social/`. All models have `created_at`; soft delete (`deleted_at`) where listed.

### `Spond`
- `id` — UUID primary key (permalinks shouldn't leak count).
- `author` — FK `User`, `on_delete=CASCADE`.
- `body` — `TextField`, length validated to ≤ 500 at serializer level.
- `ticker` — FK `Ticker`, nullable. Set when composer is on a company page (locked) or when user picks a chip on home composer. **In addition**, all `$SYMBOL` tokens in the body are extracted and stored in a `SpondTickerMention` join table (separate from the primary `ticker` FK, so the company-feed query is fast: `Spond` rows where `ticker_id = X` OR exists in `SpondTickerMention(ticker_id=X)`).
- `parent` — self-FK, nullable; one-level reply chain (replies to replies allowed but flatten visually as in StockTwits).
- `deleted_at` — nullable; tombstones preserve thread structure.
- `created_at`, `updated_at` (last edit; 5-min author-only edit window, no "edited" badge in v1).
- Indexes: `(author, -created_at)`, `(ticker, -created_at)`, `(parent, created_at)`, partial `WHERE deleted_at IS NULL`.

### `SpondMention` and `SpondTickerMention`
Both denormalize content extracted from `body` for fast lookups + notification fan-out.
- `SpondMention(spond, mentioned_user)` — unique together; created in same transaction as the Spond.
- `SpondTickerMention(spond, ticker)` — unique together.

### `SpondLike`
- `(user, spond)` unique together; `created_at`.
- Likes on a deleted Spond are not allowed (DB check).

### `Follow`
- `follower` — FK `User`.
- `followee` — FK `User`.
- `state` — `CharField` choices `pending | accepted`. Default `accepted`; `pending` only when `followee.is_private = True` at creation time.
- `created_at`, `accepted_at` (nullable).
- `unique_together = (follower, followee)`; `CHECK (follower_id <> followee_id)`.
- Index: `(followee, state)` for "incoming requests" view; `(follower, state)` for "who I follow".

### `Mute` and `Block`
Two separate models, identical shape (`actor`, `target`, unique together).
- **Mute**: target's Sponds disappear from `actor`'s feeds; target unaware; one-way.
- **Block**: target cannot see `actor`'s profile/Sponds; cannot follow; cannot reply to `actor`'s Sponds; cannot mention `actor`. Enforced symmetrically in queries (neither sees the other's content). Creating a block auto-removes any `Follow` rows in either direction.

### `Notification` (new generic model; absorbs `AlertNotification` later)
- `recipient` — FK `User`.
- `actor` — FK `User`, nullable.
- `verb` — choices: `followed`, `follow_requested`, `replied`, `mentioned`, `liked` (and later `alert_triggered`).
- `target_content_type` + `target_object_id` — generic FK (Spond, Follow, or future).
- `read_at` — nullable.
- Indexes: `(recipient, -created_at)`, partial `WHERE read_at IS NULL`.

### Profile fields added to `User` (single migration on `accounts`)
- `handle` — `CharField(max_length=24, unique, null=True)`. Lowercase ASCII + digits + underscore. Reserved words list (`admin`, `api`, `user`, `spond`, locales, etc.). Data migration auto-derives a handle from email local-part with collision suffix; users may change once verified, max 1 change per 30 days.
- `display_name` — `CharField(max_length=64, blank=True)`. Defaults to handle if empty.
- `bio` — `CharField(max_length=160, blank=True)`.
- `is_private` — `BooleanField(default=False)`.

(Avatar field deferred — v2.)

## Visibility rules (centralized)

A single helper `social.querysets.visible_to(user, queryset_of_sponds)` is applied to **every** Spond queryset in views. It encodes:

1. Exclude soft-deleted **except** when needed as thread tombstones (separate flag).
2. Exclude Sponds whose author has blocked `user` or whom `user` has blocked.
3. Exclude Sponds whose author has been muted by `user` (mute is one-way and only filters `user`'s own views).
4. If author `is_private`: include only when `user` has an `accepted` Follow on author (or is the author).
5. Anonymous readers: behaves like `user=None`; private authors fully hidden; blocks/mutes irrelevant.

Same pattern for profile pages (`User` queryset filtered by visibility).

## Rate limiting

Three layers, in order: DRF throttles (enforcement) → `UserOperation` log (audit + custom rules) → application-level burst guards.

### DRF throttle scopes (per `User`, sliding window via `UserRateThrottle`)
Limits are intentionally tight — 5× more stringent than typical defaults. With 32 users we'd rather see a 429 than tolerate a runaway script or organic abuse pattern. Loosen later if real users hit ceilings.

| Action | Scope name | Limit |
|---|---|---|
| Compose Spond / reply | `spond_write` | 4 / minute, 24 / hour, 80 / day |
| Like / unlike | `spond_like` | 12 / minute, 120 / hour, 600 / day |
| Follow / unfollow | `follow_write` | 6 / minute, 20 / hour, 60 / day |
| Mute / block / unmute / unblock | `relation_write` | 8 / minute, 20 / hour |
| Profile edits (display_name, bio, is_private) | `profile_write` | 6 / hour |
| Handle change | `handle_change` | hard cap: 1 every 30 days, enforced in serializer (not throttle) |
| Notifications mark-read | `notif_write` | 24 / minute |

### DRF throttles for read / anonymous
| Action | Scope | Limit |
|---|---|---|
| Anonymous reads (any social GET) | `social_anon` | 60 / minute per IP |
| Authenticated reads | `social_user` | 300 / minute per user |

### `UserOperation` log
Every write action also writes a `UserOperation` row (`scope`, `target_id`, `created_at`). Two reasons:
- Survives across deploys / cache resets where DRF throttle counters live in cache.
- Lets us implement custom rules the throttle layer can't express, e.g.:
  - "New accounts (< 24h since signup) get half the standard daily Spond budget" — checked in the create view.
  - "If a Spond gets reported by 3+ distinct users in 1 hour, the author's `spond_write` budget halves for 24h" — checked in the create view (v2 once reporting ships).
  - "First 10 follows of a brand-new account fan out one notification each; beyond that, batch into a daily digest" — backend-side fan-out heuristic.

### Burst guards (application-level, complement throttles)
- A user cannot post the same `body` twice within 5 minutes (dedup hash check) — kills accidental double-submits and a class of spam.
- A user cannot mention more than 8 distinct `@handle`s in a single Spond (anti-spam mention bombs).
- A user cannot follow more than 20 unique accounts in any rolling 1-hour window even if throttle hasn't tripped (defense in depth against follow-spam farms).

### Email-verification gate
All write actions require `request.user.email_verified == True`. Returns `403 EMAIL_VERIFICATION_REQUIRED` with frontend-friendly code; UI shows the existing verification prompt.

### Response shape on throttle
Standard DRF `429 Too Many Requests` with `Retry-After` header and JSON `{detail, scope, retry_after_seconds}`. Frontend shows a localized toast referencing the scope.

## API surface (DRF, all under `/api/social/`)

Read endpoints (anonymous allowed unless noted):
- `GET /api/social/feed/` — auth required. Reverse-chrono Sponds from accounts the user follows + own Sponds. Cursor pagination (`?cursor=<created_at,id>`, 25 per page).
- `GET /api/social/feed/global/` — anonymous OK. All public Sponds, reverse-chrono.
- `GET /api/social/companies/<symbol>/sponds/` — anonymous OK. Sponds where `ticker_id = symbol` OR ticker mentioned in body.
- `GET /api/social/sponds/<uuid>/` — anonymous OK if Spond's author is public; 404 otherwise. Returns Spond + replies (flat, ordered).
- `GET /api/social/users/<handle>/` — public profile + visible Sponds.
- `GET /api/social/users/<handle>/followers/`, `.../following/` — paginated; 403 if author is private and viewer not approved.
- `GET /api/social/users/me/follow-requests/` — auth required; pending follows where `followee = me`.
- `GET /api/social/notifications/` + `POST .../mark-read/`.
- `GET /api/social/autocomplete/handles/?q=...` — auth required, throttled, prefix search on `User.handle`, max 8 results.
- `GET /api/social/autocomplete/tickers/?q=...` — auth required, throttled, prefix search on `Ticker.symbol` and `Ticker.display_name`, max 8 results. (May be possible to reuse an existing screener search endpoint — to verify during implementation.)

Write endpoints (CSRF, email verification + throttles):
- `POST /api/social/sponds/` — `{body, ticker?, parent?}`. Server extracts `@handle` and `$TICKER` mentions, populates join tables, fans out notifications.
- `PATCH /api/social/sponds/<uuid>/` — author-only, within 5-min window.
- `DELETE /api/social/sponds/<uuid>/` — author-only soft delete.
- `POST /api/social/sponds/<uuid>/like/`, `DELETE` to unlike.
- `POST /api/social/users/<handle>/follow/` — creates pending or accepted depending on target's `is_private`. `DELETE` to unfollow / cancel pending.
- `POST /api/social/follow-requests/<follow_id>/accept/`, `.../reject/` — recipient-only.
- `POST /api/social/users/<handle>/mute/`, `DELETE`. Same for `/block/`.
- `PATCH /api/social/users/me/profile/` — handle, display_name, bio, is_private.

## Frontend

New folder `frontend/src/components/social/`:
- `<SpondComposer />` — autosizing `<textarea>`, 500-char counter (turns red at 480), optional ticker chip (controlled prop; locked on company pages, openable picker on home), autocomplete dropdowns triggered by `@` and `$` in the textarea (uses the autocomplete endpoints above with debounced React Query). Plain `useState`.
- `<SpondCard />` — initials-circle avatar, display name + `@handle`, relative timestamp, body with `@mention` and `$TICKER` rendered as `<Link>`s, ticker badge if `ticker` FK set, action row (reply, like, mute/block in overflow, edit/delete for author).
- `<SpondFeed />` — React Query infinite scroll over a feed endpoint URL.
- `<UserAvatar />` — colored circle with initials, deterministic color from `handle` hash. Three sizes (sm/md/lg). Mounts in `AuthHeader`.
- `<FollowButton />` — three states (Follow / Requested / Following) for private targets, two states otherwise. Optimistic toggle.
- `<MuteBlockMenu />`.
- `<NotificationsBell />` — polled every 60s via React Query; dropdown list with grouped follow_request actions inline.
- `<HandlePicker />` and `<TickerPicker />` — reusable dropdown listboxes powering composer autocomplete.

New hooks: `useSocialFeed`, `useSpond`, `useCreateSpond`, `useLike`, `useFollow`, `useFollowRequests`, `useMuteBlock`, `useNotifications`, `useProfile`, `useHandleAutocomplete`, `useTickerAutocomplete`. All follow the existing pattern in `hooks/usePE10.ts`.

New pages:
- `app/[locale]/user/[handle]/page.tsx` — public profile, with `noindex` meta.
- `app/[locale]/spond/[id]/page.tsx` — Spond permalink with thread, with `noindex` meta.
- `app/[locale]/[notifications-slug]/page.tsx` — full notifications view (slug TBD per locale, e.g., `/pt/notificacoes`, `/en/notifications`).

Mounts in existing pages:
- **Home (`app/[locale]/page.tsx`)**: composer at top (no ticker pre-set, optional ticker chip), then a tabbed feed `Following | Global` below the existing `<HomepageGrid />`. Tab persists in localStorage. Anonymous viewers see Global only, with a CTA to log in to follow.
- **Company page (`app/[locale]/[ticker]/page.tsx`)**: new tab "Sponds" (rightmost), containing locked-ticker composer + per-ticker feed. Anonymous viewers see the feed in read-only mode.

`robots.txt` update (in `frontend/public/robots.txt`): disallow `/user/`, `/spond/`, `/api/social/` from indexing. Add `<meta name="robots" content="noindex,follow">` on profile and Spond permalink pages.

i18n: every UI string added to all 7 locale files in `frontend/src/i18n/locales/`. Verb conjugations live behind keys like `social.verb.compose`, `social.verb.past_tense_one` (`Spondou`, `Sponded`), `social.notification.followed`, `social.notification.follow_requested`, etc.

## Test strategy (TDD, per CLAUDE.md — tests first)

Backend (pytest + factory-boy):
- Factories for `UserFactory`, `SpondFactory`, `FollowFactory`, `LikeFactory`, `MuteFactory`, `BlockFactory` in `backend/social/tests/factories.py`.
- Model tests: handle uniqueness + reserved words, 500-char enforcement, soft delete + thread tombstone, edit-window expiry, block-symmetric visibility, mute-one-way visibility, self-follow rejection, private account auto-pending, accepted follow auto-notification, mention parsing for `@handle` and `$TICKER`.
- Visibility test matrix: matrix of (viewer state) × (author state) × (relation) × (Spond state).
- Throttle tests: each scope hits its limit and 429s; verify `Retry-After` header.
- Burst guard tests: dedup body, mention-count cap, hourly follow cap.
- API tests: every endpoint, anonymous vs authenticated, verified vs unverified, cursor pagination correctness, autocomplete.
- Notification fan-out tests: reply on Spond → author gets `replied`; mention → mentioned user gets `mentioned`; like → author gets `liked` (deduped if user re-likes within 24h); follow public → followee gets `followed`; follow private → followee gets `follow_requested`; accept → follower gets `followed`.

Frontend (vitest + RTL):
- `<SpondComposer />` — char counter color, disabled when empty/over-limit, ticker chip render, `@` and `$` triggers autocomplete dropdown, submit calls hook.
- `<SpondCard />` — `@`/`$` linkification, edit window UI, author-only actions, like optimistic toggle.
- `<SpondFeed />` — infinite scroll fetch, optimistic insertion on new Spond.
- `<FollowButton />` — three-state for private targets, optimistic + rollback on error.
- `<NotificationsBell />` — pending follow requests render inline accept/reject and call hooks.
- Hooks tested with mocked fetch.

E2E (playwright if config exists): one happy path — verified user A composes Spond on company page; user B follows A and sees the Spond; A flips `is_private`; user C requests follow → pending notification → A accepts → C now sees A's Sponds; B mutes A → A's Sponds disappear from B's Following feed; B blocks A → A's profile 404s for B and vice versa.

## Migration plan (rollout order)

1. Backend: `accounts` migration adds `handle`, `display_name`, `bio`, `is_private`; data migration backfills `handle` from email with collision suffix. Tests pass in CI.
2. Backend: new `social` app — models + admin + visibility helper + throttle scopes + tests.
3. Backend: API endpoints (compose / feed / follow / like / notifications / autocomplete) + tests.
4. Frontend: `<UserAvatar />` (initials), handle + display_name in `AuthHeader`, profile-edit modal (handle/display_name/bio/is_private). Ship. Validates identity layer end-to-end.
5. Frontend: composer + feed components + home-page integration. `noindex` meta + `robots.txt`.
6. Frontend: company-page Sponds tab.
7. Frontend: profile pages (`/user/<handle>`), Spond permalinks (`/spond/<id>`), notifications page + bell.
8. Email digests for unread notifications (daily) — separate follow-up after v1 stabilizes.

## Verification

- `pytest backend/social/` and `pytest backend/accounts/` — all green.
- `npm run test` and `npm run build` in `frontend/` — clean.
- Two-account manual E2E in local dev covering the matrix above.
- Manual throttle check: hit `/api/social/sponds/` 11× in a minute → expect 429 on 11th with `Retry-After`.
- Lighthouse on company page after Sponds tab added: no regression in LCP/CLS.
- `curl https://sponda.capital/robots.txt` post-deploy: confirm `/user/`, `/spond/`, `/api/social/` disallowed.
- Anonymous incognito tab: confirm Global feed loads, private accounts hidden, login wall on Following tab.

## Critical files to modify or create

- `backend/accounts/models.py` — add `handle`, `display_name`, `bio`, `is_private`.
- `backend/accounts/migrations/00XX_user_profile_fields.py` — schema + data migration for handle backfill.
- `backend/social/` (new app): `models.py`, `serializers.py`, `views.py`, `urls.py`, `querysets.py`, `permissions.py`, `throttles.py`, `mentions.py` (parser), `notifications.py` (fan-out), `tests/`, `migrations/`.
- `backend/config/urls.py` — mount `/api/social/`.
- `backend/config/settings/base.py` — `INSTALLED_APPS += ["social"]`, register throttle scopes in `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`.
- `frontend/src/components/social/*` (new).
- `frontend/src/hooks/useSocialFeed.ts`, `useSpond.ts`, `useCreateSpond.ts`, `useLike.ts`, `useFollow.ts`, `useFollowRequests.ts`, `useMuteBlock.ts`, `useNotifications.ts`, `useProfile.ts`, `useHandleAutocomplete.ts`, `useTickerAutocomplete.ts` (new).
- `frontend/src/app/[locale]/page.tsx` — composer + feed tabs.
- `frontend/src/app/[locale]/[ticker]/page.tsx` (and `TickerPageClient.tsx`) — add Sponds tab.
- `frontend/src/app/[locale]/user/[handle]/page.tsx`, `frontend/src/app/[locale]/spond/[id]/page.tsx` (new).
- `frontend/src/components/AuthHeader.tsx` — initials avatar dropdown, link to profile/edit.
- `frontend/src/i18n/locales/{pt,en,es,zh,fr,de,it}.ts` — `social.*` keys + verb conjugations.
- `frontend/public/robots.txt` — disallow `/user/`, `/spond/`, `/api/social/`.
- `README.md` — document the social feature, throttle scopes, rate limits, and local-test steps.
