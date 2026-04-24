from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from guide.models import Course, StudentCourseSelection
from guide.services import course_query, session_key


def course_search(request):
    query = request.GET.get('q', '').strip()
    college = request.GET.get('college', '').strip()
    status = request.GET.get('status', '').strip()
    current_session_key = session_key(request)
    courses = Course.objects.all()
    courses = course_query(courses, query)
    if college:
        courses = courses.filter(college_name=college)
    if status:
        courses = courses.filter(status=status)
    courses = courses.order_by('name', 'college_name')[:80]
    selected_course_ids = set(
        StudentCourseSelection.objects.filter(session_key=current_session_key).values_list('course_id', flat=True)
    )
    colleges = Course.objects.values_list('college_name', flat=True).distinct().order_by('college_name')
    statuses = Course.objects.values_list('status', flat=True).distinct().order_by('status')
    return render(
        request,
        'courses_app/course_search.html',
        {
            'courses': courses,
            'query': query,
            'college': college,
            'status': status,
            'colleges': colleges,
            'statuses': statuses,
            'selected_course_ids': selected_course_ids,
        },
    )


def add_course_selection(request, course_id):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    course = get_object_or_404(Course, id=course_id)
    item, created = StudentCourseSelection.objects.get_or_create(
        session_key=session_key(request),
        course=course,
    )
    if created:
        messages.success(request, f'Added {course.code} to progress.')
    else:
        messages.info(request, f'{course.code} is already in progress.')
    return redirect(request.POST.get('next') or 'courses_app:course_search')


def toggle_course_selection(request, item_id):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    item = get_object_or_404(StudentCourseSelection, id=item_id, session_key=session_key(request))
    item.is_complete = not item.is_complete
    item.save(update_fields=['is_complete', 'updated_at'])
    return redirect(request.POST.get('next') or 'progress_app:overview')


def delete_course_selection(request, item_id):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    item = get_object_or_404(StudentCourseSelection, id=item_id, session_key=session_key(request))
    item.delete()
    return redirect(request.POST.get('next') or 'progress_app:overview')

