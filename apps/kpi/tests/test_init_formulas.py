from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.kpi.models import KPIFormula

ALL_TYPES = [kpi_type for kpi_type, _ in KPIFormula.KPI_TYPES]


def _rule(thresholds, *, condition, value):
    """Одна строка порога по condition + value (value может повторяться в разных правилах)."""
    for t in thresholds:
        if t['condition'] == condition and t['value'] == value:
            return t
    raise AssertionError(f'No threshold rule: condition={condition!r}, value={value!r}')


class InitFormulasCommandTest(TestCase):
    def _call(self, **kwargs):
        out = StringIO()
        call_command('init_formulas', stdout=out, **kwargs)
        return out.getvalue()

    def test_creates_all_six_formulas(self):
        self._call()
        self.assertEqual(KPIFormula.objects.count(), 6)

    def test_all_kpi_types_present(self):
        self._call()
        created_types = set(KPIFormula.objects.values_list('kpi_type', flat=True))
        self.assertEqual(created_types, set(ALL_TYPES))

    def test_all_version_1(self):
        self._call()
        self.assertFalse(KPIFormula.objects.exclude(version=1).exists())

    def test_all_active(self):
        self._call()
        self.assertFalse(KPIFormula.objects.filter(is_active=False).exists())

    def test_idempotent_no_duplicates(self):
        self._call()
        self._call()
        self.assertEqual(KPIFormula.objects.count(), 6)

    def test_force_flag_recreates(self):
        self._call()
        # изменим конфиг вручную
        f = KPIFormula.objects.get(kpi_type='assessment')
        f.notes = 'изменено вручную'
        f.save()

        self._call(force=True)
        f_new = KPIFormula.objects.get(kpi_type='assessment')
        self.assertNotEqual(f_new.notes, 'изменено вручную')

    # --- Пороги баллов из claude.md ---

    def test_kpi1_assessment_max_score_10(self):
        self._call()
        f = KPIFormula.objects.get(kpi_type='assessment')
        self.assertEqual(f.config['max_score'], 10)

    def test_kpi1_thresholds(self):
        self._call()
        thresholds = KPIFormula.objects.get(kpi_type='assessment').config['thresholds']
        self.assertEqual(_rule(thresholds, condition='gte', value=100)['score'], 10)
        self.assertEqual(_rule(thresholds, condition='gte', value=90)['score'], 5)

    def test_kpi2_collection_max_score_40(self):
        self._call()
        f = KPIFormula.objects.get(kpi_type='collection')
        self.assertEqual(f.config['max_score'], 40)

    def test_kpi2_thresholds_four_levels(self):
        self._call()
        thresholds = KPIFormula.objects.get(kpi_type='collection').config['thresholds']
        self.assertEqual(_rule(thresholds, condition='gte', value=100)['score'], 40)
        self.assertEqual(_rule(thresholds, condition='gte', value=90)['score'], 20)
        self.assertEqual(_rule(thresholds, condition='gte', value=80)['score'], 10)

    def test_kpi3_avg_assessment_max_score_10(self):
        self._call()
        f = KPIFormula.objects.get(kpi_type='avg_assessment')
        self.assertEqual(f.config['max_score'], 10)

    def test_kpi3_no_exclude_form_type_in_config(self):
        self._call()
        f = KPIFormula.objects.get(kpi_type='avg_assessment')
        self.assertNotIn('exclude_form_type', f.config)

    def test_kpi3_no_score_for_80_to_89(self):
        """Диапазон 80–89% даёт 0 баллов, не 5 — пороги не должны включать value=80 со score>0."""
        self._call()
        thresholds = KPIFormula.objects.get(kpi_type='avg_assessment').config['thresholds']
        # Значение 80 не должно давать баллы выше 0
        for t in thresholds:
            if t.get('value') == 80:
                self.assertEqual(t['score'], 0, 'KPI 3: 80% должно давать 0 баллов')

    def test_kpi4_workload_max_score_15(self):
        self._call()
        f = KPIFormula.objects.get(kpi_type='workload')
        self.assertEqual(f.config['max_score'], 15)

    def test_kpi4_thresholds_coefficient(self):
        self._call()
        thresholds = KPIFormula.objects.get(kpi_type='workload').config['thresholds']
        self.assertEqual(_rule(thresholds, condition='gte', value=0.5)['score'], 15)
        self.assertEqual(_rule(thresholds, condition='gte', value=0.4)['score'], 5)

    def test_kpi5_long_inspections_max_score_10(self):
        self._call()
        f = KPIFormula.objects.get(kpi_type='long_inspections')
        self.assertEqual(f.config['max_score'], 10)

    def test_kpi5_threshold_180_days(self):
        self._call()
        f = KPIFormula.objects.get(kpi_type='long_inspections')
        self.assertEqual(f.config['long_threshold_days'], 180)

    def test_kpi5_threshold_lt_20_pct(self):
        self._call()
        thresholds = KPIFormula.objects.get(kpi_type='long_inspections').config['thresholds']
        ten_point = next(t for t in thresholds if t['score'] == 10)
        self.assertEqual(ten_point['condition'], 'lt')
        self.assertEqual(ten_point['value'], 20)

    def test_kpi6_cancelled_max_score_15(self):
        self._call()
        f = KPIFormula.objects.get(kpi_type='cancelled')
        self.assertEqual(f.config['max_score'], 15)

    def test_kpi6_thresholds(self):
        self._call()
        thresholds = KPIFormula.objects.get(kpi_type='cancelled').config['thresholds']
        self.assertEqual(_rule(thresholds, condition='lte', value=1)['score'], 15)
        self.assertEqual(_rule(thresholds, condition='lte', value=2)['score'], 5)

    def test_kpi6_no_two_year_exclusion_in_config(self):
        self._call()
        f = KPIFormula.objects.get(kpi_type='cancelled')
        self.assertNotIn('exclude_older_than_years', f.config)

    def test_kpi6_management_filter_una(self):
        self._call()
        f = KPIFormula.objects.get(kpi_type='cancelled')
        self.assertEqual(f.config['management_filter'], 'УНА')
