"""Tests for User profile fields (handle, display_name, bio, is_private)
added in the social rollout, plus the handle derivation/validation helpers
in accounts/handles.py."""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from accounts.handles import (
    HANDLE_MAX_LENGTH,
    HANDLE_MIN_LENGTH,
    HandleValidationError,
    derive_handle,
    is_reserved_handle,
    is_valid_handle,
    normalize_handle_input,
    validate_handle,
)


User = get_user_model()


def _make_user(email, **extra):
    return User.objects.create_user(
        username=email, email=email, password="securepass123", **extra,
    )


# ─── Field defaults & uniqueness ──────────────────────────────────────────────


@pytest.mark.django_db
class TestProfileFieldDefaults:
    def test_new_user_has_blank_profile_fields(self):
        user = _make_user("alice@example.com")
        # handle is null by default; populated by data migration or user action.
        assert user.handle is None
        assert user.display_name == ""
        assert user.bio == ""
        assert user.is_private is False


@pytest.mark.django_db
class TestHandleUniqueness:
    def test_two_users_cannot_share_a_handle(self):
        _make_user("a@x.com", handle="alice")
        with pytest.raises(IntegrityError):
            _make_user("b@x.com", handle="alice")

    def test_multiple_users_can_have_null_handle(self):
        # Postgres treats multiple NULLs as distinct in a unique index. Sqlite
        # also permits multiple NULLs in a UNIQUE column. So this should work
        # on both backends used in the project.
        _make_user("a@x.com")
        _make_user("b@x.com")
        assert User.objects.filter(handle__isnull=True).count() == 2


@pytest.mark.django_db
class TestDisplayNameAndBioLengths:
    def test_display_name_64_chars_ok(self):
        user = _make_user("a@x.com", display_name="x" * 64)
        user.full_clean()  # should not raise

    def test_bio_160_chars_ok(self):
        user = _make_user("a@x.com", bio="b" * 160)
        user.full_clean()


# ─── Handle validation rules ──────────────────────────────────────────────────


class TestHandleValidator:
    @pytest.mark.parametrize("handle", [
        "alice",
        "alice_2",
        "a1b2c3",
        "abc",            # min length
        "a" * HANDLE_MAX_LENGTH,
        "gustavo_saiani",
        "user1234",
    ])
    def test_valid_handles(self, handle):
        assert is_valid_handle(handle), f"expected {handle!r} valid"

    @pytest.mark.parametrize("handle, reason", [
        ("", "empty"),
        ("ab", "too short"),
        ("a" * (HANDLE_MAX_LENGTH + 1), "too long"),
        ("Alice", "uppercase"),
        ("ali ce", "space"),
        ("ali-ce", "dash"),
        ("ali.ce", "dot"),
        ("ali@ce", "at-sign"),
        ("_alice", "leading underscore"),
        ("alice_", "trailing underscore"),
        ("ali__ce", "double underscore"),
        ("alíce", "non-ascii"),
    ])
    def test_invalid_handles(self, handle, reason):
        assert not is_valid_handle(handle), f"expected {handle!r} invalid ({reason})"

    def test_validate_handle_raises_with_reason(self):
        with pytest.raises(HandleValidationError):
            validate_handle("Alice")
        with pytest.raises(HandleValidationError):
            validate_handle("ab")
        # Reserved words also raise.
        with pytest.raises(HandleValidationError):
            validate_handle("admin")


class TestReservedHandles:
    @pytest.mark.parametrize("handle", [
        "admin", "api", "user", "users", "spond", "sponds",
        "sponda", "auth", "login", "logout", "signup", "settings",
        "notifications", "profile", "search", "feed", "global",
        "static", "assets", "robots", "sitemap",
        # Locale codes (Sponda supports 7).
        "pt", "en", "es", "zh", "fr", "de", "it",
    ])
    def test_reserved_words_rejected(self, handle):
        assert is_reserved_handle(handle), f"{handle!r} should be reserved"

    def test_normal_handles_not_reserved(self):
        assert not is_reserved_handle("alice")
        assert not is_reserved_handle("gustavo")
        assert not is_reserved_handle("investidor1")


# ─── Handle derivation from email ─────────────────────────────────────────────


class TestNormalizeHandleInput:
    def test_lowercase(self):
        assert normalize_handle_input("Alice") == "alice"

    def test_strip_non_alnum_underscore(self):
        assert normalize_handle_input("alice.smith+spam") == "alicesmithspam"
        assert normalize_handle_input("a-b_c.d") == "ab_cd"

    def test_collapse_double_underscores(self):
        assert normalize_handle_input("a__b___c") == "a_b_c"

    def test_strip_leading_trailing_underscore(self):
        assert normalize_handle_input("_alice_") == "alice"
        assert normalize_handle_input("__a__") == "a"


class TestDeriveHandle:
    def test_uses_email_local_part(self):
        existing = set()
        assert derive_handle("alice@example.com", existing) == "alice"

    def test_strips_punctuation(self):
        existing = set()
        assert derive_handle("Alice.Smith+spam@example.com", existing) == "alicesmith"

    def test_truncates_to_max_length(self):
        existing = set()
        out = derive_handle("a" * 40 + "@x.com", existing)
        assert len(out) <= HANDLE_MAX_LENGTH

    def test_short_local_part_padded(self):
        existing = set()
        # "x" is below the min — derive_handle must produce a valid (>= 3 char)
        # handle. Strategy: append numeric suffix.
        out = derive_handle("x@example.com", existing)
        assert is_valid_handle(out)
        assert len(out) >= HANDLE_MIN_LENGTH

    def test_collision_suffix_appended(self):
        existing = {"alice"}
        out = derive_handle("alice@example.com", existing)
        assert out != "alice"
        assert out.startswith("alice")
        assert is_valid_handle(out)

    def test_collision_keeps_appending(self):
        existing = {"alice", "alice2", "alice3"}
        before = set(existing)
        out = derive_handle("alice@example.com", existing)
        assert out not in before
        assert is_valid_handle(out)
        assert out in existing  # derive_handle records the new claim

    def test_reserved_email_local_avoided(self):
        existing = set()
        # "admin@x.com" must NOT produce "admin" — that's reserved.
        out = derive_handle("admin@example.com", existing)
        assert out != "admin"
        assert not is_reserved_handle(out)
        assert is_valid_handle(out)

    def test_empty_local_part_falls_back(self):
        existing = set()
        # No usable chars → fall back to deterministic handle.
        out = derive_handle("...@example.com", existing)
        assert is_valid_handle(out)

    def test_collision_at_max_length_truncates_base(self):
        existing = {"a" * HANDLE_MAX_LENGTH}
        before = set(existing)
        # Email's local part is 24 chars, all "a". We need to fit "_2" suffix.
        out = derive_handle("a" * HANDLE_MAX_LENGTH + "@x.com", existing)
        assert len(out) <= HANDLE_MAX_LENGTH
        assert out not in before
        assert is_valid_handle(out)
