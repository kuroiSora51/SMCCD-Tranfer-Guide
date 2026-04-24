from django.urls import path

from . import views

app_name = 'guide'

urlpatterns = [
    path('', views.home, name='home'),
    path('major-path/', views.major_path, name='major_path'),
    path('paths/<slug:slug>/', views.path_detail, name='path_detail'),
    path('paths/<slug:slug>/add/', views.add_plan_item, name='add_plan_item'),
    path('plan-items/<int:item_id>/toggle/', views.toggle_plan_item, name='toggle_plan_item'),
    path('plan-items/<int:item_id>/delete/', views.delete_plan_item, name='delete_plan_item'),
    path('courses/', views.course_search, name='course_search'),
]
