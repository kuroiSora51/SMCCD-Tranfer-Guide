from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import ArticulationRule, Course, MajorPlan, RequirementArea, StudentPlanItem, TransferPath


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
