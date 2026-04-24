from collections import OrderedDict

from django.db.models import Q

from .models import (
    Agreement,
    AgreementMajor,
    ArticulationRule,
    Course,
    CourseEquivalence,
    MajorPlan,
    StudentCourseSelection,
    StudentMajorCourseSelection,
    StudentPlanItem,
    TransferPath,
    display_institution_name,
)


DEFAULT_TRANSFER_SCHOOLS = [
    'University of California, Berkeley',
    'University of California, Santa Cruz',
    'University of California, Davis',
    'University of California, Irvine',
    'University of California, Los Angeles',
    'University of California, Merced',
    'University of California, Riverside',
    'University of California, San Diego',
    'University of California, Santa Barbara',
    'San Francisco State University',
    'San Jose State University',
]


def session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def course_query(queryset, query):
    if not query:
        return queryset
    terms = [term.strip() for term in query.replace(',', ' ').split() if term.strip()]
    for term in terms:
        queryset = queryset.filter(
            Q(name__icontains=term)
            | Q(crn__icontains=term)
            | Q(professor_names__icontains=term)
            | Q(college_name__icontains=term)
        )
    return queryset


def recommended_courses(area):
    courses = Course.objects.none()
    for hint in area.hints:
        courses = courses | Course.objects.filter(name__icontains=hint)
    return courses.distinct().order_by('name', 'college_name')[:8]


def course_options_text(area):
    if area.hints:
        return ' or '.join(area.hints)
    return 'approved transferable courses'


def subject_prefix(course_code):
    return (course_code or '').split(' ', 1)[0].strip().upper()


def agreement_major_query(selected_source, selected_school, major_query=''):
    if not selected_source or not selected_school:
        return AgreementMajor.objects.none()
    majors = AgreementMajor.objects.filter(
        agreement__source_college=selected_source,
        agreement__target_institution=selected_school,
    )
    if major_query:
        majors = majors.filter(name__icontains=major_query)
    return majors.order_by('name')


def major_path_context(selected_source='', selected_school='', selected_major='', major_query=''):
    imported_school_values = set(Agreement.objects.values_list('target_institution', flat=True))
    if selected_source:
        imported_school_values = set(
            Agreement.objects.filter(source_college=selected_source).values_list('target_institution', flat=True)
        )
    school_values = set(DEFAULT_TRANSFER_SCHOOLS)
    school_values.update(imported_school_values)
    school_values.update(ArticulationRule.objects.exclude(target_institution='').values_list('target_institution', flat=True))
    school_values.update(MajorPlan.objects.exclude(institution='').values_list('institution', flat=True))
    schools = [
        {
            'value': school,
            'label': display_institution_name(school),
            'imported': school in imported_school_values,
        }
        for school in sorted(school_values, key=display_institution_name)
    ]

    major_plans = agreement_major_query(selected_source, selected_school, major_query).select_related('agreement')
    equivalences = CourseEquivalence.objects.select_related('major', 'major__agreement')
    if not selected_source or not selected_school or not selected_major:
        equivalences = equivalences.none()
    else:
        equivalences = equivalences.filter(
            major_id=selected_major,
            major__agreement__source_college=selected_source,
            major__agreement__target_institution=selected_school,
        )

    direct_equivalents = []
    current_subject = None
    subject_band = 0
    for equivalence in equivalences.order_by(
        'major__agreement__target_institution',
        'major__agreement__source_college',
        'major__name',
        'smccd_course_code',
        'target_course_code',
    ):
        subject = subject_prefix(equivalence.smccd_course_code)
        if subject != current_subject:
            current_subject = subject
            subject_band = 1 - subject_band
        direct_equivalents.append(
            {
                'equivalence': equivalence,
                'subject': subject,
                'subject_band': subject_band,
                'school': equivalence.major.agreement.display_target_institution,
                'source': equivalence.major.agreement.get_source_college_display(),
                'major': equivalence.major.name,
                'target_requirement': f'{equivalence.target_course_code} {equivalence.target_course_name}'.strip(),
                'course_code': equivalence.smccd_course_code,
                'course_title': equivalence.smccd_course_name,
                'college': equivalence.major.agreement.get_source_college_display(),
                'status': 'Articulated' if equivalence.is_articulated else 'No course articulated',
                'units': equivalence.smccd_units,
                'conditions': equivalence.conditions,
                'already_saved': False,
            }
        )

    return {
        'source_choices': Agreement.SOURCE_COLLEGE_CHOICES,
        'selected_source': selected_source,
        'schools': schools,
        'imported_schools': imported_school_values,
        'selected_school': selected_school,
        'major_plans': major_plans,
        'selected_major': selected_major,
        'major_query': major_query,
        'direct_equivalents': direct_equivalents,
    }


def progress_snapshot(current_session_key):
    path_items = (
        StudentPlanItem.objects.filter(session_key=current_session_key)
        .select_related('path', 'area', 'course')
        .order_by('path__name', 'area__sequence', 'created_at')
    )
    course_items = (
        StudentCourseSelection.objects.filter(session_key=current_session_key)
        .select_related('course')
        .order_by('course__college_name', 'course__name')
    )
    major_items = (
        StudentMajorCourseSelection.objects.filter(session_key=current_session_key)
        .select_related('equivalence', 'equivalence__major', 'equivalence__major__agreement')
        .order_by(
            'equivalence__smccd_course_code',
            'equivalence__major__agreement__source_college',
            'equivalence__major__agreement__target_institution',
            'equivalence__major__name',
        )
    )

    path_summary = OrderedDict()
    for item in path_items:
        bucket = path_summary.setdefault(
            item.path_id,
            {
                'path': item.path,
                'complete': 0,
                'total': 0,
                'items': [],
            },
        )
        bucket['total'] += 1
        bucket['complete'] += int(item.is_complete)
        bucket['items'].append(item)

    major_grouped = OrderedDict()
    for item in major_items:
        key = (
            item.equivalence.major.agreement.source_college,
            item.equivalence.smccd_course_code,
            item.equivalence.smccd_course_name,
        )
        bucket = major_grouped.setdefault(
            key,
            {
                'course_code': item.equivalence.smccd_course_code,
                'course_title': item.equivalence.smccd_course_name,
                'source_college': item.equivalence.major.agreement.get_source_college_display(),
                'is_complete': item.is_complete,
                'destinations': [],
                'items': [],
            },
        )
        bucket['is_complete'] = bucket['is_complete'] and item.is_complete
        bucket['items'].append(item)
        bucket['destinations'].append(
            {
                'selection_id': item.id,
                'is_complete': item.is_complete,
                'school': item.equivalence.major.agreement.display_target_institution,
                'major': item.equivalence.major.name,
                'target_requirement': f'{item.equivalence.target_course_code} {item.equivalence.target_course_name}'.strip(),
            }
        )

    summary = {
        'paths_total': path_items.count(),
        'paths_complete': path_items.filter(is_complete=True).count(),
        'courses_total': course_items.count(),
        'courses_complete': course_items.filter(is_complete=True).count(),
        'majors_total': major_items.count(),
        'majors_complete': major_items.filter(is_complete=True).count(),
    }
    summary['overall_total'] = summary['paths_total'] + summary['courses_total'] + summary['majors_total']
    summary['overall_complete'] = summary['paths_complete'] + summary['courses_complete'] + summary['majors_complete']
    summary['overall_percent'] = (
        int((summary['overall_complete'] / summary['overall_total']) * 100) if summary['overall_total'] else 0
    )

    return {
        'summary': summary,
        'path_groups': list(path_summary.values()),
        'course_items': list(course_items),
        'major_groups': list(major_grouped.values()),
    }
