from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from guide.models import CourseEquivalence, StudentMajorCourseSelection
from guide.services import major_path_context, session_key


def major_path(request):
    selected_source = request.GET.get('source', '').strip()
    selected_school = request.GET.get('school', '').strip()
    selected_major = request.GET.get('major', '').strip()
    major_query = request.GET.get('major_q', '').strip()
    context = major_path_context(selected_source, selected_school, selected_major, major_query)
    saved_equivalence_ids = set(
        StudentMajorCourseSelection.objects.filter(session_key=session_key(request)).values_list('equivalence_id', flat=True)
    )
    for item in context['direct_equivalents']:
        item['already_saved'] = item['equivalence'].id in saved_equivalence_ids
    return render(request, 'major_path_app/major_path.html', context)


def save_major_course(request, equivalence_id):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    equivalence = get_object_or_404(
        CourseEquivalence.objects.select_related('major', 'major__agreement'),
        id=equivalence_id,
    )
    item, created = StudentMajorCourseSelection.objects.get_or_create(
        session_key=session_key(request),
        equivalence=equivalence,
    )
    if created:
        messages.success(request, f'Added {equivalence.smccd_course_code} to major progress.')
    else:
        messages.info(request, f'{equivalence.smccd_course_code} is already in major progress.')
    return redirect(request.POST.get('next') or 'major_path_app:major_path')


def toggle_major_course(request, item_id):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    item = get_object_or_404(StudentMajorCourseSelection, id=item_id, session_key=session_key(request))
    item.is_complete = not item.is_complete
    item.save(update_fields=['is_complete', 'updated_at'])
    return redirect(request.POST.get('next') or 'progress_app:overview')


def delete_major_course(request, item_id):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    item = get_object_or_404(StudentMajorCourseSelection, id=item_id, session_key=session_key(request))
    item.delete()
    return redirect(request.POST.get('next') or 'progress_app:overview')

