"""Push company pages to IndexNow.

Submits the HTML page, per sitemap locale, for every listed company we hold
indicators for and have not submitted before.

Deliberately one-shot per company. Prices move every fifteen minutes and
resubmitting 17,000 companies on every tick is how a host gets deprioritised;
a price tick is not a content change. Run it after new coverage appears, or
with --resubmit after something that genuinely rewrites the pages.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from quotes.indexnow import (
    MAX_URLS_PER_SUBMISSION,
    KeyMismatch,
    batched,
    build_company_urls,
    covered_symbols,
    key_file_url,
    submit,
    verify_key_is_live,
)
from quotes.models import IndexNowSubmission


class Command(BaseCommand):
    help = "Submit company pages to IndexNow (Bing, DuckDuckGo, Yandex, Seznam, Naver)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be sent without sending or recording it.",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Submit at most this many companies.",
        )
        parser.add_argument(
            "--resubmit", action="store_true",
            help="Include companies already submitted before.",
        )

    def handle(self, *args, **options):
        try:
            verify_key_is_live()
        except KeyMismatch as error:
            raise CommandError(str(error)) from error

        already = (
            set()
            if options["resubmit"]
            else set(IndexNowSubmission.objects.values_list("ticker", flat=True))
        )
        symbols = covered_symbols(exclude=already)

        limit = options["limit"]
        if limit:
            symbols = symbols[:limit]

        if not symbols:
            self.stdout.write("Nothing new to submit.")
            return

        urls = build_company_urls(symbols)
        self.stdout.write(
            f"{len(symbols)} companies, {len(urls)} URLs, key at {key_file_url()}",
        )

        if options["dry_run"]:
            for url in urls[:10]:
                self.stdout.write(f"  {url}")
            if len(urls) > 10:
                self.stdout.write(f"  ... and {len(urls) - 10} more")
            self.stdout.write(self.style.WARNING("dry run, nothing sent"))
            return

        accepted = 0
        for batch in batched(urls, MAX_URLS_PER_SUBMISSION):
            if submit(batch):
                accepted += len(batch)
            else:
                self.stdout.write(self.style.ERROR(
                    f"A batch of {len(batch)} URLs was rejected. Stopping.",
                ))
                break

        if accepted == 0:
            self.stdout.write(self.style.ERROR("Nothing was accepted; recorded nothing."))
            return

        # Record only the companies whose URLs actually went through, so a
        # partial run can be finished by running the command again.
        submitted_symbols = symbols[: accepted // len(build_company_urls(["X"]))]
        IndexNowSubmission.objects.bulk_create(
            [IndexNowSubmission(ticker=symbol) for symbol in submitted_symbols],
            ignore_conflicts=True,
        )
        self.stdout.write(self.style.SUCCESS(
            f"Submitted {accepted} URLs for {len(submitted_symbols)} companies.",
        ))
