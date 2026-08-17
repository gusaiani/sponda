"""The MCP announcement send.

This is the first marketing email Sponda has ever sent, so the tests here
guard the rules that separate marketing from transactional mail: it never
reaches someone who did not opt in, it always carries a working one-click
unsubscribe, and it refuses to blast anyone unless explicitly told to.
"""
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.email_subjects import MCP_ANNOUNCEMENT_SUBJECTS
from accounts.models import User
from accounts.unsubscribe import resolve_unsubscribe_token

TEMPLATE_DIRECTORY = Path(__file__).resolve().parent.parent / "accounts" / "templates" / "emails"


@pytest.fixture
def opted_in_user(db):
    return User.objects.create_user(
        username="leitor@example.com",
        email="leitor@example.com",
        password="pw123456",
        allow_contact=True,
        language="pt",
    )


@pytest.fixture
def english_user(db):
    return User.objects.create_user(
        username="reader@example.com",
        email="reader@example.com",
        password="pw123456",
        allow_contact=True,
        language="en",
    )


@pytest.fixture
def opted_out_user(db):
    return User.objects.create_user(
        username="saiu@example.com",
        email="saiu@example.com",
        password="pw123456",
        allow_contact=False,
        language="pt",
    )


def run_command(**options):
    output = StringIO()
    call_command("send_mcp_announcement", stdout=output, stderr=output, **options)
    return output.getvalue()


def token_from(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


class TestTargeting:
    def test_sends_to_the_named_recipient(self, opted_in_user):
        run_command(to=[opted_in_user.email])

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [opted_in_user.email]

    def test_refuses_to_run_without_a_target(self, opted_in_user):
        """Neither --to nor --all must never mean "everyone"."""
        with pytest.raises(CommandError):
            run_command()

        assert mail.outbox == []

    def test_unknown_address_is_an_error(self, db):
        with pytest.raises(CommandError):
            run_command(to=["ninguem@example.com"])

        assert mail.outbox == []

    def test_skips_a_recipient_who_opted_out(self, opted_out_user):
        output = run_command(to=[opted_out_user.email])

        assert mail.outbox == []
        assert opted_out_user.email in output

    def test_all_reaches_only_opted_in_users(self, opted_in_user, opted_out_user):
        run_command(all=True)

        assert [message.to[0] for message in mail.outbox] == [opted_in_user.email]

    def test_dry_run_sends_nothing(self, opted_in_user):
        output = run_command(to=[opted_in_user.email], dry_run=True)

        assert mail.outbox == []
        assert opted_in_user.email in output


class TestMessage:
    def test_carries_the_one_click_unsubscribe_headers(self, opted_in_user):
        run_command(to=[opted_in_user.email])

        headers = mail.outbox[0].extra_headers
        assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
        assert headers["List-Unsubscribe"].startswith("<")

    def test_header_token_resolves_back_to_the_recipient(self, opted_in_user):
        run_command(to=[opted_in_user.email])

        url = mail.outbox[0].extra_headers["List-Unsubscribe"].strip("<>")
        assert resolve_unsubscribe_token(token_from(url)) == opted_in_user

    def test_body_carries_the_same_working_unsubscribe_link(self, opted_in_user):
        """The footer link and the header must not drift apart."""
        run_command(to=[opted_in_user.email])

        header_url = mail.outbox[0].extra_headers["List-Unsubscribe"].strip("<>")
        html_body = mail.outbox[0].alternatives[0][0]

        assert "/unsubscribe/" in html_body
        assert resolve_unsubscribe_token(token_from(header_url)) == opted_in_user

    def test_each_recipient_gets_their_own_link(self, opted_in_user, db):
        other_user = User.objects.create_user(
            username="outra@example.com",
            email="outra@example.com",
            password="pw123456",
            allow_contact=True,
            language="pt",
        )

        run_command(all=True)

        resolved = [
            resolve_unsubscribe_token(
                token_from(message.extra_headers["List-Unsubscribe"].strip("<>")),
            )
            for message in mail.outbox
        ]
        assert set(resolved) == {opted_in_user, other_user}

    def test_ships_both_a_plain_and_an_html_body(self, opted_in_user):
        """HTML-only mail scores worse with every spam filter."""
        run_command(to=[opted_in_user.email])

        message = mail.outbox[0]
        assert message.body.strip()
        assert message.alternatives[0][1] == "text/html"

    def test_announces_the_mcp_endpoint(self, opted_in_user):
        run_command(to=[opted_in_user.email])

        html_body = mail.outbox[0].alternatives[0][0]
        assert "https://sponda.capital/api/mcp/" in html_body
        assert "https://sponda.capital/api/mcp/" in mail.outbox[0].body

    def test_subject_is_set(self, opted_in_user):
        run_command(to=[opted_in_user.email])

        assert mail.outbox[0].subject == "O Sponda agora é um servidor MCP"

    def test_falls_back_to_portuguese_for_a_language_with_no_template(self, db):
        german_user = User.objects.create_user(
            username="hallo@example.com",
            email="hallo@example.com",
            password="pw123456",
            allow_contact=True,
            language="de",
        )

        run_command(to=[german_user.email])

        assert len(mail.outbox) == 1
        assert "servidor MCP" in mail.outbox[0].alternatives[0][0]


class TestEnglishEdition:
    """Nearly half the opted-in list reads English, so it is not a fallback."""

    def test_an_english_speaker_gets_the_english_subject(self, english_user):
        run_command(to=[english_user.email])

        assert mail.outbox[0].subject == "Sponda is now an MCP server"

    def test_both_bodies_are_in_english(self, english_user):
        run_command(to=[english_user.email])

        message = mail.outbox[0]
        html_body = message.alternatives[0][0]

        assert "MCP server" in html_body
        assert "MCP server" in message.body
        assert "servidor MCP" not in html_body
        assert "servidor MCP" not in message.body

    def test_declares_english_as_the_document_language(self, english_user):
        """A wrong lang attribute sends screen readers into Portuguese."""
        run_command(to=[english_user.email])

        assert '<html lang="en">' in mail.outbox[0].alternatives[0][0]

    def test_announces_the_mcp_endpoint(self, english_user):
        run_command(to=[english_user.email])

        assert "https://sponda.capital/api/mcp/" in mail.outbox[0].alternatives[0][0]
        assert "https://sponda.capital/api/mcp/" in mail.outbox[0].body

    def test_carries_a_working_unsubscribe_link(self, english_user):
        run_command(to=[english_user.email])

        header_url = mail.outbox[0].extra_headers["List-Unsubscribe"].strip("<>")
        assert resolve_unsubscribe_token(token_from(header_url)) == english_user
        assert "/unsubscribe/" in mail.outbox[0].alternatives[0][0]
        assert "/unsubscribe/" in mail.outbox[0].body

    def test_links_to_the_english_site(self, english_user):
        """A /pt link drops an English reader onto a Portuguese page."""
        run_command(to=[english_user.email])

        base_url = settings.SITE_BASE_URL.rstrip("/")
        for body in (mail.outbox[0].body, mail.outbox[0].alternatives[0][0]):
            assert f"{base_url}/en" in body
            assert f"{base_url}/pt" not in body


class TestTheCallToActionOpensTheModal:
    """The site's MCP modal auto-opens only until it is dismissed once.

    A bare link to the homepage is therefore dead for the readers most likely
    to click it: anyone who already visited and closed the modal. The `?mcp=1`
    parameter forces it open regardless.
    """

    @pytest.mark.parametrize(
        ("language", "locale_path"),
        [("pt", "/pt"), ("en", "/en")],
    )
    def test_the_instructions_link_carries_the_modal_parameter(
        self, db, language, locale_path,
    ):
        user = User.objects.create_user(
            username=f"{language}@example.com",
            email=f"{language}@example.com",
            password="pw123456",
            allow_contact=True,
            language=language,
        )
        base_url = settings.SITE_BASE_URL.rstrip("/")

        run_command(to=[user.email])

        for body in (mail.outbox[0].body, mail.outbox[0].alternatives[0][0]):
            assert f"{base_url}{locale_path}?mcp=1" in body

    def test_the_footer_disclaimer_is_in_english(self, english_user):
        """A Portuguese risk warning in an English email is not a warning."""
        run_command(to=[english_user.email])

        for body in (mail.outbox[0].body, mail.outbox[0].alternatives[0][0]):
            assert "Past performance does not guarantee future results." in body
            assert "Resultados passados" not in body

    def test_the_performance_line_is_in_english(self, english_user):
        run_command(to=[english_user.email])

        for body in (mail.outbox[0].body, mail.outbox[0].alternatives[0][0]):
            assert "Poema cumulative return" in body
            assert "Retorno acumulado" not in body

    def test_leaves_no_unrendered_template_syntax(self, english_user):
        """The Portuguese edition shipped a visible template comment once."""
        run_command(to=[english_user.email])

        for body in (mail.outbox[0].body, mail.outbox[0].alternatives[0][0]):
            assert "{{" not in body
            assert "{%" not in body


class TestTemplateCoverage:
    """A subject with no template raises TemplateDoesNotExist mid-campaign."""

    @pytest.mark.parametrize("language", sorted(MCP_ANNOUNCEMENT_SUBJECTS))
    @pytest.mark.parametrize("extension", ["html", "txt"])
    def test_every_announced_language_has_a_template(self, language, extension):
        template = TEMPLATE_DIRECTORY / f"mcp_announcement_{language}.{extension}"

        assert template.is_file(), f"missing {template.name}"
