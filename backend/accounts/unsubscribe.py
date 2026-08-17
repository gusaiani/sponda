"""One-click opt-out from Sponda's marketing email.

The link in an email carries a signed token instead of a database row. A
send never has to write tokens ahead of time, the link keeps working for as
long as the address does, and there is nothing to expire or exhaust — which
is what RFC 8058 and the bulk-sender rules at Gmail and Outlook expect. The
signature covers the address it was issued for, so a token dies the moment
the account moves to a different email.

Two behaviours here are load-bearing:

* **GET changes nothing.** Spam filters and corporate link scanners fetch
  every URL in an email. A GET that opted people out would unsubscribe an
  entire send before a human read it. GET only renders a confirmation page.
* **POST is CSRF-exempt.** The one-click POST comes from the mail provider,
  not from a browser carrying a Sponda session, so there is no cookie and no
  token to check. The signed link is the credential.
"""
from django.conf import settings
from django.core import signing
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .languages import resolve_user_language
from .models import User
from .unsubscribe_text import html_lang, unsubscribe_copy

# Namespacing the signature keeps a token minted here from being accepted
# anywhere else that signs values with the same SECRET_KEY.
UNSUBSCRIBE_TOKEN_SALT = "accounts.unsubscribe"

ONE_CLICK_HEADER_VALUE = "List-Unsubscribe=One-Click"

DEFAULT_UNSUBSCRIBE_BASE_URL = "https://sponda.capital"
DEFAULT_SITE_BASE_URL = "https://sponda.capital"

UNSUBSCRIBE_TEMPLATE = "unsubscribe/page.html"

STATE_CONFIRM = "confirm"
STATE_DONE = "done"
STATE_ALREADY = "already"
STATE_INVALID = "invalid"

# States where telling the reader that account email keeps coming is useful.
STATES_SHOWING_TRANSACTIONAL_NOTE = (STATE_CONFIRM, STATE_DONE)


def generate_unsubscribe_token(user):
    """Return a signed token identifying ``user`` for opt-out purposes."""
    return signing.dumps(
        {"user_id": user.pk, "email": user.email},
        salt=UNSUBSCRIBE_TOKEN_SALT,
    )


def resolve_unsubscribe_token(token):
    """Return the user a token was issued for, or ``None`` if it is not usable.

    A token is unusable when the signature fails, when the account is gone,
    or when the account's address no longer matches the one signed into the
    token.
    """
    try:
        payload = signing.loads(token, salt=UNSUBSCRIBE_TOKEN_SALT)
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict):
        return None

    user = User.objects.filter(pk=payload.get("user_id")).first()
    if user is None:
        return None

    signed_email = str(payload.get("email") or "")
    if user.email.lower() != signed_email.lower():
        return None
    return user


def build_unsubscribe_url(user):
    """Return the absolute URL of ``user``'s unsubscribe page."""
    path = reverse("unsubscribe", kwargs={"token": generate_unsubscribe_token(user)})
    return f"{_unsubscribe_base_url()}{path}"


def build_unsubscribe_headers(user):
    """Return the RFC 8058 headers every marketing send must carry.

    ``List-Unsubscribe-Post`` is what turns the header into Gmail's and
    Outlook's native "Unsubscribe" button; without it they fall back to
    hunting for a link in the body, or to marking the sender as spam.
    """
    return {
        "List-Unsubscribe": f"<{build_unsubscribe_url(user)}>",
        "List-Unsubscribe-Post": ONE_CLICK_HEADER_VALUE,
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def unsubscribe_view(request, token):
    """Render the opt-out page, and on POST actually opt the reader out."""
    user = resolve_unsubscribe_token(token)
    if user is None:
        return _render_unsubscribe_page(request, None, STATE_INVALID, status=404)

    if request.method == "POST":
        _opt_out_of_marketing_email(user)
        return _render_unsubscribe_page(request, user, STATE_DONE)

    state = STATE_CONFIRM if user.allow_contact else STATE_ALREADY
    return _render_unsubscribe_page(request, user, state)


def _opt_out_of_marketing_email(user):
    """Clear the contact flag. A second call on the same user is a no-op."""
    if not user.allow_contact:
        return
    user.allow_contact = False
    user.save(update_fields=["allow_contact"])


def _render_unsubscribe_page(request, user, state, status=200):
    language = resolve_user_language(user)
    copy = unsubscribe_copy(language)
    email = user.email if user else ""

    context = {
        "html_lang": html_lang(language),
        "title": copy[state]["title"],
        "message": copy[state]["body"].format(email=email),
        "action_label": copy["action"],
        "note": copy["note"] if state in STATES_SHOWING_TRANSACTIONAL_NOTE else "",
        "account_action": copy["account_action"],
        "account_url": f"{_site_base_url()}/{language}/account",
        "home_url": _site_base_url(),
        "shows_confirm_button": state == STATE_CONFIRM,
    }
    return render(request, UNSUBSCRIBE_TEMPLATE, context, status=status)


def _unsubscribe_base_url():
    """Origin serving the unsubscribe page — Django, not the Next.js frontend."""
    base_url = getattr(settings, "UNSUBSCRIBE_BASE_URL", DEFAULT_UNSUBSCRIBE_BASE_URL)
    return base_url.rstrip("/")


def _site_base_url():
    base_url = getattr(settings, "SITE_BASE_URL", DEFAULT_SITE_BASE_URL)
    return base_url.rstrip("/")
