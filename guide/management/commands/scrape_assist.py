from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from guide.models import Agreement, AgreementMajor, CourseEquivalence
from guide.scrapers import (
    DEFAULT_ACADEMIC_YEAR,
    DEFAULT_ACADEMIC_YEAR_ID,
    SMCCD_SOURCES,
    AssistClient,
    detail_url,
    list_url,
    parse_major_equivalences,
)


class Command(BaseCommand):
    help = 'Import ASSIST major agreements and direct course equivalences for SMCCD colleges.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sources',
            nargs='+',
            default=list(SMCCD_SOURCES.keys()),
            choices=list(SMCCD_SOURCES.keys()),
            help='SMCCD source colleges to import.',
        )
        parser.add_argument(
            '--targets',
            nargs='+',
            help='Target institution names to import. Defaults to all non-community-college institutions.',
        )
        parser.add_argument('--academic-year-id', type=int, default=DEFAULT_ACADEMIC_YEAR_ID)
        parser.add_argument('--academic-year', default=DEFAULT_ACADEMIC_YEAR)
        parser.add_argument('--target-limit', type=int, help='Limit number of target schools for test runs.')
        parser.add_argument('--major-limit', type=int, help='Limit number of majors per agreement for test runs.')
        parser.add_argument('--delay', type=float, default=0.15, help='Delay between ASSIST HTTP requests.')
        parser.add_argument('--cache-dir', default='assist_json', help='Directory where raw ASSIST JSON responses are kept.')
        parser.add_argument('--refresh-cache', action='store_true', help='Re-download JSON even when a cached file exists.')
        parser.add_argument('--no-prune', action='store_true', help='Do not delete majors absent from the latest ASSIST response.')
        parser.add_argument('--dry-run', action='store_true', help='Fetch and parse without writing to the database.')

    def handle(self, *args, **options):
        client = AssistClient(
            delay_seconds=options['delay'],
            cache_dir=options['cache_dir'],
            refresh_cache=options['refresh_cache'],
        )
        institutions = client.institutions()
        targets = self._target_institutions(institutions, options['targets'], options['target_limit'])
        if not targets:
            raise CommandError('No target institutions matched.')

        total_majors = 0
        total_equivalences = 0
        for source_code in options['sources']:
            source = SMCCD_SOURCES[source_code]
            for target in targets:
                reports = client.major_reports(
                    receiving_id=target.assist_id,
                    sending_id=source['assist_id'],
                    academic_year_id=options['academic_year_id'],
                )
                if options['major_limit']:
                    reports = reports[: options['major_limit']]
                if not reports:
                    self.stdout.write(f'No major agreements: {source["name"]} -> {target.name}')
                    continue

                self.stdout.write(f'{source["name"]} -> {target.name}: {len(reports)} major agreement(s)')
                if options['dry_run']:
                    continue

                agreement = self._upsert_agreement(source_code, source, target, options)
                seen_major_ids = []
                for report in reports:
                    detail = client.agreement_detail(report.key)
                    equivalences = parse_major_equivalences(detail)
                    major = self._upsert_major(agreement, report)
                    seen_major_ids.append(major.id)
                    written = self._replace_equivalences(major, equivalences)
                    total_majors += 1
                    total_equivalences += written
                    self.stdout.write(f'  {report.label}: {written} equivalence row(s)')

                if not options['major_limit'] and not options['no_prune']:
                    AgreementMajor.objects.filter(agreement=agreement).exclude(id__in=seen_major_ids).delete()
                agreement.last_scraped = timezone.now()
                agreement.save(update_fields=['last_scraped', 'updated_at'])

        self.stdout.write(
            self.style.SUCCESS(f'Imported {total_majors} major(s), {total_equivalences} equivalence row(s).')
        )

    def _target_institutions(self, institutions, target_names, target_limit):
        if target_names:
            wanted = {name.lower() for name in target_names}
            targets = [institution for institution in institutions if institution.name.lower() in wanted]
            missing = wanted - {institution.name.lower() for institution in targets}
            if missing:
                raise CommandError(f'Target institution(s) not found in ASSIST: {", ".join(sorted(missing))}')
        else:
            smccd_ids = {source['assist_id'] for source in SMCCD_SOURCES.values()}
            targets = [
                institution
                for institution in institutions
                if not institution.is_community_college and institution.assist_id not in smccd_ids
            ]
        targets = sorted(targets, key=lambda institution: institution.name)
        return targets[:target_limit] if target_limit else targets

    @transaction.atomic
    def _upsert_agreement(self, source_code, source, target, options):
        agreement, _ = Agreement.objects.update_or_create(
            source_college=source_code,
            target_institution=target.name,
            defaults={
                'source_institution_id': source['assist_id'],
                'target_institution_id': target.assist_id,
                'academic_year': options['academic_year'],
                'academic_year_id': options['academic_year_id'],
                'assist_url': list_url(target.assist_id, source['assist_id'], options['academic_year_id']),
            },
        )
        return agreement

    def _upsert_major(self, agreement, report):
        major, _ = AgreementMajor.objects.update_or_create(
            agreement=agreement,
            name=report.label,
            defaults={
                'assist_key': report.key,
                'assist_url': detail_url(report.key),
            },
        )
        return major

    @transaction.atomic
    def _replace_equivalences(self, major, equivalences):
        CourseEquivalence.objects.filter(major=major).delete()
        rows = [
            CourseEquivalence(
                major=major,
                smccd_course_code=item.smccd_course_code[:50],
                smccd_course_name=item.smccd_course_name[:200],
                smccd_units=item.smccd_units,
                target_course_code=item.target_course_code[:50],
                target_course_name=item.target_course_name[:200],
                target_units=item.target_units,
                group_conjunction=item.group_conjunction[:20],
                course_conjunction=item.course_conjunction[:20],
                conditions=item.conditions,
                is_articulated=item.is_articulated,
                raw_template_cell_id=item.template_cell_id[:80],
                source_group_position=item.source_group_position,
                source_course_position=item.source_course_position,
            )
            for item in equivalences
        ]
        CourseEquivalence.objects.bulk_create(rows)
        return len(rows)
