from django.test import TestCase

from apps.regions.models import Region


class RegionModelTest(TestCase):
    fixtures = ['regions']

    def test_fixture_loaded_20_dgd(self):
        dgd_count = Region.objects.filter(is_summary=False).count()
        self.assertEqual(dgd_count, 20)

    def test_fixture_has_kgd_summary(self):
        summary = Region.objects.filter(is_summary=True)
        self.assertEqual(summary.count(), 1)
        self.assertEqual(summary.first().code, '00xx')

    def test_all_codes_unique(self):
        codes = list(Region.objects.values_list('code', flat=True))
        self.assertEqual(len(codes), len(set(codes)))

    def test_ordering_by_order_field(self):
        regions = list(Region.objects.all())
        orders = [r.order for r in regions]
        self.assertEqual(orders, sorted(orders))

    def test_kgd_is_last(self):
        last = Region.objects.last()
        self.assertTrue(last.is_summary)

    def test_str_returns_name_ru(self):
        region = Region.objects.get(code='62xx')
        self.assertIn('Астана', str(region))

    def test_expected_codes_present(self):
        expected = {
            '03xx', '06xx', '09xx', '15xx', '18xx', '21xx', '27xx',
            '30xx', '33xx', '39xx', '43xx', '45xx', '48xx', '58xx',
            '59xx', '60xx', '62xx', '70xx', '71xx', '72xx', '00xx',
        }
        actual = set(Region.objects.values_list('code', flat=True))
        self.assertEqual(actual, expected)

    def test_name_fields_not_empty(self):
        for region in Region.objects.all():
            self.assertTrue(region.name_ru, f'{region.code}: name_ru пустой')
            self.assertTrue(region.name_kz, f'{region.code}: name_kz пустой')
            self.assertTrue(region.name_en, f'{region.code}: name_en пустой')


class RegionCreateTest(TestCase):
    def test_create_region(self):
        region = Region.objects.create(
            code='99xx',
            name_ru='Тестовый ДГД',
            name_kz='Тест МКД',
            name_en='Test STD',
            order=99,
        )
        self.assertEqual(Region.objects.get(code='99xx').name_ru, 'Тестовый ДГД')
        self.assertFalse(region.is_summary)

    def test_code_unique_constraint(self):
        Region.objects.create(
            code='98xx', name_ru='А', name_kz='А', name_en='A', order=98
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Region.objects.create(
                code='98xx', name_ru='Б', name_kz='Б', name_en='B', order=99
            )
