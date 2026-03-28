from django.test import TestCase

from apps.core.models import AuditLog, User, UserRegion
from apps.regions.models import Region


def make_region(code='03xx', order=1):
    return Region.objects.create(
        code=code,
        name_ru=f'ДГД {code}',
        name_kz=f'МКД {code}',
        name_en=f'STD {code}',
        order=order,
    )


def make_user(username='testuser', role='viewer'):
    return User.objects.create_user(username=username, password='pass', role=role)


class UserModelTest(TestCase):
    def test_role_choices(self):
        user = make_user(role='admin')
        self.assertEqual(user.role, 'admin')
        self.assertTrue(user.is_admin)
        self.assertFalse(user.is_operator)

    def test_role_properties(self):
        for role, prop in [
            ('admin', 'is_admin'),
            ('operator', 'is_operator'),
            ('reviewer', 'is_reviewer'),
            ('viewer', 'is_viewer'),
        ]:
            user = make_user(username=f'u_{role}', role=role)
            self.assertTrue(getattr(user, prop))

    def test_str(self):
        user = make_user(username='kuanysh', role='operator')
        self.assertIn('kuanysh', str(user))
        self.assertIn('Оператор', str(user))

    def test_mac_address_blank_by_default(self):
        user = make_user()
        self.assertEqual(user.mac_address, '')

    def test_mac_address_stored(self):
        user = make_user()
        user.mac_address = 'AA:BB:CC:DD:EE:FF'
        user.save()
        self.assertEqual(User.objects.get(pk=user.pk).mac_address, 'AA:BB:CC:DD:EE:FF')


class UserRegionTest(TestCase):
    def setUp(self):
        self.user = make_user(role='viewer')
        self.region = make_region()

    def test_create_user_region(self):
        ur = UserRegion.objects.create(user=self.user, region=self.region)
        self.assertEqual(str(ur), f'{self.user} → {self.region}')

    def test_unique_together(self):
        UserRegion.objects.create(user=self.user, region=self.region)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            UserRegion.objects.create(user=self.user, region=self.region)

    def test_m2m_via_user_regions(self):
        UserRegion.objects.create(user=self.user, region=self.region)
        self.assertIn(self.region, self.user.regions.all())


class AuditLogTest(TestCase):
    def setUp(self):
        self.user = make_user(role='operator')

    def test_log_classmethod(self):
        log = AuditLog.log(
            event='login',
            user=self.user,
            details={'ip': '127.0.0.1'},
            ip_address='127.0.0.1',
            mac_address='AA:BB:CC:DD:EE:FF',
        )
        self.assertEqual(log.event, 'login')
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.ip_address, '127.0.0.1')
        self.assertEqual(log.mac_address, 'AA:BB:CC:DD:EE:FF')

    def test_log_without_user(self):
        log = AuditLog.log(event='import')
        self.assertIsNone(log.user)

    def test_ordering_newest_first(self):
        AuditLog.log(event='login', user=self.user)
        AuditLog.log(event='logout', user=self.user)
        logs = list(AuditLog.objects.all())
        self.assertEqual(logs[0].event, 'logout')
        self.assertEqual(logs[1].event, 'login')

    def test_all_event_types_valid(self):
        events = [e[0] for e in AuditLog.EVENTS]
        for event in events:
            log = AuditLog.log(event=event)
            self.assertEqual(log.event, event)

    def test_str(self):
        log = AuditLog.log(event='export', user=self.user)
        self.assertIn('Экспорт', str(log))
