from django.shortcuts import render

from guide.services import progress_snapshot, session_key


def overview(request):
    context = progress_snapshot(session_key(request))
    return render(request, 'progress_app/overview.html', context)
