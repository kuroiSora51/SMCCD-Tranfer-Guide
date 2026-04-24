from django.shortcuts import render

from .models import Course, TransferPath


def home(request):
    paths = TransferPath.objects.filter(is_active=True).prefetch_related('areas')
    recent_courses = Course.objects.order_by('name')[:6]
    return render(request, 'guide/home.html', {'paths': paths, 'recent_courses': recent_courses})
