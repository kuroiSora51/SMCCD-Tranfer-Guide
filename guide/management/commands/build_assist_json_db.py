from django.core.management.base import BaseCommand, CommandError

from guide.assist_sqlite import build_assist_sqlite


class Command(BaseCommand):
    help = 'Build a standalone SQLite database from the cached ASSIST JSON files.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cache-dir',
            default='assist_json',
            help='Directory containing institutions.json, agreement_lists/, and agreement_details/.',
        )
        parser.add_argument(
            '--output',
            default='assist_json.sqlite3',
            help='Path to the SQLite database file to create.',
        )

    def handle(self, *args, **options):
        try:
            summary = build_assist_sqlite(
                cache_dir=options['cache_dir'],
                output_path=options['output'],
            )
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f'Wrote {summary["output_path"]}'))
        self.stdout.write(f'  institutions: {summary["institutions"]}')
        self.stdout.write(f'  institution names: {summary["institution_names"]}')
        self.stdout.write(f'  agreement lists: {summary["agreement_lists"]}')
        self.stdout.write(f'  agreement reports: {summary["agreement_reports"]}')
        self.stdout.write(f'  agreement details: {summary["agreement_details"]}')
