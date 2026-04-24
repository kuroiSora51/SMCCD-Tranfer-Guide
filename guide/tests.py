from django.test import SimpleTestCase

from guide.assist_sqlite import parse_detail_stem, parse_list_stem


class AssistSqliteTests(SimpleTestCase):
    def test_parse_list_stem(self):
        parsed = parse_list_stem('76_127_to_1')
        self.assertEqual(
            parsed,
            {
                'academic_year_id': 76,
                'sending_id': 127,
                'receiving_id': 1,
            },
        )

    def test_parse_detail_stem(self):
        parsed = parse_detail_stem('76_127_to_1_Major_25f20291-e740-4bee-a336-321796150396')
        self.assertEqual(parsed['academic_year_id'], 76)
        self.assertEqual(parsed['sending_id'], 127)
        self.assertEqual(parsed['receiving_id'], 1)
        self.assertEqual(parsed['report_type'], 'Major')
        self.assertEqual(parsed['report_id'], '25f20291-e740-4bee-a336-321796150396')
        self.assertEqual(
            parsed['report_key'],
            '76/127/to/1/Major/25f20291-e740-4bee-a336-321796150396',
        )
