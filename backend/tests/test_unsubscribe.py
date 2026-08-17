"""Opt-out from Sponda's marketing email.

The two properties that matter most here are easy to get wrong, so both are
pinned by name: a GET must never change anything (spam filters and corporate
link scanners fetch every URL in an email), and a POST must work without a
CSRF token (RFC 8058 one-click comes straight from the mail provider, with
no cookie and no session).
"""
import pytest
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import Client
from django.urls import reverse

from accounts.unsubscribe import (
    build_unsubscribe_headers,
    build_unsubscribe_url,
    generate_unsubscribe_token,
    resolve_unsubscribe_token,
)


@pytest.fixture
def contactable_user(db):
    """A user who opted in to marketing email, writing in Portuguese."""
    return get_user_model().objects.create_user(
        username="leitor@example.com",
        email="leitor@example.com",
        password="pw123456",
        allow_contact=True,
        language="pt",
    )


def unsubscribe_path(user):
    return reverse("unsubscribe", kwargs={"token": generate_unsubscribe_token(user)})


class TestUnsubscribeToken:
    def test_token_resolves_back_to_its_user(self, contactable_user):
        token = generate_unsubscribe_token(contactable_user)

        assert resolve_unsubscribe_token(token) == contactable_user

    def test_tampered_token_resolves_to_nobody(self, contactable_user):
        token = generate_unsubscribe_token(contactable_user)

        assert resolve_unsubscribe_token(token + "tampered") is None

    def test_token_signed_with_another_salt_resolves_to_nobody(self, contactable_user):
        """A signature lifted from another feature must not unsubscribe anyone."""
        forged = signing.dumps(
            {"user_id": contactable_user.pk, "email": contactable_user.email},
            salt="accounts.something-else",
        )

        assert resolve_unsubscribe_token(forged) is None

    def test_garbage_resolves_to_nobody(self):
        assert resolve_unsubscribe_token("not-a-token") is None

    def test_token_stops_working_once_the_address_changes(self, contactable_user):
        """Whoever inherits the old address must not be able to opt out the new one."""
        token = generate_unsubscribe_token(contactable_user)
        contactable_user.email = "mudou@example.com"
        contactable_user.save(update_fields=["email"])

        assert resolve_unsubscribe_token(token) is None

    def test_token_of_a_deleted_user_resolves_to_nobody(self, contactable_user):
        token = generate_unsubscribe_token(contactable_user)
        contactable_user.delete()

        assert resolve_unsubscribe_token(token) is None

    def test_a_token_does_not_open_another_account(self, contactable_user, db):
        other_user = get_user_model().objects.create_user(
            username="outro@example.com",
            email="outro@example.com",
            password="pw123456",
            allow_contact=True,
        )
        token = generate_unsubscribe_token(contactable_user)

        assert resolve_unsubscribe_token(token) != other_user


class TestUnsubscribeUrlAndHeaders:
    def test_url_carries_a_token_that_resolves(self, contactable_user, settings):
        settings.UNSUBSCRIBE_BASE_URL = "https://sponda.capital"

        url = build_unsubscribe_url(contactable_user)

        assert url.startswith("https://sponda.capital/unsubscribe/")
        token = url.rstrip("/").rsplit("/", 1)[-1]
        assert resolve_unsubscribe_token(token) == contactable_user

    def test_headers_declare_rfc_8058_one_click(self, contactable_user, settings):
        settings.UNSUBSCRIBE_BASE_URL = "https://sponda.capital"

        headers = build_unsubscribe_headers(contactable_user)

        assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
        assert headers["List-Unsubscribe"].startswith("<https://sponda.capital/unsubscribe/")
        assert headers["List-Unsubscribe"].endswith(">")

    def test_headers_url_matches_the_page_that_serves_it(self, contactable_user, settings):
        settings.UNSUBSCRIBE_BASE_URL = "https://sponda.capital"

        header_url = build_unsubscribe_headers(contactable_user)["List-Unsubscribe"].strip("<>")
        token = header_url.rstrip("/").rsplit("/", 1)[-1]

        assert header_url.endswith(reverse("unsubscribe", kwargs={"token": token}))


@pytest.mark.django_db
class TestUnsubscribePage:
    def test_get_never_opts_the_user_out(self, client, contactable_user):
        """Link scanners fetch every URL in an email. GET must be inert."""
        response = client.get(unsubscribe_path(contactable_user))

        assert response.status_code == 200
        contactable_user.refresh_from_db()
        assert contactable_user.allow_contact is True

    def test_get_shows_the_address_that_will_be_removed(self, client, contactable_user):
        response = client.get(unsubscribe_path(contactable_user))

        assert contactable_user.email in response.content.decode()

    def test_get_offers_a_post_form(self, client, contactable_user):
        body = client.get(unsubscribe_path(contactable_user)).content.decode()

        assert 'method="post"' in body.lower()

    def test_page_needs_no_login(self, client, contactable_user):
        """The recipient clicks from their inbox, with no Sponda session."""
        response = client.get(unsubscribe_path(contactable_user))

        assert response.status_code == 200
        assert "login" not in response.get("Location", "")

    def test_post_opts_the_user_out(self, client, contactable_user):
        response = client.post(unsubscribe_path(contactable_user))

        assert response.status_code == 200
        contactable_user.refresh_from_db()
        assert contactable_user.allow_contact is False

    def test_one_click_post_needs_no_csrf_token(self, contactable_user):
        """Gmail and Outlook POST straight to the URL, cookieless."""
        provider_client = Client(enforce_csrf_checks=True)

        response = provider_client.post(
            unsubscribe_path(contactable_user),
            data="List-Unsubscribe=One-Click",
            content_type="application/x-www-form-urlencoded",
        )

        assert response.status_code == 200
        contactable_user.refresh_from_db()
        assert contactable_user.allow_contact is False

    def test_post_is_idempotent(self, client, contactable_user):
        path = unsubscribe_path(contactable_user)

        client.post(path)
        response = client.post(path)

        assert response.status_code == 200
        contactable_user.refresh_from_db()
        assert contactable_user.allow_contact is False

    def test_get_tells_an_already_opted_out_user_they_are_out(self, client, contactable_user):
        contactable_user.allow_contact = False
        contactable_user.save(update_fields=["allow_contact"])

        response = client.get(unsubscribe_path(contactable_user))

        assert response.status_code == 200
        assert "não recebe mais" in response.content.decode()

    def test_invalid_token_gets_a_404_page(self, client):
        response = client.get(reverse("unsubscribe", kwargs={"token": "bogus"}))

        assert response.status_code == 404

    def test_post_with_an_invalid_token_is_a_404(self, client):
        response = client.post(reverse("unsubscribe", kwargs={"token": "bogus"}))

        assert response.status_code == 404

    def test_other_methods_are_rejected(self, client, contactable_user):
        response = client.delete(unsubscribe_path(contactable_user))

        assert response.status_code == 405

    def test_page_is_rendered_in_the_user_language(self, client, contactable_user, db):
        english_user = get_user_model().objects.create_user(
            username="reader@example.com",
            email="reader@example.com",
            password="pw123456",
            allow_contact=True,
            language="en",
        )

        portuguese_body = client.get(unsubscribe_path(contactable_user)).content.decode()
        english_body = client.get(unsubscribe_path(english_user)).content.decode()

        assert 'lang="pt-BR"' in portuguese_body
        assert 'lang="en"' in english_body
        assert "Confirmar" in portuguese_body
        assert "Unsubscribe" in english_body

    def test_page_links_to_account_settings(self, client, contactable_user):
        body = client.get(unsubscribe_path(contactable_user)).content.decode()

        assert "/pt/account" in body

    def test_address_is_fenced_off_from_cloudflare_obfuscation(self, client, contactable_user):
        """Cloudflare rewrites bare addresses into "[email protected]" plus a
        decoder script. Here the address is the whole point of the page, and
        it has to survive with JavaScript off, so it sits inside Cloudflare's
        documented opt-out fence.
        """
        body = client.get(unsubscribe_path(contactable_user)).content.decode()

        fenced = body.split("<!--email_off-->")[1].split("<!--email_on-->")[0]
        assert contactable_user.email in fenced

    def test_confirmation_page_says_account_email_keeps_coming(self, client, contactable_user):
        """Opting out of marketing must not read as opting out of password resets."""
        body = client.get(unsubscribe_path(contactable_user)).content.decode()

        assert "senha" in body
