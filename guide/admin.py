from django.contrib import admin

from .models import (
    Agreement,
    AgreementMajor,
    ArticulationRule,
    CourseEquivalence,
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
    list_display = ('smccd_course_text', 'source_course', 'major_plan', 'target_institution', 'target_requirement', 'verified_on')
    search_fields = ('smccd_course_text', 'target_institution', 'target_requirement', 'major_plan__name', 'notes')
    list_filter = ('target_institution', 'major_plan', 'verified_on')
    autocomplete_fields = ('source_course', 'major_plan')


class AgreementMajorInline(admin.TabularInline):
    model = AgreementMajor
    extra = 0
    fields = ('name', 'assist_key', 'assist_url')


@admin.register(Agreement)
class AgreementAdmin(admin.ModelAdmin):
    list_display = ('source_college', 'target_institution', 'academic_year', 'last_scraped')
    search_fields = ('target_institution', 'academic_year')
    list_filter = ('source_college', 'academic_year')
    inlines = [AgreementMajorInline]


class CourseEquivalenceInline(admin.TabularInline):
    model = CourseEquivalence
    extra = 0
    fields = (
        'smccd_course_code',
        'smccd_course_name',
        'target_course_code',
        'target_course_name',
        'group_conjunction',
        'course_conjunction',
        'conditions',
        'is_articulated',
    )


@admin.register(AgreementMajor)
class AgreementMajorAdmin(admin.ModelAdmin):
    list_display = ('name', 'agreement')
    search_fields = ('name', 'agreement__target_institution')
    list_filter = ('agreement__source_college', 'agreement__target_institution')
    inlines = [CourseEquivalenceInline]


@admin.register(CourseEquivalence)
class CourseEquivalenceAdmin(admin.ModelAdmin):
    list_display = ('smccd_course_code', 'target_course_code', 'major', 'is_articulated')
    search_fields = (
        'smccd_course_code',
        'smccd_course_name',
        'target_course_code',
        'target_course_name',
        'major__name',
        'major__agreement__target_institution',
    )
    list_filter = ('is_articulated', 'major__agreement__source_college', 'major__agreement__target_institution')


@admin.register(StudentPlanItem)
class StudentPlanItemAdmin(admin.ModelAdmin):
    list_display = ('session_key', 'path', 'area', 'course', 'custom_label', 'is_complete', 'updated_at')
    search_fields = ('session_key', 'custom_label', 'notes')
    list_filter = ('path', 'is_complete', 'updated_at')
