import html
import re
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests


SOURCE_DB = Path('database.db')
TARGET_DB = Path('database_alt.db')
MAX_WORKERS = 8
REQUEST_TIMEOUT = 30

SECTION_HEADINGS = [
    'Course Information',
    'Course Details',
    'Meeting Information',
    'Critical Dates',
    'Section Fees',
]
MEETING_HEADERS = [
    'Instructor',
    'Meeting Date',
    'Meeting Time',
    'Days',
    'Building',
    'Room',
    'Section',
    'Section Description',
]


thread_local = threading.local()


def get_session():
    session = getattr(thread_local, 'session', None)
    if session is None:
        session = requests.Session()
        session.headers.update(
            {
                'User-Agent': 'SMCCD-Transfer-Guide/0.1',
                'Accept': 'text/html,application/xhtml+xml',
            }
        )
        thread_local.session = session
    return session


def strip_tags(value):
    value = re.sub(r'<!--.*?-->', ' ', value, flags=re.S)
    value = re.sub(r'<script.*?</script>', ' ', value, flags=re.S | re.I)
    value = re.sub(r'<style.*?</style>', ' ', value, flags=re.S | re.I)
    value = re.sub(r'</?(br|p|div|h1|h2|h3|h4|h5|tr|td|th|li|ul|ol|section|article)[^>]*>', '\n', value, flags=re.I)
    value = re.sub(r'<[^>]+>', ' ', value)
    value = html.unescape(value)
    value = value.replace('\xa0', ' ')
    value = re.sub(r'[ \t]+', ' ', value)
    value = re.sub(r'\n+', '\n', value)
    return value.strip()


def html_lines(raw_html):
    text = strip_tags(raw_html)
    return [line.strip() for line in text.splitlines() if line.strip()]


def section_slice(lines, start_heading):
    try:
        start = lines.index(start_heading) + 1
    except ValueError:
        return []
    end = len(lines)
    for heading in SECTION_HEADINGS:
        if heading == start_heading:
            continue
        try:
            idx = lines.index(heading, start)
            end = min(end, idx)
        except ValueError:
            pass
    return lines[start:end]


def first_match(pattern, text, flags=0):
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else ''


def parse_title(raw_html):
    title = first_match(r'<title>(.*?)</title>', raw_html, re.I | re.S)
    title = html.unescape(title.replace('\xa0', ' '))
    title = re.sub(r'\s+', ' ', title).strip()
    if '|' in title:
        title = title.split('|', 1)[0].strip()
    if ' - ' in title:
        code, course_title = title.split(' - ', 1)
        return code.strip(), course_title.strip()
    return title.strip(), ''


def parse_college_and_term(raw_html, lines):
    college = first_match(r'at.*?<strong>(.*?)</strong>.*?for', raw_html, re.I | re.S)
    term = first_match(r'</strong>\s*<!-- -->for\s*<!-- -->([^<]+)</p>', raw_html, re.I | re.S)
    if college and term:
        return html.unescape(college), html.unescape(term)

    for i, line in enumerate(lines[:-3]):
        if line == 'at':
            college = lines[i + 1]
        if line == 'for':
            term = lines[i + 1]
        if college and term:
            break
    return college, term


def parse_notes(lines):
    section = section_slice(lines, 'Course Information')
    return '\n'.join(section).strip()


def parse_course_details(lines):
    section = section_slice(lines, 'Course Details')
    details = {}
    i = 0
    while i + 1 < len(section):
        key = section[i].rstrip(':').strip()
        value = section[i + 1].strip()
        details[key] = value
        i += 2
    return details


def parse_meetings(lines):
    section = section_slice(lines, 'Meeting Information')
    if not section:
        return {}

    if section[: len(MEETING_HEADERS)] == MEETING_HEADERS:
        section = section[len(MEETING_HEADERS) :]

    rows = []
    width = len(MEETING_HEADERS)
    for i in range(0, len(section), width):
        chunk = section[i : i + width]
        if len(chunk) != width:
            break
        rows.append(dict(zip(MEETING_HEADERS, chunk)))

    instructors = unique_nonempty(row['Instructor'] for row in rows)
    meeting_dates = unique_nonempty(normalize_date_range(row['Meeting Date']) for row in rows)
    meeting_times = unique_nonempty(row['Meeting Time'] for row in rows)
    meeting_days = unique_nonempty(row['Days'] for row in rows)

    start_times = []
    end_times = []
    for value in meeting_times:
        parts = value.split('-', 1)
        if len(parts) == 2:
            start_times.append(parts[0].strip())
            end_times.append(parts[1].strip())

    return {
        'professor_names': ', '.join(instructors),
        'duration': '; '.join(meeting_dates),
        'time': '; '.join(meeting_times),
        'class_days': '; '.join(meeting_days),
        'start_times': '; '.join(unique_nonempty(start_times)),
        'end_times': '; '.join(unique_nonempty(end_times)),
    }


def unique_nonempty(values):
    seen = []
    for value in values:
        value = (value or '').strip()
        if value and value not in seen:
            seen.append(value)
    return seen


def normalize_date_range(value):
    value = re.sub(r'\s*-\s*', ' - ', value or '')
    return re.sub(r'\s+', ' ', value).strip()


def parse_units(value):
    value = (value or '').strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def scrape_course(source_row):
    course_id, name, crn, status, href, professor_names, class_days, duration, time_value, start_times, end_times, units, college_name, notes, load, capacity, waitlist_load, waitlist_capacity = source_row
    if not href:
        return source_row

    session = get_session()
    response = session.get(href, timeout=REQUEST_TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    raw_html = response.text

    code, course_title = parse_title(raw_html)
    lines = html_lines(raw_html)
    college, _term = parse_college_and_term(raw_html, lines)
    details = parse_course_details(lines)
    meetings = parse_meetings(lines)
    scraped_notes = parse_notes(lines)

    rebuilt_name = name
    if code and course_title:
        rebuilt_name = f'{code}\xa0–\xa0 {course_title}'

    return (
        course_id,
        rebuilt_name,
        crn,
        status,
        href,
        meetings.get('professor_names') or professor_names,
        meetings.get('class_days') or class_days,
        meetings.get('duration') or duration,
        meetings.get('time') or time_value,
        meetings.get('start_times') or start_times,
        meetings.get('end_times') or end_times,
        parse_units(details.get('Units')) if details.get('Units') else units,
        college or college_name,
        scraped_notes or notes,
        load,
        capacity,
        waitlist_load,
        waitlist_capacity,
    )


def create_target_db(source_connection, target_connection):
    cur = source_connection.cursor()
    for table in ('courses', 'professors'):
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
        sql = cur.fetchone()[0]
        target_connection.execute(sql)
    target_connection.commit()


def copy_professors(source_connection, target_connection):
    rows = source_connection.execute('SELECT * FROM professors').fetchall()
    target_connection.executemany(
        'INSERT INTO professors (first_name, last_name, rate, num_rating, department, prof_id) VALUES (?, ?, ?, ?, ?, ?)',
        rows,
    )
    target_connection.commit()


def main():
    if not SOURCE_DB.exists():
        raise SystemExit(f'Missing source database: {SOURCE_DB}')

    if TARGET_DB.exists():
        TARGET_DB.unlink()

    source_connection = sqlite3.connect(SOURCE_DB)
    target_connection = sqlite3.connect(TARGET_DB)
    try:
        create_target_db(source_connection, target_connection)
        copy_professors(source_connection, target_connection)

        course_rows = source_connection.execute(
            '''
            SELECT id, name, CRN, status, href, professor_names, class_days, duration, time,
                   start_times, end_times, units, college_name, notes,
                   load, capacity, waitlist_load, waitlist_capacity
            FROM courses
            ORDER BY id
            '''
        ).fetchall()

        scraped_rows = []
        failures = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(scrape_course, row): row for row in course_rows}
            for index, future in enumerate(as_completed(futures), start=1):
                source_row = futures[future]
                try:
                    result = future.result()
                    if result is None:
                        failures.append((source_row[2], source_row[4], '404 dropped'))
                    else:
                        scraped_rows.append(result)
                except Exception as exc:
                    failures.append((source_row[2], source_row[4], repr(exc)))
                if index % 100 == 0 or index == len(futures):
                    print(f'Processed {index}/{len(futures)} course pages...')

        scraped_rows.sort(key=lambda row: row[0])
        target_connection.executemany(
            '''
            INSERT INTO courses (
                id, name, CRN, status, href, professor_names, class_days, duration, time,
                start_times, end_times, units, college_name, notes,
                load, capacity, waitlist_load, waitlist_capacity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            scraped_rows,
        )
        target_connection.commit()

        print(f'Wrote {TARGET_DB} with {len(scraped_rows)} live course rows.')
        print(f'Copied 688 professor rows.')
        print(f'Dropped/failed course pages: {len(failures)}')
        if failures:
            for crn, href, error in failures[:20]:
                print(f'  CRN {crn} {href} -> {error}')
    finally:
        source_connection.close()
        target_connection.close()


if __name__ == '__main__':
    main()
