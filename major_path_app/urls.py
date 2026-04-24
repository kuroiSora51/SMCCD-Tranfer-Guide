from django.urls import path

from . import views

app_name = 'major_path_app'

urlpatterns = [
    path('', views.major_path, name='major_path'),
    path('save/<int:equivalence_id>/', views.save_major_course, name='save_major_course'),
    path('saved/<int:item_id>/toggle/', views.toggle_major_course, name='toggle_major_course'),
    path('saved/<int:item_id>/delete/', views.delete_major_course, name='delete_major_course'),
]

