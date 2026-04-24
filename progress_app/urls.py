from django.urls import path

from . import views

app_name = 'progress_app'

urlpatterns = [
    path('', views.overview, name='overview'),
]

