from datetime import date

from django.test import TestCase

from apps.core.models import User
from apps.kpi.models import KPISummary
from apps.regions.models import Region
from apps.reports.models import ReportApproval

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERIOD = (date(2025, 1, 1), date(2025, 3, 31))


def make_region(code='03xx', order=1):
    return Region.objects.create(
        code=code, name_ru=f'ДГД {code}',
        name_kz=f'МКД {code}', name_en=f'STD {code}', order=order,
    )


def make_user(username='reviewer', role='reviewer'):
    return User.objects.create_user(username=username, password='pass', role=role)


def make_summary(region, rank=1):
    return KPISummary.objects.create(
        region=region,
        date_from=PERIOD[0],
        date_to=PERIOD[1],
        score_total=75,
        rank=rank,
    )


def make_approval(summary, action='submit', actor=None, comment=''):
    return ReportApproval.objects.create(
        summary=summary,
        action=action,
        actor=actor,
        comment=comment,
    )


# ---------------------------------------------------------------------------
# ReportApproval
# ---------------------------------------------------------------------------

class ReportApprovalTest(TestCase):
    def setUp(self):
        self.region = make_region()
        self.summary = make_summary(self.region)
        self.reviewer = make_user()

    def test_create_submit(self):
        ap = make_approval(self.summary, action='submit', actor=self.reviewer)
        self.assertEqual(ap.action, 'submit')
        self.assertEqual(ap.actor, self.reviewer)
        self.assertEqual(ap.comment, '')

    def test_all_actions_valid(self):
        for i, (action, _) in enumerate(ReportApproval.ACTIONS):
            ap = ReportApproval.objects.create(
                summary=self.summary, action=action,
            )
            self.assertEqual(ap.action, action)
            ap.delete()

    def test_comment_stored(self):
        ap = make_approval(
            self.summary, action='reject',
            actor=self.reviewer,
            comment='Требуется пересчёт KPI 3',
        )
        ap.refresh_from_db()
        self.assertEqual(ap.comment, 'Требуется пересчёт KPI 3')

    def test_actor_nullable(self):
        ap = make_approval(self.summary, actor=None)
        self.assertIsNone(ap.actor)

    def test_actor_set_null_on_user_delete(self):
        user = make_user('tmp')
        ap = make_approval(self.summary, actor=user)
        user.delete()
        ap.refresh_from_db()
        self.assertIsNone(ap.actor)

    def test_cascade_delete_with_summary(self):
        make_approval(self.summary, action='submit')
        make_approval(self.summary, action='approve')
        self.assertEqual(ReportApproval.objects.count(), 2)
        self.summary.delete()
        self.assertEqual(ReportApproval.objects.count(), 0)

    def test_ordering_chronological(self):
        make_approval(self.summary, action='submit')
        make_approval(self.summary, action='approve')
        actions = list(ReportApproval.objects.values_list('action', flat=True))
        self.assertEqual(actions, ['submit', 'approve'])

    def test_str(self):
        ap = make_approval(self.summary, action='approve', actor=self.reviewer)
        s = str(ap)
        self.assertIn('Утверждено', s)
        self.assertIn(self.reviewer.username, s)

    def test_multiple_actions_per_summary(self):
        """Один итог может иметь несколько записей (workflow: submit → reject → submit → approve)."""
        make_approval(self.summary, action='submit')
        make_approval(self.summary, action='reject',  comment='Ошибка в KPI 2')
        make_approval(self.summary, action='submit')
        make_approval(self.summary, action='approve')
        self.assertEqual(ReportApproval.objects.filter(summary=self.summary).count(), 4)
