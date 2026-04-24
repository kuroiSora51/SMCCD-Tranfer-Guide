from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import (
    Agreement,
    AgreementMajor,
    ArticulationRule,
    Course,
    CourseEquivalence,
    MajorPlan,
    RequirementArea,
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


def _session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _course_query(queryset, query):
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


def _recommended_courses(area):
    courses = Course.objects.none()
    for hint in area.hints:
        courses = courses | Course.objects.filter(name__icontains=hint)
    return courses.distinct().order_by('name', 'college_name')[:8]


def _course_options_text(area):
    if area.hints:
        return ' or '.join(area.hints)
    return 'approved transferable courses'


def _subject_prefix(course_code):
    return (course_code or '').split(' ', 1)[0].strip().upper()


def _agreement_major_query(selected_source, selected_school, major_query=''):
    if not selected_source or not selected_school:
        return AgreementMajor.objects.none()
    majors = AgreementMajor.objects.filter(
        agreement__source_college=selected_source,
        agreement__target_institution=selected_school,
    )
    if major_query:
        majors = majors.filter(name__icontains=major_query)
    return majors.order_by('name')


def home(request):
    paths = TransferPath.objects.filter(is_active=True).prefetch_related('areas')
    recent_courses = Course.objects.order_by('name')[:6]
    return render(request, 'guide/home.html', {'paths': paths, 'recent_courses': recent_courses})


def path_detail(request, slug):
    session_key = _session_key(request)
    path = get_object_or_404(
        TransferPath.objects.prefetch_related('areas'),
        slug=slug,
        is_active=True,
    )
    plan_items = (
        StudentPlanItem.objects.filter(session_key=session_key, path=path)
        .select_related('area', 'course')
        .order_by('area__sequence', 'created_at')
    )
    items_by_area = {}
    for item in plan_items:
        if item.area_id:
            items_by_area.setdefault(item.area_id, []).append(item)
    progress = {
        'complete': plan_items.filter(is_complete=True).count(),
        'total': plan_items.count(),
    }
    progress['percent'] = int((progress['complete'] / progress['total']) * 100) if progress['total'] else 0
    areas = []
    for area in path.areas.all():
        area.plan_items = items_by_area.get(area.id, [])
        area.recommended_courses = _recommended_courses(area)
        complete_count = sum(1 for item in area.plan_items if item.is_complete)
        planned_count = len(area.plan_items)
        area.remaining_courses = max(area.minimum_courses - complete_count, 0)
        area.selected_label = ', '.join(
            item.course.code if item.course_id else item.custom_label for item in area.plan_items
        )
        area.options_text = _course_options_text(area)
        if area.remaining_courses == 0 and area.minimum_courses:
            area.status_label = 'complete'
            area.status_symbol = '✓'
        elif planned_count:
            area.status_label = 'planned'
            area.status_symbol = '○'
        else:
            area.status_label = 'needed'
            area.status_symbol = ''
        areas.append(area)
    majors = MajorPlan.objects.filter(Q(path=path) | Q(path__isnull=True)).prefetch_related('requirements')[:10]
    articulations = ArticulationRule.objects.filter(target_requirement__icontains=path.name)[:10]
    return render(
        request,
        'guide/path_detail.html',
        {
            'path': path,
            'areas': areas,
            'majors': majors,
            'progress': progress,
            'articulations': articulations,
        },
    )


def major_path(request):
    selected_source = request.GET.get('source', '').strip()
    selected_school = request.GET.get('school', '').strip()
    selected_major = request.GET.get('major', '').strip()
    major_query = request.GET.get('major_q', '').strip()
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

    imported_majors = _agreement_major_query(selected_source, selected_school, major_query)
    major_plans = imported_majors.select_related('agreement')

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
        subject = _subject_prefix(equivalence.smccd_course_code)
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
            }
        )

    return render(
        request,
        'guide/major_path.html',
        {
            'source_choices': Agreement.SOURCE_COLLEGE_CHOICES,
            'selected_source': selected_source,
            'schools': schools,
            'imported_schools': imported_school_values,
            'selected_school': selected_school,
            'major_plans': major_plans,
            'selected_major': selected_major,
            'major_query': major_query,
            'direct_equivalents': direct_equivalents,
        },
    )


def add_plan_item(request, slug):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    session_key = _session_key(request)
    path = get_object_or_404(TransferPath, slug=slug, is_active=True)
    area = get_object_or_404(RequirementArea, id=request.POST.get('area_id'), path=path)
    course = None
    course_id = request.POST.get('course_id')
    if course_id:
        course = get_object_or_404(Course, id=course_id)
    custom_label = request.POST.get('custom_label', '').strip()
    notes = request.POST.get('notes', '').strip()
    if not course and not custom_label:
        messages.error(request, 'Choose a course or enter a planned requirement.')
        return redirect(reverse('guide:path_detail', args=[path.slug]) + f'#area-{area.id}')
    StudentPlanItem.objects.create(
        session_key=session_key,
        path=path,
        area=area,
        course=course,
        custom_label=custom_label,
        notes=notes,
    )
    messages.success(request, 'Added to your transfer plan.')
    return redirect(reverse('guide:path_detail', args=[path.slug]) + f'#area-{area.id}')


def toggle_plan_item(request, item_id):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    item = get_object_or_404(StudentPlanItem, id=item_id, session_key=_session_key(request))
    item.is_complete = not item.is_complete
    item.save(update_fields=['is_complete', 'updated_at'])
    return redirect(reverse('guide:path_detail', args=[item.path.slug]) + (f'#area-{item.area_id}' if item.area_id else ''))


def delete_plan_item(request, item_id):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    item = get_object_or_404(StudentPlanItem, id=item_id, session_key=_session_key(request))
    slug = item.path.slug
    area_id = item.area_id
    item.delete()
    return redirect(reverse('guide:path_detail', args=[slug]) + (f'#area-{area_id}' if area_id else ''))


def course_search(request):
    query = request.GET.get('q', '').strip()
    college = request.GET.get('college', '').strip()
    status = request.GET.get('status', '').strip()
    courses = Course.objects.all()
    courses = _course_query(courses, query)
    if college:
        courses = courses.filter(college_name=college)
    if status:
        courses = courses.filter(status=status)
    courses = courses.order_by('name', 'college_name')[:80]
    colleges = Course.objects.values_list('college_name', flat=True).distinct().order_by('college_name')
    statuses = Course.objects.values_list('status', flat=True).distinct().order_by('status')
    return render(
        request,
        'guide/course_search.html',
        {
            'courses': courses,
            'query': query,
            'college': college,
            'status': status,
            'colleges': colleges,
            'statuses': statuses,
        },
    )

# Create your views here.
