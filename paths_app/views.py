from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from guide.models import ArticulationRule, Course, MajorPlan, RequirementArea, StudentPlanItem, TransferPath
from guide.services import course_options_text, recommended_courses, session_key


def path_detail(request, slug):
    current_session_key = session_key(request)
    path = get_object_or_404(
        TransferPath.objects.prefetch_related('areas'),
        slug=slug,
        is_active=True,
    )
    plan_items = (
        StudentPlanItem.objects.filter(session_key=current_session_key, path=path)
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
        area.recommended_courses = recommended_courses(area)
        complete_count = sum(1 for item in area.plan_items if item.is_complete)
        planned_count = len(area.plan_items)
        area.remaining_courses = max(area.minimum_courses - complete_count, 0)
        area.selected_label = ', '.join(
            item.course.code if item.course_id else item.custom_label for item in area.plan_items
        )
        area.options_text = course_options_text(area)
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
        'paths_app/path_detail.html',
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
    current_session_key = session_key(request)
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
        return redirect(reverse('paths_app:path_detail', args=[path.slug]) + f'#area-{area.id}')
    StudentPlanItem.objects.create(
        session_key=current_session_key,
        path=path,
        area=area,
        course=course,
        custom_label=custom_label,
        notes=notes,
    )
    messages.success(request, 'Added to your transfer plan.')
    return redirect(reverse('paths_app:path_detail', args=[path.slug]) + f'#area-{area.id}')


def toggle_plan_item(request, item_id):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    item = get_object_or_404(StudentPlanItem, id=item_id, session_key=session_key(request))
    item.is_complete = not item.is_complete
    item.save(update_fields=['is_complete', 'updated_at'])
    return redirect(reverse('paths_app:path_detail', args=[item.path.slug]) + (f'#area-{item.area_id}' if item.area_id else ''))


def delete_plan_item(request, item_id):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    item = get_object_or_404(StudentPlanItem, id=item_id, session_key=session_key(request))
    slug = item.path.slug
    area_id = item.area_id
    item.delete()
    return redirect(reverse('paths_app:path_detail', args=[slug]) + (f'#area-{area_id}' if area_id else ''))

