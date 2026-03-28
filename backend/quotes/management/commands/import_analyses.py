import json

from django.core.management.base import BaseCommand

from quotes.models import CompanyAnalysis


class Command(BaseCommand):
    help = "Import company analyses from a JSON file (skips duplicates)"

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to JSON file with analyses")

    def handle(self, *args, **options):
        file_path = options["file"]

        with open(file_path) as file:
            analyses = json.load(file)

        created_count = 0
        skipped_count = 0
        for entry in analyses:
            ticker = entry["ticker"].upper()
            content = entry["content"]
            data_quarter = entry["dataQuarter"]

            already_exists = CompanyAnalysis.objects.filter(
                ticker=ticker, data_quarter=data_quarter,
            ).exists()

            if already_exists:
                skipped_count += 1
                continue

            CompanyAnalysis.objects.create(
                ticker=ticker,
                content=content,
                data_quarter=data_quarter,
            )
            created_count += 1
            self.stdout.write(f"  {ticker} ({data_quarter})")

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {created_count} analyses, skipped {skipped_count} existing."
            )
        )
