from django.db import migrations


PATHS = [
    {
        'name': 'IGETC',
        'slug': 'igetc',
        'audience': 'UC and CSU general education',
        'summary': 'A broad general education pattern often used by students keeping both UC and CSU transfer options open.',
        'areas': [
            ('Area 1A', 'English Communication', 'Complete English composition.', 'ENGL 100, ENGL 105', 3.0, 1),
            ('Area 1B', 'Critical Thinking', 'Complete critical thinking and composition.', 'ENGL 110, PHIL, COMM', 3.0, 1),
            ('Area 1C', 'Oral Communication', 'Required for CSU-bound students.', 'COMM 110, COMM 127, COMM 130', 3.0, 1),
            ('Area 2', 'Mathematical Concepts', 'Complete transferable college-level mathematics.', 'MATH 120, MATH 200, MATH 251, STAT', 3.0, 1),
            ('Area 3', 'Arts and Humanities', 'Build breadth across arts and humanities.', 'ART, MUS, HIST, PHIL, LIT', 9.0, 3),
            ('Area 4', 'Social and Behavioral Sciences', 'Complete social science coursework across disciplines.', 'PSYC, SOCI, ECON, PLSC, ANTH', 9.0, 3),
            ('Area 5', 'Physical and Biological Sciences', 'Complete physical and biological science, including a lab where required.', 'BIOL, CHEM, PHYS, ASTR, GEOL', 7.0, 2),
            ('Area 6', 'Language Other Than English', 'UC-bound students may need LOTE completion.', 'SPAN, CHIN, JAPN, ASL', 0.0, 1),
        ],
    },
    {
        'name': 'CSU GE Breadth',
        'slug': 'csu-ge-breadth',
        'audience': 'California State University',
        'summary': 'The CSU general education pattern organized around communication, quantitative reasoning, sciences, humanities, social sciences, and lifelong learning.',
        'areas': [
            ('Area A1', 'Oral Communication', 'Complete an oral communication course.', 'COMM 110, COMM 127, COMM 130', 3.0, 1),
            ('Area A2', 'Written Communication', 'Complete freshman composition.', 'ENGL 100, ENGL 105', 3.0, 1),
            ('Area A3', 'Critical Thinking', 'Complete critical thinking.', 'ENGL 110, PHIL, COMM', 3.0, 1),
            ('Area B', 'Scientific Inquiry and Quantitative Reasoning', 'Complete physical science, life science, lab, and quantitative reasoning.', 'MATH, STAT, BIOL, CHEM, PHYS, GEOL', 12.0, 4),
            ('Area C', 'Arts and Humanities', 'Complete arts and humanities breadth.', 'ART, MUS, HIST, PHIL, LIT', 9.0, 3),
            ('Area D', 'Social Sciences', 'Complete social science breadth.', 'PSYC, SOCI, ECON, PLSC, ANTH', 6.0, 2),
            ('Area E', 'Lifelong Learning', 'Complete lifelong learning and self-development.', 'KINE, COUN, HSCI, PSYC', 3.0, 1),
            ('Area F', 'Ethnic Studies', 'Complete ethnic studies.', 'ETHN, SOCI, HIST', 3.0, 1),
        ],
    },
    {
        'name': 'UC 7-Course Pattern',
        'slug': 'uc-7-course-pattern',
        'audience': 'University of California admission baseline',
        'summary': 'The minimum UC admission pattern: English composition, mathematical concepts, and four additional transferable courses from approved subject areas.',
        'areas': [
            ('English 1', 'First English composition course', 'Complete the first transferable English composition course.', 'ENGL 100, ENGL 105', 3.0, 1),
            ('English 2', 'Second English composition course', 'Complete the second transferable English composition or critical thinking course.', 'ENGL 110, ENGL 165', 3.0, 1),
            ('Math', 'Mathematical concepts and quantitative reasoning', 'Complete one transferable mathematics course.', 'MATH 120, MATH 200, MATH 251, STAT', 3.0, 1),
            ('Additional 1', 'Arts and humanities, social science, or science', 'Add the first additional transferable course.', 'ART, HIST, PHIL, PSYC, BIOL, CHEM', 3.0, 1),
            ('Additional 2', 'Arts and humanities, social science, or science', 'Add the second additional transferable course.', 'ART, HIST, PHIL, PSYC, BIOL, CHEM', 3.0, 1),
            ('Additional 3', 'Arts and humanities, social science, or science', 'Add the third additional transferable course.', 'ART, HIST, PHIL, PSYC, BIOL, CHEM', 3.0, 1),
            ('Additional 4', 'Arts and humanities, social science, or science', 'Add the fourth additional transferable course.', 'ART, HIST, PHIL, PSYC, BIOL, CHEM', 3.0, 1),
        ],
    },
]


def seed_paths(apps, schema_editor):
    TransferPath = apps.get_model('guide', 'TransferPath')
    RequirementArea = apps.get_model('guide', 'RequirementArea')
    for path_index, data in enumerate(PATHS):
        path, _ = TransferPath.objects.update_or_create(
            slug=data['slug'],
            defaults={
                'name': data['name'],
                'audience': data['audience'],
                'summary': data['summary'],
                'is_active': True,
            },
        )
        for sequence, (short_label, name, description, hints, units, minimum_courses) in enumerate(data['areas'], start=1):
            RequirementArea.objects.update_or_create(
                path=path,
                name=name,
                defaults={
                    'short_label': short_label,
                    'description': description,
                    'course_hints': hints,
                    'minimum_units': units,
                    'minimum_courses': minimum_courses,
                    'sequence': (path_index * 20) + sequence,
                },
            )


def remove_seeded_paths(apps, schema_editor):
    TransferPath = apps.get_model('guide', 'TransferPath')
    TransferPath.objects.filter(slug__in=[path['slug'] for path in PATHS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('guide', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_paths, remove_seeded_paths),
    ]
