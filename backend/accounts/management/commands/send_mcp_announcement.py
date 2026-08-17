"""Send the MCP announcement to users who opted in to contact.

This is marketing mail, so the rules are stricter than for the transactional
senders elsewhere in this app. It never reaches a user with ``allow_contact``
off. Every message carries its own one-click unsubscribe, in the headers and
in the footer. And the command refuses to do anything at all unless the
operator names recipients with ``--to`` or asks for the whole list with
``--all``, so there is no way to blast everyone by forgetting an argument.

Failures are loud on purpose: a campaign that silently drops half its
recipients is worse than one that stops and says so.
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string

from assistant.mcp import MCP_PUBLIC_ENDPOINT_URL

from ...branding import POEMA_DISCLAIMER, POEMA_PERFORMANCE_LINE
from ...email_subjects import MCP_ANNOUNCEMENT_SUBJECTS, mcp_announcement_language
from ...languages import resolve_user_language
from ...models import User
from ...unsubscribe import build_unsubscribe_headers, build_unsubscribe_url

DEFAULT_SITE_BASE_URL = "https://sponda.capital"
DEFAULT_FROM_EMAIL = "noreply@sponda.capital"


class Command(BaseCommand):
    help = "Send the MCP announcement email to opted-in users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            action="append",
            default=[],
            metavar="EMAIL",
            help="Send to this address only. Repeatable.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Send to every user with allow_contact on.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report who would be mailed without sending anything.",
        )

    def handle(self, *args, **options):
        recipients = self._resolve_recipients(options["to"], options["all"])
        sent_count = 0
        skipped_count = 0

        for user in recipients:
            if not user.allow_contact:
                self.stdout.write(f"pulado, optou por não receber: {user.email}")
                skipped_count += 1
                continue

            if options["dry_run"]:
                self.stdout.write(f"seria enviado para: {user.email}")
                continue

            self._send_to(user)
            self.stdout.write(f"enviado para: {user.email}")
            sent_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"enviados: {sent_count} · pulados: {skipped_count}",
            ),
        )

    def _resolve_recipients(self, addresses, send_to_everyone):
        """Turn the command-line target into a concrete list of users."""
        if addresses and send_to_everyone:
            raise CommandError("Use --to ou --all, não os dois.")

        if send_to_everyone:
            return list(User.objects.filter(allow_contact=True).order_by("pk"))

        if not addresses:
            raise CommandError(
                "Informe --to <email> ou --all. Sem alvo explícito nada é enviado.",
            )

        recipients = []
        for address in addresses:
            user = User.objects.filter(email__iexact=address).first()
            if user is None:
                raise CommandError(f"Nenhum usuário com o email {address}.")
            recipients.append(user)
        return recipients

    def _send_to(self, user):
        language = mcp_announcement_language(resolve_user_language(user))
        context = {
            "base_url": _site_base_url(),
            "mcp_endpoint_url": MCP_PUBLIC_ENDPOINT_URL,
            "unsubscribe_url": build_unsubscribe_url(user),
            "poema_performance_line": POEMA_PERFORMANCE_LINE,
            "poema_disclaimer": POEMA_DISCLAIMER,
        }

        message = EmailMultiAlternatives(
            subject=MCP_ANNOUNCEMENT_SUBJECTS[language],
            body=render_to_string(f"emails/mcp_announcement_{language}.txt", context),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", DEFAULT_FROM_EMAIL),
            to=[user.email],
            headers=build_unsubscribe_headers(user),
        )
        message.attach_alternative(
            render_to_string(f"emails/mcp_announcement_{language}.html", context),
            "text/html",
        )
        message.send()


def _site_base_url():
    return getattr(settings, "SITE_BASE_URL", DEFAULT_SITE_BASE_URL).rstrip("/")
