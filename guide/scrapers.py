import html
import json
import re
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

import requests


ASSIST_BASE_URL = 'https://prod.assistng.org'
DEFAULT_ACADEMIC_YEAR_ID = 76
DEFAULT_ACADEMIC_YEAR = '2025-2026'

SMCCD_SOURCES = {
    'CSM': {'name': 'College of San Mateo', 'assist_id': 5},
    'SKYLINE': {'name': 'Skyline College', 'assist_id': 127},
    'CANADA': {'name': 'Canada College', 'assist_id': 68},
}


@dataclass(frozen=True)
class AssistInstitution:
    assist_id: int
    name: str
    code: str
    is_community_college: bool
    category: str | int | None


@dataclass(frozen=True)
class AssistMajorReport:
    key: str
    label: str
    owner_institution_id: int | None
    report_type: str


@dataclass(frozen=True)
class ParsedEquivalence:
    target_course_code: str
    target_course_name: str
    target_units: Decimal | None
    smccd_course_code: str
    smccd_course_name: str
    smccd_units: Decimal | None
    group_conjunction: str
    course_conjunction: str
    conditions: str
    is_articulated: bool
    template_cell_id: str
    source_group_position: int
    source_course_position: int


class AssistClient:
    def __init__(self, delay_seconds=0.15, timeout=30, cache_dir=None, refresh_cache=False):
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.refresh_cache = refresh_cache
        self.session = requests.Session()
        self.session.headers.update({'Accept': 'application/json', 'User-Agent': 'SMCCD-Transfer-Guide/0.1'})
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get(self, path_or_url, params=None, cache_path=None):
        if cache_path and not self.refresh_cache and cache_path.exists():
            return json.loads(cache_path.read_text(encoding='utf-8'))
        url = path_or_url if path_or_url.startswith('http') else f'{ASSIST_BASE_URL}{path_or_url}'
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        return payload

    def institutions(self) -> list[AssistInstitution]:
        rows = self._get('/Institutions/api', cache_path=self._cache_path('institutions.json'))
        institutions = []
        for row in rows:
            name = visible_institution_name(row)
            if not name:
                continue
            institutions.append(
                AssistInstitution(
                    assist_id=row['id'],
                    name=name,
                    code=(row.get('code') or '').strip(),
                    is_community_college=bool(row.get('isCommunityCollege')),
                    category=row.get('category'),
                )
            )
        return institutions

    def major_reports(self, receiving_id, sending_id, academic_year_id=DEFAULT_ACADEMIC_YEAR_ID) -> list[AssistMajorReport]:
        payload = self._get(
            f'/articulation/api/Agreements/Published/for/{receiving_id}/to/{sending_id}/in/{academic_year_id}',
            params={'types': 'Major'},
            cache_path=self._cache_path('agreement_lists', f'{academic_year_id}_{sending_id}_to_{receiving_id}.json'),
        )
        result = payload.get('result') or payload
        reports = result.get('reports') or []
        return [
            AssistMajorReport(
                key=report.get('key', ''),
                label=report.get('label', '').strip(),
                owner_institution_id=report.get('ownerInstitutionId'),
                report_type=report.get('type', ''),
            )
            for report in reports
            if report.get('key') and report.get('label')
        ]

    def agreement_detail(self, key):
        return self._get(
            '/articulation/api/Agreements',
            params={'Key': key},
            cache_path=self._cache_path('agreement_details', f'{safe_filename(key)}.json'),
        ).get('result') or {}

    def _cache_path(self, *parts):
        if not self.cache_dir:
            return None
        return self.cache_dir.joinpath(*parts)


def visible_institution_name(row):
    names = row.get('names') or []
    visible = [item for item in names if not item.get('hideInList') and item.get('name')]
    if visible:
        return sorted(visible, key=lambda item: item.get('fromYear') or 0)[-1]['name']
    return names[0].get('name') if names else ''


def safe_filename(value):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', value).strip('_')


def detail_url(key):
    return f'{ASSIST_BASE_URL}/articulation/api/Agreements?Key={quote(key, safe="")}'


def list_url(receiving_id, sending_id, academic_year_id):
    return (
        f'{ASSIST_BASE_URL}/articulation/api/Agreements/Published/for/'
        f'{receiving_id}/to/{sending_id}/in/{academic_year_id}?types=Major'
    )


def course_code(course):
    if not course:
        return ''
    prefix = (course.get('prefix') or '').strip()
    number = (course.get('courseNumber') or '').strip()
    return f'{prefix} {number}'.strip()


def course_name(course):
    return (course or {}).get('courseTitle') or ''


def course_units(course):
    value = (course or {}).get('minUnits')
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal('0.1'))
    except (InvalidOperation, ValueError):
        return None


def clean_text(value):
    if not value:
        return ''
    value = re.sub(r'<[^>]+>', ' ', str(value))
    value = html.unescape(value)
    return re.sub(r'\s+', ' ', value).strip()


def attribute_text(attributes: Iterable[dict]):
    return '; '.join(clean_text(item.get('content')) for item in attributes or [] if item.get('content'))


def parse_json_field(value, fallback):
    if not value:
        return fallback
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def group_conjunctions_by_start(sending_articulation):
    joins = {}
    for item in sending_articulation.get('courseGroupConjunctions') or []:
        start = item.get('sendingCourseGroupBeginPosition')
        if start is not None:
            joins[start] = item.get('groupConjunction') or ''
    return joins


def parse_major_equivalences(detail) -> list[ParsedEquivalence]:
    articulations = parse_json_field(detail.get('articulations'), [])
    parsed = []
    for template in articulations:
        articulation = template.get('articulation') or {}
        receiving_course = articulation.get('course') or {}
        target_code = course_code(receiving_course)
        if not target_code:
            continue

        sending = articulation.get('sendingArticulation') or {}
        no_articulation_reason = clean_text(sending.get('noArticulationReason'))
        articulation_conditions = attribute_text(articulation.get('attributes'))
        group_joins = group_conjunctions_by_start(sending)
        groups = sending.get('items') or []

        if no_articulation_reason or not groups:
            parsed.append(
                ParsedEquivalence(
                    target_course_code=target_code,
                    target_course_name=course_name(receiving_course),
                    target_units=course_units(receiving_course),
                    smccd_course_code='NO COURSE ARTICULATED',
                    smccd_course_name='',
                    smccd_units=None,
                    group_conjunction='',
                    course_conjunction='',
                    conditions=no_articulation_reason or articulation_conditions,
                    is_articulated=False,
                    template_cell_id=template.get('templateCellId') or '',
                    source_group_position=-1,
                    source_course_position=-1,
                )
            )
            continue

        for group in groups:
            group_position = group.get('position')
            group_join = group_joins.get(group_position, '')
            course_join = group.get('courseConjunction') or ''
            group_conditions = attribute_text(group.get('attributes'))
            for sending_course in group.get('items') or []:
                conditions = '; '.join(
                    item
                    for item in [
                        articulation_conditions,
                        group_conditions,
                        attribute_text(sending_course.get('attributes')),
                    ]
                    if item
                )
                parsed.append(
                    ParsedEquivalence(
                        target_course_code=target_code,
                        target_course_name=course_name(receiving_course),
                        target_units=course_units(receiving_course),
                        smccd_course_code=course_code(sending_course),
                        smccd_course_name=course_name(sending_course),
                        smccd_units=course_units(sending_course),
                        group_conjunction=group_join,
                        course_conjunction=course_join,
                        conditions=conditions,
                        is_articulated=True,
                        template_cell_id=template.get('templateCellId') or '',
                        source_group_position=group_position if group_position is not None else -1,
                        source_course_position=sending_course.get('position')
                        if sending_course.get('position') is not None
                        else -1,
                    )
                )
    return parsed
