from django.urls import path

from . import views

app_name = 'courses_app'

urlpatterns = [
    path('', views.course_search, name='course_search'),
    path('add/<int:course_id>/', views.add_course_selection, name='add_course_selection'),
    path('selected/<int:item_id>/toggle/', views.toggle_course_selection, name='toggle_course_selection'),
    path('selected/<int:item_id>/delete/', views.delete_course_selection, name='delete_course_selection'),
]

