import re

from django.db import models


def display_institution_name(name):
    replacements = {
        'University of California, ': 'UC ',
        'California State University, ': 'CSU ',
    }
    for original, replacement in replacements.items():
        if name.startswith(original):
            return name.replace(original, replacement, 1)
    return name


class Course(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.TextField(blank=True, null=True)
    crn = models.TextField(db_column='CRN', blank=True, null=True)
    status = models.TextField(blank=True, null=True)
    href = models.TextField(blank=True, null=True)
    professor_names = models.TextField(blank=True, null=True)
    class_days = models.TextField(blank=True, null=True)
    duration = models.TextField(blank=True, null=True)
    time = models.TextField(blank=True, null=True)
    start_times = models.TextField(blank=True, null=True)
    end_times = models.TextField(blank=True, null=True)
    units = models.FloatField(blank=True, null=True)
    college_name = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    load = models.IntegerField(blank=True, null=True)
    capacity = models.IntegerField(blank=True, null=True)
    waitlist_load = models.IntegerField(blank=True, null=True)
    waitlist_capacity = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'courses'
        ordering = ['name', 'college_name', 'crn']

    def __str__(self):
        return self.name or f'Course {self.pk}'

    @property
    def code(self):
        if not self.name:
            return ''
        cleaned = self.name.replace('\xa0', ' ')
        match = re.match(r'([A-Z]{2,6})\s+([0-9A-Z]+)', cleaned)
        return ' '.join(match.groups()) if match else cleaned.split(' - ')[0]

    @property
    def title(self):
        if not self.name:
            return ''
        cleaned = self.name.replace('\xa0', ' ')
        parts = re.split(r'\s+[–-]\s+', cleaned, maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else cleaned

    @property
    def seats_open(self):
        if self.capacity is None or self.load is None:
            return None
        return max(self.capacity - self.load, 0)


class Professor(models.Model):
    first_name = models.TextField(blank=True, null=True)
    last_name = models.TextField(blank=True, null=True)
    rate = models.FloatField(blank=True, null=True)
    num_rating = models.IntegerField(blank=True, null=True)
    department = models.TextField(blank=True, null=True)
    prof_id = models.TextField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'professors'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.first_name or ""} {self.last_name or ""}'.strip() or self.prof_id


class TransferPath(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    summary = models.TextField()
    audience = models.CharField(max_length=180, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class RequirementArea(models.Model):
    path = models.ForeignKey(TransferPath, on_delete=models.CASCADE, related_name='areas')
    name = models.CharField(max_length=140)
    short_label = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    minimum_units = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    minimum_courses = models.PositiveSmallIntegerField(default=1)
    course_hints = models.TextField(
        blank=True,
        help_text='Comma-separated course codes or prefixes to surface as likely SMCCD matches.',
    )
    sequence = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['path', 'sequence', 'name']
        unique_together = [('path', 'name')]

    def __str__(self):
        return f'{self.path.name}: {self.name}'

    @property
    def hints(self):
        return [hint.strip() for hint in self.course_hints.split(',') if hint.strip()]


class MajorPlan(models.Model):
    name = models.CharField(max_length=140)
    institution = models.CharField(max_length=140, blank=True)
    path = models.ForeignKey(TransferPath, on_delete=models.SET_NULL, null=True, blank=True)
    overview = models.TextField(blank=True)
    assist_url = models.URLField(blank=True)

    class Meta:
        ordering = ['institution', 'name']

    def __str__(self):
        return f'{self.name} - {self.institution}' if self.institution else self.name


class MajorRequirement(models.Model):
    major_plan = models.ForeignKey(MajorPlan, on_delete=models.CASCADE, related_name='requirements')
    name = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    course_hints = models.TextField(blank=True)
    sequence = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['major_plan', 'sequence', 'name']

    def __str__(self):
        return f'{self.major_plan}: {self.name}'


class ArticulationRule(models.Model):
    major_plan = models.ForeignKey(MajorPlan, on_delete=models.CASCADE, null=True, blank=True, related_name='articulations')
    source_course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False)
    smccd_course_text = models.CharField(max_length=160, blank=True)
    target_institution = models.CharField(max_length=140)
    target_requirement = models.CharField(max_length=180)
    assist_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    verified_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['target_institution', 'target_requirement', 'smccd_course_text']

    def __str__(self):
        label = self.source_course.code if self.source_course else self.smccd_course_text
        return f'{label} -> {self.target_institution} {self.target_requirement}'


class Agreement(models.Model):
    COLLEGE_OF_SAN_MATEO = 'CSM'
    SKYLINE = 'SKYLINE'
    CANADA = 'CANADA'
    SOURCE_COLLEGE_CHOICES = [
        (COLLEGE_OF_SAN_MATEO, 'College of San Mateo'),
        (SKYLINE, 'Skyline College'),
        (CANADA, 'Canada College'),
    ]

    source_college = models.CharField(max_length=20, choices=SOURCE_COLLEGE_CHOICES)
    source_institution_id = models.PositiveIntegerField(null=True, blank=True)
    target_institution = models.CharField(max_length=140, db_index=True)
    target_institution_id = models.PositiveIntegerField(null=True, blank=True)
    academic_year = models.CharField(max_length=20, blank=True)
    academic_year_id = models.PositiveIntegerField(null=True, blank=True)
    assist_url = models.URLField(unique=True)
    last_scraped = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['source_college', 'target_institution']
        unique_together = [('source_college', 'target_institution')]
        indexes = [
            models.Index(fields=['source_college', 'target_institution']),
        ]

    def __str__(self):
        return f'{self.get_source_college_display()} -> {self.display_target_institution}'

    @property
    def display_target_institution(self):
        return display_institution_name(self.target_institution)


class AgreementMajor(models.Model):
    agreement = models.ForeignKey(Agreement, on_delete=models.CASCADE, related_name='majors')
    name = models.CharField(max_length=200)
    assist_key = models.CharField(max_length=260, blank=True, db_index=True)
    assist_url = models.URLField(blank=True)

    class Meta:
        ordering = ['agreement', 'name']
        unique_together = [('agreement', 'name')]

    def __str__(self):
        return f'{self.agreement}: {self.name}'


class CourseEquivalence(models.Model):
    major = models.ForeignKey(AgreementMajor, on_delete=models.CASCADE, related_name='equivalences')
    smccd_course_code = models.CharField(max_length=50)
    smccd_course_name = models.CharField(max_length=200, blank=True)
    smccd_units = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    target_course_code = models.CharField(max_length=50)
    target_course_name = models.CharField(max_length=200, blank=True)
    target_units = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    group_conjunction = models.CharField(max_length=20, blank=True)
    course_conjunction = models.CharField(max_length=20, blank=True)
    prerequisites = models.TextField(blank=True, help_text='Prerequisites for the target course')
    conditions = models.TextField(blank=True, help_text='Special conditions, advisories, or no-articulation notes')
    is_articulated = models.BooleanField(default=True)
    raw_template_cell_id = models.CharField(max_length=80, blank=True)
    source_group_position = models.IntegerField(default=-1)
    source_course_position = models.IntegerField(default=-1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            'major',
            'smccd_course_code',
            'target_course_code',
            'raw_template_cell_id',
            'source_group_position',
            'source_course_position',
        ]
        unique_together = [
            (
                'major',
                'raw_template_cell_id',
                'source_group_position',
                'source_course_position',
                'smccd_course_code',
                'target_course_code',
            )
        ]
        indexes = [
            models.Index(fields=['major', 'smccd_course_code']),
            models.Index(fields=['major', 'target_course_code']),
            models.Index(fields=['major', 'raw_template_cell_id']),
        ]

    def __str__(self):
        return f'{self.smccd_course_code} -> {self.target_course_code}'


class StudentPlanItem(models.Model):
    session_key = models.CharField(max_length=80, db_index=True)
    path = models.ForeignKey(TransferPath, on_delete=models.CASCADE)
    area = models.ForeignKey(RequirementArea, on_delete=models.CASCADE, null=True, blank=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, db_constraint=False)
    custom_label = models.CharField(max_length=180, blank=True)
    notes = models.TextField(blank=True)
    is_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        if self.custom_label:
            return self.custom_label
        if self.course_id:
            return str(self.course)
        return 'Plan item'
