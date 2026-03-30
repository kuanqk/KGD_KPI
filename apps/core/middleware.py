"""
Middleware безопасности.

MACAddressMiddleware — проверка MAC-адреса клиента при входе.
"""
import json
import logging

from django.http import JsonResponse

logger = logging.getLogger(__name__)

_LOGIN_PATH = '/api/v1/auth/login/'


class MACAddressMiddleware:
    """
    Проверяет MAC-адрес клиента при POST /api/v1/auth/login/.

    Алгоритм:
      1. Читает заголовок X-MAC-Address (нормализует к верхнему регистру).
      2. Извлекает username из тела запроса.
      3. Находит пользователя в БД.
      4. Если User.mac_address пуст → пропускает запрос (не блокирует).
      5. Если User.mac_address заполнен и НЕ совпадает с клиентским → 403
         + запись в AuditLog (event='login', status='blocked').
      6. Если совпадает или MAC-заголовок не передан → пропускает.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.path == _LOGIN_PATH:
            block_response = self._check_mac(request)
            if block_response is not None:
                return block_response
        return self.get_response(request)

    # ── Приватные методы ───────────────────────────────────────────────────

    def _check_mac(self, request):
        """Вернуть JsonResponse(403) если MAC не совпадает, иначе None."""
        client_mac = request.META.get('HTTP_X_MAC_ADDRESS', '').strip().upper()
        if not client_mac:
            return None  # заголовок не передан — не блокируем

        username = self._extract_username(request)
        if not username:
            return None

        user = self._get_user(username)
        if user is None:
            return None  # неизвестный username — пусть auth вернёт 401

        stored_mac = user.mac_address.strip().upper()
        if not stored_mac:
            return None  # MAC не привязан — пропускаем

        if stored_mac == client_mac:
            return None  # совпадает — OK

        # MAC не совпал → блокируем и логируем
        logger.warning(
            'MACAddressMiddleware: MAC mismatch user=%s ip=%s expected=%s got=%s',
            username, _get_ip(request), stored_mac, client_mac,
        )
        self._log_blocked(user, client_mac, _get_ip(request))
        return JsonResponse(
            {'detail': 'Доступ запрещён: MAC-адрес не совпадает.'},
            status=403,
        )

    @staticmethod
    def _extract_username(request) -> str:
        try:
            body = json.loads(request.body)
            return body.get('username', '').strip()
        except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
            return ''

    @staticmethod
    def _get_user(username):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None

    @staticmethod
    def _log_blocked(user, client_mac: str, ip: str | None):
        from apps.core.models import AuditLog
        AuditLog.log(
            event='login',
            user=user,
            ip_address=ip,
            mac_address=client_mac,
            details={
                'status': 'blocked',
                'reason': 'mac_mismatch',
                'client_mac': client_mac,
                'stored_mac': user.mac_address,
            },
        )


def _get_ip(request) -> str | None:
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
