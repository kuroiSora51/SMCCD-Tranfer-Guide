import json
import re
import sqlite3
from pathlib import Path

from guide.scrapers import visible_institution_name


DETAIL_FILE_RE = re.compile(
    r'^(?P<academic_year_id>\d+)_(?P<sending_id>\d+)_to_(?P<receiving_id>\d+)_(?P<report_type>[^_]+)_(?P<report_id>.+)$'
)
LIST_FILE_RE = re.compile(r'^(?P<academic_year_id>\d+)_(?P<sending_id>\d+)_to_(?P<receiving_id>\d+)$')


def parse_detail_stem(stem: str) -> dict:
    match = DETAIL_FILE_RE.match(stem)
    if not match:
        raise ValueError(f'Unrecognized agreement detail filename: {stem}')
    data = match.groupdict()
    data['academic_year_id'] = int(data['academic_year_id'])
    data['sending_id'] = int(data['sending_id'])
    data['receiving_id'] = int(data['receiving_id'])
    data['report_key'] = (
        f"{data['academic_year_id']}/{data['sending_id']}/to/"
        f"{data['receiving_id']}/{data['report_type']}/{data['report_id']}"
    )
    return data


def parse_list_stem(stem: str) -> dict:
    match = LIST_FILE_RE.match(stem)
    if not match:
        raise ValueError(f'Unrecognized agreement list filename: {stem}')
    data = match.groupdict()
    data['academic_year_id'] = int(data['academic_year_id'])
    data['sending_id'] = int(data['sending_id'])
    data['receiving_id'] = int(data['receiving_id'])
    return data


def json_text(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':'))


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        '''
        PRAGMA foreign_keys = ON;

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE institutions_raw (
            file_path TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        );

        CREATE TABLE institutions (
            assist_id INTEGER PRIMARY KEY,
            code TEXT,
            visible_name TEXT,
            is_community_college INTEGER NOT NULL,
            category TEXT,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE institution_names (
            institution_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            from_year INTEGER,
            hide_in_list INTEGER NOT NULL DEFAULT 0,
            has_departments INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (institution_id, name, from_year),
            FOREIGN KEY (institution_id) REFERENCES institutions (assist_id) ON DELETE CASCADE
        );

        CREATE TABLE agreement_lists (
            file_path TEXT PRIMARY KEY,
            academic_year_id INTEGER NOT NULL,
            sending_institution_id INTEGER NOT NULL,
            receiving_institution_id INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        );

        CREATE TABLE agreement_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            report_group TEXT NOT NULL,
            report_key TEXT NOT NULL,
            report_label TEXT,
            owner_institution_id INTEGER,
            report_type TEXT,
            academic_year_id INTEGER NOT NULL,
            sending_institution_id INTEGER NOT NULL,
            receiving_institution_id INTEGER NOT NULL,
            FOREIGN KEY (file_path) REFERENCES agreement_lists (file_path) ON DELETE CASCADE
        );

        CREATE TABLE agreement_details (
            file_path TEXT PRIMARY KEY,
            academic_year_id INTEGER NOT NULL,
            sending_institution_id INTEGER NOT NULL,
            receiving_institution_id INTEGER NOT NULL,
            report_type TEXT NOT NULL,
            report_id TEXT NOT NULL,
            report_key TEXT NOT NULL,
            name TEXT,
            publish_date TEXT,
            receiving_institution_json TEXT,
            sending_institution_json TEXT,
            academic_year_json TEXT,
            catalog_year_json TEXT,
            payload_json TEXT NOT NULL
        );

        CREATE INDEX agreement_reports_key_idx ON agreement_reports(report_key);
        CREATE INDEX agreement_reports_triplet_idx
            ON agreement_reports(academic_year_id, sending_institution_id, receiving_institution_id);
        CREATE INDEX agreement_details_key_idx ON agreement_details(report_key);
        CREATE INDEX agreement_details_triplet_idx
            ON agreement_details(academic_year_id, sending_institution_id, receiving_institution_id);

        CREATE VIEW agreement_major_summary AS
        SELECT
            r.academic_year_id,
            r.sending_institution_id,
            send.visible_name AS sending_institution_name,
            r.receiving_institution_id,
            recv.visible_name AS receiving_institution_name,
            r.report_key,
            r.report_label,
            r.report_type,
            d.name AS detail_name,
            d.publish_date,
            d.file_path AS detail_file_path
        FROM agreement_reports AS r
        LEFT JOIN agreement_details AS d ON d.report_key = r.report_key
        LEFT JOIN institutions AS send ON send.assist_id = r.sending_institution_id
        LEFT JOIN institutions AS recv ON recv.assist_id = r.receiving_institution_id;
        '''
    )


def build_assist_sqlite(cache_dir, output_path) -> dict:
    cache_dir = Path(cache_dir)
    output_path = Path(output_path)

    institutions_path = cache_dir / 'institutions.json'
    list_dir = cache_dir / 'agreement_lists'
    detail_dir = cache_dir / 'agreement_details'

    if not institutions_path.exists():
        raise FileNotFoundError(f'Missing institutions file: {institutions_path}')
    if not list_dir.exists():
        raise FileNotFoundError(f'Missing agreement list directory: {list_dir}')
    if not detail_dir.exists():
        raise FileNotFoundError(f'Missing agreement detail directory: {detail_dir}')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    connection = sqlite3.connect(output_path)
    try:
        initialize_schema(connection)

        institutions_payload = json.loads(institutions_path.read_text(encoding='utf-8'))
        connection.execute(
            'INSERT INTO institutions_raw (file_path, payload_json) VALUES (?, ?)',
            (str(institutions_path.relative_to(cache_dir.parent)), json_text(institutions_payload)),
        )

        institution_rows = []
        institution_name_rows = []
        for row in institutions_payload:
            institution_rows.append(
                (
                    row['id'],
                    (row.get('code') or '').strip(),
                    visible_institution_name(row),
                    int(bool(row.get('isCommunityCollege'))),
                    '' if row.get('category') is None else str(row.get('category')),
                    json_text(row),
                )
            )
            for name in row.get('names') or []:
                institution_name_rows.append(
                    (
                        row['id'],
                        name.get('name') or '',
                        name.get('fromYear'),
                        int(bool(name.get('hideInList'))),
                        int(bool(name.get('hasDepartments'))),
                    )
                )

        connection.executemany(
            '''
            INSERT INTO institutions (
                assist_id, code, visible_name, is_community_college, category, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''',
            institution_rows,
        )
        connection.executemany(
            '''
            INSERT INTO institution_names (
                institution_id, name, from_year, hide_in_list, has_departments
            ) VALUES (?, ?, ?, ?, ?)
            ''',
            institution_name_rows,
        )

        list_rows = []
        report_rows = []
        for path in sorted(list_dir.glob('*.json')):
            meta = parse_list_stem(path.stem)
            payload = json.loads(path.read_text(encoding='utf-8'))
            result = payload.get('result') or {}
            rel_path = str(path.relative_to(cache_dir.parent))
            list_rows.append(
                (
                    rel_path,
                    meta['academic_year_id'],
                    meta['sending_id'],
                    meta['receiving_id'],
                    json_text(payload),
                )
            )
            for group_name in ('reports', 'allReports'):
                for report in result.get(group_name) or []:
                    report_rows.append(
                        (
                            rel_path,
                            group_name,
                            report.get('key') or '',
                            report.get('label') or '',
                            report.get('ownerInstitutionId'),
                            report.get('type') or '',
                            meta['academic_year_id'],
                            meta['sending_id'],
                            meta['receiving_id'],
                        )
                    )

        connection.executemany(
            '''
            INSERT INTO agreement_lists (
                file_path, academic_year_id, sending_institution_id, receiving_institution_id, payload_json
            ) VALUES (?, ?, ?, ?, ?)
            ''',
            list_rows,
        )
        connection.executemany(
            '''
            INSERT INTO agreement_reports (
                file_path, report_group, report_key, report_label, owner_institution_id,
                report_type, academic_year_id, sending_institution_id, receiving_institution_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            report_rows,
        )

        detail_rows = []
        for path in sorted(detail_dir.glob('*.json')):
            meta = parse_detail_stem(path.stem)
            payload = json.loads(path.read_text(encoding='utf-8'))
            result = payload.get('result') or {}
            detail_rows.append(
                (
                    str(path.relative_to(cache_dir.parent)),
                    meta['academic_year_id'],
                    meta['sending_id'],
                    meta['receiving_id'],
                    meta['report_type'],
                    meta['report_id'],
                    meta['report_key'],
                    result.get('name') or '',
                    result.get('publishDate') or '',
                    result.get('receivingInstitution') or '',
                    result.get('sendingInstitution') or '',
                    result.get('academicYear') or '',
                    result.get('catalogYear') or '',
                    json_text(payload),
                )
            )

        connection.executemany(
            '''
            INSERT INTO agreement_details (
                file_path, academic_year_id, sending_institution_id, receiving_institution_id,
                report_type, report_id, report_key, name, publish_date,
                receiving_institution_json, sending_institution_json, academic_year_json,
                catalog_year_json, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            detail_rows,
        )

        metadata_rows = [
            ('cache_dir', str(cache_dir)),
            ('institutions_file', str(institutions_path)),
            ('output_path', str(output_path)),
            ('institutions_count', str(len(institution_rows))),
            ('institution_names_count', str(len(institution_name_rows))),
            ('agreement_lists_count', str(len(list_rows))),
            ('agreement_reports_count', str(len(report_rows))),
            ('agreement_details_count', str(len(detail_rows))),
        ]
        connection.executemany('INSERT INTO metadata (key, value) VALUES (?, ?)', metadata_rows)
        connection.commit()
    finally:
        connection.close()

    return {
        'output_path': output_path,
        'institutions': len(institution_rows),
        'institution_names': len(institution_name_rows),
        'agreement_lists': len(list_rows),
        'agreement_reports': len(report_rows),
        'agreement_details': len(detail_rows),
    }
