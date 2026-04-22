from django.contrib import admin

from .models import (
    ArticulationRule,
    Course,
    MajorPlan,
    MajorRequirement,
    Professor,
    RequirementArea,
    StudentPlanItem,
    TransferPath,
)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'crn', 'status', 'units', 'college_name', 'professor_names')
    search_fields = ('name', 'crn', 'professor_names', 'college_name')
    list_filter = ('status', 'college_name')


@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'department', 'rate', 'num_rating')
    search_fields = ('first_name', 'last_name', 'department')


class RequirementAreaInline(admin.TabularInline):
    model = RequirementArea
    extra = 1


@admin.register(TransferPath)
class TransferPathAdmin(admin.ModelAdmin):
    list_display = ('name', 'audience', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [RequirementAreaInline]


class MajorRequirementInline(admin.TabularInline):
    model = MajorRequirement
    extra = 1


@admin.register(MajorPlan)
class MajorPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'institution', 'path')
    search_fields = ('name', 'institution')
    list_filter = ('institution', 'path')
    inlines = [MajorRequirementInline]


@admin.register(ArticulationRule)
class ArticulationRuleAdmin(admin.ModelAdmin):
    list_display = ('smccd_course_text', 'source_course', 'target_institution', 'target_requirement', 'verified_on')
    search_fields = ('smccd_course_text', 'target_institution', 'target_requirement', 'notes')
    list_filter = ('target_institution', 'verified_on')
    autocomplete_fields = ('source_course',)


@admin.register(StudentPlanItem)
class StudentPlanItemAdmin(admin.ModelAdmin):
    list_display = ('session_key', 'path', 'area', 'course', 'custom_label', 'is_complete', 'updated_at')
    search_fields = ('session_key', 'custom_label', 'notes')
    list_filter = ('path', 'is_complete', 'updated_at')
